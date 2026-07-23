#!/usr/bin/env python3
"""Accelerated test-only endurance check for the staged game."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.testing.fixture import FixtureSerialClient  # noqa: E402
from pqc_sat.stand.investigation import InvestigationController  # noqa: E402
from pqc_sat.stand.model import InvestigationState, StandConfig  # noqa: E402
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH  # noqa: E402


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def report_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "staged_game_soak.json",
    )
    args = parser.parse_args(argv)
    if args.cycles < 1:
        parser.error("--cycles deve ser positivo")

    config = replace(
        StandConfig.load(args.config),
        pot_poll_interval_seconds=0.001,
        button_debounce_seconds=0.001,
        screen_input_guard_seconds=0.001,
        checkpoint_animation_ms=tuple(
            (stage, 1)
            for stage in ("PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "DEBRIEF")
        ),
        target_max_seconds=2.0,
    )
    client = FixtureSerialClient(args.fixture, config, latency_seconds=0)
    sent_commands: list[str] = []
    button_actions = 0
    pot_changes = 0

    def send(command, *, timeout=None):
        sent_commands.append(command)
        client.send(command, timeout=timeout)

    controller = InvestigationController(config, send, mode="simulated", now=0)
    client.start()
    synthetic_now = 0.0
    started = time.monotonic()
    rss_start = rss_bytes()

    def pump(now):
        for _ in range(30):
            events = client.poll()
            if not events:
                return
            for event_type, payload in events:
                controller.handle_serial_event(event_type, payload, now=now)
        raise RuntimeError("fila da fixture não estabilizou")

    def press() -> None:
        nonlocal button_actions
        if controller.handle_button(now=synthetic_now, origin="test-fixture"):
            button_actions += 1

    pump(synthetic_now)
    while controller.completed_cycles < args.cycles:
        synthetic_now += 0.02
        pump(synthetic_now)
        if controller.input_ready(synthetic_now) and controller.pending is None:
            state = controller.state
            if state is InvestigationState.ATTRACT:
                value = (controller.completed_cycles * 977) % (config.pot_maximum + 1)
                client.set_pot(value)
                pot_changes += 1
                press()
            elif state is InvestigationState.SELECT_MISSION:
                if not controller.pending_choice:
                    mission = config.missions[(controller.cycle_index - 1) % len(config.missions)]
                    controller.handle_action(f"mission:{mission.mission_id}", now=synthetic_now)
                else:
                    press()
            elif state is InvestigationState.SELECT_PROFILE:
                mhz = config.baseline_mhz if controller.cycle_index % 2 else config.limited_mhz
                if not controller.pending_choice:
                    controller.handle_action(f"profile:{mhz}", now=synthetic_now)
                else:
                    press()
            elif state is InvestigationState.SELECT_KEY_MODE:
                mode = controller.KEY_MODES[(controller.cycle_index - 1) % len(controller.KEY_MODES)]
                if not controller.pending_choice:
                    controller.handle_action(f"key:{mode}", now=synthetic_now)
                else:
                    press()
            elif state is InvestigationState.SELECT_GUARD:
                guard = controller.GUARDS[((controller.cycle_index - 1) // 2) % len(controller.GUARDS)]
                if not controller.pending_choice:
                    controller.handle_action(f"guard:{guard}", now=synthetic_now)
                else:
                    press()
            elif state in {
                InvestigationState.PREPARE,
                InvestigationState.PROTECT,
                InvestigationState.TRANSMIT,
                InvestigationState.VERIFY,
                InvestigationState.RETRY,
            } and controller.stage_ready_for_confirmation:
                if state is InvestigationState.PROTECT:
                    value = (client.pot_value + 613) % (config.pot_maximum + 1)
                    client.set_pot(value)
                    controller.set_simulated_pot(value)
                    pot_changes += 1
                press()
            elif state is InvestigationState.DIAGNOSE:
                if not controller.pending_choice:
                    expected = controller._EXPECTED_DIAGNOSIS[controller.incident]
                    controller.handle_action(f"diagnosis:{expected}", now=synthetic_now)
                else:
                    press()
            elif state is InvestigationState.SELECT_RESPONSE:
                if not controller.pending_choice:
                    decision = "RETRY" if controller.cycle_index % 2 else "SAFE_MODE"
                    controller.handle_action(f"response:{decision}", now=synthetic_now)
                else:
                    press()
            elif (
                state is InvestigationState.DEBRIEF
                and controller.end_receipt is not None
                and controller.animation_complete
            ):
                press()

        controller.update(now=synthetic_now)
        pump(synthetic_now)
        if controller.state is InvestigationState.ERROR:
            raise RuntimeError(controller.error_message)
        if synthetic_now > args.cycles * 5:
            raise RuntimeError("limite sintético excedido")

    elapsed = time.monotonic() - started
    game_commands = [command for command in sent_commands if command.startswith("GAME_")]
    report = {
        "schema_version": "pqc-sat-stand-soak-v3",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "test-only-deterministic-fixture",
        "flow": "staged_game",
        "result": "PASS",
        "cycles_requested": args.cycles,
        "cycles_completed": controller.completed_cycles,
        "button_actions": button_actions,
        "pot_changes": pot_changes,
        "commands_total": len(sent_commands),
        "game_commands": len(game_commands),
        "game_begin_commands": sum(command.startswith("GAME_BEGIN ") for command in game_commands),
        "game_retry_commands": sum(command.startswith("GAME_RETRY ") for command in game_commands),
        "rejected_events": controller.rejected_events,
        "ignored_inputs": controller.ignored_inputs,
        "rss_start_bytes": rss_start,
        "rss_end_bytes": rss_bytes(),
        "wall_elapsed_seconds": round(elapsed, 3),
        "synthetic_elapsed_seconds": round(synthetic_now, 3),
        "fixture": report_path(args.fixture),
        "limitations": [
            "Ferramenta exclusiva de teste; não é um modo executável pela aplicação de produção.",
            "Não valida USB, D27, A39, heap real nem continuidade física.",
        ],
    }
    report["rss_growth_bytes"] = max(0, report["rss_end_bytes"] - report["rss_start_bytes"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    client.stop()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
