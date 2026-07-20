#!/usr/bin/env python3
"""Validate operator-produced JSONL evidence against the stand endurance gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_records(paths: list[Path]) -> list[dict[str, object]]:
    records = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: JSON inválido") from exc
            if record.get("schema_version") != "pqc-sat-stand-log-v1":
                raise ValueError(f"{path}:{line_number}: schema incompatível")
            record["_path"] = str(path)
            records.append(record)
    return records


def count_disconnect_recoveries(records: list[dict[str, object]]) -> tuple[int, int]:
    """Count real connected→disconnected transitions and later recoveries."""
    last_connected: dict[str, bool] = {}
    awaiting_recovery: set[str] = set()
    disconnects = 0
    recoveries = 0
    for record in records:
        if record.get("event") != "connection":
            continue
        session = str(record.get("session_id"))
        connected = bool(record.get("connected"))
        if last_connected.get(session) and not connected:
            disconnects += 1
            awaiting_recovery.add(session)
        elif connected and session in awaiting_recovery:
            recoveries += 1
            awaiting_recovery.remove(session)
        last_connected[session] = connected
    return disconnects, recoveries


def count_pot_activity(records: list[dict[str, object]]) -> tuple[int, int, int]:
    """Count samples, selected-bit transitions and unique selected positions."""
    last_position: dict[str, int] = {}
    unique_positions: set[tuple[str, int]] = set()
    samples = 0
    changes = 0
    for record in records:
        if record.get("event") != "fault_selection":
            continue
        try:
            position = int(record["bit_position"])
        except (KeyError, TypeError, ValueError):
            continue
        session = str(record.get("session_id"))
        samples += 1
        if session in last_position and last_position[session] != position:
            changes += 1
        last_position[session] = position
        unique_positions.add((session, position))
    return samples, changes, len(unique_positions)


def validate_cycle(record: dict[str, object]) -> list[str]:
    errors = []
    measurements = record.get("measurements", {})
    faults = record.get("faults", {})
    if not isinstance(measurements, dict) or not isinstance(faults, dict):
        return ["cycle_complete sem medições/falhas estruturadas"]
    required = ("CLASSIC_240", "PQC_240", "PQC_80")
    for key in required:
        if key not in measurements:
            errors.append(f"ciclo sem {key}")
    if errors:
        return errors
    payloads = {str(measurements[key].get("payload_hex")) for key in required}
    if len(payloads) != 1:
        errors.append("payload divergiu entre CLASSIC/PQC/240/80")
    if any(measurements[key].get("source") != "hardware-live" for key in required):
        errors.append("ciclo contém métrica que não é hardware-live")
    if measurements["PQC_240"].get("bytes_total") != measurements["PQC_80"].get("bytes_total"):
        errors.append("bytes PQC mudaram entre 240 e 80 MHz")
    none = faults.get("NONE")
    crc = faults.get("CRC32")
    if not isinstance(none, dict) or not isinstance(crc, dict):
        errors.append("ciclo sem par FAULT NONE/CRC32")
        return errors
    comparable = ("byte_index", "bit_mask", "before_byte", "after_byte")
    if any(none.get(key) != crc.get(key) for key in comparable):
        errors.append("FAULT NONE/CRC32 não repetiu a mesma falha")
    if none.get("result") != "SILENT" or crc.get("result") != "DETECTED_GUARD":
        errors.append("classificação de falha inesperada")
    if none.get("source") != "hardware-live" or crc.get("source") != "hardware-live":
        errors.append("falha não veio do hardware")
    duration = record.get("duration_seconds")
    if not isinstance(duration, (int, float)) or duration > 100:
        errors.append("ciclo excedeu 100 s ou não registrou duração")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--min-cycles", type=int, default=30)
    parser.add_argument("--min-button-actions", type=int, default=100)
    parser.add_argument("--min-pot-changes", type=int, default=100)
    parser.add_argument("--min-disconnects", type=int, default=10)
    parser.add_argument("--min-continuous-seconds", type=float, default=10800.0)
    parser.add_argument("--output", type=Path, default=Path("docs/stand/evidence/hardware_acceptance_summary.json"))
    args = parser.parse_args(argv)

    try:
        records = load_records(args.logs)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    starts = [record for record in records if record.get("event") == "session_start"]
    ends = [record for record in records if record.get("event") == "session_end"]
    hardware_sessions = {str(record.get("session_id")) for record in starts if record.get("mode") == "hardware"}
    non_hardware = [record for record in starts if record.get("mode") != "hardware"]
    handshakes = [record for record in records if record.get("event") == "handshake" and record.get("mode") == "hardware"]
    cycles = [record for record in records if record.get("event") == "cycle_complete"]
    errors = [record for record in records if record.get("event") == "error"]
    buttons = [record for record in records if record.get("event") == "button" and record.get("origin") == "physical"]
    pot_samples, pot_changes, pot_unique_positions = count_pot_activity(records)

    disconnects, disconnect_recoveries = count_disconnect_recoveries(records)

    end_by_session = {str(record.get("session_id")): record for record in ends}
    session_durations = []
    for start in starts:
        session = str(start.get("session_id"))
        end = end_by_session.get(session)
        if end:
            session_durations.append((parse_timestamp(str(end["timestamp"])) - parse_timestamp(str(start["timestamp"]))).total_seconds())
    max_continuous = max(session_durations, default=0.0)

    cycle_errors = []
    for record in cycles:
        for message in validate_cycle(record):
            cycle_errors.append({"cycle": record.get("cycle"), "session_id": record.get("session_id"), "error": message})

    gates = {
        "only_hardware_sessions": not non_hardware and bool(hardware_sessions),
        "handshake_present": bool(handshakes),
        "cycles": len(cycles) >= args.min_cycles,
        "button_actions": len(buttons) >= args.min_button_actions,
        "pot_changes": pot_changes >= args.min_pot_changes,
        "disconnect_recoveries": disconnect_recoveries >= args.min_disconnects,
        "continuous_runtime": max_continuous >= args.min_continuous_seconds,
        "no_errors": not errors,
        "cycle_invariants": not cycle_errors,
    }
    report = {
        "schema_version": "pqc-sat-stand-hardware-acceptance-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(gates.values()) else "FAIL",
        "inputs": [str(path) for path in args.logs],
        "gates": gates,
        "counts": {
            "hardware_sessions": len(hardware_sessions),
            "handshakes": len(handshakes),
            "cycles": len(cycles),
            "button_actions": len(buttons),
            "pot_samples": pot_samples,
            "pot_changes": pot_changes,
            "pot_unique_positions": pot_unique_positions,
            "disconnects": disconnects,
            "disconnect_recoveries": disconnect_recoveries,
            "errors": len(errors),
            "max_continuous_seconds": round(max_continuous, 3),
        },
        "thresholds": {
            "cycles": args.min_cycles,
            "button_actions": args.min_button_actions,
            "pot_changes": args.min_pot_changes,
            "disconnect_recoveries": args.min_disconnects,
            "continuous_seconds": args.min_continuous_seconds,
        },
        "cycle_errors": cycle_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
