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

from stand_demo import DEFAULT_CONFIG_PATH, StandConfig  # noqa: E402
from tools.serial_bridge import SerialBridge, SerialBridgeError, list_serial_ports  # noqa: E402
from tools.serial_protocol import decode_key_values  # noqa: E402


def choose_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    ports = list_serial_ports()
    wisdom = [
        port.device
        for port in ports
        if "cp210" in f"{port.description} {port.manufacturer}".lower()
        or "silicon labs" in f"{port.description} {port.manufacturer}".lower()
    ]
    if len(wisdom) == 1:
        return wisdom[0]
    if len(ports) == 1:
        return ports[0].device
    if not ports:
        raise SerialBridgeError("nenhuma porta serial encontrada")
    raise SerialBridgeError("mais de uma porta encontrada; informe --port: " + ", ".join(port.device for port in ports))


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
    parser.add_argument("--check-only", action="store_true", help="somente resolve a porta; não abre a serial")
    parser.add_argument("--full", action="store_true", help="inclui um smoke curto de MISSION e FAULT")
    parser.add_argument("--wait-button-seconds", type=float, default=0.0, help="aguarda um BUTTON_PING físico")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs" / "stand" / "diagnostics")
    args = parser.parse_args(argv)

    config = StandConfig.load(args.config)
    try:
        port = choose_port(args.port)
    except SerialBridgeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"porta selecionada: {port}")
    if args.check_only:
        return 0

    commands = ["HELLO", "STATUS", "ANALOG POT"]
    if args.full:
        commands.extend(
            [
                f"PROFILE {config.baseline_name}",
                f"MISSION CLASSIC {config.payload_hex}",
                f"MISSION PQC {config.payload_hex}",
                f"FAULT NONE {config.payload_hex} 0 0x01",
                f"FAULT CRC32 {config.payload_hex} 0 0x01",
                f"PROFILE {config.baseline_name}",
            ]
        )
    records = []
    try:
        with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
            for command in commands:
                record = request(bridge, command)
                records.append(record)
                print(f"{record['status']:>5}  {command}")
                if record["status"] != "OK":
                    raise SerialBridgeError(f"{command} retornou {record['status']}")
            if args.wait_button_seconds > 0:
                print(f"aguardando BUTTON_PING por {args.wait_button_seconds:.0f} s…", flush=True)
                deadline = time.monotonic() + args.wait_button_seconds
                button_event = None
                while time.monotonic() < deadline and button_event is None:
                    for frame in bridge.poll_events():
                        if frame.payload_fields and frame.payload_fields[0].upper() == "BUTTON_PING":
                            button_event = {
                                "command": "EVENT BUTTON_PING",
                                "status": "OK",
                                "payload": decode_key_values(frame.payload_fields[1:]),
                            }
                            break
                    time.sleep(0.02)
                if button_event is None:
                    raise SerialBridgeError("BUTTON_PING não recebido dentro do prazo")
                records.append(button_event)
                print("   OK  EVENT BUTTON_PING")
    except (SerialBridgeError, ValueError) as exc:
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
                "schema_version": "pqc-sat-stand-diagnostic-v1",
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
