"""Pygame color palette and validated presentation fonts."""

import pygame


pygame.font.init()

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

__all__ = (
    "load_font",
    "C_SPACE_BG",
    "C_PANEL_BG",
    "C_PANEL_BORDER",
    "C_PANEL_HEADER",
    "C_ACCENT_CYAN",
    "C_ACCENT_BLUE",
    "C_ACCENT_GREEN",
    "C_ACCENT_ORANGE",
    "C_ACCENT_RED",
    "C_ACCENT_PURPLE",
    "C_TEXT_PRIMARY",
    "C_TEXT_DIM",
    "C_SAT_BODY",
    "C_SAT_PANEL_BLUE",
    "C_SAT_PANEL_DARK",
    "C_SAT_GOLD",
    "C_ROBOT_FACE",
    "C_ROBOT_EYE",
    "C_ROBOT_SMILE",
    "FONT_TITLE",
    "FONT_HEADER",
    "FONT_BODY",
    "FONT_SMALL",
    "FONT_LARGE",
    "FONT_CMD",
    "FONT_PIXEL",
    "FONT_LABEL",
)
