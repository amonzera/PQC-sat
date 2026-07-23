#!/usr/bin/env python3
"""Repeatable headless render benchmark for the staged-game interface.

This is a host-side engineering benchmark, not a source of hardware or mission
metrics.  Results are machine- and SDL-dependent and should only be compared
under the same environment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

import pygame


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.ui.display import DISPLAY  # noqa: E402
from pqc_sat.ui.game import GamePanel  # noqa: E402
from pqc_sat.ui.scene import CosmicDust, Nebula, ShootingStars, StarField  # noqa: E402
from pqc_sat.ui.theme import C_SPACE_BG  # noqa: E402
from tools.capture_stand_evidence import (  # noqa: E402
    INVESTIGATION_STATE_ORDER,
    build_completed_investigation_controller,
    prepare_investigation_capture_state,
)
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction) - 1))
    return ordered[index]


def render_frame(surface, scene, panel, frame_index: int) -> None:
    stars, nebula, dust, shooting_stars = scene
    t = frame_index / 60.0
    surface.fill(C_SPACE_BG)
    nebula.draw(surface, t)
    stars.draw(surface, t)
    dust.draw(surface)
    shooting_stars.draw(surface)
    panel.draw(surface, t)


def run_benchmark(*, width: int, height: int, frames: int, warmup: int) -> dict[str, object]:
    pygame.init()
    previous_size = DISPLAY.size
    DISPLAY.set_size(width, height)
    surface = pygame.Surface(DISPLAY.size, pygame.SRCALPHA)

    construct_started = time.perf_counter()
    scene = (
        StarField(350),
        Nebula(),
        CosmicDust(50),
        ShootingStars(),
    )
    controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
    panel = GamePanel.for_test(controller)
    construction_ms = (time.perf_counter() - construct_started) * 1000.0

    prepared_state = None

    def render_benchmark_frame(frame_index: int) -> None:
        nonlocal prepared_state
        state = INVESTIGATION_STATE_ORDER[(frame_index // 30) % len(INVESTIGATION_STATE_ORDER)]
        if state != prepared_state:
            prepare_investigation_capture_state(controller, state)
            controller.state = state
            controller.state_entered_at = frame_index / 60.0
            controller.last_clock_at = frame_index / 60.0
            prepared_state = state
        render_frame(surface, scene, panel, frame_index)

    for frame_index in range(warmup):
        render_benchmark_frame(frame_index)

    samples_ms = []
    for frame_index in range(frames):
        started = time.perf_counter()
        render_benchmark_frame(warmup + frame_index)
        samples_ms.append((time.perf_counter() - started) * 1000.0)

    mean_ms = statistics.mean(samples_ms)
    result = {
        "schema_version": "pqc-sat-game-render-benchmark-v1",
        "scope": "host_headless_render_only",
        "flow": "staged_game",
        "resolution": [width, height],
        "frames": frames,
        "warmup_frames": warmup,
        "construction_ms": round(construction_ms, 3),
        "mean_frame_ms": round(mean_ms, 3),
        "median_frame_ms": round(statistics.median(samples_ms), 3),
        "p95_frame_ms": round(percentile(samples_ms, 0.95), 3),
        "max_frame_ms": round(max(samples_ms), 3),
        "estimated_fps": round(1000.0 / mean_ms, 1),
        "frame_budget_60fps_ms": 16.667,
        "within_60fps_mean_budget": mean_ms <= 1000.0 / 60.0,
        "pygame_version": pygame.version.ver,
        "python_version": sys.version.split()[0],
    }
    DISPLAY.set_size(*previous_size)
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark headless do dashboard PQC-SAT")
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--warmup", type=int, default=10)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width e height devem ser positivos")
    if args.frames <= 0 or args.warmup < 0:
        raise SystemExit("frames deve ser positivo e warmup não negativo")
    result = run_benchmark(
        width=args.width,
        height=args.height,
        frames=args.frames,
        warmup=args.warmup,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
