#!/usr/bin/env python3
"""Accelerated offline endurance check for the complete stand state machine."""

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

from stand_demo import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    DEFAULT_FIXTURE_PATH,
    DemoState,
    FixtureSerialClient,
    StandConfig,
    StandController,
)


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
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "stand" / "evidence" / "simulated_soak.json")
    args = parser.parse_args(argv)
    if args.cycles < 1:
        parser.error("--cycles deve ser positivo")

    config = replace(
        StandConfig.load(args.config),
        intro_seconds=0.01,
        comparison_hold_seconds=0.01,
        fault_hold_seconds=0.01,
        auto_reset_seconds=0.01,
        pot_poll_interval_seconds=0.001,
        button_debounce_seconds=0.001,
        interaction_timeout_seconds=1.0,
    )
    client = FixtureSerialClient(args.fixture, config, latency_seconds=0)
    sent_commands = []
    button_actions = 0
    pot_changes = 0

    def send(command, *, timeout=None):
        sent_commands.append(command)
        client.send(command, timeout=timeout)

    controller = StandController(config, send, mode="simulated", now=0)
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

    pump(synthetic_now)
    while controller.completed_cycles < args.cycles:
        synthetic_now += 0.02
        pump(synthetic_now)
        if controller.state == DemoState.ATTRACT and controller.pending is None:
            value = (controller.completed_cycles * 977) % (config.pot_maximum + 1)
            client.set_pot(value)
            pot_changes += 1
            if controller.handle_button(now=synthetic_now, origin="soak"):
                button_actions += 1
        elif controller.state == DemoState.SELECT_BIT and controller.substage == "select_ready":
            value = (client.pot_value + 613) % (config.pot_maximum + 1)
            client.set_pot(value)
            pot_changes += 1
            if controller.handle_button(now=synthetic_now, origin="soak"):
                button_actions += 1
        controller.update(now=synthetic_now)
        pump(synthetic_now)
        if controller.state == DemoState.ERROR:
            raise RuntimeError(controller.error_message)
        if synthetic_now > args.cycles * 5:
            raise RuntimeError("limite sintético excedido")

    elapsed = time.monotonic() - started
    rss_end = rss_bytes()
    mission_commands = [command for command in sent_commands if command.startswith("MISSION ")]
    fault_commands = [command for command in sent_commands if command.startswith("FAULT ")]
    report = {
        "schema_version": "pqc-sat-stand-soak-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "simulated-official-fixture",
        "result": "PASS",
        "cycles_requested": args.cycles,
        "cycles_completed": controller.completed_cycles,
        "button_actions": button_actions,
        "pot_changes": pot_changes,
        "commands_total": len(sent_commands),
        "mission_commands": len(mission_commands),
        "fault_commands": len(fault_commands),
        "rejected_events": controller.rejected_events,
        "rss_start_bytes": rss_start,
        "rss_end_bytes": rss_end,
        "rss_growth_bytes": max(0, rss_end - rss_start),
        "wall_elapsed_seconds": round(elapsed, 3),
        "synthetic_elapsed_seconds": round(synthetic_now, 3),
        "fixture": report_path(args.fixture),
        "limitations": [
            "Este teste acelera o relógio da máquina de estados.",
            "Não valida USB, botão físico, potenciômetro físico, heap da placa nem execução contínua em tempo real.",
            "As métricas de missão vêm da fixture da campanha oficial; FAULT é um modelo determinístico offline.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    client.stop()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
