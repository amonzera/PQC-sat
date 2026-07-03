#!/usr/bin/env python3
"""AES-GCM hardware metrics battery for the PQC-SAT seminar.

Run this from a terminal with the Wisdom connected. The goal is to generate
the official ECDH-vs-ML-KEM JSON: CLASSIC uses ephemeral ECDH P-256, and
PQC/PQC_CRC32 use ML-KEM-512. All scenarios derive an AES-128-GCM key.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.final_metrics_battery import (  # noqa: E402
    DEFAULT_LOG_DIR,
    DEFAULT_PROFILES,
    FAULT_VECTORS,
    MISSION_SCENARIOS,
    command_starts,
    mission_scenario_of,
    payload_of,
    profile_of,
    send_record,
    stats,
    summarize,
    utc_now_iso,
    write_document,
)
from tools.serial_bridge import SerialBridge, SerialBridgeError  # noqa: E402
from tools.serial_console import choose_port  # noqa: E402


SCHEMA_VERSION = "pqc-sat-aes-gcm-metrics-v2"
DEFAULT_AES_PAYLOAD = b"PQC-SAT|AESGCM|TEMP=24.5|STATUS=OK"
DEFAULT_AES_PAYLOAD_HEX = DEFAULT_AES_PAYLOAD.hex().upper()
MAX_PAYLOAD_BYTES = 96
OFFICIAL_CYCLES_PER_PROFILE = 100
OFFICIAL_MISSIONS_PER_PROFILE = OFFICIAL_CYCLES_PER_PROFILE * len(MISSION_SCENARIOS)
OFFICIAL_MISSIONS_PER_SCENARIO = OFFICIAL_CYCLES_PER_PROFILE * len(DEFAULT_PROFILES)
OFFICIAL_MISSION_RECORDS = OFFICIAL_MISSIONS_PER_PROFILE * len(DEFAULT_PROFILES)
AES_REQUIRED_FIELDS = (
    "cipher",
    "nonce_bytes",
    "gcm_tag_bytes",
    "nonce_crc32",
    "ciphertext_crc32",
    "gcm_tag_crc32",
    "encrypt_us",
    "decrypt_us",
    "aead_match",
    "decrypt_ok",
    "tag_match",
)
ECDH_REQUIRED_FIELDS = (
    "bytes_ecdh",
    "keygen_us",
    "ecdh_tx_us",
    "ecdh_rx_us",
    "key_match",
    "key_source",
)
PQC_REQUIRED_FIELDS = (
    "bytes_mlkem",
    "keygen_us",
    "encap_us",
    "decap_us",
    "key_match",
    "key_source",
)


def _positive_int(payload: dict[str, str], field: str) -> bool:
    try:
        return int(str(payload.get(field, "0")), 0) > 0
    except (TypeError, ValueError):
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the official ECDH P-256 vs ML-KEM-512 hardware metrics battery"
    )
    parser.add_argument("--port", help="serial port, for example /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="serial baudrate")
    parser.add_argument("--timeout", type=float, default=12.0, help="response timeout in seconds")
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="MISSION cycles per profile; each cycle runs CLASSIC, PQC and PQC_CRC32",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
        help="seconds between mission/fault commands to reduce burst bias",
    )
    parser.add_argument(
        "--bench-rounds",
        type=int,
        default=100,
        help="PQC_BENCH rounds per command, accepted firmware range is 1..100",
    )
    parser.add_argument("--bench-repeats", type=int, default=3, help="PQC_BENCH repetitions per profile")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=list(DEFAULT_PROFILES),
        choices=list(DEFAULT_PROFILES),
        help="profiles to test; default: BASELINE and OBC-1U-LIMITED",
    )
    parser.add_argument(
        "--payload-hex",
        default=DEFAULT_AES_PAYLOAD_HEX,
        help="fixed plaintext payload in hex; fixed payload makes nonce/cipher variation visible",
    )
    parser.add_argument(
        "--skip-faults",
        action="store_true",
        help="skip FAULT NONE/CRC32 checks and collect only MISSION/PQC_BENCH data",
    )
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="directory for JSON output")
    parser.add_argument("--dry-run", action="store_true", help="print the command plan without opening serial")
    return parser.parse_args()


def validate_payload_hex(payload_hex: str) -> str:
    value = payload_hex.strip().upper()
    if not value:
        raise ValueError("payload hex cannot be empty")
    if len(value) % 2:
        raise ValueError("payload hex must have an even number of characters")
    try:
        payload = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("payload hex is not valid hexadecimal") from exc
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload must be <= {MAX_PAYLOAD_BYTES} bytes")
    return value


def planned_commands(args: argparse.Namespace) -> list[tuple[str, str, str | None]]:
    payload_hex = validate_payload_hex(args.payload_hex)
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
                plan.append(("STATUS", "health", profile))
        for cycle in range(args.cycles):
            for scenario in MISSION_SCENARIOS:
                plan.append((f"MISSION {scenario} {payload_hex}", "mission", profile))
            if not args.skip_faults:
                byte_index, mask = FAULT_VECTORS[cycle % len(FAULT_VECTORS)]
                plan.append((f"FAULT NONE {payload_hex} {byte_index} {mask}", "fault", profile))
                plan.append((f"FAULT CRC32 {payload_hex} {byte_index} {mask}", "fault", profile))
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


def _rate(payloads: list[dict[str, str]], field: str, expected: object) -> float | None:
    present = [payload for payload in payloads if field in payload]
    if not present:
        return None
    expected_text = str(expected)
    ok = sum(1 for payload in present if str(payload.get(field)) == expected_text)
    return round(100.0 * ok / len(present), 2)


def _truthy_rate(payloads: list[dict[str, str]], field: str) -> float | None:
    present = [payload for payload in payloads if field in payload]
    if not present:
        return None
    ok = sum(1 for payload in present if str(payload.get(field)) in {"1", "true", "True"})
    return round(100.0 * ok / len(present), 2)


def _unique_summary(payloads: list[dict[str, str]], field: str) -> dict[str, object]:
    values = [str(payload[field]) for payload in payloads if payload.get(field)]
    counts = Counter(values)
    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "n": len(values),
        "unique": len(counts),
        "duplicates": duplicates,
        "top_duplicates": {value: count for value, count in counts.items() if count > 1},
    }


def summarize_aes_gcm(records: list[dict[str, object]]) -> dict[str, object]:
    mission_records = [record for record in records if command_starts(record, "MISSION")]
    summary: dict[str, object] = {
        "required_fields": list(AES_REQUIRED_FIELDS),
        "profiles": {},
        "checks": {},
    }
    nonce_values = [
        str(payload_of(record).get("nonce_crc32"))
        for record in mission_records
        if payload_of(record).get("nonce_crc32") not in {None, ""}
    ]
    duplicate_nonce_total = len(nonce_values) - len(set(nonce_values))
    missing_required_total = 0
    non_aes_total = 0
    aead_fail_total = 0
    ecdh_invalid_total = 0
    pqc_invalid_total = 0
    scenario_counts = Counter(mission_scenario_of(record) for record in mission_records)
    profile_counts = Counter(profile_of(record) for record in mission_records)

    for profile in sorted({profile_of(record) for record in mission_records}):
        profile_records = [record for record in mission_records if profile_of(record) == profile]
        scenarios: dict[str, object] = {}
        for scenario in MISSION_SCENARIOS:
            scenario_records = [
                record for record in profile_records if mission_scenario_of(record) == scenario
            ]
            payloads = [payload_of(record) for record in scenario_records]
            missing_required = sum(
                1 for payload in payloads for field in AES_REQUIRED_FIELDS if field not in payload
            )
            nonce_summary = _unique_summary(payloads, "nonce_crc32")
            missing_required_total += missing_required
            non_aes_total += sum(1 for payload in payloads if payload.get("cipher") != "AES-128-GCM")
            aead_fail_total += sum(1 for payload in payloads if str(payload.get("aead_match")) not in {"1", "true", "True"})
            ecdh_invalid = 0
            if scenario == "CLASSIC":
                ecdh_invalid = sum(
                    1
                    for payload in payloads
                    if any(field not in payload for field in ECDH_REQUIRED_FIELDS)
                    or payload.get("crypto") != "ECDH-P256"
                    or payload.get("key_source") != "ECDH-P256"
                    or str(payload.get("bytes_ecdh")) != "65"
                    or str(payload.get("key_match")) not in {"1", "true", "True"}
                    or not all(_positive_int(payload, field) for field in ("keygen_us", "ecdh_tx_us", "ecdh_rx_us"))
                )
                ecdh_invalid_total += ecdh_invalid
            pqc_invalid = 0
            if scenario in {"PQC", "PQC_CRC32"}:
                pqc_invalid = sum(
                    1
                    for payload in payloads
                    if any(field not in payload for field in PQC_REQUIRED_FIELDS)
                    or payload.get("crypto") != "ML-KEM-512"
                    or payload.get("key_source") != "ML-KEM-512"
                    or str(payload.get("bytes_mlkem")) != "768"
                    or str(payload.get("key_match")) not in {"1", "true", "True"}
                    or not all(_positive_int(payload, field) for field in ("keygen_us", "encap_us", "decap_us"))
                )
                pqc_invalid_total += pqc_invalid
            scenarios[scenario] = {
                "runs": len(scenario_records),
                "ok": sum(1 for record in scenario_records if record.get("ok")),
                "delivered": sum(1 for payload in payloads if payload.get("result") == "DELIVERED"),
                "missing_required_fields": missing_required,
                "cipher_aes_gcm_rate_pct": _rate(payloads, "cipher", "AES-128-GCM"),
                "nonce_12_bytes_rate_pct": _rate(payloads, "nonce_bytes", "12"),
                "tag_16_bytes_rate_pct": _rate(payloads, "gcm_tag_bytes", "16"),
                "aead_match_rate_pct": _truthy_rate(payloads, "aead_match"),
                "decrypt_ok_rate_pct": _truthy_rate(payloads, "decrypt_ok"),
                "tag_match_rate_pct": _truthy_rate(payloads, "tag_match"),
                "ecdh_invalid_records": ecdh_invalid,
                "pqc_invalid_records": pqc_invalid,
                "nonce_crc32": nonce_summary,
                "ciphertext_crc32": _unique_summary(payloads, "ciphertext_crc32"),
                "gcm_tag_crc32": _unique_summary(payloads, "gcm_tag_crc32"),
                "payload_crc32": _unique_summary(payloads, "payload_crc32"),
                "key_source_counts": dict(sorted(Counter(payload.get("key_source", "--") for payload in payloads).items())),
                "encrypt_us": stats(payload.get("encrypt_us") for payload in payloads),
                "decrypt_us": stats(payload.get("decrypt_us") for payload in payloads),
                "rng_us": stats(payload.get("rng_us") for payload in payloads),
                "kdf_us": stats(payload.get("kdf_us") for payload in payloads),
                "ecdh_tx_us": stats(payload.get("ecdh_tx_us") for payload in payloads),
                "ecdh_rx_us": stats(payload.get("ecdh_rx_us") for payload in payloads),
                "bytes_ciphertext": stats(payload.get("bytes_ciphertext") for payload in payloads),
                "bytes_total": stats(payload.get("bytes_total") for payload in payloads),
            }
        summary["profiles"][profile] = {
            "runs": len(profile_records),
            "scenarios": scenarios,
        }

    scenario_counts_clean = {scenario: int(scenario_counts.get(scenario, 0)) for scenario in MISSION_SCENARIOS}
    balanced_scenarios = len(set(scenario_counts_clean.values())) == 1 and all(scenario_counts_clean.values())
    profile_counts_clean = {profile: int(profile_counts.get(profile, 0)) for profile in DEFAULT_PROFILES}
    official_sample_size = (
        len(mission_records) == OFFICIAL_MISSION_RECORDS
        and all(count == OFFICIAL_MISSIONS_PER_SCENARIO for count in scenario_counts_clean.values())
        and all(count == OFFICIAL_MISSIONS_PER_PROFILE for count in profile_counts_clean.values())
    )
    mission_failures = sum(1 for record in mission_records if not record.get("ok"))
    delivery_failures = sum(1 for record in mission_records if payload_of(record).get("result") != "DELIVERED")
    summary["checks"] = {
        "mission_records": len(mission_records),
        "classic_records": sum(1 for record in mission_records if mission_scenario_of(record) == "CLASSIC"),
        "scenario_counts": scenario_counts_clean,
        "balanced_scenarios": balanced_scenarios,
        "profile_counts": profile_counts_clean,
        "official_sample_size": official_sample_size,
        "mission_failures": mission_failures,
        "delivery_failures": delivery_failures,
        "missing_required_fields": missing_required_total,
        "non_aes_gcm_records": non_aes_total,
        "aead_failures": aead_fail_total,
        "ecdh_invalid_records": ecdh_invalid_total,
        "pqc_invalid_records": pqc_invalid_total,
        "nonce_crc32_duplicates": duplicate_nonce_total,
        "official_candidate": (
            any(mission_scenario_of(record) == "CLASSIC" for record in mission_records)
            and missing_required_total == 0
            and non_aes_total == 0
            and aead_fail_total == 0
            and ecdh_invalid_total == 0
            and pqc_invalid_total == 0
            and balanced_scenarios
            and duplicate_nonce_total == 0
            and official_sample_size
            and mission_failures == 0
            and delivery_failures == 0
        ),
    }
    return summary


def print_plan(args: argparse.Namespace) -> None:
    plan = planned_commands(args)
    mission_count = sum(1 for command, _phase, _profile in plan if command.startswith("MISSION "))
    fault_count = sum(1 for command, _phase, _profile in plan if command.startswith("FAULT "))
    bench_count = sum(1 for command, _phase, _profile in plan if command.startswith("PQC_BENCH "))
    print(f"planned_commands={len(plan)}")
    print(
        f"profiles={','.join(args.profiles)} cycles={args.cycles} "
        f"missions={mission_count} faults={fault_count} pqc_bench={bench_count}"
    )
    print(f"payload_hex={validate_payload_hex(args.payload_hex)}")
    for index, (command, phase, profile) in enumerate(plan[:50], 1):
        print(f"{index:04d} {phase:9s} {profile or '-':15s} {command}")
    if len(plan) > 50:
        print(f"... {len(plan) - 50} more commands")


def validate_args(args: argparse.Namespace) -> str | None:
    if args.cycles < 1:
        return "--cycles must be >= 1"
    if not 1 <= args.bench_rounds <= 100:
        return "--bench-rounds must be in firmware range 1..100"
    if args.bench_repeats < 0:
        return "--bench-repeats must be >= 0"
    try:
        validate_payload_hex(args.payload_hex)
    except ValueError as exc:
        return str(exc)
    return None


def main() -> int:
    args = parse_args()
    error = validate_args(args)
    if error:
        print(f"error: {error}", file=sys.stderr)
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
        "payload_hex": validate_payload_hex(args.payload_hex),
        "skip_faults": bool(args.skip_faults),
        "records": records,
    }
    document["summary"] = summarize(records, actual_elapsed_s)
    document["summary"]["aes_gcm"] = summarize_aes_gcm(records)
    path = write_document(document, args.log_dir, "aes_gcm_metrics")
    checks = document["summary"]["aes_gcm"]["checks"]
    print(f"aes_gcm_metrics_json={path}")
    print("summary=" + json.dumps(
        {
            "ok": document["summary"]["ok"],
            "failed": document["summary"]["failed"],
            "records": document["summary"]["records"],
            "mission_runs": document["summary"]["mission_runs"],
            "pqc_bench_runs": document["summary"]["pqc_bench_runs"],
            "fault_runs": document["summary"]["fault_runs"],
            "official_candidate": checks["official_candidate"],
            "missing_required_fields": checks["missing_required_fields"],
            "non_aes_gcm_records": checks["non_aes_gcm_records"],
            "aead_failures": checks["aead_failures"],
            "ecdh_invalid_records": checks["ecdh_invalid_records"],
            "pqc_invalid_records": checks["pqc_invalid_records"],
            "balanced_scenarios": checks["balanced_scenarios"],
            "official_sample_size": checks["official_sample_size"],
            "mission_failures": checks["mission_failures"],
            "delivery_failures": checks["delivery_failures"],
            "nonce_crc32_duplicates": checks["nonce_crc32_duplicates"],
        },
        sort_keys=True,
    ))
    return 0 if document["summary"]["ok"] and checks["official_candidate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
