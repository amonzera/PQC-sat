#!/usr/bin/env python3
"""Guided, offline-capable SBPC stand experience for PQC-SAT.

The state machine is deliberately independent from Pygame.  Hardware values
enter the presentation only after a typed response has been accepted; the
simulated mode uses a provenance-labelled fixture from the official campaign.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import time
import uuid
import zlib

import pygame


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = ROOT / "config" / "stand_demo.json"
DEFAULT_FIXTURE_PATH = ROOT / "fixtures" / "stand" / "official_20260702.json"
DEFAULT_LOG_DIR = ROOT / "logs" / "stand"
VIRTUAL_SIZE = (1366, 768)
FPS = 60

C_BG = (3, 7, 18)
C_BG_SOFT = (8, 17, 34)
C_PANEL = (12, 25, 48)
C_PANEL_2 = (18, 36, 65)
C_CYAN = (45, 225, 255)
C_BLUE = (69, 132, 255)
C_GREEN = (92, 232, 151)
C_YELLOW = (255, 205, 78)
C_ORANGE = (255, 151, 75)
C_RED = (255, 91, 105)
C_PURPLE = (199, 111, 255)
C_WHITE = (246, 250, 255)
C_DIM = (158, 180, 208)
C_LINE = (48, 82, 120)


class StandError(RuntimeError):
    """Base exception for stand-mode validation errors."""


class StandConfigError(StandError):
    """Raised when the local stand configuration is invalid."""


class StandProtocolError(StandError):
    """Raised when a serial/fixture response cannot prove the expected step."""


class DemoState(str, Enum):
    ATTRACT = "ATTRACT"
    INTRO = "INTRO"
    RUN_240 = "RUN_240"
    RUN_80 = "RUN_80"
    SELECT_BIT = "SELECT_BIT"
    FAULT_NONE = "FAULT_NONE"
    FAULT_CRC = "FAULT_CRC"
    SUMMARY = "SUMMARY"
    ERROR = "ERROR"


@dataclass(frozen=True)
class StandConfig:
    payload: str
    payload_display: str
    auto_reset_seconds: float
    serial_timeout_seconds: float
    intro_seconds: float
    comparison_hold_seconds: float
    fault_hold_seconds: float
    kiosk_fullscreen: bool
    windowed_size: tuple[int, int]
    animation_min_ms: int
    animation_max_ms: int
    baseline_name: str
    baseline_mhz: int
    limited_name: str
    limited_mhz: int
    pot_minimum: int
    pot_maximum: int
    pot_poll_interval_seconds: float
    button_debounce_seconds: float
    interaction_timeout_seconds: float = 35.0

    @property
    def payload_bytes(self) -> bytes:
        return self.payload.encode("ascii")

    @property
    def payload_hex(self) -> str:
        return self.payload_bytes.hex().upper()

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "StandConfig":
        config_path = Path(path)
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StandConfigError(f"não foi possível carregar {config_path}: {exc}") from exc
        if data.get("schema_version") != "pqc-sat-stand-config-v1":
            raise StandConfigError("schema_version de configuração incompatível")
        try:
            animation = data["animation"]
            profiles = data["profiles"]
            pot = data["potentiometer"]
            windowed_size = tuple(int(value) for value in data["windowed_size"])
            config = cls(
                payload=str(data["payload"]),
                payload_display=str(data["payload_display"]),
                auto_reset_seconds=float(data["auto_reset_seconds"]),
                serial_timeout_seconds=float(data["serial_timeout_seconds"]),
                intro_seconds=float(data["intro_seconds"]),
                comparison_hold_seconds=float(data["comparison_hold_seconds"]),
                fault_hold_seconds=float(data["fault_hold_seconds"]),
                kiosk_fullscreen=bool(data["kiosk_fullscreen"]),
                windowed_size=(windowed_size[0], windowed_size[1]),
                animation_min_ms=int(animation["min_duration_ms"]),
                animation_max_ms=int(animation["max_duration_ms"]),
                baseline_name=str(profiles["baseline_name"]).upper(),
                baseline_mhz=int(profiles["baseline_mhz"]),
                limited_name=str(profiles["limited_name"]).upper(),
                limited_mhz=int(profiles["limited_mhz"]),
                pot_minimum=int(pot["minimum"]),
                pot_maximum=int(pot["maximum"]),
                pot_poll_interval_seconds=float(pot["poll_interval_seconds"]),
                button_debounce_seconds=float(data["button_debounce_seconds"]),
                interaction_timeout_seconds=float(data.get("interaction_timeout_seconds", 35.0)),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise StandConfigError(f"configuração incompleta: {exc}") from exc
        try:
            payload_bytes = config.payload_bytes
        except UnicodeEncodeError as exc:
            raise StandConfigError("payload do firmware deve ser ASCII") from exc
        if not payload_bytes or len(payload_bytes) > 96:
            raise StandConfigError("payload deve conter entre 1 e 96 bytes")
        if len(config.windowed_size) != 2 or min(config.windowed_size) < 480:
            raise StandConfigError("windowed_size inválido")
        if config.pot_maximum <= config.pot_minimum:
            raise StandConfigError("faixa do potenciômetro inválida")
        if config.animation_min_ms <= 0 or config.animation_max_ms < config.animation_min_ms:
            raise StandConfigError("faixa de animação inválida")
        for value in (
            config.auto_reset_seconds,
            config.serial_timeout_seconds,
            config.intro_seconds,
            config.comparison_hold_seconds,
            config.fault_hold_seconds,
            config.pot_poll_interval_seconds,
            config.button_debounce_seconds,
            config.interaction_timeout_seconds,
        ):
            if value <= 0:
                raise StandConfigError("durações devem ser positivas")
        return config


@dataclass(frozen=True)
class HardwareMeasurement:
    command: str
    scenario: str
    profile: str
    profile_mhz: int
    elapsed_us: int
    bytes_total: int
    result: str
    source: str
    payload_hex: str
    raw_response: dict[str, str]


@dataclass(frozen=True)
class AnimationModel:
    duration_ms: int
    label: str
    scale_factor: float

    @classmethod
    def for_measurement(cls, measurement: HardwareMeasurement, config: StandConfig) -> "AnimationModel":
        measured_ms = max(0.001, measurement.elapsed_us / 1000.0)
        visual_ms = int(max(config.animation_min_ms, min(config.animation_max_ms, 900 + math.sqrt(measured_ms) * 620)))
        return cls(
            duration_ms=visual_ms,
            label="ANIMAÇÃO DIDÁTICA — TEMPO AMPLIADO",
            scale_factor=visual_ms / measured_ms,
        )


@dataclass(frozen=True)
class FaultSelection:
    byte_index: int
    bit_mask: int
    bit_position: int
    pot_value: int


@dataclass(frozen=True)
class FaultMeasurement:
    command: str
    guard: str
    result: str
    byte_index: int
    bit_mask: int
    before_byte: int
    after_byte: int
    crc_before: int
    crc_after: int
    elapsed_us: int
    source: str
    raw_response: dict[str, str]


@dataclass(frozen=True)
class PendingCommand:
    command: str
    purpose: str
    deadline: float
    expected: dict[str, object]


def safe_ratio(numerator: int | float | None, denominator: int | float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def fault_selection_from_pot(pot_value: int | str, payload_len: int, config: StandConfig) -> FaultSelection:
    if payload_len <= 0:
        raise ValueError("payload vazio")
    try:
        parsed = int(pot_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("leitura inválida do potenciômetro") from exc
    clamped = max(config.pot_minimum, min(config.pot_maximum, parsed))
    total_bits = payload_len * 8
    relative = (clamped - config.pot_minimum) / (config.pot_maximum - config.pot_minimum)
    bit_position = min(total_bits - 1, int(round(relative * (total_bits - 1))))
    return FaultSelection(
        byte_index=bit_position // 8,
        bit_mask=1 << (bit_position % 8),
        bit_position=bit_position,
        pot_value=clamped,
    )


def flip_selected_bit(payload: bytes, selection: FaultSelection) -> bytes:
    if not 0 <= selection.byte_index < len(payload):
        raise ValueError("índice fora do payload")
    if selection.bit_mask <= 0 or selection.bit_mask > 0x80 or selection.bit_mask & (selection.bit_mask - 1):
        raise ValueError("máscara não representa um único bit")
    mutated = bytearray(payload)
    mutated[selection.byte_index] ^= selection.bit_mask
    return bytes(mutated)


def _required_text(payload: dict[str, object], key: str) -> str:
    if key not in payload:
        raise StandProtocolError(f"resposta sem campo {key}")
    text = str(payload[key]).strip()
    if not text:
        raise StandProtocolError(f"campo vazio: {key}")
    return text


def _required_int(payload: dict[str, object], key: str, *, base: int = 10) -> int:
    text = _required_text(payload, key)
    try:
        return int(text, base)
    except ValueError as exc:
        raise StandProtocolError(f"campo {key} não é inteiro: {text}") from exc


def parse_profile_response(payload: dict[str, object], expected_name: str, expected_mhz: int) -> tuple[str, int]:
    profile = _required_text(payload, "profile").upper()
    cpu_mhz = _required_int(payload, "cpu_mhz")
    if profile != expected_name or cpu_mhz != expected_mhz:
        raise StandProtocolError(
            f"perfil não confirmado: esperado {expected_name}/{expected_mhz}, recebido {profile}/{cpu_mhz}"
        )
    return profile, cpu_mhz


def parse_mission_response(
    command: str,
    payload: dict[str, object],
    *,
    scenario: str,
    profile: str,
    profile_mhz: int,
    payload_hex: str,
    source: str,
) -> HardwareMeasurement:
    received_scenario = _required_text(payload, "scenario").upper()
    received_profile = _required_text(payload, "profile").upper()
    received_mhz = _required_int(payload, "cpu_mhz")
    cipher = _required_text(payload, "cipher").upper()
    result = _required_text(payload, "result").upper()
    elapsed_us = _required_int(payload, "elapsed_us")
    bytes_total = _required_int(payload, "bytes_total")
    bytes_payload = _required_int(payload, "bytes_payload")
    if received_scenario != scenario:
        raise StandProtocolError(f"cenário divergente: {received_scenario}")
    if received_profile != profile or received_mhz != profile_mhz:
        raise StandProtocolError("missão retornou perfil diferente do confirmado")
    if cipher != "AES-128-GCM":
        raise StandProtocolError(f"cifra inesperada: {cipher}")
    if result != "DELIVERED":
        raise StandProtocolError(f"missão não entregue: {result}")
    if elapsed_us <= 0 or bytes_total <= 0:
        raise StandProtocolError("métrica de missão não positiva")
    if bytes_payload != len(bytes.fromhex(payload_hex)):
        raise StandProtocolError("tamanho do payload diverge do enviado")
    if str(payload.get("aead_match", "1")).lower() not in {"1", "true"}:
        raise StandProtocolError("AES-GCM não confirmou a mensagem")
    return HardwareMeasurement(
        command=command,
        scenario=scenario,
        profile=profile,
        profile_mhz=profile_mhz,
        elapsed_us=elapsed_us,
        bytes_total=bytes_total,
        result=result,
        source=source,
        payload_hex=payload_hex,
        raw_response={key: str(value) for key, value in payload.items()},
    )


def parse_fault_response(
    command: str,
    payload: dict[str, object],
    *,
    expected_guard: str,
    selection: FaultSelection,
    source: str,
) -> FaultMeasurement:
    guard = _required_text(payload, "guard").upper()
    result = _required_text(payload, "result").upper()
    byte_index = _required_int(payload, "byte_index")
    bit_mask = _required_int(payload, "bit_mask", base=0)
    before_byte = _required_int(payload, "before_byte", base=0)
    after_byte = _required_int(payload, "after_byte", base=0)
    crc_before = _required_int(payload, "crc_before", base=0)
    crc_after = _required_int(payload, "crc_after", base=0)
    elapsed_us = _required_int(payload, "elapsed_us")
    if guard != expected_guard:
        raise StandProtocolError(f"guardião divergente: {guard}")
    if byte_index != selection.byte_index or bit_mask != selection.bit_mask:
        raise StandProtocolError("resposta alterou a falha selecionada")
    if after_byte != before_byte ^ bit_mask:
        raise StandProtocolError("resposta não comprova XOR de um único bit")
    expected_result = "SILENT" if guard == "NONE" else "DETECTED_GUARD"
    if result != expected_result:
        raise StandProtocolError(f"resultado de falha inesperado: {result}")
    if guard == "CRC32" and crc_before == crc_after:
        raise StandProtocolError("CRC32 não mudou após o bit flip")
    return FaultMeasurement(
        command=command,
        guard=guard,
        result=result,
        byte_index=byte_index,
        bit_mask=bit_mask,
        before_byte=before_byte,
        after_byte=after_byte,
        crc_before=crc_before,
        crc_after=crc_after,
        elapsed_us=elapsed_us,
        source=source,
        raw_response={key: str(value) for key, value in payload.items()},
    )


class StandSessionLogger:
    def __init__(self, log_dir: str | Path, *, mode: str, config: StandConfig, fixture_source: str = ""):
        now = datetime.now(timezone.utc)
        day_dir = Path(log_dir) / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        self.path = day_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_stand_{mode}_{uuid.uuid4().hex[:8]}.jsonl"
        self._handle = self.path.open("a", encoding="utf-8")
        self.session_id = uuid.uuid4().hex
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            revision = "UNKNOWN"
        self.write(
            "session_start",
            mode=mode,
            revision=revision,
            payload=config.payload,
            payload_hex=config.payload_hex,
            fixture_source=fixture_source or None,
        )

    def write(self, event: str, **fields: object) -> None:
        record = {
            "schema_version": "pqc-sat-stand-log-v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event": event,
            **fields,
        }
        self._handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle.closed:
            return
        self.write("session_end")
        self._handle.close()


class FixtureSerialClient:
    """Small asynchronous-compatible offline transport backed by official data."""

    def __init__(self, fixture_path: str | Path, config: StandConfig, *, latency_seconds: float = 0.06):
        self.fixture_path = Path(fixture_path)
        try:
            self.fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StandConfigError(f"fixture inválida: {exc}") from exc
        if self.fixture.get("schema_version") != "pqc-sat-stand-fixture-v1":
            raise StandConfigError("schema da fixture incompatível")
        if not self.fixture.get("official_candidate") or int(self.fixture.get("failed", -1)) != 0:
            raise StandConfigError("fixture não representa campanha oficial aceita")
        if self.fixture.get("payload") != config.payload:
            raise StandConfigError("payload da fixture difere da configuração")
        source_path = ROOT / str(self.fixture.get("source_path", ""))
        source_sha = str(self.fixture.get("source_sha256", "")).lower()
        if len(source_sha) != 64:
            raise StandConfigError("fixture sem SHA-256 de origem")
        if source_path.is_file():
            actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_sha != source_sha:
                raise StandConfigError("SHA-256 do log oficial diverge da fixture")
        self.config = config
        self.latency_seconds = max(0.0, latency_seconds)
        self.actual_port = "OFFLINE-FIXTURE"
        self.active_profile = config.baseline_name
        self.pot_value = (config.pot_minimum + config.pot_maximum) // 2
        self._scheduled: list[tuple[float, tuple[str, dict[str, object]]]] = []
        self._running = False

    @property
    def source_label(self) -> str:
        return f"{self.fixture.get('source_path')} sha256:{self.fixture.get('source_sha256')}"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        hello = {
            "command": "HELLO",
            "status": "OK",
            "payload": {
                "node": "OFFLINE-FIXTURE",
                "board": "BlackBoard-Wisdom",
                "proto": "V1",
                "fixture_source": self.fixture.get("source_path"),
                "fixture_sha256": self.fixture.get("source_sha256"),
            },
            "raw_payload": "fixture oficial",
        }
        now = time.monotonic()
        self._scheduled.extend(
            [
                (now, ("response", hello)),
                (now, ("state", {"connected": True, "status": "FIXTURE OFICIAL OFFLINE"})),
            ]
        )

    def stop(self) -> None:
        self._running = False
        self._scheduled.clear()

    def set_pot(self, value: int) -> None:
        self.pot_value = max(self.config.pot_minimum, min(self.config.pot_maximum, int(value)))

    def send(self, command_line: str, *, timeout: float | None = None) -> None:
        del timeout
        command_line = command_line.strip()
        event = self._build_response(command_line)
        self._scheduled.append((time.monotonic() + self.latency_seconds, event))

    def poll(self) -> list[tuple[str, dict[str, object]]]:
        now = time.monotonic()
        ready = [event for due, event in self._scheduled if due <= now]
        self._scheduled = [(due, event) for due, event in self._scheduled if due > now]
        return ready

    def _response(self, command_line: str, payload: dict[str, object]) -> tuple[str, dict[str, object]]:
        return (
            "response",
            {
                "command": command_line.upper(),
                "status": "OK",
                "payload": {key: str(value) for key, value in payload.items()},
                "raw_payload": " ".join(f"{key}={value}" for key, value in payload.items()),
            },
        )

    @staticmethod
    def _error(command_line: str, message: str) -> tuple[str, dict[str, object]]:
        return "error", {"command": command_line.upper(), "status": message}

    def _build_response(self, command_line: str) -> tuple[str, dict[str, object]]:
        parts = command_line.split()
        if not parts:
            return self._error(command_line, "comando vazio")
        command = parts[0].upper()
        if command == "PROFILE" and len(parts) == 2:
            profile = parts[1].upper()
            profile_data = self.fixture.get("profiles", {}).get(profile)
            if not profile_data:
                return self._error(command_line, "perfil ausente na fixture")
            self.active_profile = profile
            return self._response(command_line, {"profile": profile, "cpu_mhz": profile_data["cpu_mhz"], "radio": "off"})
        if command == "MISSION" and len(parts) == 3:
            scenario, payload_hex = parts[1].upper(), parts[2].upper()
            if payload_hex != self.config.payload_hex:
                return self._error(command_line, "payload difere da campanha oficial")
            profile_data = self.fixture.get("profiles", {}).get(self.active_profile, {})
            mission = profile_data.get("missions", {}).get(scenario)
            if not mission:
                return self._error(command_line, "cenário ausente na fixture")
            payload = {
                **mission,
                "profile": self.active_profile,
                "cpu_mhz": profile_data["cpu_mhz"],
                "fixture_source": self.fixture.get("source_path"),
                "fixture_sha256": self.fixture.get("source_sha256"),
            }
            return self._response(command_line, payload)
        if command == "ANALOG" and len(parts) == 2 and parts[1].upper() == "POT":
            return self._response(command_line, {"pot": self.pot_value})
        if command == "FAULT" and len(parts) == 5:
            guard = parts[1].upper()
            try:
                payload = bytearray.fromhex(parts[2])
                byte_index = int(parts[3], 10)
                bit_mask = int(parts[4], 0)
                if not 0 <= byte_index < len(payload):
                    raise ValueError("índice fora do payload")
                if bit_mask <= 0 or bit_mask > 0x80 or bit_mask & (bit_mask - 1):
                    raise ValueError("máscara não é single-bit")
            except ValueError as exc:
                return self._error(command_line, str(exc))
            before = payload[byte_index]
            crc_before = zlib.crc32(payload) & 0xFFFFFFFF
            payload[byte_index] ^= bit_mask
            after = payload[byte_index]
            crc_after = zlib.crc32(payload) & 0xFFFFFFFF
            result = "DETECTED_GUARD" if guard == "CRC32" else "SILENT"
            return self._response(
                command_line,
                {
                    "result": result,
                    "guard": guard,
                    "payload_len": len(payload),
                    "byte_index": byte_index,
                    "bit_mask": f"0x{bit_mask:02X}",
                    "before_byte": f"0x{before:02X}",
                    "after_byte": f"0x{after:02X}",
                    "crc_before": f"0x{crc_before:08X}",
                    "crc_after": f"0x{crc_after:08X}",
                    "elapsed_us": 0,
                    "fixture_source": "deterministic-offline-model",
                },
            )
        if command == "STATUS":
            profile_data = self.fixture.get("profiles", {}).get(self.active_profile, {})
            return self._response(
                command_line,
                {
                    "profile": self.active_profile,
                    "cpu_mhz": profile_data.get("cpu_mhz", 0),
                    "pqc": "fixture",
                    "pqc_target": "ML-KEM-512",
                },
            )
        return self._error(command_line, "comando não disponível na fixture")


class StandController:
    _ALLOWED_TRANSITIONS = {
        DemoState.ATTRACT: {DemoState.INTRO, DemoState.ERROR},
        DemoState.INTRO: {DemoState.RUN_240, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.RUN_240: {DemoState.RUN_80, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.RUN_80: {DemoState.SELECT_BIT, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.SELECT_BIT: {DemoState.FAULT_NONE, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.FAULT_NONE: {DemoState.FAULT_CRC, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.FAULT_CRC: {DemoState.SUMMARY, DemoState.ATTRACT, DemoState.ERROR},
        DemoState.SUMMARY: {DemoState.ATTRACT, DemoState.ERROR},
        DemoState.ERROR: {DemoState.ATTRACT},
    }

    def __init__(self, config: StandConfig, send_command, *, mode: str, logger: StandSessionLogger | None = None, now: float | None = None):
        if mode not in {"hardware", "simulated"}:
            raise ValueError("mode deve ser hardware ou simulated")
        self.config = config
        self.send_command = send_command
        self.mode = mode
        self.logger = logger
        now = time.monotonic() if now is None else now
        self.state = DemoState.ATTRACT
        self.state_entered_at = now
        self.last_interaction_at = now
        self.last_button_at = -math.inf
        self.connection_status = "AGUARDANDO HANDSHAKE" if mode == "hardware" else "CARREGANDO FIXTURE OFICIAL"
        self.connected = False
        self.handshake_ok = False
        self.handshake: dict[str, str] = {}
        self.pending: PendingCommand | None = None
        self.substage = "idle"
        self.hold_until: float | None = None
        self.next_pot_poll_at = now
        self.selection_lock_requested = False
        self.selection: FaultSelection | None = None
        self.measurements: dict[str, HardwareMeasurement] = {}
        self.animations: dict[str, AnimationModel] = {}
        self.fault_results: dict[str, FaultMeasurement] = {}
        self.error_message = ""
        self.rejected_events = 0
        self.cycle_index = 0
        self.cycle_started_at: float | None = None
        self.last_cycle_duration: float | None = None
        self.completed_cycles = 0
        self.last_pot_value: int | None = None
        self._log("controller_ready", state=self.state.value)

    @property
    def ready(self) -> bool:
        return self.connected and self.handshake_ok

    @property
    def measurement_source_label(self) -> str:
        if self.mode == "hardware":
            return "MEDIDO AGORA NA BLACKBOARD WISDOM"
        return "CAMPANHA OFICIAL 2026-07-02 — FIXTURE OFFLINE"

    @property
    def persistent_mode_label(self) -> str:
        if self.mode == "simulated":
            return "MODO VISUAL SIMULADO — SEM LEITURA ATUAL DA PLACA"
        if self.ready:
            return "HARDWARE REAL — BLACKBOARD WISDOM CONECTADA"
        return "HARDWARE NÃO CONFIRMADO — AGUARDANDO WISDOM"

    def state_elapsed(self, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        return max(0.0, now - self.state_entered_at)

    def _log(self, event: str, **fields: object) -> None:
        if self.logger is not None:
            self.logger.write(event, **fields)

    def transition(self, new_state: DemoState, *, reason: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if new_state not in self._ALLOWED_TRANSITIONS[self.state]:
            raise StandError(f"transição inválida: {self.state.value} -> {new_state.value}")
        previous = self.state
        self.state = new_state
        self.state_entered_at = now
        self.last_interaction_at = now
        self._log("transition", previous=previous.value, state=new_state.value, reason=reason)

    def _send(self, command: str, purpose: str, *, expected: dict[str, object] | None = None, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if self.pending is not None:
            self._enter_error("comando duplicado bloqueado", now=now)
            return False
        if not self.ready:
            self._enter_error("hardware/fixture sem handshake confirmado", now=now)
            return False
        self.pending = PendingCommand(
            command=command.upper(),
            purpose=purpose,
            deadline=now + self.config.serial_timeout_seconds,
            expected=dict(expected or {}),
        )
        self._log("command_sent", command=command, purpose=purpose, state=self.state.value)
        try:
            self.send_command(command, timeout=self.config.serial_timeout_seconds)
        except Exception as exc:  # transport boundary; converted to an explicit UI error
            self.pending = None
            self._enter_error(f"falha ao enfileirar comando: {exc}", now=now)
            return False
        return True

    def handle_serial_event(self, event_type: str, event: dict[str, object], *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if event_type == "state":
            self._handle_connection_state(event, now=now)
            return
        if event_type == "event":
            if str(event.get("name", "")).upper() == "BUTTON_PING":
                self.handle_button(now=now, origin="physical")
            else:
                self.rejected_events += 1
                self._log("event_rejected", event_type=event_type, payload=event)
            return
        if event_type == "error":
            self._log("transport_error", payload=event)
            self._enter_error(str(event.get("status", "erro serial")), now=now)
            return
        if event_type != "response":
            self.rejected_events += 1
            self._log("event_rejected", event_type=event_type, payload=event)
            return

        command = str(event.get("command", "")).upper()
        status = str(event.get("status", "UNKNOWN")).upper()
        payload_obj = event.get("payload", {})
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        self._log("response_received", command=command, status=status, raw_response=payload)
        if command == "HELLO" and self.pending is None:
            self._handle_hello(payload, now=now)
            return
        if self.pending is None:
            self.rejected_events += 1
            self._log("response_rejected", reason="no_pending_command", command=command)
            return
        pending = self.pending
        if command != pending.command:
            self.rejected_events += 1
            self._enter_error(f"resposta fora de ordem: {command}", now=now)
            return
        self.pending = None
        if status != "OK":
            self._enter_error(f"{command} retornou {status}", now=now)
            return
        try:
            self._accept_response(pending, payload, now=now)
        except (StandProtocolError, ValueError) as exc:
            self._enter_error(str(exc), now=now)

    def _handle_hello(self, payload: dict[str, object], *, now: float) -> None:
        node = str(payload.get("node", ""))
        board = str(payload.get("board", ""))
        proto = str(payload.get("proto", ""))
        valid_hardware = node == "PQC-SAT-WISDOM" and board == "BlackBoard-Wisdom" and proto == "V1"
        valid_fixture = self.mode == "simulated" and node == "OFFLINE-FIXTURE" and proto == "V1"
        if not (valid_hardware or valid_fixture):
            self._enter_error(f"handshake rejeitado: node={node} board={board} proto={proto}", now=now)
            return
        self.handshake_ok = True
        self.handshake = {key: str(value) for key, value in payload.items()}
        self._log("handshake", mode=self.mode, payload=self.handshake)

    def _handle_connection_state(self, payload: dict[str, object], *, now: float) -> None:
        was_connected = self.connected
        self.connected = bool(payload.get("connected"))
        self.connection_status = str(payload.get("status", "SERIAL"))
        if not self.connected:
            self.handshake_ok = False
            self.handshake = {}
            if self.pending is not None:
                self._log("command_cancelled", command=self.pending.command, reason="disconnect")
                self.pending = None
        self._log("connection", connected=self.connected, status=self.connection_status)
        if was_connected and not self.connected and self.state not in {DemoState.ATTRACT, DemoState.ERROR}:
            self._enter_error("Wisdom desconectada; dados ao vivo interrompidos", now=now)

    def _accept_response(self, pending: PendingCommand, payload: dict[str, object], *, now: float) -> None:
        purpose = pending.purpose
        if purpose in {"profile_240", "restore_240", "reset_restore"}:
            parse_profile_response(payload, self.config.baseline_name, self.config.baseline_mhz)
            if purpose == "profile_240":
                self.substage = "mission_classic"
                self._send_mission("CLASSIC", "mission_classic_240", self.config.baseline_name, self.config.baseline_mhz, now)
            elif purpose == "restore_240":
                self.substage = "select_ready"
                self.next_pot_poll_at = now
            else:
                self.substage = "idle"
            return
        if purpose == "profile_80":
            parse_profile_response(payload, self.config.limited_name, self.config.limited_mhz)
            self.substage = "mission_pqc_80"
            self._send_mission("PQC", "mission_pqc_80", self.config.limited_name, self.config.limited_mhz, now)
            return
        if purpose.startswith("mission_"):
            self._accept_mission(pending, payload, now=now)
            return
        if purpose == "pot":
            pot_value = _required_int(payload, "pot")
            previous = self.selection
            self.selection = fault_selection_from_pot(pot_value, len(self.config.payload_bytes), self.config)
            if previous is None or previous.pot_value != self.selection.pot_value:
                self.last_interaction_at = now
                self._log("fault_selection", **asdict(self.selection))
            self.last_pot_value = self.selection.pot_value
            self.next_pot_poll_at = now + self.config.pot_poll_interval_seconds
            if self.selection_lock_requested:
                self.selection_lock_requested = False
                self._begin_fault_none(now)
            return
        if purpose in {"fault_none", "fault_crc"}:
            self._accept_fault(pending, payload, now=now)
            return
        raise StandProtocolError(f"propósito de resposta desconhecido: {purpose}")

    def _send_mission(self, scenario: str, purpose: str, profile: str, profile_mhz: int, now: float) -> None:
        command = f"MISSION {scenario} {self.config.payload_hex}"
        self._send(
            command,
            purpose,
            expected={"scenario": scenario, "profile": profile, "profile_mhz": profile_mhz},
            now=now,
        )

    def _accept_mission(self, pending: PendingCommand, payload: dict[str, object], *, now: float) -> None:
        scenario = str(pending.expected["scenario"])
        profile = str(pending.expected["profile"])
        profile_mhz = int(pending.expected["profile_mhz"])
        source = "hardware-live" if self.mode == "hardware" else "official-campaign-fixture"
        measurement = parse_mission_response(
            pending.command,
            payload,
            scenario=scenario,
            profile=profile,
            profile_mhz=profile_mhz,
            payload_hex=self.config.payload_hex,
            source=source,
        )
        key = f"{scenario}_{profile_mhz}"
        self.measurements[key] = measurement
        self.animations[key] = AnimationModel.for_measurement(measurement, self.config)
        self._log("measurement_accepted", key=key, measurement=asdict(measurement))
        if pending.purpose == "mission_classic_240":
            self.substage = "classic_hold"
            self.hold_until = now + min(3.5, self.config.comparison_hold_seconds / 2)
        elif pending.purpose == "mission_pqc_240":
            classic = self.measurements.get(f"CLASSIC_{self.config.baseline_mhz}")
            if classic is None or classic.payload_hex != measurement.payload_hex:
                raise StandProtocolError("CLASSIC e PQC não usaram o mesmo payload")
            self.substage = "comparison_hold"
            self.hold_until = now + self.config.comparison_hold_seconds
        elif pending.purpose == "mission_pqc_80":
            pqc_240 = self.measurements.get(f"PQC_{self.config.baseline_mhz}")
            if pqc_240 is None or pqc_240.payload_hex != measurement.payload_hex:
                raise StandProtocolError("PQC 240/80 não usou o mesmo payload")
            if pqc_240.bytes_total != measurement.bytes_total:
                raise StandProtocolError("tamanho do pacote mudou entre 240 e 80 MHz")
            self.substage = "comparison_hold"
            self.hold_until = now + self.config.comparison_hold_seconds

    def _accept_fault(self, pending: PendingCommand, payload: dict[str, object], *, now: float) -> None:
        if self.selection is None:
            raise StandProtocolError("falha respondeu sem seleção congelada")
        guard = "NONE" if pending.purpose == "fault_none" else "CRC32"
        source = "hardware-live" if self.mode == "hardware" else "deterministic-offline-model"
        measurement = parse_fault_response(
            pending.command,
            payload,
            expected_guard=guard,
            selection=self.selection,
            source=source,
        )
        self.fault_results[guard] = measurement
        self._log("fault_accepted", guard=guard, measurement=asdict(measurement))
        if guard == "CRC32":
            previous = self.fault_results.get("NONE")
            if previous is None:
                raise StandProtocolError("CRC32 executado sem ensaio NONE anterior")
            same_fault = (
                previous.byte_index == measurement.byte_index
                and previous.bit_mask == measurement.bit_mask
                and previous.before_byte == measurement.before_byte
                and previous.after_byte == measurement.after_byte
            )
            if not same_fault:
                raise StandProtocolError("NONE e CRC32 não repetiram exatamente a mesma falha")
        self.substage = "result_hold"
        self.hold_until = now + self.config.fault_hold_seconds

    def handle_button(self, *, now: float | None = None, origin: str = "operator") -> bool:
        now = time.monotonic() if now is None else now
        if now - self.last_button_at < self.config.button_debounce_seconds:
            self._log("button_rejected", reason="debounce", state=self.state.value, origin=origin)
            return False
        self.last_button_at = now
        self.last_interaction_at = now
        self._log("button", state=self.state.value, origin=origin)
        if self.state == DemoState.ATTRACT:
            if not self.ready or self.pending is not None:
                self._log("button_rejected", reason="not_ready", state=self.state.value, origin=origin)
                return False
            self.cycle_index += 1
            self.cycle_started_at = now
            self.transition(DemoState.INTRO, reason="visitor_button", now=now)
            self._log("cycle_start", cycle=self.cycle_index, mode=self.mode, payload_hex=self.config.payload_hex)
            return True
        if self.state == DemoState.SELECT_BIT and self.substage == "select_ready":
            if self.pending is not None:
                if self.pending.purpose == "pot":
                    self.selection_lock_requested = True
                    return True
                return False
            if self.selection is None:
                self.selection_lock_requested = True
                return self._send("ANALOG POT", "pot", now=now)
            self._begin_fault_none(now)
            return True
        if self.state in {DemoState.SUMMARY, DemoState.ERROR}:
            self.reset_to_attract(reason="visitor_restart", now=now)
            return True
        self._log("button_rejected", reason="state_does_not_accept", state=self.state.value, origin=origin)
        return False

    def note_interaction(self, *, now: float | None = None) -> None:
        self.last_interaction_at = time.monotonic() if now is None else now

    def _begin_run_240(self, now: float) -> None:
        self.transition(DemoState.RUN_240, reason="intro_complete", now=now)
        self.substage = "profile_240"
        self._send(f"PROFILE {self.config.baseline_name}", "profile_240", now=now)

    def _begin_run_80(self, now: float) -> None:
        self.transition(DemoState.RUN_80, reason="comparison_240_complete", now=now)
        self.substage = "profile_80"
        self._send(f"PROFILE {self.config.limited_name}", "profile_80", now=now)

    def _begin_select_bit(self, now: float) -> None:
        self.transition(DemoState.SELECT_BIT, reason="comparison_80_complete", now=now)
        self.substage = "restore_240"
        self._send(f"PROFILE {self.config.baseline_name}", "restore_240", now=now)

    def _begin_fault_none(self, now: float) -> None:
        if self.selection is None:
            self._enter_error("nenhum bit selecionado", now=now)
            return
        self.transition(DemoState.FAULT_NONE, reason="bit_locked", now=now)
        self.substage = "fault_none"
        command = (
            f"FAULT NONE {self.config.payload_hex} "
            f"{self.selection.byte_index} 0x{self.selection.bit_mask:02X}"
        )
        self._send(command, "fault_none", now=now)

    def _begin_fault_crc(self, now: float) -> None:
        if self.selection is None:
            self._enter_error("seleção perdida antes do CRC32", now=now)
            return
        self.transition(DemoState.FAULT_CRC, reason="repeat_same_fault", now=now)
        self.substage = "fault_crc"
        command = (
            f"FAULT CRC32 {self.config.payload_hex} "
            f"{self.selection.byte_index} 0x{self.selection.bit_mask:02X}"
        )
        self._send(command, "fault_crc", now=now)

    def _begin_summary(self, now: float) -> None:
        self.transition(DemoState.SUMMARY, reason="crc_result_complete", now=now)
        self.substage = "summary"
        if self.cycle_started_at is not None:
            self.last_cycle_duration = now - self.cycle_started_at
        self.completed_cycles += 1
        self._log(
            "cycle_complete",
            cycle=self.cycle_index,
            duration_seconds=self.last_cycle_duration,
            measurements={key: asdict(value) for key, value in self.measurements.items()},
            faults={key: asdict(value) for key, value in self.fault_results.items()},
        )

    def _enter_error(self, message: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.error_message = message
        self.pending = None
        if self.state != DemoState.ERROR:
            if DemoState.ERROR in self._ALLOWED_TRANSITIONS[self.state]:
                self.transition(DemoState.ERROR, reason="error", now=now)
        self._log("error", message=message, state=self.state.value)

    def reset_to_attract(self, *, reason: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if self.cycle_started_at is not None and self.state != DemoState.SUMMARY:
            self._log("cycle_aborted", cycle=self.cycle_index, state=self.state.value, reason=reason)
        if self.state != DemoState.ATTRACT:
            self.transition(DemoState.ATTRACT, reason=reason, now=now)
        self.pending = None
        self.substage = "idle"
        self.hold_until = None
        self.selection_lock_requested = False
        self.selection = None
        self.measurements.clear()
        self.animations.clear()
        self.fault_results.clear()
        self.error_message = ""
        self.cycle_started_at = None
        self.last_interaction_at = now
        if self.ready:
            self.substage = "reset_restore"
            self._send(f"PROFILE {self.config.baseline_name}", "reset_restore", now=now)

    def update(self, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if self.pending is not None and now >= self.pending.deadline:
            command = self.pending.command
            self.pending = None
            self._enter_error(f"timeout aguardando {command}", now=now)
            return
        if self.state == DemoState.INTRO and self.state_elapsed(now) >= self.config.intro_seconds:
            self._begin_run_240(now)
            return
        if self.state == DemoState.RUN_240:
            if self.substage == "classic_hold" and self.hold_until is not None and now >= self.hold_until:
                self.substage = "mission_pqc"
                self._send_mission("PQC", "mission_pqc_240", self.config.baseline_name, self.config.baseline_mhz, now)
            elif self.substage == "comparison_hold" and self.hold_until is not None and now >= self.hold_until:
                self._begin_run_80(now)
            return
        if self.state == DemoState.RUN_80:
            if self.substage == "comparison_hold" and self.hold_until is not None and now >= self.hold_until:
                self._begin_select_bit(now)
            return
        if self.state == DemoState.SELECT_BIT:
            if now - self.last_interaction_at >= self.config.interaction_timeout_seconds:
                self.reset_to_attract(reason="selection_inactivity", now=now)
                return
            if self.substage == "select_ready" and self.pending is None and now >= self.next_pot_poll_at:
                self._send("ANALOG POT", "pot", now=now)
            return
        if self.state == DemoState.FAULT_NONE:
            if self.substage == "result_hold" and self.hold_until is not None and now >= self.hold_until:
                self._begin_fault_crc(now)
            return
        if self.state == DemoState.FAULT_CRC:
            if self.substage == "result_hold" and self.hold_until is not None and now >= self.hold_until:
                self._begin_summary(now)
            return
        if self.state == DemoState.SUMMARY and self.state_elapsed(now) >= self.config.auto_reset_seconds:
            self.reset_to_attract(reason="summary_auto_reset", now=now)


def _format_elapsed_us(value: int | None) -> str:
    if value is None:
        return "AGUARDANDO"
    if value < 1000:
        return f"{value:,} µs".replace(",", ".")
    return f"{value / 1000.0:.2f} ms".replace(".", ",")


def _format_ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}×".replace(".", ",")


class StandRenderer:
    """Renders every state to a fixed logical canvas, then the app scales it."""

    def __init__(self, size: tuple[int, int] = VIRTUAL_SIZE):
        self.size = size
        self.surface = pygame.Surface(size)
        self.font_title = pygame.font.SysFont("dejavusans", 44, bold=True)
        self.font_h1 = pygame.font.SysFont("dejavusans", 34, bold=True)
        self.font_h2 = pygame.font.SysFont("dejavusans", 27, bold=True)
        self.font_body = pygame.font.SysFont("dejavusans", 23)
        self.font_body_bold = pygame.font.SysFont("dejavusans", 23, bold=True)
        self.font_small = pygame.font.SysFont("dejavusans", 17)
        self.font_mono = pygame.font.SysFont("dejavusansmono", 21, bold=True)
        self.font_binary = pygame.font.SysFont("dejavusansmono", 18, bold=True)
        self.font_metric = pygame.font.SysFont("dejavusans", 39, bold=True)
        rng = random.Random(20260720)
        self.stars = [(rng.randrange(size[0]), rng.randrange(82, size[1] - 38), rng.choice((1, 1, 1, 2))) for _ in range(105)]
        self.action_rects: dict[str, pygame.Rect] = {}

    @staticmethod
    def _text(surface: pygame.Surface, font: pygame.font.Font, text: str, color, pos, *, center=False, right=False) -> pygame.Rect:
        rendered = font.render(text, True, color)
        rect = rendered.get_rect()
        if center:
            rect.center = pos
        elif right:
            rect.topright = pos
        else:
            rect.topleft = pos
        surface.blit(rendered, rect)
        return rect

    @staticmethod
    def _wrap(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def _wrapped(self, surface, font, text, color, rect: pygame.Rect, *, line_gap=5, center=False) -> int:
        y = rect.y
        line_h = font.get_linesize() + line_gap
        for line in self._wrap(font, text, rect.width):
            x = rect.centerx if center else rect.x
            self._text(surface, font, line, color, (x, y + line_h // 2) if center else (x, y), center=center)
            y += line_h
        return y

    @staticmethod
    def _panel(surface, rect: pygame.Rect, *, border=C_LINE, fill=C_PANEL, radius=18, width=2) -> None:
        pygame.draw.rect(surface, fill, rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)

    def _background(self, surface: pygame.Surface, t: float) -> None:
        surface.fill(C_BG)
        for x, y, radius in self.stars:
            pulse = 0.62 + 0.38 * math.sin(t * 0.7 + x * 0.019)
            value = int(145 + pulse * 90)
            pygame.draw.circle(surface, (value, value, min(255, value + 20)), (x, y), radius)
        glow = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.circle(glow, (0, 115, 170, 18), (220, 420), 340)
        pygame.draw.circle(glow, (126, 45, 190, 13), (1140, 300), 290)
        surface.blit(glow, (0, 0))

    def _header(self, surface: pygame.Surface, controller: StandController) -> None:
        pygame.draw.rect(surface, (5, 14, 29), (0, 0, self.size[0], 72))
        pygame.draw.line(surface, C_CYAN, (0, 71), (self.size[0], 71), 2)
        self._text(surface, self.font_h2, "PQC-SAT", C_CYAN, (30, 18))
        self._text(surface, self.font_small, "MISSÃO GUARDIÕES DO BIT", C_WHITE, (170, 27))

        sequence = [DemoState.INTRO, DemoState.RUN_240, DemoState.RUN_80, DemoState.SELECT_BIT, DemoState.FAULT_NONE, DemoState.FAULT_CRC, DemoState.SUMMARY]
        labels = ["MISSÃO", "240", "80", "BIT", "SEM CRC", "CRC", "FIM"]
        active_index = sequence.index(controller.state) if controller.state in sequence else -1
        start_x = 485
        for index, label in enumerate(labels):
            x = start_x + index * 73
            color = C_GREEN if index < active_index else (C_CYAN if index == active_index else C_LINE)
            pygame.draw.circle(surface, color, (x, 25), 7)
            self._text(surface, self.font_small, label, color if index <= active_index else C_DIM, (x, 48), center=True)

        mode_color = C_PURPLE if controller.mode == "simulated" else (C_GREEN if controller.ready else C_RED)
        badge = pygame.Rect(1034, 14, 302, 42)
        badge_fill = tuple(max(10, int(channel * 0.18)) for channel in mode_color)
        pygame.draw.rect(surface, badge_fill, badge, border_radius=11)
        pygame.draw.rect(surface, mode_color, badge, width=2, border_radius=11)
        short_label = "SIMULADO • FIXTURE OFICIAL" if controller.mode == "simulated" else ("WISDOM • AO VIVO" if controller.ready else "AGUARDANDO WISDOM")
        self._text(surface, self.font_small, short_label, mode_color, badge.center, center=True)

    def _footer(self, surface: pygame.Surface, controller: StandController) -> None:
        y = self.size[1] - 36
        pygame.draw.rect(surface, (5, 14, 29), (0, y, self.size[0], 36))
        pygame.draw.line(surface, C_LINE, (0, y), (self.size[0], y), 1)
        self._text(
            surface,
            self.font_small,
            "FALHA INJETADA POR SOFTWARE • SEM RADIAÇÃO REAL • OBC EDUCACIONAL DE BANCADA",
            C_DIM,
            (24, y + 9),
        )
        connection = controller.connection_status[:45]
        self._text(surface, self.font_small, connection, C_CYAN if controller.ready else C_ORANGE, (self.size[0] - 24, y + 9), right=True)

    def render(self, controller: StandController, *, now: float | None = None, diagnostic=False) -> pygame.Surface:
        now = time.monotonic() if now is None else now
        self.action_rects = {}
        self._background(self.surface, now)
        self._header(self.surface, controller)
        draw_method = getattr(self, f"_draw_{controller.state.value.lower()}")
        draw_method(self.surface, controller, now)
        if controller.mode == "simulated":
            banner = pygame.Rect(330, 78, 706, 34)
            pygame.draw.rect(self.surface, (73, 28, 94), banner, border_radius=8)
            pygame.draw.rect(self.surface, C_PURPLE, banner, width=2, border_radius=8)
            self._text(self.surface, self.font_small, controller.persistent_mode_label, C_WHITE, banner.center, center=True)
        self._footer(self.surface, controller)
        if diagnostic:
            self._draw_diagnostic(self.surface, controller)
        return self.surface

    def _draw_attract(self, surface, controller: StandController, now: float) -> None:
        self._text(surface, self.font_title, "UM ÚNICO BIT PODE MUDAR", C_WHITE, (683, 171), center=True)
        self._text(surface, self.font_title, "UMA MISSÃO ESPACIAL", C_CYAN, (683, 224), center=True)
        self._wrapped(
            surface,
            self.font_body,
            "Você consegue descobrir qual proteção percebe a falha?",
            C_DIM,
            pygame.Rect(250, 270, 866, 45),
            center=True,
        )

        orbit = pygame.Rect(340, 337, 686, 205)
        pygame.draw.ellipse(surface, C_LINE, orbit, width=2)
        progress = (now * 0.075) % 1.0
        angle = progress * math.tau
        sat_x = int(orbit.centerx + math.cos(angle) * orbit.width * 0.49)
        sat_y = int(orbit.centery + math.sin(angle) * orbit.height * 0.49)
        pygame.draw.circle(surface, (36, 112, 197), (orbit.centerx, orbit.centery), 72)
        pygame.draw.circle(surface, C_CYAN, (orbit.centerx, orbit.centery), 72, width=2)
        pygame.draw.rect(surface, C_WHITE, (sat_x - 22, sat_y - 14, 44, 28), border_radius=4)
        pygame.draw.rect(surface, C_BLUE, (sat_x - 58, sat_y - 9, 34, 18))
        pygame.draw.rect(surface, C_BLUE, (sat_x + 24, sat_y - 9, 34, 18))
        packet_x = int(sat_x + (orbit.centerx - sat_x) * ((now * 0.55) % 1.0))
        packet_y = int(sat_y + (orbit.centery - sat_y) * ((now * 0.55) % 1.0))
        pygame.draw.circle(surface, C_YELLOW, (packet_x, packet_y), 7)

        cta = pygame.Rect(270, 584, 826, 84)
        self._panel(surface, cta, border=C_GREEN, fill=(10, 42, 46), radius=18, width=3)
        prompt = "PRESSIONE O BOTÃO DA PLACA PARA COMEÇAR" if controller.ready else "AGUARDE A CONEXÃO SEGURA COM A DEMONSTRAÇÃO"
        self._text(surface, self.font_body_bold, prompt, C_GREEN if controller.ready else C_ORANGE, cta.center, center=True)
        self.action_rects["button"] = cta

    def _draw_intro(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "MISSÃO: ENVIAR TELEMETRIA CRÍTICA À TERRA", C_WHITE, (683, 158), center=True)
        panel = pygame.Rect(100, 222, 1166, 315)
        self._panel(surface, panel, border=C_CYAN, fill=C_PANEL)
        self._text(surface, self.font_small, "MESMO PAYLOAD EM TODAS AS COMPARAÇÕES", C_DIM, (683, 258), center=True)
        self._text(surface, self.font_h1, controller.config.payload_display, C_CYAN, (683, 330), center=True)
        self._text(surface, self.font_mono, controller.config.payload, C_WHITE, (683, 403), center=True)
        self._text(surface, self.font_small, f"{len(controller.config.payload_bytes)} bytes • registrado em hexadecimal no log da sessão", C_DIM, (683, 455), center=True)
        self._text(surface, self.font_body_bold, "A seguir: baseline AES-GCM × ML-KEM + AES-GCM", C_GREEN, (683, 594), center=True)

    def _measurement_card(
        self,
        surface,
        rect: pygame.Rect,
        title: str,
        chain: str,
        measurement: HardwareMeasurement | None,
        animation: AnimationModel | None,
        color,
        now: float,
    ) -> None:
        self._panel(surface, rect, border=color, fill=C_PANEL)
        self._text(surface, self.font_h2, title, color, (rect.centerx, rect.y + 42), center=True)
        self._text(surface, self.font_small, chain, C_DIM, (rect.centerx, rect.y + 80), center=True)
        pygame.draw.line(surface, C_LINE, (rect.x + 26, rect.y + 108), (rect.right - 26, rect.y + 108), 1)
        if measurement is None:
            self._text(surface, self.font_h2, "AGUARDANDO RESPOSTA…", C_ORANGE, (rect.centerx, rect.centery + 20), center=True)
            return
        if animation is not None:
            rail_left = rect.x + 30
            rail_right = rect.right - 30
            progress = ((now * 1000.0) % animation.duration_ms) / animation.duration_ms
            packet_x = int(rail_left + progress * (rail_right - rail_left))
            pygame.draw.line(surface, C_LINE, (rail_left, rect.y + 116), (rail_right, rect.y + 116), 2)
            pygame.draw.circle(surface, color, (packet_x, rect.y + 116), 6)
        self._text(surface, self.font_small, "TEMPO MEDIDO", C_DIM, (rect.x + 42, rect.y + 133))
        self._text(surface, self.font_metric, _format_elapsed_us(measurement.elapsed_us), C_WHITE, (rect.x + 40, rect.y + 158))
        self._text(surface, self.font_small, "TRÁFEGO MODELADO", C_DIM, (rect.x + 42, rect.y + 222))
        self._text(surface, self.font_metric, f"{measurement.bytes_total} bytes", C_WHITE, (rect.x + 40, rect.y + 247))
        result_color = C_GREEN if measurement.result == "DELIVERED" else C_RED
        self._text(surface, self.font_body_bold, f"OK • {measurement.result}", result_color, (rect.x + 42, rect.bottom - 52))

    def _draw_run_240(self, surface, controller: StandController, now: float) -> None:
        self._text(surface, self.font_h1, "MESMA MENSAGEM, DUAS PROTEÇÕES — 240 MHz", C_WHITE, (683, 145), center=True)
        classic = controller.measurements.get(f"CLASSIC_{controller.config.baseline_mhz}")
        pqc = controller.measurements.get(f"PQC_{controller.config.baseline_mhz}")
        classic_key = f"CLASSIC_{controller.config.baseline_mhz}"
        pqc_key = f"PQC_{controller.config.baseline_mhz}"
        self._measurement_card(
            surface,
            pygame.Rect(72, 190, 575, 390),
            "BASELINE AES-GCM",
            "chave AES efêmera local → AES-GCM",
            classic,
            controller.animations.get(classic_key),
            C_BLUE,
            now,
        )
        self._measurement_card(
            surface,
            pygame.Rect(719, 190, 575, 390),
            "PÓS-QUÂNTICO",
            "ML-KEM → KDF → AES-GCM",
            pqc,
            controller.animations.get(pqc_key),
            C_PURPLE,
            now,
        )
        if classic and pqc:
            ratio_time = safe_ratio(pqc.elapsed_us, classic.elapsed_us)
            ratio_bytes = safe_ratio(pqc.bytes_total, classic.bytes_total)
            message = f"ML-KEM funcionou • {_format_ratio(ratio_time)} no tempo • {_format_ratio(ratio_bytes)} nos bytes"
            self._text(surface, self.font_body_bold, message, C_GREEN, (683, 616), center=True)
        else:
            self._text(surface, self.font_body, "Executando sequencialmente na placa com o mesmo payload…", C_ORANGE, (683, 616), center=True)
        self._text(surface, self.font_small, "A animação é didática; o valor numérico vem da medição real.", C_DIM, (683, 677), center=True)
        self._text(surface, self.font_small, controller.measurement_source_label, C_CYAN, (683, 704), center=True)

    def _draw_run_80(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "AGORA: APENAS 1/3 DO CLOCK", C_WHITE, (683, 145), center=True)
        pqc_240 = controller.measurements.get(f"PQC_{controller.config.baseline_mhz}")
        pqc_80 = controller.measurements.get(f"PQC_{controller.config.limited_mhz}")
        chart = pygame.Rect(160, 205, 1046, 348)
        self._panel(surface, chart, border=C_BLUE, fill=C_PANEL)
        pygame.draw.line(surface, C_LINE, (chart.x + 85, chart.bottom - 62), (chart.right - 60, chart.bottom - 62), 2)
        values = [pqc_240.elapsed_us if pqc_240 else 0, pqc_80.elapsed_us if pqc_80 else 0]
        max_value = max(values + [1])
        for index, (label, measurement, color) in enumerate((("240 MHz", pqc_240, C_CYAN), ("80 MHz", pqc_80, C_ORANGE))):
            x = chart.x + 255 + index * 460
            bar_h = int(210 * ((measurement.elapsed_us if measurement else 0) / max_value))
            pygame.draw.rect(surface, (*color, 35), (x - 85, chart.bottom - 62 - bar_h, 170, bar_h), border_radius=12)
            pygame.draw.rect(surface, color, (x - 85, chart.bottom - 62 - bar_h, 170, bar_h), width=3, border_radius=12)
            self._text(surface, self.font_h2, label, color, (x, chart.bottom - 32), center=True)
            value_text = _format_elapsed_us(measurement.elapsed_us) if measurement else "AGUARDANDO"
            self._text(surface, self.font_metric if measurement else self.font_body_bold, value_text, C_WHITE, (x, chart.y + 56), center=True)
            bytes_text = f"{measurement.bytes_total} bytes" if measurement else "—"
            self._text(surface, self.font_body, bytes_text, C_DIM, (x, chart.y + 105), center=True)
        if pqc_240 and pqc_80:
            ratio = safe_ratio(pqc_80.elapsed_us, pqc_240.elapsed_us)
            self._text(surface, self.font_body_bold, f"Latência {_format_ratio(ratio)} maior; pacote permaneceu com {pqc_80.bytes_total} bytes.", C_GREEN, (683, 594), center=True)
        self._text(surface, self.font_small, "80 MHz é um perfil experimental, não uma especificação universal de CubeSat.", C_YELLOW, (683, 651), center=True)
        self._text(surface, self.font_small, "A animação é didática; o valor numérico vem da medição real.", C_DIM, (683, 681), center=True)

    def _draw_select_bit(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "GIRE O POTENCIÔMETRO PARA ESCOLHER UM BIT", C_WHITE, (683, 145), center=True)
        selection = controller.selection
        payload = controller.config.payload_bytes
        selected_index = selection.byte_index if selection else 0
        window_len = min(8, len(payload))
        start = max(0, min(len(payload) - window_len, selected_index - window_len // 2))
        cell_w = 128
        x0 = (self.size[0] - window_len * cell_w) // 2
        y = 245
        for offset in range(window_len):
            index = start + offset
            selected = selection is not None and index == selection.byte_index
            rect = pygame.Rect(x0 + offset * cell_w + 3, y, cell_w - 8, 103)
            self._panel(surface, rect, border=C_YELLOW if selected else C_LINE, fill=(28, 37, 54) if selected else C_PANEL, radius=10, width=3 if selected else 1)
            self._text(surface, self.font_small, f"B{index:02d}", C_YELLOW if selected else C_DIM, (rect.centerx, rect.y + 19), center=True)
            self._text(surface, self.font_binary, f"{payload[index]:08b}", C_WHITE, (rect.centerx, rect.y + 54), center=True)
            char = chr(payload[index]) if 32 <= payload[index] < 127 else "."
            self._text(surface, self.font_small, char, C_CYAN, (rect.centerx, rect.y + 83), center=True)
        gauge = pygame.Rect(245, 415, 876, 28)
        pygame.draw.rect(surface, C_PANEL_2, gauge, border_radius=14)
        pygame.draw.rect(surface, C_LINE, gauge, width=2, border_radius=14)
        if selection:
            relative = (selection.pot_value - controller.config.pot_minimum) / (controller.config.pot_maximum - controller.config.pot_minimum)
            knob_x = int(gauge.x + relative * gauge.width)
            pygame.draw.circle(surface, C_YELLOW, (knob_x, gauge.centery), 18)
            technical = f"BYTE {selection.byte_index} • MÁSCARA 0x{selection.bit_mask:02X} • BIT GLOBAL {selection.bit_position} • POT {selection.pot_value}"
        else:
            technical = "AGUARDANDO LEITURA A39…"
        self._text(surface, self.font_small, technical, C_DIM, (683, 481), center=True)
        instruction = pygame.Rect(325, 552, 716, 82)
        self._panel(surface, instruction, border=C_GREEN, fill=(10, 42, 46), width=3)
        self._text(surface, self.font_h2, "PRESSIONE O BOTÃO PARA VIRAR ESTE BIT", C_GREEN, instruction.center, center=True)
        self.action_rects["button"] = instruction
        self._text(surface, self.font_small, "A seleção fica congelada e será repetida nos dois ensaios.", C_DIM, (683, 677), center=True)

    def _fault_binary(self, surface, measurement: FaultMeasurement | None, *, accent, pending_text: str) -> None:
        if measurement is None:
            self._text(surface, self.font_h2, pending_text, C_ORANGE, (683, 376), center=True)
            return
        before = f"{measurement.before_byte:08b}"
        after = f"{measurement.after_byte:08b}"
        self._text(surface, self.font_small, "ANTES", C_DIM, (330, 269))
        self._text(surface, self.font_metric, before, C_WHITE, (330, 298))
        self._text(surface, self.font_small, "DEPOIS", C_DIM, (330, 381))
        self._text(surface, self.font_metric, after, accent, (330, 410))
        bit_index = int(math.log2(measurement.bit_mask))
        self._text(surface, self.font_body_bold, f"↑ bit {bit_index} do byte {measurement.byte_index}", C_YELLOW, (777, 418))

    def _draw_fault_none(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "ENSAIO 1 — PAYLOAD SEM GUARDIÃO ADICIONAL", C_WHITE, (683, 145), center=True)
        result = controller.fault_results.get("NONE")
        panel = pygame.Rect(190, 208, 986, 355)
        self._panel(surface, panel, border=C_RED, fill=C_PANEL)
        self._fault_binary(surface, result, accent=C_RED, pending_text="APLICANDO XOR DE UM ÚNICO BIT NA WISDOM…")
        if result:
            self._text(surface, self.font_h2, "ALTERAÇÃO SILENCIOSA NESTE ENSAIO", C_RED, (683, 517), center=True)
        legend = "Este teste representa uma corrupção controlada do payload. Ele não é o teste de alteração do ciphertext AES-GCM."
        self._wrapped(surface, self.font_body_bold, legend, C_YELLOW, pygame.Rect(180, 594, 1006, 65), center=True)

    def _draw_fault_crc(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "ENSAIO 2 — EXATAMENTE O MESMO BIT + CRC32", C_WHITE, (683, 145), center=True)
        result = controller.fault_results.get("CRC32")
        panel = pygame.Rect(175, 205, 1016, 370)
        self._panel(surface, panel, border=C_GREEN, fill=C_PANEL)
        if result is None:
            self._text(surface, self.font_h2, "REPETINDO ÍNDICE E MÁSCARA NA WISDOM…", C_ORANGE, (683, 380), center=True)
        else:
            self._text(surface, self.font_small, "CRC SALVO ANTES DA FALHA", C_DIM, (310, 267))
            self._text(surface, self.font_metric, f"0x{result.crc_before:08X}", C_WHITE, (310, 300))
            self._text(surface, self.font_small, "CRC RECALCULADO DEPOIS", C_DIM, (755, 267))
            self._text(surface, self.font_metric, f"0x{result.crc_after:08X}", C_YELLOW, (755, 300))
            self._text(surface, self.font_h1, "RESULTADO: FALHA DETECTADA", C_GREEN, (683, 462), center=True)
            self._text(surface, self.font_small, f"mesmo byte {result.byte_index} • mesma máscara 0x{result.bit_mask:02X}", C_DIM, (683, 521), center=True)
        self._text(surface, self.font_body_bold, "O CRC transformou a alteração acidental em um erro observável.", C_GREEN, (683, 613), center=True)
        self._text(surface, self.font_small, "Ele não impede um atacante de recalcular o checksum.", C_YELLOW, (683, 656), center=True)

    def _draw_summary(self, surface, controller: StandController, now: float) -> None:
        self._text(surface, self.font_h1, "MISSÃO CONCLUÍDA", C_GREEN, (683, 137), center=True)
        conclusions = (
            ("1", "ML-KEM estabeleceu uma chave pós-quântica no ESP32.", C_PURPLE),
            ("2", "O maior custo apareceu em tempo e bytes.", C_CYAN),
            ("3", "CRC32 detectou o bit flip, mas não substitui autenticação.", C_GREEN),
        )
        for index, (number, text, color) in enumerate(conclusions):
            rect = pygame.Rect(165, 183 + index * 94, 1036, 76)
            self._panel(surface, rect, border=color, fill=C_PANEL, radius=14)
            pygame.draw.circle(surface, color, (rect.x + 43, rect.centery), 23)
            self._text(surface, self.font_body_bold, number, C_BG, (rect.x + 43, rect.centery), center=True)
            self._text(surface, self.font_body_bold, text, C_WHITE, (rect.x + 84, rect.y + 23))
        cards = (
            ("ML-KEM", "estabelece a chave", C_PURPLE),
            ("AES-GCM", "cifra e autentica", C_CYAN),
            ("CRC32", "detecta erro acidental", C_GREEN),
        )
        for index, (title, subtitle, color) in enumerate(cards):
            rect = pygame.Rect(165 + index * 350, 494, 336, 102)
            self._panel(surface, rect, border=color, fill=C_PANEL)
            self._text(surface, self.font_h2, title, color, (rect.centerx, rect.y + 34), center=True)
            self._text(surface, self.font_small, subtitle, C_WHITE, (rect.centerx, rect.y + 72), center=True)
        remaining = max(0, math.ceil(controller.config.auto_reset_seconds - controller.state_elapsed(now)))
        restart = pygame.Rect(320, 625, 726, 64)
        self._panel(surface, restart, border=C_CYAN, fill=(10, 35, 52), width=2)
        self._text(surface, self.font_body_bold, f"PRESSIONE O BOTÃO PARA RECOMEÇAR  •  {remaining}s", C_CYAN, restart.center, center=True)
        self.action_rects["button"] = restart

    def _draw_error(self, surface, controller: StandController, now: float) -> None:
        del now
        self._text(surface, self.font_h1, "A DEMONSTRAÇÃO FOI INTERROMPIDA COM SEGURANÇA", C_RED, (683, 160), center=True)
        panel = pygame.Rect(185, 220, 996, 250)
        self._panel(surface, panel, border=C_RED, fill=C_PANEL)
        self._text(surface, self.font_h2, "NENHUM DADO NOVO SERÁ INVENTADO", C_YELLOW, (683, 268), center=True)
        self._wrapped(surface, self.font_body, controller.error_message or "Falha desconhecida", C_WHITE, pygame.Rect(255, 324, 856, 82), center=True)
        self._text(surface, self.font_small, controller.connection_status, C_DIM, (683, 434), center=True)
        retry = pygame.Rect(247, 535, 400, 78)
        home = pygame.Rect(719, 535, 400, 78)
        self._panel(surface, retry, border=C_GREEN, fill=(10, 42, 46), width=3)
        self._panel(surface, home, border=C_CYAN, fill=(10, 35, 52), width=3)
        self._text(surface, self.font_h2, "TENTAR NOVAMENTE", C_GREEN, retry.center, center=True)
        self._text(surface, self.font_h2, "VOLTAR AO INÍCIO", C_CYAN, home.center, center=True)
        self.action_rects["retry"] = retry
        self.action_rects["home"] = home

    def _draw_diagnostic(self, surface, controller: StandController) -> None:
        panel = pygame.Rect(932, 118, 410, 244)
        overlay = pygame.Surface(panel.size, pygame.SRCALPHA)
        overlay.fill((2, 8, 18, 235))
        surface.blit(overlay, panel.topleft)
        pygame.draw.rect(surface, C_YELLOW, panel, width=2, border_radius=10)
        lines = [
            "DIAGNÓSTICO ADMINISTRATIVO (F12)",
            f"state={controller.state.value}",
            f"substage={controller.substage}",
            f"ready={controller.ready} mode={controller.mode}",
            f"pending={controller.pending.command if controller.pending else 'NONE'}",
            f"cycles={controller.completed_cycles}",
            f"rejected={controller.rejected_events}",
            f"payload_sha256={hashlib.sha256(controller.config.payload_bytes).hexdigest()[:12]}",
        ]
        for index, line in enumerate(lines):
            self._text(surface, self.font_small, line, C_YELLOW if index == 0 else C_WHITE, (panel.x + 16, panel.y + 15 + index * 27))


class StandApp:
    def __init__(
        self,
        config: StandConfig,
        client,
        *,
        mode: str,
        logger: StandSessionLogger,
        windowed: bool = False,
        diagnostic: bool = False,
        max_runtime_seconds: float | None = None,
    ):
        pygame.init()
        pygame.display.set_caption("PQC-SAT — Missão Guardiões do Bit")
        self.config = config
        self.client = client
        self.mode = mode
        self.logger = logger
        self.windowed = windowed
        self.diagnostic = diagnostic
        self.max_runtime_seconds = max_runtime_seconds
        self.screen = self._create_display()
        self.clock = pygame.time.Clock()
        self.renderer = StandRenderer()
        self.controller = StandController(config, client.send, mode=mode, logger=logger)
        self.running = True
        self.started_at = time.monotonic()

    def _create_display(self) -> pygame.Surface:
        if self.windowed:
            return pygame.display.set_mode(self.config.windowed_size, pygame.RESIZABLE | pygame.DOUBLEBUF)
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)

    def _toggle_fullscreen(self) -> None:
        self.windowed = not self.windowed
        self.screen = self._create_display()
        self.logger.write("display_mode", windowed=self.windowed, size=self.screen.get_size())

    def _to_virtual(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        screen_w, screen_h = self.screen.get_size()
        scale = min(screen_w / VIRTUAL_SIZE[0], screen_h / VIRTUAL_SIZE[1])
        width, height = int(VIRTUAL_SIZE[0] * scale), int(VIRTUAL_SIZE[1] * scale)
        left, top = (screen_w - width) // 2, (screen_h - height) // 2
        if not (left <= pos[0] < left + width and top <= pos[1] < top + height):
            return None
        return int((pos[0] - left) / scale), int((pos[1] - top) / scale)

    def _adjust_simulated_pot(self, delta: int) -> None:
        if self.mode != "simulated" or not hasattr(self.client, "set_pot"):
            return
        current = int(getattr(self.client, "pot_value", 0))
        self.client.set_pot(current + delta)
        self.controller.note_interaction()

    def _handle_action(self, action: str) -> None:
        if action == "button":
            self.controller.handle_button(origin="screen")
        elif action == "retry":
            self.controller.reset_to_attract(reason="operator_retry")
        elif action == "home":
            self.controller.reset_to_attract(reason="operator_home")

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            if event.key == pygame.K_q and mods & pygame.KMOD_CTRL:
                self.running = False
            elif event.key == pygame.K_ESCAPE:
                self._toggle_fullscreen()
            elif event.key in {pygame.K_SPACE, pygame.K_RETURN}:
                self.controller.handle_button(origin="keyboard")
            elif event.key == pygame.K_F12:
                self.diagnostic = not self.diagnostic
            elif event.key == pygame.K_HOME:
                self.controller.reset_to_attract(reason="operator_home_key")
            elif event.key == pygame.K_r and self.controller.state == DemoState.ERROR:
                self.controller.reset_to_attract(reason="operator_retry_key")
            elif event.key == pygame.K_LEFT:
                self._adjust_simulated_pot(-128)
            elif event.key == pygame.K_RIGHT:
                self._adjust_simulated_pot(128)
            elif event.key == pygame.K_PAGEUP:
                self._adjust_simulated_pot(512)
            elif event.key == pygame.K_PAGEDOWN:
                self._adjust_simulated_pot(-512)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            virtual_pos = self._to_virtual(event.pos)
            if virtual_pos is None:
                return
            for action, rect in self.renderer.action_rects.items():
                if rect.collidepoint(virtual_pos):
                    self._handle_action(action)
                    break

    def _present(self, virtual: pygame.Surface) -> None:
        screen_w, screen_h = self.screen.get_size()
        scale = min(screen_w / VIRTUAL_SIZE[0], screen_h / VIRTUAL_SIZE[1])
        width, height = max(1, int(VIRTUAL_SIZE[0] * scale)), max(1, int(VIRTUAL_SIZE[1] * scale))
        scaled = pygame.transform.smoothscale(virtual, (width, height))
        self.screen.fill((0, 0, 0))
        self.screen.blit(scaled, ((screen_w - width) // 2, (screen_h - height) // 2))
        pygame.display.flip()

    def run(self) -> int:
        self.client.start()
        self.logger.write("display_started", size=self.screen.get_size(), windowed=self.windowed)
        try:
            while self.running:
                self.clock.tick(FPS)
                now = time.monotonic()
                for event in pygame.event.get():
                    self._handle_event(event)
                for event_type, payload in self.client.poll():
                    self.controller.handle_serial_event(event_type, payload, now=now)
                self.controller.update(now=now)
                frame = self.renderer.render(self.controller, now=now, diagnostic=self.diagnostic)
                self._present(frame)
                if self.max_runtime_seconds is not None and now - self.started_at >= self.max_runtime_seconds:
                    self.running = False
            return 0
        finally:
            try:
                self.logger.write(
                    "application_stopped",
                    state=self.controller.state.value,
                    completed_cycles=self.controller.completed_cycles,
                )
                self.client.stop()
            finally:
                self.logger.close()
                pygame.quit()


def run_stand(args, *, serial_client_factory=None) -> int:
    config_path = getattr(args, "stand_config", None) or DEFAULT_CONFIG_PATH
    fixture_path = getattr(args, "stand_fixture", None) or DEFAULT_FIXTURE_PATH
    log_dir = getattr(args, "stand_log_dir", None) or DEFAULT_LOG_DIR
    config = StandConfig.load(config_path)
    mode = "simulated" if bool(getattr(args, "simulated", False)) else "hardware"
    fixture_source = ""
    if mode == "simulated":
        client = FixtureSerialClient(fixture_path, config)
        fixture_source = client.source_label
    else:
        if serial_client_factory is None:
            from dashboard import DashboardSerialClient

            serial_client_factory = DashboardSerialClient
        client = serial_client_factory(
            port=getattr(args, "port", None),
            baudrate=int(getattr(args, "baud", 115200)),
            timeout=float(getattr(args, "serial_timeout", config.serial_timeout_seconds)),
        )
    logger = StandSessionLogger(log_dir, mode=mode, config=config, fixture_source=fixture_source)
    print(f"PQC-SAT stand log: {logger.path}")
    app = StandApp(
        config,
        client,
        mode=mode,
        logger=logger,
        windowed=bool(getattr(args, "windowed", False)),
        diagnostic=bool(getattr(args, "diagnostic", False)),
        max_runtime_seconds=getattr(args, "max_runtime_seconds", None),
    )
    return app.run()


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="PQC-SAT — Missão Guardiões do Bit no estande SBPC")
    parser.add_argument("--simulated", action="store_true", help="usa somente a fixture oficial, sempre rotulada")
    parser.add_argument("--port", help="porta serial da BlackBoard Wisdom")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--serial-timeout", type=float, default=8.0)
    parser.add_argument("--windowed", action="store_true", help="janela redimensionável para desenvolvimento")
    parser.add_argument("--stand-config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--stand-fixture", default=str(DEFAULT_FIXTURE_PATH))
    parser.add_argument("--stand-log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--diagnostic", action="store_true", help="abre o painel administrativo protegido por teclado")
    parser.add_argument("--max-runtime-seconds", type=float, help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run_stand(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
