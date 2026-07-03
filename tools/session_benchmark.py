#!/usr/bin/env python3
"""Production-like ECDH/ML-KEM session benchmark for the Wisdom ESP32.

The firmware performs one real handshake/KDF and then reuses the derived
AES-128-GCM session for 1, 100, 500 or 1000 messages. This host runner rotates
algorithm order, validates fixed 240 MHz conditions and exports raw records
plus statistical summaries. It never alternates to the 80 MHz profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.final_metrics_battery import (  # noqa: E402
    send_record,
    stats,
    utc_now_iso,
    write_document,
)
from tools.serial_bridge import SerialBridge, SerialBridgeError  # noqa: E402
from tools.serial_console import choose_port  # noqa: E402


SCHEMA_VERSION = "pqc-sat-session-benchmark-v1"
DEFAULT_LOG_DIR = Path("logs")
ALGORITHMS = ("ECDH_P256", "X25519", "MLKEM512")
MESSAGE_COUNTS = (1, 100, 500, 1000)
REQUIRED_PAYLOAD_FIELDS = (
    "algorithm",
    "profile",
    "cpu_mhz",
    "radio",
    "build_opt",
    "mbedtls_hw_mpi",
    "mbedtls_hw_aes",
    "mbedtls_hw_sha",
    "mbedtls_ecp_nist_optim",
    "messages",
    "key_match",
    "aead_match",
    "algorithm_init_us",
    "sender_setup_us",
    "receiver_setup_us",
    "setup_session_us",
    "aggregate_setup_us",
    "critical_latency_us",
    "critical_latency_model",
    "aes_gcm_encrypt_us",
    "aes_gcm_decrypt_us",
    "nonce_setup_us",
    "data_total_us",
    "total_us",
    "aggregate_total_us",
    "handshake_bytes",
    "data_message_bytes",
    "wire_total_bytes",
    "heap_before",
    "heap_after",
    "min_heap_after",
    "stack_hwm_after_bytes",
    "stack_hwm_drop_bytes",
    "flash_binary_bytes",
)
STAT_FIELDS = (
    "algorithm_init_us",
    "tx_keygen_us",
    "rx_keygen_us",
    "keygen_us",
    "tx_shared_secret_us",
    "rx_shared_secret_us",
    "shared_secret_us",
    "tx_kdf_us",
    "rx_kdf_us",
    "kdf_us",
    "sender_setup_us",
    "receiver_setup_us",
    "setup_session_us",
    "aggregate_setup_us",
    "critical_latency_us",
    "aes_gcm_encrypt_us",
    "aes_gcm_decrypt_us",
    "nonce_setup_us",
    "data_total_us",
    "total_us",
    "aggregate_total_us",
    "handshake_bytes",
    "data_message_bytes",
    "data_total_bytes",
    "wire_total_bytes",
    "overhead_total_bytes",
    "principal_crypto_buffers_bytes",
    "heap_before",
    "heap_after",
    "heap_net_delta_bytes",
    "global_heap_watermark_delta_bytes",
    "min_heap_after",
    "stack_hwm_after_bytes",
    "stack_hwm_drop_bytes",
    "flash_binary_bytes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark ECDH P-256, X25519 and ML-KEM-512 sessions at fixed 240 MHz"
    )
    parser.add_argument("--port", help="serial port, for example /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="serial baudrate")
    parser.add_argument("--timeout", type=float, default=20.0, help="response timeout in seconds")
    parser.add_argument("--repeats", type=int, default=10, help="samples per algorithm/message count")
    parser.add_argument("--pause", type=float, default=0.25, help="pause between benchmark commands")
    parser.add_argument(
        "--algorithms", nargs="+", choices=ALGORITHMS, default=list(ALGORITHMS)
    )
    parser.add_argument(
        "--messages", nargs="+", type=int, choices=MESSAGE_COUNTS, default=list(MESSAGE_COUNTS)
    )
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="directory for JSON output")
    parser.add_argument("--dry-run", action="store_true", help="print commands without opening serial")
    return parser.parse_args()


def planned_commands(args: argparse.Namespace) -> list[tuple[str, str]]:
    plan = [
        ("HELLO", "preflight"),
        ("PROFILE BASELINE", "preflight"),
        ("STATUS", "preflight"),
        ("PQC_INFO", "preflight"),
        ("PQC_KAT", "preflight"),
    ]
    algorithms = list(args.algorithms)
    for message_index, messages in enumerate(args.messages):
        for repeat in range(args.repeats):
            shift = (message_index + repeat) % len(algorithms)
            rotated = algorithms[shift:] + algorithms[:shift]
            for algorithm in rotated:
                plan.append((f"SESSION_BENCH {algorithm} {messages}", "session_bench"))
        plan.append(("STATUS", "health"))
    plan.extend((("PROFILE BASELINE", "cleanup"), ("OLED STANDBY", "cleanup")))
    return plan


def _integer(payload: dict[str, str], key: str) -> int | None:
    try:
        return int(str(payload.get(key, "")), 0)
    except (TypeError, ValueError):
        return None


def _per_message(payload: dict[str, str], key: str, messages: int) -> float | None:
    value = _integer(payload, key)
    return None if value is None else value / messages


def validate_session_record(record: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if not record.get("ok"):
        return [f"firmware_status={record.get('status', 'ERROR')}"]
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return ["missing_payload"]
    missing = [field for field in REQUIRED_PAYLOAD_FIELDS if field not in payload]
    if missing:
        errors.append("missing_fields=" + ",".join(missing))
    command_parts = str(record.get("command", "")).split()
    expected_algorithm = command_parts[1] if len(command_parts) >= 3 else ""
    expected_messages = int(command_parts[2]) if len(command_parts) >= 3 else 0
    if payload.get("algorithm") != expected_algorithm:
        errors.append("algorithm_mismatch")
    if _integer(payload, "messages") != expected_messages:
        errors.append("messages_mismatch")
    if payload.get("profile") != "BASELINE" or _integer(payload, "cpu_mhz") != 240:
        errors.append("not_fixed_240mhz_baseline")
    if payload.get("radio") != "OFF":
        errors.append("radio_not_disabled")
    if payload.get("build_opt") != "O2":
        errors.append("not_release_o2")
    for field in (
        "mbedtls_hw_mpi",
        "mbedtls_hw_aes",
        "mbedtls_hw_sha",
        "mbedtls_ecp_nist_optim",
    ):
        if payload.get(field) != "1":
            errors.append(f"{field}_disabled")
    if payload.get("key_match") != "1" or payload.get("aead_match") != "1":
        errors.append("crypto_validation_failed")
    for field in ("setup_session_us", "data_total_us", "total_us", "handshake_bytes"):
        if (_integer(payload, field) or 0) <= 0:
            errors.append(f"invalid_{field}")
    return errors


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    bench_records = [
        record for record in records if str(record.get("command", "")).startswith("SESSION_BENCH ")
    ]
    invalid: list[dict[str, object]] = []
    valid: list[dict[str, object]] = []
    for record in bench_records:
        errors = validate_session_record(record)
        if errors:
            invalid.append({"command": record.get("command"), "errors": errors})
        else:
            valid.append(record)

    groups: dict[str, dict[str, object]] = {}
    for algorithm in ALGORITHMS:
        algorithm_groups: dict[str, object] = {}
        for messages in MESSAGE_COUNTS:
            selected = [
                record
                for record in valid
                if str(record.get("command", "")) == f"SESSION_BENCH {algorithm} {messages}"
            ]
            if not selected:
                continue
            payloads = [record["payload"] for record in selected]
            fields = {field: stats(payload.get(field) for payload in payloads) for field in STAT_FIELDS}
            fields["data_avg_us"] = stats(
                _per_message(payload, "data_total_us", messages) for payload in payloads
            )
            fields["aes_gcm_encrypt_avg_us"] = stats(
                _per_message(payload, "aes_gcm_encrypt_us", messages) for payload in payloads
            )
            fields["aes_gcm_decrypt_avg_us"] = stats(
                _per_message(payload, "aes_gcm_decrypt_us", messages) for payload in payloads
            )
            fields["amortized_us"] = stats(
                _per_message(payload, "total_us", messages) for payload in payloads
            )
            fields["amortized_bytes"] = stats(
                _per_message(payload, "wire_total_bytes", messages) for payload in payloads
            )
            algorithm_groups[str(messages)] = {"runs": len(selected), "metrics": fields}
        if algorithm_groups:
            groups[algorithm] = algorithm_groups

    failed_commands = [record.get("command") for record in records if not record.get("ok")]
    return {
        "ok": not invalid and not failed_commands and bool(valid),
        "records": len(records),
        "session_runs": len(bench_records),
        "valid_session_runs": len(valid),
        "invalid_session_runs": len(invalid),
        "invalid": invalid[:50],
        "failed_commands": failed_commands[:50],
        "conditions": {
            "cpu_mhz": 240,
            "profile": "BASELINE",
            "build_opt": "O2",
            "radio": "disabled_by_firmware",
            "serial_inside_timed_region": False,
        },
        "groups": groups,
    }


def _median(group: dict[str, object], field: str) -> float | int | str:
    metrics = group.get("metrics", {})
    value = metrics.get(field, {}).get("median") if isinstance(metrics, dict) else None
    return "-" if value is None else value


def print_table(summary: dict[str, object]) -> None:
    print("\nModo | Setup us | AES-GCM medio us | N | Amortizado us/msg | Handshake B | Heap watermark B | Flash B")
    print("--- | ---: | ---: | ---: | ---: | ---: | ---: | ---:")
    for algorithm, message_groups in summary.get("groups", {}).items():
        for messages, group in message_groups.items():
            print(
                f"{algorithm} | {_median(group, 'setup_session_us')} | "
                f"{_median(group, 'data_avg_us')} | {messages} | "
                f"{_median(group, 'amortized_us')} | {_median(group, 'handshake_bytes')} | "
                f"{_median(group, 'global_heap_watermark_delta_bytes')} | "
                f"{_median(group, 'flash_binary_bytes')}"
            )


def run(args: argparse.Namespace, port: str) -> list[dict[str, object]]:
    plan = planned_commands(args)
    records: list[dict[str, object]] = []
    with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
        for index, (command, phase) in enumerate(plan, 1):
            record = send_record(bridge, command, phase, "BASELINE")
            record["sequence_index"] = index
            record["sequence_total"] = len(plan)
            records.append(record)
            print(f"[{index:03d}/{len(plan):03d}] {'OK' if record.get('ok') else 'FAIL'} {command}")
            if phase == "session_bench" and args.pause > 0:
                time.sleep(args.pause)
    return records


def main() -> int:
    args = parse_args()
    if args.repeats < 1:
        print("error: --repeats must be >= 1", file=sys.stderr)
        return 2
    plan = planned_commands(args)
    if args.dry_run:
        print(f"planned_commands={len(plan)} session_runs={len(args.algorithms) * len(args.messages) * args.repeats}")
        for index, (command, phase) in enumerate(plan, 1):
            print(f"{index:03d} {phase:13s} {command}")
        return 0

    try:
        port = choose_port(args.port)
        started = time.monotonic()
        records = run(args, port)
    except SerialBridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    summary = summarize(records)
    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "port": port,
        "baud": args.baud,
        "timeout_s": args.timeout,
        "repeats": args.repeats,
        "algorithms": list(args.algorithms),
        "message_counts": list(args.messages),
        "actual_elapsed_s": round(time.monotonic() - started, 2),
        "records": records,
        "summary": summary,
    }
    path = write_document(document, args.log_dir, "session_benchmark")
    print_table(summary)
    print(f"\nsession_benchmark_json={path}")
    print("summary=" + json.dumps({key: summary[key] for key in ("ok", "session_runs", "invalid_session_runs")}, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
