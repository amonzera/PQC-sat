"""Procedural space scene and CubeSat visual entities."""

import math
import random
import pygame
from pqc_sat.ui.game_art import (
    GameAct,
    draw_ground_station,
    draw_satellite_glyph,
    draw_signal_link,
)
from pqc_sat.ui.theme import (
    C_PANEL_HEADER,
    C_ACCENT_CYAN,
    C_ACCENT_BLUE,
    C_ACCENT_RED,
    C_SAT_BODY,
    C_SAT_PANEL_BLUE,
    C_SAT_PANEL_DARK,
    C_SAT_GOLD,
    C_ROBOT_FACE,
    C_ROBOT_EYE,
    C_ROBOT_SMILE,
    FONT_PIXEL,
)
from pqc_sat.ui.display import DISPLAY


class StarField:
    def __init__(self, count=300):
        self.stars = []
        for _ in range(count):
            x = random.randint(0, DISPLAY.width)
            y = random.randint(0, DISPLAY.height)
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

class Earth:
    def __init__(self, radius=180, center=None):
        self.radius = max(48, int(radius))
        if center is None:
            center = (DISPLAY.width // 2, DISPLAY.height // 2 + 20)
        self.center_x = int(center[0])
        self.center_y = int(center[1])
        # REFATORAÇÃO VISUAL: Terra com Textura Rolável
        self.size = 0
        self.base_cache = None
        self.land_texture = None
        self.land_view_cache = None
        self.circle_mask = None
        self.overlay_cache = None
        self.rotation_speed_px = 10.0
        self._build_surface()

    def set_position(self, center):
        self.center_x = int(center[0])
        self.center_y = int(center[1])

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


class MissionWorld:
    """Persistent Earth-to-orbit stage shared by every public game screen."""

    def __init__(self):
        self._earth_cache = {}
        self.anchors = {}

    def _earth(self, radius, center):
        radius = max(64, int(radius))
        earth = self._earth_cache.get(radius)
        if earth is None:
            earth = Earth(radius=radius, center=center)
            self._earth_cache[radius] = earth
        earth.set_position(center)
        return earth

    @staticmethod
    def _orbit_point(center, radius_x, radius_y, angle):
        return (
            int(center[0] + math.cos(angle) * radius_x),
            int(center[1] + math.sin(angle) * radius_y),
        )

    @staticmethod
    def _draw_orbit(surface, center, radius_x, radius_y, *, color):
        points = []
        for index in range(96):
            angle = index * math.tau / 96
            points.append(
                (
                    int(center[0] + math.cos(angle) * radius_x),
                    int(center[1] + math.sin(angle) * radius_y),
                )
            )
        for index in range(0, len(points), 3):
            pygame.draw.line(surface, color, points[index], points[(index + 1) % len(points)], 1)

    @staticmethod
    def _draw_orbit_trail(surface, center, radius_x, radius_y, angle, color):
        for index in range(18, 0, -1):
            trail_angle = angle - index * 0.035
            point = MissionWorld._orbit_point(center, radius_x, radius_y, trail_angle)
            factor = 0.25 + (18 - index) / 24
            trail_color = tuple(max(0, min(255, int(component * factor))) for component in color)
            pygame.draw.circle(surface, trail_color, point, max(1, 4 - index // 6))

    def draw(self, surface, viewport, t, *, act, state, online, progress=0.0):
        """Draw the world and expose semantic anchors for the active replay."""

        viewport = pygame.Rect(viewport)
        act = act if isinstance(act, GameAct) else GameAct(str(act))
        state_name = str(getattr(state, "value", state)).upper()
        width, height = viewport.size

        if act is GameAct.BRIEFING:
            radius = min(310, max(150, int(height * 0.34)))
            center = (
                viewport.x + int(width * (0.31 if state_name == "ATTRACT" else 0.12)),
                viewport.y + int(height * (0.58 if state_name == "ATTRACT" else 0.78)),
            )
            orbit_x, orbit_y = int(radius * 1.65), int(radius * 0.64)
            angle = t * 0.34 - 0.55
            satellite_size = max(52, radius // 2)
        elif act is GameAct.LOADOUT:
            radius = min(220, max(110, int(height * 0.25)))
            center = (viewport.x + int(width * 0.09), viewport.bottom + int(radius * 0.18))
            orbit_x, orbit_y = int(radius * 1.75), int(radius * 0.68)
            angle = t * 0.32 - 1.05
            satellite_size = max(44, radius // 2)
        elif act is GameAct.OPERATION:
            radius = min(190, max(105, int(height * 0.23)))
            center = (viewport.x + int(width * 0.08), viewport.bottom + int(radius * 0.18))
            orbit_x, orbit_y = int(radius * 2.10), int(radius * 0.82)
            angle = -0.78 + math.sin(t * 0.16) * 0.12
            satellite_size = max(48, radius // 2)
        else:
            radius = min(310, max(155, int(height * 0.34)))
            center = (viewport.x + int(width * 0.50), viewport.bottom + int(radius * 0.32))
            orbit_x, orbit_y = int(radius * 1.55), int(radius * 0.62)
            angle = t * 0.20 - 1.25
            satellite_size = max(46, radius // 3)

        satellite = self._orbit_point(center, orbit_x, orbit_y, angle)
        ground = (
            int(center[0] + radius * 0.12),
            int(center[1] - radius * 0.73),
        )
        receiver = (
            viewport.right - max(70, int(width * 0.055)),
            viewport.bottom - max(82, int(height * 0.13)),
        )
        self.anchors = {
            "earth": center,
            "ground": ground,
            "satellite": satellite,
            "receiver": receiver,
        }

        orbit_color = (34, 84, 132) if state_name != "ERROR" else (92, 38, 52)
        self._draw_orbit(surface, center, orbit_x, orbit_y, color=orbit_color)
        self._draw_orbit_trail(surface, center, orbit_x, orbit_y, angle, C_ACCENT_CYAN)

        earth = self._earth(radius, center)
        satellite_behind = math.sin(angle) < 0
        if satellite_behind:
            draw_satellite_glyph(surface, satellite, satellite_size, t, online=online)
        earth.draw(surface, t)
        if not satellite_behind:
            draw_satellite_glyph(surface, satellite, satellite_size, t, online=online)

        # The uplink anchor remains part of the causal diagram, but the radio
        # tower glyph no longer sits on top of the Earth in the public scene.
        if act is GameAct.OPERATION:
            link_progress = max(0.08, min(1.0, float(progress)))
            draw_signal_link(surface, ground, satellite, t, progress=link_progress)
            draw_signal_link(
                surface,
                satellite,
                receiver,
                t + 0.6,
                color=C_ACCENT_BLUE,
                progress=max(0.0, link_progress * 1.35 - 0.35),
            )
            draw_ground_station(surface, receiver, max(32, radius // 4), t + 0.5)
        elif state_name == "ATTRACT":
            draw_signal_link(surface, ground, satellite, t, progress=0.72 + 0.28 * (0.5 + 0.5 * math.sin(t)))

        if not online:
            pygame.draw.circle(surface, (220, 102, 34), satellite, max(12, satellite_size // 2), 2)
        if state_name == "ERROR":
            pygame.draw.line(surface, C_ACCENT_RED, (viewport.x + 30, viewport.y + 28), (viewport.right - 30, viewport.bottom - 28), 3)
            pygame.draw.line(surface, C_ACCENT_RED, (viewport.right - 30, viewport.y + 28), (viewport.x + 30, viewport.bottom - 28), 3)

class Nebula:
    """Cached opaque space gradient; safe because it is the first scene layer."""

    def __init__(self):
        self.surface_cache = None

    def _build_surface(self, size):
        width, height = size
        self.surface_cache = pygame.Surface(size)
        self.surface_cache.fill((0, 2, 10))
        blobs = (
            (0.42, 0.48, 340, (20, 7, 39)),
            (0.55, 0.50, 300, (27, 8, 43)),
            (0.48, 0.58, 260, (10, 20, 43)),
        )
        for cx_ratio, cy_ratio, radius, color in blobs:
            center = (int(width * cx_ratio), int(height * cy_ratio))
            for step in range(5, 0, -1):
                current_radius = max(12, int(radius * step / 5))
                strength = (6 - step) / 5
                blended = tuple(
                    int(base + (component - base) * strength * 0.32)
                    for base, component in zip((0, 2, 10), color)
                )
                pygame.draw.circle(
                    self.surface_cache,
                    blended,
                    center,
                    current_radius,
                )

    def draw(self, surface, t):
        size = surface.get_size()
        if self.surface_cache is None or self.surface_cache.get_size() != size:
            self._build_surface(size)
        surface.blit(self.surface_cache, (0, 0))

class CosmicDust:
    def __init__(self, count=40):
        self.particles = []
        for _ in range(count):
            self.particles.append(self._new_particle())

    def _new_particle(self):
        life = random.uniform(2, 8)
        return {
            'x': random.randint(0, DISPLAY.width),
            'y': random.randint(0, DISPLAY.height),
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
            x = random.randint(100, DISPLAY.width - 100)
            y = random.randint(-20, 50)
        else:
            x = random.randint(DISPLAY.width - 200, DISPLAY.width + 20)
            y = random.randint(50, DISPLAY.height // 2)
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

__all__ = (
    "StarField",
    "Earth",
    "ROBOT_PIXELS",
    "ROBOT_COLORS",
    "draw_robot_pixel",
    "Satellite",
    "MissionWorld",
    "Nebula",
    "CosmicDust",
    "ShootingStars",
)
