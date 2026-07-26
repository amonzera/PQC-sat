#!/usr/bin/env python3
"""Run short staged-game cycles against a physically confirmed Wisdom."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from pqc_sat.infrastructure.serial_client import WisdomSerialClient  # noqa: E402
from pqc_sat.infrastructure.wisdom import discover_wisdom  # noqa: E402
from pqc_sat.stand.investigation import InvestigationController  # noqa: E402
from pqc_sat.stand.model import InvestigationState, StandConfig  # noqa: E402
from pqc_sat.stand.session import StandSessionLogger  # noqa: E402
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH  # noqa: E402
from pqc_sat.ui.capture import render_game_frame  # noqa: E402
from tools.serial_bridge import SerialBridgeError  # noqa: E402


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="porta explícita; se omitida, sonda todas por HELLO")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--probe-timeout", type=float, default=2.5)
    parser.add_argument("--cycles", type=int, default=1, help="quantidade de partidas físicas")
    parser.add_argument("--overall-timeout", type=float)
    parser.add_argument("--production-timings", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "hardware_smoke.json",
    )
    parser.add_argument(
        "--evidence-log",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "hardware_smoke_cycle.jsonl",
    )
    parser.add_argument("--log-dir", type=Path, default=ROOT / "logs" / "stand" / "smoke")
    args = parser.parse_args(argv)
    if args.cycles <= 0:
        parser.error("--cycles deve ser positivo")

    try:
        device = discover_wisdom(
            args.port,
            baudrate=args.baud,
            timeout=args.probe_timeout,
            require_staged_game=True,
            require_fair_kex=True,
            require_session_bench=True,
        )
    except SerialBridgeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    base_config = StandConfig.load(args.config)
    config = base_config if args.production_timings else replace(
        base_config,
        button_debounce_seconds=0.05,
        screen_input_guard_seconds=0.05,
        checkpoint_animation_ms=tuple(
            (stage, 120)
            for stage in ("PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "DEBRIEF")
        ),
    )
    overall_timeout = args.overall_timeout or (240.0 if args.production_timings else 90.0) * args.cycles
    if overall_timeout <= 0:
        parser.error("--overall-timeout deve ser positivo")

    client = WisdomSerialClient(port=device.port, baudrate=args.baud, timeout=args.timeout)
    logger = StandSessionLogger(args.log_dir, mode="hardware", config=config)
    controller = InvestigationController(config, client.send, mode="hardware", logger=logger)
    pygame.font.init()
    states_seen: list[str] = []
    cycle_summaries: list[dict[str, object]] = []
    pending_snapshot = None
    last_prompt_state = ""
    result = "FAIL"
    error = ""
    started = time.monotonic()
    client.start()
    try:
        while time.monotonic() - started < overall_timeout:
            now = time.monotonic()
            for event_type, payload in client.poll():
                controller.handle_serial_event(event_type, payload, now=now)

            if controller.state.value not in states_seen:
                states_seen.append(controller.state.value)
                render_game_frame(controller, now=now)

            input_ready = controller.input_ready(now)
            if input_ready and not controller.pending_choice:
                if controller.state is InvestigationState.SELECT_MISSION:
                    controller.handle_action("mission:TELEMETRY", now=now)
                elif controller.state is InvestigationState.SELECT_KEY_MODE:
                    controller.handle_action("key:MLKEM", now=now)
                elif controller.state is InvestigationState.SELECT_GUARD:
                    controller.handle_action("guard:CRC32", now=now)
                elif controller.state is InvestigationState.DIAGNOSE and controller.incident is not None:
                    expected = controller._EXPECTED_DIAGNOSIS[controller.incident]
                    controller.handle_action(f"diagnosis:{expected}", now=now)
                elif controller.state is InvestigationState.SELECT_RESPONSE:
                    controller.handle_action("response:RETRY", now=now)

            if controller.state.value != last_prompt_state:
                last_prompt_state = controller.state.value
                print(f"[{last_prompt_state}] pressione o D27 físico somente quando a tela liberar", flush=True)

            if (
                controller.state is InvestigationState.DEBRIEF
                and controller.end_receipt is not None
                and controller.animation_complete
                and pending_snapshot is None
            ):
                pending_snapshot = {
                    "cycle": controller.cycle_index,
                    "selection": asdict(controller.selection) if controller.selection else None,
                    "stages": {stage.value: asdict(value) for stage, value in controller.stage_measurements.items()},
                    "result": asdict(controller.result) if controller.result else None,
                    "retry": asdict(controller.retry_result) if controller.retry_result else None,
                    "diagnosis": controller.selected_diagnosis,
                    "diagnosis_correct": controller.diagnosis_correct,
                    "decision": controller.operational_decision.value if controller.operational_decision else None,
                    "d27_confirmations": controller.button_sequence,
                }

            controller.update(now=now)
            if controller.state is InvestigationState.ERROR:
                error = controller.error_message
                break
            if pending_snapshot is not None and controller.state is InvestigationState.ATTRACT:
                pending_snapshot["duration_seconds"] = controller.last_cycle_duration
                cycle_summaries.append(pending_snapshot)
                pending_snapshot = None
                if controller.completed_cycles >= args.cycles:
                    result = "PASS"
                    break
            time.sleep(0.01)
        else:
            error = "overall timeout"
    finally:
        client.stop()
        logger.close()
        pygame.quit()

    args.evidence_log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logger.path, args.evidence_log)
    report = {
        "schema_version": "pqc-sat-stand-hardware-smoke-v3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "timing_mode": "production-config" if args.production_timings else "accelerated",
        "flow": "staged_game",
        "port": device.port,
        "preflight_handshake": device.handshake,
        "cycles_requested": args.cycles,
        "states_seen": states_seen,
        "handshake": controller.handshake,
        "connection_status": controller.connection_status,
        "completed_cycles": controller.completed_cycles,
        "cycle_summaries": cycle_summaries,
        "rejected_events": controller.rejected_events,
        "ignored_inputs": controller.ignored_inputs,
        "d27_confirmations": controller.button_sequence,
        "error": error or None,
        "session_log": report_path(args.evidence_log),
        "runtime_session_log": report_path(logger.path),
        "limitations": [
            "O script pré-seleciona cartões; todas as transições exigem BUTTON_PING físico.",
            "Este smoke curto não substitui o ensaio físico de 30 partidas e 3 horas.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
