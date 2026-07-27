"""Typed state and protocol validation for the guided presentation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from pathlib import Path
import zlib

from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH


class StandError(RuntimeError):
    """Base exception for stand-mode validation errors."""

class StandConfigError(StandError):
    """Raised when the local stand configuration is invalid."""

class StandProtocolError(StandError):
    """Raised when a serial/fixture response cannot prove the expected step."""

class InvestigationState(str, Enum):
    ATTRACT = "ATTRACT"
    SELECT_MISSION = "SELECT_MISSION"
    SELECT_KEY_MODE = "SELECT_KEY_MODE"
    SELECT_GUARD = "SELECT_GUARD"
    NEXT_PREPARE = "NEXT_PREPARE"
    PREPARE = "PREPARE"
    NEXT_PROTECT = "NEXT_PROTECT"
    PROTECT = "PROTECT"
    NEXT_TRANSMIT = "NEXT_TRANSMIT"
    TRANSMIT = "TRANSMIT"
    NEXT_VERIFY = "NEXT_VERIFY"
    VERIFY = "VERIFY"
    DIAGNOSE = "DIAGNOSE"
    SELECT_RESPONSE = "SELECT_RESPONSE"
    RETRY = "RETRY"
    DEBRIEF = "DEBRIEF"
    ERROR = "ERROR"


class KeyMode(str, Enum):
    ECDH = "ECDH"
    MLKEM = "MLKEM"


FAIR_KEY_MODES = (KeyMode.ECDH, KeyMode.MLKEM)
LEGACY_KEY_MODES = ("CLASSIC", "PQC")


class GuardMode(str, Enum):
    NONE = "NONE"
    CRC32 = "CRC32"


class GameStage(str, Enum):
    PREPARE = "PREPARE"
    PROTECT = "PROTECT"
    TRANSMIT = "TRANSMIT"
    VERIFY = "VERIFY"
    RETRY = "RETRY"
    END = "END"


class OperationalDecision(str, Enum):
    ACCEPT = "ACCEPT"
    RETRY = "RETRY"
    SAFE_MODE = "SAFE_MODE"


class IncidentScenario(str, Enum):
    NORMAL = "NORMAL"
    CHANNEL_BITFLIP = "CHANNEL_BITFLIP"
    TAMPER = "TAMPER"
    RX_MEMORY = "RX_MEMORY"


def _parse_deadline_ms(value: str) -> int:
    """Read a human deadline label while normalizing it to milliseconds."""
    normalized = value.strip().lower().replace(",", ".")
    if normalized.endswith("ms"):
        return int(float(normalized[:-2].strip()))
    if normalized.endswith("s"):
        return int(float(normalized[:-1].strip()) * 1000)
    raise StandConfigError(f"prazo de missão inválido: {value}")


@dataclass(frozen=True)
class MissionCard:
    mission_id: str
    title: str
    description: str
    payload: str
    priority: str
    deadline_ms: int
    consequence: str

    @property
    def payload_bytes(self) -> bytes:
        return self.payload.encode("ascii")

    @property
    def payload_hex(self) -> str:
        return self.payload_bytes.hex().upper()

    @property
    def deadline(self) -> str:
        """Compatibility display label backed by a typed millisecond value."""
        if self.deadline_ms < 1000:
            return f"{self.deadline_ms} ms"
        seconds = self.deadline_ms / 1000.0
        return f"{seconds:g} s"

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
    missions: tuple[MissionCard, ...] = ()
    incident_probability: float = 1.0
    radiation_weight: float = 0.50
    intrusion_weight: float = 0.50
    transmit_hold_seconds: float = 2.2
    reveal_seconds: float = 12.0
    max_cycle_seconds: float = 90.0
    screen_input_guard_seconds: float = 0.22
    public_interaction_timeout_enabled: bool = False
    public_auto_reset_enabled: bool = False
    checkpoint_animation_ms: tuple[tuple[str, int], ...] = ()
    target_min_seconds: float = 120.0
    target_max_seconds: float = 180.0

    @property
    def payload_bytes(self) -> bytes:
        return self.payload.encode("ascii")

    @property
    def payload_hex(self) -> str:
        return self.payload_bytes.hex().upper()

    def animation_duration_ms(self, stage: str | GameStage | InvestigationState) -> int:
        key = stage.value if isinstance(stage, Enum) else str(stage).upper()
        values = dict(self.checkpoint_animation_ms)
        return int(values.get(key, self.animation_min_ms))

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "StandConfig":
        config_path = Path(path)
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StandConfigError(f"não foi possível carregar {config_path}: {exc}") from exc
        schema_version = data.get("schema_version")
        if schema_version != "pqc-sat-stand-config-v3":
            raise StandConfigError("schema_version de configuração incompatível")
        try:
            animation = data["animation"]
            profiles = data["profiles"]
            pot = data["potentiometer"]
            investigation = data.get("investigation", {})
            incident_weights = investigation.get("incident_weights", {})
            if not isinstance(incident_weights, dict):
                raise TypeError("investigation.incident_weights deve ser um objeto")
            public_flow = data.get("public_flow", {})
            mission_rows = data.get("missions", [])
            missions = tuple(
                MissionCard(
                    mission_id=str(row["id"]).upper(),
                    title=str(row["title"]),
                    description=str(row["description"]),
                    payload=str(row["payload"]),
                    priority=str(row["priority"]),
                    deadline_ms=(
                        int(row["deadline_ms"])
                        if "deadline_ms" in row
                        else _parse_deadline_ms(str(row["deadline"]))
                    ),
                    consequence=str(row.get("consequence", row["description"])),
                )
                for row in mission_rows
            )
            checkpoint_animation_ms = tuple(
                (str(key).upper(), int(value))
                for key, value in animation.get("checkpoints_ms", {}).items()
            )
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
                missions=missions,
                incident_probability=float(investigation.get("incident_probability", 1.0)),
                radiation_weight=float(incident_weights.get("RX_MEMORY", 0.50)),
                intrusion_weight=float(incident_weights.get("TAMPER", 0.50)),
                transmit_hold_seconds=float(investigation.get("transmit_hold_seconds", 2.2)),
                reveal_seconds=float(investigation.get("reveal_seconds", 12.0)),
                max_cycle_seconds=float(investigation.get("max_cycle_seconds", 90.0)),
                screen_input_guard_seconds=float(investigation.get("screen_input_guard_seconds", 0.22)),
                public_interaction_timeout_enabled=bool(public_flow.get("interaction_timeout_enabled", False)),
                public_auto_reset_enabled=bool(public_flow.get("auto_reset_enabled", False)),
                checkpoint_animation_ms=checkpoint_animation_ms,
                target_min_seconds=float(investigation.get("target_min_seconds", 120.0)),
                target_max_seconds=float(investigation.get("target_max_seconds", 180.0)),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise StandConfigError(f"configuração incompleta: {exc}") from exc
        try:
            payload_bytes = config.payload_bytes
        except UnicodeEncodeError as exc:
            raise StandConfigError("payload do firmware deve ser ASCII") from exc
        if not payload_bytes or len(payload_bytes) > 96:
            raise StandConfigError("payload deve conter entre 1 e 96 bytes")
        if len(config.missions) != 3:
            raise StandConfigError("o jogo exige exatamente três missões")
        mission_ids: set[str] = set()
        for mission in config.missions:
            try:
                mission_payload = mission.payload_bytes
            except UnicodeEncodeError as exc:
                raise StandConfigError(f"payload da missão {mission.mission_id} deve ser ASCII") from exc
            if not mission.mission_id or mission.mission_id in mission_ids:
                raise StandConfigError("IDs de missão devem ser únicos e não vazios")
            mission_ids.add(mission.mission_id)
            if not mission_payload or len(mission_payload) > 96:
                raise StandConfigError(f"payload da missão {mission.mission_id} deve ter 1..96 bytes")
            if mission.deadline_ms <= 0:
                raise StandConfigError(f"prazo da missão {mission.mission_id} deve ser positivo")
            if not mission.consequence.strip():
                raise StandConfigError(f"consequência da missão {mission.mission_id} não pode ser vazia")
        if len(config.windowed_size) != 2 or min(config.windowed_size) < 480:
            raise StandConfigError("windowed_size inválido")
        if config.pot_maximum <= config.pot_minimum:
            raise StandConfigError("faixa do potenciômetro inválida")
        if config.animation_min_ms <= 0 or config.animation_max_ms < config.animation_min_ms:
            raise StandConfigError("faixa de animação inválida")
        checkpoints = dict(config.checkpoint_animation_ms)
        expected_checkpoints = {stage.value for stage in GameStage if stage is not GameStage.END} | {"DEBRIEF"}
        if set(checkpoints) != expected_checkpoints or any(value <= 0 for value in checkpoints.values()):
            raise StandConfigError("configuração v3 exige animações positivas por checkpoint")
        if config.public_interaction_timeout_enabled or config.public_auto_reset_enabled:
            raise StandConfigError("fluxo público v3 não permite timeout ou reset automático")
        if tuple(data.get("key_modes", ())) != tuple(mode.value for mode in FAIR_KEY_MODES):
            raise StandConfigError("configuração v3 exige ECDH e MLKEM como modos de chave")
        if tuple(data.get("guards", ())) != ("NONE", "CRC32"):
            raise StandConfigError("configuração v3 exige NONE e CRC32 como guardiões")
        if not 0.0 <= config.incident_probability <= 1.0:
            raise StandConfigError("probabilidade pública de incidente deve estar entre 0 e 1")
        if config.radiation_weight < 0.0 or config.intrusion_weight < 0.0:
            raise StandConfigError("pesos públicos de incidente não podem ser negativos")
        if not math.isclose(config.radiation_weight + config.intrusion_weight, 1.0, abs_tol=1e-9):
            raise StandConfigError("pesos públicos de radiação e invasão devem somar 1")
        if config.target_min_seconds <= 0 or config.target_max_seconds < config.target_min_seconds:
            raise StandConfigError("janela-alvo da partida inválida")
        for value in (
            config.auto_reset_seconds,
            config.serial_timeout_seconds,
            config.intro_seconds,
            config.comparison_hold_seconds,
            config.fault_hold_seconds,
            config.pot_poll_interval_seconds,
            config.button_debounce_seconds,
            config.interaction_timeout_seconds,
            config.transmit_hold_seconds,
            config.reveal_seconds,
            config.max_cycle_seconds,
            config.screen_input_guard_seconds,
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
    pot_value: int | None
    source: str = "POT"

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
class InvestigationResult:
    command: str
    scenario: str
    profile: str
    profile_mhz: int
    incident_id: str
    incident: str
    byte_index: int
    bit_mask: int
    before_byte: int
    after_byte: int
    frame_crc_tx: int
    frame_crc_rx: int
    frame_crc_match: bool
    key_match: bool
    aead_checked: bool
    aead_match: bool
    app_crc_present: bool
    app_crc_checked: bool
    app_crc_match: bool
    accepted: bool
    result: str
    elapsed_us: int
    bytes_total: int
    heap: int
    min_heap: int
    source: str
    payload_hex: str
    raw_response: dict[str, str]

    @property
    def operations_per_second(self) -> float:
        return 1_000_000.0 / self.elapsed_us if self.elapsed_us > 0 else 0.0


@dataclass(frozen=True)
class StageMeasurement:
    """Validated, non-secret measurement produced by one GAME_* checkpoint."""

    command: str
    game_id: str
    stage: GameStage
    profile: str
    profile_mhz: int
    key_mode: KeyMode
    guard: GuardMode
    result: str
    elapsed_us: int
    bytes_payload: int
    bytes_total: int
    heap: int
    min_heap: int
    source: str
    raw_response: dict[str, str]


@dataclass(frozen=True)
class GameResult:
    """Scientific outcome emitted only by GAME_VERIFY or GAME_RETRY."""

    command: str
    game_id: str
    stage: GameStage
    incident: IncidentScenario
    profile: str
    profile_mhz: int
    key_mode: KeyMode
    guard: GuardMode
    selection: FaultSelection
    frame_crc_match: bool
    aead_checked: bool
    aead_match: bool
    app_crc_present: bool
    app_crc_checked: bool
    app_crc_match: bool
    accepted: bool
    result: str
    elapsed_us: int
    bytes_payload: int
    bytes_total: int
    heap: int
    min_heap: int
    source: str
    raw_response: dict[str, str]

    @property
    def cryptographically_rejected(self) -> bool:
        return self.result in {"FRAME_REJECT", "AUTH_REJECT", "APP_REJECT"}


@dataclass(frozen=True)
class GameEndReceipt:
    command: str
    game_id: str
    decision: OperationalDecision
    final_result: str
    session_cleared: bool
    restored_profile: str
    restored_mhz: int
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
        source="POT",
    )

def fault_selection_from_rng(rng, payload_len: int) -> FaultSelection:
    """Choose a reproducible single-bit vector from an injected experiment RNG."""

    if payload_len <= 0:
        raise ValueError("payload vazio")
    bit_position = int(rng.randrange(payload_len * 8))
    return FaultSelection(
        byte_index=bit_position // 8,
        bit_mask=1 << (bit_position % 8),
        bit_position=bit_position,
        pot_value=None,
        source="RNG",
    )

def flip_selected_bit(payload: bytes, selection: FaultSelection) -> bytes:
    if not 0 <= selection.byte_index < len(payload):
        raise ValueError("índice fora do payload")
    if selection.bit_mask <= 0 or selection.bit_mask > 0x80 or selection.bit_mask & (selection.bit_mask - 1):
        raise ValueError("máscara não representa um único bit")
    mutated = bytearray(payload)
    mutated[selection.byte_index] ^= selection.bit_mask
    return bytes(mutated)


def scenario_for(key_mode: KeyMode | str, guard: GuardMode | str) -> str:
    key = KeyMode(key_mode)
    checksum = GuardMode(guard)
    return f"{key.value}_CRC32" if checksum is GuardMode.CRC32 else key.value


def expected_game_outcome(
    incident: IncidentScenario | str,
    guard: GuardMode | str,
) -> dict[str, object]:
    """Single scientific truth table shared by parser, fixture and tests."""
    incident_value = IncidentScenario(incident)
    guard_value = GuardMode(guard)
    use_crc = guard_value is GuardMode.CRC32
    table: dict[IncidentScenario, dict[str, object]] = {
        IncidentScenario.NORMAL: {
            "result": "DELIVERED",
            "accepted": True,
            "frame_crc_match": True,
            "aead_match": True,
            "app_crc_present": use_crc,
            "app_crc_checked": use_crc,
            "app_crc_match": use_crc,
        },
        IncidentScenario.CHANNEL_BITFLIP: {
            "result": "FRAME_REJECT",
            "accepted": False,
            "frame_crc_match": False,
            "aead_match": False,
            "app_crc_present": use_crc,
            "app_crc_checked": False,
            "app_crc_match": False,
        },
        IncidentScenario.TAMPER: {
            "result": "AUTH_REJECT",
            "accepted": False,
            "frame_crc_match": True,
            "aead_match": False,
            "app_crc_present": use_crc,
            "app_crc_checked": False,
            "app_crc_match": False,
        },
        IncidentScenario.RX_MEMORY: {
            "result": "APP_REJECT" if use_crc else "SILENT_CORRUPTION",
            "accepted": not use_crc,
            "frame_crc_match": True,
            "aead_match": True,
            "app_crc_present": use_crc,
            "app_crc_checked": use_crc,
            "app_crc_match": False,
        },
    }
    return table[incident_value]

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


def _required_bool(payload: dict[str, object], key: str) -> bool:
    text = _required_text(payload, key).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise StandProtocolError(f"campo {key} não é booleano: {text}")


def parse_button_press_event(
    event: dict[str, object],
    *,
    handshake_uptime_ms: int,
) -> int:
    """Validate a post-handshake D27 press and reject stale queued events."""
    nested = event.get("payload")
    if not isinstance(nested, dict):
        raise StandProtocolError("BUTTON_PING sem payload estruturado")
    if not _required_bool(nested, "button"):
        raise StandProtocolError("BUTTON_PING não representa botão pressionado")
    uptime_ms = _required_int(nested, "uptime_ms")
    if not 0 <= uptime_ms <= 0xFFFFFFFF:
        raise StandProtocolError("uptime_ms do botão fora da faixa uint32")
    if not 0 <= handshake_uptime_ms <= 0xFFFFFFFF:
        raise StandProtocolError("uptime_ms do handshake fora da faixa uint32")
    delta = (uptime_ms - handshake_uptime_ms) & 0xFFFFFFFF
    if delta == 0 or delta >= 0x80000000:
        raise StandProtocolError("BUTTON_PING anterior ao handshake foi ignorado")
    return uptime_ms

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


def parse_investigation_response(
    command: str,
    payload: dict[str, object],
    *,
    scenario: str,
    profile: str,
    profile_mhz: int,
    incident_id: str,
    incident: str,
    selection: FaultSelection,
    payload_hex: str,
    source: str,
) -> InvestigationResult:
    received_scenario = _required_text(payload, "scenario").upper()
    received_profile = _required_text(payload, "profile").upper()
    received_mhz = _required_int(payload, "cpu_mhz")
    received_incident_id = _required_text(payload, "incident_id")
    received_incident = _required_text(payload, "incident").upper()
    cipher = _required_text(payload, "cipher").upper()
    result = _required_text(payload, "result").upper()
    byte_index = _required_int(payload, "byte_index")
    bit_mask = _required_int(payload, "bit_mask", base=0)
    before_byte = _required_int(payload, "before_byte", base=0)
    after_byte = _required_int(payload, "after_byte", base=0)
    frame_crc_tx = _required_int(payload, "frame_crc_tx", base=0)
    frame_crc_rx = _required_int(payload, "frame_crc_rx", base=0)
    frame_crc_match = _required_bool(payload, "frame_crc_match")
    key_match = _required_bool(payload, "key_match")
    aead_checked = _required_bool(payload, "aead_checked")
    aead_match = _required_bool(payload, "aead_match")
    app_crc_present = _required_bool(payload, "app_crc_present")
    app_crc_checked = _required_bool(payload, "app_crc_checked")
    app_crc_match = _required_bool(payload, "app_crc_match")
    accepted = _required_bool(payload, "accepted")
    elapsed_us = _required_int(payload, "elapsed_us")
    bytes_total = _required_int(payload, "bytes_total")
    heap = _required_int(payload, "heap")
    min_heap = _required_int(payload, "min_heap")
    bytes_payload = _required_int(payload, "bytes_payload")

    if received_scenario != scenario or received_incident != incident:
        raise StandProtocolError("cenário ou incidente diverge do solicitado")
    if received_profile != profile or received_mhz != profile_mhz:
        raise StandProtocolError("investigação retornou perfil diferente do confirmado")
    if received_incident_id != incident_id:
        raise StandProtocolError("incident_id diverge do solicitado")
    if cipher != "AES-128-GCM":
        raise StandProtocolError(f"cifra inesperada: {cipher}")
    if bytes_payload != len(bytes.fromhex(payload_hex)):
        raise StandProtocolError("tamanho do payload investigado diverge do enviado")
    if elapsed_us <= 0 or bytes_total <= 0 or heap <= 0 or min_heap <= 0:
        raise StandProtocolError("métricas da investigação devem ser positivas")
    if byte_index != selection.byte_index or bit_mask != selection.bit_mask:
        raise StandProtocolError("resposta alterou o vetor de falha")
    if incident != IncidentScenario.NORMAL.value and after_byte != before_byte ^ bit_mask:
        raise StandProtocolError("resposta não comprova a mutação single-bit")
    if incident == IncidentScenario.NORMAL.value and after_byte != before_byte:
        raise StandProtocolError("transmissão normal não pode alterar o byte")

    use_app_crc = scenario.endswith("_CRC32")
    expected = {
        IncidentScenario.NORMAL.value: ("DELIVERED", True, True, True, use_app_crc, use_app_crc, use_app_crc),
        IncidentScenario.CHANNEL_BITFLIP.value: ("FRAME_REJECT", False, False, False, use_app_crc, False, False),
        IncidentScenario.TAMPER.value: ("AUTH_REJECT", False, True, False, use_app_crc, False, False),
        IncidentScenario.RX_MEMORY.value: (
            "APP_REJECT" if use_app_crc else "SILENT_CORRUPTION",
            not use_app_crc,
            True,
            True,
            use_app_crc,
            use_app_crc,
            False if use_app_crc else False,
        ),
    }
    if incident not in expected:
        raise StandProtocolError(f"incidente desconhecido: {incident}")
    (
        expected_result,
        expected_accepted,
        expected_frame,
        expected_aead,
        expected_app_present,
        expected_app_checked,
        expected_app_match,
    ) = expected[incident]
    observed = (
        result,
        accepted,
        frame_crc_match,
        aead_match,
        app_crc_present,
        app_crc_checked,
        app_crc_match,
    )
    wanted = (
        expected_result,
        expected_accepted,
        expected_frame,
        expected_aead,
        expected_app_present,
        expected_app_checked,
        expected_app_match,
    )
    if observed != wanted or not aead_checked:
        raise StandProtocolError(f"tabela de diagnóstico contraditória para {incident}")
    if frame_crc_match != (frame_crc_tx == frame_crc_rx):
        raise StandProtocolError("flag do CRC de quadro contradiz os valores")
    if not key_match:
        raise StandProtocolError("chaves de sessão divergentes na investigação")

    return InvestigationResult(
        command=command,
        scenario=scenario,
        profile=profile,
        profile_mhz=profile_mhz,
        incident_id=incident_id,
        incident=incident,
        byte_index=byte_index,
        bit_mask=bit_mask,
        before_byte=before_byte,
        after_byte=after_byte,
        frame_crc_tx=frame_crc_tx,
        frame_crc_rx=frame_crc_rx,
        frame_crc_match=frame_crc_match,
        key_match=key_match,
        aead_checked=aead_checked,
        aead_match=aead_match,
        app_crc_present=app_crc_present,
        app_crc_checked=app_crc_checked,
        app_crc_match=app_crc_match,
        accepted=accepted,
        result=result,
        elapsed_us=elapsed_us,
        bytes_total=bytes_total,
        heap=heap,
        min_heap=min_heap,
        source=source,
        payload_hex=payload_hex,
        raw_response={key: str(value) for key, value in payload.items()},
    )


def _validate_game_identity(
    payload: dict[str, object],
    *,
    game_id: str,
    stage: GameStage,
    profile: str,
    profile_mhz: int,
    key_mode: KeyMode,
    guard: GuardMode,
) -> None:
    if _required_text(payload, "game_id") != game_id:
        raise StandProtocolError("GAME_* respondeu com ID de sessão divergente")
    if _required_text(payload, "stage").upper() != stage.value:
        raise StandProtocolError(f"checkpoint divergente: esperado {stage.value}")
    if _required_text(payload, "profile").upper() != profile or _required_int(payload, "cpu_mhz") != profile_mhz:
        raise StandProtocolError("GAME_* respondeu com perfil divergente")
    if _required_text(payload, "key_mode").upper() != key_mode.value:
        raise StandProtocolError("GAME_* respondeu com modo de chave divergente")
    if _required_text(payload, "guard").upper() != guard.value:
        raise StandProtocolError("GAME_* respondeu com guardião divergente")


def parse_game_stage_response(
    command: str,
    payload: dict[str, object],
    *,
    game_id: str,
    stage: GameStage,
    profile: str,
    profile_mhz: int,
    key_mode: KeyMode,
    guard: GuardMode,
    payload_len: int,
    source: str,
    payload_bytes: bytes | None = None,
    incident: IncidentScenario | None = None,
    selection: FaultSelection | None = None,
) -> StageMeasurement:
    """Validate PREPARE, PROTECT or TRANSMIT without advancing the UI."""
    if stage not in {GameStage.PREPARE, GameStage.PROTECT, GameStage.TRANSMIT}:
        raise ValueError(f"checkpoint não suportado: {stage.value}")
    _validate_game_identity(
        payload,
        game_id=game_id,
        stage=stage,
        profile=profile,
        profile_mhz=profile_mhz,
        key_mode=key_mode,
        guard=guard,
    )
    result = _required_text(payload, "result").upper()
    wanted_result = {
        GameStage.PREPARE: "READY",
        GameStage.PROTECT: "PROTECTED",
        GameStage.TRANSMIT: "IN_FLIGHT",
    }[stage]
    if result != wanted_result:
        raise StandProtocolError(f"resultado inesperado em {stage.value}: {result}")
    bytes_payload = _required_int(payload, "bytes_payload")
    bytes_total = _required_int(payload, "bytes_total")
    elapsed_us = _required_int(payload, "elapsed_us")
    heap = _required_int(payload, "heap")
    min_heap = _required_int(payload, "min_heap")
    if bytes_payload != payload_len or bytes_total <= 0 or elapsed_us <= 0 or heap <= 0 or min_heap <= 0:
        raise StandProtocolError(f"métricas inválidas em {stage.value}")

    use_crc = guard is GuardMode.CRC32
    if stage is GameStage.PREPARE:
        if payload_bytes is None or len(payload_bytes) != payload_len:
            raise ValueError("PREPARE exige os bytes exatos do payload")
        if _required_bool(payload, "app_crc_present") != use_crc:
            raise StandProtocolError("PREPARE contradiz a escolha do CRC da aplicação")
        wanted_protected = payload_len + (4 if use_crc else 0)
        if _required_int(payload, "bytes_protected") != wanted_protected:
            raise StandProtocolError("PREPARE retornou tamanho protegido divergente")
        expected_crc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
        if _required_int(payload, "payload_crc32", base=0) != expected_crc:
            raise StandProtocolError("PREPARE retornou CRC do payload divergente")
        app_crc = _required_int(payload, "app_crc_tx", base=0)
        if app_crc != (expected_crc if use_crc else 0):
            raise StandProtocolError("PREPARE retornou CRC da aplicação divergente")
    elif stage is GameStage.PROTECT:
        if not _required_bool(payload, "key_match") or not _required_bool(payload, "aead_ready"):
            raise StandProtocolError("PROTECT não comprovou chave e envelope AES-GCM")
        _required_int(payload, "nonce_crc32", base=0)
        _required_int(payload, "session_key_crc32", base=0)
        if key_mode in FAIR_KEY_MODES:
            expected_kex = "ECDH-P256" if key_mode is KeyMode.ECDH else "ML-KEM-512"
            if _required_text(payload, "experiment").upper() != "KEX_FAIR_V1":
                raise StandProtocolError("PROTECT não pertence ao experimento KEX_FAIR_V1")
            if _required_text(payload, "kex").upper() != expected_kex:
                raise StandProtocolError("PROTECT retornou algoritmo de estabelecimento divergente")
            if not _required_text(payload, "crypto_impl").lower().startswith("wolfcrypt"):
                raise StandProtocolError("PROTECT não comprovou backend wolfCrypt comum")
            if _required_text(payload, "kdf").upper() != "HKDF-SHA256":
                raise StandProtocolError("PROTECT não comprovou HKDF-SHA256 comum")
            if _required_text(payload, "optimization").lower() != "portable-software":
                raise StandProtocolError("PROTECT não comprovou política portátil comum")
            if _required_bool(payload, "target_asm") or _required_bool(payload, "hw_crypto"):
                raise StandProtocolError("PROTECT ativou aceleração fora do perfil FAIR_V1")
            setup_bytes = _required_int(payload, "setup_bytes")
            response_bytes = _required_int(payload, "response_bytes")
            expected_sizes = (65, 65) if key_mode is KeyMode.ECDH else (800, 768)
            if (setup_bytes, response_bytes) != expected_sizes:
                raise StandProtocolError("PROTECT retornou material público com tamanho divergente")
            for timing in ("setup_us", "initiator_us", "responder_us", "kex_total_us", "kdf_us"):
                if _required_int(payload, timing) <= 0:
                    raise StandProtocolError(f"PROTECT retornou {timing} não positivo")
    else:
        if incident is None or selection is None:
            raise ValueError("TRANSMIT exige incidente interno e vetor confirmado")
        if _required_int(payload, "byte_index") != selection.byte_index:
            raise StandProtocolError("TRANSMIT alterou o byte do vetor selecionado")
        if _required_int(payload, "bit_mask", base=0) != selection.bit_mask:
            raise StandProtocolError("TRANSMIT alterou a máscara do vetor selecionado")
        frame_crc_tx = _required_int(payload, "frame_crc_tx", base=0)
        frame_crc_rx = _required_int(payload, "frame_crc_rx", base=0)
        frame_crc_match = _required_bool(payload, "frame_crc_match")
        expected_frame_match = bool(expected_game_outcome(incident, guard)["frame_crc_match"])
        if frame_crc_match != expected_frame_match:
            raise StandProtocolError("TRANSMIT contradiz o CRC de quadro esperado")
        if frame_crc_match != (frame_crc_tx == frame_crc_rx):
            raise StandProtocolError("TRANSMIT retornou flag e valores de CRC contraditórios")

    return StageMeasurement(
        command=command,
        game_id=game_id,
        stage=stage,
        profile=profile,
        profile_mhz=profile_mhz,
        key_mode=key_mode,
        guard=guard,
        result=result,
        elapsed_us=elapsed_us,
        bytes_payload=bytes_payload,
        bytes_total=bytes_total,
        heap=heap,
        min_heap=min_heap,
        source=source,
        raw_response={key: str(value) for key, value in payload.items()},
    )


def parse_game_result_response(
    command: str,
    payload: dict[str, object],
    *,
    game_id: str,
    stage: GameStage,
    incident: IncidentScenario,
    profile: str,
    profile_mhz: int,
    key_mode: KeyMode,
    guard: GuardMode,
    selection: FaultSelection,
    payload_len: int,
    source: str,
    initial_protect: StageMeasurement | None = None,
) -> GameResult:
    if stage not in {GameStage.VERIFY, GameStage.RETRY}:
        raise ValueError("resultado final exige VERIFY ou RETRY")
    _validate_game_identity(
        payload,
        game_id=game_id,
        stage=stage,
        profile=profile,
        profile_mhz=profile_mhz,
        key_mode=key_mode,
        guard=guard,
    )
    effective_incident = IncidentScenario.NORMAL if stage is GameStage.RETRY else incident
    wanted = expected_game_outcome(effective_incident, guard)
    observed = {
        "result": _required_text(payload, "result").upper(),
        "accepted": _required_bool(payload, "accepted"),
        "frame_crc_match": _required_bool(payload, "frame_crc_match"),
        "aead_match": _required_bool(payload, "aead_match"),
        "app_crc_present": _required_bool(payload, "app_crc_present"),
        "app_crc_checked": _required_bool(payload, "app_crc_checked"),
        "app_crc_match": _required_bool(payload, "app_crc_match"),
    }
    if observed != wanted or not _required_bool(payload, "aead_checked"):
        raise StandProtocolError(f"tabela científica contraditória em {stage.value}")
    if _required_int(payload, "byte_index") != selection.byte_index:
        raise StandProtocolError(f"{stage.value} alterou o byte selecionado")
    if _required_int(payload, "bit_mask", base=0) != selection.bit_mask:
        raise StandProtocolError(f"{stage.value} alterou a máscara selecionada")
    bytes_payload = _required_int(payload, "bytes_payload")
    bytes_total = _required_int(payload, "bytes_total")
    elapsed_us = _required_int(payload, "elapsed_us")
    heap = _required_int(payload, "heap")
    min_heap = _required_int(payload, "min_heap")
    if bytes_payload != payload_len or min(bytes_total, elapsed_us, heap, min_heap) <= 0:
        raise StandProtocolError(f"métricas inválidas em {stage.value}")
    if stage is GameStage.RETRY:
        if not all(
            _required_bool(payload, field)
            for field in ("same_payload", "fresh_key", "fresh_nonce")
        ):
            raise StandProtocolError("GAME_RETRY não comprovou payload igual e material novo")
        if initial_protect is not None:
            old_nonce = int(initial_protect.raw_response["nonce_crc32"], 0)
            old_key = int(initial_protect.raw_response["session_key_crc32"], 0)
            if _required_int(payload, "nonce_crc32", base=0) == old_nonce:
                raise StandProtocolError("GAME_RETRY reutilizou o nonce")
            if _required_int(payload, "session_key_crc32", base=0) == old_key:
                raise StandProtocolError("GAME_RETRY reutilizou a chave de sessão")

    return GameResult(
        command=command,
        game_id=game_id,
        stage=stage,
        incident=effective_incident,
        profile=profile,
        profile_mhz=profile_mhz,
        key_mode=key_mode,
        guard=guard,
        selection=selection,
        frame_crc_match=bool(observed["frame_crc_match"]),
        aead_checked=True,
        aead_match=bool(observed["aead_match"]),
        app_crc_present=bool(observed["app_crc_present"]),
        app_crc_checked=bool(observed["app_crc_checked"]),
        app_crc_match=bool(observed["app_crc_match"]),
        accepted=bool(observed["accepted"]),
        result=str(observed["result"]),
        elapsed_us=elapsed_us,
        bytes_payload=bytes_payload,
        bytes_total=bytes_total,
        heap=heap,
        min_heap=min_heap,
        source=source,
        raw_response={key: str(value) for key, value in payload.items()},
    )


def parse_game_end_response(
    command: str,
    payload: dict[str, object],
    *,
    game_id: str,
    decision: OperationalDecision,
    expected_final_result: str,
    baseline_profile: str,
    baseline_mhz: int,
    source: str,
) -> GameEndReceipt:
    if _required_text(payload, "game_id") != game_id or _required_text(payload, "stage").upper() != GameStage.END.value:
        raise StandProtocolError("GAME_END respondeu com sessão ou estágio divergente")
    if _required_text(payload, "decision").upper() != decision.value:
        raise StandProtocolError("GAME_END alterou a decisão operacional")
    final_result = _required_text(payload, "final_result").upper()
    if final_result != expected_final_result.upper():
        raise StandProtocolError("GAME_END contradiz o resultado já validado")
    cleared = _required_bool(payload, "session_cleared")
    restored = _required_text(payload, "restored_profile").upper()
    restored_mhz = _required_int(payload, "restored_mhz")
    if not cleared or restored != baseline_profile or restored_mhz != baseline_mhz:
        raise StandProtocolError("GAME_END não limpou a sessão e restaurou o baseline")
    return GameEndReceipt(
        command=command,
        game_id=game_id,
        decision=decision,
        final_result=final_result,
        session_cleared=cleared,
        restored_profile=restored,
        restored_mhz=restored_mhz,
        source=source,
        raw_response={key: str(value) for key, value in payload.items()},
    )

__all__ = (
    "StandError",
    "StandConfigError",
    "StandProtocolError",
    "InvestigationState",
    "KeyMode",
    "FAIR_KEY_MODES",
    "LEGACY_KEY_MODES",
    "GuardMode",
    "GameStage",
    "OperationalDecision",
    "IncidentScenario",
    "MissionCard",
    "StandConfig",
    "HardwareMeasurement",
    "AnimationModel",
    "FaultSelection",
    "FaultMeasurement",
    "InvestigationResult",
    "StageMeasurement",
    "GameResult",
    "GameEndReceipt",
    "PendingCommand",
    "safe_ratio",
    "fault_selection_from_pot",
    "fault_selection_from_rng",
    "flip_selected_bit",
    "scenario_for",
    "expected_game_outcome",
    "_required_text",
    "_required_int",
    "_required_bool",
    "parse_button_press_event",
    "parse_profile_response",
    "parse_mission_response",
    "parse_fault_response",
    "parse_investigation_response",
    "parse_game_stage_response",
    "parse_game_result_response",
    "parse_game_end_response",
)
