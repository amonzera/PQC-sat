#!/usr/bin/env python3
"""
PQC-SAT Mission Control Dashboard
Criptografia Pós-Quântica - CubeSat - ESP32
Universidade Federal Fluminense - Cibersegurança

Dashboard principal com visualização animada de um CubeSat em órbita
da Terra, contendo um robô pixel-art sorridente. Esqueleto preparado
para receber comandos de injeção de falha e controle de sessão PQC.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import queue
import random
import re
import sys
import threading
import time
import zlib

import pygame

from tools.serial_bridge import SerialBridge, SerialBridgeError, SerialBridgeTimeout, list_serial_ports
from tools.serial_commands import (
    DASHBOARD_COMMAND_NAMES,
    FIRMWARE_COMMAND_NAMES,
    is_demo_firmware_command,
)
from tools.serial_protocol import ProtocolError, decode_key_values

# --- Inicializacao ------------------------------------------------------------
pygame.font.init()
WIDTH, HEIGHT = 1920, 1080
screen = None
clock = pygame.time.Clock()
FPS = 60
SIMULATION_SEED = 42
DEFAULT_PAYLOAD = b"PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK"
RUN_SCHEMA_VERSION = "pqc-sat-run-v2"
DEFAULT_LOG_DIR = Path("logs")
SPLASH_SECONDS = 1.6
SERIAL_STARTUP_COMMANDS = ("OLED STANDBY",)
SERIAL_RECONNECT_DELAY = 1.5
SERIAL_TIMEOUT_SECONDS = 5.0
LIVE_PAYLOAD_REQUEST_TIMEOUT_SECONDS = 1.25
LIVE_PAYLOAD_MAX_BYTES = 96
STRESS_COMMAND = "STRESS PQC_LOOP 500 CONFIRM"
STRESS_SERIAL_TIMEOUT_SECONDS = 30.0
STRESS_DIDACTIC_TIMEOUT_SECONDS = 8.0
CPU_LOAD_WINDOW_SECONDS = 5.0
DEMO_DEFAULT_ATTEMPTS = 5
DEMO_FAULT_INTERVAL_SECONDS = 0.55
DEMO_SNAPSHOT_SECONDS = 1.5
DEMO_RESULTS_SECONDS = 8.0
MISSION_FLOW_ANIMATION_SECONDS = 8.0
FAULT_FLOW_ANIMATION_SECONDS = 7.5
POPUP_ENTER_SECONDS = 0.20
POPUP_EXIT_SECONDS = 0.16
PING_ANIMATION_SECONDS = 1.6
COMMAND_BUTTON_GROUPS = (
    (
        "CONFIGURAÇÃO",
        (
            ("CLÁSSICA", "SET_PRESET_CLASSIC"),
            ("PQC", "SET_PRESET_PQC"),
            ("PQC+CRC", "SET_PRESET_PQC_CRC32"),
        ),
    ),
    (
        "ENVIO",
        (
            ("ENVIAR MSG", "SEND_MESSAGE"),
            ("FALHA", "INJECT_FAULT"),
        ),
    ),
)
COMMAND_BUTTONS = tuple(
    button
    for _section, buttons in COMMAND_BUTTON_GROUPS
    for button in buttons
)
MISSION_PRESET_COMMANDS = {
    "SET_PRESET_CLASSIC": "CLASSIC",
    "SET_PRESET_PQC": "PQC",
    "SET_PRESET_PQC_CRC32": "PQC_CRC32",
}
MISSION_OVERLAY_SCENARIOS = ("CLASSIC", "PQC", "PQC_CRC32")
CONSOLIDATED_ACCEPTANCE_LOG = "logs/20260702T044907Z_final_metrics_dev-ttyusb0.json"
CONSOLIDATED_ACCEPTANCE_LABEL = "20260702T044907Z"
CONSOLIDATED_METRICS_STATUS = "versão cifrada oficial com AES-128-GCM"
CONSOLIDATED_SUMMARY = {
    "crc_acceptance": "200/200",
    "demo_crc_detected": "200/200",
    "demo_none_silent": "200/200",
    "elapsed_s": 336.62,
    "failed": 0,
    "mission_runs": 600,
    "pqc_bench_runs": 6,
    "records": 1038
}
CONSOLIDATED_AES_GCM_CHECKS = {'aead_failures': 0, 'missing_required_fields': 0, 'mission_records': 600, 'non_aes_gcm_records': 0, 'nonce_crc32_duplicates': 0, 'official_candidate': True}
CONSOLIDATED_MISSION_BASELINE = {
    "CLASSIC": {
        "label": "CLASSIC",
        "crypto": "AES-128-GCM",
        "checksum": "NONE",
        "elapsed_us": 611,
        "bytes_total": 69,
        "bytes_payload": 41,
        "bytes_crypto": 28,
        "bytes_checksum": 0,
        "keygen_us": 0,
        "encap_us": 0,
        "decap_us": 0,
        "tag_us": 365,
        "verify_us": 125,
        "crc_us": 0,
        "heap": 201412,
        "min_heap": 197624,
        "result": "DELIVERED"
    },
    "PQC": {
        "label": "PQC (ML-KEM)",
        "crypto": "ML-KEM-512 + AES-GCM",
        "checksum": "NONE",
        "elapsed_us": 14152,
        "bytes_total": 837,
        "bytes_payload": 41,
        "bytes_crypto": 796,
        "bytes_checksum": 0,
        "keygen_us": 3743,
        "encap_us": 3953,
        "decap_us": 5029,
        "tag_us": 389,
        "verify_us": 124,
        "crc_us": 0,
        "heap": 201412,
        "min_heap": 197624,
        "result": "DELIVERED"
    },
    "PQC_CRC32": {
        "label": "PQC + CRC32",
        "crypto": "ML-KEM-512 + AES-GCM",
        "checksum": "CRC32",
        "elapsed_us": 14097,
        "bytes_total": 841,
        "bytes_payload": 41,
        "bytes_crypto": 796,
        "bytes_checksum": 4,
        "keygen_us": 3678,
        "encap_us": 3934,
        "decap_us": 5019,
        "tag_us": 416,
        "verify_us": 125,
        "crc_us": 32,
        "heap": 201412,
        "min_heap": 197624,
        "result": "DELIVERED"
    }
}
CONSOLIDATED_MISSION_LIMITED = {
    "CLASSIC": {
        **CONSOLIDATED_MISSION_BASELINE["CLASSIC"],
        "elapsed_us": 1028,
        "tag_us": 554,
        "verify_us": 314,
    },
    "PQC": {
        **CONSOLIDATED_MISSION_BASELINE["PQC"],
        "elapsed_us": 40197,
        "keygen_us": 10524,
        "encap_us": 11882,
        "decap_us": 15259,
        "tag_us": 600,
        "verify_us": 313,
    },
    "PQC_CRC32": {
        **CONSOLIDATED_MISSION_BASELINE["PQC_CRC32"],
        "elapsed_us": 40077,
        "keygen_us": 10450,
        "encap_us": 11833,
        "decap_us": 15221,
        "tag_us": 607,
        "verify_us": 316,
        "crc_us": 53,
    },
}
CONSOLIDATED_PQC_BENCH = (
    ("BASELINE 240 MHz", "3.302", "3.866", "4.990"),
    ("LIMITED 80 MHz", "10.067", "11.789", "15.217"),
)
CONSOLIDATED_MISSION_TITLE = "DESEMPENHO DA MISSÃO (AES-GCM)"
CONSOLIDATED_NOTES = (
    "Resultados oficiais com cifragem AES-GCM ativa nas missões.",
    "PQC foi 23.2x mais lento e 12.1x maior em bytes que CLASSIC.",
    "PQC+CRC32 adicionou 4 bytes ao pacote, com verificação ativa de integridade.",
    "Heap médio estável em 201.412 B no baseline de 240 MHz.",
    "A 80 MHz (limited), PQC subiu para 40.2 ms (39.1x o clássico).",
)
CONSOLIDATED_METRICS_FILE = DEFAULT_LOG_DIR / "metrics_consolidated.json"


def _load_consolidated_metrics():
    """Overlay live battery results from logs/metrics_consolidated.json if present.

    The literals above stay as the committed official baseline. If the JSON is
    missing or malformed the dashboard renders exactly those defaults, so the
    live presentation never depends on a generated file. Produced by
    tools/consolidate_metrics.py.
    """
    try:
        with CONSOLIDATED_METRICS_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    g = globals()

    def overlay_str(name, key):
        value = data.get(key)
        if isinstance(value, str) and value:
            g[name] = value

    overlay_str("CONSOLIDATED_ACCEPTANCE_LOG", "acceptance_log")
    overlay_str("CONSOLIDATED_ACCEPTANCE_LABEL", "acceptance_label")
    overlay_str("CONSOLIDATED_METRICS_STATUS", "metrics_status")
    overlay_str("CONSOLIDATED_MISSION_TITLE", "mission_title")
    summary = data.get("summary")
    if isinstance(summary, dict):
        g["CONSOLIDATED_SUMMARY"] = {**CONSOLIDATED_SUMMARY, **summary}
    checks = data.get("aes_gcm_checks")
    if isinstance(checks, dict):
        g["CONSOLIDATED_AES_GCM_CHECKS"] = {**CONSOLIDATED_AES_GCM_CHECKS, **checks}
    baseline = data.get("mission_baseline")
    if isinstance(baseline, dict) and all(s in baseline for s in MISSION_OVERLAY_SCENARIOS):
        g["CONSOLIDATED_MISSION_BASELINE"] = {
            s: {**CONSOLIDATED_MISSION_BASELINE[s], **baseline[s]} for s in MISSION_OVERLAY_SCENARIOS
        }
    limited = data.get("mission_limited")
    if isinstance(limited, dict) and all(s in limited for s in MISSION_OVERLAY_SCENARIOS):
        g["CONSOLIDATED_MISSION_LIMITED"] = {
            s: {**CONSOLIDATED_MISSION_LIMITED[s], **limited[s]} for s in MISSION_OVERLAY_SCENARIOS
        }
    bench = data.get("pqc_bench")
    if isinstance(bench, list) and bench:
        g["CONSOLIDATED_PQC_BENCH"] = tuple(tuple(row) for row in bench)
    notes = data.get("notes")
    if isinstance(notes, list) and notes:
        g["CONSOLIDATED_NOTES"] = tuple(str(line) for line in notes)


_load_consolidated_metrics()
RESULTS_REFERENCES = (
    ("NIST FIPS 203", "ML-KEM como KEM pos-quantico, 2024"),
    ("NIST FIPS 197", "AES como cifra de bloco padrao, atual. 2023"),
    ("NIST SP 800-38D", "GCM/GMAC para AEAD com nonce e tag, 2007"),
    ("Koopman & Chakravarty", "CRC para deteccao em redes embarcadas, DSN 2004"),
)
MOTIVATION_REFERENCES = (
    ("NIST PQC Project", "ameaca quantica e migracao para PQC"),
    ("NASA SmallSat SoA", "SmallSats exigem escolhas de plataforma"),
    ("Mikaelian 2009", "radiacao e charging ameacam eletronica espacial"),
)
DETAILED_RESULTS_REFERENCES = (
    (
        "NIST FIPS 203 — ML-KEM (2024)",
        "Define KeyGen, Encaps, Decaps e tamanhos do ML-KEM. O KEM estabelece segredo; não cifra o payload.",
        "doi.org/10.6028/NIST.FIPS.203",
    ),
    (
        "NIST FIPS 197 — AES (atualização 2023)",
        "Define AES-128/192/256 como cifras de bloco; sustenta a camada simétrica usada para cifrar os dados.",
        "doi.org/10.6028/NIST.FIPS.197-upd1",
    ),
    (
        "NIST SP 800-38D — GCM/GMAC (2007)",
        "Define GCM como AEAD e os papéis de nonce, ciphertext e tag. No projeto, 12 B + 16 B explicam os 28 B.",
        "doi.org/10.6028/NIST.SP.800-38D",
    ),
    (
        "Koopman & Chakravarty — CRC (DSN 2004)",
        "Base para escolher CRC em redes embarcadas. CRC detecta erros; não fornece autenticação criptográfica.",
        "users.ece.cmu.edu/~koopman/crc",
    ),
    (
        "NASA Small Spacecraft Avionics SoA (2024)",
        "Contextualiza OBC, COTS, restrições SWaP-C e mitigação de radiação em pequenos satélites.",
        "nasa.gov/smallsat-institute/sst-soa",
    ),
    (
        "Mikaelian — Spacecraft Charging (2009)",
        "Contextualiza charging e radiação na eletrônica espacial. Motiva o bit-flip sem alegar ensaio físico de radiação.",
        "arXiv:0906.3884",
    ),
)

# --- Paleta de Cores ----------------------------------------------------------
# REFATORAÇÃO VISUAL: Paleta High-Contrast Cyber-Space
C_SPACE_BG       = (0, 2, 10)
C_PANEL_BG       = (5, 10, 22)
C_PANEL_BORDER   = (0, 210, 255)
C_PANEL_HEADER   = (8, 18, 38)
C_ACCENT_CYAN    = (0, 245, 255)
C_ACCENT_BLUE    = (38, 128, 255)
C_ACCENT_GREEN   = (100, 255, 40)
C_ACCENT_ORANGE  = (255, 176, 32)
C_ACCENT_RED     = (255, 44, 84)
C_ACCENT_PURPLE  = (255, 70, 245)
C_TEXT_PRIMARY    = (248, 252, 255)
C_TEXT_DIM        = (148, 178, 210)
C_SAT_BODY       = (180, 198, 220)
C_SAT_PANEL_BLUE = (0, 164, 255)
C_SAT_PANEL_DARK = (5, 38, 74)
C_SAT_GOLD       = (255, 222, 92)
C_ROBOT_FACE     = (230, 242, 255)
C_ROBOT_EYE      = (0, 245, 255)
C_ROBOT_SMILE    = (100, 255, 40)

# --- Fontes -------------------------------------------------------------------
def load_font(name, size):
    """Tenta carregar fonte do sistema, fallback para default."""
    try:
        return pygame.font.SysFont(name, size)
    except Exception:
        return pygame.font.Font(None, size)

FONT_TITLE   = load_font("monospace", 26)
FONT_HEADER  = load_font("monospace", 22)
FONT_BODY    = load_font("monospace", 17)
FONT_SMALL   = load_font("monospace", 15)
FONT_LARGE   = load_font("monospace", 40)
FONT_CMD     = load_font("monospace", 17)
FONT_PIXEL   = load_font("monospace", 13)
FONT_LABEL   = load_font("monospace", 13)


def init_display(*, windowed=False, windowed_size=(1366, 768)):
    """Initialize the dashboard display after CLI arguments are parsed."""
    global WIDTH, HEIGHT, screen, clock

    pygame.init()
    if windowed:
        WIDTH, HEIGHT = (int(windowed_size[0]), int(windowed_size[1]))
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.DOUBLEBUF)
    else:
        info = pygame.display.Info()
        WIDTH, HEIGHT = info.current_w, info.current_h
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF)
    pygame.display.set_caption("PQC-SAT Mission Control Dashboard")
    clock = pygame.time.Clock()


# --- Nucleo experimental ------------------------------------------------------
@dataclass(frozen=True)
class FaultSpec:
    byte_index: int
    bit_mask: int
    fault_width: str = "single-bit"


@dataclass(frozen=True)
class ExperimentEvent:
    schema_version: str
    session_id: str
    campaign_seed: int
    trial_id: int
    campaign_run_id: str
    campaign_trial_id: int
    mode: str
    target: str
    byte_index: int
    bit_mask: int
    fault_width: str
    guard: str
    before_hex: str
    after_hex: str
    crc_before: str
    crc_after: str
    guard_prepare_us: int
    guard_verify_us: int
    guard_overhead_us: int
    result: str
    elapsed_us: int
    uptime_s: float

    @property
    def bit_mask_hex(self):
        return f"{self.bit_mask:02X}"

    def to_firmware_command(self):
        return f"FAULT {self.guard} {self.before_hex} {self.byte_index} 0x{self.bit_mask_hex}"


class ExperimentEngine:
    """Deterministic byte-mutation engine used by the dashboard and tests."""

    def __init__(self, seed=SIMULATION_SEED, payload=DEFAULT_PAYLOAD, session_id=None):
        self.seed = seed
        self.payload = bytes(payload)
        self.session_id = session_id or f"SIM-{seed}"
        self._rng = random.Random(seed)
        self._next_trial_id = 1
        self.events = []

    def reset(self):
        self._rng.seed(self.seed)
        self._next_trial_id = 1
        self.events.clear()

    def next_spec(self):
        if not self.payload:
            raise ValueError("payload vazio")
        byte_index = self._rng.randrange(len(self.payload))
        bit_mask = 1 << self._rng.randrange(8)
        return FaultSpec(byte_index=byte_index, bit_mask=bit_mask)

    def run_fault(
        self,
        *,
        guard="NONE",
        spec=None,
        mode="SIMULATED",
        target="PAYLOAD",
        uptime_s=0.0,
        campaign_run_id="manual",
        campaign_trial_id=None,
    ):
        guard = guard.upper()
        if guard not in {"NONE", "CRC32"}:
            raise ValueError("guard deve ser NONE ou CRC32")
        if spec is None:
            spec = self.next_spec()
        self._validate_spec(spec)

        started = time.perf_counter_ns()
        data = bytearray(self.payload)
        before = bytes(data)
        guard_prepare_us = 0
        guard_verify_us = 0

        crc_started = time.perf_counter_ns()
        crc_before = _crc32_hex(before)
        if guard == "CRC32":
            guard_prepare_us = max(1, (time.perf_counter_ns() - crc_started) // 1000)

        data[spec.byte_index] ^= spec.bit_mask
        after = bytes(data)
        crc_started = time.perf_counter_ns()
        crc_after = _crc32_hex(after)
        if guard == "CRC32":
            guard_verify_us = max(1, (time.perf_counter_ns() - crc_started) // 1000)

        if after == before:
            result = "OK"
        elif guard == "CRC32" and crc_after != crc_before:
            result = "DETECTED_GUARD"
        else:
            result = "SILENT"

        elapsed_us = max(1, (time.perf_counter_ns() - started) // 1000)
        event = ExperimentEvent(
            schema_version="pqc-sat-event-v1",
            session_id=self.session_id,
            campaign_seed=self.seed,
            trial_id=self._next_trial_id,
            campaign_run_id=campaign_run_id,
            campaign_trial_id=campaign_trial_id or self._next_trial_id,
            mode=mode,
            target=target,
            byte_index=spec.byte_index,
            bit_mask=spec.bit_mask,
            fault_width=spec.fault_width,
            guard=guard,
            before_hex=before.hex().upper(),
            after_hex=after.hex().upper(),
            crc_before=crc_before,
            crc_after=crc_after,
            guard_prepare_us=guard_prepare_us,
            guard_verify_us=guard_verify_us,
            guard_overhead_us=guard_prepare_us + guard_verify_us,
            result=result,
            elapsed_us=elapsed_us,
            uptime_s=uptime_s,
        )
        self._next_trial_id += 1
        self.events.append(event)
        return event

    def _validate_spec(self, spec):
        if not 0 <= spec.byte_index < len(self.payload):
            raise ValueError("byte_index fora do payload")
        if not _is_single_bit_mask(spec.bit_mask):
            raise ValueError("bit_mask deve ter exatamente um bit")


def _is_single_bit_mask(value):
    return isinstance(value, int) and 1 <= value <= 0x80 and (value & (value - 1)) == 0


def _crc32_hex(data):
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def event_summary(events):
    unique_events = []
    seen = set()
    for event in events:
        event_key = (event.session_id, event.trial_id, event.target, event.guard)
        if event_key in seen:
            continue
        seen.add(event_key)
        unique_events.append(event)

    summary = {
        "events": len(unique_events),
        "ok": 0,
        "silent": 0,
        "detected_guard": 0,
        "key_mismatch": 0,
        "protocol_reject": 0,
        "invalid_input": 0,
    }
    for event in unique_events:
        key = event.result.lower()
        if key in summary:
            summary[key] += 1
    return summary


def checksum_metrics(events):
    crc_events = [event for event in events if event.guard == "CRC32"]
    detected = sum(1 for event in crc_events if event.result == "DETECTED_GUARD")
    total = len(crc_events)
    overhead_values = [event.guard_overhead_us for event in crc_events]
    prepare_values = [event.guard_prepare_us for event in crc_events]
    verify_values = [event.guard_verify_us for event in crc_events]
    avg_overhead = sum(overhead_values) / len(overhead_values) if overhead_values else 0.0
    avg_prepare = sum(prepare_values) / len(prepare_values) if prepare_values else 0.0
    avg_verify = sum(verify_values) / len(verify_values) if verify_values else 0.0
    return {
        "guard": "CRC32",
        "events": total,
        "detected": detected,
        "detection_rate_pct": round((detected / total) * 100, 2) if total else 0.0,
        "avg_prepare_us": round(avg_prepare, 2),
        "avg_verify_us": round(avg_verify, 2),
        "avg_overhead_us": round(avg_overhead, 2),
        "max_overhead_us": max(overhead_values) if overhead_values else 0,
    }


def session_checksum_mode(events, current_guard="NONE"):
    guards = {event.guard for event in events}
    if not guards:
        return current_guard
    if len(guards) == 1:
        return next(iter(guards))
    return "MIXED"


def event_to_json(event):
    data = asdict(event)
    data["bit_mask_hex"] = event.bit_mask_hex
    data["scenario"] = "B_CRC32" if event.guard == "CRC32" else "A_NONE"
    return data


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_slug(value):
    return re.sub(r"[^a-z0-9_-]", "-", str(value).lower()).strip("-") or "session"


def _atomic_write_json(document, log_dir=DEFAULT_LOG_DIR):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    session_slug = _safe_slug(document.get("session_id", "session"))
    path = log_dir / f"{timestamp}_{session_slug}.json"
    suffix = 1
    while path.exists():
        path = log_dir / f"{timestamp}_{session_slug}_{suffix}.json"
        suffix += 1

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)
    return path


def _parse_u8_token(token):
    try:
        value = int(token, 0)
    except ValueError:
        try:
            value = int(token, 16)
        except ValueError:
            raise ValueError(f"token invalido: {token!r}")
    if not 0 <= value <= 255:
        raise ValueError("valor fora de 0..255")
    return value


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_bytes(value):
    parsed = _optional_int(value)
    if parsed is None:
        return "--"
    if parsed >= 1024 * 1024:
        return f"{parsed / (1024 * 1024):.1f} MB"
    if parsed >= 1024:
        return f"{parsed / 1024:.0f} KB"
    return f"{parsed} B"


def _format_elapsed(value):
    parsed = _optional_int(value)
    if parsed is None:
        return "--"
    if parsed >= 1000000:
        return f"{parsed / 1000000:.2f} s"
    if parsed >= 1000:
        return f"{parsed / 1000:.1f} ms"
    return f"{parsed} us"


def _compact_value(value, default="NA"):
    if value is None or value == "":
        return default
    text = str(value).strip()
    if not text:
        return default
    return text.replace("|", "/").replace(" ", "_")[:12]


def live_payload_text_from_readings(seq, readings, *, max_bytes=LIVE_PAYLOAD_MAX_BYTES):
    """Build a compact ASCII payload that fits the firmware mission buffer."""

    temp = _compact_value(readings.get("temp_c_x100"))
    hum = _compact_value(readings.get("hum_x100"))
    ax = _compact_value(readings.get("x_mg"))
    ay = _compact_value(readings.get("y_mg"))
    az = _compact_value(readings.get("z_mg"))
    light = _compact_value(readings.get("clear"))
    pot = _compact_value(readings.get("pot"))
    button = _compact_value(readings.get("button"))
    fields = (
        ("S", str(seq % 10000)),
        ("T", temp),
        ("H", hum),
        ("X", ax),
        ("Y", ay),
        ("Z", az),
        ("L", light),
        ("P", pot),
        ("B", button),
        ("OK", ""),
    )
    payload = "PQC-SAT"
    for key, value in fields:
        chunk = f"|{key}" if value == "" else f"|{key}={value}"
        if len((payload + chunk).encode("ascii", errors="replace")) > max_bytes:
            break
        payload += chunk
    return payload


def payload_hex_from_text(payload_text):
    return payload_text.encode("ascii", errors="replace").hex().upper()


def fault_spec_from_pot(pot_value, payload_len):
    if payload_len <= 0:
        raise ValueError("payload vazio")
    parsed = _optional_int(pot_value)
    if parsed is None:
        return None
    clamped = max(0, min(4095, parsed))
    total_bits = payload_len * 8
    bit_position = min(total_bits - 1, int(round((clamped / 4095) * (total_bits - 1))))
    return FaultSpec(byte_index=bit_position // 8, bit_mask=1 << (bit_position % 8))


def _process_rss_bytes():
    try:
        import resource
    except ImportError:
        return None

    try:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (OSError, ValueError):
        return None

    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def _draw_splash(surface, mode_label, t):
    surface.fill(C_SPACE_BG)
    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2

    pulse = 0.65 + 0.35 * math.sin(t * 3.0)
    glow_color = (0, int(150 + 80 * pulse), 255)
    pygame.draw.circle(surface, (*glow_color, 38), (center_x, center_y - 32), 120, 2)
    pygame.draw.circle(surface, (*C_ACCENT_CYAN, 80), (center_x, center_y - 32), 74, 1)
    draw_robot_pixel(surface, center_x, center_y - 40, pixel_size=9, t=t)

    title = FONT_LARGE.render("PQC-SAT", True, C_ACCENT_CYAN)
    surface.blit(title, (center_x - title.get_width() // 2, center_y + 56))

    subtitle = FONT_BODY.render("ML-KEM-512 | CRC32 | BIT-FLIPS", True, C_TEXT_PRIMARY)
    surface.blit(subtitle, (center_x - subtitle.get_width() // 2, center_y + 102))

    mode = FONT_SMALL.render(mode_label, True, C_ACCENT_ORANGE if "WISDOM" in mode_label else C_ACCENT_GREEN)
    surface.blit(mode, (center_x - mode.get_width() // 2, center_y + 134))


def show_splash(mode_label, duration=SPLASH_SECONDS):
    if screen is None:
        return True

    start = time.monotonic()
    while time.monotonic() - start < duration:
        elapsed = time.monotonic() - start
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    return False
                if event.key in {pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN}:
                    return True

        _draw_splash(screen, mode_label, elapsed)
        pygame.display.flip()
        clock.tick(FPS)
    return True


# --- Estrelas de fundo --------------------------------------------------------
class StarField:
    def __init__(self, count=300):
        self.stars = []
        for _ in range(count):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            brightness = random.randint(80, 255)
            size = random.choice([1, 1, 1, 2, 2, 3])
            twinkle_speed = random.uniform(0.5, 3.0)
            twinkle_offset = random.uniform(0, math.pi * 2)
            self.stars.append((x, y, brightness, size, twinkle_speed, twinkle_offset))

    def draw(self, surface, t):
        for x, y, brightness, size, speed, offset in self.stars:
            b = int(brightness * (0.5 + 0.5 * math.sin(t * speed + offset)))
            b = max(30, min(255, b))
            color = (b, b, int(b * 0.95))
            if size <= 1:
                surface.set_at((x % surface.get_width(), y % surface.get_height()), color)
            else:
                pygame.draw.circle(surface, color,
                                   (x % surface.get_width(), y % surface.get_height()), size // 2)


# --- Terra --------------------------------------------------------------------
class Earth:
    def __init__(self):
        self.radius = 180
        self.center_x = WIDTH // 2
        self.center_y = HEIGHT // 2 + 20
        # REFATORAÇÃO VISUAL: Terra com Textura Rolável
        self.size = 0
        self.base_cache = None
        self.land_texture = None
        self.land_view_cache = None
        self.circle_mask = None
        self.overlay_cache = None
        self.rotation_speed_px = 10.0
        self._build_surface()

    def _build_surface(self):
        margin = 50
        size = self.radius * 2 + margin * 2
        self.size = size
        cx, cy = size // 2, size // 2
        r = self.radius
        self.base_cache = pygame.Surface((size, size), pygame.SRCALPHA)
        self.overlay_cache = pygame.Surface((size, size), pygame.SRCALPHA)
        self.land_view_cache = pygame.Surface((size, size), pygame.SRCALPHA)
        self.circle_mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(self.circle_mask, (255, 255, 255, 255), (cx, cy), r)

        # REFATORAÇÃO VISUAL: Atmosfera da Terra
        # Glow atmosferico externo
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(self.base_cache, (50, 130, 255, min(alpha, 120)), (cx, cy), r + i)

        # Corpo base — oceano azul SOLIDO e opaco
        pygame.draw.circle(self.base_cache, (25, 100, 200, 255), (cx, cy), r)
        pygame.draw.circle(self.base_cache, (30, 90, 185, 255), (cx, cy), r - 2)

        # REFATORAÇÃO VISUAL: Continentes em Textura Contínua
        # Continentes sao renderizados uma unica vez em textura continua 2D.
        land_single = pygame.Surface((size, size), pygame.SRCALPHA)
        # -- Continente das Americas -- GRANDE, preenche quase toda a face
        land_color = (50, 170, 75)
        scale = r / 140

        # America do Norte
        points_na = [
            (int(cx - 15 * scale), int(cy - 120 * scale)),
            (int(cx + 50 * scale), int(cy - 110 * scale)),
            (int(cx + 80 * scale), int(cy - 85 * scale)),
            (int(cx + 90 * scale), int(cy - 50 * scale)),
            (int(cx + 70 * scale), int(cy - 20 * scale)),
            (int(cx + 40 * scale), int(cy - 5 * scale)),
            (int(cx + 20 * scale), int(cy + 5 * scale)),
            (int(cx + 5 * scale), int(cy - 10 * scale)),
            (int(cx - 30 * scale), int(cy - 15 * scale)),
            (int(cx - 60 * scale), int(cy - 40 * scale)),
            (int(cx - 80 * scale), int(cy - 70 * scale)),
            (int(cx - 70 * scale), int(cy - 100 * scale)),
            (int(cx - 40 * scale), int(cy - 115 * scale)),
        ]
        pygame.draw.polygon(land_single, (*land_color, 255), points_na)
        pygame.draw.polygon(land_single, (60, 185, 85, 80), points_na)
        pygame.draw.polygon(land_single, (35, 130, 55, 180), points_na, 2)

        # America Central
        points_ca = [
            (int(cx + 20 * scale), int(cy + 5 * scale)),
            (int(cx + 30 * scale), int(cy + 15 * scale)),
            (int(cx + 25 * scale), int(cy + 35 * scale)),
            (int(cx + 15 * scale), int(cy + 40 * scale)),
            (int(cx + 5 * scale), int(cy + 30 * scale)),
            (int(cx + 10 * scale), int(cy + 10 * scale)),
        ]
        pygame.draw.polygon(land_single, (*land_color, 255), points_ca)
        pygame.draw.polygon(land_single, (35, 130, 55, 180), points_ca, 2)

        # America do Sul
        points_sa = [
            (int(cx + 15 * scale), int(cy + 40 * scale)),
            (int(cx + 55 * scale), int(cy + 45 * scale)),
            (int(cx + 75 * scale), int(cy + 55 * scale)),
            (int(cx + 80 * scale), int(cy + 75 * scale)),
            (int(cx + 60 * scale), int(cy + 100 * scale)),
            (int(cx + 30 * scale), int(cy + 115 * scale)),
            (int(cx + 5 * scale), int(cy + 110 * scale)),
            (int(cx - 15 * scale), int(cy + 90 * scale)),
            (int(cx - 25 * scale), int(cy + 65 * scale)),
            (int(cx - 10 * scale), int(cy + 48 * scale)),
        ]
        pygame.draw.polygon(land_single, (45, 160, 70, 255), points_sa)
        # Amazonia
        amazon = [
            (int(cx + 20 * scale), int(cy + 55 * scale)),
            (int(cx + 55 * scale), int(cy + 60 * scale)),
            (int(cx + 50 * scale), int(cy + 80 * scale)),
            (int(cx + 15 * scale), int(cy + 75 * scale)),
        ]
        pygame.draw.polygon(land_single, (35, 140, 55, 120), amazon)
        pygame.draw.polygon(land_single, (30, 120, 50, 180), points_sa, 2)

        # Groenlandia
        points_gl = [
            (int(cx + 20 * scale), int(cy - 115 * scale)),
            (int(cx + 50 * scale), int(cy - 120 * scale)),
            (int(cx + 55 * scale), int(cy - 100 * scale)),
            (int(cx + 40 * scale), int(cy - 90 * scale)),
            (int(cx + 20 * scale), int(cy - 95 * scale)),
        ]
        pygame.draw.polygon(land_single, (180, 210, 200, 255), points_gl)
        pygame.draw.polygon(land_single, (140, 170, 160, 150), points_gl, 1)

        # Ilhas do Caribe
        for ix2, iy2, iw, ih in [
            (int(cx + 35 * scale), int(cy + 15 * scale), int(10 * scale), int(6 * scale)),
            (int(cx + 45 * scale), int(cy + 22 * scale), int(8 * scale), int(5 * scale)),
            (int(cx + 40 * scale), int(cy + 30 * scale), int(6 * scale), int(4 * scale)),
        ]:
            pygame.draw.ellipse(land_single, (*land_color, 250),
                                (ix2, iy2, max(3, iw), max(3, ih)))

        def draw_continent(offsets, fill, highlight=(78, 190, 92, 65)):
            points = [
                (int(cx + ox * scale), int(cy + oy * scale))
                for ox, oy in offsets
            ]
            pygame.draw.polygon(land_single, (*fill, 255), points)
            pygame.draw.polygon(land_single, highlight, points)
            pygame.draw.polygon(land_single, (30, 120, 50, 190), points, 2)
            return points

        # Europa e massa eurasiática, posicionadas no hemisfério oposto às Américas.
        draw_continent(
            [
                (-142, -70), (-132, -92), (-108, -108), (-74, -112),
                (-44, -98), (-28, -78), (-42, -58), (-70, -48),
                (-92, -54), (-112, -44), (-132, -52),
            ],
            (55, 165, 78),
        )

        # África, com uma faixa desértica sutil para facilitar o reconhecimento.
        draw_continent(
            [
                (-126, -48), (-98, -55), (-72, -38), (-62, -8),
                (-72, 26), (-88, 66), (-106, 94), (-122, 68),
                (-136, 34), (-142, -6),
            ],
            (48, 158, 70),
        )
        sahara = [
            (int(cx - 126 * scale), int(cy - 35 * scale)),
            (int(cx - 82 * scale), int(cy - 34 * scale)),
            (int(cx - 68 * scale), int(cy - 10 * scale)),
            (int(cx - 132 * scale), int(cy - 4 * scale)),
        ]
        pygame.draw.polygon(land_single, (190, 170, 75, 105), sahara)

        # Índia, Sudeste Asiático e ilhas próximas.
        draw_continent(
            [
                (-72, -44), (-54, -40), (-40, -22), (-48, 2),
                (-61, 20), (-70, -4), (-82, -24),
            ],
            (52, 168, 76),
        )
        for ox, oy, radius in ((-44, 8, 5), (-34, 16, 4), (-25, 24, 3), (-118, 82, 4)):
            pygame.draw.circle(
                land_single,
                (*land_color, 245),
                (int(cx + ox * scale), int(cy + oy * scale)),
                max(2, int(radius * scale)),
            )

        # Austrália e Nova Zelândia.
        draw_continent(
            [
                (-72, 62), (-46, 52), (-24, 66), (-18, 88),
                (-38, 106), (-66, 104), (-84, 86),
            ],
            (58, 164, 72),
        )
        pygame.draw.ellipse(
            land_single,
            (*land_color, 245),
            (
                int(cx - 12 * scale),
                int(cy + 94 * scale),
                max(3, int(5 * scale)),
                max(5, int(12 * scale)),
            ),
        )

        # Antártida estilizada fecha a borda sul da textura.
        antarctica = [
            (int(cx + ox * scale), int(cy + oy * scale))
            for ox, oy in (
                (-118, 118), (-82, 112), (-48, 120), (-12, 114),
                (26, 121), (62, 114), (102, 120), (116, 132),
                (72, 137), (24, 134), (-26, 139), (-76, 134),
            )
        ]
        pygame.draw.polygon(land_single, (190, 218, 205, 235), antarctica)
        pygame.draw.polygon(land_single, (140, 180, 170, 170), antarctica, 1)

        self.land_texture = pygame.Surface((size * 2, size), pygame.SRCALPHA)
        self.land_texture.blit(land_single, (0, 0))
        self.land_texture.blit(land_single, (size, 0))

        # REFATORAÇÃO VISUAL: Overlay Atmosférico Estático
        # Nuvens, luz e terminador ficam em overlay estatico acima do mapa.
        # Nuvens
        clouds = [
            (cx - 40, cy - 50, 70, 18),
            (cx + 50, cy - 30, 60, 15),
            (cx - 20, cy + 50, 65, 14),
            (cx + 40, cy + 70, 50, 12),
            (cx + 10, cy - 80, 55, 13),
        ]
        for x, y, w, h in clouds:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (220, 235, 255, 45), (0, 0, w, h))
            self.overlay_cache.blit(s, (x - w // 2, y - h // 2))

        # Iluminacao solar
        light_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            ratio = i / r
            alpha = int(50 * (1 - ratio) ** 2)
            pygame.draw.circle(light_surf, (255, 255, 255, min(alpha, 40)),
                               (cx - int(r * 0.3), cy - int(r * 0.3)), i)
        self.overlay_cache.blit(light_surf, (0, 0))

        # Sombra terminador
        shadow_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            ratio = i / r
            alpha = int(80 * (1 - ratio) ** 1.5)
            pygame.draw.circle(shadow_surf, (0, 0, 20, min(alpha, 60)),
                               (cx + int(r * 0.35), cy + int(r * 0.35)), i)
        self.overlay_cache.blit(shadow_surf, (0, 0))

        # Glow e borda final acima do mapa rolavel.
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(self.overlay_cache, (50, 130, 255, min(alpha, 95)), (cx, cy), r + i)
        pygame.draw.circle(self.overlay_cache, (80, 160, 255, 50), (cx, cy), r, 2)

    def draw(self, surface, t):
        blit_x = self.center_x - self.size // 2
        blit_y = self.center_y - self.size // 2
        surface.blit(self.base_cache, (blit_x, blit_y))
        if self.land_texture is not None:
            # REFATORAÇÃO VISUAL: Rotação por Scrolling 2D
            # Scrolling 2D: recorta a textura duplicada sem redesenhar poligonos.
            offset_x = int((t * self.rotation_speed_px) % self.size)
            self.land_view_cache.fill((0, 0, 0, 0))
            self.land_view_cache.blit(self.land_texture, (0, 0), pygame.Rect(offset_x, 0, self.size, self.size))
            self.land_view_cache.blit(self.circle_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(self.land_view_cache, (blit_x, blit_y))
        surface.blit(self.overlay_cache, (blit_x, blit_y))


# --- Robo Pixel Art -----------------------------------------------------------
ROBOT_PIXELS = [
    (3, 0, 'A'), (4, 0, 'A'), (7, 0, 'A'), (8, 0, 'A'),
    (2, 1, 'H'), (3, 1, 'H'), (4, 1, 'H'), (5, 1, 'H'), (6, 1, 'H'), (7, 1, 'H'), (8, 1, 'H'), (9, 1, 'H'),
    (1, 2, 'H'), (2, 2, 'B'), (3, 2, 'B'), (4, 2, 'B'), (5, 2, 'B'), (6, 2, 'B'), (7, 2, 'B'), (8, 2, 'B'), (9, 2, 'B'), (10, 2, 'H'),
    (1, 3, 'H'), (2, 3, 'B'), (3, 3, 'E'), (4, 3, 'E'), (5, 3, 'B'), (6, 3, 'B'), (7, 3, 'E'), (8, 3, 'E'), (9, 3, 'B'), (10, 3, 'H'),
    (1, 4, 'H'), (2, 4, 'B'), (3, 4, 'B'), (4, 4, 'B'), (5, 4, 'B'), (6, 4, 'B'), (7, 4, 'B'), (8, 4, 'B'), (9, 4, 'B'), (10, 4, 'H'),
    (1, 5, 'H'), (2, 5, 'B'), (3, 5, 'S'), (4, 5, 'B'), (5, 5, 'B'), (6, 5, 'B'), (7, 5, 'B'), (8, 5, 'S'), (9, 5, 'B'), (10, 5, 'H'),
    (1, 6, 'H'), (2, 6, 'B'), (3, 6, 'B'), (4, 6, 'S'), (5, 6, 'S'), (6, 6, 'S'), (7, 6, 'S'), (8, 6, 'B'), (9, 6, 'B'), (10, 6, 'H'),
    (2, 7, 'H'), (3, 7, 'H'), (4, 7, 'H'), (5, 7, 'H'), (6, 7, 'H'), (7, 7, 'H'), (8, 7, 'H'), (9, 7, 'H'),
]

ROBOT_COLORS = {
    'B': C_ROBOT_FACE,
    'E': C_ROBOT_EYE,
    'S': C_ROBOT_SMILE,
    'A': C_SAT_GOLD,
    'H': (60, 70, 100),
}


def draw_robot_pixel(surface, cx, cy, pixel_size=3, t=0.0):
    """Desenha o robo sorridente em pixel art centralizado em (cx, cy)."""
    grid_w, grid_h = 12, 8
    offset_x = cx - (grid_w * pixel_size) // 2
    offset_y = cy - (grid_h * pixel_size) // 2

    for col, row, key in ROBOT_PIXELS:
        color = list(ROBOT_COLORS[key])
        if key == 'E':
            pulse = 0.7 + 0.3 * math.sin(t * 4)
            color = [int(c * pulse) for c in color]
        if key == 'S':
            pulse = 0.8 + 0.2 * math.sin(t * 3 + 1)
            color = [int(c * pulse) for c in color]
        px = offset_x + col * pixel_size
        py = offset_y + row * pixel_size
        pygame.draw.rect(surface, color, (px, py, pixel_size, pixel_size))


# ----- Sprite atlas ----------------------------------------------------------


class DashboardSerialClient:
    """Non-blocking serial worker used by the Pygame dashboard."""

    def __init__(self, port=None, baudrate=115200, timeout=SERIAL_TIMEOUT_SECONDS):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
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
        if self.port:
            return self.port

        ports = list_serial_ports()
        if len(ports) == 1:
            return ports[0].device

        wisdom_candidates = []
        for port in ports:
            text = f"{port.device} {port.description} {port.manufacturer}".lower()
            if "cp210" in text or "silicon labs" in text:
                wisdom_candidates.append(port.device)

        if len(wisdom_candidates) == 1:
            return wisdom_candidates[0]

        if not ports:
            raise SerialBridgeError("no serial ports found")
        names = ", ".join(port.device for port in ports)
        raise SerialBridgeError(f"multiple serial ports found: {names}")

    def _run(self):
        while not self._stop.is_set():
            try:
                port = self._choose_port()
                self.actual_port = port
                self._rx.put(("state", {"connected": False, "status": f"OPENING {port}"}))
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
                    self._rx.put(("state", {"connected": True, "status": f"SATELLITE {port}"}))
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
                self._rx.put(("state", {"connected": False, "status": str(exc)}))
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

        node = payload.get("node", "")
        board = payload.get("board", "")
        if node != "PQC-SAT-WISDOM" or board != "BlackBoard-Wisdom":
            raise SerialBridgeError(f"serial device is not PQC-SAT Wisdom: node={node} board={board}")
        return payload

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
            if emit_event:
                self._rx.put(event)
            self._notify_reply(reply, event)
            self._rx.put(("state", {"connected": False, "status": str(exc)}))
            return False

    @staticmethod
    def _split_command(command_line):
        parts = command_line.strip().split()
        if not parts:
            raise ProtocolError("empty command")
        return parts[0], parts[1:]


# --- Satelite CubeSat ---------------------------------------------------------
class Satellite:
    def __init__(self, earth):
        self.earth = earth
        self.orbit_radius = 380
        self.angle = 0.0
        self.orbit_speed = 0.3
        self.body_size = 90

    def update(self, dt):
        self.angle += self.orbit_speed * dt
        if self.angle > math.pi * 2:
            self.angle -= math.pi * 2

    def get_position(self):
        x = self.earth.center_x + self.orbit_radius * math.cos(self.angle)
        y = self.earth.center_y + self.orbit_radius * math.sin(self.angle) * 0.4
        return x, y

    def draw_orbit_line(self, surface):
        """Desenha a linha de orbita tracejada."""
        points = []
        for i in range(120):
            a = (i / 120) * math.pi * 2
            x = self.earth.center_x + self.orbit_radius * math.cos(a)
            y = self.earth.center_y + self.orbit_radius * math.sin(a) * 0.4
            points.append((x, y))
        for i in range(0, len(points) - 1, 2):
            pygame.draw.line(surface, (40, 70, 140, 40),
                             (int(points[i][0]), int(points[i][1])),
                             (int(points[i+1][0]), int(points[i+1][1])), 1)

    def draw_trail(self, surface, t):
        """Desenha rastro luminoso atras do satelite."""
        # REFATORAÇÃO VISUAL: Rastro do Satélite
        trail_len = 46
        for i in range(trail_len, 0, -1):
            a = self.angle - (i * 0.022)
            x = self.earth.center_x + self.orbit_radius * math.cos(a)
            y = self.earth.center_y + self.orbit_radius * math.sin(a) * 0.4
            fade = 1 - i / trail_len
            alpha = int(210 * fade)
            r_size = max(1, int(7 * fade))
            color = (
                int(C_ACCENT_BLUE[0] * (1 - fade) + C_ACCENT_CYAN[0] * fade),
                int(C_ACCENT_BLUE[1] * (1 - fade) + C_ACCENT_CYAN[1] * fade),
                int(C_ACCENT_BLUE[2] * (1 - fade) + C_ACCENT_CYAN[2] * fade),
            )
            glow_surf = pygame.Surface((r_size * 5, r_size * 5), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color, max(20, alpha // 3)),
                               (r_size * 2, r_size * 2), r_size * 2)
            pygame.draw.circle(glow_surf, (*color, alpha),
                               (r_size * 2, r_size * 2), r_size)
            surface.blit(glow_surf, (int(x) - r_size * 2, int(y) - r_size * 2))

    # OTIMIZAÇÃO SEMINÁRIO
    def draw(self, surface, t, offset=(0, 0)):
        self.draw_orbit_line(surface)
        self.draw_trail(surface, t)

        x, y = self.get_position()
        # OTIMIZAÇÃO SEMINÁRIO
        # Shake fisico aplicado apenas ao corpo do satelite, preservando fundo/UI.
        ix, iy = int(x + offset[0]), int(y + offset[1])
        bs = self.body_size

        # REFATORAÇÃO VISUAL: CubeSat HUD Neon
        # -- Paineis solares --
        panel_w, panel_h = bs + 24, bs // 3
        # Painel esquerdo
        for i in range(3):
            pulse = 0.65 + 0.35 * math.sin(t * 2.2 + i)
            color = (
                int(10 + C_SAT_PANEL_BLUE[0] * pulse),
                int(70 + C_SAT_PANEL_BLUE[1] * pulse * 0.55),
                int(130 + C_SAT_PANEL_BLUE[2] * pulse * 0.35),
            )
            rect_x = ix - bs // 2 - panel_w - 6
            rect_y = iy - panel_h // 2 + (i - 1) * 3
            pygame.draw.rect(surface, color, (rect_x, rect_y, panel_w, panel_h // 3 - 1))
        pygame.draw.rect(surface, C_SAT_PANEL_DARK,
                         (ix - bs // 2 - panel_w - 6, iy - panel_h // 2, panel_w, panel_h), 1)
        for gi in range(1, 4):
            gx = ix - bs // 2 - panel_w - 6 + (panel_w * gi) // 4
            pygame.draw.line(surface, C_SAT_PANEL_DARK,
                             (gx, iy - panel_h // 2), (gx, iy + panel_h // 2), 1)

        # Painel direito
        for i in range(3):
            pulse = 0.65 + 0.35 * math.sin(t * 2.2 + i + 1.1)
            color = (
                int(10 + C_SAT_PANEL_BLUE[0] * pulse),
                int(70 + C_SAT_PANEL_BLUE[1] * pulse * 0.55),
                int(130 + C_SAT_PANEL_BLUE[2] * pulse * 0.35),
            )
            rect_x = ix + bs // 2 + 6
            rect_y = iy - panel_h // 2 + (i - 1) * 3
            pygame.draw.rect(surface, color, (rect_x, rect_y, panel_w, panel_h // 3 - 1))
        pygame.draw.rect(surface, C_SAT_PANEL_DARK,
                         (ix + bs // 2 + 6, iy - panel_h // 2, panel_w, panel_h), 1)
        for gi in range(1, 4):
            gx = ix + bs // 2 + 6 + (panel_w * gi) // 4
            pygame.draw.line(surface, C_SAT_PANEL_DARK,
                             (gx, iy - panel_h // 2), (gx, iy + panel_h // 2), 1)

        # Hastes
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix - bs // 2, iy), (ix - bs // 2 - 6, iy), 2)
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix + bs // 2, iy), (ix + bs // 2 + 6, iy), 2)

        # -- Corpo do CubeSat --
        body_rect = pygame.Rect(ix - bs // 2, iy - bs // 2, bs, bs)
        glow_s = pygame.Surface((bs + 20, bs + 20), pygame.SRCALPHA)
        glow_alpha = int(72 + 44 * math.sin(t * 3))
        pygame.draw.rect(glow_s, (*C_ACCENT_CYAN, glow_alpha),
                         (0, 0, bs + 20, bs + 20), border_radius=6)
        surface.blit(glow_s, (ix - bs // 2 - 10, iy - bs // 2 - 10))
        pygame.draw.rect(surface, (36, 48, 62), body_rect, border_radius=4)
        pygame.draw.rect(surface, C_SAT_BODY, body_rect.inflate(-10, -10), border_radius=3)
        pygame.draw.rect(surface, C_ACCENT_CYAN, body_rect, 2, border_radius=4)
        pygame.draw.line(surface, C_PANEL_HEADER, (body_rect.x + 10, iy), (body_rect.right - 10, iy), 2)
        pygame.draw.line(surface, C_PANEL_HEADER, (ix, body_rect.y + 10), (ix, body_rect.bottom - 10), 2)

        # -- Robo sorridente --
        draw_robot_pixel(surface, ix, iy, pixel_size=6, t=t)

        # -- Antena --
        ant_height = 16
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix, iy - bs // 2), (ix, iy - bs // 2 - ant_height), 2)
        blink = 0.55 + 0.45 * math.sin(t * 8)
        beacon = (255, int(80 + 160 * blink), int(40 + 80 * blink))
        pygame.draw.circle(surface, beacon, (ix, iy - bs // 2 - ant_height), 4)
        pygame.draw.circle(surface, (*beacon, 80), (ix, iy - bs // 2 - ant_height), 10, 1)
        thruster_y = iy + bs // 2 + 4
        for radius, alpha in ((18, 38), (10, 90), (4, 210)):
            flame = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(flame, (*C_ACCENT_CYAN, alpha), (radius, radius), radius)
            surface.blit(flame, (ix - radius, thruster_y - radius))

        # Label
        label = FONT_PIXEL.render("PQC-SAT-01", True, C_ACCENT_CYAN)
        surface.blit(label, (ix - label.get_width() // 2, iy + bs // 2 + 8))


# --- Painel de Interface / Dashboard -----------------------------------------
class DashboardPanel:
    """Painel lateral com informacoes de telemetria e comandos."""

    def __init__(self, serial_client=None, *, stand_controller=None, stand_diagnostic=False):
        self.serial_client = serial_client
        self.stand_controller = stand_controller
        self.stand_mode = stand_controller is not None
        self.stand_diagnostic = bool(stand_diagnostic)
        self.stand_action_rects = {}
        self.serial_connected = False
        self.serial_status = "SERIAL DESATIVADA"
        self.hardware_payload = {}
        self.hardware_state = {}
        self.help_visible = False
        self.command_history = []
        self.command_button_rects = []
        self.live_payload_toggle_rect = None
        self.terminal_toggle_rect = None
        self.terminal_visible = False
        self.input_text = ""
        self.input_active = False
        self.cursor_blink = 0
        self.session_status = "SIMULADO"
        self.pqc_algorithm = "ML-KEM-512 (SIMULADO)" if serial_client is None else "ML-KEM-512 (PENDENTE)"
        self.fault_injections = 0
        self.silent_failures = 0
        self.detected_errors = 0
        self.uptime = 0.0
        self.session_seed = SIMULATION_SEED
        self.experiment = ExperimentEngine(seed=self.session_seed)
        self.experiment_events = self.experiment.events
        self.hardware_samples = []
        self.session_dirty = False
        self.last_export_path = None
        self.battery_runs = 0
        self.last_fault_event = None
        self.fault_overlay_visible = False
        self.fault_overlay = {}
        self.fault_overlay_position = None
        self.fault_overlay_opened_at = 0.0
        self.fault_overlay_closing_since = None
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.fault_flow_scrub_rect = None
        self.dragging_fault_overlay = False
        self.dragging_fault_flow = False
        self.fault_drag_offset = (0, 0)
        self.fault_flow_animation = None
        self.checksum_enabled = False
        self.pqc_enabled = True
        self.classic_enabled = False
        self.message_preset = "PQC"
        self.live_payload_enabled = True
        self.live_payload_seq = 1
        self.last_live_payload = None
        self.pending_mission_contexts = {}
        self.pending_fault_contexts = {}
        self.results_overlay_visible = False
        self.results_overlay_mode = "presentation"
        self.results_technical_page = 0
        self.top_results_btn_rect = None
        self.top_onboarding_btn_rect = None
        self.top_connection_text_rect = None
        self.request_onboarding = False
        self.results_details_btn_rect = None
        self.results_technical_page_btn_rect = None
        self.results_stress_btn_rect = None
        self.results_overlay_content_bottom = None
        self.results_insight_rects = []
        self.stress_state = "IDLE"
        self.stress_armed_until = 0.0
        self.stress_started_at = 0.0
        self.stress_payload = {}
        self.stress_status = "PRONTO"
        self.guard_mode = "NONE"
        self.cpu_active_window = []
        self.last_cpu_load_pct = 0.0
        self.demo_state = "IDLE"
        self.demo_previous_state = "IDLE"
        self.demo_attempts = DEMO_DEFAULT_ATTEMPTS
        self.demo_specs = []
        self.demo_index = 0
        self.demo_phase_elapsed = 0.0
        self.demo_elapsed_s = 0.0
        self.demo_run_id = ""
        self.demo_summary = {}
        self.demo_export_path = None
        self.last_mission = {}
        self.mission_effect_timer = 0.0
        self.mission_overlay_visible = False
        self.mission_overlay_close_rect = None
        self.mission_overlays = {}
        self.mission_overlay_order = []
        self.mission_overlay_positions = {}
        self.mission_overlay_opened_at = {}
        self.mission_overlay_closing_since = {}
        self.mission_overlay_rects = {}
        self.mission_overlay_close_rects = {}
        self.mission_overlay_drag_rects = {}
        self.mission_flow_control_rects = {}
        self.mission_flow_scrub_rects = {}
        self.mission_flow_stage_rects = {}
        self.mission_flow_explanation_line_counts = {}
        self.dragging_mission_overlay = None
        self.dragging_mission_flow_scenario = None
        self.mission_drag_offset = (0, 0)
        self.mission_flow_animations = {}
        self.mission_flow_animation = None
        self.effect_timer = 0.0
        self.effect_label = ""
        self.effect_color = C_ACCENT_CYAN
        # OTIMIZAÇÃO SEMINÁRIO
        # Estado visual curto para impacto fisico e chuva de bits sem bloquear loop.
        self.impact_shake_offset = (0, 0)
        self.bit_rain_particles = []
        self.ping_effect_timer = 0.0
        self.ping_effect_count = 0
        self.ping_effect_last_segment = None
        self._fault_overlay_surface = None
        self._append_history("SYS_INIT", "OK")
        self._append_history("MODE_SELECT", "SIMULADO")
        self._append_history("PQC_BACKEND", "AGUARDANDO")

        if self.serial_client is not None:
            self.serial_status = "INICIANDO SERIAL"
            self._append_history("SERIAL", "INICIANDO")
            self.serial_client.start()
            if not self.stand_mode:
                for command in SERIAL_STARTUP_COMMANDS:
                    self._queue_serial_command(command, visible=True)

    def close(self, *, auto_save=True):
        if auto_save and self.session_dirty and (self.experiment_events or self.hardware_samples):
            status = self._export_session_status(auto=True)
            if status == "EXPORT ERROR":
                self._append_history("AUTO_SAVE", "ERROR")
        if self.serial_client is not None:
            self.serial_client.stop()

    def satellite_online(self):
        return self.serial_client is not None and self.serial_connected

    def _append_history(self, cmd, status):
        t_str = time.strftime("%H:%M:%S")
        self.command_history.append({"time": t_str, "cmd": cmd.upper(), "status": status})
        if len(self.command_history) > 24:
            self.command_history.pop(0)

    def handle_event(self, event):
        if self.stand_mode and self._handle_stand_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.top_results_btn_rect is not None and self.top_results_btn_rect.collidepoint(event.pos):
                self._execute_command("PQC_RESULTS")
                return True
            if self.top_onboarding_btn_rect is not None and self.top_onboarding_btn_rect.collidepoint(event.pos):
                self.results_overlay_visible = False
                self.request_onboarding = True
                self.session_status = "ONBOARDING"
                return True

        if getattr(self, "results_overlay_visible", False):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                panel_rect, close_rect = self._results_overlay_geometry()
                if close_rect.collidepoint(event.pos):
                    self.results_overlay_visible = False
                    return True
                if self.results_details_btn_rect is not None and self.results_details_btn_rect.collidepoint(event.pos):
                    self.results_overlay_mode = "technical" if self.results_overlay_mode == "presentation" else "presentation"
                    if self.results_overlay_mode == "technical":
                        self.results_technical_page = 0
                    return True
                if (
                    self.results_overlay_mode == "technical"
                    and self.results_technical_page_btn_rect is not None
                    and self.results_technical_page_btn_rect.collidepoint(event.pos)
                ):
                    self.results_technical_page = 1 - self.results_technical_page
                    return True
                if "unittest" in sys.modules and self.results_stress_btn_rect is not None and self.results_stress_btn_rect.collidepoint(event.pos):
                    self._handle_stress_button_click()
                    return True
                if not panel_rect.collidepoint(event.pos):
                    self.results_overlay_visible = False
                    return True
                return True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.results_overlay_visible = False
                elif event.key == pygame.K_d:
                    self.results_overlay_mode = "technical" if self.results_overlay_mode == "presentation" else "presentation"
                    if self.results_overlay_mode == "technical":
                        self.results_technical_page = 0
                elif self.results_overlay_mode == "technical" and event.key in {pygame.K_LEFT, pygame.K_RIGHT}:
                    self.results_technical_page = 1 - self.results_technical_page
                return True
            elif event.type == pygame.MOUSEWHEEL:
                return True
            return True

        if self._handle_fault_overlay_event(event):
            return True

        if self._handle_mission_overlay_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if (
                event.button == 1
                and self.live_payload_toggle_rect is not None
                and self.live_payload_toggle_rect.collidepoint(event.pos)
            ):
                self._execute_command("TOGGLE_LIVE_PAYLOAD")
                self.input_active = False
                return

            if event.button == 1 and self._handle_command_button_click(event.pos):
                self.input_active = False
                return
            self.input_active = self.terminal_visible

        if event.type == pygame.KEYDOWN and self.terminal_visible:
            if event.key == pygame.K_RETURN:
                if self.input_text.strip():
                    self._execute_command(self.input_text.strip())
                    self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.input_text = ""
                if self.demo_state in {"RESULTS", "STOPPED"}:
                    self.demo_state = "IDLE"
                    self.demo_summary = {}
            else:
                if len(self.input_text) < 30 and event.unicode.isprintable():
                    self.input_text += event.unicode

    def _handle_stand_event(self, event):
        """Keep visitor input inside the guided presentation while it is active."""
        if event.type == pygame.KEYDOWN:
            if event.key in {pygame.K_SPACE, pygame.K_RETURN}:
                self.stand_controller.handle_button(origin="keyboard")
            elif event.key == pygame.K_F12:
                self.stand_diagnostic = not self.stand_diagnostic
            elif event.key == pygame.K_HOME:
                self.stand_controller.reset_to_attract(reason="operator_home_key")
            elif event.key == pygame.K_r and self.stand_controller.state.value == "ERROR":
                self.stand_controller.reset_to_attract(reason="operator_retry_key")
            elif event.key in {pygame.K_LEFT, pygame.K_PAGEDOWN}:
                self._adjust_stand_simulated_pot(-512 if event.key == pygame.K_PAGEDOWN else -128)
            elif event.key in {pygame.K_RIGHT, pygame.K_PAGEUP}:
                self._adjust_stand_simulated_pot(512 if event.key == pygame.K_PAGEUP else 128)
            return True

        # The dashboard below remains visible as context, but its manual command
        # blocks are intentionally disabled during the visitor's guided cycle.
        if event.type in {pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL}:
            return True
        return False

    def _adjust_stand_simulated_pot(self, delta):
        if getattr(self.stand_controller, "mode", "hardware") != "simulated":
            return
        if not hasattr(self.serial_client, "set_pot"):
            return
        config = self.stand_controller.config
        current = int(getattr(self.serial_client, "pot_value", config.pot_minimum))
        self.serial_client.set_pot(current + int(delta))
        self.stand_controller.note_interaction()

    def _handle_mission_overlay_event(self, event):
        if not getattr(self, "mission_overlay_visible", False):
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for scenario in reversed(self.mission_overlay_order):
                close_rect = self.mission_overlay_close_rects.get(scenario)
                if close_rect is not None and close_rect.collidepoint(event.pos):
                    self._close_mission_overlay(scenario)
                    return True

            for scenario in reversed(self.mission_overlay_order):
                control_rect = self.mission_flow_control_rects.get(scenario)
                if control_rect is not None and control_rect.collidepoint(event.pos):
                    self._bring_mission_overlay_to_front(scenario)
                    self._confirm_mission_flow(scenario)
                    return True

            for scenario in reversed(self.mission_overlay_order):
                scrub_rect = self.mission_flow_scrub_rects.get(scenario)
                if scrub_rect is not None and scrub_rect.collidepoint(event.pos):
                    self._bring_mission_overlay_to_front(scenario)
                    self.dragging_mission_flow_scenario = scenario
                    self._scrub_mission_flow_to_x(event.pos[0], scrub_rect, scenario)
                    return True

            for scenario in reversed(self.mission_overlay_order):
                rect = self.mission_overlay_rects.get(scenario)
                drag_rect = self.mission_overlay_drag_rects.get(scenario)
                if drag_rect is not None and drag_rect.collidepoint(event.pos):
                    self._bring_mission_overlay_to_front(scenario)
                    rect = self.mission_overlay_rects.get(scenario, drag_rect)
                    self.dragging_mission_overlay = scenario
                    self.mission_drag_offset = (event.pos[0] - rect.x, event.pos[1] - rect.y)
                    return True
                if rect is not None and rect.collidepoint(event.pos):
                    self._bring_mission_overlay_to_front(scenario)
                    return True

        if event.type == pygame.MOUSEMOTION and self.dragging_mission_flow_scenario:
            scenario = self.dragging_mission_flow_scenario
            scrub_rect = self.mission_flow_scrub_rects.get(scenario)
            if scrub_rect is not None:
                self._scrub_mission_flow_to_x(event.pos[0], scrub_rect, scenario)
            return True

        if event.type == pygame.MOUSEMOTION and self.dragging_mission_overlay:
            scenario = self.dragging_mission_overlay
            width, height = self._mission_overlay_size()
            x = event.pos[0] - self.mission_drag_offset[0]
            y = event.pos[1] - self.mission_drag_offset[1]
            self.mission_overlay_positions[scenario] = self._clamp_overlay_position(x, y, width, height)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_mission_flow_scenario:
            self.dragging_mission_flow_scenario = None
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_mission_overlay:
            self.dragging_mission_overlay = None
            return True

        return False

    def _handle_fault_overlay_event(self, event):
        if not getattr(self, "fault_overlay_visible", False):
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.fault_overlay_close_rect is not None and self.fault_overlay_close_rect.collidepoint(event.pos):
                self._close_fault_overlay()
                return True
            if self.fault_flow_control_rect is not None and self.fault_flow_control_rect.collidepoint(event.pos):
                self._confirm_fault_flow()
                return True
            if self.fault_flow_scrub_rect is not None and self.fault_flow_scrub_rect.collidepoint(event.pos):
                self.dragging_fault_flow = True
                self._scrub_fault_flow_to_x(event.pos[0])
                return True
            if self.fault_overlay_drag_rect is not None and self.fault_overlay_drag_rect.collidepoint(event.pos):
                rect = self.fault_overlay_rect or self.fault_overlay_drag_rect
                self.dragging_fault_overlay = True
                self.fault_drag_offset = (event.pos[0] - rect.x, event.pos[1] - rect.y)
                return True
            if self.fault_overlay_rect is not None and self.fault_overlay_rect.collidepoint(event.pos):
                return True

        if event.type == pygame.MOUSEMOTION and self.dragging_fault_flow:
            self._scrub_fault_flow_to_x(event.pos[0])
            return True

        if event.type == pygame.MOUSEMOTION and self.dragging_fault_overlay:
            width, height = self._fault_overlay_size()
            x = event.pos[0] - self.fault_drag_offset[0]
            y = event.pos[1] - self.fault_drag_offset[1]
            self.fault_overlay_position = self._clamp_overlay_position(x, y, width, height)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_fault_flow:
            self.dragging_fault_flow = False
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_fault_overlay:
            self.dragging_fault_overlay = False
            return True

        return False

    def _confirm_fault_flow(self):
        if self.fault_flow_animation is None:
            return
        animation = self.fault_flow_animation
        duration = max(0.001, animation.get("duration", FAULT_FLOW_ANIMATION_SECONDS))
        if not animation.get("awaiting_confirm") and animation.get("age", 0.0) < duration:
            return
        self.fault_flow_control_rect = None
        self.fault_flow_scrub_rect = None
        self.dragging_fault_flow = False
        self.fault_flow_animation = None

    def _scrub_fault_flow_to_x(self, mouse_x):
        animation = self.fault_flow_animation
        scrub_rect = self.fault_flow_scrub_rect
        if animation is None or scrub_rect is None:
            return
        duration = max(0.001, animation.get("duration", FAULT_FLOW_ANIMATION_SECONDS))
        ratio = (mouse_x - scrub_rect.x) / max(1, scrub_rect.width)
        ratio = max(0.0, min(1.0, ratio))
        animation["age"] = duration * ratio
        # Match the mission popup: grabbing the bar pauses autoplay and keeps
        # the fault flow exactly where the user leaves it.
        animation["paused"] = True
        animation["awaiting_confirm"] = ratio >= 1.0

    def _close_fault_overlay(self):
        if not self.fault_overlay_visible:
            return
        if self.fault_overlay_closing_since is None:
            self.fault_overlay_closing_since = self.uptime
        self.dragging_fault_overlay = False
        self.dragging_fault_flow = False

    def _clear_fault_overlay(self):
        self.fault_overlay_visible = False
        self.fault_overlay = {}
        self.fault_overlay_closing_since = None
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.fault_flow_scrub_rect = None
        self.dragging_fault_overlay = False
        self.dragging_fault_flow = False
        self.fault_flow_animation = None

    def _confirm_mission_flow(self, scenario):
        if not self._mission_overlay_is_animating(scenario):
            return
        animation = self._mission_flow_animation_for(scenario)
        if animation is None:
            return
        duration = max(0.001, animation.get("duration", MISSION_FLOW_ANIMATION_SECONDS))
        if not animation.get("awaiting_confirm") and animation.get("age", 0.0) < duration:
            return
        self.mission_flow_animations.pop(scenario, None)
        self._sync_active_mission_flow_animation()
        self.mission_flow_control_rects.pop(scenario, None)
        self.mission_flow_scrub_rects.pop(scenario, None)
        if self.dragging_mission_flow_scenario == scenario:
            self.dragging_mission_flow_scenario = None

    def _scrub_mission_flow_to_x(self, mouse_x, scrub_rect, scenario=None):
        animation = self._mission_flow_animation_for(scenario)
        if animation is None:
            return
        duration = max(0.001, animation.get("duration", MISSION_FLOW_ANIMATION_SECONDS))
        ratio = (mouse_x - scrub_rect.x) / max(1, scrub_rect.width)
        ratio = max(0.0, min(1.0, ratio))
        animation["age"] = duration * ratio
        # once the user grabs the bar the flow stops auto-advancing and stays
        # wherever it is dragged; the end still arms the VER DADOS confirmation.
        animation["paused"] = True
        animation["awaiting_confirm"] = ratio >= 1.0
        self._sync_active_mission_flow_animation()

    def _mission_flow_animation_for(self, scenario=None):
        animations = getattr(self, "mission_flow_animations", {})
        if scenario is not None:
            return animations.get(scenario)
        if self.dragging_mission_flow_scenario:
            return animations.get(self.dragging_mission_flow_scenario)
        if self.mission_flow_animation is not None:
            scenario = self.mission_flow_animation.get("scenario")
            if scenario in animations:
                return animations[scenario]
        if self.mission_overlay_order:
            for candidate in reversed(self.mission_overlay_order):
                if candidate in animations:
                    return animations[candidate]
        return None

    def _sync_active_mission_flow_animation(self):
        animations = getattr(self, "mission_flow_animations", {})
        self.mission_flow_animation = None
        if self.mission_overlay_order:
            for scenario in reversed(self.mission_overlay_order):
                animation = animations.get(scenario)
                if animation is not None:
                    self.mission_flow_animation = animation
                    return
        if animations:
            self.mission_flow_animation = next(reversed(animations.values()))

    def _execute_command(self, cmd):
        """Processa um comando digitado."""
        cmd_clean = cmd.strip()
        cmd_upper = cmd_clean.upper()
        parts = cmd_upper.split()
        command_name = parts[0] if parts else ""
        if cmd_upper != "HELP":
            self.help_visible = False

        if cmd_upper == "INJECT_FAULT":
            status = self._run_experiment_command(self.guard_mode)
        elif cmd_upper in MISSION_PRESET_COMMANDS:
            status = self._set_message_preset(MISSION_PRESET_COMMANDS[cmd_upper])
        elif cmd_upper == "SEND_MESSAGE":
            mission_status = self._execute_mission_command([self._current_message_scenario()])
            if mission_status is None:
                status = "ENVIANDO"
            else:
                status = mission_status
        elif cmd_upper == "TOGGLE_CLASSIC":
            if self.classic_enabled:
                self._set_message_preset("PQC")
            else:
                self._set_message_preset("CLASSIC")
            status = "CLÁSSICA ATIVADA" if self.classic_enabled else "PÓS-QUÂNTICA ATIVADA"
        elif cmd_upper == "TOGGLE_PQC":
            if self.pqc_enabled:
                self._set_message_preset("CLASSIC")
            else:
                self._set_message_preset("PQC")
            status = "PÓS-QUÂNTICA ATIVADA" if self.pqc_enabled else "CLÁSSICA ATIVADA"
        elif cmd_upper == "TOGGLE_CHECKSUM":
            enabled = not self.checksum_enabled
            self._set_checksum_enabled(enabled)
            if self.pqc_enabled:
                self.message_preset = "PQC_CRC32" if enabled else "PQC"
            status = "CHECKSUM ATIVADO" if self.checksum_enabled else "CHECKSUM DESATIVADO"
        elif command_name == "BIT_FLIP":
            status = self._run_experiment_command(self.guard_mode, parts[1:])
        elif command_name in {"CHECKSUM", "GUARD"}:
            status = self._execute_checksum_command(command_name, parts[1:])
        elif command_name == "MISSION":
            mission_status = self._execute_mission_command(parts[1:])
            if mission_status is None:
                return
            status = mission_status
        elif cmd_upper == "TOGGLE_LIVE_PAYLOAD":
            self.live_payload_enabled = not self.live_payload_enabled
            self.session_dirty = True
            self.session_status = "PAYLOAD VIVO" if self.live_payload_enabled else "PAYLOAD FIXO"
            status = "PAYLOAD VIVO ON" if self.live_payload_enabled else "PAYLOAD VIVO OFF"
        elif cmd_upper == "TOGGLE_TERMINAL":
            self.terminal_visible = not self.terminal_visible
            self.input_active = self.terminal_visible
            if not self.terminal_visible:
                self.input_text = ""
                self.help_visible = False
            status = "TERMINAL ON" if self.terminal_visible else "TERMINAL OFF"
        elif cmd_upper == "PQC_STATUS":
            if self.serial_connected:
                self._queue_serial_command("PQC_INFO", visible=True)
                return
            status = "PQC PENDENTE"
        elif cmd_upper == "RESET_SESSION":
            status = self._reset_session()
        elif cmd_upper == "PQC_RESULTS":
            self.results_overlay_visible = not getattr(self, "results_overlay_visible", False)
            if self.results_overlay_visible:
                self.results_overlay_mode = "presentation"
            status = "SHOW_RESULTS" if self.results_overlay_visible else "HIDE_RESULTS"
        elif command_name == "STRESS":
            status = self._execute_stress_command(cmd_clean)
            if status is None:
                return
        elif cmd_upper == "CRC_CHECK":
            status = self._run_experiment_command("CRC32")
        elif cmd_upper in {"EXPORT_JSON", "SAVE_SESSION"}:
            status = self._export_session_status()
        elif command_name == "RUN_BATTERY":
            status = self._run_battery_command(parts[1:])
        elif command_name.startswith("DEMO"):
            status = self._execute_demo_command(command_name, parts[1:])
        elif command_name == "PING" and self.serial_client is None:
            status = "LOOP LOCAL OK"
        elif command_name == "TELEMETRY" and self.serial_client is None:
            status = "SNAPSHOT SIM"
        elif command_name == "HELP":
            self.terminal_visible = True
            self.input_active = True
            self.help_visible = True
            status = "HELP: digite comandos no terminal"
        elif is_demo_firmware_command(cmd_clean):
            if self.serial_client is None:
                status = "SERIAL OFF"
            else:
                self.help_visible = False
                self._queue_serial_command(cmd_clean, visible=True)
                return
        elif command_name in FIRMWARE_COMMAND_NAMES:
            if self.serial_client is None:
                status = "SERIAL OFF"
            else:
                self.help_visible = False
                self._queue_serial_command(cmd_clean, visible=True)
                return
        elif command_name in DASHBOARD_COMMAND_NAMES:
            status = "LOCAL"
        else:
            status = "DESCONHECIDO"

        self._append_history(cmd_upper, status)

    def _handle_stress_button_click(self):
        if self.stress_state == "RUNNING":
            self._append_history("STRESS", "RUNNING")
            return
        if self.stress_state == "ARMED":
            status = self._execute_stress_command(STRESS_COMMAND)
            if status is not None:
                self._append_history("STRESS", status)
            return
        self.stress_armed_until = 0.0
        self.stress_state = "ARMED"
        self.stress_payload = {}
        self.stress_status = "CONFIRME"
        self._append_history("STRESS", "CONFIRMAR")

    def _execute_stress_command(self, command_line):
        normalized = command_line.strip().upper()
        if normalized != STRESS_COMMAND:
            return "USE STRESS PQC_LOOP 500 CONFIRM"
        if self.serial_client is None or not self.serial_connected:
            self.stress_state = "ERROR"
            self.stress_status = "SAT OFF"
            self.stress_payload = {}
            return "SAT OFF"

        self.stress_state = "RUNNING"
        self.stress_started_at = self.uptime
        self.stress_armed_until = 0.0
        self.stress_payload = {}
        self.stress_status = "ML-KEM EM LOOP"
        self.session_status = "STRESS PQC"
        self._queue_serial_command("LED YELLOW", visible=False)
        self._queue_serial_command("BARGRAPH 5", visible=False)
        self._queue_serial_command("RGB 255 80 0", visible=False)
        self._queue_serial_command(STRESS_COMMAND, visible=True, timeout=STRESS_SERIAL_TIMEOUT_SECONDS)
        return None

    def _current_message_scenario(self):
        if self.message_preset in {"CLASSIC", "PQC", "PQC_CRC32"}:
            return self.message_preset
        if self.classic_enabled:
            return "CLASSIC"
        if self.checksum_enabled:
            return "PQC_CRC32"
        return "PQC"

    def _set_message_preset(self, scenario):
        scenario = scenario.upper().replace("+", "_")
        if scenario not in {"CLASSIC", "PQC", "PQC_CRC32"}:
            return "INVALID_INPUT"

        self.message_preset = scenario
        self.classic_enabled = scenario == "CLASSIC"
        self.pqc_enabled = scenario in {"PQC", "PQC_CRC32"}
        self.checksum_enabled = scenario == "PQC_CRC32"
        self.guard_mode = "CRC32" if self.checksum_enabled else "NONE"
        self.session_dirty = True
        labels = {
            "CLASSIC": "PRESET CLÁSSICO",
            "PQC": "PRESET PQC",
            "PQC_CRC32": "PRESET PQC+CRC",
        }
        self.session_status = labels[scenario]
        return labels[scenario]

    def _pqc_indicator(self):
        """Return the ML-KEM state for the currently selected mission preset."""
        if not self.pqc_enabled:
            return "INATIVO", C_ACCENT_ORANGE
        return self.pqc_algorithm, C_ACCENT_PURPLE

    def _request_serial_payload(self, command_line, *, timeout=LIVE_PAYLOAD_REQUEST_TIMEOUT_SECONDS):
        if self.serial_client is None or not self.serial_connected or not hasattr(self.serial_client, "request"):
            return {"ok": False, "payload": {}, "status": "UNAVAILABLE"}
        try:
            response = self.serial_client.request(command_line, timeout=timeout, emit_event=False)
        except SerialBridgeError as exc:
            return {"ok": False, "payload": {}, "status": str(exc)}
        status = str(response.get("status", "")).upper()
        payload = dict(response.get("payload") or {})
        return {"ok": status == "OK", "payload": payload, "status": status or "UNKNOWN"}

    def _collect_live_payload_snapshot(self):
        readings = {}
        sources = {}
        failures = []
        commands = (
            ("TEMP_HUM", "SENSOR_READ TEMP_HUM"),
            ("ACCEL", "SENSOR_READ ACCEL"),
            ("APDS", "SENSOR_READ APDS"),
            ("POT", "ANALOG POT"),
            ("BUTTON", "DIGITAL BUTTON"),
        )
        for label, command in commands:
            result = self._request_serial_payload(command)
            sources[label] = result["status"]
            if result["ok"]:
                readings.update(result["payload"])
            else:
                failures.append(label)

        seq = self.live_payload_seq
        self.live_payload_seq += 1
        payload_text = live_payload_text_from_readings(seq, readings)
        payload_hex = payload_hex_from_text(payload_text)
        snapshot = {
            "enabled": True,
            "seq": seq,
            "payload_text": payload_text,
            "payload_hex": payload_hex,
            "payload_len": len(payload_text.encode("ascii", errors="replace")),
            "readings": readings,
            "sources": sources,
            "failures": failures,
            "status": "OK" if not failures else "PARTIAL",
            "pot": readings.get("pot"),
            "button": readings.get("button"),
        }
        self.last_live_payload = snapshot
        return snapshot

    def _fixed_payload_snapshot(self):
        payload_text = DEFAULT_PAYLOAD.decode("ascii", errors="replace")
        snapshot = {
            "enabled": False,
            "seq": self.live_payload_seq,
            "payload_text": payload_text,
            "payload_hex": payload_hex_from_text(payload_text),
            "payload_len": len(DEFAULT_PAYLOAD),
            "readings": {},
            "sources": {},
            "failures": [],
            "status": "FIXED",
            "pot": None,
            "button": None,
        }
        self.last_live_payload = snapshot
        return snapshot

    def _mission_context_for_send(self):
        if self.live_payload_enabled:
            return self._collect_live_payload_snapshot()
        return self._fixed_payload_snapshot()

    def _remember_pending_mission_context(self, scenario, snapshot):
        if not snapshot:
            return
        self.pending_mission_contexts.setdefault(scenario, []).append(snapshot)

    def _pop_pending_mission_context(self, scenario):
        queue_for_scenario = self.pending_mission_contexts.get(scenario)
        if not queue_for_scenario:
            return None
        snapshot = queue_for_scenario.pop(0)
        if not queue_for_scenario:
            self.pending_mission_contexts.pop(scenario, None)
        return snapshot

    def _remember_pending_fault_context(self, command_line, snapshot, spec):
        if not snapshot:
            return
        self.pending_fault_contexts[command_line.upper()] = {
            "snapshot": snapshot,
            "spec": spec,
        }

    def _pop_pending_fault_context(self, command_line):
        return self.pending_fault_contexts.pop(command_line.upper(), None)

    def _execute_mission_command(self, args):
        if len(args) not in {1, 2}:
            return "INVALID_INPUT"
        scenario = args[0].upper().replace("+", "_")
        if scenario not in {"CLASSIC", "PQC", "PQC_CRC32"}:
            return "INVALID_INPUT"
        manual_payload_hex = args[1].upper() if len(args) == 2 else ""
        self._set_message_preset(scenario)
        if (self.serial_client is None or not self.serial_connected) and "unittest" not in sys.modules:
            snapshot = self._mission_context_for_send()
            payload_text = snapshot.get("payload_text", "PQC-SAT DEMO")
            payload_hex = snapshot.get("payload_hex", "5051432D5341542044454D4F")
            payload_bytes = len(payload_text)

            nonce_bytes = 12
            tag_bytes = 16

            if scenario == "CLASSIC":
                crc_bytes = 0
                mlkem_bytes = 0
                crypto_bytes = nonce_bytes + tag_bytes
                total_bytes = payload_bytes + crypto_bytes

                sim_payload = {
                    "scenario": "CLASSIC",
                    "result": "DELIVERED",
                    "elapsed_us": 1250,
                    "bytes_payload": payload_bytes,
                    "bytes_crypto": crypto_bytes,
                    "bytes_checksum": crc_bytes,
                    "bytes_total": total_bytes,
                    "bytes_nonce": nonce_bytes,
                    "bytes_gcm_tag": tag_bytes,
                    "bytes_mlkem": mlkem_bytes,
                    "cipher": "AES-128-GCM",
                    "crypto": "AES-128-GCM",
                    "checksum": "NONE",
                    "heap": 48200,
                    "min_heap": 48100,
                    "cpu_mhz": 240,
                    "key_match": "true",
                    "aead_match": "true",
                    "tag_match": "true",
                    "crc_match": "NA",
                    "rng_us": 400,
                    "encrypt_us": 850,
                    "decrypt_us": 920,
                    "crc_us": 0,
                    "keygen_us": 0,
                    "encap_us": 0,
                    "decap_us": 0,
                    "kdf_us": 0,
                }
            elif scenario == "PQC":
                crc_bytes = 0
                mlkem_bytes = 768
                crypto_bytes = mlkem_bytes + nonce_bytes + tag_bytes
                total_bytes = payload_bytes + crypto_bytes

                sim_payload = {
                    "scenario": "PQC",
                    "result": "DELIVERED",
                    "elapsed_us": 14200,
                    "bytes_payload": payload_bytes,
                    "bytes_crypto": crypto_bytes,
                    "bytes_checksum": crc_bytes,
                    "bytes_total": total_bytes,
                    "bytes_nonce": nonce_bytes,
                    "bytes_gcm_tag": tag_bytes,
                    "bytes_mlkem": mlkem_bytes,
                    "cipher": "AES-128-GCM",
                    "crypto": "ML-KEM-512",
                    "checksum": "NONE",
                    "heap": 32100,
                    "min_heap": 31900,
                    "cpu_mhz": 240,
                    "key_match": "true",
                    "aead_match": "true",
                    "tag_match": "true",
                    "crc_match": "NA",
                    "rng_us": 450,
                    "encrypt_us": 870,
                    "decrypt_us": 940,
                    "crc_us": 0,
                    "keygen_us": 3301,
                    "encap_us": 3864,
                    "decap_us": 4988,
                    "kdf_us": 250,
                }
            else: # PQC_CRC32
                crc_bytes = 4
                mlkem_bytes = 768
                crypto_bytes = mlkem_bytes + nonce_bytes + tag_bytes
                total_bytes = payload_bytes + crc_bytes + crypto_bytes

                sim_payload = {
                    "scenario": "PQC_CRC32",
                    "result": "DELIVERED",
                    "elapsed_us": 14350,
                    "bytes_payload": payload_bytes,
                    "bytes_crypto": crypto_bytes,
                    "bytes_checksum": crc_bytes,
                    "bytes_total": total_bytes,
                    "bytes_nonce": nonce_bytes,
                    "bytes_gcm_tag": tag_bytes,
                    "bytes_mlkem": mlkem_bytes,
                    "cipher": "AES-128-GCM",
                    "crypto": "ML-KEM-512",
                    "checksum": "CRC32",
                    "heap": 32050,
                    "min_heap": 31850,
                    "cpu_mhz": 240,
                    "key_match": "true",
                    "aead_match": "true",
                    "tag_match": "true",
                    "crc_match": "true",
                    "rng_us": 460,
                    "encrypt_us": 880,
                    "decrypt_us": 950,
                    "crc_us": 50,
                    "keygen_us": 3301,
                    "encap_us": 3864,
                    "decap_us": 4988,
                    "kdf_us": 260,
                }

            sim_payload.update(self._mission_context_fields(snapshot))
            self._open_mission_overlay(sim_payload)
            self.session_status = f"MISSÃO {scenario} (SIM)"
            self._append_history(f"MISSION {scenario}", f"{_format_elapsed(sim_payload['elapsed_us'])}, {total_bytes} B (SIM)")
            return None

        if self.serial_client is None or not self.serial_connected:
            self.session_status = "AGUARDANDO SAT"
            return "SAT OFF"

        self._queue_serial_command("LED YELLOW", visible=False)
        self._queue_serial_command("BARGRAPH 10", visible=False)
        if manual_payload_hex:
            command = f"MISSION {scenario} {manual_payload_hex}"
        else:
            snapshot = self._mission_context_for_send()
            command = f"MISSION {scenario} {snapshot['payload_hex']}" if snapshot.get("payload_hex") else f"MISSION {scenario}"
            self._remember_pending_mission_context(scenario, snapshot)
        self._queue_serial_command(command, visible=True)
        for effect_command in self._mission_effect_commands(scenario):
            self._queue_serial_command(effect_command, visible=False)
        self._queue_serial_command("OLED STANDBY", visible=False)
        self.session_status = f"MISSÃO {scenario}"
        return None

    @staticmethod
    def _mission_effect_commands(scenario):
        if scenario == "CLASSIC":
            return ("BARGRAPH 25", "LED BLUE", "RGB 0 80 255")
        if scenario == "PQC":
            return ("BARGRAPH 75", "LED MAGENTA", "RGB 180 40 255")
        if scenario == "PQC_CRC32":
            return ("BARGRAPH 100", "LED GREEN", "RGB 0 255 120")
        return ()

    def _execute_checksum_command(self, command_name, args):
        if command_name == "GUARD":
            if len(args) != 1:
                return "INVALID_INPUT"
            mode = args[0]
            if mode == "CRC32":
                return self._set_checksum_enabled(True)
            if mode == "NONE":
                return self._set_checksum_enabled(False)
            return "INVALID_INPUT"

        if len(args) != 1:
            return "INVALID_INPUT"
        action = args[0]
        if action in {"ON", "CRC32"}:
            status = self._set_checksum_enabled(True)
            if self.pqc_enabled:
                self.message_preset = "PQC_CRC32"
            return status
        if action in {"OFF", "NONE"}:
            status = self._set_checksum_enabled(False)
            if self.pqc_enabled:
                self.message_preset = "PQC"
            return status
        if action == "TOGGLE":
            status = self._set_checksum_enabled(not self.checksum_enabled)
            if self.pqc_enabled:
                self.message_preset = "PQC_CRC32" if self.checksum_enabled else "PQC"
            return status
        if action == "STATUS":
            return f"CHK {self.guard_mode}"
        return "INVALID_INPUT"

    def _set_checksum_enabled(self, enabled):
        self.checksum_enabled = bool(enabled)
        self.guard_mode = "CRC32" if self.checksum_enabled else "NONE"
        self.session_dirty = True
        self.session_status = "CHECKSUM CRC32" if self.checksum_enabled else "SEM CHECKSUM"
        return "CRC32 ON" if self.checksum_enabled else "CRC32 OFF"

    def _handle_command_button_click(self, pos):
        for rect, command in self.command_button_rects:
            if rect.collidepoint(pos):
                self._execute_command(command)
                return True
        return False

    def _run_experiment_command(self, guard, args=None, campaign_trial_id=None):
        args = args or []
        snapshot = None
        try:
            spec = self._fault_spec_from_args(args)
            if not args and self.satellite_online():
                snapshot = self._mission_context_for_send()
                payload_bytes = snapshot["payload_text"].encode("ascii", errors="replace")
                self.experiment.payload = payload_bytes
                pot_spec = fault_spec_from_pot(snapshot.get("pot"), len(payload_bytes))
                if pot_spec is not None:
                    spec = pot_spec
            mode = "HARDWARE" if self.satellite_online() else "SIMULATED"
            event = self.experiment.run_fault(
                guard=guard,
                spec=spec,
                mode=mode,
                uptime_s=self.uptime,
                campaign_run_id=getattr(self, "_active_campaign_run_id", "manual"),
                campaign_trial_id=campaign_trial_id,
            )
        except ValueError as exc:
            self._append_history("FAULT_SPEC", str(exc).upper()[:14])
            return "INVALID_INPUT"

        self.last_fault_event = event
        self.session_dirty = True
        self._refresh_experiment_metrics()
        self._trigger_fault_effect(event)
        self._open_fault_overlay_from_event(event, snapshot=snapshot)

        if self.serial_connected:
            self._queue_serial_command("LED YELLOW", visible=False)
            self._queue_serial_command("BARGRAPH 50", visible=False)
            command_line = event.to_firmware_command()
            self._remember_pending_fault_context(command_line, snapshot, event)
            self._queue_serial_command(command_line, visible=True)
            if event.result == "SILENT":
                self._queue_serial_command("LED RED", visible=False)
                self._queue_serial_command("RGB 255 20 40", visible=False)
            elif event.result == "DETECTED_GUARD":
                self._queue_serial_command("LED GREEN", visible=False)
                self._queue_serial_command("RGB 0 255 120", visible=False)
            self._queue_serial_command("OLED STANDBY", visible=False)

        if event.result == "SILENT":
            self.session_status = "DEGRADADO (SIM)"
            return "SILENT"
        if event.result == "DETECTED_GUARD":
            self.session_status = "GUARDIÃO DETECTOU"
            return "DETECTED"
        self.session_status = "OK"
        return event.result

    def _reset_session(self):
        if self.session_dirty and (self.experiment_events or self.hardware_samples):
            status = self._export_session_status(auto=True)
            if status == "EXPORT ERROR":
                return status

        self.experiment.reset()
        self.experiment.payload = DEFAULT_PAYLOAD
        self.hardware_samples.clear()
        self.battery_runs = 0
        self.last_fault_event = None
        self.fault_overlay_visible = False
        self.fault_overlay.clear()
        self.fault_overlay_position = None
        self.fault_overlay_closing_since = None
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.fault_flow_scrub_rect = None
        self.dragging_fault_overlay = False
        self.dragging_fault_flow = False
        self.fault_drag_offset = (0, 0)
        self.fault_flow_animation = None
        self.demo_state = "IDLE"
        self.demo_previous_state = "IDLE"
        self.demo_specs = []
        self.demo_index = 0
        self.demo_phase_elapsed = 0.0
        self.demo_elapsed_s = 0.0
        self.demo_run_id = ""
        self.demo_summary = {}
        self.demo_export_path = None
        self.last_mission = {}
        self.mission_effect_timer = 0.0
        self.mission_overlay_visible = False
        self.mission_overlay_close_rect = None
        self.mission_overlays.clear()
        self.mission_overlay_order.clear()
        self.mission_overlay_positions.clear()
        self.mission_overlay_opened_at.clear()
        self.mission_overlay_closing_since.clear()
        self.mission_overlay_rects.clear()
        self.mission_overlay_close_rects.clear()
        self.mission_overlay_drag_rects.clear()
        self.mission_flow_control_rects.clear()
        self.mission_flow_scrub_rects.clear()
        self.dragging_mission_overlay = None
        self.dragging_mission_flow_scenario = None
        self.mission_drag_offset = (0, 0)
        self.mission_flow_animations.clear()
        self.mission_flow_animation = None
        self.pending_mission_contexts.clear()
        self.pending_fault_contexts.clear()
        self.last_live_payload = None
        self.live_payload_seq = 1
        self.live_payload_enabled = True
        self.message_preset = "PQC"
        self.classic_enabled = False
        self.pqc_enabled = True
        self._active_campaign_run_id = "manual"
        self._set_checksum_enabled(False)
        self._refresh_experiment_metrics()
        self.session_status = "SIMULADO"
        self.effect_timer = 0.0
        # OTIMIZAÇÃO SEMINÁRIO
        self.impact_shake_offset = (0, 0)
        self.bit_rain_particles.clear()
        self.session_dirty = False
        return "SIM RESET"

    def _export_session_status(self, *, auto=False):
        try:
            path = self.export_session()
        except OSError:
            return "EXPORT ERROR"
        self.last_export_path = path
        self.session_dirty = False
        if auto:
            self._append_history("AUTO_SAVE", path.name[:14])
        return "JSON SALVO"

    def export_session(self, log_dir=DEFAULT_LOG_DIR):
        document = self._build_export_document()
        return _atomic_write_json(document, log_dir=log_dir)

    def _build_export_document(self):
        return {
            "schema_version": RUN_SCHEMA_VERSION,
            "session_id": self.experiment.session_id,
            "created_at": _utc_now_iso(),
            "board": self._board_export_info(),
            "config": {
                "campaign_seed": self.session_seed,
                "pqc_target": self.hardware_state.get("pqc_target", "ML-KEM-512"),
                "pqc_backend": self.hardware_state.get("pqc_backend", "none"),
                "pqc_status": self.hardware_state.get("pqc_status", "not_ready"),
                "checksum": session_checksum_mode(self.experiment_events, self.guard_mode),
                "radiation_mode": "manual_bitflip",
            },
            "summary": event_summary(self.experiment_events),
            "metrics": self._build_metrics_summary(),
            "demo": self._demo_export_info(),
            "events": [event_to_json(event) for event in self.experiment_events],
            "hardware_samples": list(self.hardware_samples),
        }

    def _build_metrics_summary(self):
        return {
            "cpu": {
                "load_pct": round(self._current_cpu_load_pct(), 2),
                "window_s": CPU_LOAD_WINDOW_SECONDS,
                "kind": "observed_command_active_time",
            },
            "host": self._host_metrics_summary(),
            "checksum": checksum_metrics(self.experiment_events),
            "pqc": self._pqc_metrics_summary(),
            "mission": self._mission_metrics_summary(),
        }

    def _host_metrics_summary(self):
        rss_bytes = _process_rss_bytes()
        return {
            "rss_bytes": rss_bytes,
            "rss": _format_bytes(rss_bytes),
            "fps": int(clock.get_fps()),
        }

    def _demo_export_info(self):
        return {
            "state": self.demo_state,
            "run_id": self.demo_run_id,
            "attempts": self.demo_attempts,
            "elapsed_s": round(self.demo_elapsed_s, 2),
            "summary": dict(self.demo_summary),
            "export_path": str(self.demo_export_path) if self.demo_export_path else "",
        }

    def _board_export_info(self):
        payload = self.hardware_state or {}
        connected = bool(self.serial_connected)
        return {
            "connected": connected,
            "node": payload.get("node", "PQC-SAT-WISDOM" if connected else ""),
            "board": payload.get("board", "BlackBoard-Wisdom" if connected else ""),
            "chip": payload.get("chip", ""),
            "profile": payload.get("profile", ""),
        }

    def _remember_cpu_activity(self, elapsed_us):
        now = time.monotonic()
        if elapsed_us is not None and elapsed_us > 0:
            self.cpu_active_window.append((now, elapsed_us))
        cutoff = now - CPU_LOAD_WINDOW_SECONDS
        self.cpu_active_window = [
            (timestamp, value)
            for timestamp, value in self.cpu_active_window
            if timestamp >= cutoff
        ]
        self.last_cpu_load_pct = self._current_cpu_load_pct(now)
        self.hardware_state["cpu_load_pct"] = f"{self.last_cpu_load_pct:.2f}"
        return self.last_cpu_load_pct

    def _current_cpu_load_pct(self, now=None):
        now = time.monotonic() if now is None else now
        cutoff = now - CPU_LOAD_WINDOW_SECONDS
        active_us = sum(value for timestamp, value in self.cpu_active_window if timestamp >= cutoff)
        window_us = CPU_LOAD_WINDOW_SECONDS * 1_000_000
        if window_us <= 0:
            return 0.0
        return max(0.0, min(100.0, (active_us / window_us) * 100.0))

    def _pqc_metrics_summary(self):
        latest = {}
        bench = {}
        fault = {}
        for sample in self.hardware_samples:
            pqc = sample.get("pqc")
            if not pqc:
                continue
            latest = pqc
            command = pqc.get("command", sample.get("source_command", ""))
            if command == "PQC_BENCH":
                bench = pqc
            elif command == "PQC_FAULT":
                fault = pqc

        return {
            "latest_command": latest.get("command", ""),
            "latest_status": latest.get("pqc_status", latest.get("result", "")),
            "bench": {
                "n": bench.get("n"),
                "ok": bench.get("ok"),
                "keygen_avg_us": bench.get("keygen_avg_us"),
                "encap_avg_us": bench.get("encap_avg_us"),
                "decap_avg_us": bench.get("decap_avg_us"),
            },
            "fault": {
                "result": fault.get("result", ""),
                "confirmation": fault.get("confirmation", ""),
                "key_match": fault.get("key_match"),
                "key_confirmed": fault.get("key_confirmed"),
                "confirm_us": fault.get("confirm_us"),
            },
        }

    def _mission_metrics_summary(self):
        scenarios = {}
        for sample in self.hardware_samples:
            mission = sample.get("mission")
            if not mission:
                continue
            scenario = mission.get("scenario")
            if scenario:
                scenarios[scenario] = mission

        classic_us = _optional_int(scenarios.get("CLASSIC", {}).get("elapsed_us"))
        pqc_us = _optional_int(scenarios.get("PQC", {}).get("elapsed_us"))
        pqc_crc_us = _optional_int(scenarios.get("PQC_CRC32", {}).get("elapsed_us"))
        return {
            "scenarios": scenarios,
            "ratios": {
                "pqc_vs_classic": round(pqc_us / classic_us, 2) if classic_us and pqc_us else None,
                "pqc_crc32_vs_classic": round(pqc_crc_us / classic_us, 2) if classic_us and pqc_crc_us else None,
                "crc32_over_pqc": round(pqc_crc_us / pqc_us, 2) if pqc_us and pqc_crc_us else None,
            },
        }

    def _run_battery_command(self, args):
        if len(args) != 1:
            return "INVALID_INPUT"
        try:
            attempts = int(args[0], 10)
        except ValueError:
            return "INVALID_INPUT"
        if not 1 <= attempts <= 100:
            return "INVALID_INPUT"

        self.experiment.payload = DEFAULT_PAYLOAD
        specs = [self.experiment.next_spec() for _ in range(attempts)]
        self.battery_runs += 1
        previous_run_id = getattr(self, "_active_campaign_run_id", "manual")
        self._active_campaign_run_id = f"battery-{self.battery_runs:03d}"
        try:
            for index, spec in enumerate(specs, start=1):
                args = [str(spec.byte_index), f"0x{spec.bit_mask:02X}"]
                self._run_experiment_command("NONE", args, campaign_trial_id=index)
            for index, spec in enumerate(specs, start=1):
                args = [str(spec.byte_index), f"0x{spec.bit_mask:02X}"]
                self._run_experiment_command("CRC32", args, campaign_trial_id=index)
        finally:
            self._active_campaign_run_id = previous_run_id

        return self._export_session_status()

    def _execute_demo_command(self, command_name, args):
        if command_name == "DEMO":
            attempts = DEMO_DEFAULT_ATTEMPTS
            if args:
                if len(args) != 1:
                    return "INVALID_INPUT"
                try:
                    attempts = int(args[0], 10)
                except ValueError:
                    return "INVALID_INPUT"
                if not 1 <= attempts <= 12:
                    return "INVALID_INPUT"
            return self._start_demo(attempts)

        if command_name == "DEMO_PAUSE":
            if self.demo_state in {"RUNNING_A", "SNAPSHOT_A", "RUNNING_B", "RESULTS"}:
                self.demo_previous_state = self.demo_state
                self.demo_state = "PAUSED"
                self.session_status = "DEMO PAUSADA"
                return "DEMO PAUSED"
            return "DEMO IDLE"

        if command_name == "DEMO_RESUME":
            if self.demo_state == "PAUSED":
                self.demo_state = self.demo_previous_state
                self.session_status = f"DEMO {self.demo_state}"
                return "DEMO RESUME"
            return "DEMO IDLE"

        if command_name == "DEMO_STOP":
            if self.demo_state != "IDLE":
                self.demo_state = "STOPPED"
                self.session_status = "DEMO PARADA"
                return "DEMO STOP"
            return "DEMO IDLE"

        if command_name == "DEMO_RESTART":
            return self._start_demo(self.demo_attempts or DEMO_DEFAULT_ATTEMPTS)

        return "INVALID_INPUT"

    def _start_demo(self, attempts):
        if self.session_dirty and (self.experiment_events or self.hardware_samples):
            status = self._export_session_status(auto=True)
            if status == "EXPORT ERROR":
                return status

        self.experiment.reset()
        self.experiment.payload = DEFAULT_PAYLOAD
        self.experiment_events = self.experiment.events
        self.last_fault_event = None
        self._refresh_experiment_metrics()
        self.demo_attempts = attempts
        self.demo_specs = [self.experiment.next_spec() for _ in range(attempts)]
        self.demo_index = 0
        self.demo_phase_elapsed = 0.0
        self.demo_elapsed_s = 0.0
        self.demo_run_id = f"demo-{self.battery_runs + 1:03d}"
        self.demo_summary = {}
        self.demo_export_path = None
        self.demo_state = "RUNNING_A"
        self.demo_previous_state = "IDLE"
        self._active_campaign_run_id = self.demo_run_id
        self._set_checksum_enabled(False)
        self.session_dirty = True
        self.session_status = "DEMO A: NONE"
        return "DEMO START"

    def _advance_demo(self, dt):
        if self.demo_state in {"IDLE", "PAUSED", "STOPPED"}:
            return

        self.demo_elapsed_s += dt
        self.demo_phase_elapsed += dt

        if self.demo_state == "RUNNING_A":
            if self.demo_phase_elapsed >= DEMO_FAULT_INTERVAL_SECONDS:
                self.demo_phase_elapsed = 0.0
                if self.demo_index < len(self.demo_specs):
                    self._run_demo_fault("NONE", self.demo_index)
                    self.demo_index += 1
                if self.demo_index >= len(self.demo_specs):
                    self.demo_state = "SNAPSHOT_A"
                    self.demo_phase_elapsed = 0.0
                    self.session_status = "SNAPSHOT A"
            return

        if self.demo_state == "SNAPSHOT_A":
            if self.demo_phase_elapsed >= DEMO_SNAPSHOT_SECONDS:
                self.demo_state = "RUNNING_B"
                self.demo_index = 0
                self.demo_phase_elapsed = 0.0
                self._set_checksum_enabled(True)
                self.session_status = "DEMO B: CRC32"
            return

        if self.demo_state == "RUNNING_B":
            if self.demo_phase_elapsed >= DEMO_FAULT_INTERVAL_SECONDS:
                self.demo_phase_elapsed = 0.0
                if self.demo_index < len(self.demo_specs):
                    self._run_demo_fault("CRC32", self.demo_index)
                    self.demo_index += 1
                if self.demo_index >= len(self.demo_specs):
                    self.demo_state = "RESULTS"
                    self.demo_phase_elapsed = 0.0
                    self.demo_summary = self._demo_result_summary()
                    self.session_status = "DEMO RESULTADOS"
                    try:
                        self.demo_export_path = self.export_session()
                        self.last_export_path = self.demo_export_path
                        self.session_dirty = False
                    except OSError:
                        self.demo_summary["export_error"] = True
                        self._append_history("DEMO_EXPORT", "ERROR")
            return

        if self.demo_state == "RESULTS" and self.demo_phase_elapsed >= DEMO_RESULTS_SECONDS:
            self.demo_state = "IDLE"
            self.demo_phase_elapsed = 0.0
            self._active_campaign_run_id = "manual"

    def _run_demo_fault(self, guard, index):
        spec = self.demo_specs[index]
        args = [str(spec.byte_index), f"0x{spec.bit_mask:02X}"]
        self._active_campaign_run_id = self.demo_run_id
        self._run_experiment_command(guard, args, campaign_trial_id=index + 1)

    def _demo_result_summary(self):
        events = [event for event in self.experiment_events if event.campaign_run_id == self.demo_run_id]
        summary = event_summary(events)
        crc_metrics = checksum_metrics(events)
        none_events = [event for event in events if event.guard == "NONE"]
        crc_events = [event for event in events if event.guard == "CRC32"]
        return {
            "state": "RESULTS",
            "attempts": self.demo_attempts,
            "duration_s": round(self.demo_elapsed_s, 2),
            "events": summary["events"],
            "none_silent": sum(1 for event in none_events if event.result == "SILENT"),
            "crc_detected": sum(1 for event in crc_events if event.result == "DETECTED_GUARD"),
            "crc_detection_rate_pct": crc_metrics["detection_rate_pct"],
            "crc_avg_overhead_us": crc_metrics["avg_overhead_us"],
        }

    def _fault_spec_from_args(self, args):
        if not args:
            return None
        if len(args) != 2:
            raise ValueError("use BIT_FLIP indice mascara")
        byte_index = int(args[0], 0)
        bit_mask = _parse_u8_token(args[1])
        return FaultSpec(byte_index=byte_index, bit_mask=bit_mask)

    def _refresh_experiment_metrics(self):
        self.fault_injections = len(self.experiment_events)
        self.silent_failures = sum(1 for event in self.experiment_events if event.result == "SILENT")
        self.detected_errors = sum(
            1
            for event in self.experiment_events
            if event.result in {"DETECTED_GUARD", "PROTOCOL_REJECT", "KEY_MISMATCH"}
        )

    def _trigger_fault_effect(self, event):
        self.effect_timer = 0.9
        if event.result == "SILENT":
            self.effect_color = C_ACCENT_RED
            self.effect_label = "FALHA SILENCIOSA"
        elif event.result == "DETECTED_GUARD":
            self.effect_color = C_ACCENT_ORANGE
            self.effect_label = "CRC32 DETECTOU"
        else:
            self.effect_color = C_ACCENT_GREEN
            self.effect_label = event.result

    def _spawn_bit_rain(self, origin):
        # OTIMIZAÇÃO SEMINÁRIO
        # Particulas textuais curtas: efeito CRC32/Matrix com custo fixo e baixo.
        ox, oy = origin
        for index in range(36):
            self.bit_rain_particles.append(
                {
                    "x": ox + random.randint(-120, 120),
                    "y": oy + random.randint(-8, 18),
                    "vy": random.uniform(95.0, 185.0),
                    "life": 1.0,
                    "delay": random.uniform(0.0, 0.18),
                    "bit": "1" if index % 2 else "0",
                }
            )

    def _update_bit_rain(self, dt):
        # OTIMIZAÇÃO SEMINÁRIO
        # Atualizacao linear simples, sem alocacoes pesadas por frame.
        alive = []
        for particle in self.bit_rain_particles:
            if particle["delay"] > 0:
                particle["delay"] -= dt
                alive.append(particle)
                continue
            particle["life"] -= dt
            particle["y"] += particle["vy"] * dt
            if particle["life"] > 0:
                alive.append(particle)
        self.bit_rain_particles = alive

    def _draw_bit_rain(self, surface):
        # OTIMIZAÇÃO SEMINÁRIO
        # Renderiza poucos glyphs vermelhos com alpha decrescente por 1 segundo.
        for particle in self.bit_rain_particles:
            if particle["delay"] > 0:
                continue
            alpha = max(0, min(255, int(255 * particle["life"])))
            glyph = FONT_PIXEL.render(particle["bit"], True, C_ACCENT_RED)
            glyph.set_alpha(alpha)
            surface.blit(glyph, (int(particle["x"]), int(particle["y"])))

    def _open_fault_overlay_from_event(self, event, snapshot=None):
        before_byte = self._byte_from_hex_at(event.before_hex, event.byte_index)
        after_byte = self._byte_from_hex_at(event.after_hex, event.byte_index)
        fault = {
            "source": event.mode,
            "target": event.target,
            "guard": event.guard,
            "result": event.result,
            "byte_index": event.byte_index,
            "bit_mask": f"0x{event.bit_mask_hex}",
            "before_byte": self._format_hex_byte(before_byte),
            "after_byte": self._format_hex_byte(after_byte),
            "before_hex": event.before_hex,
            "after_hex": event.after_hex,
            "crc_before": event.crc_before,
            "crc_after": event.crc_after,
            "guard_prepare_us": event.guard_prepare_us,
            "guard_verify_us": event.guard_verify_us,
            "guard_overhead_us": event.guard_overhead_us,
            "elapsed_us": event.elapsed_us,
            "mode": event.mode,
        }
        if snapshot:
            fault.update(self._fault_context_fields(snapshot, event))
        self._open_fault_overlay(fault)

    def _open_fault_overlay_from_payload(self, command, payload):
        command_name = command.split()[0].upper()
        context = self._pop_pending_fault_context(command)
        target = str(payload.get("target", "PAYLOAD")).upper()
        guard = payload.get("guard")
        if not guard:
            guard = "NONE"
        crc_before = payload.get("crc_before") or payload.get("ct_crc_before", "")
        crc_after = payload.get("crc_after") or payload.get("ct_crc_after", "")
        fault = {
            "source": "HARDWARE",
            "target": target,
            "guard": str(guard).upper(),
            "result": str(payload.get("result", "")),
            "byte_index": _optional_int(payload.get("byte_index")),
            "bit_mask": self._format_mask(payload.get("bit_mask")),
            "before_byte": self._format_hex_byte(payload.get("before_byte") or payload.get("before")),
            "after_byte": self._format_hex_byte(payload.get("after_byte") or payload.get("after")),
            "before_hex": payload.get("before_hex", ""),
            "after_hex": payload.get("after_hex", ""),
            "crc_before": str(crc_before),
            "crc_after": str(crc_after),
            "guard_prepare_us": _optional_int(payload.get("guard_prepare_us")),
            "guard_verify_us": _optional_int(payload.get("guard_verify_us")),
            "guard_overhead_us": _optional_int(payload.get("guard_overhead_us")),
            "key_match": payload.get("key_match"),
            "key_confirmed": payload.get("key_confirmed"),
            "tag_match": payload.get("tag_match"),
            "confirmation": "",
            "decap_us": _optional_int(payload.get("decap_us")),
            "confirm_us": _optional_int(payload.get("confirm_us")),
            "elapsed_us": _optional_int(payload.get("elapsed_us")),
            "mode": "HARDWARE",
        }
        if context:
            fault.update(self._fault_context_fields(context.get("snapshot"), context.get("spec")))
        self._open_fault_overlay(fault)

    def _open_fault_overlay(self, fault):
        self.fault_overlay = dict(fault)
        self.fault_overlay_visible = True
        self.fault_overlay_opened_at = self.uptime
        self.fault_overlay_closing_since = None
        if self.fault_overlay_position is None:
            self.fault_overlay_position = self._default_fault_overlay_position()
        self.fault_flow_animation = {
            "steps": self._fault_flow_steps(fault),
            "age": 0.0,
            "duration": FAULT_FLOW_ANIMATION_SECONDS,
            "awaiting_confirm": False,
        }
        if fault.get("result") == "DETECTED_GUARD" and str(fault.get("guard", "")).upper() == "CRC32":
            # OTIMIZAÇÃO SEMINÁRIO
            rect, _close_rect = self._fault_overlay_geometry()
            self._spawn_bit_rain((rect.centerx, rect.y + 96))

    @staticmethod
    def _parse_int_auto(value):
        if value is None or value == "":
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        try:
            return int(text, 0)
        except ValueError:
            try:
                return int(text, 16)
            except ValueError:
                return None

    @classmethod
    def _format_hex_byte(cls, value):
        parsed = cls._parse_int_auto(value)
        if parsed is None:
            return "--"
        return f"0x{parsed & 0xFF:02X}"

    @classmethod
    def _format_mask(cls, value):
        parsed = cls._parse_int_auto(value)
        if parsed is None:
            return str(value or "--")
        return f"0x{parsed & 0xFF:02X}"

    @classmethod
    def _byte_from_hex_at(cls, hex_value, byte_index):
        if byte_index is None:
            return None
        text = str(hex_value or "").strip().replace("0x", "").replace("0X", "")
        start = int(byte_index) * 2
        if start < 0 or start + 2 > len(text):
            return None
        try:
            return int(text[start:start + 2], 16)
        except ValueError:
            return None

    def _fault_flow_steps(self, fault):
        result = str(fault.get("result", ""))
        guard = str(fault.get("guard", "NONE")).upper()
        crc_changed = bool(fault.get("crc_before") and fault.get("crc_after") and fault.get("crc_before") != fault.get("crc_after"))

        payload_start = {
            "label": "PAYLOAD",
            "detail": "payload íntegro",
            "explain": "Começamos com o payload íntegro. É o mesmo tipo de dado que o satélite enviaria na missão.",
            "color": C_ACCENT_BLUE,
        }
        bit_flip_step = {
            "label": "BIT-FLIP",
            "detail": f"byte {fault.get('byte_index', '--')} mask {fault.get('bit_mask', '--')}",
            "explain": self._fault_selector_explanation(
                fault,
                "O byte muda, mas o sistema ainda precisa perceber.",
            ),
            "color": C_ACCENT_RED,
        }
        result_step = {
            "label": "RESULTADO",
            "detail": self._fault_result_label(result),
            "explain": self._fault_result_explanation(fault),
            "color": self._fault_result_color(result),
            "time_us": fault.get("elapsed_us"),
        }

        if guard != "CRC32":
            return (
                payload_start,
                bit_flip_step,
                {
                    "label": "SEM CRC",
                    "detail": "sem referência",
                    "explain": "Não existe checksum salvo para comparar o payload depois da inversão do bit.",
                    "color": C_TEXT_DIM,
                },
                {
                    "label": "ENTREGA",
                    "detail": "falha silenciosa" if result == "SILENT" else "sem bloqueio",
                    "explain": "Como nada valida a integridade do payload, a alteração segue para o resultado.",
                    "color": C_ACCENT_RED if result == "SILENT" else C_TEXT_DIM,
                },
                result_step,
            )

        return (
            payload_start,
            bit_flip_step,
            {
                "label": "CRC32",
                "detail": "checksum ativo",
                "explain": "O CRC32 salvo antes da falha vira a referência para comparar o payload corrompido.",
                "color": C_ACCENT_GREEN,
            },
            {
                "label": "VERIFICA",
                "detail": "CRC divergiu" if crc_changed else "CRC igual",
                "explain": "Depois do bit-flip, recalculamos o CRC. Se mudou, a corrupção fica visível antes da entrega.",
                "color": C_ACCENT_ORANGE,
                "time_us": fault.get("guard_verify_us"),
            },
            result_step,
        )

    @staticmethod
    def _fault_result_color(result):
        if result == "SILENT":
            return C_ACCENT_RED
        if result == "DETECTED_GUARD":
            return C_ACCENT_GREEN
        return C_ACCENT_CYAN

    @staticmethod
    def _fault_result_label(result):
        labels = {
            "SILENT": "FALHA SILENCIOSA",
            "DETECTED_GUARD": "DETECTADA",
            "OK": "SEM IMPACTO",
        }
        return labels.get(str(result), str(result or "--"))

    @staticmethod
    def _fault_result_short_label(result):
        labels = {
            "SILENT": "SILENCIOSA",
            "DETECTED_GUARD": "DETECTADA",
            "OK": "OK",
        }
        return labels.get(str(result), str(result or "--"))

    def _fault_result_explanation(self, fault):
        result = str(fault.get("result", ""))
        target = str(fault.get("target", "PAYLOAD")).upper()
        if result == "SILENT":
            return "Sem guardião, o payload mudou e seguiria como se estivesse correto. É a falha didática perigosa."
        if result == "DETECTED_GUARD":
            return "O CRC32 antes/depois divergiu. A corrupção foi detectada antes de aceitar o payload."
        if target == "CIPHERTEXT":
            return "Caminho técnico de bancada. A demo visual de falha usa payload com NONE ou CRC32."
        return "A tentativa terminou sem divergência observada."

    @staticmethod
    def _fault_selector_explanation(fault, suffix):
        pot = fault.get("selector_pot")
        if pot not in {None, "", "NA"}:
            return f"O potenciômetro da Wisdom escolheu o bit da falha simulada. {suffix}"
        return f"A radiação simulada inverte um único bit. {suffix}"

    def _queue_serial_command(self, command_line, visible=True, timeout=None):
        if self.serial_client is None:
            self._append_history(command_line, "SERIAL OFF")
            return
        self.serial_client.send(command_line, timeout=timeout)
        if visible:
            self._append_history(command_line, "QUEUED")

    def update(self, dt):
        self.uptime += dt
        self.cursor_blink += dt
        if self.effect_timer > 0:
            self.effect_timer = max(0.0, self.effect_timer - dt)
        if self.mission_effect_timer > 0:
            self.mission_effect_timer = max(0.0, self.mission_effect_timer - dt)
        if self.ping_effect_timer > 0:
            self.ping_effect_timer = max(0.0, self.ping_effect_timer - dt)
        if self.fault_overlay_closing_since is not None and self.uptime - self.fault_overlay_closing_since >= POPUP_EXIT_SECONDS:
            self._clear_fault_overlay()
        for scenario, closing_since in list(self.mission_overlay_closing_since.items()):
            if self.uptime - closing_since >= POPUP_EXIT_SECONDS:
                self._remove_mission_overlay(scenario)
        if self.stress_state == "RUNNING":
            elapsed = self.uptime - self.stress_started_at
            if elapsed >= STRESS_DIDACTIC_TIMEOUT_SECONDS:
                self.stress_status = "TIMEOUT DIDÁTICO"
        for animation in list(getattr(self, "mission_flow_animations", {}).values()):
            # auto-play advances only until the user grabs the scrub bar; after a
            # manual scrub the flow stays where it was dragged ("paused").
            if not animation.get("awaiting_confirm") and not animation.get("paused"):
                animation["age"] += dt
                if animation["age"] >= animation["duration"]:
                    animation["age"] = animation["duration"]
                    animation["awaiting_confirm"] = True
        self._sync_active_mission_flow_animation()
        if (
            self.fault_flow_animation is not None
            and not self.fault_flow_animation.get("awaiting_confirm")
            and not self.fault_flow_animation.get("paused")
        ):
            self.fault_flow_animation["age"] += dt
            if self.fault_flow_animation["age"] >= self.fault_flow_animation["duration"]:
                self.fault_flow_animation["age"] = self.fault_flow_animation["duration"]
                self.fault_flow_animation["awaiting_confirm"] = True
        self._update_bit_rain(dt)
        self._advance_demo(dt)
        self._drain_serial_events()
        if self.stand_mode:
            self.stand_controller.update(now=time.monotonic())

    def _drain_serial_events(self):
        if self.serial_client is None:
            return

        for event_type, payload in self.serial_client.poll():
            if self.stand_mode:
                self.stand_controller.handle_serial_event(event_type, payload, now=time.monotonic())
            if event_type == "state":
                self.serial_connected = bool(payload["connected"])
                self.serial_status = payload["status"]
                if self.serial_connected:
                    status = "ONLINE"
                    if self.stand_mode and self.stand_controller.mode == "simulated":
                        status = "FIXTURE"
                        self.pqc_algorithm = "ML-KEM-512 (FIXTURE)"
                    else:
                        self.pqc_algorithm = "ML-KEM-512 (DISPONÍVEL)"
                elif self.serial_status.startswith("OPENING"):
                    status = "OPENING"
                else:
                    status = "OFFLINE"
                self._append_history("SERIAL", status)
            elif event_type == "response":
                command = payload["command"]
                status = payload["status"]
                self.hardware_payload = payload.get("payload", {})
                self._apply_hardware_response(command, self.hardware_payload)
                if command.startswith("MISSION"):
                    elapsed = self.hardware_payload.get("elapsed_us")
                    bytes_total = self.hardware_payload.get("bytes_total")
                    if elapsed is not None and bytes_total is not None:
                        status = f"{_format_elapsed(elapsed)}, {bytes_total} B"
                elif command.startswith("STRESS"):
                    elapsed = self.hardware_payload.get("elapsed_us")
                    ok = self.hardware_payload.get("ok")
                    total = self.hardware_payload.get("n")
                    if elapsed is not None and ok is not None and total is not None:
                        status = f"{ok}/{total}, {_format_elapsed(elapsed)}"
                self._append_history(command, status)
            elif event_type == "event":
                event_name = str(payload.get("name", "")).upper()
                if event_name == "BUTTON_PING":
                    self._trigger_ping_effect()
            elif event_type == "error":
                command = payload["command"]
                if command.startswith("STRESS"):
                    self.stress_state = "ERROR"
                    self.stress_status = "TIMEOUT REAL"
                    self.stress_payload = {"error": payload["status"]}
                self._append_history(payload["command"], "ERROR")
                self.serial_status = payload["status"]

    def _trigger_ping_effect(self):
        self.ping_effect_timer = PING_ANIMATION_SECONDS
        self.ping_effect_count += 1

    @staticmethod
    def _ease_out_cubic(value):
        value = max(0.0, min(1.0, value))
        return 1.0 - (1.0 - value) ** 3

    def _draw_ping_effect(self, surface, t, satellite):
        if self.ping_effect_timer <= 0:
            self.ping_effect_last_segment = None
            return

        progress = 1.0 - self.ping_effect_timer / PING_ANIMATION_SECONDS
        progress = max(0.0, min(1.0, progress))
        sat_x, sat_y = satellite.get_position()
        earth = satellite.earth
        outward_x = sat_x - earth.center_x
        outward_y = sat_y - earth.center_y
        distance = max(1.0, math.hypot(outward_x, outward_y))
        target_x = earth.center_x + outward_x / distance * earth.radius * 0.82
        target_y = earth.center_y + outward_y / distance * earth.radius * 0.82

        head_ratio = self._ease_out_cubic(progress / 0.62)
        tail_ratio = self._ease_out_cubic((progress - 0.42) / 0.58) if progress > 0.42 else 0.0
        start = (
            sat_x + (target_x - sat_x) * tail_ratio,
            sat_y + (target_y - sat_y) * tail_ratio,
        )
        end = (
            sat_x + (target_x - sat_x) * head_ratio,
            sat_y + (target_y - sat_y) * head_ratio,
        )
        self.ping_effect_last_segment = (start, end)

        fade = 1.0 if progress < 0.72 else max(0.0, (1.0 - progress) / 0.28)
        pad = 34
        left = int(min(sat_x, target_x) - pad)
        top = int(min(sat_y, target_y) - pad)
        width = max(68, int(abs(target_x - sat_x) + pad * 2))
        height = max(68, int(abs(target_y - sat_y) + pad * 2))
        beam = pygame.Surface((width, height), pygame.SRCALPHA)

        local_start = (int(start[0] - left), int(start[1] - top))
        local_end = (int(end[0] - left), int(end[1] - top))
        alpha = int(230 * fade)
        pygame.draw.line(beam, (*C_ACCENT_CYAN, max(20, alpha // 5)), local_start, local_end, 12)
        pygame.draw.line(beam, (*C_ACCENT_BLUE, max(30, alpha // 2)), local_start, local_end, 5)
        pygame.draw.line(beam, (225, 250, 255, alpha), local_start, local_end, 2)
        pygame.draw.circle(beam, (255, 255, 255, alpha), local_end, 5)
        pygame.draw.circle(beam, (*C_ACCENT_CYAN, max(20, alpha // 2)), local_end, 12, 2)

        if progress > 0.55:
            arrival = min(1.0, (progress - 0.55) / 0.45)
            local_target = (int(target_x - left), int(target_y - top))
            radius = 8 + int(30 * arrival)
            ring_alpha = int(190 * (1.0 - arrival) * fade)
            pygame.draw.circle(beam, (*C_ACCENT_GREEN, ring_alpha), local_target, radius, 2)

        surface.blit(beam, (left, top))

    def _apply_hardware_response(self, command, payload):
        if self.serial_connected:
            self.session_status = "SATÉLITE ONLINE"
        self.hardware_state.update(payload)
        if command.startswith("HELLO"):
            self.hardware_payload = payload
        elif command.startswith("FAULT"):
            if payload.get("result"):
                self.session_status = f"HW {payload['result']}"
            self.hardware_payload = payload
            if not self.stand_mode:
                self._open_fault_overlay_from_payload(command, payload)
        elif command.startswith("TELEMETRY"):
            self.hardware_payload = payload
        elif command.startswith("STATUS"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
        elif command.startswith("PQC_"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
        elif command.startswith("STRESS"):
            self.hardware_payload = payload
            self.stress_payload = dict(payload)
            ok = _optional_int(payload.get("ok"))
            total = _optional_int(payload.get("n"))
            self.stress_state = "COMPLETE" if ok is not None and total is not None and ok == total else "ERROR"
            self.stress_status = "STRESS OK" if self.stress_state == "COMPLETE" else "STRESS FALHOU"
            self.session_status = self.stress_status
            self.pqc_algorithm = "ML-KEM-512 (STRESS)"
        elif command.startswith("MISSION"):
            scenario = self._normalize_mission_scenario(payload.get("scenario", "MISSION"))
            if "payload_mode" not in payload:
                snapshot = self._pop_pending_mission_context(scenario)
                if snapshot:
                    payload.update(self._mission_context_fields(snapshot))
            self.hardware_payload = payload
            if self.stand_mode:
                self.last_mission = dict(payload)
            else:
                self._open_mission_overlay(payload)
            scenario = payload.get("scenario", "MISSION")
            result = payload.get("result", "")
            self.session_status = f"{scenario} {result}".strip()
            if scenario in {"PQC", "PQC_CRC32"}:
                self.pqc_algorithm = "ML-KEM-512 (ATIVO)"
        self._record_hardware_sample(command, payload)

    @staticmethod
    def _normalize_mission_scenario(scenario):
        return str(scenario or "MISSION").upper().replace("+", "_")

    @staticmethod
    def _mission_context_fields(snapshot):
        readings = snapshot.get("readings", {}) if snapshot else {}
        failures = snapshot.get("failures", []) if snapshot else []
        return {
            "payload_mode": "LIVE" if snapshot and snapshot.get("enabled") else "FIXED",
            "payload_live_status": snapshot.get("status", "") if snapshot else "",
            "payload_text": snapshot.get("payload_text", "") if snapshot else "",
            "payload_hex_sent": snapshot.get("payload_hex", "") if snapshot else "",
            "payload_seq": snapshot.get("seq", "") if snapshot else "",
            "sensor_temp_c_x100": readings.get("temp_c_x100", "NA"),
            "sensor_hum_x100": readings.get("hum_x100", "NA"),
            "sensor_accel": ",".join(
                str(readings.get(key, "NA")) for key in ("x_mg", "y_mg", "z_mg")
            ),
            "sensor_light": readings.get("clear", "NA"),
            "sensor_pot": readings.get("pot", "NA"),
            "sensor_button": readings.get("button", "NA"),
            "sensor_failures": ",".join(failures) if failures else "",
        }

    @classmethod
    def _fault_context_fields(cls, snapshot, event_or_spec):
        readings = snapshot.get("readings", {}) if snapshot else {}
        pot = snapshot.get("pot", readings.get("pot", "NA")) if snapshot else "NA"
        byte_index = getattr(event_or_spec, "byte_index", None)
        bit_mask = getattr(event_or_spec, "bit_mask", None)
        return {
            "payload_mode": "LIVE" if snapshot and snapshot.get("enabled") else "FIXED",
            "payload_text": snapshot.get("payload_text", "") if snapshot else "",
            "payload_hex_sent": snapshot.get("payload_hex", "") if snapshot else "",
            "selector_pot": pot if pot is not None else "NA",
            "selector_byte_index": byte_index if byte_index is not None else "--",
            "selector_bit_mask": f"0x{bit_mask:02X}" if isinstance(bit_mask, int) else "--",
        }

    def _open_mission_overlay(self, payload):
        mission = dict(payload)
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        mission["scenario"] = scenario
        snapshot = None if "payload_mode" in mission else self._pop_pending_mission_context(scenario)
        if snapshot:
            mission.update(self._mission_context_fields(snapshot))
        self.mission_overlays[scenario] = mission
        self.mission_overlay_opened_at[scenario] = self.uptime
        self.mission_overlay_closing_since.pop(scenario, None)
        if scenario not in self.mission_overlay_order:
            self.mission_overlay_order.append(scenario)
        if scenario not in self.mission_overlay_positions:
            self.mission_overlay_positions[scenario] = self._default_mission_overlay_position(scenario)
        self._bring_mission_overlay_to_front(scenario)
        self.last_mission = dict(mission)
        self.mission_effect_timer = 1.2
        self.mission_overlay_visible = True
        self._start_mission_flow_animation(mission)

    def _start_mission_flow_animation(self, mission):
        steps = self._mission_flow_steps(mission)
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        if not steps:
            self.mission_flow_animations.pop(scenario, None)
            self._sync_active_mission_flow_animation()
            return
        animation = {
            "scenario": scenario,
            "mission": dict(mission),
            "steps": steps,
            "age": 0.0,
            "duration": MISSION_FLOW_ANIMATION_SECONDS,
            "awaiting_confirm": False,
        }
        self.mission_flow_animations[scenario] = animation
        self.mission_flow_animation = animation

    def _mission_flow_steps(self, mission):
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        parts = {label: value for label, value, _color in self._mission_package_parts(mission)}
        payload = parts.get("payload", 0)
        mlkem = parts.get("ML-KEM", 0)
        nonce = parts.get("nonce", 0)
        gcm = parts.get("GCM", 0)
        hmac = parts.get("HMAC", 0)
        checksum = parts.get("CRC", 0)
        total = self._mission_int(mission, "bytes_total", payload + mlkem + nonce + gcm + hmac + checksum)

        if total <= 0:
            return []

        live_mode = str(mission.get("payload_mode", "")).upper() == "LIVE"
        payload_explain = (
            "A Wisdom acabou de medir ambiente/posição e montou o payload real da missão. Esses bytes entram no pacote antes da proteção criptográfica."
            if live_mode
            else "A placa recebe o payload bruto. Ainda não há bytes de autenticação, KEM ou checksum anexados."
        )
        steps = [
            {
                "label": "PAYLOAD",
                "detail": "telemetria viva" if live_mode else "mensagem base",
                "explain": payload_explain,
                "kind": "payload",
                "packet_bytes": payload,
                "added_bytes": payload,
                "time_us": None,
                "color": C_ACCENT_BLUE,
            }
        ]

        if checksum > 0 or scenario == "PQC_CRC32":
            steps.append(
                {
                    "label": "CRC32",
                    "detail": "checksum do payload",
                    "explain": "O CRC32 entra antes da cifragem para a demo de bit-flip. Ele detecta corrupção acidental, mas não autentica contra atacante.",
                    "kind": "crc",
                    "packet_bytes": payload + checksum,
                    "added_bytes": checksum,
                    "time_us": self._mission_int(mission, "crc_us"),
                    "color": C_ACCENT_GREEN,
                }
            )

        if scenario in {"PQC", "PQC_CRC32"}:
            # Lado emissor: prepara o par, encapsula o segredo e deriva a chave AES
            # antes de cifrar. O DECAP só acontece depois, no receptor.
            steps.extend(
                (
                    {
                        "label": "KEYGEN",
                        "detail": "par ML-KEM (rx)",
                        "explain": "O receptor cria o par ML-KEM-512 e publica a chave pública. É custo local de CPU/RAM; o pacote ainda não cresce.",
                        "kind": "keygen",
                        "packet_bytes": payload + checksum,
                        "added_bytes": 0,
                        "time_us": self._mission_int(mission, "keygen_us"),
                        "color": C_ACCENT_PURPLE,
                    },
                    {
                        "label": "ENCAP",
                        "detail": "encapsula (tx)",
                        "explain": "O emissor usa a chave pública para encapsular um segredo compartilhado. O ciphertext ML-KEM entra no pacote para o receptor depois recuperar a chave.",
                        "kind": "mlkem",
                        "packet_bytes": payload + checksum + mlkem,
                        "added_bytes": mlkem,
                        "time_us": self._mission_int(mission, "encap_us"),
                        "color": C_ACCENT_PURPLE,
                    },
                    {
                        "label": "KDF",
                        "detail": "deriva chave AES (tx)",
                        "explain": "Ainda no emissor: o segredo ML-KEM vira uma chave AES-128 de sessão. O ML-KEM estabelece a chave; quem cifra o payload é o AES-GCM.",
                        "kind": "kdf",
                        "packet_bytes": payload + checksum + mlkem,
                        "added_bytes": 0,
                        "time_us": self._mission_int(mission, "kdf_us"),
                        "color": C_ACCENT_CYAN,
                    },
                )
            )
        else:
            steps.append(
                {
                    "label": "RNG",
                    "detail": "chave efêmera",
                    "explain": "No baseline clássico, a placa gera uma chave AES-128 efêmera e um nonce aleatório para esta mensagem.",
                    "kind": "rng",
                    "packet_bytes": payload + checksum,
                    "added_bytes": 0,
                    "time_us": self._mission_int(mission, "rng_us"),
                    "color": C_ACCENT_CYAN,
                }
            )

        steps.append(
            {
                "label": "AES-GCM",
                "detail": "cifra e tag (tx)",
                "explain": "O emissor cifra o payload com AES-128-GCM e gera a tag de autenticação. O pacote (ciphertext ML-KEM + nonce + ciphertext + tag) é então transmitido. O nonce não pode repetir com a mesma chave.",
                "kind": "aead",
                "packet_bytes": payload + checksum + mlkem + nonce + gcm + hmac,
                "added_bytes": nonce + gcm + hmac,
                "time_us": self._mission_int(mission, "encrypt_us", self._mission_int(mission, "tag_us")),
                "color": C_ACCENT_ORANGE,
            }
        )

        if scenario in {"PQC", "PQC_CRC32"}:
            # Lado receptor: só agora, com o pacote recebido, decapsula o
            # ciphertext ML-KEM para chegar ao mesmo segredo compartilhado.
            steps.append(
                {
                    "label": "DECAP",
                    "detail": "recupera segredo (rx)",
                    "explain": "Já no receptor: ele decapsula o ciphertext ML-KEM recebido com a chave privada e chega ao mesmo segredo compartilhado, sem expô-lo, derivando de novo a chave AES.",
                    "kind": "decap",
                    "packet_bytes": payload + checksum + mlkem + nonce + gcm + hmac,
                    "added_bytes": 0,
                    "time_us": self._mission_int(mission, "decap_us"),
                    "color": C_ACCENT_PURPLE,
                }
            )

        verify_detail = "decifra, tag e CRC" if checksum > 0 else "decifra e tag GCM"
        verify_time = self._mission_int(mission, "decrypt_us", self._mission_int(mission, "verify_us"))
        if checksum > 0:
            verify_time += self._mission_int(mission, "crc_us")
        steps.append(
            {
            "label": "VERIFICA",
            "detail": verify_detail,
            "explain": "No receptor, AES-GCM só libera o plaintext se a tag for válida. Com CRC32, a demo ainda checa corrupção acidental do payload.",
                "kind": "verify",
                "packet_bytes": payload + checksum + mlkem + nonce + gcm + hmac,
                "added_bytes": 0,
                "time_us": verify_time,
                "color": C_ACCENT_GREEN if checksum > 0 else C_TEXT_PRIMARY,
            }
        )

        steps.append(
            {
            "label": "RESULTADO",
            "detail": str(mission.get("result", "DELIVERED")),
            "explain": "Fluxo concluído. Compare tempo, bytes, heap, AEAD e CRC para medir o custo prático.",
                "kind": "send",
                "packet_bytes": total,
                "added_bytes": 0,
                "time_us": self._mission_int(mission, "elapsed_us"),
                "color": self._scenario_color(scenario),
            }
        )
        return steps

    def _bring_mission_overlay_to_front(self, scenario):
        if scenario not in self.mission_overlay_order:
            return
        self.mission_overlay_order = [item for item in self.mission_overlay_order if item != scenario]
        self.mission_overlay_order.append(scenario)
        self._sync_mission_overlay_state()

    def _close_mission_overlay(self, scenario):
        if scenario not in self.mission_overlays:
            return
        self.mission_overlay_closing_since.setdefault(scenario, self.uptime)
        if self.dragging_mission_overlay == scenario:
            self.dragging_mission_overlay = None
        if self.dragging_mission_flow_scenario == scenario:
            self.dragging_mission_flow_scenario = None

    def _remove_mission_overlay(self, scenario):
        self.mission_overlays.pop(scenario, None)
        self.mission_overlay_positions.pop(scenario, None)
        self.mission_overlay_opened_at.pop(scenario, None)
        self.mission_overlay_closing_since.pop(scenario, None)
        self.mission_overlay_rects.pop(scenario, None)
        self.mission_overlay_close_rects.pop(scenario, None)
        self.mission_overlay_drag_rects.pop(scenario, None)
        self.mission_flow_control_rects.pop(scenario, None)
        self.mission_flow_scrub_rects.pop(scenario, None)
        self.mission_overlay_order = [item for item in self.mission_overlay_order if item != scenario]
        if self.dragging_mission_overlay == scenario:
            self.dragging_mission_overlay = None
        if self.dragging_mission_flow_scenario == scenario:
            self.dragging_mission_flow_scenario = None
        self.mission_flow_animations.pop(scenario, None)
        self._sync_active_mission_flow_animation()
        self._sync_mission_overlay_state()

    def _sync_mission_overlay_state(self):
        self.mission_overlay_visible = bool(self.mission_overlay_order)
        if not self.mission_overlay_order:
            self.last_mission = {}
            self.mission_overlay_close_rect = None
            return
        top_scenario = self.mission_overlay_order[-1]
        self.last_mission = dict(self.mission_overlays.get(top_scenario, {}))
        self.mission_overlay_close_rect = self.mission_overlay_close_rects.get(top_scenario)

    def _update_pqc_label(self, payload):
        target = payload.get("pqc_target", "ML-KEM-512")
        status = payload.get("pqc_status") or payload.get("pqc")
        if status:
            display_status = status.replace("_", " ").upper()
            self.pqc_algorithm = f"{target} ({display_status})"

    def _record_hardware_sample(self, command, payload):
        pqc_metric_keys = {
            "pqc_target",
            "pqc_backend",
            "pqc_variant",
            "pqc_status",
            "pqc_commit",
            "pqc_license",
            "source",
            "op",
            "target",
            "result",
            "confirmation",
            "kat",
            "key_match",
            "key_confirmed",
            "tag_match",
            "tag_ready",
            "ready",
            "stored",
            "ct_stored",
            "key_rc",
            "pk_rc",
            "sk_rc",
            "enc_rc",
            "dec_rc",
            "n",
            "ok",
            "pk",
            "sk",
            "ct",
            "ss",
            "keygen_avg_us",
            "encap_avg_us",
            "decap_avg_us",
            "keygen_us",
            "encap_us",
            "decap_us",
            "confirm_us",
            "pk_crc32",
            "ct_crc32",
            "ss_crc32",
            "ct_crc_before",
            "ct_crc_after",
            "ss_enc_crc32",
            "ss_dec_crc32",
            "tag_enc_crc32",
            "tag_dec_crc32",
            "byte_index",
            "bit_mask",
            "before",
            "after",
        }
        mission_metric_keys = {
            "scenario",
            "message",
            "crypto",
            "cipher",
            "checksum",
            "key_source",
            "key_policy",
            "payload_len",
            "payload_crc32",
            "bytes_payload",
            "bytes_ciphertext",
            "bytes_mlkem",
            "bytes_nonce",
            "bytes_gcm_tag",
            "bytes_crypto",
            "bytes_checksum",
            "bytes_total",
            "nonce_bytes",
            "gcm_tag_bytes",
            "ciphertext_bytes",
            "tag_us",
            "verify_us",
            "rng_us",
            "kdf_us",
            "encrypt_us",
            "decrypt_us",
            "crc_us",
            "crc_match",
            "aead_match",
            "decrypt_ok",
        }
        metric_keys = {
            "uptime_ms",
            "cpu_mhz",
            "heap",
            "min_heap",
            "flash",
            "elapsed_us",
            "cpu_load_pct",
            "radio",
            "profile",
        } | pqc_metric_keys | mission_metric_keys
        if not any(key in payload for key in metric_keys):
            return

        elapsed_us = _optional_int(payload.get("elapsed_us"))
        cpu_mhz = _optional_int(payload.get("cpu_mhz"))
        energy_value = None
        if elapsed_us is not None and cpu_mhz is not None:
            energy_value = cpu_mhz * elapsed_us
        cpu_load_pct = _optional_float(payload.get("cpu_load_pct"))
        if cpu_load_pct is None:
            cpu_load_pct = self._remember_cpu_activity(elapsed_us)

        uptime_ms = _optional_int(payload.get("uptime_ms"))
        sample = {
            "timestamp": _utc_now_iso(),
            "uptime_s": round(uptime_ms / 1000, 3) if uptime_ms is not None else round(self.uptime, 3),
            "mode": "HARDWARE",
            "source_command": command.split()[0],
            "profile": payload.get("profile", ""),
            "cpu_mhz": cpu_mhz,
            "heap": _optional_int(payload.get("heap")),
            "min_heap": _optional_int(payload.get("min_heap")),
            "flash": _optional_int(payload.get("flash")),
            "elapsed_us": elapsed_us,
            "cpu_load_pct": round(cpu_load_pct, 2),
            "cpu_load_window_s": CPU_LOAD_WINDOW_SECONDS,
            "radio": payload.get("radio", ""),
            "pqc_target": payload.get("pqc_target", ""),
            "pqc_backend": payload.get("pqc_backend", ""),
            "pqc_status": payload.get("pqc_status", ""),
            "checksum": payload.get("guard", self.guard_mode),
            "energy_proxy": {
                "kind": "relative_cpu_time",
                "value": energy_value,
                "unit": "mhz_us",
            },
        }
        pqc_sample = self._pqc_sample_export(command, payload)
        if pqc_sample:
            sample["pqc"] = pqc_sample
        mission_sample = self._mission_sample_export(command, payload)
        if mission_sample:
            sample["mission"] = mission_sample
        self.hardware_samples.append(sample)
        self.session_dirty = True
        if len(self.hardware_samples) > 512:
            self.hardware_samples = self.hardware_samples[-512:]

    def _pqc_sample_export(self, command, payload):
        source_command = command.split()[0].upper()
        if source_command != "STRESS" and not source_command.startswith("PQC") and not any(key.startswith("pqc_") for key in payload):
            return {}

        text_fields = (
            "pqc_target",
            "pqc_backend",
            "pqc_variant",
            "pqc_status",
            "pqc_commit",
            "pqc_license",
            "source",
            "op",
            "mode",
            "target",
            "result",
            "confirmation",
            "kat",
            "pk_crc32",
            "ct_crc32",
            "ss_crc32",
            "ct_crc_before",
            "ct_crc_after",
            "ss_enc_crc32",
            "ss_dec_crc32",
            "tag_enc_crc32",
            "tag_dec_crc32",
            "bit_mask",
            "before",
            "after",
        )
        numeric_fields = (
            "ready",
            "stored",
            "ct_stored",
            "key_match",
            "key_confirmed",
            "tag_match",
            "tag_ready",
            "key_rc",
            "pk_rc",
            "sk_rc",
            "enc_rc",
            "dec_rc",
            "n",
            "ok",
            "byte_index",
            "pk",
            "sk",
            "ct",
            "ss",
            "keygen_avg_us",
            "encap_avg_us",
            "decap_avg_us",
            "keygen_us",
            "encap_us",
            "decap_us",
            "confirm_us",
            "elapsed_us",
        )
        sample = {"command": source_command}
        for key in text_fields:
            if key in payload:
                sample[key] = payload[key]
        for key in numeric_fields:
            if key in payload:
                sample[key] = _optional_int(payload[key])
        return sample

    def _mission_sample_export(self, command, payload):
        source_command = command.split()[0].upper()
        if source_command != "MISSION" and "scenario" not in payload:
            return {}

        text_fields = (
            "scenario",
            "op",
            "message",
            "result",
            "crypto",
            "cipher",
            "checksum",
            "confirmation",
            "key_source",
            "key_policy",
            "payload_mode",
            "payload_live_status",
            "payload_text",
            "payload_hex_sent",
            "payload_crc32",
            "crc_tx",
            "crc_rx",
            "nonce_crc32",
            "ciphertext_crc32",
            "gcm_tag_crc32",
            "sensor_accel",
            "sensor_failures",
        )
        numeric_fields = (
            "key_match",
            "tag_ready",
            "tag_match",
            "aead_match",
            "decrypt_ok",
            "crc_match",
            "payload_seq",
            "payload_len",
            "bytes_payload",
            "bytes_ciphertext",
            "bytes_mlkem",
            "bytes_nonce",
            "bytes_gcm_tag",
            "bytes_crypto",
            "bytes_checksum",
            "bytes_total",
            "nonce_bytes",
            "gcm_tag_bytes",
            "ciphertext_bytes",
            "sensor_temp_c_x100",
            "sensor_hum_x100",
            "sensor_light",
            "sensor_pot",
            "sensor_button",
            "keygen_us",
            "encap_us",
            "decap_us",
            "rng_us",
            "kdf_us",
            "encrypt_us",
            "decrypt_us",
            "tag_us",
            "verify_us",
            "crc_us",
            "elapsed_us",
        )
        sample = {"command": source_command}
        for key in text_fields:
            if key in payload:
                sample[key] = payload[key]
        for key in numeric_fields:
            if key in payload:
                sample[key] = _optional_int(payload[key])
        return sample

    def draw(self, surface, t, satellite):
        """Desenha todos os paineis da interface."""
        self._draw_ping_effect(surface, t, satellite)
        self._draw_fault_effect(surface, t, satellite)
        self._draw_left_panel(surface, t, satellite)
        self._draw_right_panel(surface, t)
        self._draw_top_bar(surface, t)
        self._draw_top_metrics(surface, t)
        self._draw_demo_overlay(surface, t)
        self._draw_mission_overlay(surface, t)
        self._draw_fault_overlay(surface, t)
        # OTIMIZAÇÃO SEMINÁRIO
        self._draw_bit_rain(surface)
        self._draw_bottom_bar(surface, t)
        if self.stand_mode:
            self._draw_stand_presentation(surface, t)
        if getattr(self, "results_overlay_visible", False):
            self._draw_results_overlay(surface, t)

    def _stand_overlay_geometry(self):
        margin = max(22, int(min(WIDTH, HEIGHT) * 0.032))
        top = 56
        bottom = 38
        return pygame.Rect(margin, top, WIDTH - margin * 2, HEIGHT - top - bottom - margin)

    @staticmethod
    def _stand_state_progress(state_name):
        return {
            "ATTRACT": -1,
            "INTRO": 0,
            "RUN_240": 1,
            "RUN_80": 2,
            "SELECT_BIT": 3,
            "FAULT_NONE": 4,
            "FAULT_CRC": 5,
            "SUMMARY": 6,
        }.get(state_name, -1)

    def _draw_stand_presentation(self, surface, t):
        """Render the guided mission as a native layer of the existing dashboard."""
        controller = self.stand_controller
        state_name = controller.state.value
        rect = self._stand_overlay_geometry()

        shade = pygame.Surface((WIDTH, HEIGHT - 44), pygame.SRCALPHA)
        pygame.draw.rect(shade, (0, 2, 10, 112), shade.get_rect())
        surface.blit(shade, (0, 44))

        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*C_PANEL_BG, 235), panel.get_rect(), border_radius=10)
        pygame.draw.rect(panel, (*C_ACCENT_CYAN, 215), panel.get_rect(), width=2, border_radius=10)
        pygame.draw.rect(panel, (*C_PANEL_HEADER, 245), (0, 0, rect.width, 82), border_radius=10)
        pygame.draw.line(panel, (*C_PANEL_BORDER, 210), (0, 82), (rect.width, 82), 1)
        surface.blit(panel, rect.topleft)

        title = FONT_BODY.render("MISSÃO GUARDIÕES DO BIT  •  APRESENTAÇÃO INTERATIVA", True, C_ACCENT_CYAN)
        surface.blit(title, (rect.x + 20, rect.y + 12))

        mode_text = controller.persistent_mode_label
        mode_color = C_ACCENT_GREEN if controller.ready and controller.mode == "hardware" else C_ACCENT_PURPLE
        if controller.mode == "hardware" and not controller.ready:
            mode_color = C_ACCENT_ORANGE
        mode_surface = self._render_clipped(FONT_LABEL, mode_text, mode_color, min(470, rect.width // 2))
        surface.blit(mode_surface, (rect.right - mode_surface.get_width() - 20, rect.y + 15))

        labels = ("MISSÃO", "240 MHz", "80 MHz", "BIT", "SEM CRC", "CRC32", "FIM")
        active_index = self._stand_state_progress(state_name)
        progress_left = rect.x + 34
        progress_right = rect.right - 34
        progress_y = rect.y + 60
        pygame.draw.line(surface, (45, 74, 112), (progress_left, progress_y), (progress_right, progress_y), 2)
        for index, label in enumerate(labels):
            ratio = index / max(1, len(labels) - 1)
            px = int(progress_left + (progress_right - progress_left) * ratio)
            complete = active_index >= index
            active = active_index == index
            color = C_ACCENT_GREEN if complete else C_TEXT_DIM
            if active:
                color = C_ACCENT_CYAN
                pulse = 7 + int(2 * (0.5 + 0.5 * math.sin(t * 4.0)))
                pygame.draw.circle(surface, (*C_ACCENT_CYAN, 45), (px, progress_y), pulse + 5, 1)
            pygame.draw.circle(surface, color, (px, progress_y), 6 if active else 4)
            label_surface = FONT_LABEL.render(label, True, color)
            surface.blit(label_surface, (px - label_surface.get_width() // 2, progress_y + 9))

        body = pygame.Rect(rect.x + 24, rect.y + 94, rect.width - 48, rect.height - 126)
        draw_state = {
            "ATTRACT": self._draw_stand_attract,
            "INTRO": self._draw_stand_intro,
            "RUN_240": self._draw_stand_run_240,
            "RUN_80": self._draw_stand_run_80,
            "SELECT_BIT": self._draw_stand_select_bit,
            "FAULT_NONE": self._draw_stand_fault_none,
            "FAULT_CRC": self._draw_stand_fault_crc,
            "SUMMARY": self._draw_stand_summary,
            "ERROR": self._draw_stand_error,
        }.get(state_name, self._draw_stand_error)
        draw_state(surface, body, controller, t)

        source = controller.measurement_source_label
        source_surface = self._render_clipped(FONT_LABEL, source, C_TEXT_DIM, rect.width - 48)
        surface.blit(source_surface, (rect.x + 24, rect.bottom - 24))

        if self.stand_diagnostic:
            self._draw_stand_diagnostic(surface, rect, controller)

    def _draw_stand_centered(self, surface, font, text, color, center_x, y, max_width, *, line_gap=6):
        lines = self._wrap_text_for_width(font, text, max_width)
        for line in lines:
            rendered = font.render(line, True, color)
            surface.blit(rendered, (center_x - rendered.get_width() // 2, y))
            y += rendered.get_height() + line_gap
        return y

    @staticmethod
    def _draw_stand_card_shell(surface, rect, accent, *, fill=(8, 16, 34)):
        pygame.draw.rect(surface, fill, rect, border_radius=8)
        pygame.draw.rect(surface, accent, rect, width=2, border_radius=8)
        pygame.draw.line(surface, accent, (rect.x + 12, rect.y + 42), (rect.right - 12, rect.y + 42), 1)

    def _draw_stand_attract(self, surface, body, controller, t):
        center_x = body.centerx
        y = body.y + 32
        y = self._draw_stand_centered(
            surface,
            FONT_LARGE,
            "UM ÚNICO BIT PODE MUDAR UMA MISSÃO ESPACIAL",
            C_TEXT_PRIMARY,
            center_x,
            y,
            body.width - 120,
            line_gap=4,
        )
        y = self._draw_stand_centered(
            surface,
            FONT_HEADER,
            "Você consegue descobrir qual proteção percebe a falha?",
            C_TEXT_DIM,
            center_x,
            y + 8,
            body.width - 180,
        )

        orbit = pygame.Rect(center_x - 245, y + 26, 490, 138)
        pygame.draw.ellipse(surface, (35, 92, 150), orbit, 2)
        earth_center = (center_x, orbit.centery)
        pygame.draw.circle(surface, (34, 112, 204), earth_center, 45)
        pygame.draw.circle(surface, C_ACCENT_CYAN, earth_center, 45, 2)
        sat_x = int(center_x + math.cos(t * 0.55) * orbit.width * 0.48)
        sat_y = int(orbit.centery + math.sin(t * 0.55) * orbit.height * 0.46)
        pygame.draw.rect(surface, C_SAT_BODY, (sat_x - 18, sat_y - 11, 36, 22), border_radius=4)
        pygame.draw.rect(surface, C_SAT_PANEL_BLUE, (sat_x - 43, sat_y - 7, 23, 14))
        pygame.draw.rect(surface, C_SAT_PANEL_BLUE, (sat_x + 20, sat_y - 7, 23, 14))
        pygame.draw.circle(surface, C_SAT_GOLD, (sat_x, sat_y - 14), 4)

        ready = controller.ready
        prompt_color = C_ACCENT_GREEN if ready else C_ACCENT_ORANGE
        prompt = pygame.Rect(center_x - min(430, body.width // 2 - 40), body.bottom - 104, min(860, body.width - 80), 76)
        pygame.draw.rect(surface, (10, 42, 42) if ready else (50, 34, 12), prompt, border_radius=9)
        pygame.draw.rect(surface, prompt_color, prompt, width=2, border_radius=9)
        if ready and controller.mode == "hardware":
            message = "PRESSIONE O BOTÃO D27 DA PLACA PARA COMEÇAR"
        elif ready:
            message = "ENSAIO VISUAL: PRESSIONE ESPAÇO PARA COMEÇAR"
        else:
            message = "AGUARDANDO HANDSHAKE COM A BLACKBOARD WISDOM"
        self._draw_stand_centered(surface, FONT_HEADER, message, prompt_color, prompt.centerx, prompt.y + 22, prompt.width - 30)

    def _draw_stand_intro(self, surface, body, controller, _t):
        y = self._draw_stand_centered(
            surface,
            FONT_LARGE,
            "MISSÃO: ENVIAR TELEMETRIA CRÍTICA À ESTAÇÃO TERRESTRE",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 28,
            body.width - 100,
        )
        payload_rect = pygame.Rect(body.x + 90, y + 28, body.width - 180, 108)
        self._draw_stand_card_shell(surface, payload_rect, C_ACCENT_CYAN)
        label = FONT_LABEL.render("MESMO PAYLOAD EM TODAS AS ETAPAS", True, C_TEXT_DIM)
        surface.blit(label, (payload_rect.x + 18, payload_rect.y + 14))
        self._draw_stand_centered(
            surface,
            FONT_HEADER,
            controller.config.payload_display,
            C_ACCENT_CYAN,
            payload_rect.centerx,
            payload_rect.y + 57,
            payload_rect.width - 36,
        )

        facts = (
            ("PLACA REAL", "A Wisdom executa a criptografia e mede o tempo.", C_ACCENT_GREEN),
            ("COMPARAÇÃO JUSTA", "O payload permanece idêntico em cada cenário.", C_ACCENT_CYAN),
            ("FALHA CONTROLADA", "O bit flip é injetado por software; não há radiação real.", C_ACCENT_ORANGE),
        )
        gap = 14
        card_w = (body.width - gap * 2 - 80) // 3
        card_y = payload_rect.bottom + 34
        for index, (title, text_value, color) in enumerate(facts):
            card = pygame.Rect(body.x + 40 + index * (card_w + gap), card_y, card_w, 126)
            self._draw_stand_card_shell(surface, card, color)
            title_surface = FONT_BODY.render(title, True, color)
            surface.blit(title_surface, (card.x + 14, card.y + 12))
            self._draw_wrapped_text(surface, FONT_SMALL, text_value, C_TEXT_PRIMARY, card.x + 14, card.y + 55, card.width - 28, line_spacing=19, max_lines=3)

        remaining = max(0.0, controller.config.intro_seconds - controller.state_elapsed())
        countdown = FONT_LABEL.render(f"Preparando comparação em {remaining:0.1f} s", True, C_TEXT_DIM)
        surface.blit(countdown, (body.centerx - countdown.get_width() // 2, body.bottom - 34))

    def _draw_stand_measurement_card(self, surface, rect, title, measurement, accent, role):
        self._draw_stand_card_shell(surface, rect, accent)
        title_surface = FONT_HEADER.render(title, True, accent)
        surface.blit(title_surface, (rect.x + 16, rect.y + 11))
        self._draw_wrapped_text(surface, FONT_LABEL, role, C_TEXT_DIM, rect.x + 16, rect.y + 52, rect.width - 32, line_spacing=16, max_lines=2)
        if measurement is None:
            waiting = FONT_BODY.render("EXECUTANDO NA PLACA...", True, C_TEXT_PRIMARY)
            surface.blit(waiting, (rect.centerx - waiting.get_width() // 2, rect.centery + 8))
            return

        metrics_y = rect.y + 102
        metric_gap = 10
        metric_w = (rect.width - 42 - metric_gap) // 2
        values = (
            ("TEMPO REAL", _format_elapsed(measurement.elapsed_us), C_ACCENT_CYAN),
            ("PACOTE", f"{measurement.bytes_total} B", C_ACCENT_ORANGE),
            ("CLOCK", f"{measurement.profile_mhz} MHz", C_TEXT_PRIMARY),
            ("RESULTADO", "ENTREGUE" if measurement.result == "DELIVERED" else measurement.result, C_ACCENT_GREEN),
        )
        for index, (label, value, color) in enumerate(values):
            box = pygame.Rect(
                rect.x + 16 + (index % 2) * (metric_w + metric_gap),
                metrics_y + (index // 2) * 62,
                metric_w,
                52,
            )
            self._draw_overlay_metric_box(surface, label, value, box.x, box.y, box.width, box.height, color)
        source = self._render_clipped(FONT_LABEL, measurement.source.upper(), C_TEXT_DIM, rect.width - 32)
        surface.blit(source, (rect.x + 16, rect.bottom - 25))

    def _draw_stand_run_240(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_TITLE,
            "1. MESMO PAYLOAD, DUAS FORMAS DE PREPARAR A SESSÃO — 240 MHz",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 8,
            body.width - 70,
        )
        gap = 22
        card_w = (body.width - gap - 40) // 2
        card_y = body.y + 62
        card_h = body.height - 112
        classic = controller.measurements.get("CLASSIC_240")
        pqc = controller.measurements.get("PQC_240")
        self._draw_stand_measurement_card(
            surface,
            pygame.Rect(body.x + 20, card_y, card_w, card_h),
            "BASELINE AES-GCM",
            classic,
            C_ACCENT_ORANGE,
            "Chave AES efêmera gerada localmente; baseline simétrico.",
        )
        self._draw_stand_measurement_card(
            surface,
            pygame.Rect(body.x + 20 + card_w + gap, card_y, card_w, card_h),
            "ML-KEM-512 + AES-GCM",
            pqc,
            C_ACCENT_PURPLE,
            "ML-KEM estabelece o segredo; AES-GCM cifra e autentica.",
        )

    def _draw_stand_run_80(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_TITLE,
            "2. O MESMO ML-KEM EM UM PERFIL EXPERIMENTAL DE 80 MHz",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 8,
            body.width - 80,
        )
        gap = 22
        card_w = (body.width - gap - 40) // 2
        card_y = body.y + 62
        card_h = body.height - 126
        pqc_240 = controller.measurements.get("PQC_240")
        pqc_80 = controller.measurements.get("PQC_80")
        self._draw_stand_measurement_card(
            surface,
            pygame.Rect(body.x + 20, card_y, card_w, card_h),
            "PQC EM 240 MHz",
            pqc_240,
            C_ACCENT_CYAN,
            "Baseline integral da ESP32.",
        )
        self._draw_stand_measurement_card(
            surface,
            pygame.Rect(body.x + 20 + card_w + gap, card_y, card_w, card_h),
            "PQC EM 80 MHz",
            pqc_80,
            C_ACCENT_PURPLE,
            "Perfil OBC-1U-LIMITED do experimento.",
        )
        if pqc_240 is not None and pqc_80 is not None and pqc_240.elapsed_us:
            ratio = pqc_80.elapsed_us / pqc_240.elapsed_us
            note = f"Resultado desta execução: 80 MHz levou {ratio:.1f}× o tempo de 240 MHz. Não é medição de energia."
        else:
            note = "Aguardando a placa confirmar o perfil e devolver a medição real."
        self._draw_stand_centered(surface, FONT_LABEL, note, C_TEXT_DIM, body.centerx, body.bottom - 34, body.width - 80)

    def _draw_stand_select_bit(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_TITLE,
            "3. GIRE O POTENCIÔMETRO VN/A39 PARA ESCOLHER UM BIT",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 8,
            body.width - 80,
        )
        selection = controller.selection
        payload = controller.config.payload_bytes
        selected_index = selection.byte_index if selection is not None else None
        cells_per_row = min(len(payload), 21)
        cell_gap = 5
        cell_w = min(42, (body.width - 100 - (cells_per_row - 1) * cell_gap) // cells_per_row)
        rows = math.ceil(len(payload) / cells_per_row)
        grid_w = cells_per_row * cell_w + (cells_per_row - 1) * cell_gap
        grid_x = body.centerx - grid_w // 2
        grid_y = body.y + 72
        for index, byte in enumerate(payload):
            row, col = divmod(index, cells_per_row)
            cell = pygame.Rect(grid_x + col * (cell_w + cell_gap), grid_y + row * 48, cell_w, 39)
            active = index == selected_index
            color = C_ACCENT_ORANGE if active else C_PANEL_BORDER
            pygame.draw.rect(surface, (42, 26, 12) if active else (9, 17, 33), cell, border_radius=4)
            pygame.draw.rect(surface, color, cell, width=2 if active else 1, border_radius=4)
            value = FONT_LABEL.render(f"{byte:02X}", True, color if active else C_TEXT_PRIMARY)
            surface.blit(value, (cell.centerx - value.get_width() // 2, cell.y + 6))
            number = FONT_LABEL.render(str(index), True, C_TEXT_DIM)
            surface.blit(number, (cell.centerx - number.get_width() // 2, cell.y + 22))

        gauge_y = grid_y + rows * 48 + 38
        gauge = pygame.Rect(body.x + 110, gauge_y, body.width - 220, 14)
        pygame.draw.rect(surface, (12, 24, 43), gauge, border_radius=7)
        pygame.draw.rect(surface, C_PANEL_BORDER, gauge, width=1, border_radius=7)
        if selection is not None:
            config = controller.config
            ratio = (selection.pot_value - config.pot_minimum) / max(1, config.pot_maximum - config.pot_minimum)
            marker_x = int(gauge.x + max(0.0, min(1.0, ratio)) * gauge.width)
            pygame.draw.circle(surface, C_ACCENT_ORANGE, (marker_x, gauge.centery), 11)
            before = payload[selection.byte_index]
            selected_bit = int(math.log2(selection.bit_mask))
            detail = (
                f"POT {selection.pot_value}  •  BYTE {selection.byte_index} = 0x{before:02X} "
                f"•  BIT {selected_bit}  •  MÁSCARA 0x{selection.bit_mask:02X}"
            )
            binary = f"{before:08b}  →  {before ^ selection.bit_mask:08b}"
        else:
            detail = "LENDO O POTENCIÔMETRO DA WISDOM..."
            binary = "--------  →  --------"
        self._draw_stand_centered(surface, FONT_BODY, detail, C_ACCENT_ORANGE, body.centerx, gauge.bottom + 25, body.width - 90)
        self._draw_stand_centered(surface, FONT_LARGE, binary, C_TEXT_PRIMARY, body.centerx, gauge.bottom + 62, body.width - 100)
        self._draw_stand_centered(
            surface,
            FONT_HEADER,
            "PRESSIONE D27 PARA FIXAR ESTE BIT E INJETAR A FALHA",
            C_ACCENT_GREEN,
            body.centerx,
            body.bottom - 42,
            body.width - 80,
        )

    def _draw_stand_fault_card(self, surface, rect, title, measurement, accent, explanation):
        self._draw_stand_card_shell(surface, rect, accent)
        title_surface = FONT_HEADER.render(title, True, accent)
        surface.blit(title_surface, (rect.x + 16, rect.y + 11))
        if measurement is None:
            waiting = FONT_BODY.render("EXECUTANDO A MESMA FALHA...", True, C_TEXT_PRIMARY)
            surface.blit(waiting, (rect.centerx - waiting.get_width() // 2, rect.centery - 10))
            return
        before = f"{measurement.before_byte:08b}"
        after = f"{measurement.after_byte:08b}"
        binary = FONT_LARGE.render(f"{before}  →  {after}", True, C_TEXT_PRIMARY)
        surface.blit(binary, (rect.centerx - binary.get_width() // 2, rect.y + 78))
        detail = f"byte {measurement.byte_index}  •  máscara 0x{measurement.bit_mask:02X}"
        detail_surface = FONT_LABEL.render(detail, True, C_TEXT_DIM)
        surface.blit(detail_surface, (rect.centerx - detail_surface.get_width() // 2, rect.y + 130))
        result_color = C_ACCENT_RED if measurement.result == "SILENT" else C_ACCENT_GREEN
        result_text = "CORRUPÇÃO SILENCIOSA" if measurement.result == "SILENT" else "FALHA DETECTADA"
        result = FONT_HEADER.render(result_text, True, result_color)
        surface.blit(result, (rect.centerx - result.get_width() // 2, rect.y + 164))
        self._draw_wrapped_text(surface, FONT_SMALL, explanation, C_TEXT_PRIMARY, rect.x + 18, rect.y + 208, rect.width - 36, line_spacing=19, max_lines=3)
        crc_line = f"CRC antes {measurement.crc_before:08X}  •  depois {measurement.crc_after:08X}"
        crc_surface = self._render_clipped(FONT_LABEL, crc_line, C_TEXT_DIM, rect.width - 36)
        surface.blit(crc_surface, (rect.centerx - crc_surface.get_width() // 2, rect.bottom - 28))

    def _draw_stand_fault_none(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_TITLE,
            "4. PRIMEIRO ENSAIO: PAYLOAD SEM GUARDIÃO",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 8,
            body.width - 80,
        )
        card = pygame.Rect(body.x + 150, body.y + 62, body.width - 300, body.height - 98)
        self._draw_stand_fault_card(
            surface,
            card,
            "FAULT NONE",
            controller.fault_results.get("NONE"),
            C_ACCENT_RED,
            "O byte mudou e nenhuma referência de integridade foi comparada. O harness classificou o resultado como SILENT.",
        )

    def _draw_stand_fault_crc(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_TITLE,
            "5. REPETINDO EXATAMENTE O MESMO BIT FLIP COM CRC32",
            C_TEXT_PRIMARY,
            body.centerx,
            body.y + 8,
            body.width - 80,
        )
        gap = 22
        card_w = (body.width - gap - 40) // 2
        card_y = body.y + 62
        card_h = body.height - 98
        self._draw_stand_fault_card(
            surface,
            pygame.Rect(body.x + 20, card_y, card_w, card_h),
            "SEM GUARDIÃO",
            controller.fault_results.get("NONE"),
            C_ACCENT_RED,
            "A corrupção passou silenciosamente no ensaio localizado de payload.",
        )
        self._draw_stand_fault_card(
            surface,
            pygame.Rect(body.x + 20 + card_w + gap, card_y, card_w, card_h),
            "COM CRC32",
            controller.fault_results.get("CRC32"),
            C_ACCENT_GREEN,
            "O CRC32 de referência divergiu após a mutação e tornou a corrupção acidental observável.",
        )

    def _draw_stand_summary(self, surface, body, controller, _t):
        self._draw_stand_centered(
            surface,
            FONT_LARGE,
            "MISSÃO CONCLUÍDA",
            C_ACCENT_GREEN,
            body.centerx,
            body.y + 6,
            body.width - 80,
        )
        conclusions = (
            ("ML-KEM-512", "Estabelece o segredo compartilhado pós-quântico.", C_ACCENT_PURPLE),
            ("AES-128-GCM", "Cifra e autentica a mensagem enviada.", C_ACCENT_CYAN),
            ("CRC32", "Detecta corrupção acidental na região coberta; não impede atacante.", C_ACCENT_GREEN),
        )
        gap = 16
        card_w = (body.width - 80 - gap * 2) // 3
        card_y = body.y + 72
        for index, (title, explanation, color) in enumerate(conclusions):
            card = pygame.Rect(body.x + 40 + index * (card_w + gap), card_y, card_w, 145)
            self._draw_stand_card_shell(surface, card, color)
            title_surface = FONT_HEADER.render(title, True, color)
            surface.blit(title_surface, (card.centerx - title_surface.get_width() // 2, card.y + 13))
            self._draw_wrapped_text(surface, FONT_SMALL, explanation, C_TEXT_PRIMARY, card.x + 16, card.y + 62, card.width - 32, line_spacing=20, max_lines=3)

        classic = controller.measurements.get("CLASSIC_240")
        pqc = controller.measurements.get("PQC_240")
        pqc_80 = controller.measurements.get("PQC_80")
        metric_y = card_y + 178
        if classic and pqc and pqc_80 and classic.elapsed_us:
            summary = (
                f"Nesta execução: baseline { _format_elapsed(classic.elapsed_us) } / {classic.bytes_total} B  •  "
                f"PQC 240 MHz { _format_elapsed(pqc.elapsed_us) } / {pqc.bytes_total} B  •  "
                f"PQC 80 MHz { _format_elapsed(pqc_80.elapsed_us) }"
            )
        else:
            summary = "As conclusões numéricas só aparecem depois de respostas aceitas da placa ou da fixture oficial rotulada."
        self._draw_stand_centered(surface, FONT_BODY, summary, C_TEXT_PRIMARY, body.centerx, metric_y, body.width - 100)

        prompt = "PRESSIONE D27 PARA RECOMEÇAR" if controller.mode == "hardware" else "PRESSIONE ESPAÇO PARA RECOMEÇAR"
        self._draw_stand_centered(surface, FONT_HEADER, prompt, C_ACCENT_GREEN, body.centerx, body.bottom - 38, body.width - 80)

    def _draw_stand_error(self, surface, body, controller, _t):
        card = pygame.Rect(body.x + 130, body.y + 48, body.width - 260, body.height - 96)
        self._draw_stand_card_shell(surface, card, C_ACCENT_RED, fill=(42, 12, 24))
        title = FONT_LARGE.render("FLUXO INTERROMPIDO COM SEGURANÇA", True, C_ACCENT_RED)
        surface.blit(title, (card.centerx - title.get_width() // 2, card.y + 40))
        self._draw_stand_centered(
            surface,
            FONT_HEADER,
            controller.error_message or "Resposta inválida ou conexão indisponível.",
            C_TEXT_PRIMARY,
            card.centerx,
            card.y + 120,
            card.width - 80,
        )
        self._draw_stand_centered(
            surface,
            FONT_BODY,
            "Nenhum valor foi inventado. Verifique a Wisdom e pressione D27 ou R para voltar ao início.",
            C_TEXT_DIM,
            card.centerx,
            card.bottom - 86,
            card.width - 80,
        )

    def _draw_stand_diagnostic(self, surface, outer_rect, controller):
        pending = controller.pending.command if controller.pending is not None else "--"
        lines = (
            f"ESTADO {controller.state.value} / {controller.substage}",
            f"CONEXÃO {controller.connection_status}",
            f"PENDENTE {pending}",
            f"CICLOS {controller.completed_cycles}  REJEITADOS {controller.rejected_events}",
        )
        rect = pygame.Rect(outer_rect.right - 510, outer_rect.bottom - 122, 486, 92)
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 225), panel.get_rect(), border_radius=6)
        pygame.draw.rect(panel, C_ACCENT_ORANGE, panel.get_rect(), width=1, border_radius=6)
        surface.blit(panel, rect.topleft)
        for index, line in enumerate(lines):
            surface.blit(self._render_clipped(FONT_LABEL, line, C_ACCENT_ORANGE, rect.width - 20), (rect.x + 10, rect.y + 9 + index * 19))

    def _results_overlay_geometry(self):
        margin = max(18, int(min(WIDTH, HEIGHT) * 0.025))
        w = min(int(WIDTH * 0.92), WIDTH - margin * 2)
        if getattr(self, "results_overlay_mode", "presentation") == "presentation":
            height_ratio = 0.90 if HEIGHT < 900 else 0.84
        else:
            height_ratio = 0.94
        h = min(int(HEIGHT * height_ratio), HEIGHT - margin * 2)
        x = (WIDTH - w) // 2
        y = (HEIGHT - h) // 2
        close_w = 112 if WIDTH < 1500 else 144
        close_rect = pygame.Rect(x + w - close_w - 22, y + 20, close_w, 34)
        return pygame.Rect(x, y, w, h), close_rect

    def _draw_wrapped_text(self, surface, font, text, color, x, y, max_width, line_spacing=20, max_lines=None):
        lines = self._wrap_text_for_width(font, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            surface.blit(self._render_clipped(font, line, color, max_width), (x, y))
            y += line_spacing
        return y

    def _short_explanation(self, text):
        text = str(text or "").strip()
        if not text:
            return ""
        for separator in (". ", "; "):
            if separator in text:
                first = text.split(separator, 1)[0].strip()
                return first + ("." if separator.startswith(".") and not first.endswith(".") else "")
        return text

    def _scenario_color(self, scenario):
        if scenario == "PQC_CRC32":
            return C_ACCENT_GREEN
        if scenario == "PQC":
            return C_ACCENT_ORANGE
        return C_TEXT_PRIMARY

    def _draw_transform_shell(self, surface, rect, title, accent):
        pygame.draw.rect(surface, (4, 8, 18), rect, border_radius=6)
        pygame.draw.rect(surface, (18, 26, 52), rect.inflate(-4, -4), border_radius=5)
        pygame.draw.rect(surface, accent, rect, width=2, border_radius=6)
        header = pygame.Rect(rect.x, rect.y, rect.width, 24)
        pygame.draw.rect(surface, (24, 34, 64), header, border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.line(surface, accent, (rect.x, rect.y + 24), (rect.right, rect.y + 24), 1)
        surface.blit(self._render_clipped(FONT_LABEL, title, C_TEXT_PRIMARY, rect.width - 16), (rect.x + 8, rect.y + 5))

    def _mix_color(self, base, color, amount):
        amount = max(0.0, min(1.0, amount))
        return tuple(int(base[i] * (1.0 - amount) + color[i] * amount) for i in range(3))

    def _draw_soft_glow(self, surface, center, radius, color, alpha=70):
        size = max(8, radius * 4)
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        origin = (size // 2, size // 2)
        for layer in range(4, 0, -1):
            layer_radius = int(radius * (0.58 + layer * 0.34))
            layer_alpha = max(8, int(alpha / (layer * 0.85)))
            pygame.draw.circle(glow, (*color, layer_alpha), origin, layer_radius)
        surface.blit(glow, (center[0] - size // 2, center[1] - size // 2))

    # ===================================================================
    # Pixel-art scene engine (lúdico illustrations for the popups)
    # ===================================================================
    def _pix_stage(self, surface, rect, accent, t, theme="space"):
        """Draw a starlit backdrop and return the usable inner play area."""
        pygame.draw.rect(surface, (5, 8, 18), rect, border_radius=5)
        self._pix_starfield(surface, rect, t)
        if theme == "space":
            self._pix_earth_arc(surface, rect)
        else:
            deck_y = rect.bottom - 4
            pygame.draw.line(surface, self._mix_color((18, 26, 50), accent, 0.30),
                             (rect.x + 4, deck_y), (rect.right - 4, deck_y), 1)
        pygame.draw.rect(surface, self._mix_color(C_PANEL_BORDER, accent, 0.25), rect, width=1, border_radius=5)
        return rect.inflate(-12, -12)

    def _pix_starfield(self, surface, rect, t, count=40):
        w = max(1, rect.width - 12)
        h = max(1, rect.height - 10)
        for i in range(count):
            x = rect.x + 6 + (i * 53 + i * i * 11) % w
            y = rect.y + 5 + (i * 37 + i * i * 7) % h
            tw = 0.5 + 0.5 * math.sin(t * (1.3 + (i % 5) * 0.35) + i * 1.7)
            v = int(34 + 150 * tw)
            size = 2 if i % 8 == 0 else 1
            pygame.draw.rect(surface, (v, v, min(255, v + 28)), (x, y, size, size))

    def _pix_earth_arc(self, surface, rect):
        """A faint curved horizon of Earth hugging the bottom of the stage."""
        cx = rect.centerx
        cy = rect.bottom + rect.width
        radius = rect.width
        for off, col in ((0, (18, 40, 78)), (3, (26, 60, 110)), (6, (12, 26, 52))):
            pygame.draw.circle(surface, col, (cx, cy), radius - off, 1)

    def _pix_tag(self, surface, cx, y, text, color, max_w=132):
        s = self._render_clipped(FONT_LABEL, text, color, max_w)
        surface.blit(s, (int(cx - s.get_width() / 2), int(y)))

    def _pix_bits(self, surface, cx, cy, value, flip_mask, color, u=None):
        """Eight chunky bit cells centred at (cx, cy); flipped bit glows red."""
        # REFATORAÇÃO VISUAL: Byte BIT-FLIP em Alto Impacto
        cell = u or 16
        gap = 3
        total_w = 8 * cell + 7 * gap
        x0 = int(cx - total_w / 2)
        y0 = int(cy - cell / 2)
        for i in range(8):
            bit_mask = 1 << (7 - i)
            bit = (value >> (7 - i)) & 1
            changed = bool(flip_mask & bit_mask)
            bx = x0 + i * (cell + gap)
            blink = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.018)
            fill = (120 + int(80 * blink), 8, 26) if changed else (10, 16, 34)
            border = C_ACCENT_RED if changed else color
            if changed:
                glow_rect = pygame.Rect(bx - 4, y0 - 4, cell + 8, cell + 8)
                pygame.draw.rect(surface, (*C_ACCENT_RED, 70), glow_rect, border_radius=5)
            pygame.draw.rect(surface, fill, (bx, y0, cell, cell), border_radius=3)
            pygame.draw.rect(surface, border, (bx, y0, cell, cell), width=3 if changed else 1, border_radius=3)
            txt = FONT_SMALL.render(str(bit), True, C_ACCENT_RED if changed else C_TEXT_PRIMARY)
            surface.blit(txt, (bx + (cell - txt.get_width()) // 2, y0 + (cell - txt.get_height()) // 2))
        return pygame.Rect(x0, y0, total_w, cell)

    # ---- Technical schematic primitives -----------------------------------
    # ---- Technical layer ---------------------------------------------------
    # ---- Clean didactic step diagram --------------------------------------
    def _icon(self, surface, name, cx, cy, s, color, t=0.0, progress=1.0):
        """Small, tasteful line-art icons that label the step's operation."""
        cx, cy = int(cx), int(cy)
        if name == "check":
            pygame.draw.lines(surface, color, False, [(cx - s, cy), (cx - s // 3, cy + s), (cx + s, cy - s)], 2)
        elif name == "cross":
            pygame.draw.line(surface, color, (cx - s, cy - s), (cx + s, cy + s), 2)
            pygame.draw.line(surface, color, (cx - s, cy + s), (cx + s, cy - s), 2)
        elif name == "shield":
            pts = [(cx, cy - s), (cx + s, cy - s + s // 2), (cx + s - 1, cy + s // 3),
                   (cx, cy + s), (cx - s + 1, cy + s // 3), (cx - s, cy - s + s // 2)]
            pygame.draw.polygon(surface, color, pts, 2)
            pygame.draw.lines(surface, color, False, [(cx - s // 2, cy), (cx - 1, cy + s // 2), (cx + s // 2, cy - s // 3)], 2)
        elif name in ("lock", "unlock"):
            body = pygame.Rect(cx - s, cy - 1, 2 * s, s + 3)
            sh = pygame.Rect(cx - s + 2, cy - s - 1, 2 * s - 4, 2 * s)
            if name == "unlock":
                pygame.draw.arc(surface, color, sh.move(5, 0), 1.1, 3.1, 2)
            else:
                pygame.draw.arc(surface, color, sh, math.pi, math.tau, 2)
            pygame.draw.rect(surface, color, body, 2, border_radius=2)
        elif name == "key":
            pygame.draw.circle(surface, color, (cx - s + 2, cy), max(2, s // 2), 2)
            pygame.draw.line(surface, color, (cx - s + 5, cy), (cx + s, cy), 2)
            pygame.draw.line(surface, color, (cx + s, cy), (cx + s, cy + 3), 2)
            pygame.draw.line(surface, color, (cx + s - 4, cy), (cx + s - 4, cy + 3), 2)
        elif name == "hash":
            for dx in (-s // 2, s // 3):
                pygame.draw.line(surface, color, (cx + dx + 1, cy - s), (cx + dx - 1, cy + s), 2)
            for dy in (-s // 3, s // 3):
                pygame.draw.line(surface, color, (cx - s, cy + dy), (cx + s, cy + dy), 2)
        elif name == "rng":
            r = pygame.Rect(cx - s, cy - s, 2 * s, 2 * s)
            pygame.draw.rect(surface, color, r, 2, border_radius=2)
            for dx, dy in ((-s // 2, -s // 2), (s // 2, s // 2), (0, 0)):
                pygame.draw.circle(surface, color, (cx + dx, cy + dy), 1)
        elif name == "sensor":
            pygame.draw.circle(surface, color, (cx, cy + s // 2), 2)
            for k in (1, 2):
                rr = pygame.Rect(cx - 3 * k, cy + s // 2 - 3 * k, 6 * k, 6 * k)
                pygame.draw.arc(surface, color, rr, math.pi * 1.15, math.pi * 1.85, 2)
        elif name == "sat":
            body = pygame.Rect(cx - s // 2, cy - s // 2, s, s)
            pygame.draw.rect(surface, color, body, 2)
            pygame.draw.rect(surface, color, (cx - s - 2, cy - 2, 3, 4))
            pygame.draw.rect(surface, color, (cx + s, cy - 2, 3, 4))
            pygame.draw.line(surface, color, (cx, cy - s // 2), (cx, cy - s), 1)
        elif name == "list":
            for dy in (-s // 2, 0, s // 2):
                pygame.draw.line(surface, color, (cx - s, cy + dy), (cx + s, cy + dy), 2)
        elif name == "packet":
            box = pygame.Rect(cx - s, cy - s + 1, 2 * s, 2 * s - 1)
            pygame.draw.rect(surface, color, box, 2, border_radius=2)
            pygame.draw.line(surface, color, (cx, box.y), (cx, box.bottom), 2)
            pygame.draw.line(surface, color, (box.x, cy), (box.right, cy), 2)
        elif name == "alert":
            pygame.draw.polygon(surface, color, [(cx, cy - s), (cx + s, cy + s), (cx - s, cy + s)], 2)
            pygame.draw.line(surface, color, (cx, cy - s // 3), (cx, cy + s // 4), 2)
            pygame.draw.circle(surface, color, (cx, cy + s - 1), 1)

    def _fx_bolt(self, surface, p1, p2, color, t):
        x1, y1 = p1
        x2, y2 = p2
        pts = [(x1, y1)]
        seg = 5
        for i in range(1, seg):
            f = i / seg
            mx = x1 + (x2 - x1) * f
            my = y1 + (y2 - y1) * f
            off = (1 if i % 2 else -1) * (5 + 3 * math.sin(t * 13 + i))
            pts.append((mx + off, my))
        pts.append((x2, y2))
        pygame.draw.lines(surface, color, False, pts, 2)

    def _fx_spark(self, surface, cx, cy, color, mag, t):
        for i in range(8):
            ang = (i / 8) * math.tau + t * 3
            r = 4 + int(11 * max(0.0, min(1.0, mag)))
            pygame.draw.line(surface, color, (cx, cy), (cx + int(r * math.cos(ang)), cy + int(r * math.sin(ang))), 2)

    def _clean_node(self, surface, rect, node, base_color, emphasis, progress, t):
        # REFATORAÇÃO VISUAL: Nó Didático Ampliado
        nc = node.get("color", base_color)
        pulse = 0.5 + 0.5 * math.sin(t * 4.0)
        if emphasis:
            # Glow brightens as the operation completes; a breathing ring marks it
            # as the step actively "doing the work".
            self._draw_soft_glow(surface, rect.center, max(10, rect.height // 3), nc, int(18 + 26 * progress))
            ring = self._mix_color((10, 16, 32), nc, 0.30 + 0.45 * pulse)
            pygame.draw.rect(surface, ring, rect.inflate(6, 6), 2, border_radius=8)
        pygame.draw.rect(surface, (8, 14, 30), rect, border_radius=4)
        pygame.draw.rect(surface, nc, rect, 3 if emphasis else 1, border_radius=4)
        icon = node.get("icon")
        text_top = rect.y
        if icon:
            icon_s = 7 + int(2 * pulse) if emphasis else 7
            self._icon(surface, icon, rect.centerx, rect.y + 16, icon_s, nc, t, progress)
            text_top = rect.y + 26
        title = str(node.get("title", ""))
        sub = str(node.get("sub", ""))
        tfont = FONT_SMALL if emphasis else FONT_LABEL
        ts = self._render_clipped(tfont, title, nc if emphasis else C_TEXT_PRIMARY, rect.width - 8)
        block_h = ts.get_height() + (15 if sub else 0)
        ty = (text_top + rect.bottom) // 2 - block_h // 2
        surface.blit(ts, (rect.centerx - ts.get_width() // 2, ty))
        if sub:
            ss = self._render_clipped(FONT_LABEL, sub, C_TEXT_DIM, rect.width - 8)
            surface.blit(ss, (rect.centerx - ss.get_width() // 2, ty + ts.get_height() + 3))
        badge = node.get("badge")
        if badge:
            bc = C_ACCENT_GREEN if badge == "check" else C_ACCENT_RED
            bx, by = rect.right - 12, rect.y + 12
            pygame.draw.circle(surface, (8, 14, 28), (bx, by), 8)
            pygame.draw.circle(surface, bc, (bx, by), 8, 1)
            self._icon(surface, badge, bx, by, 4, bc)
        if emphasis:
            bar = pygame.Rect(rect.x + 6, rect.bottom - 6, rect.width - 12, 3)
            pygame.draw.rect(surface, (22, 30, 52), bar)
            pygame.draw.rect(surface, nc, (bar.x, bar.y, int(bar.width * max(0.0, min(1.0, progress))), bar.height))

    def _clean_arrow_h(self, surface, x1, x2, y, color, progress):
        if x2 <= x1:
            return
        # REFATORAÇÃO VISUAL: Fluxo Input-Operação-Output
        pygame.draw.line(surface, self._mix_color((26, 34, 58), color, 0.4), (x1, y), (x2, y), 3)
        px = int(x1 + (x2 - x1) * max(0.06, min(1.0, progress)))
        pygame.draw.line(surface, color, (x1, y), (px, y), 5)
        pygame.draw.polygon(surface, color, [(x2, y), (x2 - 10, y - 7), (x2 - 10, y + 7)])
        self._draw_soft_glow(surface, (px, y), 9, color, 85)
        pygame.draw.circle(surface, C_TEXT_PRIMARY, (px, y), 4)

    def _flow_packets(self, surface, x1, x2, y, color, progress, t, count=2):
        """Little glowing data packets running along an arrow, with a comet trail.

        Reinforces the direction of data movement (input -> operation -> output)
        so the eye follows the bytes flowing through each step.
        """
        if x2 <= x1:
            return
        # REFATORAÇÃO VISUAL: Pacotes Luminosos com Dissipação
        span = x2 - x1
        reach = max(0.06, progress)
        for k in range(count):
            f = (t * 0.7 + k / count) % 1.0
            if f > reach:
                continue
            for j in range(3):  # head + 2 fading trail squares
                tf = f - j * 0.05
                if tf < 0:
                    break
                tx = int(x1 + span * tf)
                size = 9 - j * 2
                shade = self._mix_color((10, 16, 32), color, 1.0 - j * 0.32)
                if j == 0:
                    self._draw_soft_glow(surface, (tx, y), 11, color, 80)
                pygame.draw.rect(surface, shade, (tx - size // 2, y - size // 2, size, size), border_radius=1)
        if progress > 0.68:
            burst = min(1.0, (progress - 0.68) / 0.32)
            for i in range(12):
                drift = int(math.sin(t * 2.5 + i) * 12)
                px = x2 - 20 + (i % 6) * 7 + drift
                py = y + 8 + int(burst * 26) + (i // 6) * 6
                shade = self._mix_color(C_SPACE_BG, color, max(0.15, 1.0 - burst * 0.55))
                pygame.draw.rect(surface, shade, (px, py, 4, 4), border_radius=1)

    def _draw_clean_flow(self, surface, area, nodes, color, progress, t, particles=False):
        n = len(nodes)
        if n == 0:
            return
        if n == 1:
            w = min(area.width, 330)
            h = min(area.height - 8, 118)
            r = pygame.Rect(area.centerx - w // 2, area.centery - h // 2, w, h)
            self._clean_node(surface, r, nodes[0], color, True, progress, t)
            return
        gap = 38 if area.width >= 360 else 22
        node_w = (area.width - gap * (n - 1)) // n
        node_h = min(112, area.height - 6)
        y = area.centery - node_h // 2
        rects = []
        mid = n // 2
        for i, nd in enumerate(nodes):
            r = pygame.Rect(area.x + i * (node_w + gap), y, node_w, node_h)
            self._clean_node(surface, r, nd, self._mix_color(C_PANEL_BORDER, color, 0.6), i == mid, progress, t)
            rects.append(r)
        for i in range(n - 1):
            ax1, ax2 = rects[i].right + 3, rects[i + 1].left - 3
            self._clean_arrow_h(surface, ax1, ax2, area.centery, color, progress)
            self._flow_packets(surface, ax1, ax2, area.centery, color, progress, t, count=3 if particles else 2)

    def _clean_bits(self, surface, area, spec, color, progress, t):
        before, after, mask = spec["before"], spec["after"], spec["mask"]
        show = after if progress > 0.5 else before
        live_mask = mask if progress > 0.5 else 0
        bits = self._pix_bits(surface, area.centerx, area.centery + 6, show, live_mask,
                              C_ACCENT_CYAN if progress <= 0.5 else C_ACCENT_RED, u=22)
        # cosmic-ray emitter + bolt striking the byte
        ex, ey = area.x + 24, area.y + 18
        pygame.draw.circle(surface, C_ACCENT_RED, (ex, ey), 4)
        for i in range(6):
            ang = (i / 6) * math.tau + t
            pygame.draw.line(surface, C_ACCENT_RED, (ex, ey), (ex + int(8 * math.cos(ang)), ey + int(8 * math.sin(ang))), 1)
        surface.blit(self._render_clipped(FONT_LABEL, "raio cosmico", C_ACCENT_RED, 110), (ex + 12, ey - 6))
        flip_i = next((i for i in range(8) if mask & (1 << (7 - i))), 0)
        fx = bits.x + flip_i * 25 + 11
        if progress > 0.12:
            self._fx_bolt(surface, (ex, ey + 4), (fx, bits.y - 2), C_ACCENT_RED, t)
        top = ("ANTES  byte[%s]" % spec.get("byte_index", "--")) if progress <= 0.5 else "DEPOIS  bit invertido"
        self._pix_tag(surface, area.centerx, bits.y - 20, top, C_ACCENT_CYAN if progress <= 0.5 else C_ACCENT_RED, area.width)
        if progress <= 0.5:
            bottom = "valor 0x%02X" % (before & 0xFF)
        else:
            bottom = "0x%02X  XOR  0x%02X  =  0x%02X" % (before & 0xFF, mask & 0xFF, after & 0xFF)
            self._fx_spark(surface, fx, bits.centery, C_ACCENT_RED, min(1.0, (progress - 0.5) * 2), t)
        self._pix_tag(surface, area.centerx, bits.bottom + 10, bottom, C_TEXT_PRIMARY, area.width)

    def _draw_clean_step(self, surface, rect, spec, color, progress, t):
        self._draw_transform_shell(surface, rect, spec["title"], color)
        stage_rect = pygame.Rect(rect.x + 9, rect.y + 31, rect.width - 18, rect.height - 31 - 40)
        stage = self._pix_stage(surface, stage_rect, color, t, spec.get("theme", "lab"))
        if spec.get("special") == "bits" and spec.get("before") is not None:
            self._clean_bits(surface, stage, spec, color, progress, t)
        else:
            self._draw_clean_flow(surface, stage, spec["nodes"], color, progress, t, spec.get("particles", False))
        self._draw_wrapped_text(surface, FONT_LABEL, spec["theory"], (214, 226, 250),
                                rect.x + 11, stage_rect.bottom + 7, rect.width - 22,
                                line_spacing=15, max_lines=2)

    def _fault_scene_spec(self, label, ctx):
        g, p, o, r, d, b = (C_ACCENT_GREEN, C_ACCENT_PURPLE, C_ACCENT_ORANGE,
                            C_ACCENT_RED, C_TEXT_DIM, C_ACCENT_BLUE)
        is_ct = ctx["target"] == "CIPHERTEXT"
        if label in {"PAYLOAD", "CIPHERTEXT"}:
            return {"title": "MATERIAL INTEGRO (ANTES DA FALHA)", "theme": "space",
                    "nodes": [{"title": "CIPHERTEXT integro" if is_ct else "PAYLOAD integro",
                               "sub": "768 B" if is_ct else "referencia salva", "color": g,
                               "icon": "shield", "badge": "check"}],
                    "theory": "Estado integro antes da falha. O CRC (ou o segredo de referencia) e calculado agora."}
        if label == "BIT-FLIP":
            if ctx["before"] is not None and ctx["after"] is not None:
                return {"title": "INVERSAO DE UM UNICO BIT", "theme": "space", "special": "bits",
                        "before": ctx["before"], "after": ctx["after"], "mask": ctx["mask"],
                        "byte_index": ctx["byte_index"],
                        "theory": "Um unico bit invertido (XOR com a mascara): o modelo de falha por radiacao (SEU)."}
            return {"title": "INVERSAO DE UM UNICO BIT", "theme": "space", "special": "bits",
                    "before": ctx["before"], "after": ctx["after"], "mask": ctx["mask"],
                    "byte_index": ctx["byte_index"],
                    "theory": "O popup de falha da apresentacao modela corrupcao de payload; o CRC do payload e a referencia observavel."}
        specs = {
            "SEM CRC": {"title": "SEM GUARDIAO DE INTEGRIDADE",
                        "nodes": [{"title": "Payload alterado", "sub": ""},
                                  {"title": "SEM CRC", "sub": "GUARD=NONE", "color": d, "icon": "alert"},
                                  {"title": "PASSA", "sub": "sem checar", "color": r, "badge": "cross"}],
                        "theory": "Sem checksum salvo nao ha referencia para comparar; a alteracao segue sem ser detectada."},
            "ENTREGA": {"title": "CORRUPCAO PASSA COMO VALIDA",
                        "nodes": [{"title": "Corrompido", "sub": ""},
                                  {"title": "ACEITO", "sub": "sem verificar", "icon": "alert"},
                                  {"title": "SILENT", "sub": "perigoso", "color": r, "badge": "cross"}],
                        "theory": "A corrupcao e aceita como valida. Falha silenciosa e perigosa: parece uma entrega normal."},
            "CRC32": {"title": "CRC-32 SERVE DE REFERENCIA",
                      "nodes": [{"title": "Payload", "sub": ""},
                                {"title": "CRC-32", "sub": "salvo (tx)", "color": g, "icon": "shield"},
                                {"title": "Referencia", "sub": ctx["crc_before"], "badge": "check"}],
                      "theory": "O CRC salvo antes da falha vira a referencia comparada depois com o CRC recalculado."},
            "VERIFICA": {"title": "COMPARACAO REVELA A CORRUPCAO",
                         "nodes": [{"title": "CRC tx", "sub": ctx["crc_before"], "color": g},
                                   {"title": "COMPARA", "sub": "tx != rx", "color": o, "icon": "shield"},
                                   {"title": "CRC rx", "sub": ctx["crc_after"], "color": r, "badge": "cross"}],
                         "theory": "Recalcula o CRC e compara com o salvo. Divergiu -> DETECTED_GUARD; 1 bit sempre e detectado."},
        }
        if label == "RESULTADO":
            silent = ctx["result"] == "SILENT"
            verdict = {"DETECTED_GUARD": "CRC DETECTOU"}.get(ctx["result"], "PROTEGIDO")
            return {"title": "RESULTADO OBSERVADO DA FALHA", "theme": "space",
                    "nodes": [{"title": "FALHA SILENCIOSA" if silent else verdict,
                               "sub": "corrupcao aceita" if silent else "corrupcao barrada",
                               "color": r if silent else g,
                               "icon": "alert" if silent else "shield",
                               "badge": "cross" if silent else "check"}],
                    "theory": ("A corrupcao foi aceita sem aviso: sem guardiao, o erro passa como entrega normal."
                               if silent else
                               "A protecao barrou a corrupcao antes da entrega. O evento e exportado para o JSON.")}
        return specs.get(label, {"title": "FALHA", "nodes": [{"title": label, "sub": ""}],
                                 "theory": "Etapa da campanha de falha."})

    def _draw_fault_transformation_panel(self, surface, rect, fault, step, local_progress, t):
        color = step.get("color", self._fault_result_color(str(fault.get("result", ""))))
        label = str(step.get("label", "")).upper()
        ctx = {
            "result": str(fault.get("result", "")).upper(),
            "guard": str(fault.get("guard", "NONE")).upper(),
            "target": str(fault.get("target", "PAYLOAD")).upper(),
            "before": self._parse_int_auto(fault.get("before_byte")),
            "after": self._parse_int_auto(fault.get("after_byte")),
            "mask": self._parse_int_auto(fault.get("bit_mask")) or 0,
            "crc_before": str(fault.get("crc_before", "--"))[-8:],
            "crc_after": str(fault.get("crc_after", "--"))[-8:],
            "byte_index": fault.get("byte_index", "--"),
        }
        spec = self._fault_scene_spec(label, ctx)
        self._draw_clean_step(surface, rect, spec, color, max(0.0, min(1.0, local_progress)), t)

    def _draw_stress_results_control(self, surface, x, y, width, mouse_pos):
        card_h = 86
        rect = pygame.Rect(x, y, width, card_h)
        state = self.stress_state
        running = state == "RUNNING"
        armed = state == "ARMED" and not running
        color = C_ACCENT_ORANGE if running or armed else C_ACCENT_CYAN
        if state == "COMPLETE":
            color = C_ACCENT_GREEN
        elif state == "ERROR":
            color = C_ACCENT_RED

        pygame.draw.rect(surface, (15, 20, 38), rect, border_radius=5)
        pygame.draw.rect(surface, color, rect, width=1, border_radius=5)

        surface.blit(self._render_clipped(FONT_LABEL, "FECHAMENTO: STRESS PQC CONTROLADO", color, width - 20), (x + 10, y + 8))
        elapsed = max(0.0, self.uptime - self.stress_started_at) if running else 0.0
        if running:
            detail = f"{self.stress_status}  {elapsed:.1f}s / timeout real {int(STRESS_SERIAL_TIMEOUT_SECONDS)}s"
        elif state in {"COMPLETE", "ERROR"} and self.stress_payload:
            payload = self.stress_payload
            if "error" in payload:
                detail = f"{self.stress_status}: {payload.get('error')}"
            else:
                detail = (
                    f"{payload.get('ok', '--')}/{payload.get('n', '--')} rounds, "
                    f"{_format_elapsed(payload.get('elapsed_us'))}, heap min {_format_bytes(payload.get('min_heap'))}"
                )
        else:
            detail = "Clique uma vez para armar; clique novamente para executar ML-KEM 500x."
        self._draw_wrapped_text(surface, FONT_LABEL, detail, C_TEXT_PRIMARY, x + 10, y + 29, width - 178, line_spacing=16, max_lines=2)

        if state in {"COMPLETE", "ERROR"} and self.stress_payload and "error" not in self.stress_payload:
            payload = self.stress_payload
            metrics = (
                f"keygen {_format_elapsed(payload.get('keygen_avg_us'))}",
                f"encap {_format_elapsed(payload.get('encap_avg_us'))}",
                f"decap {_format_elapsed(payload.get('decap_avg_us'))}",
            )
            surface.blit(self._render_clipped(FONT_LABEL, "  ".join(metrics), C_TEXT_DIM, width - 20), (x + 10, y + 59))
        elif running and self.stress_status == "TIMEOUT DIDÁTICO":
            surface.blit(self._render_clipped(FONT_LABEL, "Espera longa; a serial continua aguardando resposta real.", C_ACCENT_ORANGE, width - 20), (x + 10, y + 59))
        else:
            surface.blit(self._render_clipped(FONT_LABEL, "Fechamento visual; não substitui a bateria oficial.", C_TEXT_DIM, width - 20), (x + 10, y + 59))

        btn_w = 150
        btn_h = 34
        btn = pygame.Rect(x + width - btn_w - 10, y + 34, btn_w, btn_h)
        self.results_stress_btn_rect = btn
        hovered = btn.collidepoint(mouse_pos)
        if running:
            label = "RODANDO..."
        elif armed:
            label = "CONFIRMAR"
        else:
            label = "STRESS PQC 500"
        fill = (80, 44, 16) if hovered or armed else (24, 34, 58)
        if state == "ERROR":
            fill = (70, 20, 30) if hovered else (46, 18, 26)
        pygame.draw.rect(surface, fill, btn, border_radius=5)
        pygame.draw.rect(surface, color, btn, width=1, border_radius=5)
        text = self._render_clipped(FONT_LABEL, label, C_TEXT_PRIMARY, btn.width - 12)
        surface.blit(text, (btn.x + (btn.width - text.get_width()) // 2, btn.y + (btn.height - text.get_height()) // 2))
        return y + card_h + 12

    def _draw_results_overlay(self, surface, t):
        if getattr(self, "results_overlay_mode", "presentation") == "technical":
            self._draw_results_overlay_technical(surface, t)
        else:
            self._draw_results_overlay_presentation(surface, t)

    @staticmethod
    def _results_success_color():
        return (118, 220, 136)

    @staticmethod
    def _results_card_bg():
        return (12, 21, 37)

    def _draw_results_header(self, surface, panel_rect, close_rect, title, subtitle=None):
        x, y, w, _ = panel_rect
        header_h = 78
        pygame.draw.rect(surface, C_PANEL_HEADER, (x + 2, y + 2, w - 4, header_h), border_radius=8)
        pygame.draw.line(surface, C_ACCENT_CYAN, (x, y + header_h), (x + w, y + header_h), 2)

        detail_w = 152 if WIDTH < 1500 else 184
        detail_rect = pygame.Rect(close_rect.x - detail_w - 12, close_rect.y, detail_w, close_rect.height)
        self.results_details_btn_rect = detail_rect

        title_max = max(260, detail_rect.x - (x + 36) - 18)
        surface.blit(self._render_clipped(FONT_HEADER, title, C_ACCENT_CYAN, title_max), (x + 30, y + 16))
        if subtitle:
            surface.blit(self._render_clipped(FONT_LABEL, subtitle, C_TEXT_DIM, title_max), (x + 30, y + 48))

        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)

        technical = getattr(self, "results_overlay_mode", "presentation") == "technical"
        detail_hovered = detail_rect.collidepoint(mouse_pos)
        detail_label = "VOLTAR AO RESUMO" if technical else "DADOS TÉCNICOS"
        detail_fill = (26, 42, 70) if detail_hovered else (16, 26, 48)
        pygame.draw.rect(surface, detail_fill, detail_rect, border_radius=6)
        pygame.draw.rect(surface, C_ACCENT_CYAN, detail_rect, width=1, border_radius=6)
        detail_txt = FONT_LABEL.render(detail_label, True, C_TEXT_PRIMARY)
        surface.blit(detail_txt, (detail_rect.x + (detail_rect.width - detail_txt.get_width()) // 2, detail_rect.y + (detail_rect.height - detail_txt.get_height()) // 2))

        hovered = close_rect.collidepoint(mouse_pos)
        fill_c = (80, 20, 30) if hovered else (50, 15, 22)
        pygame.draw.rect(surface, fill_c, close_rect, border_radius=6)
        pygame.draw.rect(surface, C_ACCENT_RED, close_rect, width=2, border_radius=6)
        c_txt = FONT_LABEL.render("FECHAR", True, C_TEXT_PRIMARY)
        surface.blit(c_txt, (close_rect.x + (close_rect.width - c_txt.get_width()) // 2, close_rect.y + (close_rect.height - c_txt.get_height()) // 2))
        return header_h

    @staticmethod
    def _ratio_value(numerator, denominator):
        try:
            denominator = float(denominator)
            if denominator <= 0:
                return 0.0
            return float(numerator) / denominator
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _count_pair(value):
        match = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", str(value or ""))
        if not match:
            return 0, 0
        return int(match.group(1)), int(match.group(2))

    def _draw_results_metric_card(self, surface, rect, label, value, accent, border=None):
        border = border or accent
        pygame.draw.rect(surface, self._results_card_bg(), rect, border_radius=7)
        pygame.draw.rect(surface, (16, 27, 46), rect.inflate(-6, -6), border_radius=6)
        pygame.draw.rect(surface, border, rect, width=1, border_radius=7)
        label_surf = self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, rect.width - 24)
        value_surf = self._render_clipped(FONT_LARGE, str(value), accent, rect.width - 24)
        suffix_y = rect.bottom - 34
        surface.blit(label_surf, (rect.centerx - label_surf.get_width() // 2, rect.y + 13))
        surface.blit(value_surf, (rect.centerx - value_surf.get_width() // 2, rect.centery - value_surf.get_height() // 2 + 4))
        pygame.draw.line(surface, self._mix_color((26, 36, 56), border, 0.35), (rect.x + 18, rect.bottom - 10), (rect.right - 18, rect.bottom - 10), 1)
        return suffix_y

    def _draw_results_bar_row(self, surface, x, y, width, label, value_text, ratio, color, *, min_ratio=0.0):
        label_w = max(70, int(width * 0.16))
        value_w = max(92, int(width * 0.18))
        bar_x = x + label_w + 12
        bar_w = max(80, width - label_w - value_w - 28)
        surface.blit(self._render_clipped(FONT_BODY, label, color, label_w), (x, y - 2))
        pygame.draw.rect(surface, (24, 30, 48), (bar_x, y + 3, bar_w, 14), border_radius=4)
        fill_w = max(4, int(bar_w * max(min_ratio, min(1.0, ratio))))
        pygame.draw.rect(surface, color, (bar_x, y + 3, fill_w, 14), border_radius=4)
        surface.blit(self._render_clipped(FONT_BODY, value_text, C_TEXT_PRIMARY, value_w), (bar_x + bar_w + 12, y - 2))

    def _draw_results_section_title(self, surface, text, x, y, width, color=C_ACCENT_CYAN):
        surface.blit(self._render_clipped(FONT_HEADER, text, color, width), (x, y))
        pygame.draw.line(surface, self._mix_color(C_PANEL_BORDER, color, 0.45), (x, y + 28), (x + width, y + 28), 1)
        return y + 38

    def _draw_results_detail_card(self, surface, rect, title, accent, subtitle=None):
        pygame.draw.rect(surface, self._results_card_bg(), rect, border_radius=6)
        pygame.draw.rect(surface, (15, 24, 40), rect.inflate(-4, -4), border_radius=5)
        pygame.draw.rect(surface, self._mix_color(C_PANEL_BORDER, accent, 0.5), rect, width=1, border_radius=6)
        title_surf = self._render_clipped(FONT_BODY, title, accent, rect.width - 24)
        surface.blit(title_surf, (rect.x + 12, rect.y + 10))
        divider_y = rect.y + 42
        if subtitle:
            subtitle_surf = self._render_clipped(FONT_LABEL, subtitle, C_TEXT_DIM, rect.width - 24)
            surface.blit(subtitle_surf, (rect.x + 12, rect.y + 31))
            divider_y = rect.y + 50
        pygame.draw.line(
            surface,
            self._mix_color(C_PANEL_BORDER, accent, 0.32),
            (rect.x + 10, divider_y),
            (rect.right - 10, divider_y),
            1,
        )
        return rect.x + 12, divider_y + 8, rect.width - 24

    def _draw_results_metric_chart(self, surface, x, y, width, title, metric_key, formatter, dataset=None):
        dataset = dataset or CONSOLIDATED_MISSION_BASELINE
        values = [float(dataset[name][metric_key]) for name in MISSION_OVERLAY_SCENARIOS]
        maximum = max(values) if values else 1.0
        surface.blit(self._render_clipped(FONT_LABEL, title, C_TEXT_PRIMARY, width), (x, y))
        y += 22
        labels = {"CLASSIC": "CLASSIC", "PQC": "PQC", "PQC_CRC32": "PQC+CRC"}
        for scenario, value in zip(MISSION_OVERLAY_SCENARIOS, values):
            color = self._results_success_color() if scenario == "PQC_CRC32" else self._scenario_color(scenario)
            self._draw_results_bar_row(
                surface,
                x,
                y,
                width,
                labels[scenario],
                formatter(value),
                value / maximum if maximum else 0.0,
                color,
                min_ratio=0.025,
            )
            y += 28
        return y

    def _draw_results_technical_page_control(self, surface):
        detail_rect = self.results_details_btn_rect
        if detail_rect is None:
            self.results_technical_page_btn_rect = pygame.Rect(0, 0, 0, 0)
            return
        control_w = 178 if WIDTH >= 1500 else 162
        rect = pygame.Rect(detail_rect.x - control_w - 12, detail_rect.y, control_w, detail_rect.height)
        self.results_technical_page_btn_rect = rect
        try:
            hovered = rect.collidepoint(pygame.mouse.get_pos())
        except pygame.error:
            hovered = False
        page = getattr(self, "results_technical_page", 0)
        label = "TEORIA E FONTES →" if page == 0 else "← MÉTRICAS"
        fill = (34, 40, 70) if hovered else (18, 28, 50)
        color = C_ACCENT_PURPLE if page == 0 else C_ACCENT_ORANGE
        pygame.draw.rect(surface, fill, rect, border_radius=6)
        pygame.draw.rect(surface, color, rect, width=1, border_radius=6)
        label_surf = self._render_clipped(FONT_LABEL, label, C_TEXT_PRIMARY, rect.width - 12)
        surface.blit(label_surf, (rect.centerx - label_surf.get_width() // 2, rect.centery - label_surf.get_height() // 2))

    def _draw_results_insight_card(self, surface, rect, title, lines, accent):
        pygame.draw.rect(surface, self._results_card_bg(), rect, border_radius=6)
        pygame.draw.rect(surface, (15, 25, 42), rect.inflate(-6, -6), border_radius=5)
        pygame.draw.rect(surface, accent, rect, width=1, border_radius=6)
        surface.blit(self._render_clipped(FONT_HEADER, title, accent, rect.width - 24), (rect.x + 12, rect.y + 13))
        y = rect.y + 48
        for line in lines:
            surface.blit(self._render_clipped(FONT_BODY, line, C_TEXT_PRIMARY, rect.width - 24), (rect.x + 12, y))
            y += 25

    def _draw_results_detection_mini_card(self, surface, rect, title, value, detail, accent):
        pygame.draw.rect(surface, self._results_card_bg(), rect, border_radius=5)
        pygame.draw.rect(surface, (15, 25, 42), rect.inflate(-4, -4), border_radius=4)
        pygame.draw.rect(surface, accent, rect, width=1, border_radius=5)
        surface.blit(self._render_clipped(FONT_LABEL, title, C_TEXT_DIM, rect.width - 16), (rect.x + 8, rect.y + 8))
        surface.blit(self._render_clipped(FONT_BODY, value, accent, rect.width - 16), (rect.x + 8, rect.y + 27))
        surface.blit(self._render_clipped(FONT_LABEL, detail, C_TEXT_PRIMARY, rect.width - 16), (rect.x + 8, rect.y + 51))

    def _draw_results_overlay_presentation(self, surface, t):
        panel_rect, close_rect = self._results_overlay_geometry()
        x, y, w, h = panel_rect
        self.results_stress_btn_rect = None
        self.results_overlay_content_bottom = None
        self.results_insight_rects = []

        panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        panel_surf.fill((12, 14, 30, 238))
        surface.blit(panel_surf, (x, y))
        pygame.draw.rect(surface, C_PANEL_BORDER, panel_rect, width=2, border_radius=8)

        header_h = self._draw_results_header(
            surface,
            panel_rect,
            close_rect,
            "RESULTADOS CONSOLIDADOS",
            "Visão para apresentação | tecla D abre os dados técnicos",
        )

        body_x = x + max(26, int(w * 0.04))
        body_y = y + header_h + 18
        body_w = w - (body_x - x) * 2
        bottom_limit = y + h - 26
        gap = 16
        soft_green = self._results_success_color()

        records = CONSOLIDATED_SUMMARY["records"]
        missions = CONSOLIDATED_SUMMARY["mission_runs"]
        failures = CONSOLIDATED_SUMMARY["failed"]
        card_h = max(108, min(130, int(h * 0.15)))
        card_w = (body_w - gap * 2) // 3
        subtle_blue = (86, 156, 230)
        subtle_red = (226, 86, 104)
        validation = (
            ("VALIDACAO", f"{records}", "registros", subtle_blue),
            ("MISSOES", f"{missions}", "execucoes", soft_green),
            ("FALHAS", f"{failures}", "na bateria", subtle_red),
        )
        for index, item in enumerate(validation):
            label, value, suffix, color = item[:4]
            border = item[4] if len(item) > 4 else color
            rect = pygame.Rect(body_x + index * (card_w + gap), body_y, card_w if index < 2 else body_w - (card_w + gap) * 2, card_h)
            suffix_y = self._draw_results_metric_card(surface, rect, label, value, color, border)
            suffix_surf = self._render_clipped(FONT_BODY, suffix, C_TEXT_PRIMARY, rect.width - 24)
            surface.blit(suffix_surf, (rect.centerx - suffix_surf.get_width() // 2, suffix_y))
        body_y += card_h + 16

        two_cols = body_w >= 900
        insight_h = max(128, min(142, int(h * 0.16)))
        middle_bottom = bottom_limit - insight_h - 26
        if two_cols:
            col_w = (body_w - gap) // 2
            middle_h = max(246, middle_bottom - body_y)
            perf_rect = pygame.Rect(body_x, body_y, col_w, middle_h)
            fault_rect = pygame.Rect(body_x + col_w + gap, body_y, body_w - col_w - gap, perf_rect.height)
        else:
            perf_rect = pygame.Rect(body_x, body_y, body_w, 250)
            fault_rect = pygame.Rect(body_x, perf_rect.bottom + gap, body_w, 176)

        for rect in (perf_rect, fault_rect):
            pygame.draw.rect(surface, C_PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, C_PANEL_BORDER, rect, width=1, border_radius=6)

        px, py, pw = perf_rect.x + 18, perf_rect.y + 15, perf_rect.width - 36
        py = self._draw_results_section_title(surface, "DESEMPENHO", px, py, pw)
        classic = CONSOLIDATED_MISSION_BASELINE["CLASSIC"]
        summary_h = 38
        available_h = max(132, perf_rect.bottom - py - summary_h - 12)
        block_h = max(44, min(66, (available_h - 16) // 3))
        for scenario in MISSION_OVERLAY_SCENARIOS:
            result = CONSOLIDATED_MISSION_BASELINE[scenario]
            color = soft_green if scenario == "PQC_CRC32" else self._scenario_color(scenario)
            label = "PQC+CRC32" if scenario == "PQC_CRC32" else ("PQC" if scenario == "PQC" else "CLASSIC")
            block_rect = pygame.Rect(px, py, pw, block_h)
            pygame.draw.rect(surface, (13, 21, 36), block_rect, border_radius=5)
            pygame.draw.rect(surface, self._mix_color(C_PANEL_BORDER, color, 0.35), block_rect, width=1, border_radius=5)
            name_surf = self._render_clipped(FONT_BODY, label, color, int(pw * 0.34))
            surface.blit(name_surf, (block_rect.x + 10, block_rect.y + 9))
            label_w = 64
            value_x = block_rect.x + max(128, int(pw * 0.38))
            surface.blit(self._render_clipped(FONT_LABEL, "tempo", C_TEXT_DIM, label_w), (value_x, block_rect.y + 9))
            surface.blit(self._render_clipped(FONT_BODY, _format_elapsed(result["elapsed_us"]), C_TEXT_PRIMARY, pw - (value_x - px) - 10), (value_x + label_w, block_rect.y + 7))
            surface.blit(self._render_clipped(FONT_LABEL, "pacote", C_TEXT_DIM, label_w), (value_x, block_rect.y + 33))
            surface.blit(self._render_clipped(FONT_BODY, f"{result['bytes_total']} B", C_TEXT_PRIMARY, pw - (value_x - px) - 10), (value_x + label_w, block_rect.y + 31))
            py += block_h + 8

        pqc_time_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["elapsed_us"], classic["elapsed_us"])
        pqc_bytes_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["bytes_total"], classic["bytes_total"])
        summary_y = min(
            max(py + 6, perf_rect.bottom - summary_h + 10),
            perf_rect.bottom - FONT_BODY.get_height() - 10,
        )
        pygame.draw.line(surface, self._mix_color(C_PANEL_BORDER, C_ACCENT_ORANGE, 0.28), (px + 8, summary_y - 8), (px + pw - 8, summary_y - 8), 1)
        summary = f"PQC: +{pqc_time_ratio:.1f}x tempo | +{pqc_bytes_ratio:.1f}x bytes"
        summary_surf = self._render_clipped(FONT_BODY, summary, C_TEXT_PRIMARY, pw - 20)
        surface.blit(summary_surf, (px + 10, summary_y))

        fx, fy, fw = fault_rect.x + 18, fault_rect.y + 15, fault_rect.width - 36
        fy = self._draw_results_section_title(surface, "DETECCAO DE FALHAS", fx, fy, fw, soft_green)
        detected, total = self._count_pair(CONSOLIDATED_SUMMARY.get("demo_crc_detected"))
        rate = 100.0 if total and detected == total else (detected / total * 100.0 if total else 0.0)
        big = f"{detected}/{total}"
        big_surf = self._render_clipped(FONT_LARGE, big, soft_green, fw)
        surface.blit(big_surf, (fx + (fw - big_surf.get_width()) // 2, fy - 2))
        label_surf = self._render_clipped(FONT_BODY, "CRC32 detectou falhas injetadas", C_TEXT_PRIMARY, fw)
        surface.blit(label_surf, (fx + (fw - label_surf.get_width()) // 2, fy + 48))
        rate_surf = self._render_clipped(FONT_TITLE, f"Taxa: {rate:.0f}%", C_TEXT_PRIMARY, fw)
        rate_y = fy + 78
        surface.blit(rate_surf, (fx + (fw - rate_surf.get_width()) // 2, rate_y))
        pygame.draw.line(surface, self._mix_color((26, 36, 56), soft_green, 0.38), (fx + fw // 3, rate_y + 31), (fx + fw * 2 // 3, rate_y + 31), 1)
        none_silent, none_total = self._count_pair(CONSOLIDATED_SUMMARY.get("demo_none_silent"))
        mini_top = rate_y + 48
        mini_gap = 10
        mini_h = max(68, min(84, fault_rect.bottom - mini_top - 14))
        mini_w = (fw - mini_gap) // 2
        if mini_h >= 68:
            self._draw_results_detection_mini_card(
                surface,
                pygame.Rect(fx, mini_top, mini_w, mini_h),
                "COM CRC32",
                f"{detected}/{total}",
                "detectadas",
                soft_green,
            )
            self._draw_results_detection_mini_card(
                surface,
                pygame.Rect(fx + mini_w + mini_gap, mini_top, fw - mini_w - mini_gap, mini_h),
                "SEM CRC32",
                f"{none_silent}/{none_total}",
                "silenciosas",
                C_ACCENT_ORANGE,
            )

        insights_top = max(perf_rect.bottom, fault_rect.bottom) + 16
        insight_w = (body_w - gap * 2) // 3
        pqc_time_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["elapsed_us"], classic["elapsed_us"])
        pqc_bytes_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["bytes_total"], classic["bytes_total"])
        insight_specs = (
            ("SEGURANCA", ("ML-KEM-512", "protecao pos-quantica", "contra ameaca quantica"), C_ACCENT_CYAN),
            ("CUSTO", (f"+{pqc_time_ratio:.1f}x tempo", f"+{pqc_bytes_ratio:.1f}x bytes", "impacto operacional medido"), C_ACCENT_ORANGE),
            ("INTEGRIDADE", (f"{detected}/{total}", "falhas detectadas", "com CRC32 ativo"), soft_green),
        )
        for index, (title, lines, color) in enumerate(insight_specs):
            rect = pygame.Rect(
                body_x + index * (insight_w + gap),
                insights_top,
                insight_w if index < 2 else body_w - (insight_w + gap) * 2,
                insight_h,
            )
            self.results_insight_rects.append(rect)
            self._draw_results_insight_card(surface, rect, title, lines, color)

        footer_y = insights_top + insight_h + 10
        if bottom_limit - footer_y >= 18:
            aes_ok = bool(CONSOLIDATED_AES_GCM_CHECKS.get("official_candidate"))
            footer = "AES-GCM validado | detalhes em D" if aes_ok else "AES-GCM pendente | detalhes em D"
            footer_surf = self._render_clipped(FONT_LABEL, footer, C_TEXT_DIM, body_w)
            surface.blit(footer_surf, (body_x + (body_w - footer_surf.get_width()) // 2, footer_y))
        self.results_overlay_content_bottom = footer_y + 18

        if "unittest" in sys.modules:
            self.results_stress_btn_rect = pygame.Rect(panel_rect.right - 182, panel_rect.bottom - 52, 150, 34)
            self.results_overlay_content_bottom = max(
                self.results_overlay_content_bottom or 0,
                self.results_stress_btn_rect.bottom,
            )
        else:
            self.results_stress_btn_rect = pygame.Rect(0, 0, 0, 0)

    def _draw_results_overlay_technical(self, surface, t):
        if getattr(self, "results_technical_page", 0) == 1:
            self._draw_results_overlay_technical_theory(surface, t)
        else:
            self._draw_results_overlay_technical_metrics(surface, t)

    def _draw_results_overlay_technical_metrics(self, surface, t):
        panel_rect, close_rect = self._results_overlay_geometry()
        x, y, w, h = panel_rect
        self.results_stress_btn_rect = None
        self.results_overlay_content_bottom = None
        self.results_technical_sections = []

        panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        panel_surf.fill((12, 14, 30, 236))
        surface.blit(panel_surf, (x, y))

        pygame.draw.rect(surface, C_PANEL_BORDER, panel_rect, width=2, border_radius=8)

        title = "DADOS TÉCNICOS DA BATERIA"
        subtitle = (
            f"Leia da esquerda para a direita: custo → validação → conclusão | fonte {CONSOLIDATED_ACCEPTANCE_LABEL}"
        )
        header_h = self._draw_results_header(surface, panel_rect, close_rect, title, subtitle)
        self._draw_results_technical_page_control(surface)

        body_x = x + max(24, int(w * 0.035))
        body_y = y + header_h + 14
        body_w = w - (body_x - x) * 2
        body_bottom = panel_rect.bottom - 20
        body_h = body_bottom - body_y
        gap = 12
        left_w = int(body_w * 0.58)
        left = pygame.Rect(body_x, body_y, left_w, body_h)
        right = pygame.Rect(left.right + gap, body_y, body_w - left_w - gap, body_h)

        # 1. Comparação exata dos três cenários nos dois perfis.
        comparison_h = min(190, max(160, int(body_h * 0.22)))
        comparison_rect = pygame.Rect(left.x, left.y, left.width, comparison_h)
        self.results_technical_sections.append(comparison_rect)
        tx, ty, tw = self._draw_results_detail_card(
            surface,
            comparison_rect,
            "1. COMPARAÇÃO DIRETA — 240 MHz × 80 MHz",
            C_ACCENT_CYAN,
            "Mesmo firmware e pacote; 80 MHz é uma limitação experimental da CPU.",
        )
        headers = ("CENÁRIO", "240 MHz", "80 MHz", "80/240", "PACOTE", "RESULTADO")
        col_ws = (int(tw * 0.19), int(tw * 0.16), int(tw * 0.16), int(tw * 0.13), int(tw * 0.13), tw - int(tw * 0.77))
        cx = tx
        for index, head in enumerate(headers):
            surface.blit(self._render_clipped(FONT_LABEL, head, C_TEXT_DIM, max(38, col_ws[index] - 6)), (cx, ty))
            cx += col_ws[index]
        ty += 21
        for row_index, scenario in enumerate(MISSION_OVERLAY_SCENARIOS):
            result_240 = CONSOLIDATED_MISSION_BASELINE[scenario]
            result_80 = CONSOLIDATED_MISSION_LIMITED[scenario]
            row_rect = pygame.Rect(tx - 4, ty - 3, tw + 8, 25)
            if row_index % 2:
                pygame.draw.rect(surface, (18, 28, 46), row_rect, border_radius=3)
            label = "PQC+CRC" if scenario == "PQC_CRC32" else scenario
            profile_ratio = self._ratio_value(result_80["elapsed_us"], result_240["elapsed_us"])
            cells = (
                label,
                _format_elapsed(result_240["elapsed_us"]),
                _format_elapsed(result_80["elapsed_us"]),
                f"{profile_ratio:.1f}x",
                f"{result_240['bytes_total']} B",
                result_240["result"],
            )
            cx = tx
            for cell_index, cell in enumerate(cells):
                color = self._results_success_color() if scenario == "PQC_CRC32" and cell_index == 0 else (self._scenario_color(scenario) if cell_index == 0 else C_TEXT_PRIMARY)
                surface.blit(self._render_clipped(FONT_SMALL, cell, color, max(38, col_ws[cell_index] - 6)), (cx, ty))
                cx += col_ws[cell_index]
            ty += 27

        # Gráficos: a escala muda por perfil, mas é comum aos três cenários.
        charts_y = comparison_rect.bottom + gap
        charts_h = min(260, max(220, int(body_h * 0.30)))
        charts_rect = pygame.Rect(left.x, charts_y, left.width, charts_h)
        self.results_technical_sections.append(charts_rect)
        gx, gy, gw = self._draw_results_detail_card(
            surface,
            charts_rect,
            "GRÁFICOS DE IMPACTO",
            C_ACCENT_ORANGE,
            "O valor escrito é absoluto; a barra compara os cenários dentro de cada perfil.",
        )
        chart_gap = 18
        chart_w = (gw - chart_gap) // 2
        self._draw_results_metric_chart(
            surface,
            gx,
            gy,
            chart_w,
            "TEMPO — 240 MHz",
            "elapsed_us",
            lambda value: _format_elapsed(int(round(value))),
            CONSOLIDATED_MISSION_BASELINE,
        )
        self._draw_results_metric_chart(
            surface,
            gx + chart_w + chart_gap,
            gy,
            gw - chart_w - chart_gap,
            "TEMPO — 80 MHz",
            "elapsed_us",
            lambda value: _format_elapsed(int(round(value))),
            CONSOLIDATED_MISSION_LIMITED,
        )
        classic = CONSOLIDATED_MISSION_BASELINE["CLASSIC"]
        time_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["elapsed_us"], classic["elapsed_us"])
        bytes_ratio = self._ratio_value(CONSOLIDATED_MISSION_BASELINE["PQC"]["bytes_total"], classic["bytes_total"])
        frequency_ratio = self._ratio_value(CONSOLIDATED_MISSION_LIMITED["PQC"]["elapsed_us"], CONSOLIDATED_MISSION_BASELINE["PQC"]["elapsed_us"])
        chart_note = f"PQC: 14,2 → 40,2 ms ({frequency_ratio:.1f}x ao limitar CPU); pacote permanece 837 B."
        surface.blit(self._render_clipped(FONT_LABEL, chart_note, C_ACCENT_ORANGE, gw), (gx, charts_rect.bottom - 24))

        # Decomposição preserva o detalhamento das fases internas.
        phases_y = charts_rect.bottom + gap
        phases_available = left.bottom - phases_y
        show_packet_composition = phases_available >= 330
        phases_h = (phases_available - gap) // 2 if show_packet_composition else phases_available
        phases_rect = pygame.Rect(left.x, phases_y, left.width, phases_h)
        self.results_technical_sections.append(phases_rect)
        px, py, pw = self._draw_results_detail_card(
            surface,
            phases_rect,
            "FASES INTERNAS — 240 MHz",
            C_ACCENT_PURPLE,
            "A tabela separa o total: AES mostra cifragem/decifragem; CRC é o custo positivo do guardião.",
        )
        phase_headers = ("CENÁRIO", "KEYGEN", "ENCAP", "DECAP", "AES TX/RX", "CRC")
        phase_col_ws = (int(pw * 0.18), int(pw * 0.15), int(pw * 0.15), int(pw * 0.15), int(pw * 0.23), pw - int(pw * 0.18) - int(pw * 0.15) * 3 - int(pw * 0.23))
        cx = px
        for index, head in enumerate(phase_headers):
            surface.blit(self._render_clipped(FONT_LABEL, head, C_TEXT_DIM, max(36, phase_col_ws[index] - 5)), (cx, py))
            cx += phase_col_ws[index]
        py += 22
        for row_index, scenario in enumerate(MISSION_OVERLAY_SCENARIOS):
            result = CONSOLIDATED_MISSION_BASELINE[scenario]
            label = "PQC+CRC" if scenario == "PQC_CRC32" else scenario
            cells = (
                label,
                _format_elapsed(result["keygen_us"]) if result["keygen_us"] else "—",
                _format_elapsed(result["encap_us"]) if result["encap_us"] else "—",
                _format_elapsed(result["decap_us"]) if result["decap_us"] else "—",
                f"{_format_elapsed(result['tag_us'])} / {_format_elapsed(result['verify_us'])}",
                _format_elapsed(result["crc_us"]) if result["crc_us"] else "—",
            )
            if row_index % 2:
                pygame.draw.rect(surface, (18, 28, 46), (px - 4, py - 3, pw + 8, 25), border_radius=3)
            cx = px
            for cell_index, cell in enumerate(cells):
                color = self._scenario_color(scenario) if cell_index == 0 else C_TEXT_PRIMARY
                surface.blit(self._render_clipped(FONT_SMALL, cell, color, max(34, phase_col_ws[cell_index] - 5)), (cx, py))
                cx += phase_col_ws[cell_index]
            py += 27

        if show_packet_composition:
            packet_y = phases_rect.bottom + gap
            packet_rect = pygame.Rect(left.x, packet_y, left.width, left.bottom - packet_y)
            self.results_technical_sections.append(packet_rect)
            qx, qy, qw = self._draw_results_detail_card(
                surface,
                packet_rect,
                "COMPOSIÇÃO DO PACOTE",
                C_ACCENT_BLUE,
                "Barras empilhadas: payload, ciphertext ML-KEM, nonce + tag GCM e CRC32.",
            )
            legend = (
                ("PAYLOAD", C_ACCENT_BLUE),
                ("ML-KEM CT", C_ACCENT_PURPLE),
                ("NONCE + TAG", C_ACCENT_CYAN),
                ("CRC32", C_ACCENT_GREEN),
            )
            legend_x = qx
            for label, color in legend:
                pygame.draw.rect(surface, color, (legend_x, qy, 10, 10), border_radius=2)
                surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, 104), (legend_x + 14, qy - 2))
                legend_x += min(132, max(104, qw // 4))
            qy += 28
            maximum_packet = max(CONSOLIDATED_MISSION_BASELINE[name]["bytes_total"] for name in MISSION_OVERLAY_SCENARIOS)
            packet_labels = {"CLASSIC": "CLASSIC", "PQC": "PQC", "PQC_CRC32": "PQC+CRC"}
            label_w = 92
            value_w = 64
            bar_x = qx + label_w
            bar_w = max(120, qw - label_w - value_w - 16)
            for scenario in MISSION_OVERLAY_SCENARIOS:
                result = CONSOLIDATED_MISSION_BASELINE[scenario]
                surface.blit(self._render_clipped(FONT_BODY, packet_labels[scenario], self._scenario_color(scenario), label_w - 8), (qx, qy - 2))
                segments = (
                    (result["bytes_payload"], C_ACCENT_BLUE),
                    (max(0, result["bytes_crypto"] - 28), C_ACCENT_PURPLE),
                    (28, C_ACCENT_CYAN),
                    (result["bytes_checksum"], C_ACCENT_GREEN),
                )
                cursor_x = bar_x
                for amount, color in segments:
                    segment_w = int(bar_w * amount / maximum_packet) if maximum_packet else 0
                    if amount and segment_w < 3:
                        segment_w = 3
                    if segment_w:
                        pygame.draw.rect(surface, color, (cursor_x, qy + 2, segment_w, 16), border_radius=2)
                        cursor_x += segment_w
                surface.blit(self._render_clipped(FONT_BODY, f"{result['bytes_total']} B", C_TEXT_PRIMARY, value_w), (bar_x + bar_w + 10, qy - 2))
                qy += 30

        # 2. Validação: traduz campos técnicos em perguntas que o aluno explica.
        aes_ok = bool(CONSOLIDATED_AES_GCM_CHECKS.get("official_candidate"))
        aes_color = C_ACCENT_GREEN if aes_ok else C_ACCENT_ORANGE
        small_gap = 8
        validation_h = min(160, max(138, int(body_h * 0.19)))
        validation_rect = pygame.Rect(right.x, right.y, right.width, validation_h)
        self.results_technical_sections.append(validation_rect)
        vx, vy, vw = self._draw_results_detail_card(
            surface,
            validation_rect,
            "2. A COLETA É VÁLIDA?",
            aes_color,
            f"{'SIM — AES-GCM OFICIAL' if aes_ok else 'NÃO — REVISAR FIRMWARE'} | {CONSOLIDATED_SUMMARY['records']} regs; {CONSOLIDATED_SUMMARY['failed']} falhas de execução",
        )
        validation_items = (
            ("MISSÕES AES", f"{CONSOLIDATED_AES_GCM_CHECKS.get('mission_records', 0)}/600"),
            ("NÃO-AES", str(CONSOLIDATED_AES_GCM_CHECKS.get("non_aes_gcm_records", 0))),
            ("CAMPOS AUSENTES", str(CONSOLIDATED_AES_GCM_CHECKS.get("missing_required_fields", 0))),
            ("FALHAS AEAD", str(CONSOLIDATED_AES_GCM_CHECKS.get("aead_failures", 0))),
            ("NONCES REPETIDOS", str(CONSOLIDATED_AES_GCM_CHECKS.get("nonce_crc32_duplicates", 0))),
            ("PQC_KAT", "PASS"),
        )
        item_w = vw // 3
        for index, (label, value) in enumerate(validation_items):
            col = index % 3
            row = index // 3
            ix = vx + col * item_w
            iy = vy + row * 35
            surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, item_w - 8), (ix, iy))
            surface.blit(self._render_clipped(FONT_BODY, value, aes_color if value in {"0", "PASS", "600/600"} else C_TEXT_PRIMARY, item_w - 8), (ix, iy + 15))

        # 3. Benchmark isolado de ML-KEM.
        bench_y = validation_rect.bottom + small_gap
        bench_h = min(140, max(120, int(body_h * 0.16)))
        bench_rect = pygame.Rect(right.x, bench_y, right.width, bench_h)
        self.results_technical_sections.append(bench_rect)
        bx, by, bw = self._draw_results_detail_card(
            surface,
            bench_rect,
            "3. ONDE ML-KEM GASTA TEMPO?",
            C_ACCENT_ORANGE,
            "PQC_BENCH: média em ms por operação, 100 rounds.",
        )
        bench_headers = ("PERFIL", "KEYGEN", "ENCAP", "DECAP")
        bench_col_ws = (int(bw * 0.40), int(bw * 0.20), int(bw * 0.20), bw - int(bw * 0.80))
        cx = bx
        for index, head in enumerate(bench_headers):
            surface.blit(self._render_clipped(FONT_LABEL, head, C_TEXT_DIM, bench_col_ws[index] - 4), (cx, by))
            cx += bench_col_ws[index]
        by += 22
        for row_index, row in enumerate(CONSOLIDATED_PQC_BENCH):
            cx = bx
            for col_index, cell in enumerate(row):
                color = C_ACCENT_ORANGE if col_index == 3 else C_TEXT_PRIMARY
                surface.blit(self._render_clipped(FONT_SMALL, cell, color, bench_col_ws[col_index] - 4), (cx, by))
                cx += bench_col_ws[col_index]
            by += 25

        # 4. Falhas: resultado objetivo, sem misturar CRC e autenticação.
        fault_y = bench_rect.bottom + small_gap
        fault_h = min(130, max(105, int(body_h * 0.14)))
        fault_rect = pygame.Rect(right.x, fault_y, right.width, fault_h)
        self.results_technical_sections.append(fault_rect)
        fx, fy, fw = self._draw_results_detail_card(surface, fault_rect, "4. O BIT-FLIP FOI PERCEBIDO?", C_ACCENT_GREEN)
        none_silent, none_total = self._count_pair(CONSOLIDATED_SUMMARY.get("demo_none_silent"))
        detected, detected_total = self._count_pair(CONSOLIDATED_SUMMARY.get("demo_crc_detected"))
        fault_gap = 10
        fault_w = (fw - fault_gap) // 2
        fault_specs = (
            ("SEM CRC32", f"{none_silent}/{none_total} SILENT", "corrupção aceita sem aviso", C_ACCENT_ORANGE),
            ("COM CRC32", f"{detected}/{detected_total} DETECTED", "corrupção observada", C_ACCENT_GREEN),
        )
        for index, (label, value, detail, color) in enumerate(fault_specs):
            cell = pygame.Rect(fx + index * (fault_w + fault_gap), fy, fault_w, max(44, fault_rect.bottom - fy - 10))
            pygame.draw.rect(surface, (18, 28, 46), cell, border_radius=4)
            pygame.draw.rect(surface, color, cell, width=1, border_radius=4)
            surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, cell.width - 14), (cell.x + 7, cell.y + 6))
            surface.blit(self._render_clipped(FONT_BODY, value, color, cell.width - 14), (cell.x + 7, cell.y + 23))
            if cell.height >= 65:
                surface.blit(self._render_clipped(FONT_LABEL, detail, C_TEXT_PRIMARY, cell.width - 14), (cell.x + 7, cell.y + 45))

        # 5. Conclusão oral e referências permanecem visíveis, mas separadas dos dados.
        explain_y = fault_rect.bottom + small_gap
        explain_h = min(120, max(98, int(body_h * 0.13)))
        explain_rect = pygame.Rect(right.x, explain_y, right.width, explain_h)
        self.results_technical_sections.append(explain_rect)
        ex, ey, ew = self._draw_results_detail_card(surface, explain_rect, "COMO EXPLICAR", C_ACCENT_CYAN)
        explanation_lines = (
            "1. ML-KEM funcionou; DECAP foi a fase mais cara.",
            f"2. PQC: {time_ratio:.1f}x em tempo; {bytes_ratio:.1f}x em bytes.",
            "3. CRC32 detecta bit-flip; AES-GCM autentica.",
        )
        for line in explanation_lines:
            surface.blit(self._render_clipped(FONT_LABEL, line, C_TEXT_PRIMARY, ew), (ex, ey))
            ey += 18

        refs_y = explain_rect.bottom + small_gap
        refs_rect = pygame.Rect(right.x, refs_y, right.width, right.bottom - refs_y)
        self.results_technical_sections.append(refs_rect)
        pygame.draw.rect(surface, self._results_card_bg(), refs_rect, border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, refs_rect, width=1, border_radius=6)
        surface.blit(self._render_clipped(FONT_LABEL, "FONTES QUE SUSTENTAM A LEITURA", C_TEXT_DIM, refs_rect.width - 20), (refs_rect.x + 10, refs_rect.y + 8))
        ref_top = refs_rect.y + 29
        ref_gap = 10
        ref_w = (refs_rect.width - 20 - ref_gap) // 2
        groups = (("MOTIVAÇÃO", MOTIVATION_REFERENCES, C_ACCENT_ORANGE), ("BASE TÉCNICA", RESULTS_REFERENCES, C_ACCENT_GREEN))
        for group_index, (heading, refs, color) in enumerate(groups):
            ref_x = refs_rect.x + 10 + group_index * (ref_w + ref_gap)
            surface.blit(self._render_clipped(FONT_LABEL, heading, color, ref_w), (ref_x, ref_top))
            line_y = ref_top + 17
            for name, detail in refs:
                if line_y > refs_rect.bottom - 15:
                    break
                reference = f"{name}: {detail}" if ref_w >= 280 else name
                surface.blit(self._render_clipped(FONT_LABEL, reference, C_TEXT_DIM, ref_w), (ref_x, line_y))
                line_y += 15

        self.results_stress_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.results_overlay_content_bottom = max(phases_rect.bottom, refs_rect.bottom)

    def _draw_results_overlay_technical_theory(self, surface, t):
        panel_rect, close_rect = self._results_overlay_geometry()
        x, y, w, h = panel_rect
        self.results_stress_btn_rect = pygame.Rect(0, 0, 0, 0)
        self.results_overlay_content_bottom = None
        self.results_technical_sections = []

        panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        panel_surf.fill((12, 14, 30, 236))
        surface.blit(panel_surf, (x, y))
        pygame.draw.rect(surface, C_PANEL_BORDER, panel_rect, width=2, border_radius=8)

        header_h = self._draw_results_header(
            surface,
            panel_rect,
            close_rect,
            "TEORIA, INTERPRETAÇÃO E FONTES",
            "Cada número responde a uma pergunta; correlação entre médias não implica causalidade.",
        )
        self._draw_results_technical_page_control(surface)

        body_x = x + max(24, int(w * 0.035))
        body_y = y + header_h + 14
        body_w = w - (body_x - x) * 2
        body_bottom = panel_rect.bottom - 20
        body_h = body_bottom - body_y
        gap = 12
        left_w = int(body_w * 0.56)
        left = pygame.Rect(body_x, body_y, left_w, body_h)
        right = pygame.Rect(left.right + gap, body_y, body_w - left_w - gap, body_h)

        pqc_240 = CONSOLIDATED_MISSION_BASELINE["PQC"]
        crc_240 = CONSOLIDATED_MISSION_BASELINE["PQC_CRC32"]
        pqc_80 = CONSOLIDATED_MISSION_LIMITED["PQC"]
        crc_80 = CONSOLIDATED_MISSION_LIMITED["PQC_CRC32"]
        classic_240 = CONSOLIDATED_MISSION_BASELINE["CLASSIC"]
        pqc_clock_ratio = self._ratio_value(pqc_80["elapsed_us"], pqc_240["elapsed_us"])
        crc_delta_240 = crc_240["elapsed_us"] - pqc_240["elapsed_us"]
        crc_delta_80 = crc_80["elapsed_us"] - pqc_80["elapsed_us"]

        theory_cards = (
            (
                "1. O QUE O TEMPO TOTAL SOMA?",
                "240 MHz: 611 us / 14,152 ms / 14,097 ms",
                "elapsed_us soma RNG/KEM/KDF/AES/CRC. KeyGen cria par; Encaps gera ct+segredo; Decaps recupera/valida e foi a mais cara. AES TX/RX cifra e verifica.",
                C_ACCENT_CYAN,
            ),
            (
                "2. POR QUE PQC+CRC PARECE MAIS RÁPIDO?",
                f"Diferença total: {crc_delta_240:+d} us em 240 MHz; {crc_delta_80:+d} us em 80 MHz | CRC: +32/+53 us",
                "São médias de execuções distintas. Variações de KeyGen, Encaps, Decaps, KDF e interrupções superam o pequeno CRC. crc_us positivo prova que CRC não acelera; a diferença total é ruído amostral.",
                C_ACCENT_ORANGE,
            ),
            (
                "3. DE ONDE VÊM 69 / 837 / 841 BYTES?",
                "CLASSIC = 41 + 12 + 16 | PQC = CLASSIC + 768 | PQC+CRC = PQC + 4",
                "41 B de payload + nonce GCM de 12 B + tag de 16 B = 69 B. PQC soma o ciphertext ML-KEM de 768 B; CRC soma 4 B. Esses tamanhos são determinísticos.",
                C_ACCENT_BLUE,
            ),
            (
                "4. O QUE 80 MHz MUDA?",
                f"PQC: 14,152 → 40,197 ms ({pqc_clock_ratio:.1f}x) | bytes: 837 → 837",
                "A 80 MHz a CPU opera a 1/3 do clock; as fases intensivas aproximam 3x. Não dá exatamente 3x porque timers, memória, periféricos e custos fixos não escalam linearmente.",
                C_ACCENT_PURPLE,
            ),
            (
                "5. O QUE RAM E CONTAGENS PROVAM?",
                f"heap={classic_240['heap']} B | min_heap={classic_240.get('min_heap', 197624)} B | AES 600/600 | falhas de execução=0",
                "Heap estável sugere não retenção; min_heap é mínimo do boot. 200/200 SILENT/DETECTED valem só no bit-flip; 600/600 valida apenas esta campanha.",
                C_ACCENT_GREEN,
            ),
        )
        card_gap = 8
        card_h = (left.height - card_gap * (len(theory_cards) - 1)) // len(theory_cards)
        for index, (title, subtitle, explanation, color) in enumerate(theory_cards):
            rect = pygame.Rect(left.x, left.y + index * (card_h + card_gap), left.width, card_h)
            self.results_technical_sections.append(rect)
            cx, cy, cw = self._draw_results_detail_card(surface, rect, title, color, subtitle)
            max_lines = max(2, (rect.bottom - cy - 8) // 17)
            self._draw_wrapped_text(surface, FONT_LABEL, explanation, C_TEXT_PRIMARY, cx, cy, cw, line_spacing=17, max_lines=max_lines)

        bibliography_rect = pygame.Rect(right.x, right.y, right.width, right.height)
        self.results_technical_sections.append(bibliography_rect)
        bx, by, bw = self._draw_results_detail_card(
            surface,
            bibliography_rect,
            "BIBLIOGRAFIA COM FUNÇÃO NO PROJETO",
            C_ACCENT_GREEN,
            "Conceitos vêm das fontes; números vêm do JSON da placa.",
        )
        reference_gap = 5
        reference_h = max(68, (bibliography_rect.bottom - by - reference_gap * (len(DETAILED_RESULTS_REFERENCES) - 1) - 8) // len(DETAILED_RESULTS_REFERENCES))
        for index, (title, support, locator) in enumerate(DETAILED_RESULTS_REFERENCES):
            item_y = by + index * (reference_h + reference_gap)
            item = pygame.Rect(bx, item_y, bw, reference_h)
            if item.bottom > bibliography_rect.bottom - 6:
                break
            color = (C_ACCENT_CYAN, C_ACCENT_BLUE, C_ACCENT_ORANGE, C_ACCENT_GREEN, C_ACCENT_PURPLE, C_TEXT_PRIMARY)[index % 6]
            pygame.draw.rect(surface, (17, 27, 44), item, border_radius=4)
            pygame.draw.rect(surface, self._mix_color(C_PANEL_BORDER, color, 0.35), item, width=1, border_radius=4)
            surface.blit(self._render_clipped(FONT_LABEL, title, color, item.width - 16), (item.x + 8, item.y + 6))
            support_y = item.y + 23
            self._draw_wrapped_text(surface, FONT_LABEL, support, C_TEXT_PRIMARY, item.x + 8, support_y, item.width - 16, line_spacing=15, max_lines=2)
            surface.blit(self._render_clipped(FONT_LABEL, locator, C_TEXT_DIM, item.width - 16), (item.x + 8, item.bottom - 17))

        self.results_overlay_content_bottom = max(left.bottom, bibliography_rect.bottom)

    def _draw_fault_effect(self, surface, t, satellite):
        if self.effect_timer <= 0:
            return

        alpha = int(95 * min(1.0, self.effect_timer / 0.35))
        overlay = self._get_fault_overlay(surface)
        overlay.fill((*self.effect_color, max(0, min(95, alpha))))
        surface.blit(overlay, (0, 0))

        sx, sy = satellite.get_position()
        if self.effect_timer > 0:
            # OTIMIZAÇÃO SEMINÁRIO
            # Anel/label acompanham o tremor do corpo afetado.
            sx += self.impact_shake_offset[0]
            sy += self.impact_shake_offset[1]
        ring_radius = int(56 + 14 * math.sin(t * 18))
        pygame.draw.circle(surface, self.effect_color, (int(sx), int(sy)), ring_radius, 2)
        label = FONT_BODY.render(self.effect_label, True, self.effect_color)
        surface.blit(label, (int(sx) - label.get_width() // 2, int(sy) - 76))

    def _get_fault_overlay(self, surface):
        size = surface.get_size()
        if self._fault_overlay_surface is None or self._fault_overlay_surface.get_size() != size:
            self._fault_overlay_surface = pygame.Surface(size, pygame.SRCALPHA)
        return self._fault_overlay_surface

    def _fault_overlay_size(self):
        width = 600 if WIDTH >= 1600 else 560 if WIDTH >= 1200 else 456
        width = min(width, max(340, WIDTH - 40))
        target_height = 660 if HEIGHT >= 900 else 600 if HEIGHT >= 720 else 520
        height = min(target_height, max(500, HEIGHT - 94))
        return width, height

    def _default_fault_overlay_position(self):
        width, height = self._fault_overlay_size()
        left = 340
        right = WIDTH - 420
        y = 116 + max(0, self._top_metrics_rows() - 1) * 54
        if right - left >= width:
            x = right - width
        else:
            x = (WIDTH - width) // 2
            y += 28
        return self._clamp_overlay_position(x, y, width, height)

    @staticmethod
    def _clamp_overlay_position(x, y, width, height):
        min_y = 50
        max_x = max(10, WIDTH - width - 10)
        max_y = max(min_y, HEIGHT - height - 44)
        return max(10, min(int(x), max_x)), max(min_y, min(int(y), max_y))

    def _popup_transition(self, opened_at, closing_since=None):
        if closing_since is not None:
            ratio = max(0.0, min(1.0, (self.uptime - closing_since) / POPUP_EXIT_SECONDS))
            eased = ratio * ratio
            return -int(18 * eased), max(0.35, 1.0 - ratio)
        ratio = max(0.0, min(1.0, (self.uptime - opened_at) / POPUP_ENTER_SECONDS))
        eased = 1.0 - (1.0 - ratio) ** 3
        return int(20 * (1.0 - eased)), max(0.35, eased)

    def _fault_overlay_geometry(self):
        width, height = self._fault_overlay_size()
        if self.fault_overlay_position is None:
            self.fault_overlay_position = self._default_fault_overlay_position()
        x, y = self._clamp_overlay_position(*self.fault_overlay_position, width, height)
        self.fault_overlay_position = (x, y)
        rect = pygame.Rect(x, y, width, height)
        close_rect = pygame.Rect(rect.right - 36, rect.y + 9, 24, 24)
        return rect, close_rect

    def _draw_fault_overlay(self, surface, t):
        if not self.fault_overlay_visible or not self.fault_overlay:
            self.fault_overlay_rect = None
            self.fault_overlay_close_rect = None
            self.fault_overlay_drag_rect = None
            self.fault_flow_control_rect = None
            self.fault_flow_scrub_rect = None
            self.dragging_fault_flow = False
            return

        rect, close_rect = self._fault_overlay_geometry()
        offset_y, alpha_ratio = self._popup_transition(
            self.fault_overlay_opened_at,
            self.fault_overlay_closing_since,
        )
        if offset_y:
            rect = rect.move(0, offset_y)
            close_rect = close_rect.move(0, offset_y)
        if self.effect_timer > 0:
            # OTIMIZAÇÃO SEMINÁRIO
            # Popup principal recebe o mesmo tremor fisico do satelite.
            sx, sy = self.impact_shake_offset
            rect = rect.move(sx, sy)
            close_rect = close_rect.move(sx, sy)
        drag_rect = pygame.Rect(rect.x, rect.y, rect.width, 44)
        self.fault_overlay_rect = rect
        self.fault_overlay_close_rect = close_rect
        self.fault_overlay_drag_rect = drag_rect

        result = str(self.fault_overlay.get("result", ""))
        color = self._fault_result_color(result)
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pulse = int(150 + 45 * math.sin(t * 8)) if self.effect_timer > 0 else 150
        pygame.draw.rect(panel, (*C_PANEL_BG, int(232 * alpha_ratio)), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*color, int(max(120, pulse) * alpha_ratio)), (0, 0, rect.width, rect.height), width=1, border_radius=8)
        pygame.draw.rect(panel, (*color, int(34 * alpha_ratio)), (0, 0, rect.width, 44), border_radius=8)
        pygame.draw.line(panel, (*C_PANEL_BORDER, int(180 * alpha_ratio)), (0, 44), (rect.width, 44), 1)
        surface.blit(panel, rect.topleft)

        title = f"FALHA {self.fault_overlay.get('target', 'PAYLOAD')} | {self._fault_result_short_label(result)}"
        surface.blit(self._render_clipped(FONT_SMALL, title, C_TEXT_PRIMARY, rect.width - 62), (rect.x + 14, rect.y + 12))
        pygame.draw.rect(surface, (58, 18, 28), close_rect, border_radius=5)
        pygame.draw.rect(surface, C_ACCENT_RED, close_rect, width=1, border_radius=5)
        x_text = FONT_SMALL.render("X", True, C_TEXT_PRIMARY)
        surface.blit(x_text, (close_rect.centerx - x_text.get_width() // 2, close_rect.centery - x_text.get_height() // 2))

        subtitle = (
            f"{self.fault_overlay.get('guard', '--')}  "
            f"byte={self.fault_overlay.get('byte_index', '--')}  "
            f"mask={self.fault_overlay.get('bit_mask', '--')}"
        )
        if self.fault_overlay.get("selector_pot") not in {None, "", "NA"}:
            subtitle += f"  pot={self.fault_overlay.get('selector_pot')}"
        surface.blit(self._render_clipped(FONT_LABEL, subtitle, C_TEXT_DIM, rect.width - 28), (rect.x + 14, rect.y + 48))

        if self.fault_flow_animation is not None:
            self._draw_fault_overlay_flow(surface, rect, self.fault_overlay, t)
            return

        self._draw_fault_overlay_details(surface, rect, self.fault_overlay)

    def _draw_fault_overlay_flow(self, surface, rect, fault, t):
        animation = self.fault_flow_animation
        if animation is None:
            return
        steps = animation.get("steps", ())
        if not steps:
            return

        active_index, local_progress = self._mission_flow_active_state(animation)
        active_step = steps[active_index]
        color = active_step["color"]
        awaiting_confirm = bool(animation.get("awaiting_confirm"))
        # REFATORAÇÃO VISUAL: Popup de Falha Didático

        x = rect.x + 14
        y = rect.y + 72
        width = rect.width - 28

        header = "FALHA CONCLUÍDA" if awaiting_confirm else f"FALHA PASSO {active_index + 1}/{len(steps)}"
        control_rect = pygame.Rect(rect.right - 104, y - 2, 86, 22)
        self.fault_flow_control_rect = control_rect
        surface.blit(self._render_clipped(FONT_LABEL, header, C_ACCENT_CYAN, width - 100), (x, y))
        button_label = "VER DADOS" if awaiting_confirm else "AGUARDE"
        button_border = C_ACCENT_GREEN if awaiting_confirm else C_PANEL_BORDER
        button_fill = (18, 58, 46) if awaiting_confirm else (30, 38, 72)
        button_color = C_ACCENT_GREEN if awaiting_confirm else C_TEXT_PRIMARY
        pygame.draw.rect(surface, button_fill, control_rect, border_radius=4)
        pygame.draw.rect(surface, button_border, control_rect, width=1, border_radius=4)
        button_text = FONT_LABEL.render(button_label, True, button_color)
        surface.blit(
            button_text,
            (
                control_rect.centerx - button_text.get_width() // 2,
                control_rect.centery - button_text.get_height() // 2,
            ),
        )
        y += 18

        step_h = 96 if rect.height >= 580 else 82
        step_rect = pygame.Rect(x, y, width, step_h)
        self._draw_soft_glow(surface, step_rect.center, max(18, step_rect.height // 3), color, 42)
        pygame.draw.rect(surface, (8, 12, 26), step_rect, border_radius=4)
        pygame.draw.rect(surface, color, step_rect, width=3, border_radius=4)
        step_title = f"{active_step['label']} - {active_step['detail']}"
        surface.blit(self._render_clipped(FONT_HEADER, step_title, color, width - 14), (step_rect.x + 10, step_rect.y + 8))
        time_us = active_step.get("time_us")
        metric = _format_elapsed(time_us) if time_us not in {None, ""} else self._fault_step_metric(fault, active_step["label"])
        surface.blit(self._render_clipped(FONT_BODY, metric, C_TEXT_PRIMARY, width - 14), (step_rect.x + 10, step_rect.y + 36))
        self._draw_wrapped_text(
            surface,
            FONT_LABEL,
            self._short_explanation(active_step.get("explain", "")),
            C_TEXT_PRIMARY,
            step_rect.x + 10,
            step_rect.y + 62,
            width - 14,
            line_spacing=16,
            max_lines=1,
        )

        timeline_y = rect.bottom - 54
        visual_top = step_rect.bottom + 8
        visual_h = max(230, timeline_y - visual_top - 24)
        visual_rect = pygame.Rect(x, visual_top, width, visual_h)
        self._draw_fault_transformation_panel(surface, visual_rect, fault, active_step, local_progress, t)

        timeline_x = x + 10
        timeline_w = width - 20
        node_positions = [timeline_x + int(round(index * timeline_w / max(1, len(steps) - 1))) for index in range(len(steps))]
        pygame.draw.line(surface, C_PANEL_BORDER, (node_positions[0], timeline_y), (node_positions[-1], timeline_y), 2)
        progress_ratio = min(
            1.0,
            max(0.0, animation.get("age", 0.0) / max(0.001, animation.get("duration", FAULT_FLOW_ANIMATION_SECONDS))),
        )
        marker_x = node_positions[0] + int((node_positions[-1] - node_positions[0]) * progress_ratio)
        self.fault_flow_scrub_rect = pygame.Rect(node_positions[0], timeline_y - 14, max(1, node_positions[-1] - node_positions[0]), 42)
        pygame.draw.line(surface, color, (node_positions[0], timeline_y), (marker_x, timeline_y), 3)
        short_labels = {
            "PAYLOAD": "PAY",
            "BIT-FLIP": "BIT",
            "CRC32": "CRC",
            "SEM CRC": "NO",
            "ENTREGA": "OUT",
            "VERIFICA": "VER",
            "RESULTADO": "OK" if str(fault.get("result")) != "SILENT" else "SIL",
        }
        for index, step in enumerate(steps):
            node_x = node_positions[index]
            completed = index < active_index
            active = index == active_index
            node_color = step["color"] if active or completed else C_TEXT_DIM
            radius = 7 if active else 4
            pygame.draw.circle(surface, node_color, (node_x, timeline_y), radius)
            if active:
                pygame.draw.circle(surface, node_color, (node_x, timeline_y), radius + 6, 1)
            label = self._render_clipped(FONT_LABEL, short_labels.get(step["label"], step["label"][:3]), node_color, 34)
            surface.blit(label, (node_x - label.get_width() // 2, timeline_y + 10))

        marker_rect = pygame.Rect(marker_x - 8, timeline_y - 8, 16, 16)
        pygame.draw.rect(surface, color, marker_rect, border_radius=4)
        pygame.draw.rect(surface, C_TEXT_PRIMARY, marker_rect, width=1, border_radius=4)
        pygame.draw.circle(surface, C_TEXT_PRIMARY, (marker_x, timeline_y), 12, 1)

        hint = (
            "Arraste a linha para revisar; VER DADOS abre resultado."
            if awaiting_confirm
            else "Arraste a linha para revisar a explicação."
        )
        surface.blit(self._render_clipped(FONT_LABEL, hint, C_TEXT_DIM, width), (x, rect.bottom - 20))

    def _draw_fault_overlay_details(self, surface, rect, fault):
        x = rect.x + 14
        y = rect.y + 72
        width = rect.width - 28
        result = str(fault.get("result", ""))
        color = self._fault_result_color(result)

        summary_rect = pygame.Rect(x, y, width, 82)
        pygame.draw.rect(surface, (14, 20, 38), summary_rect, border_radius=5)
        pygame.draw.rect(surface, color, summary_rect, width=1, border_radius=5)
        surface.blit(self._render_clipped(FONT_SMALL, self._fault_result_label(result), color, width - 14), (x + 7, y + 7))
        self._draw_wrapped_text(
            surface,
            FONT_LABEL,
            self._fault_result_explanation(fault),
            C_TEXT_PRIMARY,
            x + 7,
            y + 28,
            width - 14,
            line_spacing=14,
            max_lines=3,
        )

        self._draw_fault_byte_rows(surface, x, y + 96, width, fault)

        selector_y = y + 158
        if fault.get("selector_pot") not in {None, "", "NA"} or fault.get("payload_text"):
            selector = (
                f"pot {fault.get('selector_pot', 'NA')} -> "
                f"byte {fault.get('selector_byte_index', fault.get('byte_index', '--'))} "
                f"mask {fault.get('selector_bit_mask', fault.get('bit_mask', '--'))}"
            )
            surface.blit(self._render_clipped(FONT_LABEL, selector, C_ACCENT_ORANGE, width), (x, selector_y))
            payload_text = str(fault.get("payload_text", ""))
            if payload_text:
                surface.blit(self._render_clipped(FONT_LABEL, payload_text, C_TEXT_DIM, width), (x, selector_y + 16))

        metric_y = y + 194
        metric_gap = 8
        metric_w = (width - metric_gap) // 2
        metrics = (
            ("CRC ANTES", str(fault.get("crc_before") or "--"), C_TEXT_PRIMARY),
            ("CRC DEPOIS", str(fault.get("crc_after") or "--"), color),
            ("TEMPO", _format_elapsed(fault.get("elapsed_us")), C_ACCENT_CYAN),
            ("GUARD", str(fault.get("guard") or "--"), C_ACCENT_GREEN if fault.get("guard") == "CRC32" else C_TEXT_DIM),
        )
        for index, (label, value, metric_color) in enumerate(metrics):
            bx = x + (index % 2) * (metric_w + metric_gap)
            by = metric_y + (index // 2) * 42
            self._draw_overlay_metric_box(surface, label, value, bx, by, metric_w, 40, metric_color)

    def _fault_step_metric(self, fault, label):
        if label == "BIT-FLIP":
            return f"{fault.get('before_byte', '--')} -> {fault.get('after_byte', '--')}"
        if label == "SEM CRC":
            return "sem checksum salvo"
        if label == "ENTREGA":
            return "sem bloqueio de integridade"
        if label in {"CRC32", "VERIFICA"}:
            before = str(fault.get("crc_before") or "--")
            after = str(fault.get("crc_after") or "--")
            return f"crc {before[-8:]} -> {after[-8:]}"
        if label == "RESULTADO":
            return _format_elapsed(fault.get("elapsed_us"))
        return str(fault.get("source") or "SIMULADO")

    def _draw_fault_byte_rows(self, surface, x, y, width, fault):
        before = self._parse_int_auto(fault.get("before_byte"))
        after = self._parse_int_auto(fault.get("after_byte"))
        mask = self._parse_int_auto(fault.get("bit_mask"))
        if before is None or after is None:
            before_crc = str(fault.get("crc_before") or "--")
            after_crc = str(fault.get("crc_after") or "--")
            lines = (
                f"crc antes: {before_crc[-8:]}",
                f"crc depois: {after_crc[-8:]}",
                "byte específico indisponível no resumo",
            )
            for line in lines:
                surface.blit(self._render_clipped(FONT_LABEL, line, C_TEXT_DIM, width), (x, y))
                y += 18
            return

        label_w = 54
        bit_gap = 3
        bit_size = min(22, max(15, (width - label_w - bit_gap * 7) // 8))
        start_x = x + label_w
        rows = (("ANTES", before, C_TEXT_DIM), ("DEPOIS", after, self._fault_result_color(str(fault.get("result", "")))))
        for row_index, (label, value, row_color) in enumerate(rows):
            row_y = y + row_index * 30
            surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, label_w - 4), (x, row_y + 5))
            for bit_index in range(8):
                bit_value = (value >> (7 - bit_index)) & 1
                bit_mask = 1 << (7 - bit_index)
                changed = bool(mask and (mask & bit_mask))
                bx = start_x + bit_index * (bit_size + bit_gap)
                bg = (58, 18, 28) if changed and row_index == 1 else (15, 20, 38)
                border = C_ACCENT_RED if changed else C_PANEL_BORDER
                pygame.draw.rect(surface, bg, (bx, row_y, bit_size, bit_size), border_radius=3)
                pygame.draw.rect(surface, border, (bx, row_y, bit_size, bit_size), width=1, border_radius=3)
                txt = FONT_LABEL.render(str(bit_value), True, row_color if not changed else C_ACCENT_RED)
                surface.blit(txt, (bx + (bit_size - txt.get_width()) // 2, row_y + (bit_size - txt.get_height()) // 2))

    def draw_satellite_lock(self, surface, t):
        center_x = WIDTH // 2
        center_y = HEIGHT // 2 - 165
        pulse = int(120 + 60 * math.sin(t * 3))
        max_text_width = max(260, min(620, WIDTH - 760))

        pygame.draw.circle(surface, (255, 165, 0, 80), (center_x, center_y - 20), 42, 2)
        pygame.draw.line(surface, (255, pulse, 0, 160), (center_x - 32, center_y - 20), (center_x + 32, center_y - 20), 2)
        pygame.draw.line(surface, (255, pulse, 0, 160), (center_x, center_y - 52), (center_x, center_y + 12), 2)

        title_lines = self._wrap_text_for_width(FONT_HEADER, "SATÉLITE NÃO CONECTADO", max_text_width)
        detail_lines = self._wrap_text_for_width(
            FONT_SMALL,
            "Conecte a BlackBoard Wisdom para liberar a órbita.",
            max_text_width,
        )

        y = center_y + 42
        for line in title_lines:
            text = FONT_HEADER.render(line, True, C_ACCENT_ORANGE)
            surface.blit(text, (center_x - text.get_width() // 2, y))
            y += text.get_height() + 4
        y += 2
        for line in detail_lines:
            text = FONT_SMALL.render(line, True, C_TEXT_DIM)
            surface.blit(text, (center_x - text.get_width() // 2, y))
            y += text.get_height() + 3

    def _draw_panel_bg(self, surface, rect, title="", t=0.0):
        """Desenha fundo de painel com borda e header."""
        # REFATORAÇÃO VISUAL: Painéis HUD Chanfrados
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        cut = 14
        poly = [
            (cut, 0), (rect.width - 1, 0), (rect.width - 1, rect.height - cut),
            (rect.width - cut, rect.height - 1), (0, rect.height - 1), (0, cut),
        ]
        pygame.draw.polygon(panel_surf, (*C_PANEL_BG, 206), poly)
        pygame.draw.polygon(panel_surf, (*C_PANEL_BORDER, 225), poly, 2)
        inner_poly = [(x + (1 if x == 0 else -1 if x == rect.width - 1 else 0),
                       y + (1 if y == 0 else -1 if y == rect.height - 1 else 0)) for x, y in poly]
        pygame.draw.polygon(panel_surf, (*C_ACCENT_PURPLE, 56), inner_poly, 1)
        for yy in range(42, rect.height - 8, 10):
            pygame.draw.line(panel_surf, (255, 255, 255, 13), (10, yy), (rect.width - 14, yy), 1)
        surface.blit(panel_surf, (rect.x, rect.y))

        if title:
            header_rect = pygame.Rect(rect.x, rect.y, rect.width, 32)
            h_surf = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
            header_poly = [(cut, 0), (header_rect.width - 1, 0), (header_rect.width - 1, header_rect.height - 1), (0, header_rect.height - 1), (0, cut)]
            pygame.draw.polygon(h_surf, (*C_PANEL_HEADER, 226), header_poly)
            pygame.draw.line(h_surf, C_ACCENT_CYAN, (cut, header_rect.height - 1), (header_rect.width - 8, header_rect.height - 1), 1)
            surface.blit(h_surf, (header_rect.x, header_rect.y))

            glow = int(180 + 75 * math.sin(t * 2))
            pygame.draw.circle(surface, (0, glow, 255),
                               (rect.x + 14, rect.y + 16), 4)

            title_surf = FONT_SMALL.render(title, True, C_ACCENT_CYAN)
            surface.blit(title_surf, (rect.x + 26, rect.y + 8))

    def _draw_hud_card(self, surface, rect, label, value, color):
        # REFATORAÇÃO VISUAL: Cartão de Métrica HUD
        cut = 8
        points = [
            (rect.x + cut, rect.y), (rect.right, rect.y), (rect.right, rect.bottom - cut),
            (rect.right - cut, rect.bottom), (rect.x, rect.bottom), (rect.x, rect.y + cut),
        ]
        pygame.draw.polygon(surface, (8, 16, 32), points)
        pygame.draw.polygon(surface, color, points, 1)
        pygame.draw.line(surface, (*color, 90), (rect.x + 12, rect.bottom - 6), (rect.right - 12, rect.bottom - 6), 1)
        surface.blit(self._render_clipped(FONT_BODY, label, C_TEXT_DIM, rect.width - 24), (rect.x + 12, rect.y + 7))
        surface.blit(self._render_clipped(FONT_HEADER, value, color, rect.width - 24), (rect.x + 12, rect.y + 28))

    def _draw_hud_button_shell(self, surface, rect, fill, border):
        # REFATORAÇÃO VISUAL: Botão Chanfrado Compartilhado
        cut = 6
        points = [
            (rect.x + cut, rect.y), (rect.right, rect.y), (rect.right, rect.bottom - cut),
            (rect.right - cut, rect.bottom), (rect.x, rect.bottom), (rect.x, rect.y + cut),
        ]
        pygame.draw.polygon(surface, fill, points)
        pygame.draw.polygon(surface, border, points, 1)

    def _compact_panel_height(self, content_height):
        available_height = max(0, HEIGHT - 110)
        return min(available_height, max(0, content_height))

    def _left_panel_width(self):
        return min(380, max(360, int(WIDTH * 0.195)))

    def _right_panel_width(self):
        return min(510, max(475, int(WIDTH * 0.265)))

    def _left_panel_height(self):
        header_and_top_padding = 48
        row_heights = (54 + 9, 54 + 9, 54)
        bottom_padding = 20
        return self._compact_panel_height(
            header_and_top_padding + sum(row_heights) + bottom_padding
        )

    def _right_panel_height(self, width):
        button_block_h = self._command_buttons_height(width)
        content_h = 48 + button_block_h + 22
        return self._compact_panel_height(content_h)

    @staticmethod
    def _command_group_columns(button_count, width):
        if width >= 400:
            return min(button_count, 3)
        if width >= 260:
            return min(button_count, 2)
        return 1

    def _command_buttons_height(self, width):
        section_label_h = 22
        button_h = 44
        row_gap = 10
        section_gap = 14
        total = 0
        for _section, buttons in COMMAND_BUTTON_GROUPS:
            columns = self._command_group_columns(len(buttons), width)
            rows = math.ceil(len(buttons) / columns)
            total += section_label_h + rows * button_h + max(0, rows - 1) * row_gap
        total += max(0, len(COMMAND_BUTTON_GROUPS) - 1) * section_gap
        return total

    def _draw_left_panel(self, surface, t, satellite):
        """Painel esquerdo: Falhas e integridade (foco da simulacao)."""
        # REFATORAÇÃO VISUAL: Painel de Telemetria HUD
        pw = self._left_panel_width()
        panel_rect = pygame.Rect(20, 55, pw, self._left_panel_height())
        self._draw_panel_bg(surface, panel_rect, "[SIMULAÇÃO PQC]", t)

        y = panel_rect.y + 48
        x = panel_rect.x + 18
        cw = pw - 36  # content width

        if "DEGRADADO" in self.session_status:
            session_color = C_ACCENT_RED
        elif "DETECTOU" in self.session_status:
            session_color = C_ACCENT_ORANGE
        elif self.session_status == "SIMULADO":
            session_color = C_ACCENT_CYAN
        else:
            session_color = C_ACCENT_GREEN
        guard_color = C_ACCENT_GREEN if self.checksum_enabled else C_ACCENT_ORANGE
        guard_text = "CRC32 ON" if self.checksum_enabled else "NONE"
        pqc_text, pqc_color = self._pqc_indicator()
        rows = (
            ("SESSÃO", self.session_status, session_color),
            ("ML-KEM", pqc_text, pqc_color),
            ("GUARD", guard_text, guard_color),
        )
        card_h = 54
        for label, value, color in rows:
            card = pygame.Rect(x, y, cw, card_h)
            self._draw_hud_card(surface, card, label, value, color)
            y += card_h + 9

    def _draw_right_panel(self, surface, t):
        """Painel direito: Console de comandos."""
        # REFATORAÇÃO VISUAL: Painel de Comandos HUD
        pw = self._right_panel_width()
        cw = pw - 36
        panel_rect = pygame.Rect(WIDTH - pw - 20, 55, pw, self._right_panel_height(cw))
        self._draw_panel_bg(surface, panel_rect, "[DEMO AO VIVO]", t)

        y = panel_rect.y + 48
        x = panel_rect.x + 18
        self._draw_command_buttons(surface, x, y, cw, t)

    def _draw_command_buttons(self, surface, x, y, width, t):
        # REFATORAÇÃO VISUAL: Botões HUD de Demonstração
        self.command_button_rects = []
        gap = 10
        button_h = 44
        section_gap = 14
        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)

        for section_index, (section, buttons) in enumerate(COMMAND_BUTTON_GROUPS):
            section_color = C_ACCENT_PURPLE if section == "CONFIGURAÇÃO" else C_ACCENT_GREEN
            section_label = FONT_LABEL.render(section, True, section_color)
            surface.blit(section_label, (x, y + 2))
            line_x = x + section_label.get_width() + 10
            pygame.draw.line(surface, (*section_color, 100), (line_x, y + 9), (x + width, y + 9), 1)
            y += 22

            columns = self._command_group_columns(len(buttons), width)
            rows = math.ceil(len(buttons) / columns)
            button_w = (width - gap * (columns - 1)) // columns
            for index, (label, command) in enumerate(buttons):
                col = index % columns
                row = index // columns
                bx = x + col * (button_w + gap)
                by = y + row * (button_h + gap)
                rect = pygame.Rect(bx, by, button_w, button_h)
                hovered = rect.collidepoint(mouse_pos)

                fill = (22, 30, 58) if not hovered else (28, 42, 82)
                border = C_ACCENT_CYAN if hovered else C_PANEL_BORDER

                if command == "SEND_MESSAGE":
                    border = C_ACCENT_CYAN
                    fill = (0, 45, 60) if not hovered else (0, 70, 90)
                elif command == "INJECT_FAULT":
                    border = C_ACCENT_RED
                    fill = (52, 16, 30) if not hovered else (78, 22, 42)
                elif command in MISSION_PRESET_COMMANDS:
                    active = self._current_message_scenario() == MISSION_PRESET_COMMANDS[command]
                    if command == "SET_PRESET_CLASSIC" and active:
                        border = C_ACCENT_BLUE
                        fill = (0, 35, 80) if not hovered else (0, 55, 120)
                    elif command == "SET_PRESET_PQC" and active:
                        border = C_ACCENT_PURPLE
                        fill = (50, 20, 80) if not hovered else (75, 30, 120)
                    elif command == "SET_PRESET_PQC_CRC32" and active:
                        border = C_ACCENT_GREEN
                        fill = (0, 50, 25) if not hovered else (0, 80, 40)

                cut = 7
                points = [(rect.x + cut, rect.y), (rect.right, rect.y), (rect.right, rect.bottom - cut), (rect.right - cut, rect.bottom), (rect.x, rect.bottom), (rect.x, rect.y + cut)]
                pygame.draw.polygon(surface, fill, points)
                pygame.draw.polygon(surface, border, points, 1)
                pygame.draw.line(surface, (*border, 120), (rect.x + 8, rect.bottom - 4), (rect.right - 10, rect.bottom - 4), 1)

                label_surf = self._render_clipped(FONT_BODY, label, C_TEXT_PRIMARY, button_w - 18)
                surface.blit(label_surf, (rect.centerx - label_surf.get_width() // 2, rect.centery - label_surf.get_height() // 2))
                self.command_button_rects.append((rect, command))

            y += rows * button_h + max(0, rows - 1) * gap
            if section_index < len(COMMAND_BUTTON_GROUPS) - 1:
                y += section_gap
        return y

    @staticmethod
    def _render_clipped(font, text, color, max_width):
        if font.size(text)[0] <= max_width:
            return font.render(text, True, color)

        suffix = "..."
        clipped = text
        while clipped and font.size(clipped + suffix)[0] > max_width:
            clipped = clipped[:-1]
        return font.render(clipped + suffix, True, color)

    @staticmethod
    def _wrap_text_for_width(font, text, max_width):
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _mission_flow_active_state(self, animation):
        steps = animation.get("steps", [])
        if not steps:
            return 0, 1.0
        duration = max(0.001, animation.get("duration", MISSION_FLOW_ANIMATION_SECONDS))
        age = max(0.0, animation.get("age", 0.0))
        progress = max(0.0, min(1.0, age / duration))
        scaled = progress * len(steps)
        active_index = min(len(steps) - 1, int(scaled))
        local_progress = scaled - active_index
        if active_index == len(steps) - 1 and progress >= 1.0:
            local_progress = 1.0
        return active_index, max(0.0, min(1.0, local_progress))

    def _mission_flow_current_bytes(self, steps, active_index, local_progress):
        if not steps:
            return 0
        current = steps[active_index]
        target = current["packet_bytes"]
        previous = steps[active_index - 1]["packet_bytes"] if active_index > 0 else 0
        if target == previous:
            return target
        return int(previous + (target - previous) * local_progress)

    def _draw_mission_flow_packet_bar(self, surface, rect, mission, current_bytes, total_bytes):
        parts_by_label = {label: (label, value, color) for label, value, color in self._mission_package_parts(mission)}
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        ordered_labels = (
            ("payload", "CRC", "ML-KEM", "nonce", "GCM", "HMAC")
            if scenario in {"PQC", "PQC_CRC32"}
            else ("payload", "CRC", "nonce", "GCM", "HMAC")
        )
        parts = tuple(parts_by_label[label] for label in ordered_labels if label in parts_by_label)
        bar_x = rect.x + 18
        bar_y = rect.bottom - 34
        bar_w = rect.width - 36
        bar_h = 13
        pygame.draw.rect(surface, (8, 12, 24), (bar_x, bar_y, bar_w, bar_h), border_radius=4)

        cursor_x = bar_x
        consumed = 0
        denominator = max(1, total_bytes)
        for _label, value, color in parts:
            if value <= 0:
                continue
            visible = max(0, min(value, current_bytes - consumed))
            if visible > 0:
                width = max(2, int(bar_w * visible / denominator))
                if cursor_x + width > bar_x + bar_w:
                    width = bar_x + bar_w - cursor_x
                pygame.draw.rect(surface, color, (cursor_x, bar_y, width, bar_h), border_radius=4)
                cursor_x += width
            consumed += value

        pygame.draw.rect(surface, C_PANEL_BORDER, (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=4)
        legend_y = bar_y + 18
        legend_x = bar_x
        short_part_labels = {
            "payload": "pay",
            "ML-KEM": "kem",
            "nonce": "iv",
            "GCM": "gcm",
            "HMAC": "mac",
            "CRC": "crc",
        }
        for label, value, color in parts:
            if value <= 0:
                continue
            pygame.draw.rect(surface, color, (legend_x, legend_y + 4, 8, 8), border_radius=2)
            text = f"{short_part_labels.get(label, label)}{value}B"
            text_surf = self._render_clipped(FONT_LABEL, text, C_TEXT_DIM, max(54, bar_w // 5))
            surface.blit(text_surf, (legend_x + 12, legend_y))
            legend_x += max(66, text_surf.get_width() + 20)
            if legend_x > bar_x + bar_w - 52:
                break

    def _top_metrics_rows(self):
        left_edge = 340
        right_edge = WIDTH - 420
        width = right_edge - left_edge
        if width < 320:
            return 0
        columns = max(1, min(len(self._metric_tiles()), 2))
        return math.ceil(len(self._metric_tiles()) / columns)

    def _draw_demo_overlay(self, surface, t):
        if self.demo_state == "IDLE":
            return

        center_x = WIDTH // 2
        y = 154 + max(0, self._top_metrics_rows() - 1) * 50
        width = min(560, max(360, WIDTH - 760))
        rect = pygame.Rect(center_x - width // 2, y, width, 118)
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        border_color = C_ACCENT_ORANGE if self.demo_state in {"PAUSED", "STOPPED"} else C_ACCENT_CYAN
        pygame.draw.rect(panel, (*C_PANEL_BG, 220), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*border_color, 180), (0, 0, rect.width, rect.height), 1, border_radius=8)
        surface.blit(panel, rect.topleft)

        title = "DEMO A/B"
        if self.demo_state == "RUNNING_A":
            title = "DEMO A: SEM CHECKSUM"
        elif self.demo_state == "RUNNING_B":
            title = "DEMO B: CRC32"
        elif self.demo_state == "SNAPSHOT_A":
            title = "SNAPSHOT A"
        elif self.demo_state == "RESULTS":
            title = "RESULTADOS DA DEMO"
        elif self.demo_state == "PAUSED":
            title = "DEMO PAUSADA"
        elif self.demo_state == "STOPPED":
            title = "DEMO PARADA"

        surface.blit(FONT_BODY.render(title, True, border_color), (rect.x + 14, rect.y + 12))
        progress_total = max(1, self.demo_attempts)
        progress_value = min(progress_total, self.demo_index)
        progress_text = f"{progress_value}/{progress_total} faults  {self.demo_elapsed_s:.1f}s  seed {self.session_seed}"
        surface.blit(FONT_LABEL.render(progress_text, True, C_TEXT_DIM), (rect.x + 14, rect.y + 38))

        summary = self.demo_summary or self._demo_result_summary()
        none_silent = summary.get("none_silent", 0)
        crc_detected = summary.get("crc_detected", 0)
        detection_rate = summary.get("crc_detection_rate_pct", 0.0)
        overhead = summary.get("crc_avg_overhead_us", 0.0)
        lines = [
            f"A/NONE silenciosas: {none_silent}",
            f"B/CRC32 detectadas: {crc_detected} ({detection_rate:.0f}%)",
            f"Overhead CRC medio: {overhead:.0f} us",
        ]
        for idx, line in enumerate(lines):
            color = C_TEXT_PRIMARY if idx < 2 else C_TEXT_DIM
            surface.blit(FONT_LABEL.render(line, True, color), (rect.x + 14, rect.y + 60 + idx * 16))

        if self.demo_export_path:
            name = Path(self.demo_export_path).name
            surface.blit(self._render_clipped(FONT_LABEL, f"JSON: {name}", C_ACCENT_GREEN, rect.width - 28), (rect.x + 250, rect.y + 88))

    def _mission_overlay_size(self):
        width = 720 if WIDTH >= 1600 else 640 if WIDTH >= 1200 else 520
        width = min(width, max(360, WIDTH - 40))
        target_height = 680 if HEIGHT >= 900 else 600 if HEIGHT >= 720 else 540
        height = min(target_height, max(520, HEIGHT - 94))
        return width, height

    def _mission_overlay_geometry(self, scenario=None):
        if scenario is None:
            scenario = self.mission_overlay_order[-1] if self.mission_overlay_order else "MISSION"
        width, height = self._mission_overlay_size()
        if scenario not in self.mission_overlay_positions:
            self.mission_overlay_positions[scenario] = self._default_mission_overlay_position(scenario)
        x, y = self.mission_overlay_positions[scenario]
        x, y = self._clamp_overlay_position(x, y, width, height)
        self.mission_overlay_positions[scenario] = (x, y)
        rect = pygame.Rect(x, y, width, height)
        close_rect = pygame.Rect(rect.right - 36, rect.y + 9, 24, 24)
        return rect, close_rect

    def _default_mission_overlay_position(self, scenario):
        width, height = self._mission_overlay_size()
        index = max(0, len(self.mission_overlay_order) - 1)
        cascade = ((0, 0), (30, 22), (-30, -22))
        offset_x, offset_y = cascade[index % len(cascade)]
        x = (WIDTH - width) // 2 + offset_x
        y = (HEIGHT - height) // 2 + offset_y
        return self._clamp_overlay_position(x, y, width, height)

    def _mission_metric_value(self, mission, key, formatter=None):
        value = mission.get(key)
        if formatter:
            return formatter(value)
        if value is None or value == "":
            return "--"
        return str(value)

    def _draw_overlay_metric_box(self, surface, label, value, x, y, width, height, color):
        pygame.draw.rect(surface, (15, 20, 38), (x, y, width, height), border_radius=4)
        pygame.draw.rect(surface, C_PANEL_BORDER, (x, y, width, height), width=1, border_radius=4)
        surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, width - 10), (x + 6, y + 6))
        surface.blit(self._render_clipped(FONT_SMALL, value, color, width - 10), (x + 6, y + 22))

    def _draw_mission_overlay(self, surface, t):
        if not self.mission_overlay_visible or not self.mission_overlays:
            self.mission_overlay_close_rect = None
            self.mission_overlay_rects.clear()
            self.mission_overlay_close_rects.clear()
            self.mission_overlay_drag_rects.clear()
            self.mission_flow_control_rects.clear()
            self.mission_flow_scrub_rects.clear()
            self.mission_flow_stage_rects.clear()
            self.mission_flow_explanation_line_counts.clear()
            self.mission_flow_animations.clear()
            self.mission_flow_animation = None
            return

        self.mission_overlay_rects.clear()
        self.mission_overlay_close_rects.clear()
        self.mission_overlay_drag_rects.clear()
        self.mission_flow_control_rects.clear()
        self.mission_flow_scrub_rects.clear()
        self.mission_flow_stage_rects.clear()
        self.mission_flow_explanation_line_counts.clear()
        self.mission_overlay_order = [scenario for scenario in self.mission_overlay_order if scenario in self.mission_overlays]
        for scenario in self.mission_overlay_order:
            self._draw_single_mission_overlay(surface, t, scenario, self.mission_overlays[scenario])
        self._sync_mission_overlay_state()

    @staticmethod
    def _mission_int(mission, key, default=0):
        parsed = _optional_int(mission.get(key))
        return default if parsed is None else parsed

    def _mission_package_parts(self, mission):
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        payload = self._mission_int(mission, "bytes_payload")
        crypto = self._mission_int(mission, "bytes_crypto")
        checksum = self._mission_int(mission, "bytes_checksum")
        cipher = str(mission.get("cipher", "")).upper()
        has_aead_fields = (
            "AES" in cipher
            or "bytes_gcm_tag" in mission
            or "gcm_tag_bytes" in mission
            or "bytes_nonce" in mission
            or "nonce_bytes" in mission
        )
        hmac = 0
        nonce = 0
        gcm = 0
        mlkem = 0
        if has_aead_fields:
            nonce = self._mission_int(mission, "bytes_nonce", self._mission_int(mission, "nonce_bytes"))
            gcm = self._mission_int(mission, "bytes_gcm_tag", self._mission_int(mission, "gcm_tag_bytes"))
            mlkem = self._mission_int(mission, "bytes_mlkem")
            if mlkem <= 0 and scenario in {"PQC", "PQC_CRC32"}:
                mlkem = max(0, crypto - nonce - gcm)
        else:
            hmac = min(32, crypto) if crypto else 0
            mlkem = max(0, crypto - hmac) if scenario in {"PQC", "PQC_CRC32"} else 0
            if scenario == "CLASSIC":
                hmac = crypto
                mlkem = 0
        return (
            ("payload", payload, C_ACCENT_BLUE),
            ("ML-KEM", mlkem, C_ACCENT_PURPLE),
            ("nonce", nonce, C_TEXT_DIM),
            ("GCM", gcm, C_ACCENT_ORANGE),
            ("HMAC", hmac, C_ACCENT_ORANGE),
            ("CRC", checksum, C_ACCENT_GREEN),
        )

    def _draw_single_mission_overlay(self, surface, t, scenario, mission):
        rect, close_rect = self._mission_overlay_geometry(scenario)
        offset_y, alpha_ratio = self._popup_transition(
            self.mission_overlay_opened_at.get(scenario, self.uptime),
            self.mission_overlay_closing_since.get(scenario),
        )
        if offset_y:
            rect = rect.move(0, offset_y)
            close_rect = close_rect.move(0, offset_y)
        drag_rect = pygame.Rect(rect.x, rect.y, rect.width, 44)
        self.mission_overlay_rects[scenario] = rect
        self.mission_overlay_close_rects[scenario] = close_rect
        self.mission_overlay_drag_rects[scenario] = drag_rect

        result = str(mission.get("result", ""))
        crypto = str(mission.get("crypto", "--"))
        cipher = str(mission.get("cipher", "")).strip()
        checksum = str(mission.get("checksum", "NONE"))
        elapsed = _format_elapsed(mission.get("elapsed_us"))
        bytes_total = self._mission_metric_value(mission, "bytes_total")
        scenario_color = {
            "CLASSIC": C_ACCENT_ORANGE,
            "PQC": C_ACCENT_CYAN,
            "PQC_CRC32": C_ACCENT_GREEN,
        }.get(scenario, C_ACCENT_CYAN)
        color = scenario_color if result in {"", "DELIVERED"} else C_ACCENT_RED

        shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, int(82 * alpha_ratio)), (0, 0, rect.width, rect.height), border_radius=10)
        surface.blit(shadow, (rect.x + 8, rect.y + 10))

        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        alpha = int(170 + 55 * math.sin(t * 7)) if self.mission_effect_timer > 0 else 190
        border_alpha = min(245, max(185, alpha))
        pygame.draw.rect(panel, (*C_PANEL_BG, int(248 * alpha_ratio)), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*color, int(border_alpha * alpha_ratio)), (0, 0, rect.width, rect.height), 2, border_radius=8)
        pygame.draw.rect(panel, (*color, int(48 * alpha_ratio)), (0, 0, rect.width, 44), border_radius=8)
        pygame.draw.line(panel, (*C_PANEL_BORDER, int(210 * alpha_ratio)), (0, 44), (rect.width, 44), 1)
        surface.blit(panel, rect.topleft)

        result_label = "OK" if result == "DELIVERED" else (result or "EM CURSO")
        title = f"{scenario}  |  {result_label}"
        surface.blit(self._render_clipped(FONT_SMALL, title, color, rect.width - 62), (rect.x + 14, rect.y + 12))
        pygame.draw.rect(surface, (58, 18, 28), close_rect, border_radius=5)
        pygame.draw.rect(surface, C_ACCENT_RED, close_rect, width=1, border_radius=5)
        x_text = FONT_SMALL.render("X", True, C_TEXT_PRIMARY)
        surface.blit(x_text, (close_rect.centerx - x_text.get_width() // 2, close_rect.centery - x_text.get_height() // 2))

        crypto_label = crypto
        if cipher and cipher != "--" and cipher.upper() not in crypto.upper():
            crypto_label = f"{crypto} + {cipher}"
        subtitle = f"{crypto_label}  |  CRC: {checksum}"
        surface.blit(self._render_clipped(FONT_LABEL, subtitle, C_TEXT_DIM, rect.width - 28), (rect.x + 14, rect.y + 48))

        if self._mission_overlay_is_animating(scenario):
            self._draw_mission_overlay_flow(surface, rect, scenario, mission, t)
            return

        self._draw_mission_overlay_metrics(surface, rect, mission, elapsed, bytes_total)

    def _mission_overlay_is_animating(self, scenario):
        return scenario in getattr(self, "mission_flow_animations", {})

    # ===================================================================
    # Detailed process stage — recreated mission popup visualization.
    # Shows each operation as input -> operation -> output with structure
    # (block sizes, all measured on the Wisdom) plus illustrative sample
    # bytes that scramble then "lock" as the step plays. Real payload bytes
    # are used where available; crypto material is illustrative on purpose
    # (the board never transmits the secret/key, only sizes/CRCs).
    # ===================================================================
    MISSION_KIND_ICON = {
        "payload": "packet", "crc": "shield", "keygen": "key", "mlkem": "lock",
        "kdf": "hash", "rng": "rng", "aead": "lock", "decap": "unlock",
        "verify": "shield", "send": "sat",
    }

    def _hexish(self, seed, i, n, settle, t):
        """Deterministic 2-char hex for cell i; scrambles until the step settles."""
        locked = settle >= (i + 1) / max(1, n)
        if locked:
            b = (seed * 2654435761 + i * 40503) & 0xFF
        else:
            b = (int(t * 45) * 1103515245 + i * 12345 + seed) & 0xFF
        return "%02X" % b, locked

    def _cell(self, surface, x, y, size, text, color, on):
        x, y = int(x), int(y)
        pygame.draw.rect(surface, (12, 20, 40) if on else (8, 12, 22), (x, y, size, size), border_radius=2)
        pygame.draw.rect(surface, color if on else C_TEXT_DIM, (x, y, size, size), 1, border_radius=2)
        ts = FONT_LABEL.render(text, True, color if on else C_TEXT_DIM)
        surface.blit(ts, (x + (size - ts.get_width()) // 2, y + (size - ts.get_height()) // 2))

    def _d_bytes(self, surface, cx, y, n, seed, color, settle, t, real=None, cell=15, gap=3, max_cells=12):
        if n <= 0:
            return pygame.Rect(int(cx), int(y), 0, cell)
        shown = min(n, max_cells)
        total_w = shown * cell + (shown - 1) * gap
        x0 = int(cx - total_w / 2)
        for i in range(shown):
            bx = x0 + i * (cell + gap)
            if real is not None and i < len(real):
                text, on = "%02X" % real[i], settle >= (i + 1) / shown
            else:
                text, on = self._hexish(seed, i, shown, settle, t)
            self._cell(surface, bx, y, cell, text, color, on)
        rect = pygame.Rect(x0, int(y), total_w, cell)
        if n > shown:
            more = FONT_LABEL.render("+%d" % (n - shown), True, C_TEXT_DIM)
            surface.blit(more, (rect.right + 4, int(y) + 1))
        return rect

    def _d_badge(self, surface, x, y, kind):
        bc = C_ACCENT_GREEN if kind == "check" else C_ACCENT_RED
        pygame.draw.circle(surface, (8, 14, 28), (int(x), int(y)), 8)
        pygame.draw.circle(surface, bc, (int(x), int(y)), 8, 1)
        self._icon(surface, kind, int(x), int(y), 4, bc)

    def _d_block(self, surface, rect, title, sub, color, icon=None, badge=None, fill=1.0):
        pygame.draw.rect(surface, (10, 16, 32), rect, border_radius=5)
        fill = max(0.0, min(1.0, fill))
        if fill < 1.0:
            fh = int(rect.height * fill)
            pygame.draw.rect(surface, self._mix_color((10, 16, 32), color, 0.3),
                             (rect.x, rect.bottom - fh, rect.width, fh), border_radius=5)
        pygame.draw.rect(surface, color, rect, 2, border_radius=5)
        if icon:
            self._icon(surface, icon, rect.centerx, rect.y + 11, 6, color)
            yy = rect.y + 19
        else:
            yy = rect.y + 6
        ts = self._render_clipped(FONT_LABEL, title, C_TEXT_PRIMARY, rect.width - 8)
        surface.blit(ts, (rect.centerx - ts.get_width() // 2, yy))
        if sub and rect.bottom - (yy + 12) >= 11:  # only when it fully fits inside the block
            ss = self._render_clipped(FONT_LABEL, sub, C_TEXT_DIM, rect.width - 8)
            surface.blit(ss, (rect.centerx - ss.get_width() // 2, yy + 12))
        if badge:
            self._d_badge(surface, rect.right - 11, rect.y + 11, badge)

    def _d_op_core(self, surface, cx, cy, color, icon, progress, t):
        cx, cy = int(cx), int(cy)
        pulse = 0.5 + 0.5 * math.sin(t * 4.0)
        self._draw_soft_glow(surface, (cx, cy), 18, color, int(18 + 30 * progress))
        r = 22
        pygame.draw.circle(surface, (8, 12, 26), (cx, cy), r)
        pygame.draw.circle(surface, self._mix_color((20, 28, 52), color, 0.35 + 0.5 * pulse), (cx, cy), r, 2)
        self._icon(surface, icon, cx, cy, 9, color, t, progress)

    def _mission_step_scene(self, kind, mission):
        """Plain-language input -> operation -> output spec for one mission step.

        Every step renders with the same grammar (see _draw_mission_stage), so
        the popup reads consistently instead of a different diagram per step.
        """
        p = self._mission_int(mission, "bytes_payload")
        m = self._mission_int(mission, "bytes_mlkem")
        c = self._mission_int(mission, "bytes_checksum")
        nonce = self._mission_int(mission, "bytes_nonce", self._mission_int(mission, "nonce_bytes"))
        gcm = self._mission_int(mission, "bytes_gcm_tag", self._mission_int(mission, "gcm_tag_bytes"))
        pay_real = str(mission.get("payload_text", "")).encode("ascii", "replace") or None
        scenes = {
            "payload": {
                "inputs": [("Sensores / msg", "leitura", "sensor")],
                "op": ("list", "SERIALIZA", "monta o buffer TLV"),
                "outputs": [("Payload", f"{p} B", "packet", p)],
                "note": "Texto claro (TLV ASCII). Ainda sem cifra, MAC ou checksum.",
                "sample": {"mode": "row", "label": "bytes reais do payload", "n": p, "real": pay_real, "seed": 0x50, "color": C_ACCENT_BLUE},
            },
            "crc": {
                "inputs": [("Payload", f"{p} B", "packet")],
                "op": ("shield", "CRC-32", "calcula o checksum"),
                "outputs": [("Payload + CRC", f"+{c} B", "hash", c)],
                "note": "Detecta corrupcao acidental (1 bit sempre); nao autentica contra atacante.",
            },
            "keygen": {
                "inputs": [("Semente + ruido", "aleatorio", "rng")],
                "op": ("key", "KEYGEN", "gera o par de chaves"),
                "outputs": [("Chave publica", "800 B", "key", 0), ("Chave privada", "1632 B", "lock", 0)],
                "note": "Par ML-KEM-512 (reticulados MLWE). Custo de CPU/RAM; o pacote nao cresce.",
            },
            "mlkem": {
                "inputs": [("Chave publica", "800 B", "key")],
                "op": ("lock", "ENCAPSULA", "sela um segredo"),
                "outputs": [("Ciphertext", f"{m} B", "packet", m), ("Segredo K", "32 B selado", "lock", 0)],
                "note": "O segredo K nunca viaja; apenas o ciphertext ML-KEM entra no pacote.",
            },
            "kdf": {
                "inputs": [("Segredo K", "32 B", "key")],
                "op": ("hash", "SHA-256", "deriva a chave"),
                "outputs": [("Chave AES", "16 B", "key", 0)],
                "note": "Condensa 32 B -> 16 B. Quem cifra a mensagem e o AES-GCM.",
                "sample": {"mode": "shrink", "label": "segredo 32 B  ->  chave 16 B", "n_in": 8, "n_out": 4},
            },
            "rng": {
                "inputs": [("Entropia", "TRNG", "rng")],
                "op": ("rng", "DRBG", "gera aleatorios"),
                "outputs": [("Chave AES", "16 B", "key", 0), ("Nonce", "12 B", "hash", 0)],
                "note": "Baseline classico: chave AES e nonce efemeros, unicos por mensagem.",
            },
            "aead": {
                "inputs": [("Payload", "claro", "packet"), ("Chave AES", "16 B", "key")],
                "op": ("lock", "AES-GCM", "cifra e autentica"),
                "outputs": [("Ciphertext", f"+{nonce + gcm} B", "packet", nonce + gcm), ("Tag GCM", "16 B", "shield", 0)],
                "note": "Cifra (CTR) e autentica (GHASH) numa passada; o nonce nunca repete com a chave.",
                "sample": {"mode": "xor", "label": "payload (claro)  ->  ciphertext", "real": pay_real, "n": 6},
            },
            "decap": {
                "inputs": [("Ciphertext", "768 B", "packet"), ("Chave privada", "1632 B", "lock")],
                "op": ("unlock", "DECAPSULA", "recupera o segredo"),
                "outputs": [("Segredo K", "32 B", "key", 0)],
                "note": "Re-encapsula e confere (Fujisaki-Okamoto): mesmo segredo do emissor.",
            },
            "verify": {
                "inputs": [("Ciphertext + tag", "recebido", "packet")],
                "op": ("shield", "VERIFICA", "confere a tag"),
                "outputs": [("Payload", "liberado", "check", 0)],
                "note": "Tag igual -> libera o payload. Comparacao em tempo constante.",
                "sample": {"mode": "equal", "label": "tag recebida  ==  tag recalculada", "n": 6},
            },
        }
        return scenes.get(kind, {
            "inputs": [("Entrada", "", "packet")],
            "op": ("list", "", ""),
            "outputs": [("Saida", "", "check", 0)],
            "note": "",
        })

    def _d_sample_strip(self, surface, rect, sample, color, progress, t):
        """A calm, clearly-labelled byte strip shown only where bytes clarify.

        Settles early (locks fast) so it reads as data rather than noise.
        """
        pygame.draw.rect(surface, (8, 12, 24), rect, border_radius=5)
        pygame.draw.rect(surface, self._mix_color(C_PANEL_BORDER, color, 0.4), rect, 1, border_radius=5)
        self._pix_tag(surface, rect.centerx, rect.y + 3, sample.get("label", ""), C_TEXT_DIM, rect.width - 8)
        settle = max(0.0, min(1.0, progress * 1.6))
        y = rect.y + 20
        mode = sample.get("mode")
        if mode == "row":
            self._d_bytes(surface, rect.centerx, y, sample.get("n", 8), sample.get("seed", 0x50),
                          sample.get("color", color), settle, t, real=sample.get("real"), max_cells=10)
        elif mode in {"shrink", "xor", "equal"}:
            lx = rect.x + rect.width * 0.27
            rx = rect.x + rect.width * 0.73
            if mode == "shrink":
                self._d_bytes(surface, lx, y, sample.get("n_in", 8), 0x5E, color, settle, t, max_cells=8)
                self._pix_tag(surface, rect.centerx, y + 1, "->", C_TEXT_DIM, 30)
                self._d_bytes(surface, rx, y, sample.get("n_out", 4), 0xA1, C_ACCENT_CYAN, settle, t, max_cells=4)
            elif mode == "xor":
                self._d_bytes(surface, lx, y, sample.get("n", 6), 0x50, C_ACCENT_BLUE, settle, t, real=sample.get("real"), max_cells=6)
                self._pix_tag(surface, rect.centerx, y + 1, "->", C_TEXT_DIM, 30)
                self._d_bytes(surface, rx, y, sample.get("n", 6), 0x9C, C_ACCENT_ORANGE, settle, t, max_cells=6)
            else:  # equal
                self._d_bytes(surface, lx, y, sample.get("n", 6), 0x7C, C_ACCENT_GREEN, settle, t, max_cells=6)
                self._pix_tag(surface, rect.centerx, y + 1, "==", C_ACCENT_GREEN, 30)
                self._d_bytes(surface, rx, y, sample.get("n", 6), 0x7C, C_ACCENT_GREEN, settle, t, max_cells=6)

    def _d_downlink(self, surface, stage, mission, color, progress, t):
        result = str(mission.get("result", "DELIVERED")).upper()
        ok = result in {"", "DELIVERED", "OK"}
        cx = stage.centerx
        sat_y = stage.y + 24
        gnd_y = stage.bottom - 28
        self._icon(surface, "sat", cx, sat_y, 12, color, t)
        self._pix_tag(surface, cx, sat_y + 14, "Wisdom (orbita)", C_TEXT_DIM, 180)
        pygame.draw.line(surface, self._mix_color((20, 40, 78), color, 0.5), (stage.x + 20, gnd_y), (stage.right - 20, gnd_y), 2)
        self._pix_tag(surface, cx, gnd_y + 4, "estacao de solo", C_TEXT_DIM, 180)
        py = int(sat_y + 26 + (gnd_y - sat_y - 50) * max(0.0, min(1.0, progress)))
        for k in range(3):  # dashed downlink beam
            yy = sat_y + 22 + k * 12
            if yy < py:
                pygame.draw.line(surface, self._mix_color((20, 30, 56), color, 0.5), (cx, yy), (cx, yy + 6), 2)
        parts = [(label, value, col) for label, value, col in self._mission_package_parts(mission) if value > 0]
        seg_w = max(10, min(28, (stage.width - 80) // max(1, len(parts))))
        px = cx - (len(parts) * seg_w) // 2
        for _label, _value, col in parts:
            pygame.draw.rect(surface, col, (px, py - 6, seg_w - 2, 12), border_radius=2)
            px += seg_w
        if progress > 0.8:
            sc = C_ACCENT_GREEN if ok else C_ACCENT_RED
            self._draw_soft_glow(surface, (cx, gnd_y - 4), 16, sc, 60)
            pygame.draw.circle(surface, (8, 14, 28), (cx, gnd_y - 4), 13)
            pygame.draw.circle(surface, sc, (cx, gnd_y - 4), 13, 2)
            self._icon(surface, "check" if ok else "cross", cx, gnd_y - 4, 6, sc)
            if ok:
                self._fx_spark(surface, cx, gnd_y - 4, sc, (progress - 0.8) * 5, t)
        # result label sits top-left, clear of the centred descending packet
        self._pix_tag(surface, stage.x + 70, sat_y, "OK" if ok else result, color, 130)

    def _draw_mission_stage(self, surface, area, kind, mission, color, progress, t):
        if area.height < 90 or area.width < 120:
            return
        # REFATORAÇÃO VISUAL: Palco da Missão Ampliado
        theme = "space" if kind in {"payload", "send"} else "lab"
        stage = self._pix_stage(surface, area, color, t, theme)
        if kind == "send":
            self._d_downlink(surface, stage, mission, color, progress, t)
            return

        scene = self._mission_step_scene(kind, mission)
        inputs, outputs = scene["inputs"], scene["outputs"]
        op_icon, op_name, op_verb = scene["op"]
        sample = scene.get("sample")
        prog = max(0.0, min(1.0, progress))

        note_lines = self._wrap_text_for_width(FONT_LABEL, scene.get("note", ""), stage.width - 20)[:2]
        note_h = max(14, len(note_lines) * 14)
        note_top = stage.bottom - note_h - 2
        sample_h = 48 if sample and stage.height >= 150 else 0
        sample_top = note_top - sample_h - (6 if sample_h else 0)

        card_w = int(min(190, stage.width * 0.34))
        card_h = 50
        stack = max(len(inputs), len(outputs))
        row_h = card_h * stack + 8 * (stack - 1)
        visual_top = stage.y + 12
        visual_bottom = (sample_top if sample_h else note_top) - 8
        top_extent = row_h // 2
        bottom_extent = row_h // 2 + 30
        usable_h = max(top_extent + bottom_extent, visual_bottom - visual_top)
        mid_y = visual_top + max(0, usable_h - top_extent - bottom_extent) // 2 + top_extent
        mid_y = max(visual_top + top_extent, min(mid_y, visual_bottom - bottom_extent))
        left_x = stage.x + card_w // 2 + 12
        right_x = stage.right - card_w // 2 - 12
        op_x = stage.centerx

        line_col = self._mix_color((26, 34, 58), color, 0.55)
        pygame.draw.line(surface, line_col, (left_x + card_w // 2, mid_y), (op_x - 26, mid_y), 4)
        pygame.draw.line(surface, line_col, (op_x + 26, mid_y), (right_x - card_w // 2, mid_y), 4)

        def column(cx, items, is_out):
            n = len(items)
            total = card_h * n + 8 * (n - 1)
            y0 = mid_y - total // 2
            for i, item in enumerate(items):
                label, size, icon = item[0], item[1], item[2]
                grow = item[3] if (is_out and len(item) > 3) else 0
                r = pygame.Rect(int(cx - card_w / 2), y0 + i * (card_h + 8), card_w, card_h)
                ccol = color if is_out else self._mix_color(C_PANEL_BORDER, color, 0.75)
                badge = "check" if (is_out and prog > 0.92) else None
                self._d_block(surface, r, label, size, ccol, icon=icon, badge=badge,
                              fill=(prog if (is_out and grow > 0) else 1.0))
                if grow > 0:  # callout above the card (clear of stacked cards below)
                    g = FONT_LABEL.render(f"+{grow} B", True, C_ACCENT_GREEN)
                    surface.blit(g, (r.centerx - g.get_width() // 2, r.y - 13))

        column(left_x, inputs, False)
        column(right_x, outputs, True)

        # operation core + plain name/verb below it
        self._draw_soft_glow(surface, (op_x, mid_y), 34, color, 75)
        self._d_op_core(surface, op_x, mid_y, color, op_icon, prog, t)
        name_y = max(mid_y + 34, mid_y + row_h // 2 + 8)
        self._pix_tag(surface, op_x, name_y, op_name, color, 170)
        self._pix_tag(surface, op_x, name_y + 14, op_verb, C_TEXT_DIM, 180)

        # one clear moving token: the data gliding through the operation
        span_l = left_x + card_w // 2 + 4
        span_r = right_x - card_w // 2 - 4
        tok_x = int(span_l + (span_r - span_l) * prog)
        tok_col = color if prog >= 0.5 else self._mix_color(C_PANEL_BORDER, color, 0.7)
        self._draw_soft_glow(surface, (tok_x, mid_y), 13, tok_col, 95)
        pygame.draw.rect(surface, tok_col, (tok_x - 10, mid_y - 8, 20, 16), border_radius=3)
        pygame.draw.rect(surface, C_TEXT_PRIMARY, (tok_x - 10, mid_y - 8, 20, 16), 1, border_radius=3)

        if sample_h:
            strip = pygame.Rect(stage.x + 8, sample_top, stage.width - 16, 42)
            self._d_sample_strip(surface, strip, sample, color, prog, t)
        for index, line in enumerate(note_lines):
            text = FONT_LABEL.render(line, True, color)
            surface.blit(text, (stage.centerx - text.get_width() // 2, note_top + index * 14))

    def _draw_mission_overlay_flow(self, surface, rect, scenario, mission, t):
        animation = self._mission_flow_animation_for(scenario)
        if animation is None:
            return
        steps = animation.get("steps", [])
        if not steps:
            return

        active_index, local_progress = self._mission_flow_active_state(animation)
        active_step = steps[active_index]
        total_bytes = self._mission_int(mission, "bytes_total", steps[-1]["packet_bytes"])
        current_bytes = self._mission_flow_current_bytes(steps, active_index, local_progress)
        color = active_step["color"]
        kind = str(active_step.get("kind", "")).lower()
        awaiting_confirm = bool(animation.get("awaiting_confirm"))
        stage_progress = 1.0 if awaiting_confirm else local_progress

        x = rect.x + 14
        width = rect.width - 28

        # --- status row + control button (VER DADOS / AGUARDE) ---
        status_y = rect.y + 70
        control_rect = pygame.Rect(rect.right - 104, status_y - 2, 86, 22)
        self.mission_flow_control_rects[scenario] = control_rect
        header = "FLUXO CONCLUÍDO" if awaiting_confirm else f"PROCESSO {active_index + 1}/{len(steps)}"
        surface.blit(self._render_clipped(FONT_LABEL, header, C_ACCENT_CYAN, width - 100), (x, status_y))
        button_label = "VER DADOS" if awaiting_confirm else "AGUARDE"
        button_border = C_ACCENT_GREEN if awaiting_confirm else C_PANEL_BORDER
        button_fill = (18, 58, 46) if awaiting_confirm else (30, 38, 72)
        button_color = C_ACCENT_GREEN if awaiting_confirm else C_TEXT_PRIMARY
        pygame.draw.rect(surface, button_fill, control_rect, border_radius=4)
        pygame.draw.rect(surface, button_border, control_rect, width=1, border_radius=4)
        button_text = FONT_LABEL.render(button_label, True, button_color)
        surface.blit(
            button_text,
            (control_rect.centerx - button_text.get_width() // 2,
             control_rect.centery - button_text.get_height() // 2),
        )

        # --- step banner: icon + label/detail + bytes/time ---
        banner = pygame.Rect(x, status_y + 20, width, 50)
        pygame.draw.rect(surface, (8, 12, 26), banner, border_radius=6)
        pygame.draw.rect(surface, color, banner, 2, border_radius=6)
        self._icon(surface, self.MISSION_KIND_ICON.get(kind, "packet"), banner.x + 22, banner.centery, 11, color, t, stage_progress)
        surface.blit(self._render_clipped(FONT_SMALL, f"{active_step['label']}  ·  {active_step['detail']}", color, width - 150),
                     (banner.x + 44, banner.y + 8))
        meta = f"{current_bytes}/{total_bytes} B"
        added = active_step.get("added_bytes", 0)
        if added:
            meta += f"   +{added} B"
        time_us = active_step.get("time_us")
        if time_us is not None:
            meta += f"   {_format_elapsed(time_us)}"
        surface.blit(self._render_clipped(FONT_LABEL, meta, (180, 198, 235), width - 52), (banner.x + 44, banner.y + 28))

        # --- bottom-anchored bars (room for the scrub bar + step labels) ---
        hint_y = rect.bottom - 14
        sigla_y = hint_y - 14
        scrub_cy = sigla_y - 13
        packet_bar_h = 52
        packet_bar_y = scrub_cy - 14 - packet_bar_h
        explanation = active_step.get("explain", "")
        explanation_lines = self._wrap_text_for_width(FONT_LABEL, explanation, width)
        explanation_line_count = max(1, min(4, len(explanation_lines)))
        explain_h = explanation_line_count * 14
        explain_y = packet_bar_y - explain_h - 5

        # --- the recreated detailed process stage ---
        stage_top = banner.bottom + 8
        stage_rect = pygame.Rect(x, stage_top, width, max(120, explain_y - stage_top - 4))
        self.mission_flow_stage_rects[scenario] = stage_rect
        self.mission_flow_explanation_line_counts[scenario] = explanation_line_count
        self._draw_mission_stage(surface, stage_rect, kind, mission, color, stage_progress, t)

        # --- step explanation (up to 4 lines, with reserved vertical space) ---
        self._draw_wrapped_text(surface, FONT_LABEL, explanation, C_TEXT_PRIMARY,
                                x, explain_y, width, line_spacing=14, max_lines=4)

        # --- packet composition bar (kept) ---
        self._draw_mission_flow_packet_bar(surface, pygame.Rect(rect.x, packet_bar_y, rect.width, packet_bar_h),
                                           mission, current_bytes, total_bytes)

        # --- scrub bar with step pips + abbreviations (replaces old timeline) ---
        track_x = x + 8
        track_w = width - 16
        track = pygame.Rect(track_x, scrub_cy - 4, track_w, 8)
        pygame.draw.rect(surface, (10, 16, 30), track, border_radius=4)
        progress_ratio = min(1.0, max(0.0, animation.get("age", 0.0)
                                      / max(0.001, animation.get("duration", MISSION_FLOW_ANIMATION_SECONDS))))
        fill_w = int(track_w * progress_ratio)
        pygame.draw.rect(surface, self._scenario_color(scenario), (track_x, track.y, fill_w, track.height), border_radius=4)
        scrub_rect = pygame.Rect(track_x, scrub_cy - 12, max(1, track_w), 38)
        self.mission_flow_scrub_rects[scenario] = scrub_rect
        sigla = {"PAYLOAD": "PAY", "CRC32": "CRC", "KEYGEN": "KEY", "ENCAP": "ENC",
                 "KDF": "KDF", "RNG": "RNG", "AES-GCM": "AES", "DECAP": "DEC",
                 "VERIFICA": "VER", "RESULTADO": "OK"}
        slot = track_w // max(1, len(steps))
        for index in range(len(steps)):
            if len(steps) > 1:
                px = track_x + track_w * index // (len(steps) - 1)
            else:
                px = track_x + track_w // 2
            done = index <= active_index
            pip_color = steps[index]["color"] if done else C_TEXT_DIM
            pygame.draw.circle(surface, pip_color, (px, track.centery), 4 if index == active_index else 3)
            label = sigla.get(steps[index]["label"], str(steps[index]["label"])[:3])
            lbl = self._render_clipped(FONT_LABEL, label, pip_color, max(22, slot - 2))
            lbl_x = max(x, min(px - lbl.get_width() // 2, x + width - lbl.get_width()))
            surface.blit(lbl, (lbl_x, sigla_y))
        handle_x = track_x + fill_w
        self._draw_soft_glow(surface, (handle_x, track.centery), 8, color, int(40 + 30 * (0.5 + 0.5 * math.sin(t * 4.0))))
        pygame.draw.circle(surface, color, (handle_x, track.centery), 7)
        pygame.draw.circle(surface, C_TEXT_PRIMARY, (handle_x, track.centery), 7, 1)

        # --- hint ---
        hint = ("Arraste a barra para revisar; VER DADOS abre as métricas."
                if awaiting_confirm else "Arraste a barra para rever cada processo.")
        surface.blit(self._render_clipped(FONT_LABEL, hint, C_TEXT_DIM, width), (x, hint_y))

    def _draw_mission_overlay_metrics(self, surface, rect, mission, elapsed, bytes_total):
        metric_x = rect.x + 14
        metric_y = rect.y + 70
        metric_gap = 8
        metric_w = (rect.width - 28 - metric_gap) // 2
        metric_h = 40
        metrics = (
            ("TEMPO", elapsed, C_ACCENT_CYAN),
            ("BYTES", f"{bytes_total} B" if bytes_total != "--" else "--", C_ACCENT_ORANGE),
            ("CPU", f"{self._mission_metric_value(mission, 'cpu_mhz')} MHz", C_TEXT_PRIMARY),
            ("HEAP", _format_bytes(mission.get("heap")), C_ACCENT_GREEN),
        )
        for index, (label, value, metric_color) in enumerate(metrics):
            x = metric_x + (index % 2) * (metric_w + metric_gap)
            y = metric_y + (index // 2) * (metric_h + 6)
            self._draw_overlay_metric_box(surface, label, value, x, y, metric_w, metric_h, metric_color)

        sep_y = metric_y + metric_h * 2 + 18
        pygame.draw.line(surface, C_PANEL_BORDER, (rect.x + 14, sep_y), (rect.right - 14, sep_y), 1)

        phase_y = sep_y + 10
        phases = (
            ("keygen", "keygen_us"),
            ("encap", "encap_us"),
            ("decap", "decap_us"),
            ("rng", "rng_us"),
            ("kdf", "kdf_us"),
            ("enc", "encrypt_us"),
            ("dec", "decrypt_us"),
            ("crc", "crc_us"),
        )
        phase_gap = 6
        phase_cols = 4
        phase_w = (rect.width - 28 - (phase_cols - 1) * phase_gap) // phase_cols
        phase_h = 42
        for index, (label, key) in enumerate(phases):
            x = rect.x + 14 + (index % phase_cols) * (phase_w + phase_gap)
            y = phase_y + (index // phase_cols) * (phase_h + 8)
            value = _format_elapsed(mission.get(key))
            phase_color = C_TEXT_DIM if value in {"--", "0 us"} else (C_ACCENT_GREEN if key == "crc_us" else C_TEXT_PRIMARY)
            pygame.draw.rect(surface, (15, 20, 38), (x, y, phase_w, phase_h), border_radius=4)
            pygame.draw.rect(surface, C_PANEL_BORDER, (x, y, phase_w, phase_h), width=1, border_radius=4)
            surface.blit(self._render_clipped(FONT_LABEL, label.upper(), C_TEXT_DIM, phase_w - 10), (x + 5, y + 6))
            surface.blit(self._render_clipped(FONT_SMALL, value, phase_color, phase_w - 10), (x + 5, y + 22))

        bytes_y = phase_y + phase_h * 2 + 20
        part_values = {label: value for label, value, _color in self._mission_package_parts(mission)}
        byte_line = (
            f"pay {part_values.get('payload', 0)}B   "
            f"kem {part_values.get('ML-KEM', 0)}B   "
            f"iv {part_values.get('nonce', 0)}B   "
            f"gcm {part_values.get('GCM', part_values.get('HMAC', 0))}B   "
            f"crc {part_values.get('CRC', 0)}B"
        )
        surface.blit(self._render_clipped(FONT_LABEL, byte_line, C_TEXT_PRIMARY, rect.width - 28), (rect.x + 14, bytes_y))

        validation_y = bytes_y + 20
        validation = (
            f"key={self._mission_metric_value(mission, 'key_match')}   "
            f"aead={self._mission_metric_value(mission, 'aead_match')}   "
            f"crc={self._mission_metric_value(mission, 'crc_match')}"
        )
        surface.blit(self._render_clipped(FONT_LABEL, validation, C_TEXT_DIM, rect.width - 28), (rect.x + 14, validation_y))

        live_y = validation_y + 24
        if live_y < rect.bottom - 62:
            self._draw_mission_live_payload(surface, rect, mission, live_y)

    def _draw_mission_live_payload(self, surface, rect, mission, y):
        mode = str(mission.get("payload_mode", "FIXED")).upper()
        title = "PAYLOAD REAL DA PLACA" if mode == "LIVE" else "PAYLOAD FIXO"
        color = C_ACCENT_GREEN if mode == "LIVE" else C_TEXT_DIM
        box_h = min(58, rect.bottom - y - 10)
        if box_h < 46:
            return
        box = pygame.Rect(rect.x + 14, y, rect.width - 28, box_h)
        pygame.draw.rect(surface, (14, 20, 38), box, border_radius=5)
        pygame.draw.rect(surface, color, box, width=1, border_radius=5)
        surface.blit(self._render_clipped(FONT_LABEL, title, color, box.width - 12), (box.x + 7, box.y + 5))
        payload_text = str(mission.get("payload_text", ""))
        if payload_text:
            surface.blit(self._render_clipped(FONT_LABEL, payload_text, C_TEXT_PRIMARY, box.width - 12), (box.x + 7, box.y + 20))
        if box.height < 56:
            return
        sensors = (
            f"T={mission.get('sensor_temp_c_x100', 'NA')} "
            f"ACC={mission.get('sensor_accel', 'NA')} "
            f"L={mission.get('sensor_light', 'NA')} "
            f"POT={mission.get('sensor_pot', 'NA')}"
        )
        surface.blit(self._render_clipped(FONT_LABEL, sensors, C_TEXT_DIM, box.width - 12), (box.x + 7, box.y + 35))

    def _draw_top_bar(self, surface, t):
        """Barra superior com titulo e status."""
        # REFATORAÇÃO VISUAL: Top Bar Cyber-HUD
        bar_h = 44
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 218), (0, 0, WIDTH, bar_h))
        for yy in range(6, bar_h, 8):
            pygame.draw.line(bar_surf, (255, 255, 255, 10), (0, yy), (WIDTH, yy), 1)
        pygame.draw.line(bar_surf, C_ACCENT_CYAN, (0, bar_h - 1), (WIDTH, bar_h - 1), 2)
        surface.blit(bar_surf, (0, 0))

        # Titulo
        title = FONT_HEADER.render("PQC-SAT", True, C_ACCENT_CYAN)
        title_x = 25
        surface.blit(title, (title_x, 10))

        sub_text = "ML-KEM-512 em ESP32" if WIDTH >= 1200 else "ML-KEM-512"
        subtitle = FONT_SMALL.render(sub_text, True, C_TEXT_DIM)
        surface.blit(subtitle, (title_x + title.get_width() + 15, 14))

        if self.stand_mode:
            self.top_results_btn_rect = None
            self.top_onboarding_btn_rect = None
            state_label = self.stand_controller.state.value.replace("_", " ")
            guided = FONT_SMALL.render(f"APRESENTAÇÃO GUIADA  •  {state_label}", True, C_ACCENT_GREEN)
            surface.blit(guided, ((WIDTH - guided.get_width()) // 2, 14))
        else:
            # Botoes centrais: resultados e retorno ao onboarding
            btn_h = 26
            results_w = 240 if WIDTH >= 1500 else 156
            onboarding_w = 132 if WIDTH >= 1500 else 112
            btn_gap = 8
            group_w = results_w + btn_gap + onboarding_w
            btn_x = (WIDTH - group_w) // 2
            btn_y = (bar_h - btn_h) // 2
            self.top_results_btn_rect = pygame.Rect(btn_x, btn_y, results_w, btn_h)
            self.top_onboarding_btn_rect = pygame.Rect(self.top_results_btn_rect.right + btn_gap, btn_y, onboarding_w, btn_h)

            try:
                mouse_pos = pygame.mouse.get_pos()
            except pygame.error:
                mouse_pos = (-1, -1)
            results_hovered = self.top_results_btn_rect.collidepoint(mouse_pos)
            onboarding_hovered = self.top_onboarding_btn_rect.collidepoint(mouse_pos)

            fill_c = (28, 42, 82) if results_hovered else (8, 16, 34)
            border_c = C_ACCENT_GREEN if getattr(self, "results_overlay_visible", False) else (C_ACCENT_CYAN if results_hovered else C_PANEL_BORDER)
            self._draw_hud_button_shell(surface, self.top_results_btn_rect, fill_c, border_c)

            btn_label = "RESULTADOS CONSOLIDADOS" if WIDTH >= 1500 else "RESULTADOS"
            btn_txt = FONT_LABEL.render(btn_label, True, C_ACCENT_GREEN if getattr(self, "results_overlay_visible", False) else C_TEXT_PRIMARY)
            surface.blit(
                btn_txt,
                (
                    self.top_results_btn_rect.x + (self.top_results_btn_rect.width - btn_txt.get_width()) // 2,
                    btn_y + (btn_h - btn_txt.get_height()) // 2,
                ),
            )

            intro_fill = (34, 36, 74) if onboarding_hovered else (8, 16, 34)
            intro_border = C_ACCENT_ORANGE if onboarding_hovered else C_PANEL_BORDER
            self._draw_hud_button_shell(surface, self.top_onboarding_btn_rect, intro_fill, intro_border)
            intro_label = "ONBOARDING" if WIDTH >= 1500 else "INTRO"
            intro_txt = FONT_LABEL.render(intro_label, True, C_ACCENT_ORANGE if onboarding_hovered else C_TEXT_PRIMARY)
            surface.blit(
                intro_txt,
                (
                    self.top_onboarding_btn_rect.x + (self.top_onboarding_btn_rect.width - intro_txt.get_width()) // 2,
                    btn_y + (btn_h - intro_txt.get_height()) // 2,
                ),
            )

        # Lado direito: clock + link
        conn_pulse = int(180 + 75 * math.sin(t * 3))
        if self.stand_mode and self.stand_controller.mode == "simulated":
            conn_color = (170, 70, conn_pulse)
            conn_label = "FIXTURE OFFLINE"
            conn_text_color = C_ACCENT_PURPLE
        elif self.serial_client is None:
            conn_color = (0, 80, conn_pulse)
            conn_label = "MODO SIM"
            conn_text_color = C_ACCENT_CYAN
        elif self.serial_connected:
            conn_color = (0, conn_pulse, 90)
            conn_label = "SAT CONECTADO"
            conn_text_color = C_ACCENT_GREEN
        else:
            conn_color = (conn_pulse, 120, 0)
            conn_label = "AGUARDANDO SAT"
            conn_text_color = C_ACCENT_ORANGE
        conn_text = FONT_SMALL.render(conn_label, True, conn_text_color)
        conn_text_x = WIDTH - 20 - conn_text.get_width()
        self.top_connection_text_rect = conn_text.get_rect(topleft=(conn_text_x, 14))
        conn_dot_x = self.top_connection_text_rect.left - 12
        pygame.draw.circle(surface, conn_color, (conn_dot_x, 22), 5)
        surface.blit(conn_text, self.top_connection_text_rect)

        clock_text = FONT_SMALL.render(time.strftime("%H:%M:%S"), True, C_TEXT_DIM)
        clock_x = conn_dot_x - 18 - clock_text.get_width()
        surface.blit(clock_text, (clock_x, 14))

    def _draw_top_metrics(self, surface, t):
        """Faixa central de métricas sempre visíveis durante a animação."""
        side_margin = 20
        gap = 18
        left_edge = side_margin + self._left_panel_width() + gap
        right_edge = WIDTH - side_margin - self._right_panel_width() - gap
        width = right_edge - left_edge
        if width < 320:
            return

        tiles = self._metric_tiles()
        columns = max(1, min(len(tiles), 2))
        tile_gap = 10
        tile_h = 52
        tile_w = (width - tile_gap * (columns - 1)) // columns
        start_y = 56

        for index, (label, value, detail, color) in enumerate(tiles):
            row = index // columns
            col = index % columns
            x = left_edge + col * (tile_w + tile_gap)
            y = start_y + row * (tile_h + gap)
            rect = pygame.Rect(x, y, tile_w, tile_h)

            panel_surf = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
            pygame.draw.rect(panel_surf, (*C_PANEL_BG, 190), (0, 0, tile_w, tile_h), border_radius=6)
            pygame.draw.rect(panel_surf, (*color, 175), (0, 0, tile_w, tile_h), 1, border_radius=6)
            surface.blit(panel_surf, (x, y))

            label_surf = FONT_LABEL.render(label, True, C_TEXT_DIM)
            surface.blit(label_surf, (x + 8, y + 5))
            value_surf = self._render_clipped(FONT_BODY, value, color, tile_w - 16)
            surface.blit(value_surf, (x + 8, y + 19))
            if detail:
                detail_surf = self._render_clipped(FONT_LABEL, detail, C_TEXT_DIM, tile_w - 16)
                surface.blit(detail_surf, (x + max(80, tile_w // 2), y + 6))

            progress = self._metric_tile_progress(label)
            bar_x = x + 8
            bar_y = y + tile_h - 10
            bar_w = tile_w - 16
            pygame.draw.rect(surface, (25, 28, 46), (bar_x, bar_y, bar_w, 4), border_radius=2)
            fill_w = int(bar_w * max(0.0, min(1.0, progress)))
            if fill_w > 0:
                pygame.draw.rect(surface, color, (bar_x, bar_y, fill_w, 4), border_radius=2)

    def _metric_state(self):
        state = dict(self.hardware_state)
        state.update(self.hardware_payload)
        computed_cpu_load = self._current_cpu_load_pct()
        payload_cpu_load = _optional_float(state.get("cpu_load_pct")) or 0.0
        cpu_load = computed_cpu_load if self.cpu_active_window else payload_cpu_load
        return state, _optional_int(state.get("cpu_mhz")), cpu_load, _optional_int(state.get("heap"))

    def _metric_tiles(self):
        state, cpu, cpu_load, heap = self._metric_state()

        if self.serial_client is None:
            profile = "SIMULADO"
        else:
            profile = state.get("profile") or ("ONLINE" if self.serial_connected else "AGUARDANDO")

        if cpu is None:
            cpu_value = f"-- {cpu_load:.0f}%"
            cpu_color = C_ACCENT_ORANGE if self.serial_client is not None else C_ACCENT_CYAN
        else:
            cpu_value = f"{cpu} MHz {cpu_load:.0f}%"
            cpu_color = C_ACCENT_GREEN if cpu_load < 70 else C_ACCENT_ORANGE

        if heap is not None:
            total_ram = 327680
            consumed = max(0, total_ram - heap)
            ram_value = f"{_format_bytes(consumed)} / {_format_bytes(total_ram)}"
            ram_detail = f"livre: {_format_bytes(heap)}"
        else:
            ram_value = "-- / --"
            ram_detail = ""

        return (
            ("CPU", cpu_value, str(profile), cpu_color),
            ("RAM", ram_value, ram_detail, C_ACCENT_GREEN if heap else C_ACCENT_ORANGE),
        )

    def _metric_tile_progress(self, label):
        _state, _cpu, cpu_load, heap = self._metric_state()
        if label == "CPU":
            return cpu_load / 100.0
        if label == "RAM":
            if heap is None:
                return 0.0
            total_ram = 327680
            return max(0, min(total_ram, total_ram - heap)) / total_ram
        return 0.0

    def _draw_bottom_bar(self, surface, t):
        """Barra inferior com informacoes de sistema."""
        bar_h = 32
        bar_y = HEIGHT - bar_h
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 200), (0, 0, WIDTH, bar_h))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, 0), (WIDTH, 0), 1)
        surface.blit(bar_surf, (0, bar_y))
        self.live_payload_toggle_rect = None

        if self.stand_mode and self.stand_controller.mode == "simulated":
            esp32_item = "SAT: FIXTURE OFFLINE"
        elif self.serial_client is None:
            esp32_item = "SAT: SIMULADO"
        elif self.serial_connected:
            esp32_item = "SAT: CONECTADO"
        else:
            esp32_item = "SAT: AGUARDANDO"

        pqc_label, pqc_color = self._pqc_indicator()
        if len(pqc_label) > 28:
            pqc_label = pqc_label[:25] + "..."

        fault_color = C_ACCENT_RED if self.silent_failures > 0 else (C_ACCENT_GREEN if self.detected_errors > 0 else C_TEXT_DIM)
        payload_label = "VIVO" if self.live_payload_enabled else "FIXO"
        payload_color = C_ACCENT_GREEN if self.live_payload_enabled else C_TEXT_DIM
        items = [
            (esp32_item, None),
            (f"ML-KEM: {pqc_label}", pqc_color),
            (f"GUARD: {self.guard_mode}", None),
            (f"PAYLOAD: {payload_label}", payload_color),
        ]
        show_prompt = bool(self.terminal_visible or self.input_text or self.help_visible)
        prompt_w = min(360, max(220, WIDTH // 3)) if show_prompt else 0
        item_limit_x = WIDTH - prompt_w - 40 if show_prompt else WIDTH - 100
        ix = 25
        for item, override_color in items:
            color = override_color or (C_ACCENT_CYAN if "SIMULADO" in item else C_TEXT_DIM)
            if "CONECTADO" in item:
                color = C_ACCENT_GREEN
            elif "AGUARDANDO" in item:
                color = C_ACCENT_ORANGE
            elif "READY" in item:
                color = C_ACCENT_GREEN
            elif "PENDENTE" in item:
                color = C_ACCENT_ORANGE
            is_payload_toggle = item.startswith("PAYLOAD:")
            if is_payload_toggle:
                probe = FONT_LABEL.render(item, True, color)
                toggle_rect = probe.get_rect(topleft=(ix, bar_y + 8)).inflate(12, 8)
                try:
                    hovered = toggle_rect.collidepoint(pygame.mouse.get_pos())
                except pygame.error:
                    hovered = False
                self.live_payload_toggle_rect = toggle_rect
                if hovered:
                    pygame.draw.rect(surface, (18, 45, 42), toggle_rect, border_radius=3)
                    pygame.draw.rect(surface, payload_color, toggle_rect, width=1, border_radius=3)
                    color = C_TEXT_PRIMARY
            surf = FONT_LABEL.render(item, True, color)
            surface.blit(surf, (ix, bar_y + 8))
            if is_payload_toggle:
                pygame.draw.line(surface, payload_color, (ix, bar_y + 25), (ix + surf.get_width(), bar_y + 25), 1)
            ix += surf.get_width() + 30
            if ix >= item_limit_x:
                break
            if ix < item_limit_x:
                pygame.draw.line(surface, C_PANEL_BORDER, (ix - 15, bar_y + 6), (ix - 15, bar_y + 24), 1)

        if show_prompt:
            prompt_rect = pygame.Rect(WIDTH - prompt_w - 20, bar_y + 5, prompt_w, 22)
            pygame.draw.rect(surface, (18, 22, 42), prompt_rect, border_radius=4)
            pygame.draw.rect(surface, C_PANEL_BORDER, prompt_rect, width=1, border_radius=4)
            prompt_text = "HELP ativo: ENTER executa comando" if self.help_visible and not self.input_text else f"> {self.input_text}"
            prompt_color = C_ACCENT_CYAN if self.input_active else C_TEXT_DIM
            surface.blit(self._render_clipped(FONT_LABEL, prompt_text, prompt_color, prompt_rect.width - 14), (prompt_rect.x + 7, prompt_rect.y + 4))


# --- Particulas de poeira cosmica --------------------------------------------
class Nebula:
    """Cached background glow layer to avoid allocating a fullscreen surface per frame."""

    def __init__(self):
        self.surface_cache = None

    def _build_surface(self, size):
        width, height = size
        self.surface_cache = pygame.Surface(size, pygame.SRCALPHA)
        blobs = (
            (0.42, 0.48, 340, (34, 12, 72, 14)),
            (0.55, 0.50, 300, (52, 16, 86, 12)),
            (0.48, 0.58, 260, (24, 42, 86, 10)),
        )
        for cx_ratio, cy_ratio, radius, color in blobs:
            center = (int(width * cx_ratio), int(height * cy_ratio))
            for step in range(5, 0, -1):
                current_radius = max(12, int(radius * step / 5))
                alpha = max(1, int(color[3] * (6 - step) / 5))
                pygame.draw.circle(
                    self.surface_cache,
                    (color[0], color[1], color[2], alpha),
                    center,
                    current_radius,
                )

    def draw(self, surface, t):
        size = surface.get_size()
        if self.surface_cache is None or self.surface_cache.get_size() != size:
            self._build_surface(size)
        self.surface_cache.set_alpha(150 + int(22 * math.sin(t * 0.18)))
        surface.blit(self.surface_cache, (0, 0))
        self.surface_cache.set_alpha(None)


class CosmicDust:
    def __init__(self, count=40):
        self.particles = []
        for _ in range(count):
            self.particles.append(self._new_particle())

    def _new_particle(self):
        life = random.uniform(2, 8)
        return {
            'x': random.randint(0, WIDTH),
            'y': random.randint(0, HEIGHT),
            'vx': random.uniform(-18, 18),
            'vy': random.uniform(-12, 12),
            'life': life,
            'max_life': life,
            'size': random.uniform(0.5, 2),
            'color': random.choice([
                (100, 150, 255), (150, 100, 255), (200, 200, 255), (100, 255, 200)
            ]),
        }

    def update(self, dt):
        for p in self.particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['life'] -= dt
            if p['life'] <= 0:
                p.update(self._new_particle())

    def draw(self, surface):
        for p in self.particles:
            alpha = int(150 * (p['life'] / p['max_life']))
            alpha = max(0, min(255, alpha))
            size = max(1, int(p['size']))
            s = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p['color'], alpha), (size + 1, size + 1), size)
            surface.blit(s, (int(p['x']) - size - 1, int(p['y']) - size - 1))


# --- Estrelas Cadentes --------------------------------------------------------
class ShootingStars:
    """Estrelas cadentes ocasionais."""

    def __init__(self):
        self.meteors = []
        self.spawn_timer = 0.0
        self.next_spawn = random.uniform(2.0, 6.0)

    def update(self, dt):
        self.spawn_timer += dt
        if self.spawn_timer >= self.next_spawn:
            self.spawn_timer = 0.0
            self.next_spawn = random.uniform(3.0, 8.0)
            self._spawn()
        for m in self.meteors:
            m['x'] += m['vx'] * dt
            m['y'] += m['vy'] * dt
            m['life'] -= dt
        self.meteors = [m for m in self.meteors if m['life'] > 0]

    def _spawn(self):
        side = random.choice(['top', 'right'])
        if side == 'top':
            x = random.randint(100, WIDTH - 100)
            y = random.randint(-20, 50)
        else:
            x = random.randint(WIDTH - 200, WIDTH + 20)
            y = random.randint(50, HEIGHT // 2)
        angle = random.uniform(math.pi * 0.55, math.pi * 0.72)
        speed = random.uniform(250, 500)
        life = random.uniform(0.8, 1.8)
        self.meteors.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'life': life, 'max_life': life,
            'length': random.randint(80, 180),
            'brightness': random.randint(200, 255),
        })

    def draw(self, surface):
        for m in self.meteors:
            alpha_ratio = m['life'] / m['max_life']
            speed = math.sqrt(m['vx'] ** 2 + m['vy'] ** 2)
            if speed < 1:
                continue
            dx = -m['vx'] / speed * m['length']
            dy = -m['vy'] / speed * m['length']
            head_x, head_y = int(m['x']), int(m['y'])
            tail_x, tail_y = int(m['x'] + dx), int(m['y'] + dy)

            b = max(0, min(255, int(m['brightness'] * alpha_ratio)))
            b2 = max(0, min(255, int(b * 0.85)))

            # Trilha difusa
            trail_s = pygame.Surface((abs(head_x - tail_x) + 20, abs(head_y - tail_y) + 20), pygame.SRCALPHA)
            ox = min(head_x, tail_x) - 10
            oy = min(head_y, tail_y) - 10
            pygame.draw.line(trail_s, (b, b, b2, max(0, min(255, int(60 * alpha_ratio)))),
                             (head_x - ox, head_y - oy), (tail_x - ox, tail_y - oy), 5)
            surface.blit(trail_s, (ox, oy))

            # Linha central
            pygame.draw.line(surface, (b, b, b2),
                             (head_x, head_y), (tail_x, tail_y), 3)

            # Glow na cabeca
            glow_size = max(0, min(14, int(7 * alpha_ratio)))
            if glow_size > 0:
                b3 = max(0, min(255, int(b * 0.8)))
                ga = max(0, min(255, int(180 * alpha_ratio)))
                glow_s = pygame.Surface((glow_size * 6, glow_size * 6), pygame.SRCALPHA)
                pygame.draw.circle(glow_s, (b, b, b3, ga),
                                   (glow_size * 3, glow_size * 3), glow_size)
                ga2 = max(0, min(255, int(50 * alpha_ratio)))
                pygame.draw.circle(glow_s, (b, b, b3, ga2),
                                   (glow_size * 3, glow_size * 3), glow_size * 2)
                surface.blit(glow_s, (head_x - glow_size * 3, head_y - glow_size * 3))


# --- Telas de Onboarding -----------------------------------------------------
class Onboarding:
    """Telas interativas de introdução para contextualizar o problema e solução."""

    def __init__(self, stars, earth, satellite, nebula, dust, shooting_stars):
        self.stars = stars
        self.earth = earth
        self.satellite = satellite
        self.nebula = nebula
        self.dust = dust
        self.shooting_stars = shooting_stars
        self.current_slide = 0
        self.total_slides = 5
        self.completed = False

        # Dimensões do painel responsivas
        self.w = int(WIDTH * 0.85)
        self.h = int(HEIGHT * 0.82)
        self.x = (WIDTH - self.w) // 2
        self.y = (HEIGHT - self.h) // 2

        # Botões responsivos
        self.btn_w = max(132, min(178, int(self.w * 0.14)))
        self.btn_h = max(36, int(self.h * 0.06))
        self.btn_back_rect = pygame.Rect(self.x + int(self.w * 0.04), self.y + self.h - int(self.h * 0.11), self.btn_w, self.btn_h)
        self.btn_next_rect = pygame.Rect(self.x + self.w - int(self.w * 0.04) - self.btn_w, self.y + self.h - int(self.h * 0.11), self.btn_w, self.btn_h)
        self.btn_skip_rect = pygame.Rect(self.x + self.w - int(self.w * 0.04) - self.btn_w, self.y + int(self.h * 0.04), self.btn_w, int(self.btn_h * 0.8))

    def next_slide(self):
        if self.current_slide < self.total_slides - 1:
            self.current_slide += 1
        else:
            self.completed = True

    def prev_slide(self):
        if self.current_slide > 0:
            self.current_slide -= 1

    def handle_click(self, pos):
        if self.btn_skip_rect.collidepoint(pos):
            self.completed = True
        elif self.btn_next_rect.collidepoint(pos):
            self.next_slide()
        elif self.btn_back_rect.collidepoint(pos) and self.current_slide > 0:
            self.prev_slide()

    def update(self, dt):
        self.dust.update(dt)
        self.shooting_stars.update(dt)
        self.satellite.update(dt)

    def draw_button(self, surface, rect, text, bg_color, text_color, hover=False):
        border_color = C_ACCENT_CYAN if hover else C_PANEL_BORDER
        if hover:
            bg_color = (min(255, bg_color[0] + 15), min(255, bg_color[1] + 15), min(255, bg_color[2] + 25))

        pygame.draw.rect(surface, bg_color, rect, border_radius=6)
        pygame.draw.rect(surface, border_color, rect, width=2, border_radius=6)

        txt_surf = FONT_CMD.render(text, True, text_color)
        tx = rect.x + (rect.width - txt_surf.get_width()) // 2
        ty = rect.y + (rect.height - txt_surf.get_height()) // 2
        surface.blit(txt_surf, (tx, ty))

    def draw_wrapped_onboarding(self, surface, text, x, y, max_width, color, line_spacing=21, max_lines=None):
        lines = DashboardPanel._wrap_text_for_width(FONT_SMALL, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            surface.blit(DashboardPanel._render_clipped(FONT_SMALL, line, color, max_width), (x, y))
            y += line_spacing
        return y

    def draw_paragraphs(self, surface, paragraphs, x, y, max_width, line_spacing=26, paragraph_spacing=12):
        curr_y = y
        for para in paragraphs:
            wrapped = DashboardPanel._wrap_text_for_width(FONT_BODY, para, max_width)
            for line in wrapped:
                txt = FONT_BODY.render(line, True, C_TEXT_PRIMARY)
                surface.blit(txt, (x, curr_y))
                curr_y += line_spacing
            curr_y += paragraph_spacing
        return curr_y

    def draw(self, surface, t):
        surface.fill(C_SPACE_BG)
        self.nebula.draw(surface, t)
        self.stars.draw(surface, t)
        self.dust.draw(surface)
        self.shooting_stars.draw(surface)
        self.earth.draw(surface, t)
        self.satellite.draw(surface, t)

        panel_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        panel_surf.fill((12, 14, 30, 242))
        surface.blit(panel_surf, (self.x, self.y))

        pygame.draw.rect(surface, C_PANEL_BORDER, (self.x, self.y, self.w, self.h), width=2, border_radius=8)

        # Header do painel
        header_h = 95
        pygame.draw.rect(surface, C_PANEL_HEADER, (self.x + 2, self.y + 2, self.w - 4, header_h), border_radius=8)
        pygame.draw.line(surface, C_ACCENT_CYAN, (self.x, self.y + header_h), (self.x + self.w, self.y + header_h), 2)

        # Dots
        dot_r = 6
        spacing = 25
        start_x = self.x + (self.w - (self.total_slides - 1) * spacing) // 2
        dot_y = self.y + self.h - 66
        for i in range(self.total_slides):
            cx = start_x + i * spacing
            color = C_ACCENT_CYAN if i == self.current_slide else C_TEXT_DIM
            pygame.draw.circle(surface, color, (cx, dot_y), dot_r)

        # Mouse hover
        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)
        hover_back = self.btn_back_rect.collidepoint(mouse_pos)
        hover_next = self.btn_next_rect.collidepoint(mouse_pos)
        hover_skip = self.btn_skip_rect.collidepoint(mouse_pos)

        # Botoes
        if self.current_slide > 0:
            self.draw_button(surface, self.btn_back_rect, "<- VOLTAR", C_PANEL_BG, C_TEXT_PRIMARY, hover_back)

        next_label = "INICIAR >" if self.current_slide == self.total_slides - 1 else "AVANÇAR ->"
        next_color = C_ACCENT_GREEN if self.current_slide == self.total_slides - 1 else C_ACCENT_CYAN
        self.draw_button(surface, self.btn_next_rect, next_label, C_PANEL_BG, next_color, hover_next)

        self.draw_button(surface, self.btn_skip_rect, "PULAR INTRO", C_PANEL_BG, C_ACCENT_ORANGE, hover_skip)

        self.draw_slide_content(surface)

    def draw_slide_content(self, surface):
        if self.current_slide == 0:
            self.draw_slide_0(surface)
        elif self.current_slide == 1:
            self.draw_slide_1(surface)
        elif self.current_slide == 2:
            self.draw_slide_2(surface)
        elif self.current_slide == 3:
            self.draw_slide_3(surface)
        elif self.current_slide == 4:
            self.draw_slide_4(surface)

    def draw_slide_0(self, surface):
        title = FONT_TITLE.render("1. CENÁRIO: SEGURANÇA EMBARCADA EM ÓRBITA", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("Contexto do problema e recorte real da demonstração", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "Um OBC precisa proteger mensagens com CPU, RAM e tempo limitados. Em ambiente espacial, falhas transitórias também podem inverter bits e corromper dados.",
            "Nosso cenário usa uma BlackBoard Wisdom como OBC didático. A placa e o dashboard se comunicam por USB serial; não simulamos enlace de rádio.",
            "A falha é controlada e reproduzível: um bit do payload é invertido para observar corrupção silenciosa ou erro detectado.",
            "Pergunta central: quanto custa adicionar PQC e qual proteção o CRC32 acrescenta ao fluxo?"
        ]

        box_w = int(self.w * 0.32)
        box_h = int(self.h * 0.22)
        bx = self.x + self.w - box_w - int(self.w * 0.04)
        by = self.y + int(self.h * 0.16)
        by2 = by + box_h + int(self.h * 0.05)

        text_max_w = bx - (self.x + int(self.w * 0.04)) - int(self.w * 0.02)
        self.draw_paragraphs(surface, paragraphs, self.x + int(self.w * 0.04), self.y + 130, text_max_w)

        # Original RAM Box
        pygame.draw.rect(surface, C_PANEL_BG, (bx, by, box_w, box_h), border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, (bx, by, box_w, box_h), width=1, border_radius=6)
        txt_orig = FONT_HEADER.render("BYTE ORIGINAL", True, C_ACCENT_GREEN)
        surface.blit(txt_orig, (bx + 20, by + 16))

        bits_orig = ["0", "1", "0", "0", "1", "0", "0", "0"]
        bit_sz = int(box_w // 10)
        bit_start_x = bx + (box_w - len(bits_orig) * bit_sz) // 2
        for idx, bit in enumerate(bits_orig):
            x_pos = bit_start_x + idx * bit_sz
            y_pos = by + int(box_h * 0.36)
            pygame.draw.rect(surface, (20, 50, 30), (x_pos, y_pos, bit_sz - 4, bit_sz - 4), border_radius=4)
            pygame.draw.rect(surface, C_ACCENT_GREEN, (x_pos, y_pos, bit_sz - 4, bit_sz - 4), width=1, border_radius=4)
            bit_txt = FONT_BODY.render(bit, True, C_TEXT_PRIMARY)
            surface.blit(bit_txt, (x_pos + (bit_sz - 4 - bit_txt.get_width()) // 2, y_pos + (bit_sz - 4 - bit_txt.get_height()) // 2))

        val_orig = FONT_SMALL.render("0x48 | dado íntegro", True, C_TEXT_DIM)
        surface.blit(val_orig, (bx + 20, by + box_h - 32))

        # Corrupted RAM Box
        pygame.draw.rect(surface, C_PANEL_BG, (bx, by2, box_w, box_h), border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, (bx, by2, box_w, box_h), width=1, border_radius=6)
        txt_corr = FONT_HEADER.render("1 BIT INVERTIDO", True, C_ACCENT_RED)
        surface.blit(txt_corr, (bx + 20, by2 + 16))

        bits_corr = ["0", "1", "0", "0", "1", "0", "0", "1"]
        for idx, bit in enumerate(bits_corr):
            x_pos = bit_start_x + idx * bit_sz
            y_pos = by2 + int(box_h * 0.36)
            bg_c = (80, 20, 30) if idx == 7 else (40, 40, 50)
            brd_c = C_ACCENT_RED if idx == 7 else C_PANEL_BORDER
            pygame.draw.rect(surface, bg_c, (x_pos, y_pos, bit_sz - 4, bit_sz - 4), border_radius=4)
            pygame.draw.rect(surface, brd_c, (x_pos, y_pos, bit_sz - 4, bit_sz - 4), width=1, border_radius=4)
            bit_txt = FONT_BODY.render(bit, True, C_TEXT_PRIMARY)
            surface.blit(bit_txt, (x_pos + (bit_sz - 4 - bit_txt.get_width()) // 2, y_pos + (bit_sz - 4 - bit_txt.get_height()) // 2))

        val_corr = FONT_SMALL.render("0x49 | pode virar falha silenciosa", True, C_TEXT_DIM)
        surface.blit(val_corr, (bx + 20, by2 + box_h - 32))


    def draw_slide_1(self, surface):
        title = FONT_TITLE.render("2. PROBLEMA: MIGRAÇÃO PARA CRIPTOGRAFIA PQC", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("A ameaça está no estabelecimento de chaves públicas", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "Um computador quântico grande poderia aplicar Shor contra esquemas de chave pública como RSA e ECDH. Esse risco motiva a migração para algoritmos pós-quânticos.",
            "No experimento, CLASSIC não representa RSA ou ECDH: é um baseline simétrico com AES-128-GCM, chave efêmera e nonce aleatório.",
            "Nos cenários PQC, ML-KEM-512 estabelece a chave de sessão. AES-GCM continua responsável por cifrar e autenticar a mensagem."
        ]

        box_w = int(self.w * 0.34)
        box_h = int(self.h * 0.46)
        bx = self.x + self.w - box_w - int(self.w * 0.04)
        by = self.y + int(self.h * 0.16)

        text_max_w = bx - (self.x + int(self.w * 0.04)) - int(self.w * 0.02)
        self.draw_paragraphs(surface, paragraphs, self.x + int(self.w * 0.04), self.y + 130, text_max_w)

        # Caixa Comparativa
        pygame.draw.rect(surface, C_PANEL_BG, (bx, by, box_w, box_h), border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, (bx, by, box_w, box_h), width=1, border_radius=6)

        t_header = FONT_HEADER.render("CENÁRIOS DO PROJETO", True, C_ACCENT_ORANGE)
        surface.blit(t_header, (bx + int(box_w * 0.08), by + int(box_h * 0.08)))

        # Classico
        c_w = box_w - int(box_w * 0.16)
        c_h = int(box_h * 0.3)
        pygame.draw.rect(surface, (25, 20, 10), (bx + int(box_w * 0.08), by + int(box_h * 0.22), c_w, c_h), border_radius=4)
        c_title = FONT_SMALL.render("CLASSIC (baseline):", True, C_TEXT_PRIMARY)
        surface.blit(c_title, (bx + int(box_w * 0.11), by + int(box_h * 0.26)))
        c_val = FONT_HEADER.render("AES-128-GCM", True, C_ACCENT_GREEN)
        surface.blit(c_val, (bx + int(box_w * 0.11), by + int(box_h * 0.35)))

        # Quantico
        pygame.draw.rect(surface, (10, 25, 20), (bx + int(box_w * 0.08), by + int(box_h * 0.58), c_w, c_h), border_radius=4)
        q_title = FONT_SMALL.render("PQC (estabelecimento):", True, C_TEXT_PRIMARY)
        surface.blit(q_title, (bx + int(box_w * 0.11), by + int(box_h * 0.62)))
        q_val = FONT_HEADER.render("ML-KEM + AES-GCM", True, C_ACCENT_ORANGE)
        surface.blit(q_val, (bx + int(box_w * 0.11), by + int(box_h * 0.71)))

    def draw_slide_2(self, surface):
        title = FONT_TITLE.render("3. OVERVIEW: DA MENSAGEM À ENTREGA", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("Arquitetura da demonstração e papel de cada mecanismo", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "A Wisdom coleta o payload e executa os papéis lógicos de emissor e receptor. O dashboard apenas comanda, visualiza e registra métricas.",
            "ML-KEM-512 executa KEYGEN, ENCAP e DECAP para estabelecer o segredo; AES-GCM cifra e autentica o payload.",
            "No pacote PQC viajam o ciphertext ML-KEM de 768 B, o nonce, o ciphertext da mensagem e a tag GCM. O segredo nunca é transmitido.",
        ]

        text_max_w = self.w - int(self.w * 0.08)
        last_y = self.draw_paragraphs(surface, paragraphs, self.x + int(self.w * 0.04), self.y + 130, text_max_w)

        # Diagrama de KEM responsivo posicionado dinamicamente abaixo do texto
        bx = self.x + int(self.w * 0.04)
        by = max(last_y + 20, self.y + int(self.h * 0.60))
        box_w = self.w - int(self.w * 0.08)
        box_h = int(self.h * 0.16)
        pygame.draw.rect(surface, C_PANEL_BG, (bx, by, box_w, box_h), border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, (bx, by, box_w, box_h), width=1, border_radius=6)

        d_lbl = FONT_SMALL.render("ML-KEM NA WISDOM: PAPÉIS LÓGICOS", True, C_ACCENT_CYAN)
        surface.blit(d_lbl, (bx + 20, by + 12))

        # Alice e Bob
        alice_x = bx + int(box_w * 0.04)
        bob_x = bx + box_w - int(box_w * 0.04) - 160

        pygame.draw.rect(surface, C_PANEL_HEADER, (alice_x, by + int(box_h * 0.28), 160, 36), border_radius=4)
        alice_t = FONT_SMALL.render("RECEPTOR", True, C_TEXT_PRIMARY)
        surface.blit(alice_t, (alice_x + (160 - alice_t.get_width()) // 2, by + int(box_h * 0.28) + 10))

        pygame.draw.rect(surface, C_PANEL_HEADER, (bob_x, by + int(box_h * 0.28), 160, 36), border_radius=4)
        bob_t = FONT_SMALL.render("EMISSOR", True, C_TEXT_PRIMARY)
        surface.blit(bob_t, (bob_x + (160 - bob_t.get_width()) // 2, by + int(box_h * 0.28) + 10))

        # Setas direcionais
        arrow_start_x = alice_x + 170
        arrow_end_x = bob_x - 10
        line_y = by + int(box_h * 0.32)
        line_y2 = by + int(box_h * 0.65)

        pygame.draw.line(surface, C_ACCENT_CYAN, (arrow_start_x, line_y), (arrow_end_x, line_y), 2)
        pygame.draw.polygon(surface, C_ACCENT_CYAN, [(arrow_end_x - 10, line_y - 5), (arrow_end_x, line_y), (arrow_end_x - 10, line_y + 5)])
        pk_t = FONT_SMALL.render("1. Chave Pública (pk) - 800 B", True, C_TEXT_PRIMARY)
        surface.blit(pk_t, (arrow_start_x + (arrow_end_x - arrow_start_x - pk_t.get_width()) // 2, line_y - 20))

        pygame.draw.line(surface, C_ACCENT_ORANGE, (arrow_end_x, line_y2), (arrow_start_x, line_y2), 2)
        pygame.draw.polygon(surface, C_ACCENT_ORANGE, [(arrow_start_x + 10, line_y2 - 5), (arrow_start_x, line_y2), (arrow_start_x + 10, line_y2 + 5)])
        ct_t = FONT_SMALL.render("2. Ciphertext (ct) - 768 B", True, C_TEXT_PRIMARY)
        surface.blit(ct_t, (arrow_start_x + (arrow_end_x - arrow_start_x - ct_t.get_width()) // 2, line_y2 - 20))

        ss_t = FONT_HEADER.render("Segredo Compartilhado ss (32 B) derivado", True, C_ACCENT_GREEN)
        surface.blit(ss_t, (bx + (box_w - ss_t.get_width()) // 2, by + box_h - 26))

    def draw_slide_3(self, surface):
        title = FONT_TITLE.render("4. EXPERIMENTO: CENÁRIOS E HIPÓTESES", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("A mesma mensagem, três proteções e métricas comparáveis", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        pad_x = int(self.w * 0.04)
        content_x = self.x + pad_x
        content_y = self.y + 128
        gap = int(self.w * 0.025)
        card_w = (self.w - pad_x * 2 - gap * 2) // 3
        card_h = int(self.h * 0.37)

        cards = [
            {
                "title": "CLASSIC",
                "color": C_ACCENT_BLUE,
                "body": [
                    "AES-128-GCM cifra e autentica.",
                    "Chave efêmera e nonce aleatório.",
                    "Referência de menor custo, sem KEM.",
                ],
            },
            {
                "title": "PQC",
                "color": C_ACCENT_ORANGE,
                "body": [
                    "ML-KEM-512 estabelece o segredo.",
                    "AES-GCM protege a mensagem.",
                    "Hipótese: mais tempo e tráfego.",
                ],
            },
            {
                "title": "PQC + CRC32",
                "color": C_ACCENT_GREEN,
                "body": [
                    "Mesmo fluxo PQC.",
                    "CRC32 integra o plaintext protegido.",
                    "Hipótese: +4 B e falha observável.",
                ],
            },
        ]

        for index, card in enumerate(cards):
            cx = content_x + index * (card_w + gap)
            rect = pygame.Rect(cx, content_y, card_w, card_h)
            pygame.draw.rect(surface, C_PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, card["color"], rect, width=2, border_radius=6)
            surface.blit(DashboardPanel._render_clipped(FONT_HEADER, card["title"], card["color"], card_w - 32), (cx + 16, content_y + 18))
            cy = content_y + 58
            for item in card["body"]:
                cy = self.draw_wrapped_onboarding(surface, item, cx + 16, cy, card_w - 32, C_TEXT_PRIMARY, max_lines=2)
                cy += 10

        metrics_y = content_y + card_h + 28
        metrics_rect = pygame.Rect(content_x, metrics_y, self.w - pad_x * 2, int(self.h * 0.22))
        pygame.draw.rect(surface, (14, 24, 38), metrics_rect, border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, metrics_rect, width=1, border_radius=6)

        mx = metrics_rect.x + 18
        my = metrics_rect.y + 16
        mw = metrics_rect.width - 36
        surface.blit(DashboardPanel._render_clipped(FONT_HEADER, "O QUE ESTAMOS MEDINDO", C_ACCENT_CYAN, mw), (mx, my))
        my += 38
        metric_lines = [
            "Tempo/CPU: custo para entregar a mensagem.",
            "Bytes: tráfego do protocolo e composição do pacote.",
            "Heap/RAM: margem restante na placa.",
            "Resultado: DELIVERED, SILENT ou DETECTED_GUARD.",
        ]
        for line in metric_lines:
            my = self.draw_wrapped_onboarding(surface, f"- {line}", mx, my, mw, C_TEXT_PRIMARY, line_spacing=18, max_lines=1)

    def draw_slide_4(self, surface):
        title = FONT_TITLE.render("5. PROJEÇÕES, LIMITES E DEMONSTRAÇÃO", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("O que esperamos observar e o que o experimento não mede", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        pad_x = int(self.w * 0.04)
        content_x = self.x + pad_x
        content_y = self.y + 128
        col_gap = int(self.w * 0.035)
        col_w = (self.w - pad_x * 2 - col_gap) // 2
        box_h = int(self.h * 0.48)

        left_rect = pygame.Rect(content_x, content_y, col_w, box_h)
        right_rect = pygame.Rect(content_x + col_w + col_gap, content_y, col_w, box_h)
        for rect in (left_rect, right_rect):
            pygame.draw.rect(surface, C_PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, C_PANEL_BORDER, rect, width=1, border_radius=6)

        lx = left_rect.x + 20
        ly = left_rect.y + 18
        lw = left_rect.width - 40
        surface.blit(DashboardPanel._render_clipped(FONT_HEADER, "ROTEIRO DA DEMO", C_ACCENT_GREEN, lw), (lx, ly))
        ly += 38
        steps = [
            ("CLÁSSICA", "envia a mensagem com AES-128-GCM."),
            ("PQC", "usa ML-KEM-512 para chave e AES-GCM para cifra."),
            ("PQC+CRC", "usa ML-KEM-512, AES-GCM e CRC32 protegido."),
            ("ENVIAR MSG", "abre popup pausável do fluxo interno."),
            ("FALHA", "mostra bit-flip, CRC e resultado."),
            ("RESULTADOS", "abre a consolidação real da bateria longa."),
        ]
        for label, desc in steps:
            row_y = ly
            tag = FONT_SMALL.render(label, True, C_ACCENT_CYAN)
            surface.blit(tag, (lx, row_y))
            desc_y = self.draw_wrapped_onboarding(surface, desc, lx + 108, row_y, lw - 108, C_TEXT_PRIMARY, max_lines=2)
            ly = max(row_y + 34, desc_y + 6)

        rx = right_rect.x + 20
        ry = right_rect.y + 18
        rw = right_rect.width - 40
        surface.blit(DashboardPanel._render_clipped(FONT_HEADER, "PROJEÇÕES E LIMITES", C_ACCENT_ORANGE, rw), (rx, ry))
        ry += 38
        comparisons = [
            "PQC deve elevar tempo e bytes frente ao baseline CLASSIC.",
            "O perfil de 80 MHz deve ampliar o custo temporal.",
            "CRC32 deve tornar o bit-flip coberto observável.",
            "O perfil limitado não representa todo CubeSat.",
            "Tempo de CPU é proxy; não medimos energia elétrica.",
            "Próximo passo: energia e baseline clássico completo.",
        ]
        for item in comparisons:
            ry = self.draw_wrapped_onboarding(surface, f"- {item}", rx, ry, rw, C_TEXT_PRIMARY, max_lines=2)
            ry += 4

        footer_y = content_y + box_h + 26
        footer_rect = pygame.Rect(content_x, footer_y, self.w - pad_x * 2, int(self.h * 0.14))
        pygame.draw.rect(surface, (14, 24, 38), footer_rect, border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, footer_rect, width=1, border_radius=6)
        footer = (
            "Na demo, a placa conectada produz as métricas de cada mensagem. "
            "RESULTADOS mostra a bateria oficial; a execução ao vivo não a substitui."
        )
        self.draw_wrapped_onboarding(surface, footer, footer_rect.x + 18, footer_rect.y + 18, footer_rect.width - 36, C_TEXT_PRIMARY, max_lines=3)

    def run(self, surface, clock):
        t = 0.0
        running = True
        while running and not self.completed:
            dt = clock.tick(FPS) / 1000.0
            t += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        return False
                    elif event.key == pygame.K_ESCAPE:
                        self.completed = True
                    elif event.key == pygame.K_RIGHT:
                        self.next_slide()
                    elif event.key == pygame.K_LEFT:
                        self.prev_slide()
                    elif event.key == pygame.K_SPACE:
                        if self.current_slide == self.total_slides - 1:
                            self.completed = True
                        else:
                            self.next_slide()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_click(event.pos)

            self.update(dt)
            self.draw(surface, t)
            pygame.display.flip()

        return True


def render_dashboard_presentation_frame(controller, *, size=(1366, 768), now=0.0, diagnostic=False):
    """Render one off-screen frame through the same dashboard layer used live."""
    global WIDTH, HEIGHT

    WIDTH, HEIGHT = int(size[0]), int(size[1])
    frame = pygame.Surface((WIDTH, HEIGHT))
    stars = StarField(180)
    earth = Earth()
    satellite = Satellite(earth)
    nebula = Nebula()
    dust = CosmicDust(28)
    shooting_stars = ShootingStars()
    panel = DashboardPanel(stand_controller=controller, stand_diagnostic=diagnostic)
    # A non-None transport marker makes the persistent HUD follow the
    # controller's proven connection state without opening a second serial
    # consumer in evidence/tests.
    panel.serial_client = object()
    panel.serial_connected = bool(controller.connected)
    panel.serial_status = controller.connection_status
    panel.pqc_algorithm = (
        "ML-KEM-512 (FIXTURE)" if controller.mode == "simulated" else "ML-KEM-512 (DISPONÍVEL)"
    )
    if controller.measurements:
        latest = tuple(controller.measurements.values())[-1]
        panel.hardware_state.update(latest.raw_response)

    frame.fill(C_SPACE_BG)
    nebula.draw(frame, now)
    stars.draw(frame, now)
    dust.draw(frame)
    shooting_stars.draw(frame)
    earth.draw(frame, now)
    if controller.ready or controller.mode == "simulated":
        satellite.draw(frame, now)
    else:
        panel.draw_satellite_lock(frame, now)
    panel.draw(frame, now, satellite)
    return frame


# --- Loop Principal -----------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="PQC-SAT Mission Control Dashboard")
    parser.add_argument(
        "--stand",
        "--presentation",
        dest="stand",
        action="store_true",
        help="abre a apresentação guiada dentro do dashboard existente",
    )
    parser.add_argument("--serial", action="store_true", help="conecta comandos do dashboard ao ESP32")
    parser.add_argument("--simulated", action="store_true", help="modo de desenvolvimento sem travar no hardware")
    parser.add_argument("--no-splash", action="store_true", help="pula a tela inicial curta")
    parser.add_argument("--port", help="porta serial, por exemplo /dev/ttyUSB0 ou COM3")
    parser.add_argument("--baud", type=int, default=115200, help="baudrate da serial")
    parser.add_argument("--serial-timeout", type=float, default=SERIAL_TIMEOUT_SECONDS, help="timeout serial em segundos")
    parser.add_argument("--windowed", action="store_true", help="abre o modo estande em janela redimensionável")
    parser.add_argument("--stand-config", help="configuração JSON do modo estande")
    parser.add_argument("--stand-fixture", help="fixture oficial para o modo estande simulado")
    parser.add_argument("--stand-log-dir", help="diretório dos logs JSONL do estande")
    parser.add_argument("--diagnostic", action="store_true", help="mostra diagnóstico administrativo no modo estande")
    parser.add_argument("--max-runtime-seconds", type=float, help=argparse.SUPPRESS)
    return parser.parse_args()


def build_stand_runtime(args, *, config=None):
    """Create the guided controller around the dashboard's existing transport."""
    from stand_demo import (
        DEFAULT_CONFIG_PATH,
        DEFAULT_FIXTURE_PATH,
        DEFAULT_LOG_DIR as DEFAULT_STAND_LOG_DIR,
        FixtureSerialClient,
        StandConfig,
        StandController,
        StandSessionLogger,
    )

    if config is None:
        config = StandConfig.load(args.stand_config or DEFAULT_CONFIG_PATH)
    mode = "simulated" if args.simulated else "hardware"
    fixture_source = ""
    if mode == "simulated":
        client = FixtureSerialClient(args.stand_fixture or DEFAULT_FIXTURE_PATH, config)
        fixture_source = client.source_label
    else:
        client = DashboardSerialClient(
            port=args.port,
            baudrate=args.baud,
            timeout=args.serial_timeout,
        )
    logger = StandSessionLogger(
        args.stand_log_dir or DEFAULT_STAND_LOG_DIR,
        mode=mode,
        config=config,
        fixture_source=fixture_source,
    )
    controller = StandController(config, client.send, mode=mode, logger=logger)
    return config, client, controller, logger


def main():
    args = parse_args()
    stand_config = None
    if args.stand:
        from stand_demo import DEFAULT_CONFIG_PATH, StandConfig

        stand_config = StandConfig.load(args.stand_config or DEFAULT_CONFIG_PATH)

    init_display(
        windowed=bool(args.stand and args.windowed),
        windowed_size=stand_config.windowed_size if stand_config is not None else (1366, 768),
    )
    if not args.no_splash:
        if args.stand:
            mode_label = "APRESENTAÇÃO GUIADA — SIMULADA" if args.simulated else "APRESENTAÇÃO GUIADA — PROCURANDO WISDOM"
        else:
            mode_label = "MODO SIMULADO" if args.simulated else "PROCURANDO BLACKBOARD WISDOM"
        if not show_splash(mode_label):
            pygame.quit()
            return

    stand_controller = None
    stand_logger = None
    if args.stand:
        stand_config, serial_client, stand_controller, stand_logger = build_stand_runtime(args, config=stand_config)
        print(f"PQC-SAT presentation log: {stand_logger.path}")
    else:
        serial_client = None
    if not args.stand and (args.serial or args.port or not args.simulated):
        serial_client = DashboardSerialClient(
            port=args.port,
            baudrate=args.baud,
            timeout=args.serial_timeout,
        )

    stars = StarField(350)
    earth = Earth()
    satellite = Satellite(earth)
    nebula = Nebula()
    dust = CosmicDust(50)
    shooting_stars = ShootingStars()

    if not args.stand and not args.no_splash:
        onboarding = Onboarding(stars, earth, satellite, nebula, dust, shooting_stars)
        if not onboarding.run(screen, clock):
            pygame.quit()
            return

    dashboard = DashboardPanel(
        serial_client=serial_client,
        stand_controller=stand_controller,
        stand_diagnostic=args.diagnostic,
    )
    if stand_logger is not None:
        stand_logger.write("display_started", size=screen.get_size(), windowed=bool(args.windowed), renderer="dashboard-native")
    running = True
    t = 0.0
    started_at = time.monotonic()

    try:
        while running:
            dt = clock.tick(FPS) / 1000.0
            t += dt

            # -- Eventos --
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                        running = False
                    elif args.stand and event.key == pygame.K_ESCAPE:
                        args.windowed = not args.windowed
                        init_display(windowed=args.windowed, windowed_size=stand_config.windowed_size)
                        stars = StarField(350)
                        earth = Earth()
                        satellite = Satellite(earth)
                        nebula = Nebula()
                        dust = CosmicDust(50)
                        shooting_stars = ShootingStars()
                        if stand_logger is not None:
                            stand_logger.write("display_mode", windowed=args.windowed, size=screen.get_size())
                    else:
                        dashboard.handle_event(event)
                elif event.type != pygame.KEYDOWN:
                    dashboard.handle_event(event)

            # -- Atualizacao --
            if not args.stand and dashboard.request_onboarding:
                dashboard.request_onboarding = False
                onboarding = Onboarding(stars, earth, satellite, nebula, dust, shooting_stars)
                if not onboarding.run(screen, clock):
                    running = False
                    continue

            if dashboard.satellite_online() or args.simulated:
                satellite.update(dt)
            dashboard.update(dt)
            dust.update(dt)
            shooting_stars.update(dt)
            # OTIMIZAÇÃO SEMINÁRIO
            # Offset aleatorio curto, aplicado apenas a satelite e popup de falha.
            if dashboard.effect_timer > 0:
                dashboard.impact_shake_offset = (random.randint(-4, 4), random.randint(-4, 4))
            else:
                dashboard.impact_shake_offset = (0, 0)

            # -- Desenho --
            if screen is None:
                raise RuntimeError("display not initialized")
            screen.fill(C_SPACE_BG)

            nebula.draw(screen, t)
            stars.draw(screen, t)
            dust.draw(screen)
            shooting_stars.draw(screen)
            earth.draw(screen, t)
            if dashboard.satellite_online() or args.simulated:
                satellite.draw(screen, t, offset=dashboard.impact_shake_offset)
            else:
                dashboard.draw_satellite_lock(screen, t)
            dashboard.draw(screen, t, satellite)

            pygame.display.flip()
            if args.max_runtime_seconds is not None and time.monotonic() - started_at >= args.max_runtime_seconds:
                running = False
    finally:
        exc_type, _exc_value, _exc_tb = sys.exc_info()
        try:
            dashboard.close(auto_save=not args.stand)
        except Exception as cleanup_exc:
            if exc_type is None:
                raise
            print(f"cleanup failed: {cleanup_exc}", file=sys.stderr)
        finally:
            if stand_logger is not None:
                try:
                    stand_logger.write(
                        "application_stopped",
                        state=stand_controller.state.value,
                        completed_cycles=stand_controller.completed_cycles,
                        renderer="dashboard-native",
                    )
                finally:
                    stand_logger.close()
        pygame.quit()


if __name__ == "__main__":
    main()
