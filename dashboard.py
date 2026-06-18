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
HELP_HINT_LINES = (
    "Botões: comandos visuais da demo.",
    "Terminal: HELP mostra comandos avançados.",
    "Ex.: MISSION PQC, PQC_KAT, HELP LED",
)
COMMAND_BUTTONS = (
    ("DEMO", "DEMO"),
    ("CLÁSSICA", "MISSION CLASSIC"),
    ("PQC", "MISSION PQC"),
    ("PQC+CRC", "MISSION PQC_CRC32"),
    ("STATUS", "STATUS"),
    ("FALHA", "INJECT_FAULT"),
    ("PAUSA", "DEMO_PAUSE"),
    ("EXPORT", "EXPORT_JSON"),
    ("OLED", "OLED STANDBY"),
)

# --- Paleta de Cores ----------------------------------------------------------
C_SPACE_BG       = (5, 5, 18)
C_PANEL_BG       = (12, 14, 30)
C_PANEL_BORDER   = (40, 60, 120)
C_PANEL_HEADER   = (18, 22, 50)
C_ACCENT_CYAN    = (0, 220, 255)
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
        self.pqc_algorithm = "ML-KEM-512 (PENDENTE)"
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
        self.checksum_enabled = False
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

    def _execute_mission_command(self, args):
        if len(args) != 1:
            return "INVALID_INPUT"
        scenario = args[0].upper().replace("+", "_")
        if scenario not in {"CLASSIC", "PQC", "PQC_CRC32"}:
            return "INVALID_INPUT"
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
            return self._set_checksum_enabled(True)
        if action in {"OFF", "NONE"}:
            return self._set_checksum_enabled(False)
        if action == "TOGGLE":
            return self._set_checksum_enabled(not self.checksum_enabled)
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
        elif command.startswith("TELEMETRY"):
            self.hardware_payload = payload
        elif command.startswith("STATUS"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
        elif command.startswith("PQC_"):
            self.hardware_payload = payload
            self._update_pqc_label(payload)
        elif command.startswith("MISSION"):
            self.hardware_payload = payload
            self.last_mission = dict(payload)
            self.mission_effect_timer = 5.0
            scenario = payload.get("scenario", "MISSION")
            result = payload.get("result", "")
            self.session_status = f"{scenario} {result}".strip()
        self._record_hardware_sample(command, payload)

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
        self._draw_bottom_bar(surface, t)

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

                # Comando (truncar para caber)
                cmd_text = entry["cmd"][:14]
                cs = FONT_SMALL.render(cmd_text, True, C_TEXT_PRIMARY)
                surface.blit(cs, (x + 80, y))

                # Status com cor
                status = entry["status"]
                if "FAIL" in status or "SILENT" in status or "SILENCIOSO" in status:
                    s_color = C_ACCENT_RED
                elif "DETECT" in status or "OK" in status or "ONLINE" in status:
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

                ss = FONT_SMALL.render(status[:14], True, s_color)
                surface.blit(ss, (x + 240, y))
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

    def _top_metrics_rows(self):
        left_edge = 340
        right_edge = WIDTH - 420
        width = right_edge - left_edge
        if width < 320:
            return 0
        columns = 5 if width >= 1100 else 3 if width >= 620 else 2
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

    def _draw_mission_overlay(self, surface, t):
        if self.mission_effect_timer <= 0 or not self.last_mission:
            return

        center_x = WIDTH // 2
        y = 154 + max(0, self._top_metrics_rows() - 1) * 50
        if self.demo_state != "IDLE":
            y += 132
        width = min(560, max(360, WIDTH - 760))
        rect = pygame.Rect(center_x - width // 2, y, width, 126)
        scenario = str(self.last_mission.get("scenario", "MISSION"))
        result = str(self.last_mission.get("result", ""))
        crypto = str(self.last_mission.get("crypto", "--"))
        checksum = str(self.last_mission.get("checksum", "NONE"))
        elapsed = _format_elapsed(self.last_mission.get("elapsed_us"))
        bytes_total = self.last_mission.get("bytes_total", "--")
        tag_match = self.last_mission.get("tag_match", "--")
        color = C_ACCENT_GREEN if result == "DELIVERED" else C_ACCENT_RED

        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        alpha = int(180 + 35 * math.sin(t * 7))
        pygame.draw.rect(panel, (*C_PANEL_BG, 225), (0, 0, rect.width, rect.height), border_radius=8)
        pygame.draw.rect(panel, (*color, max(120, alpha)), (0, 0, rect.width, rect.height), 1, border_radius=8)
        surface.blit(panel, rect.topleft)

        title = f"MENSAGEM {result or 'EM CURSO'}"
        surface.blit(self._render_clipped(FONT_BODY, title, color, rect.width - 28), (rect.x + 14, rect.y + 12))
        lines = [
            f"Cenário: {scenario}",
            f"Crypto: {crypto}   Checksum: {checksum}",
            f"Tempo: {elapsed}   Tráfego: {bytes_total}B",
            f"Tag/recebimento: {'OK' if str(tag_match) == '1' else tag_match}",
        ]
        for idx, line in enumerate(lines):
            line_color = C_TEXT_PRIMARY if idx < 3 else C_TEXT_DIM
            surface.blit(self._render_clipped(FONT_LABEL, line, line_color, rect.width - 28), (rect.x + 14, rect.y + 42 + idx * 17))

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

        subtitle = FONT_SMALL.render("Mission Control  //  UFF Cibersegurança", True, C_TEXT_DIM)
        surface.blit(subtitle, (title_x + title.get_width() + 15, 14))

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
        columns = 5 if width >= 1100 else 3 if width >= 620 else 2
        gap = 8
        tile_h = 42
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
            value_surf = self._render_clipped(FONT_SMALL, value, color, tile_w - 16)
            surface.blit(value_surf, (x + 8, y + 20))
            if detail:
                detail_surf = self._render_clipped(FONT_LABEL, detail, C_TEXT_DIM, tile_w - 16)
                surface.blit(detail_surf, (x + 74, y + 5))

    def _metric_tiles(self):
        state = dict(self.hardware_state)
        state.update(self.hardware_payload)

        cpu = _optional_int(state.get("cpu_mhz"))
        computed_cpu_load = self._current_cpu_load_pct()
        payload_cpu_load = _optional_float(state.get("cpu_load_pct"))
        cpu_load = computed_cpu_load if self.cpu_active_window else (payload_cpu_load or 0.0)
        heap = _optional_int(state.get("heap"))
        min_heap = _optional_int(state.get("min_heap"))

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

        ram_detail = f"min {_format_bytes(min_heap)}" if min_heap is not None else ""
        pqc_summary = self._pqc_metrics_summary()
        bench = pqc_summary.get("bench", {})
        mission_summary = self._mission_metrics_summary()
        scenarios = mission_summary.get("scenarios", {})
        classic_value, classic_detail, classic_color = self._mission_tile_values(
            scenarios.get("CLASSIC"),
            fallback_value="--",
            fallback_detail="HMAC",
            ready_color=C_ACCENT_GREEN,
        )
        pqc_value, pqc_detail, pqc_color = self._mission_tile_values(
            scenarios.get("PQC"),
            fallback_value=f"K {_format_elapsed(bench.get('keygen_avg_us'))}" if bench.get("keygen_avg_us") is not None else "--",
            fallback_detail="ML-KEM" if bench.get("keygen_avg_us") is None else f"E {_format_elapsed(bench.get('encap_avg_us'))}",
            ready_color=C_ACCENT_PURPLE,
        )
        pqc_crc_value, pqc_crc_detail, pqc_crc_color = self._mission_tile_values(
            scenarios.get("PQC_CRC32"),
            fallback_value="--",
            fallback_detail="ML-KEM+CRC",
            ready_color=C_ACCENT_ORANGE,
        )

        return (
            ("CPU", cpu_value, str(profile), cpu_color),
            ("RAM", f"{_format_bytes(heap)} livre", ram_detail, C_ACCENT_GREEN if heap else C_ACCENT_ORANGE),
            ("CLÁSSICA", classic_value, classic_detail, classic_color),
            ("PQC", pqc_value, pqc_detail, pqc_color),
            ("PQC+CRC", pqc_crc_value, pqc_crc_detail, pqc_crc_color),
        )

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
    dashboard = DashboardPanel(serial_client=serial_client)
    nebula = Nebula()
    dust = CosmicDust(50)
    shooting_stars = ShootingStars()

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
