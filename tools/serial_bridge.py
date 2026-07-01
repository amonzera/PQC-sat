#!/usr/bin/env python3
"""Synchronous serial bridge for the initial ESP32 transport spike."""

from __future__ import annotations

import itertools
from collections import deque
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.serial_protocol import ProtocolError, ProtocolFrame, build_command, parse_frame


class SerialBridgeError(RuntimeError):
    """Base error for host/ESP32 serial communication."""


class SerialBridgeTimeout(SerialBridgeError):
    """Raised when a matching response is not received before timeout."""


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    manufacturer: str


def _load_serial_modules():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        raise SerialBridgeError(
            "pyserial is not installed. Run: python3 -m pip install -r requirements.txt"
        ) from exc
    return serial, list_ports


def list_serial_ports() -> list[PortInfo]:
    """Return available serial ports using pyserial metadata."""

    _, list_ports = _load_serial_modules()
    ports = []
    for port in list_ports.comports():
        ports.append(
            PortInfo(
                device=port.device,
                description=port.description or "",
                manufacturer=port.manufacturer or "",
            )
        )
    return ports


class SerialBridge:
    """Small request/response bridge for V1 serial frames."""

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout: float = 2.0,
        startup_delay: float = 1.5,
    ) -> None:
        serial, _ = _load_serial_modules()
        self._serial_module = serial
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.startup_delay = startup_delay
        self._request_ids = itertools.count(1)
        self._ser = None
        self._events = deque()

    def open(self) -> None:
        if self._ser is not None and self._ser.is_open:
            return

        try:
            self._ser = self._serial_module.Serial(
                self.port,
                self.baudrate,
                timeout=0.1,
                write_timeout=self.timeout,
            )
        except self._serial_module.SerialException as exc:
            raise SerialBridgeError(
                f"could not open {self.port}. On Linux, check permissions with "
                f"`ls -l {self.port}`; a temporary fix is `sudo chmod 666 {self.port}` "
                "and the permanent fix is adding your user to the device group."
            ) from exc
        time.sleep(self.startup_delay)
        self._ser.reset_input_buffer()

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def __enter__(self) -> "SerialBridge":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def send(self, command: str, args: Iterable[object] = ()) -> ProtocolFrame:
        if self._ser is None or not self._ser.is_open:
            self.open()

        request_id = str(next(self._request_ids))
        frame = build_command(request_id, command, *args)
        self._ser.write(frame.encode("utf-8"))
        self._ser.flush()
        return self._read_response(request_id)

    def _read_response(self, request_id: str) -> ProtocolFrame:
        deadline = time.monotonic() + self.timeout
        malformed_lines: list[str] = []

        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue

            try:
                frame = parse_frame(raw)
            except ProtocolError:
                malformed_lines.append(raw.decode("utf-8", errors="replace").strip())
                continue

            if frame.message_type == "EVENT":
                self._events.append(frame)
                continue

            if frame.request_id == request_id and frame.is_result:
                return frame

        detail = f"timeout waiting for request_id={request_id}"
        if malformed_lines:
            detail += f"; malformed={malformed_lines[-3:]}"
        raise SerialBridgeTimeout(detail)

    def poll_events(self) -> list[ProtocolFrame]:
        """Return unsolicited EVENT frames without blocking command traffic."""
        if self._ser is not None and self._ser.is_open:
            while getattr(self._ser, "in_waiting", 0) > 0:
                raw = self._ser.readline()
                if not raw:
                    break
                try:
                    frame = parse_frame(raw)
                except ProtocolError:
                    continue
                if frame.message_type == "EVENT":
                    self._events.append(frame)

        events = list(self._events)
        self._events.clear()
        return events
