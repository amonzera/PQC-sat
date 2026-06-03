#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  PQC-SAT Mission Control Dashboard                              ║
║  Criptografia Pós-Quântica · CubeSat · ESP32                    ║
║  Universidade Federal Fluminense — Cibersegurança               ║
╚══════════════════════════════════════════════════════════════════╝

Dashboard principal com visualização animada de um CubeSat em órbita
da Terra, contendo um robô pixel-art sorridente. Esqueleto preparado
para receber comandos de injeção de falha e controle de sessão PQC.
"""

import pygame
import math
import sys
import time
import random
import os

# ─── Inicialização ────────────────────────────────────────────────
pygame.init()

# Resolução e janela
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("PQC-SAT · Mission Control Dashboard")

clock = pygame.time.Clock()
FPS = 60

# ─── Paleta de Cores ─────────────────────────────────────────────
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
C_TEXT_GLOW       = (0, 180, 255)
C_EARTH_BLUE     = (30, 90, 180)
C_EARTH_GREEN    = (30, 140, 70)
C_EARTH_CLOUDS   = (200, 220, 255, 80)
C_SAT_BODY       = (70, 80, 100)
C_SAT_PANEL_BLUE = (40, 100, 200)
C_SAT_PANEL_DARK = (20, 50, 120)
C_SAT_GOLD       = (220, 190, 80)
C_ROBOT_FACE     = (180, 200, 230)
C_ROBOT_EYE      = (0, 200, 255)
C_ROBOT_SMILE    = (0, 255, 160)
C_ORBIT_LINE     = (40, 70, 140, 60)

# ─── Fontes ───────────────────────────────────────────────────────
def load_font(name, size):
    """Tenta carregar fonte do sistema, fallback para default."""
    try:
        return pygame.font.SysFont(name, size)
    except Exception:
        return pygame.font.Font(None, size)

FONT_TITLE   = load_font("monospace", 28)
FONT_HEADER  = load_font("monospace", 18)
FONT_BODY    = load_font("monospace", 14)
FONT_SMALL   = load_font("monospace", 12)
FONT_LARGE   = load_font("monospace", 40)
FONT_CMD     = load_font("monospace", 15)
FONT_PIXEL   = load_font("monospace", 10)

# ─── Estrelas de fundo ────────────────────────────────────────────
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


# ─── Terra ────────────────────────────────────────────────────────
class Earth:
    def __init__(self):
        self.radius = 160
        self.center_x = WIDTH // 2
        self.center_y = HEIGHT // 2 + 40
        self.surface_cache = None
        self._build_surface()

    def _build_surface(self):
        size = self.radius * 2 + 4
        self.surface_cache = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        r = self.radius

        # Gradiente atmosférico (glow externo)
        for i in range(30, 0, -1):
            alpha = int(3 * (30 - i))
            glow_color = (60, 140, 255, alpha)
            pygame.draw.circle(self.surface_cache, glow_color, (cx, cy), r + i)

        # Corpo da Terra
        pygame.draw.circle(self.surface_cache, C_EARTH_BLUE, (cx, cy), r)

        # Continentes estilizados (manchas verdes)
        continents = [
            (cx - 40, cy - 30, 35, 25),
            (cx + 20, cy - 50, 45, 30),
            (cx - 60, cy + 20, 30, 40),
            (cx + 30, cy + 30, 40, 25),
            (cx - 10, cy + 50, 25, 20),
            (cx + 50, cy - 10, 20, 35),
        ]
        for x, y, w, h in continents:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (*C_EARTH_GREEN, 180), (0, 0, w, h))
            self.surface_cache.blit(s, (x - w // 2, y - h // 2))

        # Nuvens semitransparentes
        clouds = [
            (cx - 50, cy - 60, 60, 15),
            (cx + 30, cy - 20, 70, 12),
            (cx - 30, cy + 40, 50, 10),
            (cx + 50, cy + 50, 40, 8),
        ]
        for x, y, w, h in clouds:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (200, 220, 255, 50), (0, 0, w, h))
            self.surface_cache.blit(s, (x - w // 2, y - h // 2))

        # Máscara circular (limpar fora do círculo)
        mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), r)
        # Aplicar máscara: somente o conteúdo DENTRO do círculo fica
        final = pygame.Surface((size, size), pygame.SRCALPHA)
        for px in range(size):
            for py in range(size):
                if (px - cx) ** 2 + (py - cy) ** 2 <= r * r:
                    final.set_at((px, py), self.surface_cache.get_at((px, py)))
                elif (px - cx) ** 2 + (py - cy) ** 2 <= (r + 30) ** 2:
                    # Glow externo
                    final.set_at((px, py), self.surface_cache.get_at((px, py)))
        self.surface_cache = final

    def draw(self, surface, t):
        # Desenha a terra com rotação simulada via offset de continentes
        blit_x = self.center_x - self.surface_cache.get_width() // 2
        blit_y = self.center_y - self.surface_cache.get_height() // 2
        surface.blit(self.surface_cache, (blit_x, blit_y))


# ─── Robô Pixel Art (dentro do satélite) ─────────────────────────
ROBOT_PIXELS = [
    # Formato: (col, row, color_key)
    # Grade 12x12 — robô sorridente
    # 'B' = body, 'E' = eye, 'S' = smile, 'A' = antenna, 'H' = head border
    # Row 0 — antena
    (5, 0, 'A'), (6, 0, 'A'),
    # Row 1 — antena base
    (4, 1, 'A'), (5, 1, 'H'), (6, 1, 'H'), (7, 1, 'A'),
    # Row 2 — topo cabeça
    (3, 2, 'H'), (4, 2, 'H'), (5, 2, 'B'), (6, 2, 'B'), (7, 2, 'H'), (8, 2, 'H'),
    # Row 3 — cabeça
    (2, 3, 'H'), (3, 3, 'B'), (4, 3, 'B'), (5, 3, 'B'), (6, 3, 'B'), (7, 3, 'B'), (8, 3, 'B'), (9, 3, 'H'),
    # Row 4 — olhos
    (2, 4, 'H'), (3, 4, 'B'), (4, 4, 'E'), (5, 4, 'B'), (6, 4, 'B'), (7, 4, 'E'), (8, 4, 'B'), (9, 4, 'H'),
    # Row 5 — entre olhos e boca
    (2, 5, 'H'), (3, 5, 'B'), (4, 5, 'B'), (5, 5, 'B'), (6, 5, 'B'), (7, 5, 'B'), (8, 5, 'B'), (9, 5, 'H'),
    # Row 6 — sorriso
    (2, 6, 'H'), (3, 6, 'B'), (4, 6, 'S'), (5, 6, 'B'), (6, 6, 'B'), (7, 6, 'S'), (8, 6, 'B'), (9, 6, 'H'),
    # Row 7 — sorriso base
    (2, 7, 'H'), (3, 7, 'B'), (4, 7, 'B'), (5, 7, 'S'), (6, 7, 'S'), (7, 7, 'B'), (8, 7, 'B'), (9, 7, 'H'),
    # Row 8 — queixo
    (3, 8, 'H'), (4, 8, 'H'), (5, 8, 'H'), (6, 8, 'H'), (7, 8, 'H'), (8, 8, 'H'),
    # Row 9 — pescoço / corpo
    (4, 9, 'H'), (5, 9, 'B'), (6, 9, 'B'), (7, 9, 'H'),
    # Row 10 — corpo
    (3, 10, 'H'), (4, 10, 'B'), (5, 10, 'B'), (6, 10, 'B'), (7, 10, 'B'), (8, 10, 'H'),
    # Row 11 — pernas
    (3, 11, 'H'), (4, 11, 'H'), (5, 11, 'H'), (6, 11, 'H'), (7, 11, 'H'), (8, 11, 'H'),
]

ROBOT_COLORS = {
    'B': C_ROBOT_FACE,
    'E': C_ROBOT_EYE,
    'S': C_ROBOT_SMILE,
    'A': C_SAT_GOLD,
    'H': (60, 70, 100),
}


def draw_robot_pixel(surface, cx, cy, pixel_size=3, t=0.0):
    """Desenha o robô sorridente em pixel art centralizado em (cx, cy)."""
    grid_w, grid_h = 12, 12
    offset_x = cx - (grid_w * pixel_size) // 2
    offset_y = cy - (grid_h * pixel_size) // 2

    for col, row, key in ROBOT_PIXELS:
        color = list(ROBOT_COLORS[key])
        # Efeito de brilho pulsante nos olhos
        if key == 'E':
            pulse = 0.7 + 0.3 * math.sin(t * 4)
            color = [int(c * pulse) for c in color]
        # Efeito de brilho no sorriso
        if key == 'S':
            pulse = 0.8 + 0.2 * math.sin(t * 3 + 1)
            color = [int(c * pulse) for c in color]
        px = offset_x + col * pixel_size
        py = offset_y + row * pixel_size
        pygame.draw.rect(surface, color, (px, py, pixel_size, pixel_size))


# ─── Satélite CubeSat ────────────────────────────────────────────
class Satellite:
    def __init__(self, earth):
        self.earth = earth
        self.orbit_radius = 260
        self.angle = 0.0
        self.orbit_speed = 0.3  # radianos por segundo
        self.body_size = 48  # tamanho do corpo do cubesat
        self.trail = []  # rastro orbital

    def update(self, dt):
        self.angle += self.orbit_speed * dt
        if self.angle > math.pi * 2:
            self.angle -= math.pi * 2

    def get_position(self):
        x = self.earth.center_x + self.orbit_radius * math.cos(self.angle)
        y = self.earth.center_y + self.orbit_radius * math.sin(self.angle) * 0.4  # órbita achatada
        return x, y

    def draw_orbit_line(self, surface):
        """Desenha a linha de órbita tracejada."""
        points = []
        for i in range(120):
            a = (i / 120) * math.pi * 2
            x = self.earth.center_x + self.orbit_radius * math.cos(a)
            y = self.earth.center_y + self.orbit_radius * math.sin(a) * 0.4
            points.append((x, y))

        for i in range(0, len(points) - 1, 2):
            alpha_val = 30 + int(20 * math.sin(i * 0.1 + pygame.time.get_ticks() * 0.002))
            color = (40, 70, 140, max(10, min(60, alpha_val)))
            s = pygame.Surface((abs(int(points[i+1][0] - points[i][0])) + 4,
                                abs(int(points[i+1][1] - points[i][1])) + 4), pygame.SRCALPHA)
            pygame.draw.line(surface, (*color[:3], 40),
                             (int(points[i][0]), int(points[i][1])),
                             (int(points[i+1][0]), int(points[i+1][1])), 1)

    def draw_trail(self, surface, t):
        """Desenha rastro luminoso atrás do satélite."""
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

        # Rotação simulada pelo ângulo orbital
        rot = math.sin(self.angle * 2) * 0.05

        # ── Painéis solares ──
        panel_w, panel_h = bs + 20, bs // 3
        # Painel esquerdo
        for i in range(3):
            shade = max(0, min(255, int(C_SAT_PANEL_BLUE[0] + 20 * math.sin(t * 2 + i))))
            color = (shade, C_SAT_PANEL_BLUE[1], C_SAT_PANEL_BLUE[2])
            rect_x = ix - bs // 2 - panel_w - 5
            rect_y = iy - panel_h // 2 + (i - 1) * 3
            pygame.draw.rect(surface, color, (rect_x, rect_y, panel_w, panel_h // 3 - 1))
        pygame.draw.rect(surface, C_SAT_PANEL_DARK,
                         (ix - bs // 2 - panel_w - 5, iy - panel_h // 2, panel_w, panel_h), 1)
        # Grid do painel esquerdo
        for gi in range(1, 4):
            gx = ix - bs // 2 - panel_w - 5 + (panel_w * gi) // 4
            pygame.draw.line(surface, C_SAT_PANEL_DARK,
                             (gx, iy - panel_h // 2), (gx, iy + panel_h // 2), 1)

        # Painel direito
        for i in range(3):
            shade = max(0, min(255, int(C_SAT_PANEL_BLUE[0] + 20 * math.sin(t * 2 + i + 1))))
            color = (shade, C_SAT_PANEL_BLUE[1], C_SAT_PANEL_BLUE[2])
            rect_x = ix + bs // 2 + 5
            rect_y = iy - panel_h // 2 + (i - 1) * 3
            pygame.draw.rect(surface, color, (rect_x, rect_y, panel_w, panel_h // 3 - 1))
        pygame.draw.rect(surface, C_SAT_PANEL_DARK,
                         (ix + bs // 2 + 5, iy - panel_h // 2, panel_w, panel_h), 1)
        for gi in range(1, 4):
            gx = ix + bs // 2 + 5 + (panel_w * gi) // 4
            pygame.draw.line(surface, C_SAT_PANEL_DARK,
                             (gx, iy - panel_h // 2), (gx, iy + panel_h // 2), 1)

        # Hastes de conexão
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix - bs // 2, iy), (ix - bs // 2 - 5, iy), 2)
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix + bs // 2, iy), (ix + bs // 2 + 5, iy), 2)

        # ── Corpo do CubeSat ──
        body_rect = pygame.Rect(ix - bs // 2, iy - bs // 2, bs, bs)

        # Glow ao redor do corpo
        glow_s = pygame.Surface((bs + 20, bs + 20), pygame.SRCALPHA)
        glow_alpha = int(40 + 20 * math.sin(t * 3))
        pygame.draw.rect(glow_s, (0, 180, 255, glow_alpha),
                         (0, 0, bs + 20, bs + 20), border_radius=6)
        surface.blit(glow_s, (ix - bs // 2 - 10, iy - bs // 2 - 10))

        # Corpo principal
        pygame.draw.rect(surface, C_SAT_BODY, body_rect, border_radius=4)
        pygame.draw.rect(surface, C_ACCENT_CYAN, body_rect, 1, border_radius=4)

        # ── Robô sorridente dentro do corpo ──
        draw_robot_pixel(surface, ix, iy, pixel_size=3, t=t)

        # ── Antena no topo ──
        ant_height = 14
        pygame.draw.line(surface, C_SAT_GOLD,
                         (ix, iy - bs // 2), (ix, iy - bs // 2 - ant_height), 2)
        # Bolinha piscante na ponta
        blink = int(200 + 55 * math.sin(t * 6))
        pygame.draw.circle(surface, (blink, 50, 50),
                           (ix, iy - bs // 2 - ant_height), 3)

        # ── Label do satélite ──
        label = FONT_PIXEL.render("PQC-SAT-01", True, C_ACCENT_CYAN)
        surface.blit(label, (ix - label.get_width() // 2, iy + bs // 2 + 6))


# ─── Painel de Interface / Dashboard ─────────────────────────────
class DashboardPanel:
    """Painel lateral com informações de telemetria e comandos."""

    def __init__(self):
        self.command_history = [
            {"time": "00:00:01", "cmd": "SYS_INIT", "status": "OK"},
            {"time": "00:00:02", "cmd": "PQC_KEYGEN ML-KEM-768", "status": "OK"},
            {"time": "00:00:03", "cmd": "ORBIT_CONFIRM", "status": "OK"},
            {"time": "00:00:05", "cmd": "TELEMETRY_START", "status": "ACTIVE"},
        ]
        self.input_text = ""
        self.input_active = False
        self.cursor_blink = 0
        self.session_status = "NOMINAL"
        self.pqc_algorithm = "ML-KEM-768"
        self.fault_injections = 0
        self.silent_failures = 0
        self.detected_errors = 0
        self.uptime = 0.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Verificar clique na área de input
            input_rect = pygame.Rect(20, HEIGHT - 55, 340, 30)
            self.input_active = input_rect.collidepoint(event.pos)

        if event.type == pygame.KEYDOWN and self.input_active:
            if event.key == pygame.K_RETURN:
                if self.input_text.strip():
                    self._execute_command(self.input_text.strip())
                    self.input_text = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.input_active = False
                self.input_text = ""
            else:
                if len(self.input_text) < 35 and event.unicode.isprintable():
                    self.input_text += event.unicode

    def _execute_command(self, cmd):
        """Processa um comando digitado."""
        cmd_upper = cmd.upper()
        t_str = time.strftime("%H:%M:%S")

        # Comandos reconhecidos
        known_commands = {
            "INJECT_FAULT": ("FAULT INJECTED", C_ACCENT_ORANGE),
            "PQC_STATUS": ("PQC NOMINAL", C_ACCENT_GREEN),
            "RESET_SESSION": ("SESSION RESET", C_ACCENT_CYAN),
            "TELEMETRY": ("STREAMING", C_ACCENT_GREEN),
            "HELP": ("CMD LIST SHOWN", C_ACCENT_CYAN),
            "BIT_FLIP": ("BIT-FLIP SIMULATED", C_ACCENT_RED),
            "CRC_CHECK": ("CRC OK", C_ACCENT_GREEN),
            "PING": ("PONG — 12ms", C_ACCENT_GREEN),
        }

        if cmd_upper in known_commands:
            status = known_commands[cmd_upper][0]
            if cmd_upper == "INJECT_FAULT":
                self.fault_injections += 1
                if random.random() < 0.4:
                    self.silent_failures += 1
                    status = "SILENT FAILURE!"
                else:
                    self.detected_errors += 1
                    status = "ERROR DETECTED"
            elif cmd_upper == "BIT_FLIP":
                self.fault_injections += 1
                if random.random() < 0.3:
                    self.silent_failures += 1
                    status = "CORRUPTION SILENCIOSA"
                else:
                    self.detected_errors += 1
        else:
            status = "UNKNOWN CMD"

        self.command_history.append({"time": t_str, "cmd": cmd_upper, "status": status})
        # Manter histórico limitado
        if len(self.command_history) > 12:
            self.command_history.pop(0)

    def update(self, dt):
        self.uptime += dt
        self.cursor_blink += dt

    def draw(self, surface, t, satellite):
        """Desenha todos os painéis da interface."""
        self._draw_left_panel(surface, t, satellite)
        self._draw_right_panel(surface, t)
        self._draw_top_bar(surface, t)
        self._draw_bottom_bar(surface, t)

    def _draw_panel_bg(self, surface, rect, title="", t=0.0):
        """Desenha fundo de painel com borda e header."""
        # Fundo semitransparente
        panel_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (*C_PANEL_BG, 200), (0, 0, rect.width, rect.height),
                         border_radius=6)
        pygame.draw.rect(panel_surf, (*C_PANEL_BORDER, 150), (0, 0, rect.width, rect.height),
                         1, border_radius=6)
        surface.blit(panel_surf, (rect.x, rect.y))

        if title:
            # Header bar
            header_rect = pygame.Rect(rect.x, rect.y, rect.width, 28)
            h_surf = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(h_surf, (*C_PANEL_HEADER, 220),
                             (0, 0, header_rect.width, header_rect.height),
                             border_top_left_radius=6, border_top_right_radius=6)
            surface.blit(h_surf, (header_rect.x, header_rect.y))

            # Indicador luminoso
            glow = int(180 + 75 * math.sin(t * 2))
            pygame.draw.circle(surface, (0, glow, int(glow * 0.8)),
                               (rect.x + 14, rect.y + 14), 4)

            title_surf = FONT_SMALL.render(title, True, C_ACCENT_CYAN)
            surface.blit(title_surf, (rect.x + 24, rect.y + 7))

    def _draw_left_panel(self, surface, t, satellite):
        """Painel esquerdo: Telemetria e status."""
        panel_rect = pygame.Rect(10, 50, 260, HEIGHT - 110)
        self._draw_panel_bg(surface, panel_rect, "◆ TELEMETRIA", t)

        y = panel_rect.y + 38
        x = panel_rect.x + 15

        # Status da sessão
        self._draw_metric(surface, x, y, "STATUS", self.session_status,
                          C_ACCENT_GREEN if self.session_status == "NOMINAL" else C_ACCENT_RED)
        y += 30

        self._draw_metric(surface, x, y, "ALGORITMO PQC", self.pqc_algorithm, C_ACCENT_PURPLE)
        y += 30

        # Posição orbital
        sat_x, sat_y = satellite.get_position()
        self._draw_metric(surface, x, y, "POS X", f"{sat_x:.1f}", C_TEXT_PRIMARY)
        y += 22
        self._draw_metric(surface, x, y, "POS Y", f"{sat_y:.1f}", C_TEXT_PRIMARY)
        y += 22
        self._draw_metric(surface, x, y, "ÂNGULO", f"{math.degrees(satellite.angle):.1f}°", C_TEXT_PRIMARY)
        y += 30

        # Separador
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + 220, y), 1)
        y += 12

        # Estatísticas de falha
        section_title = FONT_SMALL.render("── INJEÇÃO DE FALHAS ──", True, C_ACCENT_ORANGE)
        surface.blit(section_title, (x, y))
        y += 22

        self._draw_metric(surface, x, y, "INJEÇÕES", str(self.fault_injections), C_ACCENT_ORANGE)
        y += 22
        self._draw_metric(surface, x, y, "DETECTADOS", str(self.detected_errors), C_ACCENT_GREEN)
        y += 22
        self._draw_metric(surface, x, y, "SILENCIOSOS", str(self.silent_failures),
                          C_ACCENT_RED if self.silent_failures > 0 else C_TEXT_DIM)
        y += 30

        # Separador
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + 220, y), 1)
        y += 12

        # Barra de integridade visual
        section_title2 = FONT_SMALL.render("── INTEGRIDADE ──", True, C_ACCENT_GREEN)
        surface.blit(section_title2, (x, y))
        y += 22

        total = max(1, self.fault_injections)
        integrity = 1.0 - (self.silent_failures / total)
        bar_w = 220
        bar_h = 12

        # Fundo da barra
        pygame.draw.rect(surface, (30, 30, 50), (x, y, bar_w, bar_h), border_radius=3)

        # Barra de integridade
        fill_w = int(bar_w * integrity)
        bar_color = C_ACCENT_GREEN if integrity > 0.7 else (C_ACCENT_ORANGE if integrity > 0.4 else C_ACCENT_RED)
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (x, y, fill_w, bar_h), border_radius=3)

        # Porcentagem
        pct_text = FONT_SMALL.render(f"{integrity * 100:.0f}%", True, C_TEXT_PRIMARY)
        surface.blit(pct_text, (x + bar_w + 8, y - 1))
        y += 30

        # Uptime
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(self.uptime))
        self._draw_metric(surface, x, y, "UPTIME", uptime_str, C_TEXT_DIM)
        y += 30

        # Velocidade orbital visual
        speed_label = FONT_SMALL.render("VEL. ORBITAL", True, C_TEXT_DIM)
        surface.blit(speed_label, (x, y))
        # Gauge animada
        gauge_x = x
        gauge_y = y + 18
        gauge_w = 220
        gauge_h = 6
        pygame.draw.rect(surface, (30, 30, 50), (gauge_x, gauge_y, gauge_w, gauge_h), border_radius=2)
        # Indicador oscilante
        indicator_pos = int(gauge_w * (0.5 + 0.3 * math.sin(t * satellite.orbit_speed * 3)))
        pygame.draw.rect(surface, C_ACCENT_CYAN, (gauge_x + indicator_pos - 3, gauge_y - 2, 6, gauge_h + 4),
                         border_radius=2)

    def _draw_right_panel(self, surface, t):
        """Painel direito: Log de comandos e entrada."""
        panel_rect = pygame.Rect(WIDTH - 370, 50, 360, HEIGHT - 110)
        self._draw_panel_bg(surface, panel_rect, "◆ CONSOLE DE COMANDOS", t)

        y = panel_rect.y + 38
        x = panel_rect.x + 12

        # Log de comandos
        for entry in self.command_history[-10:]:
            # Timestamp
            time_surf = FONT_SMALL.render(entry["time"], True, C_TEXT_DIM)
            surface.blit(time_surf, (x, y))

            # Comando
            cmd_surf = FONT_SMALL.render(entry["cmd"][:18], True, C_TEXT_PRIMARY)
            surface.blit(cmd_surf, (x + 70, y))

            # Status com cor
            status = entry["status"]
            if "FAIL" in status or "CORRUP" in status:
                s_color = C_ACCENT_RED
            elif "DETECT" in status or "OK" in status or "NOMINAL" in status:
                s_color = C_ACCENT_GREEN
            elif "ACTIVE" in status or "STREAM" in status:
                s_color = C_ACCENT_CYAN
            else:
                s_color = C_ACCENT_ORANGE

            status_surf = FONT_SMALL.render(status[:16], True, s_color)
            surface.blit(status_surf, (x + 215, y))

            y += 20

        # Separador antes do input
        sep_y = panel_rect.y + panel_rect.height - 80
        pygame.draw.line(surface, C_PANEL_BORDER, (x, sep_y), (x + 330, sep_y), 1)

        # Comandos disponíveis (hint)
        hint_y = sep_y + 8
        hint_text = "CMDS: INJECT_FAULT | BIT_FLIP | PING | PQC_STATUS"
        hint_surf = FONT_SMALL.render(hint_text, True, C_TEXT_DIM)
        surface.blit(hint_surf, (x, hint_y))

        # Campo de input
        input_y = panel_rect.y + panel_rect.height - 45
        input_rect = pygame.Rect(x, input_y, 330, 30)

        # Fundo do input
        input_bg_color = (25, 30, 55) if self.input_active else (18, 20, 40)
        pygame.draw.rect(surface, input_bg_color, input_rect, border_radius=4)
        border_color = C_ACCENT_CYAN if self.input_active else C_PANEL_BORDER
        pygame.draw.rect(surface, border_color, input_rect, 1, border_radius=4)

        # Prompt
        prompt = FONT_CMD.render("❯ ", True, C_ACCENT_CYAN)
        surface.blit(prompt, (x + 6, input_y + 6))

        # Texto digitado
        text_surf = FONT_CMD.render(self.input_text, True, C_TEXT_PRIMARY)
        surface.blit(text_surf, (x + 24, input_y + 6))

        # Cursor piscante
        if self.input_active and int(self.cursor_blink * 2) % 2 == 0:
            cursor_x = x + 24 + text_surf.get_width() + 2
            pygame.draw.line(surface, C_ACCENT_CYAN, (cursor_x, input_y + 5),
                             (cursor_x, input_y + 24), 2)

    def _draw_top_bar(self, surface, t):
        """Barra superior com título e status global."""
        bar_surf = pygame.Surface((WIDTH, 42), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 220), (0, 0, WIDTH, 42))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, 41), (WIDTH, 41), 1)
        surface.blit(bar_surf, (0, 0))

        # Título principal
        title = FONT_HEADER.render("PQC-SAT", True, C_ACCENT_CYAN)
        surface.blit(title, (WIDTH // 2 - 200, 10))

        subtitle = FONT_SMALL.render("Mission Control Dashboard · UFF Cibersegurança", True, C_TEXT_DIM)
        surface.blit(subtitle, (WIDTH // 2 - 200 + title.get_width() + 15, 14))

        # Indicador de conexão
        conn_pulse = int(180 + 75 * math.sin(t * 3))
        pygame.draw.circle(surface, (0, conn_pulse, 0), (WIDTH - 120, 21), 5)
        conn_text = FONT_SMALL.render("LINK ATIVO", True, C_ACCENT_GREEN)
        surface.blit(conn_text, (WIDTH - 108, 14))

        # Clock
        clock_text = FONT_SMALL.render(time.strftime("%H:%M:%S"), True, C_TEXT_DIM)
        surface.blit(clock_text, (WIDTH - 240, 14))

    def _draw_bottom_bar(self, surface, t):
        """Barra inferior com informações secundárias."""
        bar_y = HEIGHT - 30
        bar_surf = pygame.Surface((WIDTH, 30), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 200), (0, 0, WIDTH, 30))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, 0), (WIDTH, 0), 1)
        surface.blit(bar_surf, (0, bar_y))

        # Info bottom
        items = [
            f"FPS: {int(clock.get_fps())}",
            f"ESP32: CONECTADO",
            f"PQC: ML-KEM-768",
            f"CRC: HABILITADO",
            f"SEED: 42",
        ]
        x = 20
        for item in items:
            color = C_TEXT_DIM
            if "CONECTADO" in item:
                color = C_ACCENT_GREEN
            surf = FONT_SMALL.render(item, True, color)
            surface.blit(surf, (x, bar_y + 8))
            x += surf.get_width() + 30

            # Separador
            if x < WIDTH - 100:
                pygame.draw.line(surface, C_PANEL_BORDER, (x - 15, bar_y + 6), (x - 15, bar_y + 22), 1)

    def _draw_metric(self, surface, x, y, label, value, value_color):
        """Desenha uma métrica label: value."""
        label_surf = FONT_SMALL.render(label, True, C_TEXT_DIM)
        value_surf = FONT_BODY.render(str(value), True, value_color)
        surface.blit(label_surf, (x, y))
        surface.blit(value_surf, (x + 130, y - 1))


# ─── Partículas de poeira cósmica ────────────────────────────────
class CosmicDust:
    def __init__(self, count=40):
        self.particles = []
        for _ in range(count):
            self.particles.append(self._new_particle())

    def _new_particle(self):
        return {
            'x': random.randint(0, WIDTH),
            'y': random.randint(0, HEIGHT),
            'vx': random.uniform(-0.3, 0.3),
            'vy': random.uniform(-0.2, 0.2),
            'life': random.uniform(2, 8),
            'max_life': random.uniform(2, 8),
            'size': random.uniform(0.5, 2),
            'color': random.choice([
                (100, 150, 255), (150, 100, 255), (200, 200, 255), (100, 255, 200)
            ]),
        }

    def update(self, dt):
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
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


# ─── Loop Principal ──────────────────────────────────────────────
def main():
    global WIDTH, HEIGHT, screen

    stars = StarField(350)
    earth = Earth()
    satellite = Satellite(earth)
    dashboard = DashboardPanel()
    dust = CosmicDust(50)

    running = True
    t = 0.0

    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        # ── Eventos ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                WIDTH, HEIGHT = event.w, event.h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    running = False
            dashboard.handle_event(event)

        # ── Atualização ──
        satellite.update(dt)
        dashboard.update(dt)
        dust.update(dt)

        # ── Desenho ──
        screen.fill(C_SPACE_BG)

        # Nebulosa de fundo sutil
        nebula_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(3):
            nx = WIDTH // 2 + int(150 * math.sin(t * 0.1 + i * 2))
            ny = HEIGHT // 2 + int(80 * math.cos(t * 0.08 + i * 1.5))
            ns = pygame.Surface((300, 300), pygame.SRCALPHA)
            pygame.draw.circle(ns, (30 + i * 15, 10, 50 + i * 20, 8), (150, 150), 150)
            nebula_surf.blit(ns, (nx - 150, ny - 150))
        screen.blit(nebula_surf, (0, 0))

        stars.draw(screen, t)
        dust.draw(screen)
        earth.draw(screen, t)
        satellite.draw(screen, t)
        dashboard.draw(screen, t, satellite)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
