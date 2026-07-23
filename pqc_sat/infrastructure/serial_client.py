"""Non-blocking serial transport adapter for the BlackBoard Wisdom."""

import queue
import threading
import time
from pqc_sat.settings import (
    LIVE_PAYLOAD_REQUEST_TIMEOUT_SECONDS,
    SERIAL_RECONNECT_DELAY,
    SERIAL_TIMEOUT_SECONDS,
)
from pqc_sat.infrastructure.wisdom import discover_wisdom, validate_wisdom_handshake
from tools.serial_bridge import SerialBridge, SerialBridgeError, SerialBridgeTimeout
from tools.serial_protocol import ProtocolError, decode_key_values


class WisdomSerialClient:
    """Non-blocking serial worker used by the staged game."""

    def __init__(
        self,
        port=None,
        baudrate=115200,
        timeout=SERIAL_TIMEOUT_SECONDS,
        probe_timeout=None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.probe_timeout = timeout if probe_timeout is None else float(probe_timeout)
        self.actual_port = None
        self._tx = queue.Queue()
        self._rx = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pqc-sat-serial", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._tx.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def send(self, command_line, *, timeout=None):
        self._tx.put({"command": command_line, "reply": None, "emit": True, "timeout": timeout})

    def request(self, command_line, *, timeout=LIVE_PAYLOAD_REQUEST_TIMEOUT_SECONDS, emit_event=False):
        reply = queue.Queue(maxsize=1)
        self._tx.put({"command": command_line, "reply": reply, "emit": emit_event})
        try:
            event_type, payload = reply.get(timeout=timeout)
        except queue.Empty as exc:
            raise SerialBridgeTimeout(f"timeout waiting for live request: {command_line}") from exc
        if event_type == "error":
            raise SerialBridgeError(payload.get("status", "serial request error"))
        return payload

    def poll(self):
        events = []
        while True:
            try:
                events.append(self._rx.get_nowait())
            except queue.Empty:
                return events

    def _choose_port(self):
        device = discover_wisdom(
            self.port,
            baudrate=self.baudrate,
            timeout=self.probe_timeout,
            require_staged_game=True,
        )
        return device.port

    def _run(self):
        while not self._stop.is_set():
            try:
                self.actual_port = None
                self._rx.put(
                    (
                        "state",
                        {
                            "connected": False,
                            "status": "PROCURANDO WISDOM STAGED_V1",
                            "port": self.port,
                        },
                    )
                )
                port = self._choose_port()
                self.actual_port = port
                self._rx.put(
                    (
                        "state",
                        {"connected": False, "status": f"ABRINDO {port}", "port": port},
                    )
                )
                with SerialBridge(port, baudrate=self.baudrate, timeout=self.timeout) as bridge:
                    hello_payload = self._handshake(bridge)
                    self._rx.put(
                        (
                            "response",
                            {
                                "command": "HELLO",
                                "status": "OK",
                                "payload": hello_payload,
                                "raw_payload": " ".join(f"{key}={value}" for key, value in hello_payload.items()),
                            },
                        )
                    )
                    self._rx.put(
                        (
                            "state",
                            {"connected": True, "status": f"WISDOM {port}", "port": port},
                        )
                    )
                    while not self._stop.is_set():
                        try:
                            command_line = self._tx.get(timeout=0.1)
                        except queue.Empty:
                            self._publish_protocol_events(bridge)
                            continue
                        if command_line is None:
                            break
                        reply = None
                        emit_event = True
                        timeout_override = None
                        if isinstance(command_line, dict):
                            reply = command_line.get("reply")
                            emit_event = bool(command_line.get("emit", True))
                            timeout_override = command_line.get("timeout")
                            command_line = command_line.get("command")
                        if not self._send_one(
                            bridge,
                            command_line,
                            reply=reply,
                            emit_event=emit_event,
                            timeout_override=timeout_override,
                        ):
                            break
                        self._publish_protocol_events(bridge)
            except SerialBridgeError as exc:
                self._rx.put(
                    (
                        "state",
                        {
                            "connected": False,
                            "status": str(exc),
                            "port": self.actual_port or self.port,
                        },
                    )
                )
                self._wait_before_retry()

        self._rx.put(("state", {"connected": False, "status": "SERIAL OFF"}))

    def _handshake(self, bridge):
        frame = bridge.send("HELLO", [])
        if frame.status != "OK":
            raise SerialBridgeError(f"HELLO rejected with status={frame.status}")
        try:
            payload = decode_key_values(frame.payload_fields)
        except ProtocolError as exc:
            raise SerialBridgeError("HELLO response did not contain key=value payload") from exc

        return validate_wisdom_handshake(payload, require_staged_game=True)

    def _wait_before_retry(self):
        deadline = time.monotonic() + SERIAL_RECONNECT_DELAY
        while not self._stop.is_set() and time.monotonic() < deadline:
            time.sleep(0.05)

    @staticmethod
    def _notify_reply(reply, event):
        if reply is None:
            return
        try:
            reply.put_nowait(event)
        except queue.Full:
            pass

    def _publish_protocol_events(self, bridge):
        for frame in bridge.poll_events():
            fields = frame.payload_fields
            if not fields:
                continue
            name = str(fields[0]).upper()
            try:
                event_payload = decode_key_values(fields[1:]) if len(fields) > 1 else {}
            except ProtocolError:
                event_payload = {"raw": " ".join(fields[1:])}
            self._rx.put(
                (
                    "event",
                    {
                        "name": name,
                        "payload": event_payload,
                        "raw_payload": " ".join(fields),
                    },
                )
            )

    def _send_one(self, bridge, command_line, *, reply=None, emit_event=True, timeout_override=None):
        try:
            command, args = self._split_command(command_line)
            previous_timeout = bridge.timeout
            if timeout_override is not None:
                bridge.timeout = float(timeout_override)
            try:
                frame = bridge.send(command, args)
            finally:
                bridge.timeout = previous_timeout
            payload = {}
            raw_payload = ""
            if frame.payload_fields:
                raw_payload = " ".join(frame.payload_fields)
                try:
                    payload = decode_key_values(frame.payload_fields)
                except ProtocolError:
                    payload = {"payload": raw_payload}
            event = (
                "response",
                {
                    "command": command_line.upper(),
                    "status": frame.status or "UNKNOWN",
                    "payload": payload,
                    "raw_payload": raw_payload,
                },
            )
            if emit_event:
                self._rx.put(event)
            self._notify_reply(reply, event)
            return True
        except ProtocolError as exc:
            event = ("error", {"command": command_line.upper(), "status": str(exc)})
            if emit_event:
                self._rx.put(event)
            self._notify_reply(reply, event)
            return True
        except SerialBridgeError as exc:
            event = ("error", {"command": command_line.upper(), "status": str(exc)})
            self._rx.put(
                (
                    "state",
                    {
                        "connected": False,
                        "status": str(exc),
                        "port": self.actual_port or self.port,
                    },
                )
            )
            if emit_event:
                self._rx.put(event)
            self._notify_reply(reply, event)
            return False

    @staticmethod
    def _split_command(command_line):
        parts = command_line.strip().split()
        if not parts:
            raise ProtocolError("empty command")
        return parts[0], parts[1:]

__all__ = ("WisdomSerialClient",)
