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

# Resolução e janela (fullscreen)
info = pygame.display.Info()
WIDTH, HEIGHT = info.current_w, info.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF)
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

FONT_TITLE   = load_font("monospace", 34)
FONT_HEADER  = load_font("monospace", 24)
FONT_BODY    = load_font("monospace", 18)
FONT_SMALL   = load_font("monospace", 16)
FONT_LARGE   = load_font("monospace", 46)
FONT_CMD     = load_font("monospace", 19)
FONT_PIXEL   = load_font("monospace", 13)

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
        self.radius = 140
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

        # Glow atmosférico externo
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(self.surface_cache, (50, 130, 255, min(alpha, 120)), (cx, cy), r + i)

        # Corpo base — oceano azul SÓLIDO e opaco
        pygame.draw.circle(self.surface_cache, (25, 100, 200, 255), (cx, cy), r)

        # Segundo passe oceânico para profundidade (totalmente opaco)
        pygame.draw.circle(self.surface_cache, (30, 90, 185, 255), (cx, cy), r - 2)

        # ── Continente das Américas — GRANDE, preenche quase toda a face ──
        land_color = (50, 170, 75)  # verde vibrante

        # América do Norte — massa enorme
        s_na = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        scale = r / 140  # escalar proporcionalmente ao raio
        points_na = [
            (int(cx - 15 * scale), int(cy - 120 * scale)),   # topo centro
            (int(cx + 50 * scale), int(cy - 110 * scale)),   # topo direito
            (int(cx + 80 * scale), int(cy - 85 * scale)),    # canto NE
            (int(cx + 90 * scale), int(cy - 50 * scale)),    # leste superior
            (int(cx + 70 * scale), int(cy - 20 * scale)),    # leste
            (int(cx + 40 * scale), int(cy - 5 * scale)),     # golfo
            (int(cx + 20 * scale), int(cy + 5 * scale)),     # america central topo
            (int(cx + 5 * scale), int(cy - 10 * scale)),     # recuo golfo
            (int(cx - 30 * scale), int(cy - 15 * scale)),    # costa oeste baixo
            (int(cx - 60 * scale), int(cy - 40 * scale)),    # costa oeste
            (int(cx - 80 * scale), int(cy - 70 * scale)),    # canto NW
            (int(cx - 70 * scale), int(cy - 100 * scale)),   # alaska
            (int(cx - 40 * scale), int(cy - 115 * scale)),   # topo esquerdo
        ]
        pygame.draw.polygon(self.surface_cache, (*land_color, 255), points_na)
        # Textura interna
        pygame.draw.polygon(self.surface_cache, (60, 185, 85, 80), points_na)
        # Borda costeira
        pygame.draw.polygon(self.surface_cache, (35, 130, 55, 180), points_na, 2)

        # América Central — istmo conectando
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

        # América do Sul — massa grande
        points_sa = [
            (int(cx + 15 * scale), int(cy + 40 * scale)),    # topo
            (int(cx + 55 * scale), int(cy + 45 * scale)),    # NE
            (int(cx + 75 * scale), int(cy + 55 * scale)),    # leste alto
            (int(cx + 80 * scale), int(cy + 75 * scale)),    # leste
            (int(cx + 60 * scale), int(cy + 100 * scale)),   # SE
            (int(cx + 30 * scale), int(cy + 115 * scale)),   # sul
            (int(cx + 5 * scale), int(cy + 110 * scale)),    # ponta sul
            (int(cx - 15 * scale), int(cy + 90 * scale)),    # SW
            (int(cx - 25 * scale), int(cy + 65 * scale)),    # costa oeste
            (int(cx - 10 * scale), int(cy + 48 * scale)),    # NW
        ]
        pygame.draw.polygon(self.surface_cache, (45, 160, 70, 255), points_sa)
        # Textura interna — Amazônia mais escura
        amazon = [
            (int(cx + 20 * scale), int(cy + 55 * scale)),
            (int(cx + 55 * scale), int(cy + 60 * scale)),
            (int(cx + 50 * scale), int(cy + 80 * scale)),
            (int(cx + 15 * scale), int(cy + 75 * scale)),
        ]
        pygame.draw.polygon(self.surface_cache, (35, 140, 55, 120), amazon)
        # Borda costeira
        pygame.draw.polygon(self.surface_cache, (30, 120, 50, 180), points_sa, 2)

        # Groenlândia
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

        # Iluminação solar — highlight especular
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

        # Máscara circular — manter só o planeta + glow
        clean = pygame.Surface((size, size), pygame.SRCALPHA)
        # Glow externo
        for i in range(40, 0, -1):
            alpha = int(4.5 * (40 - i))
            pygame.draw.circle(clean, (50, 130, 255, min(alpha, 120)), (cx, cy), r + i)
        # Corpo mascarado — copiar pixels dentro do raio
        for y_pos in range(size):
            for x_pos in range(size):
                dist_sq = (x_pos - cx) ** 2 + (y_pos - cy) ** 2
                if dist_sq <= r * r:
                    clean.set_at((x_pos, y_pos), self.surface_cache.get_at((x_pos, y_pos)))
        self.surface_cache = clean

        # Borda atmosférica
        pygame.draw.circle(self.surface_cache, (80, 160, 255, 50), (cx, cy), r, 2)

    def draw(self, surface, t):
        blit_x = self.center_x - self.surface_cache.get_width() // 2
        blit_y = self.center_y - self.surface_cache.get_height() // 2
        surface.blit(self.surface_cache, (blit_x, blit_y))


