#!/usr/bin/env python3
"""Command-line console for the PQC-SAT ESP32 serial transport."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.serial_bridge import SerialBridge, SerialBridgeError, list_serial_ports
from tools.serial_commands import command_help_lines
from tools.serial_protocol import ProtocolError, decode_key_values


DEFAULT_COMMANDS = ["HELLO", "PING", "STATUS", "PERIPHERALS", "TELEMETRY"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PQC-SAT ESP32 serial console")
    parser.add_argument("--port", help="serial port, for example /dev/ttyUSB0 or COM3")
    parser.add_argument("--baud", type=int, default=115200, help="serial baudrate")
    parser.add_argument("--timeout", type=float, default=2.0, help="response timeout in seconds")
    parser.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    parser.add_argument("--commands", action="store_true", help="list live-demo commands and exit")
    parser.add_argument("--all-commands", action="store_true", help="list every bench/hardware command and exit")
    parser.add_argument(
        "--command",
        action="append",
        help="command to send; may be repeated. Example: --command 'LED TOGGLE'",
    )
    parser.add_argument("--interactive", action="store_true", help="keep a prompt open")
    return parser.parse_args()


def print_ports() -> int:
    ports = list_serial_ports()
    if not ports:
        print("No serial ports found.")
        return 1

    for port in ports:
        details = " - ".join(part for part in [port.description, port.manufacturer] if part)
        if details:
            print(f"{port.device}\t{details}")
        else:
            print(port.device)
    return 0


def print_command_help(*, all_commands: bool = False) -> None:
    for line in command_help_lines(include_dashboard=False, demo_only=not all_commands):
        print(line)
    print("")
    print("Comandos locais do console:")
    print("  HELP                                   mostra esta lista")
    print("  EXIT|QUIT                              sai do modo interativo")


def choose_port(explicit_port: str | None) -> str:
    if explicit_port:
        return explicit_port

    ports = list_serial_ports()
    if len(ports) == 1:
        return ports[0].device

    if not ports:
        raise SerialBridgeError("no serial ports found; connect the ESP32 and try --list-ports")

    port_names = ", ".join(port.device for port in ports)
    raise SerialBridgeError(f"multiple ports found ({port_names}); pass --port explicitly")


def split_command(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    if not parts:
        raise ProtocolError("empty command")
    return parts[0], parts[1:]


def print_response(command_line: str, frame) -> None:
    status = frame.status or "UNKNOWN"
    print(f"> {command_line}")
    print(f"< request_id={frame.request_id} status={status}")

    if frame.payload_fields:
        try:
            payload = decode_key_values(frame.payload_fields)
        except ProtocolError:
            print("  payload=" + " ".join(frame.payload_fields))
        else:
            for key, value in payload.items():
                print(f"  {key}={value}")


def send_command(bridge: SerialBridge, command_line: str) -> None:
    command, args = split_command(command_line)
    frame = bridge.send(command, args)
    print_response(command_line, frame)


def interactive_loop(bridge: SerialBridge) -> None:
    print("Modo interativo. Digite HELP para comandos de demo, ou EXIT para sair.")
    while True:
        try:
            line = input("sat> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not line:
            continue
        if line.upper() in {"EXIT", "QUIT"}:
            return
        if line.upper() == "HELP":
            print_command_help()

        try:
            send_command(bridge, line)
        except (ProtocolError, SerialBridgeError) as exc:
            print(f"error: {exc}", file=sys.stderr)


def main() -> int:
    args = parse_args()

    try:
        if args.list_ports:
            return print_ports()
        if args.commands:
            print_command_help()
            return 0
        if args.all_commands:
            print_command_help(all_commands=True)
            return 0

        port = choose_port(args.port)
        command_lines = args.command or DEFAULT_COMMANDS

        with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
            for command_line in command_lines:
                send_command(bridge, command_line)
            if args.interactive:
                interactive_loop(bridge)
    except (ProtocolError, SerialBridgeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
