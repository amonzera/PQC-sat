#!/usr/bin/env python3
"""Long hardware metrics battery for the PQC-SAT seminar.

This runner is intended to be executed by the human operator in a terminal,
not from the dashboard. It produces a raw record list plus aggregated metrics
for presentation tables.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.serial_bridge import SerialBridge, SerialBridgeError
from tools.serial_console import choose_port, split_command
from tools.serial_protocol import ProtocolError, decode_key_values


SCHEMA_VERSION = "pqc-sat-final-metrics-v1"
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_PROFILES = ("BASELINE", "OBC-1U-LIMITED")
MISSION_SCENARIOS = ("CLASSIC", "PQC", "PQC_CRC32")
DEFAULT_FAULT_PAYLOAD_HEX = "5051432D5341547C54454D503D32342E357C5354415455533D4F4B"
FAULT_VECTORS = (
    (0, "0x01"),
    (2, "0x04"),
    (5, "0x20"),
    (8, "0x80"),
)
NUMERIC_FIELDS = {
    "elapsed_us",
    "keygen_us",
    "encap_us",
    "decap_us",
    "rng_us",
    "kdf_us",
    "encrypt_us",
    "decrypt_us",
    "tag_us",
    "verify_us",
    "crc_us",
    "guard_prepare_us",
    "guard_verify_us",
    "guard_overhead_us",
    "bytes_total",
    "heap",
    "min_heap",
    "cpu_mhz",
    "keygen_avg_us",
    "encap_avg_us",
    "decap_avg_us",
    "ok",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a long, balanced PQC-SAT hardware metrics battery"
    )
    parser.add_argument("--port", help="serial port, for example /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="serial baudrate")
    parser.add_argument("--timeout", type=float, default=12.0, help="response timeout in seconds")
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="mission/fault cycles per profile; 100 gives 600 mission samples total",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
        help="seconds to wait between cycles to reduce serial/thermal burst bias",
    )
    parser.add_argument(
        "--bench-rounds",
        type=int,
        default=100,
        help="PQC_BENCH rounds per bench command, accepted firmware range is 1..100",
    )
    parser.add_argument(
        "--bench-repeats",
        type=int,
        default=3,
        help="PQC_BENCH repetitions per profile",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=list(DEFAULT_PROFILES),
        choices=list(DEFAULT_PROFILES),
        help="profiles to test, defaults to BASELINE and OBC-1U-LIMITED",
    )
    parser.add_argument(
        "--fault-payload-hex",
        default=DEFAULT_FAULT_PAYLOAD_HEX,
        help="hex payload used by FAULT NONE/CRC32 checks",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="directory for the JSON output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned command sequence without opening the serial port",
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "-", str(value).lower()).strip("-") or "serial"


def parse_number(value: object) -> float | int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return None


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def stats(values: Iterable[object]) -> dict[str, object]:
    parsed = [float(number) for number in (parse_number(value) for value in values) if number is not None]
    if not parsed:
        return {"n": 0}
    result = {
        "n": len(parsed),
        "avg": round(statistics.fmean(parsed), 3),
        "min": min(parsed),
        "median": round(statistics.median(parsed), 3),
        "p95": round(percentile(parsed, 95.0) or 0.0, 3),
        "max": max(parsed),
    }
    result["stdev"] = round(statistics.stdev(parsed), 3) if len(parsed) > 1 else 0.0
    return result


def send_record(bridge: SerialBridge, command_line: str, phase: str, profile: str | None = None) -> dict[str, object]:
    command, args = split_command(command_line)
    started = time.monotonic()
    record: dict[str, object] = {
        "phase": phase,
        "command": command_line,
        "profile_requested": profile or "",
        "started_at": utc_now_iso(),
    }
    try:
        frame = bridge.send(command, args)
        raw_payload = list(frame.payload_fields)
        payload: dict[str, str] = {}
        if frame.payload_fields:
            try:
                payload = decode_key_values(frame.payload_fields)
            except ProtocolError:
                payload = {"raw": " ".join(frame.payload_fields)}
        record.update(
            {
                "ok": frame.status == "OK",
                "request_id": frame.request_id,
                "status": frame.status or "UNKNOWN",
                "elapsed_ms_host": round((time.monotonic() - started) * 1000, 2),
                "payload": payload,
                "raw_payload": raw_payload,
            }
        )
    except (ProtocolError, SerialBridgeError) as exc:
        record.update(
            {
                "ok": False,
                "status": "ERROR",
                "elapsed_ms_host": round((time.monotonic() - started) * 1000, 2),
                "error": str(exc),
                "payload": {},
                "raw_payload": [],
            }
        )
    return record


def planned_commands(args: argparse.Namespace) -> list[tuple[str, str, str | None]]:
    plan: list[tuple[str, str, str | None]] = [
        ("HELLO", "preflight", None),
        ("PING", "preflight", None),
    ]
    for profile in args.profiles:
        plan.append((f"PROFILE {profile}", "profile", profile))
        plan.extend(
            [
                ("STATUS", "preflight", profile),
                ("TELEMETRY", "preflight", profile),
                ("PQC_INFO", "preflight", profile),
                ("PQC_KAT", "preflight", profile),
            ]
        )
        for repeat in range(args.bench_repeats):
            plan.append((f"PQC_BENCH {args.bench_rounds}", "bench", profile))
            if repeat == 0:
                plan.append(("STATUS", "preflight", profile))
        for cycle in range(args.cycles):
            for scenario in MISSION_SCENARIOS:
                plan.append((f"MISSION {scenario}", "mission", profile))
            byte_index, mask = FAULT_VECTORS[cycle % len(FAULT_VECTORS)]
            plan.append((f"FAULT NONE {args.fault_payload_hex} {byte_index} {mask}", "fault", profile))
            plan.append((f"FAULT CRC32 {args.fault_payload_hex} {byte_index} {mask}", "fault", profile))
            if (cycle + 1) % 25 == 0:
                plan.append(("STATUS", "health", profile))
                plan.append(("TELEMETRY", "health", profile))
    plan.extend(
        [
            ("PROFILE BASELINE", "cleanup", "BASELINE"),
            ("OLED STANDBY", "cleanup", "BASELINE"),
        ]
    )
    return plan


def run_battery(args: argparse.Namespace, port: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    plan = planned_commands(args)
    total = len(plan)
    with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
        for index, (command_line, phase, profile) in enumerate(plan, 1):
            record = send_record(bridge, command_line, phase, profile)
            record["sequence_index"] = index
            record["sequence_total"] = total
            records.append(record)
            marker = "OK" if record.get("ok") else "FAIL"
            print(f"[{index:04d}/{total:04d}] {marker} {command_line}")
            if phase in {"mission", "fault"} and args.pause > 0:
                time.sleep(args.pause)
    return records


def payload_of(record: dict[str, object]) -> dict[str, str]:
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def profile_of(record: dict[str, object]) -> str:
    payload = payload_of(record)
    return str(payload.get("profile") or record.get("profile_requested") or "UNKNOWN")


def command_starts(record: dict[str, object], prefix: str) -> bool:
    return str(record.get("command", "")).startswith(prefix)


def mission_scenario_of(record: dict[str, object]) -> str | None:
    payload = payload_of(record)
    scenario = str(payload.get("scenario") or "").strip().upper()
    if scenario in MISSION_SCENARIOS:
        return scenario
    parts = str(record.get("command", "")).split()
    if len(parts) >= 2 and parts[0] == "MISSION" and parts[1] in MISSION_SCENARIOS:
        return parts[1]
    return None


def summarize_missions(records: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for profile in sorted({profile_of(record) for record in records if command_starts(record, "MISSION")}):
        profile_records = [record for record in records if command_starts(record, "MISSION") and profile_of(record) == profile]
        scenarios: dict[str, object] = {}
        for scenario in MISSION_SCENARIOS:
            scenario_records = [
                record for record in profile_records if mission_scenario_of(record) == scenario
            ]
            payloads = [payload_of(record) for record in scenario_records]
            scenario_summary: dict[str, object] = {
                "runs": len(scenario_records),
                "ok": sum(1 for record in scenario_records if record.get("ok")),
                "delivered": sum(1 for payload in payloads if payload.get("result") == "DELIVERED"),
                "bytes_total": stats(payload.get("bytes_total") for payload in payloads),
            }
            for field in (
                "elapsed_us",
                "keygen_us",
                "encap_us",
                "decap_us",
                "ecdh_tx_us",
                "ecdh_rx_us",
                "rng_us",
                "kdf_us",
                "encrypt_us",
                "decrypt_us",
                "tag_us",
                "verify_us",
                "crc_us",
                "heap",
                "min_heap",
                "cpu_mhz",
            ):
                scenario_summary[field] = stats(payload.get(field) for payload in payloads)
            for field in ("key_match", "aead_match", "tag_match", "crc_match"):
                present = [payload.get(field) for payload in payloads if field in payload]
                scenario_summary[f"{field}_rate_pct"] = (
                    round(100.0 * sum(1 for value in present if str(value) in {"1", "true", "True"}) / len(present), 2)
                    if present
                    else None
                )
            scenarios[scenario] = scenario_summary
        summary[profile] = {
            "runs": len(profile_records),
            "scenarios": scenarios,
            "ratios": mission_ratios(scenarios),
        }
    return summary


def stat_avg(section: dict[str, object], field: str) -> float | None:
    field_stats = section.get(field)
    if isinstance(field_stats, dict):
        value = field_stats.get("avg")
        parsed = parse_number(value)
        return float(parsed) if parsed is not None else None
    return None


def mission_ratios(scenarios: dict[str, object]) -> dict[str, object]:
    classic = scenarios.get("CLASSIC")
    pqc = scenarios.get("PQC")
    pqc_crc = scenarios.get("PQC_CRC32")
    if not isinstance(classic, dict) or not isinstance(pqc, dict) or not isinstance(pqc_crc, dict):
        return {}

    classic_elapsed = stat_avg(classic, "elapsed_us")
    pqc_elapsed = stat_avg(pqc, "elapsed_us")
    pqc_crc_elapsed = stat_avg(pqc_crc, "elapsed_us")
    classic_bytes = stat_avg(classic, "bytes_total")
    pqc_bytes = stat_avg(pqc, "bytes_total")
    pqc_crc_bytes = stat_avg(pqc_crc, "bytes_total")
    pqc_crc_crc_us = stat_avg(pqc_crc, "crc_us")
    return {
        "pqc_vs_classic_elapsed": round(pqc_elapsed / classic_elapsed, 3)
        if classic_elapsed and pqc_elapsed
        else None,
        "pqc_crc32_vs_classic_elapsed": round(pqc_crc_elapsed / classic_elapsed, 3)
        if classic_elapsed and pqc_crc_elapsed
        else None,
        "pqc_vs_classic_bytes": round(pqc_bytes / classic_bytes, 3)
        if classic_bytes and pqc_bytes
        else None,
        "pqc_crc32_vs_classic_bytes": round(pqc_crc_bytes / classic_bytes, 3)
        if classic_bytes and pqc_crc_bytes
        else None,
        "crc32_extra_bytes": round(pqc_crc_bytes - pqc_bytes, 3)
        if pqc_bytes is not None and pqc_crc_bytes is not None
        else None,
        "crc32_avg_us": pqc_crc_crc_us,
    }


def summarize_benches(records: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    bench_records = [record for record in records if command_starts(record, "PQC_BENCH")]
    for profile in sorted({profile_of(record) for record in bench_records}):
        payloads = [payload_of(record) for record in bench_records if profile_of(record) == profile]
        summary[profile] = {
            "runs": len(payloads),
            "ok_rounds": stats(payload.get("ok") for payload in payloads),
            "keygen_avg_us": stats(payload.get("keygen_avg_us") for payload in payloads),
            "encap_avg_us": stats(payload.get("encap_avg_us") for payload in payloads),
            "decap_avg_us": stats(payload.get("decap_avg_us") for payload in payloads),
            "elapsed_us": stats(payload.get("elapsed_us") for payload in payloads),
            "heap": stats(payload.get("heap") for payload in payloads),
            "min_heap": stats(payload.get("min_heap") for payload in payloads),
        }
    return summary


def summarize_faults(records: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    fault_records = [record for record in records if command_starts(record, "FAULT ")]
    for profile in sorted({profile_of(record) for record in fault_records}):
        profile_records = [record for record in fault_records if profile_of(record) == profile]
        guards: dict[str, object] = {}
        for guard in sorted({str(payload_of(record).get("guard") or "NONE") for record in profile_records}):
            guard_records = [record for record in profile_records if str(payload_of(record).get("guard") or "NONE") == guard]
            result_counts = Counter(str(payload_of(record).get("result") or "UNKNOWN") for record in guard_records)
            guards[guard] = {
                "runs": len(guard_records),
                "ok": sum(1 for record in guard_records if record.get("ok")),
                "results": dict(sorted(result_counts.items())),
                "elapsed_us": stats(payload_of(record).get("elapsed_us") for record in guard_records),
            }
        summary[profile] = {"runs": len(profile_records), "guards": guards}
    return summary


def summarize_preflight(records: list[dict[str, object]]) -> dict[str, object]:
    kat_records = [record for record in records if str(record.get("command")) == "PQC_KAT"]
    info_records = [record for record in records if str(record.get("command")) == "PQC_INFO"]
    return {
        "pqc_kat": [
            {
                "profile": profile_of(record),
                "ok": record.get("ok"),
                "kat": payload_of(record).get("kat"),
                "elapsed_us": payload_of(record).get("elapsed_us"),
                "ss_crc32": payload_of(record).get("ss_crc32"),
            }
            for record in kat_records
        ],
        "pqc_info": [
            {
                "profile": profile_of(record),
                "ok": record.get("ok"),
                "backend": payload_of(record).get("backend"),
                "target": payload_of(record).get("target"),
                "pk": payload_of(record).get("pk"),
                "ct": payload_of(record).get("ct"),
                "ss": payload_of(record).get("ss"),
            }
            for record in info_records
        ],
    }


def summarize(records: list[dict[str, object]], actual_elapsed_s: float) -> dict[str, object]:
    failed = [record for record in records if not record.get("ok")]
    mission_records = [record for record in records if command_starts(record, "MISSION")]
    bench_records = [record for record in records if command_starts(record, "PQC_BENCH")]
    fault_records = [record for record in records if command_starts(record, "FAULT ")]
    summary = {
        "ok": not failed,
        "records": len(records),
        "failed": len(failed),
        "actual_elapsed_s": round(actual_elapsed_s, 2),
        "mission_runs": len(mission_records),
        "pqc_bench_runs": len(bench_records),
        "fault_runs": len(fault_records),
        "failed_commands": [record.get("command") for record in failed[:20]],
        "preflight": summarize_preflight(records),
        "mission": summarize_missions(records),
        "pqc_bench": summarize_benches(records),
        "faults": summarize_faults(records),
    }
    return summary


def write_document(document: dict[str, object], log_dir: str, kind: str = "final_metrics") -> Path:
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    port = safe_slug(str(document.get("port", "serial")))
    path = directory / f"{timestamp}_{kind}_{port}.json"
    suffix = 1
    while path.exists():
        path = directory / f"{timestamp}_{kind}_{port}_{suffix}.json"
        suffix += 1
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)
    return path


def print_plan(args: argparse.Namespace) -> None:
    plan = planned_commands(args)
    print(f"planned_commands={len(plan)}")
    print(f"profiles={','.join(args.profiles)} cycles={args.cycles} bench_repeats={args.bench_repeats}")
    for index, (command, phase, profile) in enumerate(plan[:40], 1):
        print(f"{index:04d} {phase:9s} {profile or '-':15s} {command}")
    if len(plan) > 40:
        print(f"... {len(plan) - 40} more commands")


def main() -> int:
    args = parse_args()
    if args.cycles < 1:
        print("error: --cycles must be >= 1", file=sys.stderr)
        return 2
    if not 1 <= args.bench_rounds <= 100:
        print("error: --bench-rounds must be in firmware range 1..100", file=sys.stderr)
        return 2
    if args.bench_repeats < 0:
        print("error: --bench-repeats must be >= 0", file=sys.stderr)
        return 2

    if args.dry_run:
        print_plan(args)
        return 0

    started = time.monotonic()
    try:
        port = choose_port(args.port)
        records = run_battery(args, port)
    except SerialBridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    actual_elapsed_s = time.monotonic() - started
    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "port": port,
        "baud": args.baud,
        "timeout_s": args.timeout,
        "cycles_per_profile": args.cycles,
        "pause_s": args.pause,
        "bench_rounds": args.bench_rounds,
        "bench_repeats_per_profile": args.bench_repeats,
        "profiles": list(args.profiles),
        "fault_payload_hex": args.fault_payload_hex,
        "records": records,
    }
    document["summary"] = summarize(records, actual_elapsed_s)
    path = write_document(document, args.log_dir)
    print(f"final_metrics_json={path}")
    print("summary=" + json.dumps(
        {
            "ok": document["summary"]["ok"],
            "failed": document["summary"]["failed"],
            "records": document["summary"]["records"],
            "mission_runs": document["summary"]["mission_runs"],
            "pqc_bench_runs": document["summary"]["pqc_bench_runs"],
            "fault_runs": document["summary"]["fault_runs"],
            "actual_elapsed_s": document["summary"]["actual_elapsed_s"],
        },
        sort_keys=True,
    ))
    return 0 if document["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
