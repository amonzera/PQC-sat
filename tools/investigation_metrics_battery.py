#!/usr/bin/env python3
"""Operator-run controlled battery for the transactional STAGED_V1 protocol."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.stand.model import (  # noqa: E402
    FAIR_KEY_MODES,
    FaultSelection,
    GameStage,
    GuardMode,
    IncidentScenario,
    KeyMode,
    OperationalDecision,
    StandConfig,
    StandProtocolError,
    parse_game_end_response,
    parse_game_result_response,
    parse_game_stage_response,
    scenario_for,
)
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH  # noqa: E402
from tools.serial_bridge import SerialBridge, SerialBridgeError  # noqa: E402
from tools.serial_protocol import decode_key_values  # noqa: E402
from tools.stand_diagnostics import choose_port  # noqa: E402


COMBINATIONS = tuple((key_mode, guard) for key_mode in FAIR_KEY_MODES for guard in GuardMode)
INCIDENTS = tuple(IncidentScenario)


def request(bridge: SerialBridge, command_line: str) -> dict[str, str]:
    parts = command_line.split()
    frame = bridge.send(parts[0], parts[1:])
    if frame.status != "OK":
        payload = decode_key_values(frame.payload_fields) if frame.payload_fields else {}
        raise SerialBridgeError(f"{command_line} retornou {frame.status}: {payload}")
    return decode_key_values(frame.payload_fields) if frame.payload_fields else {}


def build_matrix(config: StandConfig, cycles: int):
    mission = config.missions[0]
    profiles = (
        (config.baseline_name, config.baseline_mhz),
        (config.limited_name, config.limited_mhz),
    )
    for profile, profile_mhz in profiles:
        for scenario_index, (key_mode, guard) in enumerate(COMBINATIONS):
            for incident_index, incident in enumerate(INCIDENTS):
                for cycle in range(cycles):
                    bit_position = (
                        cycle * 17 + scenario_index * 29 + incident_index * 43
                    ) % (len(mission.payload_bytes) * 8)
                    selection = FaultSelection(
                        byte_index=bit_position // 8,
                        bit_mask=1 << (bit_position % 8),
                        bit_position=bit_position,
                        pot_value=0,
                    )
                    yield profile, profile_mhz, mission, key_mode, guard, incident, cycle, selection


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--cycles", type=int, default=100, help="repetições por perfil/proteção/incidente")
    parser.add_argument("--pause", type=float, default=0.10)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs" / "stand" / "investigation_battery")
    args = parser.parse_args(argv)
    if args.cycles <= 0 or args.pause < 0 or args.timeout <= 0:
        parser.error("cycles/timeout devem ser positivos e pause não negativo")

    config = StandConfig.load(args.config)
    try:
        port = choose_port(args.port)
    except SerialBridgeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2

    started_at = datetime.now(timezone.utc)
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    try:
        with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
            hello = request(bridge, "HELLO")
            if (
                hello.get("node") != "PQC-SAT-WISDOM"
                or hello.get("board") != "BlackBoard-Wisdom"
                or hello.get("proto") != "V1"
                or hello.get("game") != "STAGED_V1"
            ):
                raise SerialBridgeError("handshake não confirmou BlackBoard Wisdom/V1/STAGED_V1")
            try:
                hello_uptime_ms = int(str(hello["uptime_ms"]), 10)
            except (KeyError, TypeError, ValueError) as exc:
                raise SerialBridgeError("firmware desatualizado: HELLO sem uptime_ms") from exc
            if not 0 <= hello_uptime_ms <= 0xFFFFFFFF:
                raise SerialBridgeError("HELLO retornou uptime_ms fora da faixa uint32")
            for profile, profile_mhz, mission, key_mode, guard, incident, cycle, selection in build_matrix(config, args.cycles):
                scenario = scenario_for(key_mode, guard)
                game_id = f"B{cycle:04d}{profile_mhz}{key_mode.value[0]}{guard.value[0]}{incident.value[:2]}"
                commands = {
                    "begin": f"GAME_BEGIN {game_id} {profile} {key_mode.value} {guard.value} {incident.value} {mission.payload_hex}",
                    "protect": f"GAME_PROTECT {game_id}",
                    "transmit": f"GAME_TRANSMIT {game_id} {selection.byte_index} 0x{selection.bit_mask:02X}",
                    "verify": f"GAME_VERIFY {game_id}",
                    "retry": f"GAME_RETRY {game_id}",
                }
                try:
                    common = dict(
                        game_id=game_id,
                        profile=profile,
                        profile_mhz=profile_mhz,
                        key_mode=key_mode,
                        guard=guard,
                        payload_len=len(mission.payload_bytes),
                        source="hardware-live",
                    )
                    prepare = parse_game_stage_response(
                        commands["begin"],
                        request(bridge, commands["begin"]),
                        stage=GameStage.PREPARE,
                        payload_bytes=mission.payload_bytes,
                        **common,
                    )
                    protect = parse_game_stage_response(
                        commands["protect"], request(bridge, commands["protect"]), stage=GameStage.PROTECT, **common
                    )
                    transmit = parse_game_stage_response(
                        commands["transmit"],
                        request(bridge, commands["transmit"]),
                        stage=GameStage.TRANSMIT,
                        incident=incident,
                        selection=selection,
                        **common,
                    )
                    verified = parse_game_result_response(
                        commands["verify"],
                        request(bridge, commands["verify"]),
                        stage=GameStage.VERIFY,
                        incident=incident,
                        selection=selection,
                        **common,
                    )
                    retry = None
                    if incident is not IncidentScenario.NORMAL and cycle == 0:
                        retry = parse_game_result_response(
                            commands["retry"],
                            request(bridge, commands["retry"]),
                            stage=GameStage.RETRY,
                            incident=incident,
                            selection=selection,
                            initial_protect=protect,
                            **common,
                        )
                    decision = (
                        OperationalDecision.ACCEPT
                        if retry is not None or incident is IncidentScenario.NORMAL
                        else OperationalDecision.SAFE_MODE
                    )
                    end_command = f"GAME_END {game_id} {decision.value}"
                    receipt = parse_game_end_response(
                        end_command,
                        request(bridge, end_command),
                        game_id=game_id,
                        decision=decision,
                        expected_final_result=(retry or verified).result,
                        baseline_profile=config.baseline_name,
                        baseline_mhz=config.baseline_mhz,
                        source="hardware-live",
                    )
                    records.append(
                        {
                            "game_id": game_id,
                            "profile": profile,
                            "profile_mhz": profile_mhz,
                            "scenario": scenario,
                            "key_mode": key_mode.value,
                            "guard": guard.value,
                            "incident": incident.value,
                            "cycle": cycle,
                            "selection": asdict(selection),
                            "prepare": asdict(prepare),
                            "protect": asdict(protect),
                            "transmit": asdict(transmit),
                            "verify": asdict(verified),
                            "retry": asdict(retry) if retry else None,
                            "end": asdict(receipt),
                            "result": verified.result,
                        }
                    )
                except (SerialBridgeError, StandProtocolError, ValueError) as exc:
                    failures.append(
                        {
                            "game_id": game_id,
                            "profile": profile,
                            "scenario": scenario,
                            "incident": incident.value,
                            "cycle": cycle,
                            "error": str(exc),
                        }
                    )
                    try:
                        request(bridge, "HELLO")
                    except SerialBridgeError:
                        raise
                if args.pause:
                    time.sleep(args.pause)
            request(bridge, "HELLO")
    except (SerialBridgeError, StandProtocolError, OSError, ValueError) as exc:
        failures.append({"error": str(exc), "fatal": True})

    finished_at = datetime.now(timezone.utc)
    expected = 2 * len(COMBINATIONS) * len(INCIDENTS) * args.cycles
    outcome_counts: dict[str, int] = {}
    for record in records:
        outcome = str(record["result"])
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
    report = {
        "schema_version": "pqc-sat-staged-game-battery-v2",
        "created_at": finished_at.isoformat(),
        "started_at": started_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "port": port,
        "cycles_per_case": args.cycles,
        "expected_records": expected,
        "records_ok": len(records),
        "failed": len(failures),
        "official_candidate": len(records) == expected and not failures,
        "matrix": {
            "profiles": [config.baseline_name, config.limited_name],
            "scenarios": [scenario_for(key_mode, guard) for key_mode, guard in COMBINATIONS],
            "key_modes": [mode.value for mode in FAIR_KEY_MODES],
            "guards": [mode.value for mode in GuardMode],
            "incidents": [incident.value for incident in INCIDENTS],
            "mission": config.missions[0].mission_id,
        },
        "outcome_counts": outcome_counts,
        "failures": failures,
        "records": records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{started_at.strftime('%Y%m%dT%H%M%SZ')}_staged_game_{Path(port).name}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False, indent=2))
    print(f"arquivo: {output}")
    return 0 if report["official_candidate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
