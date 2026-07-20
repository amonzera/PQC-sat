#!/usr/bin/env python3
"""Render one provenance-labelled screenshot for every stand state."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pygame

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
    StandRenderer,
)


STATE_ORDER = (
    DemoState.ATTRACT,
    DemoState.INTRO,
    DemoState.RUN_240,
    DemoState.RUN_80,
    DemoState.SELECT_BIT,
    DemoState.FAULT_NONE,
    DemoState.FAULT_CRC,
    DemoState.SUMMARY,
    DemoState.ERROR,
)


def build_completed_fixture_controller(config_path: Path, fixture_path: Path) -> StandController:
    config = replace(
        StandConfig.load(config_path),
        intro_seconds=0.02,
        comparison_hold_seconds=0.02,
        fault_hold_seconds=0.02,
        pot_poll_interval_seconds=0.01,
        button_debounce_seconds=0.01,
    )
    client = FixtureSerialClient(fixture_path, config, latency_seconds=0)

    def send(command, *, timeout=None):
        client.send(command, timeout=timeout)

    controller = StandController(config, send, mode="simulated", now=0)

    def pump(now):
        for _ in range(20):
            events = client.poll()
            if not events:
                return
            for event_type, payload in events:
                controller.handle_serial_event(event_type, payload, now=now)
        raise RuntimeError("fixture não estabilizou")

    client.start()
    pump(0)
    controller.handle_button(now=0.1, origin="evidence")
    for now in (0.2, 0.3, 0.4, 0.5, 0.51):
        controller.update(now=now)
        pump(now)
    controller.handle_button(now=0.6, origin="evidence")
    pump(0.6)
    for now in (0.7, 0.8):
        controller.update(now=now)
        pump(now)
    if controller.state != DemoState.SUMMARY:
        raise RuntimeError(f"fluxo da fixture terminou em {controller.state.value}")
    client.stop()
    return controller


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "stand" / "evidence" / "states")
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    args = parser.parse_args(argv)

    pygame.init()
    controller = build_completed_fixture_controller(args.config, args.fixture)
    renderer = StandRenderer()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index, state in enumerate(STATE_ORDER):
        controller.state = state
        controller.state_entered_at = 0
        if state == DemoState.ERROR:
            controller.error_message = "Exemplo de recuperação: timeout aguardando a Wisdom"
            controller.connection_status = "USB desconectado — reconecte e tente novamente"
        frame = renderer.render(controller, now=2.0)
        if (args.width, args.height) != frame.get_size():
            frame = pygame.transform.smoothscale(frame, (args.width, args.height))
        output = args.output_dir / f"{index:02d}_{state.value.lower()}_{args.width}x{args.height}.png"
        pygame.image.save(frame, output)
        print(output)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
