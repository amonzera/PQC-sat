#!/usr/bin/env python3
"""Run one end-to-end stand cycle against real hardware."""

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

from dashboard import DashboardSerialClient, render_dashboard_presentation_frame  # noqa: E402
from stand_demo import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    DemoState,
    StandConfig,
    StandController,
    StandSessionLogger,
)


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--cycles", type=int, default=1, help="quantidade de ciclos administrativos")
    parser.add_argument("--overall-timeout", type=float, help="limite total; padrão ajustado à quantidade de ciclos")
    parser.add_argument(
        "--production-timings",
        action="store_true",
        help="preserva os tempos visuais do config em vez de acelerar o ciclo",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "stand" / "evidence" / "hardware_smoke.json")
    parser.add_argument(
        "--evidence-log",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "hardware_smoke_cycle.jsonl",
    )
    parser.add_argument("--log-dir", type=Path, default=ROOT / "logs" / "stand" / "smoke")
    args = parser.parse_args(argv)
    if args.cycles <= 0:
        parser.error("--cycles deve ser positivo")

    base_config = StandConfig.load(args.config)
    config = base_config if args.production_timings else replace(
        base_config,
        intro_seconds=0.12,
        comparison_hold_seconds=0.12,
        fault_hold_seconds=0.12,
        auto_reset_seconds=0.2,
        pot_poll_interval_seconds=0.05,
        button_debounce_seconds=0.05,
    )
    overall_timeout = (
        args.overall_timeout
        if args.overall_timeout is not None
        else (
            120.0 * args.cycles
            if args.production_timings
            else max(35.0, 5.0 * args.cycles)
        )
    )
    if overall_timeout <= 0:
        parser.error("--overall-timeout deve ser positivo")
    client = DashboardSerialClient(port=args.port, baudrate=args.baud, timeout=args.timeout)
    logger = StandSessionLogger(args.log_dir, mode="hardware", config=config)
    controller = StandController(config, client.send, mode="hardware", logger=logger)
    pygame.font.init()
    states_seen = []
    started = time.monotonic()
    start_pressed = False
    bit_pressed = False
    result = "FAIL"
    error = ""
    captured_measurements = {}
    captured_faults = {}
    captured_selection = None
    captured_duration = None
    cycle_summaries = []
    client.start()
    try:
        while time.monotonic() - started < overall_timeout:
            now = time.monotonic()
            for event_type, payload in client.poll():
                controller.handle_serial_event(event_type, payload, now=now)
            if controller.state.value not in states_seen:
                states_seen.append(controller.state.value)
                render_dashboard_presentation_frame(controller, now=now)
            if (
                controller.ready
                and controller.state == DemoState.ATTRACT
                and controller.pending is None
                and not start_pressed
            ):
                start_pressed = controller.handle_button(now=now, origin="hardware-smoke-driver")
            if (
                controller.state == DemoState.SELECT_BIT
                and controller.substage == "select_ready"
                and controller.selection is not None
                and controller.pending is None
                and not bit_pressed
            ):
                bit_pressed = controller.handle_button(now=now, origin="hardware-smoke-driver")
            controller.update(now=now)
            if controller.state == DemoState.ERROR:
                error = controller.error_message
                break
            if controller.state == DemoState.SUMMARY:
                if controller.state.value not in states_seen:
                    states_seen.append(controller.state.value)
                    render_dashboard_presentation_frame(controller, now=now)
                captured_measurements = {key: asdict(value) for key, value in controller.measurements.items()}
                captured_faults = {key: asdict(value) for key, value in controller.fault_results.items()}
                captured_selection = asdict(controller.selection) if controller.selection else None
                captured_duration = controller.last_cycle_duration
                cycle_summaries.append(
                    {
                        "cycle": controller.completed_cycles,
                        "duration_seconds": captured_duration,
                        "selection": captured_selection,
                        "measurements": {
                            key: {
                                "elapsed_us": value["elapsed_us"],
                                "bytes_total": value["bytes_total"],
                                "result": value["result"],
                                "source": value["source"],
                                "payload_hex": value["payload_hex"],
                            }
                            for key, value in captured_measurements.items()
                        },
                        "faults": {
                            key: {
                                "byte_index": value["byte_index"],
                                "bit_mask": value["bit_mask"],
                                "before_byte": value["before_byte"],
                                "after_byte": value["after_byte"],
                                "result": value["result"],
                                "source": value["source"],
                            }
                            for key, value in captured_faults.items()
                        },
                    }
                )
                if controller.completed_cycles >= args.cycles:
                    result = "PASS"
                    break
                controller.reset_to_attract(reason="hardware_smoke_next_cycle", now=now)
                start_pressed = False
                bit_pressed = False
            time.sleep(0.01)
        else:
            error = "overall timeout"

        if result == "PASS":
            controller.reset_to_attract(reason="hardware_smoke_complete")
            restore_deadline = time.monotonic() + 2.0
            while controller.pending is not None and time.monotonic() < restore_deadline:
                now = time.monotonic()
                for event_type, payload in client.poll():
                    controller.handle_serial_event(event_type, payload, now=now)
                controller.update(now=now)
                time.sleep(0.01)
    finally:
        client.stop()
        logger.close()
        pygame.quit()

    args.evidence_log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logger.path, args.evidence_log)

    report = {
        "schema_version": "pqc-sat-stand-hardware-smoke-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "timing_mode": "production-config" if args.production_timings else "accelerated",
        "port": args.port,
        "cycles_requested": args.cycles,
        "states_seen": states_seen,
        "handshake": controller.handshake,
        "connection_status": controller.connection_status,
        "completed_cycles": controller.completed_cycles,
        "cycle_duration_seconds": captured_duration,
        "measurements": captured_measurements,
        "faults": captured_faults,
        "selection": captured_selection,
        "cycle_summaries": cycle_summaries,
        "rejected_events": controller.rejected_events,
        "error": error or None,
        "session_log": report_path(args.evidence_log),
        "runtime_session_log": report_path(logger.path),
        "limitations": [
            "O driver administrativo acionou as duas transições de cada ciclo; BUTTON_PING físico é validado separadamente.",
            (
                "Os tempos visuais vieram da configuração de produção."
                if args.production_timings
                else "Os tempos visuais foram reduzidos; as métricas criptográficas são respostas reais da Wisdom."
            ),
            "Os ciclos administrativos não substituem o ensaio físico de 30 ciclos/3 horas.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
