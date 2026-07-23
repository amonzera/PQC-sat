#!/usr/bin/env python3
"""Short, operator-triggered readiness check for the SBPC stand."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.infrastructure.wisdom import discover_wisdom  # noqa: E402
from pqc_sat.stand.model import StandConfig  # noqa: E402
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH  # noqa: E402
from pqc_sat.stand.model import (  # noqa: E402
    FaultSelection,
    GameStage,
    GuardMode,
    IncidentScenario,
    KeyMode,
    OperationalDecision,
    StandProtocolError,
    fault_selection_from_pot,
    parse_button_press_event,
    parse_investigation_response,
    parse_game_end_response,
    parse_game_result_response,
    parse_game_stage_response,
    parse_profile_response,
)
from tools.serial_bridge import SerialBridge, SerialBridgeError  # noqa: E402
from tools.serial_protocol import ProtocolError, decode_key_values  # noqa: E402


def choose_port(explicit: str | None) -> str:
    """Compatibility helper backed by an active STAGED_V1 probe."""

    return discover_wisdom(explicit, require_staged_game=True).port


def request(bridge: SerialBridge, command_line: str) -> dict[str, object]:
    parts = command_line.split()
    started = time.monotonic()
    frame = bridge.send(parts[0], parts[1:])
    payload = decode_key_values(frame.payload_fields) if frame.payload_fields else {}
    return {
        "command": command_line,
        "status": frame.status,
        "elapsed_ms_host": round((time.monotonic() - started) * 1000, 3),
        "payload": payload,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--check-only", action="store_true", help="confirma Wisdom/STAGED_V1 por HELLO e encerra")
    parser.add_argument(
        "--full",
        action="store_true",
        help="inclui GAME_* por etapas e regressões curtas de MISSION, FAULT e INVESTIGATE",
    )
    parser.add_argument("--wait-button-seconds", type=float, default=0.0, help="aguarda um BUTTON_PING físico")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs" / "stand" / "diagnostics")
    args = parser.parse_args(argv)

    config = StandConfig.load(args.config)
    try:
        device = discover_wisdom(
            args.port,
            baudrate=args.baud,
            timeout=min(args.timeout, 3.0),
            require_staged_game=True,
        )
        port = device.port
    except SerialBridgeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"porta selecionada: {port}")
    if args.check_only:
        return 0

    commands = ["HELLO", "STATUS", "ANALOG POT"]
    if args.full:
        mission = config.missions[0] if config.missions else None
        investigation_payload = mission.payload_hex if mission is not None else config.payload_hex
        commands.extend(
            [
                f"PROFILE {config.baseline_name}",
                f"MISSION CLASSIC {config.payload_hex}",
                f"MISSION PQC {config.payload_hex}",
                f"FAULT NONE {config.payload_hex} 0 0x01",
                f"FAULT CRC32 {config.payload_hex} 0 0x01",
                "GAME_VERIFY DIAG-NONE",
                "HELLO",
                f"GAME_BEGIN DIAG-GAME {config.baseline_name} PQC CRC32 RX_MEMORY {investigation_payload}",
                "GAME_PROTECT DIAG-GAME",
                "ANALOG POT",
                "GAME_TRANSMIT DIAG-GAME A39",
                "GAME_VERIFY DIAG-GAME",
                "GAME_RETRY DIAG-GAME",
                "GAME_END DIAG-GAME ACCEPT",
                f"INVESTIGATE PQC NORMAL {investigation_payload} 0 0x01 DIAG-NORMAL",
                f"INVESTIGATE PQC CHANNEL_BITFLIP {investigation_payload} 0 0x01 DIAG-CHANNEL",
                f"INVESTIGATE PQC TAMPER {investigation_payload} 0 0x01 DIAG-TAMPER",
                f"INVESTIGATE PQC_CRC32 RX_MEMORY {investigation_payload} 0 0x01 DIAG-MEMORY",
                f"PROFILE {config.baseline_name}",
            ]
        )
    records = []
    hello_uptime_ms = None
    game_id = "DIAG-GAME"
    game_mission = config.missions[0] if config.missions else None
    game_payload_hex = game_mission.payload_hex if game_mission else config.payload_hex
    game_selection = None
    protect_measurement = None
    try:
        with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
            for command_template in commands:
                command = command_template
                if command_template == "GAME_TRANSMIT DIAG-GAME A39":
                    if game_selection is None:
                        raise SerialBridgeError("A39 ativo não foi lido antes de GAME_TRANSMIT")
                    command = (
                        f"GAME_TRANSMIT {game_id} {game_selection.byte_index} "
                        f"0x{game_selection.bit_mask:02X}"
                    )
                record = request(bridge, command)
                records.append(record)
                print(f"{record['status']:>5}  {command}")
                expected_bad_state = command == "GAME_VERIFY DIAG-NONE"
                if expected_bad_state:
                    if record["status"] == "OK" or record["payload"].get("code") != "BAD_GAME_STATE":
                        raise SerialBridgeError("ordem GAME_* inválida não retornou BAD_GAME_STATE")
                    continue
                if record["status"] != "OK":
                    raise SerialBridgeError(f"{command} retornou {record['status']}")
                if command == "HELLO":
                    payload = record["payload"]
                    if (
                        payload.get("node") != "PQC-SAT-WISDOM"
                        or payload.get("board") != "BlackBoard-Wisdom"
                        or payload.get("proto") != "V1"
                        or payload.get("game") != "STAGED_V1"
                    ):
                        raise SerialBridgeError("HELLO não confirmou Wisdom/V1/game=STAGED_V1")
                    try:
                        hello_uptime_ms = int(str(payload["uptime_ms"]), 10)
                    except (KeyError, TypeError, ValueError) as exc:
                        raise SerialBridgeError(
                            "firmware desatualizado: HELLO não informou uptime_ms"
                        ) from exc
                    if not 0 <= hello_uptime_ms <= 0xFFFFFFFF:
                        raise SerialBridgeError("HELLO retornou uptime_ms fora da faixa uint32")
                if command == "ANALOG POT" and protect_measurement is not None:
                    try:
                        pot_value = int(str(record["payload"]["pot"]), 10)
                        game_selection = fault_selection_from_pot(
                            pot_value,
                            len(bytes.fromhex(game_payload_hex)),
                            config,
                        )
                    except (KeyError, StandProtocolError, TypeError, ValueError) as exc:
                        raise SerialBridgeError("ANALOG POT ativo não confirmou A39 válido") from exc
                    record["purpose"] = "active_game_a39"
                    record["fault_selection"] = {
                        "pot": game_selection.pot_value,
                        "byte_index": game_selection.byte_index,
                        "bit_mask": f"0x{game_selection.bit_mask:02X}",
                    }
                if command.startswith("PROFILE "):
                    parse_profile_response(
                        record["payload"],
                        config.baseline_name,
                        config.baseline_mhz,
                    )
                if command.startswith("INVESTIGATE "):
                    parts = command.split()
                    byte_index = int(parts[4], 10)
                    bit_mask = int(parts[5], 0)
                    selection = FaultSelection(
                        byte_index=byte_index,
                        bit_mask=bit_mask,
                        bit_position=byte_index * 8 + (bit_mask.bit_length() - 1),
                        pot_value=0,
                    )
                    parse_investigation_response(
                        command,
                        record["payload"],
                        scenario=parts[1],
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        incident_id=parts[6],
                        incident=parts[2],
                        selection=selection,
                        payload_hex=parts[3],
                        source="hardware-live",
                    )
                if command.startswith("GAME_BEGIN "):
                    parse_game_stage_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        stage=GameStage.PREPARE,
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        key_mode=KeyMode.PQC,
                        guard=GuardMode.CRC32,
                        payload_len=len(bytes.fromhex(game_payload_hex)),
                        payload_bytes=bytes.fromhex(game_payload_hex),
                        source="hardware-live",
                    )
                elif command.startswith("GAME_PROTECT "):
                    protect_measurement = parse_game_stage_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        stage=GameStage.PROTECT,
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        key_mode=KeyMode.PQC,
                        guard=GuardMode.CRC32,
                        payload_len=len(bytes.fromhex(game_payload_hex)),
                        source="hardware-live",
                    )
                elif command.startswith("GAME_TRANSMIT "):
                    parse_game_stage_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        stage=GameStage.TRANSMIT,
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        key_mode=KeyMode.PQC,
                        guard=GuardMode.CRC32,
                        payload_len=len(bytes.fromhex(game_payload_hex)),
                        source="hardware-live",
                        incident=IncidentScenario.RX_MEMORY,
                        selection=game_selection,
                    )
                elif command == "GAME_VERIFY DIAG-GAME":
                    parse_game_result_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        stage=GameStage.VERIFY,
                        incident=IncidentScenario.RX_MEMORY,
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        key_mode=KeyMode.PQC,
                        guard=GuardMode.CRC32,
                        selection=game_selection,
                        payload_len=len(bytes.fromhex(game_payload_hex)),
                        source="hardware-live",
                    )
                elif command.startswith("GAME_RETRY "):
                    parse_game_result_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        stage=GameStage.RETRY,
                        incident=IncidentScenario.RX_MEMORY,
                        profile=config.baseline_name,
                        profile_mhz=config.baseline_mhz,
                        key_mode=KeyMode.PQC,
                        guard=GuardMode.CRC32,
                        selection=game_selection,
                        payload_len=len(bytes.fromhex(game_payload_hex)),
                        source="hardware-live",
                        initial_protect=protect_measurement,
                    )
                elif command.startswith("GAME_END "):
                    parse_game_end_response(
                        command,
                        record["payload"],
                        game_id=game_id,
                        decision=OperationalDecision.ACCEPT,
                        expected_final_result="DELIVERED",
                        baseline_profile=config.baseline_name,
                        baseline_mhz=config.baseline_mhz,
                        source="hardware-live",
                    )
            if args.wait_button_seconds > 0:
                print(f"aguardando BUTTON_PING por {args.wait_button_seconds:.0f} s…", flush=True)
                deadline = time.monotonic() + args.wait_button_seconds
                button_event = None
                while time.monotonic() < deadline and button_event is None:
                    for frame in bridge.poll_events():
                        if frame.payload_fields and frame.payload_fields[0].upper() == "BUTTON_PING":
                            candidate = {
                                "command": "EVENT BUTTON_PING",
                                "status": "OK",
                                "payload": decode_key_values(frame.payload_fields[1:]),
                            }
                            try:
                                parse_button_press_event(
                                    {"name": "BUTTON_PING", "payload": candidate["payload"]},
                                    handshake_uptime_ms=int(hello_uptime_ms),
                                )
                                pot = int(str(candidate["payload"]["pot"]), 10)
                                if not config.pot_minimum <= pot <= config.pot_maximum:
                                    raise ValueError("pot fora da faixa")
                            except (KeyError, StandProtocolError, ProtocolError, TypeError, ValueError):
                                continue
                            button_event = candidate
                            break
                    time.sleep(0.02)
                if button_event is None:
                    raise SerialBridgeError("BUTTON_PING não recebido dentro do prazo")
                records.append(button_event)
                print("   OK  EVENT BUTTON_PING")
    except (SerialBridgeError, ProtocolError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        result = "FAIL"
    else:
        result = "PASS"

    now = datetime.now(timezone.utc)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_stand_diagnostic.json"
    output.write_text(
        json.dumps(
            {
                "schema_version": "pqc-sat-stand-diagnostic-v2",
                "created_at": now.isoformat(),
                "port": port,
                "result": result,
                "full": args.full,
                "wait_button_seconds": args.wait_button_seconds,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"relatório: {output}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
