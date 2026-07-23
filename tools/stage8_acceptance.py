#!/usr/bin/env python3
"""Stage 8 hardware acceptance runner for PQC-SAT.

This script keeps the final presentation checks reproducible without moving
advanced bench commands into the visitor game interface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.final_metrics_battery import send_record, utc_now_iso, write_document
from tools.kex_metrics_battery import (
    DEFAULT_PAYLOAD,
    DEFAULT_PAYLOAD_HEX,
    PROFILE_CPU,
    SESSION_BENCH_CAPABILITY,
    payload_of,
    validate_bench,
    validate_kex_info,
    validate_mission,
    validate_session,
)
from tools.serial_bridge import SerialBridge, SerialBridgeError, SerialBridgeTimeout
from pqc_sat.infrastructure.wisdom import discover_wisdom


SCHEMA_VERSION = "pqc-sat-stage8-acceptance-v2"
DEFAULT_LOG_DIR = Path("logs")
SMOKE_COMMANDS = (
    "HELLO",
    "PING",
    "STATUS",
    "TELEMETRY",
    "KEX_INFO",
    "KEX_BENCH 100",
    f"MISSION ECDH {DEFAULT_PAYLOAD_HEX}",
    f"MISSION MLKEM {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH ECDH 1 {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH MLKEM 1 {DEFAULT_PAYLOAD_HEX}",
    "PROFILE OBC-1U-LIMITED",
    "STATUS",
    "KEX_INFO",
    "KEX_BENCH 100",
    f"MISSION ECDH {DEFAULT_PAYLOAD_HEX}",
    f"MISSION MLKEM {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH ECDH 1 {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH MLKEM 1 {DEFAULT_PAYLOAD_HEX}",
    "PROFILE BASELINE",
    "OLED STANDBY",
    "LED GREEN",
    "RGB TEST",
    "BARGRAPH 75",
)
LONG_COMMANDS = (
    "PING",
    "TELEMETRY",
    "STATUS",
    "KEX_INFO",
    f"MISSION ECDH {DEFAULT_PAYLOAD_HEX}",
    f"MISSION MLKEM {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH ECDH 1 {DEFAULT_PAYLOAD_HEX}",
    f"SESSION_BENCH MLKEM 1 {DEFAULT_PAYLOAD_HEX}",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PQC-SAT stage 8 acceptance checks")
    parser.add_argument("--port", help="serial port, for example /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="serial baudrate")
    parser.add_argument("--timeout", type=float, default=10.0, help="response timeout in seconds")
    parser.add_argument("--duration", type=float, default=1800.0, help="long-run duration in seconds")
    parser.add_argument("--interval", type=float, default=30.0, help="seconds between long-run commands")
    parser.add_argument("--skip-long-run", action="store_true", help="run only the short serial smoke")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="directory for JSON output")
    return parser.parse_args()


def run_smoke(bridge: SerialBridge) -> list[dict[str, object]]:
    return [send_record(bridge, command, "smoke") for command in SMOKE_COMMANDS]


def run_long(bridge: SerialBridge, duration: float, interval: float) -> list[dict[str, object]]:
    records = []
    deadline = time.monotonic() + duration
    index = 0
    while time.monotonic() < deadline:
        command = LONG_COMMANDS[index % len(LONG_COMMANDS)]
        records.append(send_record(bridge, command, "long_run"))
        index += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    return records


def choose_port(explicit: str | None) -> str:
    """Resolve the port by probing the current staged FAIR firmware."""

    device = discover_wisdom(
        explicit,
        require_staged_game=True,
        require_fair_kex=True,
        require_session_bench=True,
    )
    return device.port


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    failed = [record for record in records if not record.get("ok")]
    kex_bench = [
        record
        for record in records
        if str(record.get("command", "")).startswith("KEX_BENCH") and record.get("ok")
    ]
    mission_runs = [
        record
        for record in records
        if str(record.get("command", "")).startswith("MISSION") and record.get("ok")
    ]
    session_runs = [
        record
        for record in records
        if str(record.get("command", "")).startswith("SESSION_BENCH") and record.get("ok")
    ]
    semantic_errors: list[dict[str, object]] = []
    for index, record in enumerate(records, 1):
        if not record.get("ok"):
            continue
        command = str(record.get("command", ""))
        parts = command.split()
        payload = payload_of(record)
        expected_profile = payload.get("profile")
        errors: list[str] = []
        is_fair_measurement = (
            command == "KEX_INFO"
            or parts[:1] in (["KEX_BENCH"], ["MISSION"], ["SESSION_BENCH"])
        )
        if is_fair_measurement and expected_profile not in PROFILE_CPU:
            errors = ["profile FAIR ausente ou inválido"]
        elif command == "KEX_INFO":
            errors = validate_kex_info(payload, expected_profile)
        elif parts[:1] == ["KEX_BENCH"] and len(parts) == 2:
            errors = validate_bench(payload, int(parts[1]), str(expected_profile))
        elif parts[:1] == ["MISSION"] and len(parts) == 3:
            errors = validate_mission(
                payload,
                parts[1],
                len(DEFAULT_PAYLOAD),
                expected_profile,
            )
        elif parts[:1] == ["SESSION_BENCH"] and len(parts) == 4:
            errors = validate_session(
                payload,
                parts[1],
                int(parts[2]),
                len(DEFAULT_PAYLOAD),
                str(expected_profile),
            )
        semantic_errors.extend(
            {"record": index, "command": command, "error": error}
            for error in errors
        )
    return {
        "records": len(records),
        "failed": len(failed),
        "kex_bench_runs": len(kex_bench),
        "fresh_mission_runs": len(mission_runs),
        "session_bench_runs": len(session_runs),
        "semantic_errors": semantic_errors,
        "ok": not failed and not semantic_errors,
    }


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    records: list[dict[str, object]] = []
    try:
        port = choose_port(args.port)
        with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
            records.extend(run_smoke(bridge))
            if not args.skip_long_run:
                records.extend(run_long(bridge, args.duration, args.interval))
    except SerialBridgeTimeout:
        raise
    except SerialBridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "port": port,
        "baud": args.baud,
        "timeout_s": args.timeout,
        "requested_duration_s": 0 if args.skip_long_run else args.duration,
        "actual_elapsed_s": round(time.monotonic() - started, 2),
        "records": records,
        "game_preflight": {
            "ok": True,
            "port": port,
            "required_capabilities": {
                "game": "STAGED_V1",
                "kex": "FAIR_V1",
                "session_bench": SESSION_BENCH_CAPABILITY,
            },
        },
    }
    document["summary"] = summarize(records)
    path = write_document(document, args.log_dir, "stage8_acceptance")
    print(f"stage8_acceptance_json={path}")
    print("summary=" + json.dumps(document["summary"], sort_keys=True))
    return 0 if document["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
