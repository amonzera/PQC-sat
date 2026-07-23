#!/usr/bin/env python3
"""Validate operator-produced JSONL evidence against the stand endurance gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys


MIN_A39_ADC_DELTA = 16


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
            if record.get("schema_version") not in {
                "pqc-sat-stand-log-v1",
                "pqc-sat-stand-log-v2",
            }:
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
    """Count real A39 changes without mixing raw ADC and derived bit positions."""
    last_position: dict[tuple[str, str], int] = {}
    unique_positions: set[tuple[str, str, int]] = set()
    samples = 0
    changes = 0
    for record in records:
        event = record.get("event")
        schema = record.get("schema_version")
        if (
            schema == "pqc-sat-stand-log-v2"
            and event == "button_confirmed"
            and record.get("origin") in {"physical", "screen"}
            and record.get("pot_source") in {None, "BUTTON_PING", "ANALOG POT"}
        ):
            value = record.get("pot")
            stream = "raw_a39"
        elif schema in {None, "pqc-sat-stand-log-v1"} and event == "fault_selection":
            value = record.get("bit_position")
            stream = "derived_bit"
        else:
            continue
        try:
            position = int(value)
        except (KeyError, TypeError, ValueError):
            continue
        session = str(record.get("session_id"))
        key = (session, stream)
        samples += 1
        minimum_delta = MIN_A39_ADC_DELTA if stream == "raw_a39" else 1
        if key in last_position and abs(last_position[key] - position) >= minimum_delta:
            changes += 1
        last_position[key] = position
        unique_positions.add((session, stream, position))
    return samples, changes, len(unique_positions)


def validate_cycle(record: dict[str, object]) -> list[str]:
    errors = []
    if record.get("flow") == "investigation":
        result = record.get("result")
        if not isinstance(result, dict):
            return ["partida STAGED_V1 sem resultado estruturado"]
        if record.get("schema_version") == "pqc-sat-stand-log-v1":
            incident = str(result.get("incident", ""))
            use_app_crc = str(result.get("scenario", "")) == "PQC_CRC32"
            expected = {
                "NORMAL": ("DELIVERED", True, True, True, use_app_crc, use_app_crc, use_app_crc),
                "CHANNEL_BITFLIP": ("FRAME_REJECT", False, False, False, use_app_crc, False, False),
                "TAMPER": ("AUTH_REJECT", False, True, False, use_app_crc, False, False),
                "RX_MEMORY": ("APP_REJECT" if use_app_crc else "SILENT_CORRUPTION", not use_app_crc, True, True, use_app_crc, use_app_crc, False),
            }.get(incident)
            observed = (
                result.get("result"), result.get("accepted"), result.get("frame_crc_match"),
                result.get("aead_match"), result.get("app_crc_present"),
                result.get("app_crc_checked"), result.get("app_crc_match"),
            )
            if result.get("source") != "hardware-live":
                errors.append("investigação V1 não veio do hardware")
            if expected is None or observed != expected:
                errors.append(f"tabela investigativa V1 contraditória: {incident}")
            duration = record.get("duration_seconds")
            if not isinstance(duration, (int, float)) or duration > 90:
                errors.append("ciclo V1 excedeu 90 s ou não registrou duração")
            return errors
        if result.get("source") != "hardware-live":
            errors.append("partida não veio do hardware")
        if str(result.get("key_mode", "")) not in {"ECDH", "MLKEM"}:
            errors.append("partida STAGED_V1 não usou ECDH/MLKEM FAIR")
        incident = str(result.get("incident", ""))
        guard = str(result.get("guard", ""))
        use_app_crc = guard == "CRC32"
        expected = {
            "NORMAL": ("DELIVERED", True, True, True, use_app_crc, use_app_crc, use_app_crc),
            "CHANNEL_BITFLIP": ("FRAME_REJECT", False, False, False, use_app_crc, False, False),
            "TAMPER": ("AUTH_REJECT", False, True, False, use_app_crc, False, False),
            "RX_MEMORY": (
                "APP_REJECT" if use_app_crc else "SILENT_CORRUPTION",
                not use_app_crc,
                True,
                True,
                use_app_crc,
                use_app_crc,
                False,
            ),
        }.get(incident)
        observed = (
            result.get("result"),
            result.get("accepted"),
            result.get("frame_crc_match"),
            result.get("aead_match"),
            result.get("app_crc_present"),
            result.get("app_crc_checked"),
            result.get("app_crc_match"),
        )
        if expected is None or observed != expected:
            errors.append(f"tabela STAGED_V1 contraditória: {incident}/{guard}")
        if result.get("aead_checked") is not True:
            errors.append("tag AES-GCM não foi verificada")
        selection = result.get("selection")
        if not isinstance(selection, dict):
            errors.append("vetor single-bit ausente ou inválido")
        else:
            try:
                byte_index = int(selection.get("byte_index"))
                mask = int(selection.get("bit_mask"))
                bit_position = int(selection.get("bit_position"))
            except (TypeError, ValueError):
                errors.append("vetor single-bit ausente ou inválido")
            else:
                invalid_mask = mask <= 0 or mask > 0x80 or bool(mask & (mask - 1))
                if invalid_mask or byte_index < 0 or bit_position != byte_index * 8 + (mask.bit_length() - 1):
                    errors.append("vetor single-bit fora da faixa")
        duration = record.get("duration_seconds")
        if not isinstance(duration, (int, float)) or duration <= 0:
            errors.append("partida não registrou duração positiva")
        diagnosis = str(record.get("diagnosis", ""))
        if diagnosis not in {"CHANNEL", "AUTH", "MEMORY"}:
            errors.append("partida sem diagnóstico confirmado")
        decision = str(record.get("decision", ""))
        if decision not in {"ACCEPT", "RETRY", "SAFE_MODE"}:
            errors.append("partida sem decisão operacional confirmada")
        retry = record.get("retry_result")
        if decision == "RETRY":
            if not isinstance(retry, dict) or retry.get("result") != "DELIVERED":
                errors.append("retransmissão não terminou DELIVERED")
            elif not all(str(retry.get("raw_response", {}).get(key)) == "1" for key in ("same_payload", "fresh_key", "fresh_nonce")):
                errors.append("retransmissão não comprovou payload igual e material novo")
        return errors

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


def validate_confirmation_transition_causes(records: list[dict[str, object]]) -> list[str]:
    """Every v2 forward transition must reference an allowed explicit confirmation."""

    confirmations: dict[tuple[str, int], str] = {}
    errors: list[str] = []
    for record in records:
        if record.get("schema_version") != "pqc-sat-stand-log-v2":
            continue
        session = str(record.get("session_id"))
        if record.get("event") == "button_confirmed" and record.get("origin") in {"physical", "screen"}:
            try:
                confirmations[(session, int(record["button_seq"]))] = str(record.get("origin"))
            except (KeyError, TypeError, ValueError):
                errors.append(f"{session}: confirmação sem sequência")
        if record.get("event") != "transition":
            continue
        state = str(record.get("state", ""))
        if state in {"ERROR", "ATTRACT"} and record.get("cause") != "button":
            continue
        try:
            button_seq = int(record["button_seq"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{session}: transição {state} sem button_seq")
            continue
        origin = confirmations.get((session, button_seq))
        if record.get("cause") != "button" or origin is None:
            errors.append(f"{session}: transição {state} sem confirmação correspondente")
            continue
        recorded_origin = str(record.get("confirmation_origin", ""))
        if recorded_origin and recorded_origin != origin:
            errors.append(f"{session}: transição {state} divergiu da origem {origin}")
    return errors


def validate_physical_transition_causes(records: list[dict[str, object]]) -> list[str]:
    """Compatibility alias for callers of the former physical-only validator."""

    return validate_confirmation_transition_causes(records)


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
    handshakes = [
        record
        for record in records
        if record.get("event") == "handshake"
        and record.get("mode") == "hardware"
        and isinstance(record.get("payload"), dict)
        and (
            record.get("schema_version") == "pqc-sat-stand-log-v1"
            or record["payload"].get("game") == "STAGED_V1"
        )
    ]
    cycles = [record for record in records if record.get("event") == "cycle_complete"]
    errors = [record for record in records if record.get("event") == "error"]
    buttons = [
        record
        for record in records
        if record.get("event") in {"button", "button_confirmed"}
        and record.get("origin") == "physical"
    ]
    screen_confirmations = [
        record
        for record in records
        if record.get("event") == "button_confirmed"
        and record.get("origin") == "screen"
    ]
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
    transition_errors = validate_confirmation_transition_causes(records)
    staged_durations = [
        float(record["duration_seconds"])
        for record in cycles
        if record.get("flow") == "investigation" and isinstance(record.get("duration_seconds"), (int, float))
    ]
    median_duration = statistics.median(staged_durations) if staged_durations else 0.0
    has_staged_v2 = any(record.get("schema_version") == "pqc-sat-stand-log-v2" for record in records)

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
        "confirmation_transition_invariant": not transition_errors,
        "median_duration_120_180": (120.0 <= median_duration <= 180.0) if has_staged_v2 else True,
    }
    report = {
        "schema_version": "pqc-sat-stand-hardware-acceptance-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS" if all(gates.values()) else "FAIL",
        "inputs": [str(path) for path in args.logs],
        "gates": gates,
        "counts": {
            "hardware_sessions": len(hardware_sessions),
            "handshakes": len(handshakes),
            "cycles": len(cycles),
            "button_actions": len(buttons),
            "screen_confirmations": len(screen_confirmations),
            "pot_samples": pot_samples,
            "pot_changes": pot_changes,
            "pot_unique_positions": pot_unique_positions,
            "disconnects": disconnects,
            "disconnect_recoveries": disconnect_recoveries,
            "errors": len(errors),
            "max_continuous_seconds": round(max_continuous, 3),
            "median_game_seconds": round(median_duration, 3),
        },
        "thresholds": {
            "cycles": args.min_cycles,
            "button_actions": args.min_button_actions,
            "pot_changes": args.min_pot_changes,
            "disconnect_recoveries": args.min_disconnects,
            "continuous_seconds": args.min_continuous_seconds,
            "a39_minimum_adc_delta_per_change": MIN_A39_ADC_DELTA,
        },
        "cycle_errors": cycle_errors,
        "transition_errors": transition_errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
