#!/usr/bin/env python3
"""Build and, only with explicit consent, deploy the staged Wisdom firmware."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.infrastructure.wisdom import discover_wisdom, probe_wisdom  # noqa: E402
from tools.serial_bridge import SerialBridgeError  # noqa: E402


PLATFORMIO_ENV = "robocore_wisdom_esp32_fair"
FIRMWARE_BIN = ROOT / ".pio" / "build" / PLATFORMIO_ENV / "firmware.bin"
DEFAULT_MANIFEST_DIR = ROOT / "logs" / "firmware"
DEPLOY_SCHEMA = "pqc-sat-firmware-deploy-v1"
SESSION_BENCH_CAPABILITY = "FAIR_SESSION_V1"
WOLFSSL_ROOT = ROOT / "firmware" / "lib" / "wolfssl"
WOLFSSL_EXPECTED_VERSION = "5.9.2"
WOLFSSL_EXPECTED_UPSTREAM_COMMIT = "ac01707f552c611fbd135cc723b2682b3e7f80f2"
SOURCE_PATHS = (
    ROOT / "platformio.ini",
    ROOT / "firmware" / "esp32_serial_spike" / "esp32_serial_spike.ino",
    ROOT / "firmware" / "esp32_serial_spike" / "pqc_sat_fair_crypto.cpp",
    ROOT / "firmware" / "esp32_serial_spike" / "pqc_sat_fair_crypto.h",
    ROOT / "firmware" / "esp32_serial_spike" / "user_settings.h",
)


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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)): file_sha256(path)
        for path in SOURCE_PATHS
    }


def directory_sha256(root: Path) -> tuple[int, str]:
    """Hash relative names and contents so a licensed source tree is identifiable."""

    if not root.is_dir():
        raise FileNotFoundError(root)
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        raise ValueError(f"diretório de dependência vazio: {root}")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return len(files), digest.hexdigest()


def wolfssl_provenance() -> dict[str, object]:
    file_count, tree_digest = directory_sha256(WOLFSSL_ROOT)
    return {
        "path": str(WOLFSSL_ROOT.relative_to(ROOT)),
        "expected_version": WOLFSSL_EXPECTED_VERSION,
        "expected_upstream_commit": WOLFSSL_EXPECTED_UPSTREAM_COMMIT,
        "file_count": file_count,
        "tree_sha256": tree_digest,
    }


def git_metadata() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unavailable", True
    return commit, dirty


def write_deployment_manifest(
    *,
    output_dir: Path,
    firmware_size: int,
    firmware_sha256: str,
    port: str,
    baudrate: int,
    pre_upload_handshake: dict[str, str],
    post_upload_handshake: dict[str, str],
) -> Path:
    now = datetime.now(timezone.utc)
    commit, dirty = git_metadata()
    document = {
        "schema_version": DEPLOY_SCHEMA,
        "created_at": now.isoformat(),
        "platformio_env": PLATFORMIO_ENV,
        "firmware_path": str(FIRMWARE_BIN.relative_to(ROOT)),
        "firmware_size": firmware_size,
        "firmware_sha256": firmware_sha256,
        "source_sha256": source_hashes(),
        "dependency_provenance": {
            "wolfssl": wolfssl_provenance(),
        },
        "git_commit": commit,
        "git_dirty": dirty,
        "uploaded": True,
        "verified": True,
        "port": port,
        "port_realpath": os.path.realpath(port),
        "baudrate": baudrate,
        "pre_upload_handshake": dict(pre_upload_handshake),
        "post_upload_handshake": dict(post_upload_handshake),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_port = port.strip("/").replace("/", "-") or "serial"
    destination = output_dir / (
        f"{now.strftime('%Y%m%dT%H%M%SZ')}_firmware_deploy_{safe_port}.json"
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_dir,
        prefix=".firmware_deploy_",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(document, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return destination


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
            device = probe_wisdom(
                port,
                baudrate=baudrate,
                timeout=probe_timeout,
                require_staged_game=True,
                require_fair_kex=True,
                require_session_bench=True,
            )
            return device
        except (OSError, SerialBridgeError) as exc:
            last_error = exc
            time.sleep(0.35)
    raise SerialBridgeError(
        "a Wisdom não confirmou game=STAGED_V1 kex=FAIR_V1 "
        f"session_bench=FAIR_SESSION_V1 após o upload: {last_error or 'timeout'}"
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
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=DEFAULT_MANIFEST_DIR,
        help="diretório do manifesto JSON criado após upload e handshake válidos",
    )
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
                require_fair_kex=False,
                require_session_bench=False,
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

    print("Aguardando reset e HELLO STAGED_V1/FAIR_V1/FAIR_SESSION_V1...", flush=True)
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
        f"proto={verified.handshake['proto']} game={verified.handshake['game']} "
        f"kex={verified.handshake['kex']} "
        f"session_bench={verified.handshake['session_bench']}",
        flush=True,
    )
    try:
        manifest = write_deployment_manifest(
            output_dir=args.manifest_dir,
            firmware_size=size,
            firmware_sha256=digest,
            port=verified.port,
            baudrate=args.baud,
            pre_upload_handshake=device.handshake,
            post_upload_handshake=verified.handshake,
        )
    except OSError as exc:
        print(
            "ERRO: firmware gravado e verificado, mas o manifesto não pôde ser salvo: "
            f"{exc}",
            file=sys.stderr,
        )
        return 2
    print(f"firmware_deploy_manifest={manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
