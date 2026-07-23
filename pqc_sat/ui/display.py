"""Mutable display context shared by responsive Pygame views."""

from dataclasses import dataclass, field

import pygame


@dataclass
class DisplayContext:
    width: int = 1920
    height: int = 1080
    surface: pygame.Surface | None = None
    clock: pygame.time.Clock = field(default_factory=pygame.time.Clock)

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    def set_size(self, width: int, height: int) -> None:
        self.width = int(width)
        self.height = int(height)


DISPLAY = DisplayContext()


def init_display(*, windowed: bool = False, windowed_size: tuple[int, int] = (1366, 768)) -> pygame.Surface:
    """Initialize the display only after command-line arguments are parsed."""
    pygame.init()
    if windowed:
        DISPLAY.set_size(*windowed_size)
        flags = pygame.DOUBLEBUF
    else:
        info = pygame.display.Info()
        DISPLAY.set_size(info.current_w, info.current_h)
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
    DISPLAY.surface = pygame.display.set_mode(DISPLAY.size, flags)
    pygame.display.set_caption("PQC-SAT Mission Control Dashboard")
    DISPLAY.clock = pygame.time.Clock()
    return DISPLAY.surface


__all__ = ("DISPLAY", "DisplayContext", "init_display")
