"""Wisdom-search standby drawn inside the non-blocking main loop."""

import math
import pygame
from pqc_sat.ui.theme import (
    C_SPACE_BG,
    C_ACCENT_CYAN,
    C_ACCENT_ORANGE,
    FONT_BODY,
    FONT_LABEL,
)
from pqc_sat.ui.scene import draw_robot_pixel


def draw_wisdom_search(surface, status_label, t):
    """Render a minimal standby until a validated Wisdom is discovered."""

    surface.fill(C_SPACE_BG)
    center_x = surface.get_width() // 2
    center_y = surface.get_height() // 2

    pulse = 0.65 + 0.35 * math.sin(t * 3.0)
    glow_color = (0, int(150 + 80 * pulse), 255)
    pygame.draw.circle(surface, (*glow_color, 38), (center_x, center_y - 54), 120, 2)
    pygame.draw.circle(surface, (*C_ACCENT_CYAN, 80), (center_x, center_y - 54), 74, 1)
    draw_robot_pixel(surface, center_x, center_y - 62, pixel_size=9, t=t)

    width = min(620, surface.get_width() - 80)
    action = pygame.Rect(center_x - width // 2, center_y + 92, width, 56)
    color = C_ACCENT_CYAN
    fill = (7, 28, 42)
    pygame.draw.rect(surface, fill, action, border_radius=12)
    pygame.draw.rect(surface, color, action, width=3, border_radius=12)
    instruction = "PROCURANDO A BLACKBOARD WISDOM"
    rendered = FONT_BODY.render(instruction, True, color)
    surface.blit(rendered, (action.centerx - rendered.get_width() // 2, action.centery - rendered.get_height() // 2))

    if str(status_label).startswith("FIXTURE"):
        watermark = FONT_LABEL.render(str(status_label), True, C_ACCENT_ORANGE)
        surface.blit(watermark, (surface.get_width() - watermark.get_width() - 14, surface.get_height() - 22))


__all__ = ("draw_wisdom_search",)
