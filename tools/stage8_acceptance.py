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
from tools.serial_bridge import SerialBridge, SerialBridgeError, SerialBridgeTimeout
from pqc_sat.infrastructure.wisdom import discover_wisdom


SCHEMA_VERSION = "pqc-sat-stage8-acceptance-v1"
DEFAULT_LOG_DIR = Path("logs")
SMOKE_COMMANDS = (
    "HELLO",
    "PING",
    "STATUS",
    "TELEMETRY",
    "PQC_INFO",
    "PQC_KAT",
    "PQC_FAULT 0 0x01 CONFIRM",
    "PQC_FAULT 0 0x01 NONE",
    "PQC_BENCH 100",
    "MISSION CLASSIC",
    "MISSION PQC",
    "MISSION PQC_CRC32",
    "PROFILE OBC-1U-LIMITED",
    "PQC_BENCH 100",
    "MISSION CLASSIC",
    "MISSION PQC",
    "MISSION PQC_CRC32",
    "FAULT CRC32 5051432D534154 0 0x01",
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
    "PQC_INFO",
    "MISSION CLASSIC",
    "MISSION PQC",
    "MISSION PQC_CRC32",
    "FAULT CRC32 5051432D534154 0 0x01",
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
    """Resolve the port by probing the actual staged-game firmware."""

    return discover_wisdom(explicit, require_staged_game=True).port


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    failed = [record for record in records if not record.get("ok")]
    pqc_bench = [
        record
        for record in records
        if str(record.get("command", "")).startswith("PQC_BENCH") and record.get("ok")
    ]
    mission_runs = [
        record
        for record in records
        if str(record.get("command", "")).startswith("MISSION") and record.get("ok")
    ]
    return {
        "records": len(records),
        "failed": len(failed),
        "pqc_bench_runs": len(pqc_bench),
        "mission_runs": len(mission_runs),
        "ok": not failed,
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
        "game_preflight": {"ok": True, "port": port, "required_capability": "STAGED_V1"},
    }
    document["summary"] = summarize(records)
    path = write_document(document, args.log_dir, "stage8_acceptance")
    print(f"stage8_acceptance_json={path}")
    print("summary=" + json.dumps(document["summary"], sort_keys=True))
    return 0 if document["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
