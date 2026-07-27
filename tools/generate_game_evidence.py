#!/usr/bin/env python3
"""Generate test-only staged-game screenshots and a labelled evidence video."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "states_staged_game",
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "staged_game_test_fixture.mp4",
    )
    parser.add_argument(
        "--replay-output-dir",
        type=Path,
        default=ROOT / "docs" / "stand" / "evidence" / "states_staged_game_replay",
    )
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    args = parser.parse_args(argv)

    legacy_tutorial = args.output_dir / f"00b_tutorial_{args.width}x{args.height}.png"
    if legacy_tutorial.exists():
        legacy_tutorial.unlink()

    environment = dict(os.environ)
    environment.setdefault("SDL_VIDEODRIVER", "dummy")
    environment.setdefault("SDL_AUDIODRIVER", "dummy")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "capture_stand_evidence.py"),
            "--output-dir",
            str(args.output_dir),
            "--replay-output-dir",
            str(args.replay_output_dir),
            "--width",
            str(args.width),
            "--height",
            str(args.height),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        print(f"ffmpeg não encontrado; capturas preservadas em {args.output_dir}", file=sys.stderr)
        return 2
    args.video.parent.mkdir(parents=True, exist_ok=True)
    frames = sorted(args.output_dir.glob(f"*_{args.width}x{args.height}.png"))
    for prefix in ("debrief", "debrief_failure"):
        frames.extend(
            args.replay_output_dir / f"{prefix}_{position}_{args.width}x{args.height}.png"
            for position in ("inicio", "meio", "fim")
        )
    missing = [path for path in frames if not path.exists()]
    if missing:
        raise RuntimeError(f"quadros de evidência ausentes: {missing}")
    with tempfile.NamedTemporaryFile("w", suffix=".ffconcat", encoding="utf-8") as manifest:
        manifest.write("ffconcat version 1.0\n")
        for frame in frames:
            escaped = str(frame.resolve()).replace("'", "'\\''")
            manifest.write(f"file '{escaped}'\n")
            manifest.write("duration 4\n")
        escaped_last = str(frames[-1].resolve()).replace("'", "'\\''")
        manifest.write(f"file '{escaped_last}'\n")
        manifest.flush()
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                manifest.name,
                "-vf",
                "fps=5,format=yuv420p",
                "-c:v",
                "mpeg4",
                "-q:v",
                "4",
                "-movflags",
                "+faststart",
                str(args.video),
            ],
            cwd=ROOT,
            check=True,
        )
    print(f"Evidência de fixture de teste: {args.video}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
