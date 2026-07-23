#!/usr/bin/env python3
"""Line-based protocol helpers for the PQC-SAT ESP32 transport spike."""

from __future__ import annotations

from dataclasses import dataclass

FRAME_VERSION = "V1"
MAX_COMMAND_CHARS = 384
MAX_FRAME_CHARS = 4096


class ProtocolError(ValueError):
    """Raised when a serial frame is malformed."""


@dataclass(frozen=True)
class ProtocolFrame:
    version: str
    request_id: str
    message_type: str
    fields: tuple[str, ...] = ()

    @property
    def is_result(self) -> bool:
        return self.message_type == "RESULT"

    @property
    def status(self) -> str | None:
        if not self.is_result or not self.fields:
            return None
        return self.fields[0]

    @property
    def payload_fields(self) -> tuple[str, ...]:
        if self.is_result:
            return self.fields[1:]
        return self.fields


def _normalize_token(token: object, *, name: str, uppercase: bool = False) -> str:
    value = str(token).strip()
    if uppercase:
        value = value.upper()
    if not value:
        raise ProtocolError(f"{name} cannot be empty")
    if "|" in value or "\r" in value or "\n" in value:
        raise ProtocolError(f"{name} contains a frame separator")
    return value


def _join_tokens(tokens: list[str], *, max_chars: int, kind: str) -> str:
    frame = "|".join(tokens)
    if len(frame) > max_chars:
        raise ProtocolError(f"{kind} exceeds {max_chars} characters")
    return frame + "\n"


def build_command(request_id: int | str, command: str, *args: object) -> str:
    """Build a command frame to be sent to the ESP32."""

    request = _normalize_token(request_id, name="request_id")
    command_token = _normalize_token(command, name="command", uppercase=True)
    arg_tokens = [_normalize_token(arg, name=f"arg_{idx}") for idx, arg in enumerate(args, 1)]
    return _join_tokens(
        [FRAME_VERSION, request, command_token, *arg_tokens],
        max_chars=MAX_COMMAND_CHARS,
        kind="command",
    )


def build_response(request_id: int | str, status: str, *fields: object) -> str:
    """Build a RESULT frame. Useful for tests and fake serial peers."""

    request = _normalize_token(request_id, name="request_id")
    status_token = _normalize_token(status, name="status", uppercase=True)
    field_tokens = [_normalize_token(field, name=f"field_{idx}") for idx, field in enumerate(fields, 1)]
    return _join_tokens(
        [FRAME_VERSION, request, "RESULT", status_token, *field_tokens],
        max_chars=MAX_FRAME_CHARS,
        kind="frame",
    )


def parse_frame(line: bytes | str) -> ProtocolFrame:
    """Parse one protocol line without the serial side effects."""

    if isinstance(line, bytes):
        try:
            raw = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("frame is not valid utf-8") from exc
    else:
        raw = line

    raw = raw.strip("\r\n")
    if not raw:
        raise ProtocolError("frame is empty")
    if len(raw) > MAX_FRAME_CHARS:
        raise ProtocolError(f"frame exceeds {MAX_FRAME_CHARS} characters")

    parts = raw.split("|")
    if any(part == "" for part in parts):
        raise ProtocolError("frame contains an empty field")
    if len(parts) < 3:
        raise ProtocolError("frame must contain version, request_id, and message_type")
    if parts[0] != FRAME_VERSION:
        raise ProtocolError(f"unsupported frame version: {parts[0]}")

    message_type = parts[2].upper()
    fields = tuple(parts[3:])
    if message_type == "RESULT" and not fields:
        raise ProtocolError("RESULT frame must contain a status")

    return ProtocolFrame(
        version=parts[0],
        request_id=parts[1],
        message_type=message_type,
        fields=fields,
    )


def decode_key_values(fields: tuple[str, ...] | list[str]) -> dict[str, str]:
    """Decode key=value payload fields from a RESULT or EVENT frame."""

    decoded: dict[str, str] = {}
    for field in fields:
        if "=" not in field:
            raise ProtocolError(f"payload field is not key=value: {field}")
        key, value = field.split("=", 1)
        key = _normalize_token(key, name="key")
        if key in decoded:
            raise ProtocolError(f"duplicated payload key: {key}")
        decoded[key] = value
    return decoded
