"""Headless rendering through the staged game's production view."""

import pygame
from pqc_sat.ui.theme import C_SPACE_BG
from pqc_sat.ui.display import DISPLAY
from pqc_sat.ui.game import GamePanel
from pqc_sat.ui.scene import CosmicDust, Nebula, ShootingStars, StarField


def render_game_frame(
    controller,
    *,
    size=(1366, 768),
    now=0.0,
    diagnostic=False,
    replay_progress=None,
    search_active=None,
):
    """Render one off-screen frame through the same dashboard layer used live."""
    DISPLAY.set_size(int(size[0]), int(size[1]))
    frame = pygame.Surface((DISPLAY.width, DISPLAY.height))
    stars = StarField(180)
    nebula = Nebula()
    dust = CosmicDust(28)
    shooting_stars = ShootingStars()
    panel = GamePanel.for_test(controller, diagnostic=diagnostic)
    if search_active is not None:
        panel.search_screen_enabled = bool(search_active)
        panel.wisdom_search_active = bool(search_active)
    if replay_progress is not None:
        panel.replay_interaction.sync(controller.state.value, 1.0, True)
        panel.replay_interaction.display_progress = max(0.0, min(1.0, float(replay_progress)))

    frame.fill(C_SPACE_BG)
    nebula.draw(frame, now)
    stars.draw(frame, now)
    dust.draw(frame)
    shooting_stars.draw(frame)
    panel.draw(frame, now)
    return frame

__all__ = ("render_game_frame",)
