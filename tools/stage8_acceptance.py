#!/usr/bin/env python3
"""Stage 8 hardware acceptance runner for PQC-SAT.

This script keeps the final presentation checks reproducible without moving
advanced bench commands into the dashboard's visual button set.
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
from tools.serial_console import choose_port


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
    parser.add_argument("--attempts", type=int, default=5, help="dashboard demo attempts")
    parser.add_argument("--skip-long-run", action="store_true", help="run only smoke checks and dashboard demo")
    parser.add_argument("--skip-dashboard-demo", action="store_true", help="skip headless dashboard DEMO")
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


def run_dashboard_demo(port: str, baudrate: int, timeout: float, attempts: int) -> dict[str, object]:
    import dashboard

    client = dashboard.DashboardSerialClient(port=port, baudrate=baudrate, timeout=timeout)
    panel = dashboard.DashboardPanel(serial_client=client)
    started = time.monotonic()
    record: dict[str, object] = {
        "phase": "dashboard_demo",
        "attempts": attempts,
        "started_at": utc_now_iso(),
        "ok": False,
    }
    connect_window = max(20.0, timeout * 2)
    try:
        while not panel.serial_connected and time.monotonic() - started < connect_window:
            panel.update(0.1)
            time.sleep(0.1)

        if not panel.serial_connected:
            record["error"] = panel.serial_status
            return record

        panel._execute_command(f"DEMO {attempts}")
        command_status = panel.command_history[-1]["status"] if panel.command_history else ""
        deadline = time.monotonic() + max(40.0, attempts * 4.0)
        while time.monotonic() < deadline:
            panel.update(0.1)
            time.sleep(0.1)
            if panel.demo_state in {"RESULTS", "IDLE"} and len(panel.experiment_events) >= attempts * 2:
                break

        summary = panel._demo_result_summary()
        record.update(
            {
                "ok": (
                    command_status == "DEMO START"
                    and summary.get("none_silent") == attempts
                    and summary.get("crc_detected") == attempts
                ),
                "status": command_status,
                "serial_status": panel.serial_status,
                "demo_state": panel.demo_state,
                "summary": summary,
                "event_count": len(panel.experiment_events),
                "export_path": str(panel.last_export_path) if panel.last_export_path else "",
            }
        )
        return record
    finally:
        panel.close()


def summarize(records: list[dict[str, object]], dashboard_demo: dict[str, object] | None) -> dict[str, object]:
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
        "dashboard_demo_ok": bool(dashboard_demo and dashboard_demo.get("ok")),
        "pqc_bench_runs": len(pqc_bench),
        "mission_runs": len(mission_runs),
        "ok": not failed and (dashboard_demo is None or bool(dashboard_demo.get("ok"))),
    }


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    records: list[dict[str, object]] = []
    dashboard_demo = None

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

    if not args.skip_dashboard_demo:
        dashboard_demo = run_dashboard_demo(port, args.baud, args.timeout, args.attempts)

    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "port": port,
        "baud": args.baud,
        "timeout_s": args.timeout,
        "requested_duration_s": 0 if args.skip_long_run else args.duration,
        "actual_elapsed_s": round(time.monotonic() - started, 2),
        "records": records,
        "dashboard_demo": dashboard_demo,
    }
    document["summary"] = summarize(records, dashboard_demo)
    path = write_document(document, args.log_dir, "stage8_acceptance")
    print(f"stage8_acceptance_json={path}")
    print("summary=" + json.dumps(document["summary"], sort_keys=True))
    return 0 if document["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
