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
import sys
import threading
import time
import zlib

import pygame

from tools.serial_bridge import SerialBridge, SerialBridgeError, list_serial_ports
from tools.serial_commands import (
    DASHBOARD_COMMAND_NAMES,
    FIRMWARE_COMMAND_NAMES,
    command_help_lines,
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
DEFAULT_PAYLOAD = b"PQC-SAT|TEMP=24.5|STATUS=OK"
RUN_SCHEMA_VERSION = "pqc-sat-run-v2"
DEFAULT_LOG_DIR = Path("logs")
SPLASH_SECONDS = 1.6
TIMELINE_WINDOW = 16
SERIAL_STARTUP_COMMANDS = ("OLED STANDBY",)
SERIAL_RECONNECT_DELAY = 1.5
SERIAL_TIMEOUT_SECONDS = 5.0
AUTO_TELEMETRY_ENABLED = False
TELEMETRY_POLL_SECONDS = 30.0
CPU_LOAD_WINDOW_SECONDS = 5.0
DEMO_DEFAULT_ATTEMPTS = 5
DEMO_FAULT_INTERVAL_SECONDS = 0.55
DEMO_SNAPSHOT_SECONDS = 1.5
DEMO_RESULTS_SECONDS = 8.0
MISSION_FLOW_ANIMATION_SECONDS = 12.0
FAULT_FLOW_ANIMATION_SECONDS = 9.5
HELP_HINT_LINES = (
    "Botões: comandos visuais da demo.",
    "Terminal: HELP mostra comandos avançados.",
    "Ex.: MISSION PQC, PQC_KAT, HELP LED",
)
COMMAND_BUTTONS = (
    ("ENVIAR MSG", "SEND_MESSAGE"),
    ("CLÁSSICA", "SET_PRESET_CLASSIC"),
    ("PQC", "SET_PRESET_PQC"),
    ("PQC+CRC", "SET_PRESET_PQC_CRC32"),
    ("FALHA", "INJECT_FAULT"),
)
MISSION_PRESET_COMMANDS = {
    "SET_PRESET_CLASSIC": "CLASSIC",
    "SET_PRESET_PQC": "PQC",
    "SET_PRESET_PQC_CRC32": "PQC_CRC32",
}
MISSION_OVERLAY_SCENARIOS = ("CLASSIC", "PQC", "PQC_CRC32")
CONSOLIDATED_ACCEPTANCE_LOG = "logs/20260625T005330Z_final_metrics_dev-ttyusb0.json"
CONSOLIDATED_ACCEPTANCE_LABEL = "20260625T005330Z"
CONSOLIDATED_SUMMARY = {
    "elapsed_s": 1681.24,
    "records": 3074,
    "failed": 0,
    "mission_runs": 1800,
    "pqc_bench_runs": 10,
    "demo_none_silent": "600/600",
    "demo_crc_detected": "600/600",
    "crc_acceptance": "600/600",
}
CONSOLIDATED_MISSION_BASELINE = {
    "CLASSIC": {
        "label": "CLASSIC (HMAC)",
        "crypto": "HMAC-SHA256",
        "checksum": "NONE",
        "elapsed_us": 511,
        "bytes_total": 73,
        "bytes_payload": 41,
        "bytes_crypto": 32,
        "bytes_checksum": 0,
        "keygen_us": 0,
        "encap_us": 0,
        "decap_us": 0,
        "tag_us": 335,
        "verify_us": 168,
        "crc_us": 0,
        "heap": 201412,
        "result": "DELIVERED",
    },
    "PQC": {
        "label": "PQC (ML-KEM)",
        "crypto": "ML-KEM-512",
        "checksum": "NONE",
        "elapsed_us": 13234,
        "bytes_total": 841,
        "bytes_payload": 41,
        "bytes_crypto": 800,
        "bytes_checksum": 0,
        "keygen_us": 3684,
        "encap_us": 3937,
        "decap_us": 5029,
        "tag_us": 408,
        "verify_us": 168,
        "crc_us": 0,
        "heap": 201412,
        "result": "DELIVERED",
    },
    "PQC_CRC32": {
        "label": "PQC + CRC32",
        "crypto": "ML-KEM-512",
        "checksum": "CRC32",
        "elapsed_us": 13130,
        "bytes_total": 845,
        "bytes_payload": 41,
        "bytes_crypto": 800,
        "bytes_checksum": 4,
        "keygen_us": 3586,
        "encap_us": 3911,
        "decap_us": 5012,
        "tag_us": 435,
        "verify_us": 168,
        "crc_us": 10,
        "heap": 201412,
        "result": "DELIVERED",
    },
}
CONSOLIDATED_PQC_BENCH = (
    ("BASELINE 240 MHz", "3.302", "3.866", "4.990"),
    ("LIMITED 80 MHz", "10.066", "11.787", "15.217"),
)

# --- Paleta de Cores ----------------------------------------------------------
C_SPACE_BG       = (5, 5, 18)
C_PANEL_BG       = (12, 14, 30)
C_PANEL_BORDER   = (40, 60, 120)
C_PANEL_HEADER   = (18, 22, 50)
C_ACCENT_CYAN    = (0, 220, 255)
C_ACCENT_BLUE    = (0, 120, 255)
C_ACCENT_GREEN   = (0, 255, 140)
C_ACCENT_ORANGE  = (255, 165, 0)
C_ACCENT_RED     = (255, 60, 80)
C_ACCENT_PURPLE  = (160, 80, 255)
C_TEXT_PRIMARY    = (220, 230, 255)
C_TEXT_DIM        = (100, 120, 160)
C_SAT_BODY       = (70, 80, 100)
C_SAT_PANEL_BLUE = (40, 100, 200)
C_SAT_PANEL_DARK = (20, 50, 120)
C_SAT_GOLD       = (220, 190, 80)
C_ROBOT_FACE     = (180, 200, 230)
C_ROBOT_EYE      = (0, 200, 255)
C_ROBOT_SMILE    = (0, 255, 160)

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


def init_display():
    """Initialize the fullscreen display after CLI arguments are parsed."""
    global WIDTH, HEIGHT, screen, clock

    pygame.init()
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
        elif guard == "NONE":
            result = "SILENT"
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


def visible_timeline_events(events, limit=TIMELINE_WINDOW):
    return list(events)[-limit:]


def timeline_layout(events, x, y, width, height, limit=TIMELINE_WINDOW):
    visible_events = visible_timeline_events(events, limit=limit)
    if not visible_events:
        return []

    lane_top = y + 16
    lane_bottom = y + max(34, height - 14)
    left_pad = min(46, max(32, width // 5))
    right_pad = 10
    usable_w = max(1, width - left_pad - right_pad)
    step = 0 if len(visible_events) == 1 else usable_w / (len(visible_events) - 1)

    points = []
    for index, event in enumerate(visible_events):
        if len(visible_events) == 1:
            cx = x + left_pad + usable_w // 2
        else:
            cx = x + left_pad + int(round(step * index))
        cy = lane_bottom if event.guard == "CRC32" else lane_top
        points.append(
            {
                "event": event,
                "x": max(x, min(x + width - 1, cx)),
                "y": max(y, min(y + height - 1, cy)),
                "lane": "B CRC32" if event.guard == "CRC32" else "A NONE",
            }
        )
    return points


def event_to_json(event):
    data = asdict(event)
    data["bit_mask_hex"] = event.bit_mask_hex
    data["scenario"] = "B_CRC32" if event.guard == "CRC32" else "A_NONE"
    return data


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_slug(value):
    slug = []
    for char in str(value).lower():
        if char.isalnum():
            slug.append(char)
        elif char in {"-", "_"}:
            slug.append(char)
        else:
            slug.append("-")
    return "".join(slug).strip("-") or "session"


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
        value = int(token, 16)
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
        self.surface_cache = None
        self._build_surface()

    def _build_surface(self):
        margin = 50
        size = self.radius * 2 + margin * 2
        self.surface_cache = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        r = self.radius

        # Glow atmosferico externo
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(self.surface_cache, (50, 130, 255, min(alpha, 120)), (cx, cy), r + i)

        # Corpo base — oceano azul SOLIDO e opaco
        pygame.draw.circle(self.surface_cache, (25, 100, 200, 255), (cx, cy), r)
        pygame.draw.circle(self.surface_cache, (30, 90, 185, 255), (cx, cy), r - 2)

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
        pygame.draw.polygon(self.surface_cache, (*land_color, 255), points_na)
        pygame.draw.polygon(self.surface_cache, (60, 185, 85, 80), points_na)
        pygame.draw.polygon(self.surface_cache, (35, 130, 55, 180), points_na, 2)

        # America Central
        points_ca = [
            (int(cx + 20 * scale), int(cy + 5 * scale)),
            (int(cx + 30 * scale), int(cy + 15 * scale)),
            (int(cx + 25 * scale), int(cy + 35 * scale)),
            (int(cx + 15 * scale), int(cy + 40 * scale)),
            (int(cx + 5 * scale), int(cy + 30 * scale)),
            (int(cx + 10 * scale), int(cy + 10 * scale)),
        ]
        pygame.draw.polygon(self.surface_cache, (*land_color, 255), points_ca)
        pygame.draw.polygon(self.surface_cache, (35, 130, 55, 180), points_ca, 2)

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
        pygame.draw.polygon(self.surface_cache, (45, 160, 70, 255), points_sa)
        # Amazonia
        amazon = [
            (int(cx + 20 * scale), int(cy + 55 * scale)),
            (int(cx + 55 * scale), int(cy + 60 * scale)),
            (int(cx + 50 * scale), int(cy + 80 * scale)),
            (int(cx + 15 * scale), int(cy + 75 * scale)),
        ]
        pygame.draw.polygon(self.surface_cache, (35, 140, 55, 120), amazon)
        pygame.draw.polygon(self.surface_cache, (30, 120, 50, 180), points_sa, 2)

        # Groenlandia
        points_gl = [
            (int(cx + 20 * scale), int(cy - 115 * scale)),
            (int(cx + 50 * scale), int(cy - 120 * scale)),
            (int(cx + 55 * scale), int(cy - 100 * scale)),
            (int(cx + 40 * scale), int(cy - 90 * scale)),
            (int(cx + 20 * scale), int(cy - 95 * scale)),
        ]
        pygame.draw.polygon(self.surface_cache, (180, 210, 200, 255), points_gl)
        pygame.draw.polygon(self.surface_cache, (140, 170, 160, 150), points_gl, 1)

        # Ilhas do Caribe
        for ix2, iy2, iw, ih in [
            (int(cx + 35 * scale), int(cy + 15 * scale), int(10 * scale), int(6 * scale)),
            (int(cx + 45 * scale), int(cy + 22 * scale), int(8 * scale), int(5 * scale)),
            (int(cx + 40 * scale), int(cy + 30 * scale), int(6 * scale), int(4 * scale)),
        ]:
            pygame.draw.ellipse(self.surface_cache, (*land_color, 250),
                                (ix2, iy2, max(3, iw), max(3, ih)))

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
            self.surface_cache.blit(s, (x - w // 2, y - h // 2))

        # Iluminacao solar
        light_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            ratio = i / r
            alpha = int(50 * (1 - ratio) ** 2)
            pygame.draw.circle(light_surf, (255, 255, 255, min(alpha, 40)),
                               (cx - int(r * 0.3), cy - int(r * 0.3)), i)
        self.surface_cache.blit(light_surf, (0, 0))

        # Sombra terminador
        shadow_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            ratio = i / r
            alpha = int(80 * (1 - ratio) ** 1.5)
            pygame.draw.circle(shadow_surf, (0, 0, 20, min(alpha, 60)),
                               (cx + int(r * 0.35), cy + int(r * 0.35)), i)
        self.surface_cache.blit(shadow_surf, (0, 0))

        # Mascara circular
        clean = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(clean, (50, 130, 255, min(alpha, 120)), (cx, cy), r + i)
        for y_pos in range(size):
            for x_pos in range(size):
                dist_sq = (x_pos - cx) ** 2 + (y_pos - cy) ** 2
                if dist_sq <= r * r:
                    clean.set_at((x_pos, y_pos), self.surface_cache.get_at((x_pos, y_pos)))
        self.surface_cache = clean
        pygame.draw.circle(self.surface_cache, (80, 160, 255, 50), (cx, cy), r, 2)

    def draw(self, surface, t):
        blit_x = self.center_x - self.surface_cache.get_width() // 2
        blit_y = self.center_y - self.surface_cache.get_height() // 2
        surface.blit(self.surface_cache, (blit_x, blit_y))


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

    def send(self, command_line):
        self._tx.put(command_line)

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
                            continue
                        if command_line is None:
                            break
                        if not self._send_one(bridge, command_line):
                            break
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

    def _send_one(self, bridge, command_line):
        try:
            command, args = self._split_command(command_line)
            frame = bridge.send(command, args)
            payload = {}
            raw_payload = ""
            if frame.payload_fields:
                raw_payload = " ".join(frame.payload_fields)
                try:
                    payload = decode_key_values(frame.payload_fields)
                except ProtocolError:
                    payload = {"payload": raw_payload}
            self._rx.put(
                (
                    "response",
                    {
                        "command": command_line.upper(),
                        "status": frame.status or "UNKNOWN",
                        "payload": payload,
                        "raw_payload": raw_payload,
                    },
                )
            )
            return True
        except ProtocolError as exc:
            self._rx.put(("error", {"command": command_line.upper(), "status": str(exc)}))
            return True
        except SerialBridgeError as exc:
            self._rx.put(("error", {"command": command_line.upper(), "status": str(exc)}))
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
        trail_len = 25
        for i in range(trail_len, 0, -1):
            a = self.angle - (i * 0.03)
            x = self.earth.center_x + self.orbit_radius * math.cos(a)
            y = self.earth.center_y + self.orbit_radius * math.sin(a) * 0.4
            alpha = int(200 * (1 - i / trail_len))
            r_size = max(1, int(4 * (1 - i / trail_len)))
            glow_surf = pygame.Surface((r_size * 4, r_size * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (0, 180, 255, alpha),
                               (r_size * 2, r_size * 2), r_size)
            surface.blit(glow_surf, (int(x) - r_size * 2, int(y) - r_size * 2))

    def draw(self, surface, t):
        self.draw_orbit_line(surface)
        self.draw_trail(surface, t)

        x, y = self.get_position()
        ix, iy = int(x), int(y)
        bs = self.body_size

        # -- Paineis solares --
        panel_w, panel_h = bs + 24, bs // 3
        # Painel esquerdo
        for i in range(3):
            shade = max(0, min(255, int(C_SAT_PANEL_BLUE[0] + 20 * math.sin(t * 2 + i))))
            color = (shade, C_SAT_PANEL_BLUE[1], C_SAT_PANEL_BLUE[2])
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
            shade = max(0, min(255, int(C_SAT_PANEL_BLUE[0] + 20 * math.sin(t * 2 + i + 1))))
            color = (shade, C_SAT_PANEL_BLUE[1], C_SAT_PANEL_BLUE[2])
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
        glow_alpha = int(40 + 20 * math.sin(t * 3))
        pygame.draw.rect(glow_s, (0, 180, 255, glow_alpha),
                         (0, 0, bs + 20, bs + 20), border_radius=6)
        surface.blit(glow_s, (ix - bs // 2 - 10, iy - bs // 2 - 10))
        pygame.draw.rect(surface, C_SAT_BODY, body_rect, border_radius=4)
        pygame.draw.rect(surface, C_ACCENT_CYAN, body_rect, 1, border_radius=4)

        # -- Robo sorridente --
        draw_robot_pixel(surface, ix, iy, pixel_size=6, t=t)

        # -- Antena --
        ant_height = 16
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix, iy - bs // 2), (ix, iy - bs // 2 - ant_height), 2)
        blink = int(200 + 55 * math.sin(t * 6))
        pygame.draw.circle(surface, (blink, 50, 50),
                           (ix, iy - bs // 2 - ant_height), 3)

        # Label
        label = FONT_PIXEL.render("PQC-SAT-01", True, C_ACCENT_CYAN)
        surface.blit(label, (ix - label.get_width() // 2, iy + bs // 2 + 8))


# --- Painel de Interface / Dashboard -----------------------------------------
class DashboardPanel:
    """Painel lateral com informacoes de telemetria e comandos."""

    def __init__(self, serial_client=None):
        self.serial_client = serial_client
        self.serial_connected = False
        self.serial_status = "SERIAL DESATIVADA"
        self.hardware_payload = {}
        self.hardware_state = {}
        self.help_visible = False
        self.help_topic = "INDEX"
        self.help_scroll = 0
        self.command_history = []
        self.command_button_rects = []
        self.input_text = ""
        self.input_active = True
        self.cursor_blink = 0
        self.session_status = "SIMULADO"
        self.pqc_algorithm = "ML-KEM-512 (ATIVO - SIMULADO)" if serial_client is None else "ML-KEM-512 (PENDENTE)"
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
        self.telemetry_poll_timer = 0.0
        self.last_fault_event = None
        self.fault_overlay_visible = False
        self.fault_overlay = {}
        self.fault_overlay_position = None
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.dragging_fault_overlay = False
        self.fault_drag_offset = (0, 0)
        self.fault_flow_animation = None
        self.checksum_enabled = False
        self.pqc_enabled = True
        self.classic_enabled = False
        self.message_preset = "PQC"
        self.results_overlay_visible = False
        self.top_results_btn_rect = None
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
        self.mission_overlay_rects = {}
        self.mission_overlay_close_rects = {}
        self.mission_overlay_drag_rects = {}
        self.mission_flow_control_rects = {}
        self.mission_comparison_rect = None
        self.dragging_mission_overlay = None
        self.mission_drag_offset = (0, 0)
        self.mission_flow_animation = None
        self.effect_timer = 0.0
        self.effect_result = ""
        self.effect_label = ""
        self.effect_color = C_ACCENT_CYAN
        self._fault_overlay_surface = None
        self._append_history("SYS_INIT", "OK")
        self._append_history("MODE_SELECT", "SIMULADO")
        self._append_history("PQC_BACKEND", "AGUARDANDO")

        if self.serial_client is not None:
            self.serial_status = "INICIANDO SERIAL"
            self._append_history("SERIAL", "INICIANDO")
            self.serial_client.start()
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
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.top_results_btn_rect is not None and self.top_results_btn_rect.collidepoint(event.pos):
                self._execute_command("PQC_RESULTS")
                return True

        if getattr(self, "results_overlay_visible", False):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                panel_rect, close_rect = self._results_overlay_geometry()
                if close_rect.collidepoint(event.pos):
                    self.results_overlay_visible = False
                    return
                if not panel_rect.collidepoint(event.pos):
                    self.results_overlay_visible = False
                    return
                return
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.results_overlay_visible = False
                return
            elif event.type == pygame.MOUSEWHEEL:
                return
            return

        if self._handle_fault_overlay_event(event):
            return True

        if self._handle_mission_overlay_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self._handle_command_button_click(event.pos):
                self.input_active = False
                return
            if event.button in {4, 5} and self.help_visible:
                delta = -3 if event.button == 4 else 3
                self.help_scroll = max(0, self.help_scroll + delta)
                return
            self.input_active = True

        if event.type == pygame.MOUSEWHEEL and self.help_visible:
            self.help_scroll = max(0, self.help_scroll - event.y * 3)
            return

        if event.type == pygame.KEYDOWN:
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
                    self._toggle_mission_flow_pause(scenario)
                    self._bring_mission_overlay_to_front(scenario)
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

        if event.type == pygame.MOUSEMOTION and self.dragging_mission_overlay:
            scenario = self.dragging_mission_overlay
            width, height = self._mission_overlay_size()
            x = event.pos[0] - self.mission_drag_offset[0]
            y = event.pos[1] - self.mission_drag_offset[1]
            self.mission_overlay_positions[scenario] = self._clamp_mission_overlay_position(x, y, width, height)
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
                self._toggle_fault_flow_pause()
                return True
            if self.fault_overlay_drag_rect is not None and self.fault_overlay_drag_rect.collidepoint(event.pos):
                rect = self.fault_overlay_rect or self.fault_overlay_drag_rect
                self.dragging_fault_overlay = True
                self.fault_drag_offset = (event.pos[0] - rect.x, event.pos[1] - rect.y)
                return True
            if self.fault_overlay_rect is not None and self.fault_overlay_rect.collidepoint(event.pos):
                return True

        if event.type == pygame.MOUSEMOTION and self.dragging_fault_overlay:
            width, height = self._fault_overlay_size()
            x = event.pos[0] - self.fault_drag_offset[0]
            y = event.pos[1] - self.fault_drag_offset[1]
            self.fault_overlay_position = self._clamp_overlay_position(x, y, width, height)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging_fault_overlay:
            self.dragging_fault_overlay = False
            return True

        return False

    def _toggle_fault_flow_pause(self):
        if self.fault_flow_animation is None:
            return
        paused = not bool(self.fault_flow_animation.get("paused"))
        self.fault_flow_animation["paused"] = paused

    def _close_fault_overlay(self):
        self.fault_overlay_visible = False
        self.fault_overlay = {}
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.dragging_fault_overlay = False
        self.fault_flow_animation = None

    def _toggle_mission_flow_pause(self, scenario):
        if not self._mission_overlay_is_animating(scenario):
            return
        paused = not bool(self.mission_flow_animation.get("paused"))
        self.mission_flow_animation["paused"] = paused

    def _execute_command(self, cmd):
        """Processa um comando digitado."""
        cmd_clean = cmd.strip()
        cmd_upper = cmd_clean.upper()
        parts = cmd_upper.split()
        command_name = parts[0] if parts else ""
        if cmd_upper != "HELP":
            self.help_visible = False
            self.help_scroll = 0

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
        elif cmd_upper == "PQC_STATUS":
            if self.serial_connected:
                self._queue_serial_command("PQC_INFO", visible=True)
                return
            status = "PQC PENDENTE"
        elif cmd_upper == "RESET_SESSION":
            status = self._reset_session()
        elif cmd_upper == "PQC_RESULTS":
            self.results_overlay_visible = not getattr(self, "results_overlay_visible", False)
            status = "SHOW_RESULTS" if self.results_overlay_visible else "HIDE_RESULTS"
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
            self.help_visible = True
            self.help_topic = "INDEX"
            self.help_scroll = 0
            status = "HELP AVANÇADO"
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

    def _execute_mission_command(self, args):
        if len(args) != 1:
            return "INVALID_INPUT"
        scenario = args[0].upper().replace("+", "_")
        if scenario not in {"CLASSIC", "PQC", "PQC_CRC32"}:
            return "INVALID_INPUT"
        self._set_message_preset(scenario)
        if self.serial_client is None or not self.serial_connected:
            self.session_status = "AGUARDANDO SAT"
            return "SAT OFF"

        command = f"MISSION {scenario}"
        self._queue_serial_command(command, visible=True)
        for effect_command in self._mission_effect_commands(scenario):
            self._queue_serial_command(effect_command, visible=False)
        self.session_status = f"MISSÃO {scenario}"
        return None

    @staticmethod
    def _mission_effect_commands(scenario):
        if scenario == "CLASSIC":
            return ("BARGRAPH 25", "LED BLUE")
        if scenario == "PQC":
            return ("BARGRAPH 75", "LED MAGENTA")
        if scenario == "PQC_CRC32":
            return ("BARGRAPH 100", "LED GREEN")
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
        try:
            spec = self._fault_spec_from_args(args or [])
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
        self._open_fault_overlay_from_event(event)

        if self.serial_connected:
            self._queue_serial_command(event.to_firmware_command(), visible=True)

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
        self.hardware_samples.clear()
        self.battery_runs = 0
        self.last_fault_event = None
        self.fault_overlay_visible = False
        self.fault_overlay.clear()
        self.fault_overlay_position = None
        self.fault_overlay_rect = None
        self.fault_overlay_close_rect = None
        self.fault_overlay_drag_rect = None
        self.fault_flow_control_rect = None
        self.dragging_fault_overlay = False
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
        self.mission_overlay_rects.clear()
        self.mission_overlay_close_rects.clear()
        self.mission_overlay_drag_rects.clear()
        self.mission_flow_control_rects.clear()
        self.mission_comparison_rect = None
        self.dragging_mission_overlay = None
        self.mission_drag_offset = (0, 0)
        self.mission_flow_animation = None
        self.message_preset = "PQC"
        self.classic_enabled = False
        self.pqc_enabled = True
        self._active_campaign_run_id = "manual"
        self._set_checksum_enabled(False)
        self._refresh_experiment_metrics()
        self.session_status = "SIMULADO"
        self.effect_timer = 0.0
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
        self.effect_result = event.result
        if event.result == "SILENT":
            self.effect_color = C_ACCENT_RED
            self.effect_label = "FALHA SILENCIOSA"
        elif event.result == "DETECTED_GUARD":
            self.effect_color = C_ACCENT_ORANGE
            self.effect_label = "CRC32 DETECTOU"
        else:
            self.effect_color = C_ACCENT_GREEN
            self.effect_label = event.result

    def _open_fault_overlay_from_event(self, event):
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
        self._open_fault_overlay(fault)

    def _open_fault_overlay_from_payload(self, command, payload):
        command_name = command.split()[0].upper()
        is_pqc_fault = command_name == "PQC_FAULT"
        target = str(payload.get("target", "CIPHERTEXT" if is_pqc_fault else "PAYLOAD")).upper()
        guard = payload.get("guard")
        if not guard:
            confirmation = str(payload.get("confirmation", "NONE")).upper()
            guard = "KEY_CONFIRM" if is_pqc_fault and confirmation != "NONE" else "NONE"
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
            "confirmation": payload.get("confirmation", ""),
            "decap_us": _optional_int(payload.get("decap_us")),
            "confirm_us": _optional_int(payload.get("confirm_us")),
            "elapsed_us": _optional_int(payload.get("elapsed_us")),
            "mode": "HARDWARE",
        }
        self._open_fault_overlay(fault)

    def _open_fault_overlay(self, fault):
        self.fault_overlay = dict(fault)
        self.fault_overlay_visible = True
        if self.fault_overlay_position is None:
            self.fault_overlay_position = self._default_fault_overlay_position()
        self.fault_flow_animation = {
            "steps": self._fault_flow_steps(fault),
            "age": 0.0,
            "duration": FAULT_FLOW_ANIMATION_SECONDS,
            "paused": False,
        }

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
        target = str(fault.get("target", "PAYLOAD")).upper()
        crc_changed = bool(fault.get("crc_before") and fault.get("crc_after") and fault.get("crc_before") != fault.get("crc_after"))
        is_pqc = target == "CIPHERTEXT" or guard == "KEY_CONFIRM"

        if is_pqc:
            return (
                {
                    "label": "CIPHERTEXT",
                    "detail": "pacote ML-KEM antes da falha",
                    "explain": "A falha é aplicada no ciphertext ML-KEM. A mensagem ainda depende da decapsulação correta.",
                    "color": C_ACCENT_PURPLE,
                },
                {
                    "label": "BIT-FLIP",
                    "detail": f"byte {fault.get('byte_index', '--')} mask {fault.get('bit_mask', '--')}",
                    "explain": "Um único bit é invertido. Em PQC isso pode mudar o segredo derivado pelo receptor.",
                    "color": C_ACCENT_RED,
                },
                {
                    "label": "DECAP",
                    "detail": "tenta recuperar segredo",
                    "explain": "A Wisdom decapsula o ciphertext corrompido e compara o segredo esperado.",
                    "color": C_ACCENT_PURPLE,
                    "time_us": fault.get("decap_us"),
                },
                {
                    "label": "CONFIRMA",
                    "detail": str(fault.get("confirmation") or guard),
                    "explain": "A confirmação HMAC testa se as duas pontas chegaram ao mesmo segredo sem revelar a chave.",
                    "color": C_ACCENT_ORANGE,
                    "time_us": fault.get("confirm_us"),
                },
                {
                    "label": "RESULTADO",
                    "detail": self._fault_result_label(result),
                    "explain": self._fault_result_explanation(fault),
                    "color": self._fault_result_color(result),
                    "time_us": fault.get("elapsed_us"),
                },
            )

        return (
            {
                "label": "PAYLOAD",
                "detail": "payload íntegro",
                "explain": "Começamos com o payload íntegro. É o mesmo tipo de dado que o satélite enviaria na missão.",
                "color": C_ACCENT_BLUE,
            },
            {
                "label": "BIT-FLIP",
                "detail": f"byte {fault.get('byte_index', '--')} mask {fault.get('bit_mask', '--')}",
                "explain": "A radiação simulada inverte um único bit. O byte muda, mas o sistema ainda precisa perceber.",
                "color": C_ACCENT_RED,
            },
            {
                "label": "GUARD",
                "detail": "CRC32 ativo" if guard == "CRC32" else "sem checksum",
                "explain": (
                    "O CRC32 guardado antes da falha será comparado com o CRC recalculado depois."
                    if guard == "CRC32"
                    else "Sem checksum, o sistema não tem uma referência simples para comparar o payload."
                ),
                "color": C_ACCENT_GREEN if guard == "CRC32" else C_TEXT_DIM,
            },
            {
                "label": "VERIFICA",
                "detail": "CRC divergiu" if crc_changed else "nada compara",
                "explain": "Depois do bit-flip, recalculamos o CRC. Se mudou, a corrupção fica visível antes da entrega.",
                "color": C_ACCENT_ORANGE if guard == "CRC32" else C_TEXT_DIM,
                "time_us": fault.get("guard_verify_us"),
            },
            {
                "label": "RESULTADO",
                "detail": self._fault_result_label(result),
                "explain": self._fault_result_explanation(fault),
                "color": self._fault_result_color(result),
                "time_us": fault.get("elapsed_us"),
            },
        )

    @staticmethod
    def _fault_result_color(result):
        if result == "SILENT":
            return C_ACCENT_RED
        if result in {"DETECTED_GUARD", "PROTOCOL_REJECT", "KEY_MISMATCH"}:
            return C_ACCENT_GREEN
        return C_ACCENT_CYAN

    @staticmethod
    def _fault_result_label(result):
        labels = {
            "SILENT": "FALHA SILENCIOSA",
            "DETECTED_GUARD": "DETECTADA",
            "PROTOCOL_REJECT": "REJEIÇÃO DO PROTOCOLO",
            "KEY_MISMATCH": "CHAVE DIVERGENTE",
            "OK": "SEM IMPACTO",
        }
        return labels.get(str(result), str(result or "--"))

    @staticmethod
    def _fault_result_short_label(result):
        labels = {
            "SILENT": "SILENCIOSA",
            "DETECTED_GUARD": "DETECTADA",
            "PROTOCOL_REJECT": "REJEITADA",
            "KEY_MISMATCH": "CHAVE DIF.",
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
        if result == "PROTOCOL_REJECT":
            return "A confirmação autenticada falhou. O protocolo rejeita o ciphertext corrompido."
        if result == "KEY_MISMATCH":
            return "A decapsulação produziu segredo diferente. Sem confirmação, isso vira divergência de chave."
        if target == "CIPHERTEXT":
            return "A falha atingiu o material PQC; compare segredo, tag e resultado final."
        return "A tentativa terminou sem divergência observada."

    def _queue_serial_command(self, command_line, visible=True):
        if self.serial_client is None:
            self._append_history(command_line, "SERIAL OFF")
            return
        self.serial_client.send(command_line)
        if visible:
            self._append_history(command_line, "QUEUED")

    def update(self, dt):
        self.uptime += dt
        self.cursor_blink += dt
        if self.effect_timer > 0:
            self.effect_timer = max(0.0, self.effect_timer - dt)
        if self.mission_effect_timer > 0:
            self.mission_effect_timer = max(0.0, self.mission_effect_timer - dt)
        if self.mission_flow_animation is not None and not self.mission_flow_animation.get("paused"):
            self.mission_flow_animation["age"] += dt
            if self.mission_flow_animation["age"] >= self.mission_flow_animation["duration"]:
                scenario = self.mission_flow_animation.get("scenario")
                if scenario:
                    self.mission_flow_control_rects.pop(scenario, None)
                self.mission_flow_animation = None
        if self.fault_flow_animation is not None and not self.fault_flow_animation.get("paused"):
            self.fault_flow_animation["age"] += dt
            if self.fault_flow_animation["age"] >= self.fault_flow_animation["duration"]:
                self.fault_flow_control_rect = None
                self.fault_flow_animation = None
        self._advance_demo(dt)
        self._poll_telemetry(dt)
        self._drain_serial_events()

    def _poll_telemetry(self, dt):
        if not AUTO_TELEMETRY_ENABLED:
            self.telemetry_poll_timer = 0.0
            return
        if self.serial_client is None or not self.serial_connected:
            self.telemetry_poll_timer = 0.0
            return
        self.telemetry_poll_timer += dt
        if self.telemetry_poll_timer >= TELEMETRY_POLL_SECONDS:
            self.telemetry_poll_timer = 0.0
            self._queue_serial_command("TELEMETRY", visible=False)

    def _drain_serial_events(self):
        if self.serial_client is None:
            return

        for event_type, payload in self.serial_client.poll():
            if event_type == "state":
                self.serial_connected = bool(payload["connected"])
                self.serial_status = payload["status"]
                if self.serial_connected:
                    status = "ONLINE"
                    self.pqc_algorithm = "ML-KEM-512 (ATIVO)"
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
                self._append_history(command, status)
            elif event_type == "error":
                self._append_history(payload["command"], "ERROR")
                self.serial_status = payload["status"]

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
            self._open_fault_overlay_from_payload(command, payload)
        elif command.startswith("TELEMETRY"):
            self.hardware_payload = payload
        elif command.startswith("STATUS"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
        elif command.startswith("PQC_"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
            if command.startswith("PQC_FAULT"):
                self._open_fault_overlay_from_payload(command, payload)
        elif command.startswith("MISSION"):
            self.hardware_payload = payload
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

    def _open_mission_overlay(self, payload):
        mission = dict(payload)
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        mission["scenario"] = scenario
        self.mission_overlays[scenario] = mission
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
        if not steps:
            self.mission_flow_animation = None
            return
        self.mission_flow_animation = {
            "scenario": self._normalize_mission_scenario(mission.get("scenario", "MISSION")),
            "mission": dict(mission),
            "steps": steps,
            "age": 0.0,
            "duration": MISSION_FLOW_ANIMATION_SECONDS,
            "paused": False,
        }

    def _mission_flow_steps(self, mission):
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        parts = {label: value for label, value, _color in self._mission_package_parts(mission)}
        payload = parts.get("payload", 0)
        hmac = parts.get("HMAC", 0)
        mlkem = parts.get("ML-KEM", 0)
        checksum = parts.get("CRC", 0)
        total = self._mission_int(mission, "bytes_total", payload + hmac + mlkem + checksum)

        if total <= 0:
            return []

        steps = [
            {
                "label": "PAYLOAD",
                "detail": "mensagem base",
                "explain": "A placa recebe o payload bruto. Ainda não há bytes de autenticação, KEM ou checksum anexados.",
                "kind": "payload",
                "packet_bytes": payload,
                "added_bytes": payload,
                "time_us": None,
                "color": C_ACCENT_BLUE,
            }
        ]

        if scenario in {"PQC", "PQC_CRC32"}:
            steps.extend(
                (
                    {
                        "label": "KEYGEN",
                        "detail": "gera chaves ML-KEM",
                        "explain": "A Wisdom cria o par ML-KEM-512. É custo local de CPU/RAM; o pacote ainda não cresce.",
                        "kind": "keygen",
                        "packet_bytes": payload,
                        "added_bytes": 0,
                        "time_us": self._mission_int(mission, "keygen_us"),
                        "color": C_ACCENT_PURPLE,
                    },
                    {
                        "label": "ENCAP",
                        "detail": "encapsula segredo",
                        "explain": "O emissor usa a chave pública para encapsular um segredo. O ciphertext ML-KEM entra no pacote.",
                        "kind": "mlkem",
                        "packet_bytes": payload + mlkem,
                        "added_bytes": mlkem,
                        "time_us": self._mission_int(mission, "encap_us"),
                        "color": C_ACCENT_PURPLE,
                    },
                    {
                        "label": "DECAP",
                        "detail": "recupera segredo",
                        "explain": "O receptor decapsula o ciphertext e deriva o mesmo segredo. Bit-flip crítico pode ser rejeitado.",
                        "kind": "decap",
                        "packet_bytes": payload + mlkem,
                        "added_bytes": 0,
                        "time_us": self._mission_int(mission, "decap_us"),
                        "color": C_ACCENT_PURPLE,
                    },
                )
            )

        steps.append(
            {
                "label": "HMAC",
                "detail": "autenticação",
                "explain": "A placa calcula HMAC-SHA256 com o segredo. A tag autentica mensagem e chave.",
                "kind": "hmac",
                "packet_bytes": payload + mlkem + hmac,
                "added_bytes": hmac,
                "time_us": self._mission_int(mission, "tag_us"),
                "color": C_ACCENT_ORANGE,
            }
        )

        if checksum > 0 or scenario == "PQC_CRC32":
            steps.append(
                {
                    "label": "CRC32",
                    "detail": "checksum do payload",
                    "explain": "O CRC32 adiciona 4 bytes baratos. Não é criptografia; revela bit-flip acidental no payload.",
                    "kind": "crc",
                    "packet_bytes": payload + mlkem + hmac + checksum,
                    "added_bytes": checksum,
                    "time_us": self._mission_int(mission, "crc_us"),
                    "color": C_ACCENT_GREEN,
                }
            )

        verify_detail = "verifica CRC e tag" if checksum > 0 else "verifica tag"
        verify_time = self._mission_int(mission, "verify_us") + (self._mission_int(mission, "crc_us") if checksum > 0 else 0)
        steps.append(
            {
            "label": "VERIFICA",
            "detail": verify_detail,
            "explain": "No recebimento, a Wisdom recalcula tag e CRC. A comparação decide entrega, silêncio ou rejeição.",
                "kind": "verify",
                "packet_bytes": payload + mlkem + hmac + checksum,
                "added_bytes": 0,
                "time_us": verify_time,
                "color": C_ACCENT_GREEN if checksum > 0 else C_TEXT_PRIMARY,
            }
        )

        steps.append(
            {
            "label": "RESULTADO",
            "detail": str(mission.get("result", "DELIVERED")),
            "explain": "Fluxo concluído. Compare tempo, bytes, heap e flags para medir o custo prático.",
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
        self.mission_overlays.pop(scenario, None)
        self.mission_overlay_positions.pop(scenario, None)
        self.mission_overlay_rects.pop(scenario, None)
        self.mission_overlay_close_rects.pop(scenario, None)
        self.mission_overlay_drag_rects.pop(scenario, None)
        self.mission_flow_control_rects.pop(scenario, None)
        self.mission_overlay_order = [item for item in self.mission_overlay_order if item != scenario]
        if self.dragging_mission_overlay == scenario:
            self.dragging_mission_overlay = None
        if self.mission_flow_animation and self.mission_flow_animation.get("scenario") == scenario:
            self.mission_flow_animation = None
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
            "checksum",
            "payload_len",
            "payload_crc32",
            "bytes_payload",
            "bytes_crypto",
            "bytes_checksum",
            "bytes_total",
            "tag_us",
            "verify_us",
            "crc_us",
            "crc_match",
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
        if not source_command.startswith("PQC") and not any(key.startswith("pqc_") for key in payload):
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
            "checksum",
            "confirmation",
            "payload_crc32",
            "crc_tx",
            "crc_rx",
        )
        numeric_fields = (
            "key_match",
            "tag_ready",
            "tag_match",
            "crc_match",
            "payload_len",
            "bytes_payload",
            "bytes_crypto",
            "bytes_checksum",
            "bytes_total",
            "keygen_us",
            "encap_us",
            "decap_us",
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
        self._draw_fault_effect(surface, t, satellite)
        self._draw_left_panel(surface, t, satellite)
        self._draw_right_panel(surface, t)
        self._draw_top_bar(surface, t)
        self._draw_top_metrics(surface, t)
        self._draw_demo_overlay(surface, t)
        self._draw_mission_overlay(surface, t)
        self._draw_fault_overlay(surface, t)
        self._draw_bottom_bar(surface, t)
        if getattr(self, "results_overlay_visible", False):
            self._draw_results_overlay(surface, t)

    def _results_overlay_geometry(self):
        margin = max(26, int(min(WIDTH, HEIGHT) * 0.04))
        w = min(int(WIDTH * 0.88), WIDTH - margin * 2)
        h = min(int(HEIGHT * 0.88), HEIGHT - margin * 2)
        x = (WIDTH - w) // 2
        y = (HEIGHT - h) // 2
        close_w = 118 if WIDTH < 1500 else 150
        close_rect = pygame.Rect(x + w - close_w - 28, y + 28, close_w, 36)
        return pygame.Rect(x, y, w, h), close_rect

    def _draw_wrapped_text(self, surface, font, text, color, x, y, max_width, line_spacing=20, max_lines=None):
        lines = self._wrap_text_for_width(font, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            surface.blit(self._render_clipped(font, line, color, max_width), (x, y))
            y += line_spacing
        return y

    def _scenario_color(self, scenario):
        if scenario == "PQC_CRC32":
            return C_ACCENT_GREEN
        if scenario == "PQC":
            return C_ACCENT_ORANGE
        return C_TEXT_PRIMARY

    def _draw_results_overlay(self, surface, t):
        panel_rect, close_rect = self._results_overlay_geometry()
        x, y, w, h = panel_rect

        panel_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        panel_surf.fill((12, 14, 30, 236))
        surface.blit(panel_surf, (x, y))

        pygame.draw.rect(surface, C_PANEL_BORDER, panel_rect, width=2, border_radius=8)

        header_h = 92
        pygame.draw.rect(surface, C_PANEL_HEADER, (x + 2, y + 2, w - 4, header_h), border_radius=8)
        pygame.draw.line(surface, C_ACCENT_CYAN, (x, y + header_h), (x + w, y + header_h), 2)

        title_max = max(260, close_rect.x - (x + 36) - 18)
        title = "RESULTADOS CONSOLIDADOS DA BATERIA REAL"
        surface.blit(self._render_clipped(FONT_TITLE, title, C_ACCENT_CYAN, title_max), (x + 36, y + 19))
        subtitle = f"{CONSOLIDATED_ACCEPTANCE_LABEL}: {CONSOLIDATED_SUMMARY['records']} registros, {CONSOLIDATED_SUMMARY['failed']} falhas, {CONSOLIDATED_SUMMARY['mission_runs']} missões"
        surface.blit(self._render_clipped(FONT_BODY, subtitle, C_TEXT_DIM, title_max), (x + 36, y + 54))

        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)
        hovered = close_rect.collidepoint(mouse_pos)
        fill_c = (80, 20, 30) if hovered else (50, 15, 22)
        pygame.draw.rect(surface, fill_c, close_rect, border_radius=6)
        pygame.draw.rect(surface, C_ACCENT_RED, close_rect, width=2, border_radius=6)
        c_txt = FONT_LABEL.render("FECHAR", True, C_TEXT_PRIMARY)
        surface.blit(c_txt, (close_rect.x + (close_rect.width - c_txt.get_width()) // 2, close_rect.y + (close_rect.height - c_txt.get_height()) // 2))

        body_x = x + max(24, int(w * 0.035))
        body_y = y + header_h + 24
        body_w = w - (body_x - x) * 2
        gap = 18
        two_cols = body_w >= 920
        col_w = (body_w - gap) // 2 if two_cols else body_w
        col_h = h - (body_y - y) - 32

        if two_cols:
            left = pygame.Rect(body_x, body_y, col_w, col_h)
            right = pygame.Rect(body_x + col_w + gap, body_y, col_w, col_h)
        else:
            stacked_h = (col_h - gap) // 2
            left = pygame.Rect(body_x, body_y, col_w, stacked_h)
            right = pygame.Rect(body_x, body_y + stacked_h + gap, col_w, stacked_h)
        for rect in (left, right):
            pygame.draw.rect(surface, C_PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, C_PANEL_BORDER, rect, width=1, border_radius=6)

        # Coluna esquerda: custo das missões.
        pad = 18
        lx = left.x + pad
        ly = left.y + 18
        lw = left.width - pad * 2
        surface.blit(self._render_clipped(FONT_HEADER, "CUSTO DAS MISSÕES (240 MHz)", C_ACCENT_CYAN, lw), (lx, ly))
        ly += 38

        table_h = min(170, max(142, int(left.height * 0.36)))
        pygame.draw.rect(surface, C_PANEL_HEADER, (lx, ly, lw, table_h), border_radius=4)
        pygame.draw.rect(surface, C_PANEL_BORDER, (lx, ly, lw, table_h), width=1, border_radius=4)
        headers = ("CENÁRIO", "TEMPO", "BYTES", "STATUS")
        col_ws = (int(lw * 0.39), int(lw * 0.21), int(lw * 0.16), lw - int(lw * 0.39) - int(lw * 0.21) - int(lw * 0.16) - 8)
        cx = lx + 10
        for index, head in enumerate(headers):
            surface.blit(self._render_clipped(FONT_LABEL, head, C_ACCENT_CYAN, max(40, col_ws[index] - 6)), (cx, ly + 10))
            cx += col_ws[index]
        pygame.draw.line(surface, C_PANEL_BORDER, (lx, ly + 33), (lx + lw, ly + 33), 1)

        row_y = ly + 34
        row_h = max(30, (table_h - 35) // 3)
        for idx, scenario in enumerate(("CLASSIC", "PQC", "PQC_CRC32")):
            result = CONSOLIDATED_MISSION_BASELINE[scenario]
            if idx % 2:
                pygame.draw.rect(surface, (15, 20, 38), (lx + 1, row_y, lw - 2, row_h))
            cells = (
                result["label"],
                _format_elapsed(result["elapsed_us"]),
                f"{result['bytes_total']} B",
                result["result"],
            )
            cx = lx + 10
            for cell_index, cell in enumerate(cells):
                color = self._scenario_color(scenario) if cell_index == 0 else C_TEXT_PRIMARY
                surface.blit(self._render_clipped(FONT_SMALL, cell, color, max(42, col_ws[cell_index] - 8)), (cx, row_y + 8))
                cx += col_ws[cell_index]
            if idx < 2:
                pygame.draw.line(surface, C_PANEL_BORDER, (lx, row_y + row_h), (lx + lw, row_y + row_h), 1)
            row_y += row_h

        ly += table_h + 18
        notes = (
            "PQC foi 25,9x mais lento e 11,5x maior em bytes que CLASSIC.",
            "PQC+CRC32 manteve a entrega funcional e adicionou +4 bytes ao pacote.",
            "A RAM livre ficou estável: 201.412 B de heap nas amostras consolidadas.",
            "A 80 MHz, PQC subiu para 38,8 ms e 34,1x o baseline clássico.",
        )
        for note in notes:
            ly = self._draw_wrapped_text(surface, FONT_SMALL, f"- {note}", C_TEXT_PRIMARY, lx, ly, lw, line_spacing=18, max_lines=2)
            ly += 3

        # Coluna direita: segurança, campanha e próximos passos.
        rx = right.x + pad
        ry = right.y + 18
        rw = right.width - pad * 2
        surface.blit(self._render_clipped(FONT_HEADER, "SEGURANÇA E BENCHMARK", C_ACCENT_CYAN, rw), (rx, ry))
        ry += 38

        bench_h = min(132, max(112, int(right.height * 0.25)))
        pygame.draw.rect(surface, C_PANEL_HEADER, (rx, ry, rw, bench_h), border_radius=4)
        pygame.draw.rect(surface, C_PANEL_BORDER, (rx, ry, rw, bench_h), width=1, border_radius=4)
        surface.blit(self._render_clipped(FONT_LABEL, "ML-KEM-512, média em us, 100 rounds", C_ACCENT_ORANGE, rw - 20), (rx + 10, ry + 10))
        b_col_ws = (int(rw * 0.38), int(rw * 0.2), int(rw * 0.2), rw - int(rw * 0.38) - int(rw * 0.2) - int(rw * 0.2) - 8)
        by = ry + 36
        for row_index, row in enumerate(CONSOLIDATED_PQC_BENCH):
            cx = rx + 10
            for col_index, cell in enumerate(row):
                surface.blit(self._render_clipped(FONT_SMALL, cell, C_TEXT_PRIMARY, max(40, b_col_ws[col_index] - 8)), (cx, by))
                cx += b_col_ws[col_index]
            if row_index == 0:
                pygame.draw.line(surface, C_PANEL_BORDER, (rx, by + 24), (rx + rw, by + 24), 1)
            by += 38
        ry += bench_h + 16

        security_notes = (
            f"Aceite: {CONSOLIDATED_SUMMARY['records']} registros, {CONSOLIDATED_SUMMARY['failed']} falhas, {CONSOLIDATED_SUMMARY['mission_runs']} missões.",
            "PQC_KAT aprovado: ss_crc32=0xD9DA8D6C.",
            "Falhas payload: 600/600 silenciosas sem CRC32; 600/600 detectadas com CRC32.",
            "Coleta final: 10 PQC_BENCH de 100 rounds, todos OK.",
            "PQC_FAULT com confirmação: PROTOCOL_REJECT.",
        )
        for note in security_notes:
            ry = self._draw_wrapped_text(surface, FONT_SMALL, f"- {note}", C_TEXT_PRIMARY, rx, ry, rw, line_spacing=18, max_lines=2)
            ry += 3

        ry += 6
        pygame.draw.line(surface, C_PANEL_BORDER, (rx, ry), (rx + rw, ry), 1)
        ry += 14
        surface.blit(self._render_clipped(FONT_LABEL, "TRÊS MENSAGENS PARA FECHAR", C_ACCENT_GREEN, rw), (rx, ry))
        ry += 24
        block_gap = 8
        block_w = max(120, (rw - block_gap * 2) // 3)
        block_h = min(74, max(58, right.bottom - ry - 8))
        narrative_blocks = (
            ("CUSTO", "PQC: 25,9x tempo e 11,5x bytes.", C_ACCENT_ORANGE),
            ("SEGURANÇA", "CRC detecta; HMAC autentica.", C_ACCENT_GREEN),
            ("LIMITES", "Energia real fica como próximo passo.", C_ACCENT_CYAN),
        )
        for index, (label, body, color) in enumerate(narrative_blocks):
            bx = rx + index * (block_w + block_gap)
            bw = block_w if index < 2 else rw - (block_w + block_gap) * 2
            pygame.draw.rect(surface, (15, 20, 38), (bx, ry, bw, block_h), border_radius=5)
            pygame.draw.rect(surface, color, (bx, ry, bw, block_h), width=1, border_radius=5)
            surface.blit(self._render_clipped(FONT_LABEL, label, color, bw - 12), (bx + 7, ry + 7))
            self._draw_wrapped_text(surface, FONT_LABEL, body, C_TEXT_PRIMARY, bx + 7, ry + 27, bw - 14, line_spacing=15, max_lines=2)

    def _draw_fault_effect(self, surface, t, satellite):
        if self.effect_timer <= 0:
            return

        alpha = int(95 * min(1.0, self.effect_timer / 0.35))
        overlay = self._get_fault_overlay(surface)
        overlay.fill((*self.effect_color, max(0, min(95, alpha))))
        surface.blit(overlay, (0, 0))

        sx, sy = satellite.get_position()
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
        width = 386 if WIDTH >= 1600 else 350
        width = min(width, max(300, WIDTH - 40))
        height = min(360, max(332, HEIGHT - 120))
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
            return

        rect, close_rect = self._fault_overlay_geometry()
        drag_rect = pygame.Rect(rect.x, rect.y, rect.width, 44)
        self.fault_overlay_rect = rect
        self.fault_overlay_close_rect = close_rect
        self.fault_overlay_drag_rect = drag_rect

        result = str(self.fault_overlay.get("result", ""))
        color = self._fault_result_color(result)
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pulse = int(150 + 45 * math.sin(t * 8)) if self.effect_timer > 0 else 150
        pygame.draw.rect(panel, (*C_PANEL_BG, 232), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*color, max(120, pulse)), (0, 0, rect.width, rect.height), width=1, border_radius=8)
        pygame.draw.rect(panel, (*color, 34), (0, 0, rect.width, 44), border_radius=8)
        pygame.draw.line(panel, (*C_PANEL_BORDER, 180), (0, 44), (rect.width, 44), 1)
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
        paused = bool(animation.get("paused"))

        x = rect.x + 14
        y = rect.y + 72
        width = rect.width - 28

        header = f"FALHA PASSO {active_index + 1}/{len(steps)}"
        control_rect = pygame.Rect(rect.right - 82, y - 2, 64, 22)
        self.fault_flow_control_rect = control_rect
        surface.blit(self._render_clipped(FONT_LABEL, header, C_ACCENT_CYAN, width - 76), (x, y))
        button_label = "PLAY" if paused else "PAUSAR"
        pygame.draw.rect(surface, (16, 22, 42), control_rect, border_radius=4)
        pygame.draw.rect(surface, C_ACCENT_ORANGE if paused else C_PANEL_BORDER, control_rect, width=1, border_radius=4)
        button_text = FONT_LABEL.render(button_label, True, C_ACCENT_ORANGE if paused else C_TEXT_DIM)
        surface.blit(
            button_text,
            (
                control_rect.centerx - button_text.get_width() // 2,
                control_rect.centery - button_text.get_height() // 2,
            ),
        )
        y += 18

        step_rect = pygame.Rect(x, y, width, 96)
        pygame.draw.rect(surface, (14, 20, 38), step_rect, border_radius=5)
        pygame.draw.rect(surface, color, step_rect, width=1, border_radius=5)
        step_title = f"{active_step['label']} - {active_step['detail']}"
        surface.blit(self._render_clipped(FONT_SMALL, step_title, color, width - 14), (step_rect.x + 7, step_rect.y + 7))
        time_us = active_step.get("time_us")
        metric = _format_elapsed(time_us) if time_us not in {None, ""} else self._fault_step_metric(fault, active_step["label"])
        surface.blit(self._render_clipped(FONT_LABEL, metric, C_TEXT_DIM, width - 14), (step_rect.x + 7, step_rect.y + 27))
        self._draw_wrapped_text(
            surface,
            FONT_LABEL,
            active_step.get("explain", ""),
            C_TEXT_PRIMARY,
            step_rect.x + 7,
            step_rect.y + 46,
            width - 14,
            line_spacing=14,
            max_lines=3,
        )

        bits_y = step_rect.bottom + 12
        self._draw_fault_byte_rows(surface, x, bits_y, width, fault)

        timeline_y = bits_y + 74
        timeline_x = x + 10
        timeline_w = width - 20
        node_positions = [timeline_x + int(round(index * timeline_w / max(1, len(steps) - 1))) for index in range(len(steps))]
        pygame.draw.line(surface, C_PANEL_BORDER, (node_positions[0], timeline_y), (node_positions[-1], timeline_y), 2)
        progress_ratio = min(
            1.0,
            max(0.0, animation.get("age", 0.0) / max(0.001, animation.get("duration", FAULT_FLOW_ANIMATION_SECONDS))),
        )
        marker_x = node_positions[0] + int((node_positions[-1] - node_positions[0]) * progress_ratio)
        pygame.draw.line(surface, color, (node_positions[0], timeline_y), (marker_x, timeline_y), 3)
        short_labels = {
            "PAYLOAD": "PAY",
            "CIPHERTEXT": "CT",
            "BIT-FLIP": "BIT",
            "GUARD": "CRC",
            "VERIFICA": "VER",
            "DECAP": "DEC",
            "CONFIRMA": "MAC",
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

        hint = "Final: resultado da falha e detecção."
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

        metric_y = y + 176
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
            self._draw_overlay_metric_box(surface, label, value, bx, by, metric_w, 36, metric_color)

    def _fault_step_metric(self, fault, label):
        if label == "BIT-FLIP":
            return f"{fault.get('before_byte', '--')} -> {fault.get('after_byte', '--')}"
        if label in {"GUARD", "VERIFICA"}:
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
            flags = []
            if fault.get("key_match") is not None:
                flags.append(f"key={str(fault.get('key_match')).lower()}")
            if fault.get("tag_match") is not None:
                flags.append(f"tag={str(fault.get('tag_match')).lower()}")
            if fault.get("confirmation"):
                flags.append(f"confirm={fault.get('confirmation')}")
            lines = (
                f"ct crc antes: {before_crc[-8:]}",
                f"ct crc depois: {after_crc[-8:]}",
                "  ".join(flags) if flags else "byte específico indisponível no resumo",
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
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (*C_PANEL_BG, 210), (0, 0, rect.width, rect.height),
                         border_radius=8)
        pygame.draw.rect(panel_surf, (*C_PANEL_BORDER, 150), (0, 0, rect.width, rect.height),
                         1, border_radius=8)
        surface.blit(panel_surf, (rect.x, rect.y))

        if title:
            header_rect = pygame.Rect(rect.x, rect.y, rect.width, 32)
            h_surf = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(h_surf, (*C_PANEL_HEADER, 220),
                             (0, 0, header_rect.width, header_rect.height),
                             border_top_left_radius=8, border_top_right_radius=8)
            surface.blit(h_surf, (header_rect.x, header_rect.y))

            # Indicador luminoso (circulo verde pulsante)
            glow = int(180 + 75 * math.sin(t * 2))
            pygame.draw.circle(surface, (0, glow, int(glow * 0.8)),
                               (rect.x + 14, rect.y + 16), 4)

            title_surf = FONT_SMALL.render(title, True, C_ACCENT_CYAN)
            surface.blit(title_surf, (rect.x + 26, rect.y + 8))

    def _draw_left_panel(self, surface, t, satellite):
        """Painel esquerdo: Falhas e integridade (foco da simulacao)."""
        pw = 300
        panel_rect = pygame.Rect(20, 55, pw, HEIGHT - 110)
        self._draw_panel_bg(surface, panel_rect, "[SIMULAÇÃO PQC]", t)

        y = panel_rect.y + 42
        x = panel_rect.x + 14
        cw = pw - 28  # content width

        # --- Sessao ---
        lbl = FONT_LABEL.render("SESSÃO", True, C_TEXT_DIM)
        surface.blit(lbl, (x, y))
        y += 16
        if "DEGRADADO" in self.session_status:
            session_color = C_ACCENT_RED
        elif "DETECTOU" in self.session_status:
            session_color = C_ACCENT_ORANGE
        elif self.session_status == "SIMULADO":
            session_color = C_ACCENT_CYAN
        else:
            session_color = C_ACCENT_GREEN
        val = FONT_BODY.render(self.session_status, True, session_color)
        surface.blit(val, (x, y))
        y += 28

        # --- Algoritmo ---
        lbl = FONT_LABEL.render("ALGORITMO", True, C_TEXT_DIM)
        surface.blit(lbl, (x, y))
        y += 16
        val = FONT_BODY.render(self.pqc_algorithm, True, C_ACCENT_PURPLE)
        surface.blit(val, (x, y))
        y += 28

        # --- Guardiao ativo ---
        lbl = FONT_LABEL.render("GUARDIÃO ATIVO", True, C_TEXT_DIM)
        surface.blit(lbl, (x, y))
        guard_color = C_ACCENT_GREEN if self.checksum_enabled else C_ACCENT_ORANGE
        guard_text = "CRC32 ON" if self.checksum_enabled else "NONE"
        val = FONT_BODY.render(guard_text, True, guard_color)
        surface.blit(val, (x + 142, y - 2))
        y += 22

        # --- Separador ---
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + cw, y), 1)
        y += 12

        # --- Secao falhas ---
        lbl = FONT_LABEL.render("INJEÇÃO DE FALHAS", True, C_ACCENT_ORANGE)
        surface.blit(lbl, (x, y))
        y += 20

        # 3 metricas lado a lado
        col_w = cw // 3
        for i, (label, value, color) in enumerate([
            ("INJ", str(self.fault_injections), C_ACCENT_ORANGE),
            ("DET", str(self.detected_errors), C_ACCENT_GREEN),
            ("SIL", str(self.silent_failures), C_ACCENT_RED if self.silent_failures > 0 else C_TEXT_DIM),
        ]):
            col_x = x + i * col_w
            l = FONT_LABEL.render(label, True, C_TEXT_DIM)
            surface.blit(l, (col_x, y))
            v = FONT_BODY.render(value, True, color)
            surface.blit(v, (col_x, y + 16))
        y += 44

        # --- Separador ---
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + cw, y), 1)
        y += 12

        # --- Barra de integridade ---
        lbl = FONT_LABEL.render("INTEGRIDADE OBSERVADA", True, C_ACCENT_GREEN)
        surface.blit(lbl, (x, y))
        y += 20

        total = max(1, self.fault_injections)
        integrity = 1.0 - (self.silent_failures / total)
        bar_w = cw - 55
        bar_h = 14

        pygame.draw.rect(surface, (30, 30, 50), (x, y, bar_w, bar_h), border_radius=4)
        fill_w = int(bar_w * integrity)
        bar_color = C_ACCENT_GREEN if integrity > 0.7 else (C_ACCENT_ORANGE if integrity > 0.4 else C_ACCENT_RED)
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (x, y, fill_w, bar_h), border_radius=4)
        pct = FONT_BODY.render(f"{integrity * 100:.0f}%", True, C_TEXT_PRIMARY)
        surface.blit(pct, (x + bar_w + 8, y - 2))
        y += 32

        # --- Separador ---
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + cw, y), 1)
        y += 12

        # --- Uptime ---
        lbl = FONT_LABEL.render("UPTIME", True, C_TEXT_DIM)
        surface.blit(lbl, (x, y))
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(self.uptime))
        val = FONT_BODY.render(uptime_str, True, C_TEXT_PRIMARY)
        surface.blit(val, (x + 80, y))
        y += 28

        # --- Orbita ---
        lbl = FONT_LABEL.render("ÓRBITA", True, C_TEXT_DIM)
        surface.blit(lbl, (x, y))
        if self.satellite_online():
            ang_str = f"{math.degrees(satellite.angle):.0f} graus"
            orbit_color = C_TEXT_PRIMARY
        else:
            ang_str = "travada"
            orbit_color = C_ACCENT_ORANGE
        val = FONT_BODY.render(ang_str, True, orbit_color)
        surface.blit(val, (x + 80, y))

        if self.serial_client is not None:
            y += 28
            pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + cw, y), 1)
            y += 12
            lbl = FONT_LABEL.render("SATÉLITE WISDOM", True, C_ACCENT_CYAN)
            surface.blit(lbl, (x, y))
            y += 18
            status_color = C_ACCENT_GREEN if self.serial_connected else C_ACCENT_ORANGE
            status = self.serial_status[:28]
            val = FONT_LABEL.render(status, True, status_color)
            surface.blit(val, (x, y))
            y += 20

            hardware_keys = (
                "profile",
                "cpu_mhz",
                "heap",
                "min_heap",
                "elapsed_us",
                "pqc_status",
                "kat",
                "result",
                "key_match",
                "key_confirmed",
                "tag_match",
                "scenario",
                "crypto",
                "checksum",
                "bytes_total",
                "tag_us",
                "verify_us",
                "crc_us",
                "keygen_avg_us",
                "encap_avg_us",
                "decap_avg_us",
                "radio",
            )
            for key in hardware_keys:
                if key in self.hardware_payload and y < panel_rect.bottom - 18:
                    line = f"{key}: {self.hardware_payload[key]}"
                    surface.blit(self._render_clipped(FONT_LABEL, line, C_TEXT_DIM, cw), (x, y))
                    y += 16

        y += 28
        if y < panel_rect.bottom - 88:
            self._draw_event_timeline(surface, x, y, cw, panel_rect)

    def _draw_event_timeline(self, surface, x, y, width, panel_rect):
        lbl = FONT_LABEL.render("TIMELINE", True, C_ACCENT_CYAN)
        surface.blit(lbl, (x, y))
        y += 16

        legend = (
            ("OK", C_ACCENT_GREEN),
            ("SIL", C_ACCENT_RED),
            ("DET", C_ACCENT_ORANGE),
            ("INV", C_TEXT_DIM),
        )
        lx = x
        for label, color in legend:
            pygame.draw.circle(surface, color, (lx + 4, y + 6), 4)
            text = FONT_LABEL.render(label, True, C_TEXT_DIM)
            surface.blit(text, (lx + 12, y))
            lx += max(46, text.get_width() + 24)
        y += 18

        if not self.experiment_events:
            empty = FONT_LABEL.render("sem eventos de campanha", True, C_TEXT_DIM)
            surface.blit(empty, (x, y))
            return

        plot_h = min(72, max(48, panel_rect.bottom - y - 66))
        layout = timeline_layout(self.experiment_events, x, y, width, plot_h)
        lanes = {"A NONE": y + 16, "B CRC32": y + max(34, plot_h - 14)}
        for label, lane_y in lanes.items():
            text = FONT_LABEL.render(label, True, C_TEXT_DIM)
            surface.blit(text, (x, lane_y - 7))
            pygame.draw.line(surface, C_PANEL_BORDER, (x + 48, lane_y), (x + width, lane_y), 1)

        for point in layout:
            event = point["event"]
            cx = point["x"]
            cy = point["y"]
            color = self._result_color(event.result)
            radius = 5 if event is self.last_fault_event else 4
            pygame.draw.circle(surface, color, (cx, cy), radius)
            if event is self.last_fault_event:
                pygame.draw.circle(surface, color, (cx, cy), radius + 4, 1)

        y += plot_h + 4
        last = self.last_fault_event
        if last is not None:
            detail = (
                f"#{last.trial_id} {last.result} "
                f"i={last.byte_index} m={last.bit_mask_hex} {last.guard}"
            )
            surface.blit(self._render_clipped(FONT_LABEL, detail, C_TEXT_PRIMARY, width), (x, y))
            y += 16
            crc = f"crc {last.crc_before}->{last.crc_after}"
            surface.blit(self._render_clipped(FONT_LABEL, crc, C_TEXT_DIM, width), (x, y))
            y += 16

        if y < panel_rect.bottom - 18:
            summary_data = event_summary(self.experiment_events)
            summary = (
                f"A/B total {summary_data['events']}  "
                f"SIL {summary_data['silent']}  DET {summary_data['detected_guard']}"
            )
            surface.blit(FONT_LABEL.render(summary, True, C_TEXT_DIM), (x, y))

    @staticmethod
    def _result_color(result):
        if result == "SILENT" or result == "KEY_MISMATCH":
            return C_ACCENT_RED
        if result in {"DETECTED_GUARD", "PROTOCOL_REJECT"}:
            return C_ACCENT_ORANGE
        if result == "OK":
            return C_ACCENT_GREEN
        return C_TEXT_DIM

    @staticmethod
    def _history_command_label(command):
        labels = {
            "SET_PRESET_CLASSIC": "PRESET CLASSIC",
            "SET_PRESET_PQC": "PRESET PQC",
            "SET_PRESET_PQC_CRC32": "PRESET PQC+CRC",
            "SEND_MESSAGE": "ENVIAR MSG",
        }
        return labels.get(command, command)

    def _draw_right_panel(self, surface, t):
        """Painel direito: Console de comandos."""
        pw = 380
        panel_rect = pygame.Rect(WIDTH - pw - 20, 55, pw, HEIGHT - 110)
        self._draw_panel_bg(surface, panel_rect, "[CONSOLE]", t)

        y = panel_rect.y + 42
        x = panel_rect.x + 14
        cw = pw - 28
        y = self._draw_command_buttons(surface, x, y, cw, t) + 10
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + cw, y), 1)
        y += 10

        # Espaco: do y atual ate o input (reservar 100px para hints + input)
        sep_y = panel_rect.y + panel_rect.height - 115
        available_h = max(80, sep_y - y - 4)

        if self.help_visible:
            help_lines = self._console_help_lines()
            log_line_h = 16
            help_font = FONT_SMALL if log_line_h < 18 else FONT_LABEL
            max_lines = max(1, available_h // log_line_h)
            max_scroll = max(0, len(help_lines) - max_lines)
            self.help_scroll = max(0, min(self.help_scroll, max_scroll))
            visible_lines = help_lines[self.help_scroll:self.help_scroll + max_lines]
            for line in visible_lines:
                color = C_ACCENT_CYAN if line.endswith(":") else C_TEXT_DIM
                if line.startswith("  "):
                    color = C_TEXT_PRIMARY
                text = self._render_clipped(help_font, line, color, cw)
                surface.blit(text, (x, y + 3))
                y += log_line_h
            if max_scroll > 0:
                scroll_text = f"{self.help_scroll + 1}-{self.help_scroll + len(visible_lines)}/{len(help_lines)}"
                surface.blit(
                    FONT_LABEL.render(scroll_text, True, C_ACCENT_ORANGE),
                    (x + cw - FONT_LABEL.size(scroll_text)[0], sep_y - 18),
                )
        else:
            log_line_h = 24
            max_lines = max(3, available_h // log_line_h)
            for entry in self.command_history[-max_lines:]:
                # Timestamp
                ts = FONT_LABEL.render(entry["time"], True, C_TEXT_DIM)
                surface.blit(ts, (x, y + 2))

                cmd_text = self._history_command_label(entry["cmd"])
                surface.blit(self._render_clipped(FONT_SMALL, cmd_text, C_TEXT_PRIMARY, 140), (x + 75, y))

                # Status com cor
                status = entry["status"]
                if "FAIL" in status or "SILENT" in status or "SILENCIOSO" in status:
                    s_color = C_ACCENT_RED
                elif "DETECT" in status or "OK" in status or "ONLINE" in status or "ENVIADO" in status or "us" in status or "ms" in status:
                    s_color = C_ACCENT_GREEN
                elif (
                    "DESCONHECIDO" in status
                    or "NÃO IMPLEMENTADO" in status
                    or "OFFLINE" in status
                    or "SERIAL OFF" in status
                ):
                    s_color = C_ACCENT_ORANGE
                else:
                    s_color = C_ACCENT_CYAN

                surface.blit(self._render_clipped(FONT_SMALL, status, s_color, max(70, cw - 225)), (x + 225, y))
                y += log_line_h

        # --- Separador antes do input ---
        pygame.draw.line(surface, C_PANEL_BORDER, (x, sep_y), (x + cw, sep_y), 1)

        # --- Hints ---
        hint_y = sep_y + 8
        if self.help_visible:
            hint_lines = (
                "Scroll para navegar no HELP completo.",
                "Digite comando ou HELP LED para bancada.",
                "Ctrl+Q encerra o dashboard.",
            )
        else:
            hint_lines = HELP_HINT_LINES

        h1 = FONT_LABEL.render(hint_lines[0], True, C_TEXT_DIM)
        surface.blit(h1, (x, hint_y))
        h2 = FONT_LABEL.render(hint_lines[1], True, C_TEXT_DIM)
        surface.blit(h2, (x, hint_y + 18))
        h3 = FONT_LABEL.render(hint_lines[2], True, C_TEXT_DIM)
        surface.blit(h3, (x, hint_y + 36))

        # --- Campo de input ---
        input_y = panel_rect.y + panel_rect.height - 48
        input_rect = pygame.Rect(x, input_y, cw, 34)

        input_bg = (25, 30, 55) if self.input_active else (18, 20, 40)
        pygame.draw.rect(surface, input_bg, input_rect, border_radius=5)
        brd = C_ACCENT_CYAN if self.input_active else C_PANEL_BORDER
        pygame.draw.rect(surface, brd, input_rect, 1, border_radius=5)

        # Prompt
        prompt = FONT_CMD.render("> ", True, C_ACCENT_CYAN)
        surface.blit(prompt, (x + 8, input_y + 8))

        # Texto digitado
        text_surf = FONT_CMD.render(self.input_text, True, C_TEXT_PRIMARY)
        surface.blit(text_surf, (x + 28, input_y + 8))

        # Cursor piscante
        if self.input_active and int(self.cursor_blink * 2) % 2 == 0:
            cx_cursor = x + 28 + text_surf.get_width() + 2
            pygame.draw.line(surface, C_ACCENT_CYAN, (cx_cursor, input_y + 6),
                             (cx_cursor, input_y + 26), 2)

    def _draw_command_buttons(self, surface, x, y, width, t):
        self.command_button_rects = []
        title = FONT_LABEL.render("COMANDOS DA DEMO", True, C_ACCENT_CYAN)
        surface.blit(title, (x, y))
        y += 20

        columns = 2 if width >= 260 else 1
        gap = 8
        button_h = 30
        button_w = (width - gap * (columns - 1)) // columns
        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)

        for index, (label, command) in enumerate(COMMAND_BUTTONS):
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

            pygame.draw.rect(surface, fill, rect, border_radius=5)
            pygame.draw.rect(surface, border, rect, 1, border_radius=5)

            label_surf = self._render_clipped(FONT_LABEL, label, C_TEXT_PRIMARY, button_w - 14)
            surface.blit(label_surf, (bx + 7, by + 8))
            self.command_button_rects.append((rect, command))

        rows = math.ceil(len(COMMAND_BUTTONS) / columns)
        return y + rows * button_h + max(0, rows - 1) * gap

    def _render_clipped(self, font, text, color, max_width):
        if font.size(text)[0] <= max_width:
            return font.render(text, True, color)

        suffix = "..."
        clipped = text
        while clipped and font.size(clipped + suffix)[0] > max_width:
            clipped = clipped[:-1]
        return font.render(clipped + suffix, True, color)

    def _wrap_text_for_width(self, font, text, max_width):
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

    def _console_help_lines(self):
        lines = [
            "Terminal avançado do dashboard:",
            "  Botões acima: comandos centrais da demo visual",
            "  Campo abaixo: comandos locais e firmware completos",
            "",
        ]
        lines.extend(command_help_lines(include_dashboard=True, demo_only=False))
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
        ordered_labels = ("payload", "ML-KEM", "HMAC", "CRC") if scenario in {"PQC", "PQC_CRC32"} else ("payload", "HMAC", "CRC")
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
        width = 380 if WIDTH >= 1600 else 340
        width = min(width, max(280, WIDTH - 40))
        height = min(354, max(326, HEIGHT - 120))
        return width, height

    def _mission_overlay_geometry(self, scenario=None):
        if scenario is None:
            scenario = self.mission_overlay_order[-1] if self.mission_overlay_order else "MISSION"
        width, height = self._mission_overlay_size()
        if scenario not in self.mission_overlay_positions:
            self.mission_overlay_positions[scenario] = self._default_mission_overlay_position(scenario)
        x, y = self.mission_overlay_positions[scenario]
        x, y = self._clamp_mission_overlay_position(x, y, width, height)
        self.mission_overlay_positions[scenario] = (x, y)
        rect = pygame.Rect(x, y, width, height)
        close_rect = pygame.Rect(rect.right - 36, rect.y + 9, 24, 24)
        return rect, close_rect

    def _default_mission_overlay_position(self, scenario):
        width, height = self._mission_overlay_size()
        gap = 10
        y = 116 + max(0, self._top_metrics_rows() - 1) * 54
        if self.demo_state != "IDLE":
            y += 104
        try:
            index = MISSION_OVERLAY_SCENARIOS.index(scenario)
        except ValueError:
            index = max(0, len(self.mission_overlay_order) - 1)
        total_width = len(MISSION_OVERLAY_SCENARIOS) * width + (len(MISSION_OVERLAY_SCENARIOS) - 1) * gap
        central_left = 340
        central_right = WIDTH - 420
        if total_width <= central_right - central_left:
            x = central_left + index * (width + gap)
        else:
            central_width = max(width, central_right - central_left)
            x = central_left + min(index * 34, max(0, central_width - width))
            y += index * 34
        return self._clamp_mission_overlay_position(x, y, width, height)

    @staticmethod
    def _clamp_mission_overlay_position(x, y, width, height):
        min_y = 50
        max_x = max(10, WIDTH - width - 10)
        max_y = max(min_y, HEIGHT - height - 44)
        return max(10, min(int(x), max_x)), max(min_y, min(int(y), max_y))

    def _mission_metric_value(self, mission, key, formatter=None):
        value = mission.get(key)
        if formatter:
            return formatter(value)
        if value is None or value == "":
            return "--"
        return str(value)

    def _draw_metric_pair(self, surface, label, value, x, y, width, color=C_TEXT_PRIMARY):
        surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, width), (x, y))
        surface.blit(self._render_clipped(FONT_SMALL, value, color, width), (x, y + 15))

    def _draw_overlay_metric_box(self, surface, label, value, x, y, width, height, color):
        pygame.draw.rect(surface, (15, 20, 38), (x, y, width, height), border_radius=4)
        pygame.draw.rect(surface, C_PANEL_BORDER, (x, y, width, height), width=1, border_radius=4)
        surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, width - 10), (x + 6, y + 5))
        surface.blit(self._render_clipped(FONT_SMALL, value, color, width - 10), (x + 6, y + 21))

    def _draw_mission_overlay(self, surface, t):
        if not self.mission_overlay_visible or not self.mission_overlays:
            self.mission_overlay_close_rect = None
            self.mission_comparison_rect = None
            self.mission_overlay_rects.clear()
            self.mission_overlay_close_rects.clear()
            self.mission_overlay_drag_rects.clear()
            self.mission_flow_control_rects.clear()
            return

        self.mission_overlay_rects.clear()
        self.mission_overlay_close_rects.clear()
        self.mission_overlay_drag_rects.clear()
        self.mission_flow_control_rects.clear()
        self.mission_overlay_order = [scenario for scenario in self.mission_overlay_order if scenario in self.mission_overlays]
        if len(self.mission_overlays) >= 2:
            self._draw_mission_comparison(surface, t)
        else:
            self.mission_comparison_rect = None
        for scenario in self.mission_overlay_order:
            self._draw_single_mission_overlay(surface, t, scenario, self.mission_overlays[scenario])
        self._sync_mission_overlay_state()

    def _mission_comparison_geometry(self):
        left = 340
        right = WIDTH - 420
        if right - left < 320:
            left = 20
            right = WIDTH - 20
        width = max(280, min(right - left, WIDTH - 40))
        x = max(20, min(left, WIDTH - width - 20))
        height = 166 if HEIGHT >= 760 else 146
        y = max(96, HEIGHT - height - 58)
        return pygame.Rect(x, y, width, height)

    @staticmethod
    def _mission_int(mission, key, default=0):
        parsed = _optional_int(mission.get(key))
        return default if parsed is None else parsed

    def _mission_package_parts(self, mission):
        scenario = self._normalize_mission_scenario(mission.get("scenario", "MISSION"))
        payload = self._mission_int(mission, "bytes_payload")
        crypto = self._mission_int(mission, "bytes_crypto")
        checksum = self._mission_int(mission, "bytes_checksum")
        hmac = min(32, crypto) if crypto else 0
        mlkem = max(0, crypto - hmac) if scenario in {"PQC", "PQC_CRC32"} else 0
        if scenario == "CLASSIC":
            hmac = crypto
            mlkem = 0
        return (
            ("payload", payload, C_ACCENT_BLUE),
            ("HMAC", hmac, C_ACCENT_ORANGE),
            ("ML-KEM", mlkem, C_ACCENT_PURPLE),
            ("CRC", checksum, C_ACCENT_GREEN),
        )

    def _mission_ratio_line(self, scenarios):
        classic = self.mission_overlays.get("CLASSIC")
        pqc = self.mission_overlays.get("PQC")
        pqc_crc = self.mission_overlays.get("PQC_CRC32")
        lines = []
        if classic and pqc:
            classic_us = self._mission_int(classic, "elapsed_us")
            pqc_us = self._mission_int(pqc, "elapsed_us")
            classic_b = self._mission_int(classic, "bytes_total")
            pqc_b = self._mission_int(pqc, "bytes_total")
            if classic_us and pqc_us:
                lines.append(f"PQC: {pqc_us / classic_us:.1f}x tempo")
            if classic_b and pqc_b:
                lines.append(f"{pqc_b / classic_b:.1f}x bytes vs CLASSIC")
        if pqc and pqc_crc:
            crc_b = self._mission_int(pqc_crc, "bytes_checksum")
            crc_us = self._mission_int(pqc_crc, "crc_us")
            if crc_b or crc_us:
                lines.append(f"CRC32: +{crc_b} B, {_format_elapsed(crc_us)}")
        if not lines and scenarios:
            lines.append("Compare tempo, bytes e composição do pacote.")
        return "  |  ".join(lines)

    def _draw_mission_comparison(self, surface, t):
        scenarios = [scenario for scenario in MISSION_OVERLAY_SCENARIOS if scenario in self.mission_overlays]
        if len(scenarios) < 2:
            self.mission_comparison_rect = None
            return

        rect = self._mission_comparison_geometry()
        self.mission_comparison_rect = rect
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, (*C_PANEL_BG, 228), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*C_ACCENT_CYAN, 150), (0, 0, rect.width, rect.height), 1, border_radius=8)
        pygame.draw.rect(panel, (*C_PANEL_HEADER, 190), (0, 0, rect.width, 34), border_top_left_radius=8, border_top_right_radius=8)
        surface.blit(panel, rect.topleft)

        title = "COMPARADOR AO VIVO: o que ficou mais caro?"
        surface.blit(self._render_clipped(FONT_SMALL, title, C_ACCENT_CYAN, rect.width - 28), (rect.x + 14, rect.y + 9))
        ratio_line = self._mission_ratio_line(scenarios)
        surface.blit(self._render_clipped(FONT_LABEL, ratio_line, C_ACCENT_ORANGE, rect.width - 28), (rect.x + 14, rect.y + 36))

        gap = 10
        content_x = rect.x + 14
        content_y = rect.y + 58
        content_w = rect.width - 28
        col_w = (content_w - gap * (len(scenarios) - 1)) // len(scenarios)
        bar_h = 12
        for index, scenario in enumerate(scenarios):
            mission = self.mission_overlays[scenario]
            x = content_x + index * (col_w + gap)
            y = content_y
            color = self._scenario_color(scenario)
            pygame.draw.rect(surface, (15, 20, 38), (x, y, col_w, rect.bottom - y - 14), border_radius=5)
            pygame.draw.rect(surface, color, (x, y, col_w, rect.bottom - y - 14), width=1, border_radius=5)
            surface.blit(self._render_clipped(FONT_LABEL, scenario, color, col_w - 12), (x + 7, y + 6))
            time_text = _format_elapsed(mission.get("elapsed_us"))
            bytes_text = f"{self._mission_metric_value(mission, 'bytes_total')} B"
            surface.blit(self._render_clipped(FONT_SMALL, f"{time_text}  |  {bytes_text}", C_TEXT_PRIMARY, col_w - 12), (x + 7, y + 22))

            parts = self._mission_package_parts(mission)
            total = max(1, sum(value for _label, value, _part_color in parts))
            bar_x = x + 7
            bar_y = y + 48
            bar_w = col_w - 14
            pygame.draw.rect(surface, (8, 12, 24), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
            cursor = bar_x
            for label, value, part_color in parts:
                if value <= 0:
                    continue
                part_w = max(2, int(bar_w * value / total))
                if cursor + part_w > bar_x + bar_w:
                    part_w = bar_x + bar_w - cursor
                pygame.draw.rect(surface, part_color, (cursor, bar_y, part_w, bar_h), border_radius=3)
                cursor += part_w
            pygame.draw.rect(surface, C_PANEL_BORDER, (bar_x, bar_y, bar_w, bar_h), width=1, border_radius=3)

            part_values = {label: value for label, value, _part_color in parts}
            line1 = f"pay {part_values.get('payload', 0)}B  hmac {part_values.get('HMAC', 0)}B"
            line2 = f"kem {part_values.get('ML-KEM', 0)}B  crc {part_values.get('CRC', 0)}B"
            surface.blit(self._render_clipped(FONT_LABEL, line1, C_TEXT_DIM, col_w - 12), (x + 7, y + 67))
            surface.blit(self._render_clipped(FONT_LABEL, line2, C_TEXT_DIM, col_w - 12), (x + 7, y + 81))

    def _draw_single_mission_overlay(self, surface, t, scenario, mission):
        rect, close_rect = self._mission_overlay_geometry(scenario)
        drag_rect = pygame.Rect(rect.x, rect.y, rect.width, 44)
        self.mission_overlay_rects[scenario] = rect
        self.mission_overlay_close_rects[scenario] = close_rect
        self.mission_overlay_drag_rects[scenario] = drag_rect

        result = str(mission.get("result", ""))
        crypto = str(mission.get("crypto", "--"))
        checksum = str(mission.get("checksum", "NONE"))
        elapsed = _format_elapsed(mission.get("elapsed_us"))
        bytes_total = self._mission_metric_value(mission, "bytes_total")
        scenario_color = {
            "CLASSIC": C_ACCENT_ORANGE,
            "PQC": C_ACCENT_CYAN,
            "PQC_CRC32": C_ACCENT_GREEN,
        }.get(scenario, C_ACCENT_CYAN)
        color = scenario_color if result in {"", "DELIVERED"} else C_ACCENT_RED

        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        alpha = int(150 + 45 * math.sin(t * 7)) if self.mission_effect_timer > 0 else 150
        pygame.draw.rect(panel, (*C_PANEL_BG, 225), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*color, max(120, alpha)), (0, 0, rect.width, rect.height), 1, border_radius=8)
        pygame.draw.rect(panel, (*color, 30), (0, 0, rect.width, 44), border_radius=8)
        pygame.draw.line(panel, (*C_PANEL_BORDER, 180), (0, 44), (rect.width, 44), 1)
        surface.blit(panel, rect.topleft)

        result_label = "OK" if result == "DELIVERED" else (result or "EM CURSO")
        title = f"{scenario}  |  {result_label}"
        surface.blit(self._render_clipped(FONT_SMALL, title, color, rect.width - 62), (rect.x + 14, rect.y + 12))
        pygame.draw.rect(surface, (58, 18, 28), close_rect, border_radius=5)
        pygame.draw.rect(surface, C_ACCENT_RED, close_rect, width=1, border_radius=5)
        x_text = FONT_SMALL.render("X", True, C_TEXT_PRIMARY)
        surface.blit(x_text, (close_rect.centerx - x_text.get_width() // 2, close_rect.centery - x_text.get_height() // 2))

        subtitle = f"{crypto}  |  CRC: {checksum}"
        surface.blit(self._render_clipped(FONT_LABEL, subtitle, C_TEXT_DIM, rect.width - 28), (rect.x + 14, rect.y + 48))

        if self._mission_overlay_is_animating(scenario):
            self._draw_mission_overlay_flow(surface, rect, scenario, mission, t)
            return

        self._draw_mission_overlay_metrics(surface, rect, mission, elapsed, bytes_total)

    def _mission_overlay_is_animating(self, scenario):
        return (
            self.mission_flow_animation is not None
            and self.mission_flow_animation.get("scenario") == scenario
        )

    def _draw_mission_overlay_flow(self, surface, rect, scenario, mission, t):
        animation = self.mission_flow_animation
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

        x = rect.x + 14
        y = rect.y + 72
        width = rect.width - 28

        paused = bool(animation.get("paused"))
        header = f"FLUXO REAL {active_index + 1}/{len(steps)}"
        control_rect = pygame.Rect(rect.right - 82, y - 2, 64, 22)
        self.mission_flow_control_rects[scenario] = control_rect
        surface.blit(self._render_clipped(FONT_LABEL, header, C_ACCENT_CYAN, width - 76), (x, y))
        button_label = "PLAY" if paused else "PAUSAR"
        button_border = C_ACCENT_ORANGE if paused else C_PANEL_BORDER
        pygame.draw.rect(surface, (16, 22, 42), control_rect, border_radius=4)
        pygame.draw.rect(surface, button_border, control_rect, width=1, border_radius=4)
        button_text = FONT_LABEL.render(button_label, True, C_ACCENT_ORANGE if paused else C_TEXT_DIM)
        surface.blit(
            button_text,
            (
                control_rect.centerx - button_text.get_width() // 2,
                control_rect.centery - button_text.get_height() // 2,
            ),
        )
        y += 18

        step_rect = pygame.Rect(x, y, width, 102)
        pygame.draw.rect(surface, (14, 20, 38), step_rect, border_radius=5)
        pygame.draw.rect(surface, color, step_rect, width=1, border_radius=5)

        packet_text = f"pacote {current_bytes}/{total_bytes} B"
        added = active_step.get("added_bytes", 0)
        if added:
            packet_text += f"  +{added} B"
        time_us = active_step.get("time_us")
        if time_us is not None:
            packet_text += f"  {_format_elapsed(time_us)}"

        title = f"{active_step['label']} - {active_step['detail']}"
        surface.blit(self._render_clipped(FONT_SMALL, title, color, width - 14), (step_rect.x + 7, step_rect.y + 7))
        surface.blit(self._render_clipped(FONT_LABEL, packet_text, C_TEXT_DIM, width - 14), (step_rect.x + 7, step_rect.y + 26))
        self._draw_wrapped_text(
            surface,
            FONT_LABEL,
            active_step.get("explain", ""),
            C_TEXT_PRIMARY,
            step_rect.x + 7,
            step_rect.y + 45,
            width - 14,
            line_spacing=14,
            max_lines=3,
        )

        timeline_y = step_rect.bottom + 24
        timeline_x = x + 10
        timeline_w = width - 20
        if len(steps) == 1:
            node_positions = [timeline_x + timeline_w // 2]
        else:
            node_positions = [
                timeline_x + int(round(index * timeline_w / (len(steps) - 1)))
                for index in range(len(steps))
            ]

        pygame.draw.line(surface, C_PANEL_BORDER, (node_positions[0], timeline_y), (node_positions[-1], timeline_y), 2)
        progress_ratio = min(
            1.0,
            max(0.0, animation.get("age", 0.0) / max(0.001, animation.get("duration", MISSION_FLOW_ANIMATION_SECONDS))),
        )
        packet_x = node_positions[0] + int((node_positions[-1] - node_positions[0]) * progress_ratio)
        pygame.draw.line(surface, self._scenario_color(scenario), (node_positions[0], timeline_y), (packet_x, timeline_y), 3)

        for index, step in enumerate(steps):
            node_x = node_positions[index]
            completed = index < active_index
            active = index == active_index
            node_color = step["color"] if active or completed else C_TEXT_DIM
            radius = 7 if active else 4
            pygame.draw.circle(surface, node_color, (node_x, timeline_y), radius)
            if active:
                pygame.draw.circle(surface, node_color, (node_x, timeline_y), radius + 6, 1)
            short_labels = {
                "PAYLOAD": "PAY",
                "KEYGEN": "KEY",
                "ENCAP": "ENC",
                "DECAP": "DEC",
                "HMAC": "MAC",
                "CRC32": "CRC",
                "VERIFICA": "VER",
                "RESULTADO": "OK",
            }
            label = self._render_clipped(
                FONT_LABEL,
                short_labels.get(step["label"], step["label"][:3]),
                node_color,
                max(28, timeline_w // len(steps)),
            )
            surface.blit(label, (node_x - label.get_width() // 2, timeline_y + 10))

        packet_rect = pygame.Rect(packet_x - 8, timeline_y - 8, 16, 16)
        pygame.draw.rect(surface, color, packet_rect, border_radius=4)
        pygame.draw.rect(surface, C_TEXT_PRIMARY, packet_rect, width=1, border_radius=4)

        bar_rect = pygame.Rect(rect.x, timeline_y + 34, rect.width, 68)
        self._draw_mission_flow_packet_bar(surface, bar_rect, mission, current_bytes, total_bytes)
        hint = "Final: métricas detalhadas."
        surface.blit(self._render_clipped(FONT_LABEL, hint, C_TEXT_DIM, width), (x, rect.bottom - 20))

    def _draw_mission_overlay_metrics(self, surface, rect, mission, elapsed, bytes_total):
        metric_x = rect.x + 14
        metric_y = rect.y + 70
        metric_gap = 8
        metric_w = (rect.width - 28 - metric_gap) // 2
        metric_h = 36
        metrics = (
            ("TEMPO", elapsed, C_ACCENT_CYAN),
            ("BYTES", f"{bytes_total} B" if bytes_total != "--" else "--", C_ACCENT_ORANGE),
            ("CPU", f"{self._mission_metric_value(mission, 'cpu_mhz')} MHz", C_TEXT_PRIMARY),
            ("HEAP", _format_bytes(mission.get("heap")), C_ACCENT_GREEN),
        )
        for index, (label, value, metric_color) in enumerate(metrics):
            x = metric_x + (index % 2) * (metric_w + metric_gap)
            y = metric_y + (index // 2) * (metric_h + 7)
            self._draw_overlay_metric_box(surface, label, value, x, y, metric_w, metric_h, metric_color)

        sep_y = metric_y + metric_h * 2 + 18
        pygame.draw.line(surface, C_PANEL_BORDER, (rect.x + 14, sep_y), (rect.right - 14, sep_y), 1)

        phase_y = sep_y + 10
        phases = (
            ("keygen", "keygen_us"),
            ("encap", "encap_us"),
            ("decap", "decap_us"),
            ("tag", "tag_us"),
            ("verify", "verify_us"),
            ("crc", "crc_us"),
        )
        phase_w = (rect.width - 28 - 2 * 8) // 3
        phase_h = 40
        for index, (label, key) in enumerate(phases):
            x = rect.x + 14 + (index % 3) * (phase_w + 8)
            y = phase_y + (index // 3) * (phase_h + 8)
            value = _format_elapsed(mission.get(key))
            phase_color = C_TEXT_DIM if value in {"--", "0 us"} else (C_ACCENT_GREEN if key == "crc_us" else C_TEXT_PRIMARY)
            pygame.draw.rect(surface, (15, 20, 38), (x, y, phase_w, phase_h), border_radius=4)
            pygame.draw.rect(surface, C_PANEL_BORDER, (x, y, phase_w, phase_h), width=1, border_radius=4)
            surface.blit(self._render_clipped(FONT_LABEL, label.upper(), C_TEXT_DIM, phase_w - 10), (x + 5, y + 5))
            surface.blit(self._render_clipped(FONT_SMALL, value, phase_color, phase_w - 10), (x + 5, y + 21))

        bytes_y = phase_y + phase_h * 2 + 20
        byte_line = (
            f"payload {self._mission_metric_value(mission, 'bytes_payload')}B   "
            f"crypto {self._mission_metric_value(mission, 'bytes_crypto')}B   "
            f"crc {self._mission_metric_value(mission, 'bytes_checksum')}B"
        )
        surface.blit(self._render_clipped(FONT_LABEL, byte_line, C_TEXT_PRIMARY, rect.width - 28), (rect.x + 14, bytes_y))

        validation_y = bytes_y + 20
        validation = (
            f"key={self._mission_metric_value(mission, 'key_match')}   "
            f"tag={self._mission_metric_value(mission, 'tag_match')}   "
            f"crc={self._mission_metric_value(mission, 'crc_match')}"
        )
        surface.blit(self._render_clipped(FONT_LABEL, validation, C_TEXT_DIM, rect.width - 28), (rect.x + 14, validation_y))


    def _draw_top_bar(self, surface, t):
        """Barra superior com titulo e status."""
        bar_h = 44
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 220), (0, 0, WIDTH, bar_h))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, bar_h - 1), (WIDTH, bar_h - 1), 1)
        surface.blit(bar_surf, (0, 0))

        # Titulo
        title = FONT_HEADER.render("PQC-SAT", True, C_ACCENT_CYAN)
        title_x = 25
        surface.blit(title, (title_x, 10))

        sub_text = "Mission Control  //  UFF Cibersegurança" if WIDTH >= 1200 else "Mission Control"
        subtitle = FONT_SMALL.render(sub_text, True, C_TEXT_DIM)
        surface.blit(subtitle, (title_x + title.get_width() + 15, 14))

        # Botao de Resultados no centro da barra superior
        btn_w, btn_h = (240, 26) if WIDTH >= 1500 else (156, 26)
        btn_x = (WIDTH - btn_w) // 2
        btn_y = (bar_h - btn_h) // 2
        self.top_results_btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

        try:
            mouse_pos = pygame.mouse.get_pos()
        except pygame.error:
            mouse_pos = (-1, -1)
        hovered = self.top_results_btn_rect.collidepoint(mouse_pos)

        fill_c = (28, 42, 82) if hovered else (18, 22, 50)
        border_c = C_ACCENT_GREEN if getattr(self, "results_overlay_visible", False) else (C_ACCENT_CYAN if hovered else C_PANEL_BORDER)
        pygame.draw.rect(surface, fill_c, self.top_results_btn_rect, border_radius=4)
        pygame.draw.rect(surface, border_c, self.top_results_btn_rect, width=1, border_radius=4)

        btn_label = "RESULTADOS CONSOLIDADOS" if WIDTH >= 1500 else "RESULTADOS"
        btn_txt = FONT_LABEL.render(btn_label, True, C_ACCENT_GREEN if getattr(self, "results_overlay_visible", False) else C_TEXT_PRIMARY)
        surface.blit(btn_txt, (btn_x + (btn_w - btn_txt.get_width()) // 2, btn_y + (btn_h - btn_txt.get_height()) // 2))

        # Lado direito: clock + link
        clock_text = FONT_SMALL.render(time.strftime("%H:%M:%S"), True, C_TEXT_DIM)
        surface.blit(clock_text, (WIDTH - 210, 14))

        conn_pulse = int(180 + 75 * math.sin(t * 3))
        if self.serial_client is None:
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
        pygame.draw.circle(surface, conn_color, (WIDTH - 110, 22), 5)
        conn_text = FONT_SMALL.render(conn_label, True, conn_text_color)
        surface.blit(conn_text, (WIDTH - 98, 14))

    def _draw_top_metrics(self, surface, t):
        """Faixa central de métricas sempre visíveis durante a animação."""
        left_edge = 340
        right_edge = WIDTH - 420
        width = right_edge - left_edge
        if width < 320:
            return

        tiles = self._metric_tiles()
        columns = max(1, min(len(tiles), 2))
        gap = 8
        tile_h = 52
        tile_w = (width - gap * (columns - 1)) // columns
        start_y = 56

        for index, (label, value, detail, color) in enumerate(tiles):
            row = index // columns
            col = index % columns
            x = left_edge + col * (tile_w + gap)
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

    def _metric_tiles(self):
        state = dict(self.hardware_state)
        state.update(self.hardware_payload)

        cpu = _optional_int(state.get("cpu_mhz"))
        computed_cpu_load = self._current_cpu_load_pct()
        payload_cpu_load = _optional_float(state.get("cpu_load_pct"))
        cpu_load = computed_cpu_load if self.cpu_active_window else (payload_cpu_load or 0.0)
        heap = _optional_int(state.get("heap"))

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
        state = dict(self.hardware_state)
        state.update(self.hardware_payload)
        if label == "CPU":
            computed_cpu_load = self._current_cpu_load_pct()
            payload_cpu_load = _optional_float(state.get("cpu_load_pct")) or 0.0
            cpu_load = computed_cpu_load if self.cpu_active_window else payload_cpu_load
            return cpu_load / 100.0
        if label == "RAM":
            heap = _optional_int(state.get("heap"))
            if heap is None:
                return 0.0
            total_ram = 327680
            return max(0, min(total_ram, total_ram - heap)) / total_ram
        return 0.0

    def _mission_tile_values(self, mission, *, fallback_value, fallback_detail, ready_color):
        if not mission:
            return fallback_value, fallback_detail, C_TEXT_DIM if fallback_value == "--" else ready_color
        elapsed = _format_elapsed(mission.get("elapsed_us"))
        bytes_total = mission.get("bytes_total")
        result = str(mission.get("result", ""))
        detail = f"{bytes_total}B {result}" if bytes_total is not None else result
        color = ready_color if result == "DELIVERED" else C_ACCENT_RED
        return elapsed, detail, color

    def _draw_bottom_bar(self, surface, t):
        """Barra inferior com informacoes de sistema."""
        bar_h = 32
        bar_y = HEIGHT - bar_h
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 200), (0, 0, WIDTH, bar_h))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, 0), (WIDTH, 0), 1)
        surface.blit(bar_surf, (0, bar_y))

        if self.serial_client is None:
            esp32_item = "SAT: SIMULADO"
        elif self.serial_connected:
            esp32_item = "SAT: CONECTADO"
        else:
            esp32_item = "SAT: AGUARDANDO"

        pqc_label = self.pqc_algorithm
        if len(pqc_label) > 28:
            pqc_label = pqc_label[:25] + "..."

        items = [
            f"FPS: {int(clock.get_fps())}",
            f"HOST RAM: {_format_bytes(_process_rss_bytes())}",
            esp32_item,
            f"PQC: {pqc_label}",
            f"GUARD: {self.guard_mode}",
            f"SEED: {SIMULATION_SEED}",
        ]
        ix = 25
        for item in items:
            color = C_ACCENT_CYAN if "SIMULADO" in item else C_TEXT_DIM
            if "CONECTADO" in item:
                color = C_ACCENT_GREEN
            elif "AGUARDANDO" in item:
                color = C_ACCENT_ORANGE
            elif "READY" in item:
                color = C_ACCENT_GREEN
            elif "PENDENTE" in item:
                color = C_ACCENT_ORANGE
            surf = FONT_LABEL.render(item, True, color)
            surface.blit(surf, (ix, bar_y + 8))
            ix += surf.get_width() + 30
            if ix < WIDTH - 100:
                pygame.draw.line(surface, C_PANEL_BORDER, (ix - 15, bar_y + 6), (ix - 15, bar_y + 24), 1)


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

    def wrap_text(self, font, text, max_width):
        words = text.split()
        if not words:
            return []
        lines = []
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def wrap_render(self, font, text, color, max_width):
        if font.size(text)[0] <= max_width:
            return font.render(text, True, color)
        clipped = text
        suffix = "..."
        while clipped and font.size(clipped + suffix)[0] > max_width:
            clipped = clipped[:-1]
        return font.render(clipped + suffix, True, color)

    def draw_wrapped_onboarding(self, surface, text, x, y, max_width, color, line_spacing=21, max_lines=None):
        lines = self.wrap_text(FONT_SMALL, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            surface.blit(self.wrap_render(FONT_SMALL, line, color, max_width), (x, y))
            y += line_spacing
        return y

    def draw_paragraphs(self, surface, paragraphs, x, y, max_width, line_spacing=26, paragraph_spacing=12):
        curr_y = y
        for para in paragraphs:
            wrapped = self.wrap_text(FONT_BODY, para, max_width)
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
        title = FONT_TITLE.render("1. O PROBLEMA: SEGURANÇA EM HARDWARE LIMITADO", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("Um computador pequeno precisa ser seguro, resistente e eficiente", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "A apresentação simula um OBC educacional inspirado em CubeSat: pouco processamento, pouca memória, comunicação por rádio e necessidade de operar de forma confiável.",
            "O desafio cresce porque o mundo está migrando para criptografia pós-quântica. Algoritmos modernos protegem melhor a troca de segredo, mas exigem mais tempo e tráfego.",
            "Além disso, ambientes espaciais podem sofrer falhas transientes. Um bit-flip pequeno pode alterar mensagem, estado interno ou material criptográfico.",
            "Nossa pergunta: quanto custa entregar a mesma mensagem com CLASSIC, PQC e PQC+CRC32, e o que ganhamos em consistência quando detectamos a corrupção?"
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
        title = FONT_TITLE.render("2. AMEAÇA QUÂNTICA E MIGRAÇÃO PARA PQC", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("O que muda quando computadores quânticos entram no modelo", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "RSA e ECDH dependem de problemas matemáticos difíceis para computadores comuns. Um computador quântico grande o suficiente poderia usar o algoritmo de Shor contra esses esquemas de chave pública.",
            "Isso não significa que todo mecanismo clássico morre: HMAC e criptografia simétrica continuam relevantes. O problema central do seminário é a troca/estabelecimento de segredo em hardware limitado.",
            "O risco prático é 'harvest now, decrypt later': capturar tráfego hoje para tentar quebrar no futuro. PQC existe para antecipar essa migração."
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

        t_header = FONT_HEADER.render("MUDANÇA DE AMEAÇA", True, C_ACCENT_ORANGE)
        surface.blit(t_header, (bx + int(box_w * 0.08), by + int(box_h * 0.08)))

        # Classico
        c_w = box_w - int(box_w * 0.16)
        c_h = int(box_h * 0.3)
        pygame.draw.rect(surface, (25, 20, 10), (bx + int(box_w * 0.08), by + int(box_h * 0.22), c_w, c_h), border_radius=4)
        c_title = FONT_SMALL.render("Computador clássico:", True, C_TEXT_PRIMARY)
        surface.blit(c_title, (bx + int(box_w * 0.11), by + int(box_h * 0.26)))
        c_val = FONT_HEADER.render("RSA/ECDH ainda práticos", True, C_ACCENT_GREEN)
        surface.blit(c_val, (bx + int(box_w * 0.11), by + int(box_h * 0.35)))

        # Quantico
        pygame.draw.rect(surface, (10, 25, 20), (bx + int(box_w * 0.08), by + int(box_h * 0.58), c_w, c_h), border_radius=4)
        q_title = FONT_SMALL.render("Quântico grande + Shor:", True, C_TEXT_PRIMARY)
        surface.blit(q_title, (bx + int(box_w * 0.11), by + int(box_h * 0.62)))
        q_val = FONT_HEADER.render("Chaves públicas em risco", True, C_ACCENT_ORANGE)
        surface.blit(q_val, (bx + int(box_w * 0.11), by + int(box_h * 0.71)))

    def draw_slide_2(self, surface):
        title = FONT_TITLE.render("3. ML-KEM & MECANISMO DE ACORDO DE CHAVE", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("A Solução Pós-Quântica baseada em Reticulados", True, C_TEXT_DIM)
        surface.blit(sub, (self.x + int(self.w * 0.04), self.y + 60))

        paragraphs = [
            "ML-KEM (FIPS 203) é um mecanismo pós-quântico baseado em reticulados e no problema Learning With Errors.",
            "Um KEM não cifra a mensagem diretamente: ele executa KEYGEN, ENCAP e DECAP para criar um segredo compartilhado usado depois pelo HMAC.",
            "Na Wisdom, o custo aparece no pacote e no tempo: chave pública de 800 B, ciphertext de 768 B e segredo de 32 B. O popup pausável mostra onde isso entra.",
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

        d_lbl = FONT_SMALL.render("DIAGRAMA DE TROCA DE CHAVES ML-KEM-512", True, C_ACCENT_CYAN)
        surface.blit(d_lbl, (bx + 20, by + 12))

        # Alice e Bob
        alice_x = bx + int(box_w * 0.04)
        bob_x = bx + box_w - int(box_w * 0.04) - 160

        pygame.draw.rect(surface, C_PANEL_HEADER, (alice_x, by + int(box_h * 0.28), 160, 36), border_radius=4)
        alice_t = FONT_SMALL.render("ESP32 (Wisdom)", True, C_TEXT_PRIMARY)
        surface.blit(alice_t, (alice_x + (160 - alice_t.get_width()) // 2, by + int(box_h * 0.28) + 10))

        pygame.draw.rect(surface, C_PANEL_HEADER, (bob_x, by + int(box_h * 0.28), 160, 36), border_radius=4)
        bob_t = FONT_SMALL.render("DASHBOARD", True, C_TEXT_PRIMARY)
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
        title = FONT_TITLE.render("4. O EXPERIMENTO: A MESMA MENSAGEM EM 3 CENÁRIOS", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("A comparação é didática: muda a proteção, medimos o impacto", True, C_TEXT_DIM)
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
                    "HMAC-SHA256 com chave simétrica.",
                    "Serve como baseline: o caminho barato.",
                    "Resultado real: 511 us, 73 bytes.",
                ],
            },
            {
                "title": "PQC",
                "color": C_ACCENT_ORANGE,
                "body": [
                    "ML-KEM-512 estabelece segredo.",
                    "Depois HMAC autentica a mensagem.",
                    "Resultado real: 13.234 us, 841 bytes.",
                ],
            },
            {
                "title": "PQC + CRC32",
                "color": C_ACCENT_GREEN,
                "body": [
                    "Mesmo fluxo PQC com checksum no payload.",
                    "Mostra detecção de corrupção por bit-flip.",
                    "Resultado real: 13.130 us, 845 bytes.",
                ],
            },
        ]

        for index, card in enumerate(cards):
            cx = content_x + index * (card_w + gap)
            rect = pygame.Rect(cx, content_y, card_w, card_h)
            pygame.draw.rect(surface, C_PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, card["color"], rect, width=2, border_radius=6)
            surface.blit(self.wrap_render(FONT_HEADER, card["title"], card["color"], card_w - 32), (cx + 16, content_y + 18))
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
        surface.blit(self.wrap_render(FONT_HEADER, "O QUE ESTAMOS MEDINDO", C_ACCENT_CYAN, mw), (mx, my))
        my += 38
        metric_lines = [
            "Tempo/CPU: custo para entregar a mensagem.",
            "Bytes: tráfego do protocolo e composição do pacote.",
            "Heap/RAM: margem restante na placa.",
            "Resultado: DELIVERED, SILENT, DETECTED_GUARD ou PROTOCOL_REJECT.",
        ]
        for line in metric_lines:
            my = self.draw_wrapped_onboarding(surface, f"- {line}", mx, my, mw, C_TEXT_PRIMARY, line_spacing=18, max_lines=1)

    def draw_slide_4(self, surface):
        title = FONT_TITLE.render("5. COMO LER A DEMONSTRAÇÃO AO VIVO", True, C_ACCENT_CYAN)
        surface.blit(title, (self.x + int(self.w * 0.04), self.y + 25))

        sub = FONT_BODY.render("O dashboard substitui os slides: ele mostra narrativa, execução e resultados", True, C_TEXT_DIM)
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
        surface.blit(self.wrap_render(FONT_HEADER, "ROTEIRO MANUAL", C_ACCENT_GREEN, lw), (lx, ly))
        ly += 38
        steps = [
            ("CLÁSSICA", "envia a mensagem com HMAC-SHA256."),
            ("PQC", "troca para ML-KEM-512 + HMAC."),
            ("PQC+CRC", "usa ML-KEM-512 e CRC32 no payload."),
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
        surface.blit(self.wrap_render(FONT_HEADER, "O QUE COMPARAR", C_ACCENT_ORANGE, rw), (rx, ry))
        ry += 38
        comparisons = [
            "CPU e RAM ficam sempre no topo.",
            "Popups pausáveis mostram pacote, bit-flip e verificações.",
            "CLASSIC é o baseline barato: 511 us e 73 bytes.",
            "PQC: 13.234 us e 841 bytes por causa do ML-KEM-512.",
            "PQC+CRC32: +4 bytes e detecção de corrupção no payload.",
            "RESULTADOS fecha com 3.074 registros, 0 falhas e conclusões.",
        ]
        for item in comparisons:
            ry = self.draw_wrapped_onboarding(surface, f"- {item}", rx, ry, rw, C_TEXT_PRIMARY, max_lines=2)
            ry += 4

        footer_y = content_y + box_h + 26
        footer_rect = pygame.Rect(content_x, footer_y, self.w - pad_x * 2, int(self.h * 0.14))
        pygame.draw.rect(surface, (14, 24, 38), footer_rect, border_radius=6)
        pygame.draw.rect(surface, C_PANEL_BORDER, footer_rect, width=1, border_radius=6)
        footer = (
            "Mensagem final: em hardware limitado, PQC funciona, mas custa mais tempo e tráfego. "
            "Checksum ajuda a tornar falhas visíveis, mas não substitui autenticação criptográfica."
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


# --- Loop Principal -----------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="PQC-SAT Mission Control Dashboard")
    parser.add_argument("--serial", action="store_true", help="conecta comandos do dashboard ao ESP32")
    parser.add_argument("--simulated", action="store_true", help="modo de desenvolvimento sem travar no hardware")
    parser.add_argument("--no-splash", action="store_true", help="pula a tela inicial curta")
    parser.add_argument("--port", help="porta serial, por exemplo /dev/ttyUSB0 ou COM3")
    parser.add_argument("--baud", type=int, default=115200, help="baudrate da serial")
    parser.add_argument("--serial-timeout", type=float, default=SERIAL_TIMEOUT_SECONDS, help="timeout serial em segundos")
    return parser.parse_args()


def main():
    args = parse_args()
    init_display()
    if not args.no_splash:
        mode_label = "MODO SIMULADO" if args.simulated else "PROCURANDO BLACKBOARD WISDOM"
        if not show_splash(mode_label):
            pygame.quit()
            return

    serial_client = None
    if args.serial or args.port or not args.simulated:
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

    if not args.no_splash:
        onboarding = Onboarding(stars, earth, satellite, nebula, dust, shooting_stars)
        if not onboarding.run(screen, clock):
            pygame.quit()
            return

    dashboard = DashboardPanel(serial_client=serial_client)
    running = True
    t = 0.0

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
                    else:
                        dashboard.handle_event(event)
                elif event.type != pygame.KEYDOWN:
                    dashboard.handle_event(event)

            # -- Atualizacao --
            if dashboard.satellite_online() or args.simulated:
                satellite.update(dt)
            dashboard.update(dt)
            dust.update(dt)
            shooting_stars.update(dt)

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
                satellite.draw(screen, t)
            else:
                dashboard.draw_satellite_lock(screen, t)
            dashboard.draw(screen, t, satellite)

            pygame.display.flip()
    finally:
        exc_type, _exc_value, _exc_tb = sys.exc_info()
        try:
            dashboard.close()
        except Exception as cleanup_exc:
            if exc_type is None:
                raise
            print(f"cleanup failed: {cleanup_exc}", file=sys.stderr)
        pygame.quit()


if __name__ == "__main__":
    main()
