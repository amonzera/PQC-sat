"""Presentation-only interaction for measured didactic replays.

The object deliberately owns no mission state.  It can move a visual packet
through an already validated replay, but it cannot complete an animation,
confirm a choice or cause a controller transition.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class ReplayInteraction:
    """Mouse-driven review state kept outside the investigation controller."""

    stage_key: str = ""
    display_progress: float = 0.0
    review_enabled: bool = False
    dragging: bool = False
    track_rect: pygame.Rect = field(default_factory=pygame.Rect)
    packet_rect: pygame.Rect = field(default_factory=pygame.Rect)
    station_progresses: tuple[float, ...] = ()

    def reset(self) -> None:
        self.stage_key = ""
        self.display_progress = 0.0
        self.review_enabled = False
        self.dragging = False
        self.track_rect = pygame.Rect(0, 0, 0, 0)
        self.packet_rect = pygame.Rect(0, 0, 0, 0)
        self.station_progresses = ()

    def invalidate_if_state_changed(self, state_name: str) -> None:
        if self.stage_key and self.stage_key != str(state_name):
            self.reset()

    def sync(self, stage_key: str, autoplay_progress: float, autoplay_complete: bool) -> float:
        """Return auto progress first, then the visitor-controlled review progress."""

        stage_key = str(stage_key)
        if stage_key != self.stage_key:
            self.reset()
            self.stage_key = stage_key
        if not autoplay_complete:
            self.review_enabled = False
            self.dragging = False
            self.display_progress = _clamp(autoplay_progress)
            return self.display_progress
        if not self.review_enabled:
            # The automatic replay has already reached the end.  Reviewing it
            # Going backwards must not relock the explicit confirmation.
            self.review_enabled = True
            self.display_progress = 1.0
        return self.display_progress

    def register_geometry(
        self,
        track_rect: pygame.Rect,
        packet_rect: pygame.Rect,
        station_progresses: tuple[float, ...],
    ) -> None:
        self.track_rect = pygame.Rect(track_rect)
        self.packet_rect = pygame.Rect(packet_rect)
        values = tuple(_clamp(value) for value in station_progresses)
        self.station_progresses = values or (0.0, 1.0)

    def begin_drag(self, position: tuple[int, int]) -> bool:
        if not self.review_enabled or self.packet_rect.width <= 0:
            return False
        if not self.packet_rect.inflate(24, 20).collidepoint(position):
            return False
        self.dragging = True
        return True

    def drag_to(self, x: int) -> bool:
        if not self.dragging or self.track_rect.width <= 0:
            return False
        ratio = _clamp((int(x) - self.track_rect.left) / self.track_rect.width)
        self.display_progress = self.progress_for_ratio(ratio)
        return True

    def end_drag(self) -> bool:
        if not self.dragging:
            return False
        self.dragging = False
        if self.station_progresses:
            self.display_progress = min(
                self.station_progresses,
                key=lambda value: abs(value - self.display_progress),
            )
        return True

    def progress_for_ratio(self, ratio: float) -> float:
        """Map equally spaced visual stations to their measured cue progress."""

        ratio = _clamp(ratio)
        values = self.station_progresses or (0.0, 1.0)
        if len(values) == 1:
            return values[0]
        scaled = ratio * (len(values) - 1)
        left_index = min(len(values) - 2, int(scaled))
        local = scaled - left_index
        left = values[left_index]
        right = values[left_index + 1]
        return _clamp(left + (right - left) * local)

    def ratio_for_progress(self, progress: float) -> float:
        """Inverse of :meth:`progress_for_ratio` for packet placement."""

        progress = _clamp(progress)
        values = self.station_progresses or (0.0, 1.0)
        if len(values) == 1:
            return 1.0
        if progress <= values[0]:
            return 0.0
        for index, right in enumerate(values[1:], start=1):
            left = values[index - 1]
            if progress <= right:
                span = max(1e-9, right - left)
                local = (progress - left) / span
                return _clamp(((index - 1) + local) / (len(values) - 1))
        return 1.0


__all__ = ("ReplayInteraction",)
