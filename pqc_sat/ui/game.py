"""Single production interface for the hardware-backed staged game."""

from __future__ import annotations

import time

import pygame

from pqc_sat.stand.model import InvestigationState
from pqc_sat.ui.display import DISPLAY
from pqc_sat.ui.panel.investigation_view import InvestigationPresentationMixin
from pqc_sat.ui.replay import ReplayInteraction
from pqc_sat.ui.scene import MissionWorld
from pqc_sat.ui.splash import draw_wisdom_search
from pqc_sat.ui.theme import (
    C_ACCENT_ORANGE,
    C_PANEL_BORDER,
    C_TEXT_DIM,
    FONT_LABEL,
    FONT_SMALL,
)


class GamePanel(InvestigationPresentationMixin):
    """Visitor UI with selectable cards and explicit D27/screen confirmation."""

    def __init__(
        self,
        serial_client,
        controller,
        *,
        diagnostic: bool = False,
        startup_splash: bool = True,
    ) -> None:
        if serial_client is None:
            raise ValueError("a interface de produção exige um cliente serial")
        if controller.mode != "hardware":
            raise ValueError("a interface de produção aceita apenas o modo hardware")
        self.serial_client = serial_client
        self.stand_controller = controller
        self.stand_diagnostic = bool(diagnostic)
        self.stand_action_rects: dict[str, pygame.Rect] = {}
        self.mission_world = MissionWorld()
        self.replay_interaction = ReplayInteraction()
        self._last_public_state = controller.state
        self.search_screen_enabled = bool(startup_splash)
        self.wisdom_search_active = bool(startup_splash)
        self.serial_connected = False
        self.serial_status = "INICIANDO SERIAL"
        self.serial_client.start()

    @classmethod
    def for_test(cls, controller, *, diagnostic: bool = False, startup_splash: bool = False):
        """Build a render/input harness without weakening production checks."""

        panel = cls.__new__(cls)
        panel.serial_client = None
        panel.stand_controller = controller
        panel.stand_diagnostic = bool(diagnostic)
        panel.stand_action_rects = {}
        panel.mission_world = MissionWorld()
        panel.replay_interaction = ReplayInteraction()
        panel._last_public_state = controller.state
        panel.search_screen_enabled = bool(startup_splash)
        panel.wisdom_search_active = bool(startup_splash)
        panel.serial_connected = bool(controller.connected)
        panel.serial_status = controller.connection_status
        return panel

    def close(self) -> None:
        if self.stand_controller.state not in {
            InvestigationState.ATTRACT,
            InvestigationState.ERROR,
        }:
            self.stand_controller.abort(reason="application_closed")
        self.serial_client.stop()

    @staticmethod
    def _stand_state_label(state: str) -> str:
        return {
            "SELECT_MISSION": "ESCOLHA DA MISSÃO",
            "SELECT_KEY_MODE": "ESTABELECIMENTO DE CHAVE",
            "SELECT_GUARD": "GUARDIÃO DA APLICAÇÃO",
            "SELECT_RESPONSE": "RESPOSTA OPERACIONAL",
            "DEBRIEF": "ENCERRAMENTO",
        }.get(state, state.replace("_", " "))

    def satellite_online(self) -> bool:
        return self.serial_connected and self.stand_controller.ready

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route touch controls while never emulating physical D27 by keyboard."""

        if self.wisdom_search_active:
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F12:
                self.stand_diagnostic = not self.stand_diagnostic
            elif event.key == pygame.K_HOME:
                self.stand_controller.abort(reason="operator_home_key")
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.replay_interaction.begin_drag(event.pos):
                self.stand_controller.note_interaction()
                return True
            for action, rect in reversed(tuple(self.stand_action_rects.items())):
                if rect.collidepoint(event.pos):
                    self.stand_controller.handle_action(action)
                    return True
            self.stand_controller.note_interaction()
            return True
        if event.type == pygame.MOUSEMOTION and self.replay_interaction.dragging:
            self.replay_interaction.drag_to(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            return self.replay_interaction.end_drag() or True
        return event.type in {
            pygame.MOUSEWHEEL,
        }

    def _handle_serial_input(self, event_type: str, payload: dict[str, object], *, now: float) -> None:
        if event_type == "state":
            self.serial_connected = bool(payload.get("connected"))
            self.serial_status = str(payload.get("status", "SERIAL"))
            if not self.serial_connected and self.search_screen_enabled:
                self.wisdom_search_active = True
        if (
            self.wisdom_search_active
            and event_type == "event"
            and str(payload.get("name", "")).upper() == "BUTTON_PING"
        ):
            return
        self.stand_controller.handle_serial_event(event_type, payload, now=now)
        self._sync_wisdom_search(now=now)

    def _sync_wisdom_search(self, *, now: float) -> None:
        if not self.search_screen_enabled or not self.wisdom_search_active:
            return
        if not self.stand_controller.ready:
            return
        if self.stand_controller.complete_wisdom_search(now=now):
            self.wisdom_search_active = False

    def update(self, _dt: float) -> None:
        now = time.monotonic()
        for event_type, payload in self.serial_client.poll():
            self._handle_serial_input(event_type, payload, now=now)
        self.stand_controller.update(now=now)
        self._sync_presentation_state()

    def draw(self, surface: pygame.Surface, t: float) -> None:
        if self.wisdom_search_active:
            label = (
                "FIXTURE DE TESTE — BUSCA SEM HARDWARE"
                if self.stand_controller.mode != "hardware"
                else self.serial_status
            )
            draw_wisdom_search(surface, label, t)
            return
        self._sync_presentation_state()
        self._draw_investigation_presentation(surface, t)
        if self.stand_controller.mode != "hardware":
            label = FONT_LABEL.render("FIXTURE DE TESTE — SEM HARDWARE", True, C_ACCENT_ORANGE)
            surface.blit(label, (DISPLAY.width - label.get_width() - 14, DISPLAY.height - 22))

    def _sync_presentation_state(self) -> None:
        state = self.stand_controller.state
        if state is not self._last_public_state:
            self.replay_interaction.invalidate_if_state_changed(state.value)
            self._last_public_state = state

    def replay_progress(self, timeline) -> float:
        """Resolve autoplay versus review without changing controller readiness."""

        controller = self.stand_controller
        return self.replay_interaction.sync(
            controller.state.value,
            controller.animation_progress(),
            controller.animation_complete,
        )

    def _stand_overlay_geometry(self) -> pygame.Rect:
        margin = max(22, int(min(DISPLAY.width, DISPLAY.height) * 0.032))
        top = margin
        bottom = margin
        return pygame.Rect(
            margin,
            top,
            DISPLAY.width - margin * 2,
            DISPLAY.height - top - bottom - margin,
        )

    @staticmethod
    def _render_clipped(font, text, color, max_width):
        text = str(text)
        if font.size(text)[0] <= max_width:
            return font.render(text, True, color)
        suffix = "..."
        clipped = text
        while clipped and font.size(clipped + suffix)[0] > max_width:
            clipped = clipped[:-1]
        return font.render(clipped + suffix, True, color)

    @staticmethod
    def _wrap_text_for_width(font, text, max_width):
        lines: list[str] = []
        for paragraph in str(text).splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
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

    def _draw_wrapped_text(
        self,
        surface,
        font,
        text,
        color,
        x,
        y,
        max_width,
        line_spacing=20,
        max_lines=None,
    ):
        lines = self._wrap_text_for_width(font, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            surface.blit(self._render_clipped(font, line, color, max_width), (x, y))
            y += line_spacing
        return y

    def _draw_stand_centered(
        self,
        surface,
        font,
        text,
        color,
        center_x,
        y,
        max_width,
        *,
        line_gap=6,
        max_lines=None,
    ):
        lines = self._wrap_text_for_width(font, text, max_width)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            rendered = font.render(line, True, color)
            surface.blit(rendered, (center_x - rendered.get_width() // 2, y))
            y += rendered.get_height() + line_gap
        return y

    @staticmethod
    def _draw_stand_card_shell(surface, rect, accent, *, fill=(8, 16, 34)):
        pygame.draw.rect(surface, fill, rect, border_radius=8)
        pygame.draw.rect(surface, accent, rect, width=2, border_radius=8)
        pygame.draw.line(surface, accent, (rect.x + 12, rect.y + 42), (rect.right - 12, rect.y + 42), 1)

    def _draw_overlay_metric_box(self, surface, label, value, x, y, width, height, color):
        pygame.draw.rect(surface, (15, 20, 38), (x, y, width, height), border_radius=4)
        pygame.draw.rect(surface, C_PANEL_BORDER, (x, y, width, height), width=1, border_radius=4)
        surface.blit(self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, width - 10), (x + 6, y + 6))
        surface.blit(self._render_clipped(FONT_SMALL, value, color, width - 10), (x + 6, y + 22))

    @staticmethod
    def _stand_diagnostic_pending_label(controller) -> str:
        pending = controller.pending.command if controller.pending is not None else "--"
        if pending.startswith("GAME_BEGIN "):
            parts = pending.split(maxsplit=2)
            pending = " ".join(parts[:2]) + " [PARÂMETROS OCULTOS]"
        return pending

    def _draw_stand_diagnostic(self, surface, outer_rect, controller) -> None:
        lines = (
            f"ESTADO {controller.state.value} / {controller.flow_name}",
            f"CONEXÃO {controller.connection_status}",
            f"PENDENTE {self._stand_diagnostic_pending_label(controller)}",
            f"CICLOS {controller.completed_cycles}  REJEITADOS {controller.rejected_events}  IGNORADOS {controller.ignored_inputs}",
        )
        rect = pygame.Rect(outer_rect.right - 510, outer_rect.bottom - 122, 486, 92)
        pygame.draw.rect(surface, (0, 0, 0), rect, border_radius=6)
        pygame.draw.rect(surface, C_ACCENT_ORANGE, rect, width=1, border_radius=6)
        for index, line in enumerate(lines):
            rendered = self._render_clipped(FONT_LABEL, line, C_ACCENT_ORANGE, rect.width - 20)
            surface.blit(rendered, (rect.x + 10, rect.y + 9 + index * 19))


__all__ = ("GamePanel",)