# ─── Robô Pixel Art (dentro do satélite) ─────────────────────────
ROBOT_PIXELS = [
    # Formato: (col, row, color_key)
    # Grade 10x8 — rosto do robô sorridente (sem corpo)
    # 'B' = face fill, 'E' = eye, 'S' = smile, 'A' = antenna, 'H' = head border
    # Row 0 — antenas
    (3, 0, 'A'), (4, 0, 'A'), (7, 0, 'A'), (8, 0, 'A'),
    # Row 1 — topo cabeça
    (2, 1, 'H'), (3, 1, 'H'), (4, 1, 'H'), (5, 1, 'H'), (6, 1, 'H'), (7, 1, 'H'), (8, 1, 'H'), (9, 1, 'H'),
    # Row 2 — cabeça superior
    (1, 2, 'H'), (2, 2, 'B'), (3, 2, 'B'), (4, 2, 'B'), (5, 2, 'B'), (6, 2, 'B'), (7, 2, 'B'), (8, 2, 'B'), (9, 2, 'B'), (10, 2, 'H'),
    # Row 3 — olhos
    (1, 3, 'H'), (2, 3, 'B'), (3, 3, 'E'), (4, 3, 'E'), (5, 3, 'B'), (6, 3, 'B'), (7, 3, 'E'), (8, 3, 'E'), (9, 3, 'B'), (10, 3, 'H'),
    # Row 4 — entre olhos e boca
    (1, 4, 'H'), (2, 4, 'B'), (3, 4, 'B'), (4, 4, 'B'), (5, 4, 'B'), (6, 4, 'B'), (7, 4, 'B'), (8, 4, 'B'), (9, 4, 'B'), (10, 4, 'H'),
    # Row 5 — sorriso
    (1, 5, 'H'), (2, 5, 'B'), (3, 5, 'S'), (4, 5, 'B'), (5, 5, 'B'), (6, 5, 'B'), (7, 5, 'B'), (8, 5, 'S'), (9, 5, 'B'), (10, 5, 'H'),
    # Row 6 — sorriso inferior
    (1, 6, 'H'), (2, 6, 'B'), (3, 6, 'B'), (4, 6, 'S'), (5, 6, 'S'), (6, 6, 'S'), (7, 6, 'S'), (8, 6, 'B'), (9, 6, 'B'), (10, 6, 'H'),
    # Row 7 — queixo
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
    """Desenha o robô sorridente em pixel art centralizado em (cx, cy)."""
    grid_w, grid_h = 12, 8
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
        self.orbit_radius = 340
        self.angle = 0.0
        self.orbit_speed = 0.3  # radianos por segundo
        self.body_size = 76  # tamanho do corpo do cubesat
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
        draw_robot_pixel(surface, ix, iy, pixel_size=5, t=t)

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
            header_rect = pygame.Rect(rect.x, rect.y, rect.width, 36)
            h_surf = pygame.Surface((header_rect.width, header_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(h_surf, (*C_PANEL_HEADER, 220),
                             (0, 0, header_rect.width, header_rect.height),
                             border_top_left_radius=6, border_top_right_radius=6)
            surface.blit(h_surf, (header_rect.x, header_rect.y))

            # Indicador luminoso
            glow = int(180 + 75 * math.sin(t * 2))
            pygame.draw.circle(surface, (0, glow, int(glow * 0.8)),
                               (rect.x + 16, rect.y + 18), 5)

            title_surf = FONT_SMALL.render(title, True, C_ACCENT_CYAN)
            surface.blit(title_surf, (rect.x + 28, rect.y + 9))

    def _draw_left_panel(self, surface, t, satellite):
        """Painel esquerdo: Telemetria e status."""
        panel_rect = pygame.Rect(25, 55, 320, HEIGHT - 120)
        self._draw_panel_bg(surface, panel_rect, "◆ TELEMETRIA", t)

        y = panel_rect.y + 46
        x = panel_rect.x + 18
        content_w = panel_rect.width - 36

        # Status da sessão
        self._draw_metric_stacked(surface, x, y, "STATUS", self.session_status,
                                  C_ACCENT_GREEN if self.session_status == "NOMINAL" else C_ACCENT_RED)
        y += 42

        self._draw_metric_stacked(surface, x, y, "ALGORITMO PQC", self.pqc_algorithm, C_ACCENT_PURPLE)
        y += 42

        # Posição orbital (lado a lado, labels curtos)
        half_w = content_w // 2
        sat_x, sat_y = satellite.get_position()
        self._draw_metric_inline(surface, x, y, "X", f"{sat_x:.0f}", C_TEXT_PRIMARY)
        self._draw_metric_inline(surface, x + half_w, y, "Y", f"{sat_y:.0f}", C_TEXT_PRIMARY)
        y += 28
        self._draw_metric_inline(surface, x, y, "ÂNG", f"{math.degrees(satellite.angle):.1f}°", C_TEXT_PRIMARY)
        y += 34

        # Separador
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + content_w, y), 1)
        y += 12

        # Estatísticas de falha
        section_title = FONT_SMALL.render("── FALHAS ──", True, C_ACCENT_ORANGE)
        surface.blit(section_title, (x, y))
        y += 26

        self._draw_metric_inline(surface, x, y, "INJ", str(self.fault_injections), C_ACCENT_ORANGE)
        self._draw_metric_inline(surface, x + content_w // 3, y, "DET", str(self.detected_errors), C_ACCENT_GREEN)
        self._draw_metric_inline(surface, x + 2 * content_w // 3, y, "SIL", str(self.silent_failures),
                                 C_ACCENT_RED if self.silent_failures > 0 else C_TEXT_DIM)
        y += 34

        # Separador
        pygame.draw.line(surface, C_PANEL_BORDER, (x, y), (x + content_w, y), 1)
        y += 12

        # Barra de integridade visual
        section_title2 = FONT_SMALL.render("── INTEGRIDADE ──", True, C_ACCENT_GREEN)
        surface.blit(section_title2, (x, y))
        y += 26

        total = max(1, self.fault_injections)
        integrity = 1.0 - (self.silent_failures / total)
        bar_w = content_w - 60
        bar_h = 16

        # Fundo da barra
        pygame.draw.rect(surface, (30, 30, 50), (x, y, bar_w, bar_h), border_radius=4)

        # Barra de integridade
        fill_w = int(bar_w * integrity)
        bar_color = C_ACCENT_GREEN if integrity > 0.7 else (C_ACCENT_ORANGE if integrity > 0.4 else C_ACCENT_RED)
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (x, y, fill_w, bar_h), border_radius=4)

        # Porcentagem
        pct_text = FONT_BODY.render(f"{integrity * 100:.0f}%", True, C_TEXT_PRIMARY)
        surface.blit(pct_text, (x + bar_w + 10, y - 1))
        y += 34

        # Uptime
        uptime_str = time.strftime("%H:%M:%S", time.gmtime(self.uptime))
        self._draw_metric_inline(surface, x, y, "UP", uptime_str, C_TEXT_DIM)
        y += 34

        # Velocidade orbital visual
        speed_label = FONT_SMALL.render("VEL. ORBITAL", True, C_TEXT_DIM)
        surface.blit(speed_label, (x, y))
        gauge_x = x
        gauge_y = y + 24
        gauge_w = content_w
        gauge_h = 8
        pygame.draw.rect(surface, (30, 30, 50), (gauge_x, gauge_y, gauge_w, gauge_h), border_radius=3)
        indicator_pos = int(gauge_w * (0.5 + 0.3 * math.sin(t * satellite.orbit_speed * 3)))
        pygame.draw.rect(surface, C_ACCENT_CYAN, (gauge_x + indicator_pos - 4, gauge_y - 3, 8, gauge_h + 6),
                         border_radius=3)

    def _draw_right_panel(self, surface, t):
        """Painel direito: Log de comandos e entrada."""
        panel_rect = pygame.Rect(WIDTH - 430, 55, 405, HEIGHT - 120)
        self._draw_panel_bg(surface, panel_rect, "◆ CONSOLE DE COMANDOS", t)

        y = panel_rect.y + 46
        x = panel_rect.x + 15
        content_w = panel_rect.width - 30

        # Log de comandos
        for entry in self.command_history[-10:]:
            # Timestamp
            time_surf = FONT_SMALL.render(entry["time"], True, C_TEXT_DIM)
            surface.blit(time_surf, (x, y))

            # Comando
            cmd_surf = FONT_SMALL.render(entry["cmd"][:18], True, C_TEXT_PRIMARY)
            surface.blit(cmd_surf, (x + 90, y))

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
            surface.blit(status_surf, (x + 260, y))

            y += 28

        # Separador antes do input
        sep_y = panel_rect.y + panel_rect.height - 95
        pygame.draw.line(surface, C_PANEL_BORDER, (x, sep_y), (x + content_w, sep_y), 1)

        # Comandos disponíveis (hint)
        hint_y = sep_y + 10
        hint_text = "CMDS: INJECT_FAULT | BIT_FLIP | PING"
        hint_surf = FONT_SMALL.render(hint_text, True, C_TEXT_DIM)
        surface.blit(hint_surf, (x, hint_y))
        hint_text2 = "PQC_STATUS | CRC_CHECK | RESET_SESSION"
        hint_surf2 = FONT_SMALL.render(hint_text2, True, C_TEXT_DIM)
        surface.blit(hint_surf2, (x, hint_y + 22))

        # Campo de input
        input_y = panel_rect.y + panel_rect.height - 50
        input_rect = pygame.Rect(x, input_y, content_w, 36)

        # Fundo do input
        input_bg_color = (25, 30, 55) if self.input_active else (18, 20, 40)
        pygame.draw.rect(surface, input_bg_color, input_rect, border_radius=5)
        border_color = C_ACCENT_CYAN if self.input_active else C_PANEL_BORDER
        pygame.draw.rect(surface, border_color, input_rect, 1, border_radius=5)

        # Prompt
        prompt = FONT_CMD.render("❯ ", True, C_ACCENT_CYAN)
        surface.blit(prompt, (x + 8, input_y + 8))

        # Texto digitado
        text_surf = FONT_CMD.render(self.input_text, True, C_TEXT_PRIMARY)
        surface.blit(text_surf, (x + 28, input_y + 8))

        # Cursor piscante
        if self.input_active and int(self.cursor_blink * 2) % 2 == 0:
            cursor_x = x + 28 + text_surf.get_width() + 2
            pygame.draw.line(surface, C_ACCENT_CYAN, (cursor_x, input_y + 6),
                             (cursor_x, input_y + 28), 2)

    def _draw_top_bar(self, surface, t):
        """Barra superior com título e status global."""
        bar_h = 50
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 220), (0, 0, WIDTH, bar_h))
        pygame.draw.line(bar_surf, C_PANEL_BORDER, (0, bar_h - 1), (WIDTH, bar_h - 1), 1)
        surface.blit(bar_surf, (0, 0))

        # Título principal
        title = FONT_HEADER.render("PQC-SAT", True, C_ACCENT_CYAN)
        surface.blit(title, (WIDTH // 2 - 220, 12))

        subtitle = FONT_SMALL.render("Mission Control · UFF Cibersegurança", True, C_TEXT_DIM)
        surface.blit(subtitle, (WIDTH // 2 - 220 + title.get_width() + 15, 16))

        # Indicador de conexão
        conn_pulse = int(180 + 75 * math.sin(t * 3))
        pygame.draw.circle(surface, (0, conn_pulse, 0), (WIDTH - 150, 25), 6)
        conn_text = FONT_SMALL.render("LINK ATIVO", True, C_ACCENT_GREEN)
        surface.blit(conn_text, (WIDTH - 136, 17))

        # Clock
        clock_text = FONT_SMALL.render(time.strftime("%H:%M:%S"), True, C_TEXT_DIM)
        surface.blit(clock_text, (WIDTH - 290, 17))

    def _draw_bottom_bar(self, surface, t):
        """Barra inferior com informações secundárias."""
        bar_h = 36
        bar_y = HEIGHT - bar_h
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(bar_surf, (*C_PANEL_BG, 200), (0, 0, WIDTH, bar_h))
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
        x = 25
        for item in items:
            color = C_TEXT_DIM
            if "CONECTADO" in item:
                color = C_ACCENT_GREEN
            surf = FONT_SMALL.render(item, True, color)
            surface.blit(surf, (x, bar_y + 9))
            x += surf.get_width() + 35

            # Separador
            if x < WIDTH - 150:
                pygame.draw.line(surface, C_PANEL_BORDER, (x - 18, bar_y + 7), (x - 18, bar_y + 27), 1)

    def _draw_metric_stacked(self, surface, x, y, label, value, value_color):
        """Desenha métrica com label em cima e valor embaixo."""
        label_surf = FONT_SMALL.render(label, True, C_TEXT_DIM)
        value_surf = FONT_BODY.render(str(value), True, value_color)
        surface.blit(label_surf, (x, y))
        surface.blit(value_surf, (x, y + 18))

    def _draw_metric_inline(self, surface, x, y, label, value, value_color):
        """Desenha métrica com label curto + valor na mesma linha."""
        label_surf = FONT_SMALL.render(label, True, C_TEXT_DIM)
        value_surf = FONT_BODY.render(str(value), True, value_color)
        surface.blit(label_surf, (x, y + 1))
        surface.blit(value_surf, (x + label_surf.get_width() + 8, y))


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


# ─── Estrelas Cadentes ────────────────────────────────────────────
class ShootingStars:
    """Estrelas cadentes ocasionais e sutis."""

    def __init__(self):
        self.meteors = []
        self.spawn_timer = 0.0
        self.next_spawn = random.uniform(2.0, 6.0)  # segundos até a próxima

    def update(self, dt):
        self.spawn_timer += dt

        # Spawnar nova estrela cadente
        if self.spawn_timer >= self.next_spawn:
            self.spawn_timer = 0.0
            self.next_spawn = random.uniform(3.0, 8.0)
            self._spawn()

        # Atualizar existentes
        for m in self.meteors:
            m['x'] += m['vx'] * dt
            m['y'] += m['vy'] * dt
            m['life'] -= dt

        # Remover mortas
        self.meteors = [m for m in self.meteors if m['life'] > 0]

    def _spawn(self):
        # Posição inicial aleatória nas bordas superiores
        side = random.choice(['top', 'right'])
        if side == 'top':
            x = random.randint(100, WIDTH - 100)
            y = random.randint(-20, 50)
        else:
            x = random.randint(WIDTH - 200, WIDTH + 20)
            y = random.randint(50, HEIGHT // 2)

        # Direção: diagonal para baixo-esquerda
        angle = random.uniform(math.pi * 0.55, math.pi * 0.72)
        speed = random.uniform(250, 500)
        life = random.uniform(0.8, 1.8)
        self.meteors.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'life': life,
            'max_life': life,
            'length': random.randint(80, 180),
            'brightness': random.randint(200, 255),
        })

    def draw(self, surface):
        for m in self.meteors:
            alpha_ratio = m['life'] / m['max_life']
            # Calcular posição da cauda
            speed = math.sqrt(m['vx'] ** 2 + m['vy'] ** 2)
            if speed < 1:
                continue
            dx = -m['vx'] / speed * m['length']
            dy = -m['vy'] / speed * m['length']

            head_x, head_y = int(m['x']), int(m['y'])
            tail_x, tail_y = int(m['x'] + dx), int(m['y'] + dy)

            # Linha principal com fade — mais grossa e visível
            b = max(0, min(255, int(m['brightness'] * alpha_ratio)))
            b2 = max(0, min(255, int(b * 0.85)))

            # Trilha secundária (mais larga, translúcida)
            trail_s = pygame.Surface((abs(head_x - tail_x) + 20, abs(head_y - tail_y) + 20), pygame.SRCALPHA)
            ox = min(head_x, tail_x) - 10
            oy = min(head_y, tail_y) - 10
            pygame.draw.line(trail_s, (b, b, b2, max(0, min(255, int(60 * alpha_ratio)))),
                             (head_x - ox, head_y - oy), (tail_x - ox, tail_y - oy), 5)
            surface.blit(trail_s, (ox, oy))

            # Linha central brilhante
            pygame.draw.line(surface, (b, b, b2),
                             (head_x, head_y), (tail_x, tail_y), 3)

            # Glow na cabeça — maior
            glow_size = max(0, min(14, int(7 * alpha_ratio)))
            if glow_size > 0:
                b3 = max(0, min(255, int(b * 0.8)))
                ga = max(0, min(255, int(180 * alpha_ratio)))
                glow_s = pygame.Surface((glow_size * 6, glow_size * 6), pygame.SRCALPHA)
                pygame.draw.circle(glow_s, (b, b, b3, ga),
                                   (glow_size * 3, glow_size * 3), glow_size)
                # Segundo halo maior e mais difuso
                ga2 = max(0, min(255, int(50 * alpha_ratio)))
                pygame.draw.circle(glow_s, (b, b, b3, ga2),
                                   (glow_size * 3, glow_size * 3), glow_size * 2)
                surface.blit(glow_s, (head_x - glow_size * 3, head_y - glow_size * 3))


# ─── Loop Principal ──────────────────────────────────────────────
def main():
    global WIDTH, HEIGHT, screen

    stars = StarField(350)
    earth = Earth()
    satellite = Satellite(earth)
    dashboard = DashboardPanel()
    dust = CosmicDust(50)
    shooting_stars = ShootingStars()

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
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    running = False
            dashboard.handle_event(event)

        # ── Atualização ──
        satellite.update(dt)
        dashboard.update(dt)
        dust.update(dt)
        shooting_stars.update(dt)

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
        shooting_stars.draw(screen)
        earth.draw(screen, t)
        satellite.draw(screen, t)
        dashboard.draw(screen, t, satellite)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
