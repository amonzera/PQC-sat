"""Paths, dimensions and palette for guided stand support."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = ROOT / "config" / "game.json"

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

__all__ = (
    "ROOT",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_FIXTURE_PATH",
    "DEFAULT_LOG_DIR",
    "VIRTUAL_SIZE",
    "FPS",
    "C_BG",
    "C_BG_SOFT",
    "C_PANEL",
    "C_PANEL_2",
    "C_CYAN",
    "C_BLUE",
    "C_GREEN",
    "C_YELLOW",
    "C_ORANGE",
    "C_RED",
    "C_PURPLE",
    "C_WHITE",
    "C_DIM",
    "C_LINE",
)
