#!/usr/bin/env python3
"""Build and, only with explicit consent, deploy the staged Wisdom firmware."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.infrastructure.wisdom import discover_wisdom, probe_wisdom  # noqa: E402
from tools.serial_bridge import SerialBridgeError  # noqa: E402


PLATFORMIO_ENV = "robocore_wisdom_esp32"
FIRMWARE_BIN = ROOT / ".pio" / "build" / PLATFORMIO_ENV / "firmware.bin"


def platformio_command(*extra: str) -> list[str]:
    """Return an argv-only PlatformIO command; no shell or Bash is involved."""

    return [sys.executable, "-m", "platformio", "run", "-e", PLATFORMIO_ENV, *extra]


def run_platformio(*extra: str) -> int:
    completed = subprocess.run(
        platformio_command(*extra),
        cwd=ROOT,
        check=False,
    )
    return int(completed.returncode)


def artifact_summary(path: Path = FIRMWARE_BIN) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def wait_for_staged_firmware(
    port: str,
    *,
    baudrate: int,
    probe_timeout: float,
    verify_timeout: float,
):
    deadline = time.monotonic() + verify_timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return probe_wisdom(
                port,
                baudrate=baudrate,
                timeout=probe_timeout,
                require_staged_game=True,
            )
        except (OSError, SerialBridgeError) as exc:
            last_error = exc
            time.sleep(0.35)
    raise SerialBridgeError(
        f"a Wisdom não confirmou game=STAGED_V1 após o upload: {last_error or 'timeout'}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upload",
        action="store_true",
        help="grava a flash após identificar a Wisdom; sem esta flag apenas compila",
    )
    parser.add_argument("--port", help="porta explícita; se omitida, sonda todas por HELLO")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--probe-timeout", type=float, default=2.5)
    parser.add_argument("--verify-timeout", type=float, default=15.0)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.probe_timeout <= 0 or args.verify_timeout <= 0:
        raise SystemExit("os timeouts devem ser positivos")

    device = None
    if args.upload:
        try:
            # Old project firmware is accepted here only after proving the
            # PQC-SAT Wisdom identity. STAGED_V1 is required after the upload.
            device = discover_wisdom(
                args.port,
                baudrate=args.baud,
                timeout=args.probe_timeout,
                require_staged_game=False,
            )
        except SerialBridgeError as exc:
            print(f"ERRO: upload recusado: {exc}", file=sys.stderr)
            return 2
        print(
            f"Wisdom identificada em {device.port}: "
            f"proto={device.handshake['proto']} game={device.handshake.get('game') or '-'}",
            flush=True,
        )

    print(f"Compilando firmware para {PLATFORMIO_ENV}...", flush=True)
    if run_platformio() != 0:
        return 1
    try:
        size, digest = artifact_summary()
    except OSError as exc:
        print(f"ERRO: firmware.bin não foi produzido: {exc}", file=sys.stderr)
        return 1
    print(f"Firmware pronto: {FIRMWARE_BIN} ({size} bytes, sha256={digest})", flush=True)

    if not args.upload:
        print("Build concluído sem alterar a placa. Use --upload para autorizar a gravação.")
        return 0

    assert device is not None
    print(f"Gravando a Wisdom em {device.port}...", flush=True)
    if run_platformio("-t", "upload", "--upload-port", device.port) != 0:
        return 1

    print("Aguardando reset e HELLO STAGED_V1...", flush=True)
    try:
        verified = wait_for_staged_firmware(
            device.port,
            baudrate=args.baud,
            probe_timeout=args.probe_timeout,
            verify_timeout=args.verify_timeout,
        )
    except SerialBridgeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    print(
        f"PRONTO: {verified.port} confirmou node={verified.handshake['node']} "
        f"proto={verified.handshake['proto']} game={verified.handshake['game']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
