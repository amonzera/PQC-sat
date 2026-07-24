"""Public staged-game screens projected over the persistent orbital world."""

from __future__ import annotations

import math

import pygame

from pqc_sat.stand.model import GuardMode, IncidentScenario
from pqc_sat.ui.display import DISPLAY
from pqc_sat.ui.game_art import (
    ChoiceVisual,
    build_didactic_timeline,
    build_mission_review_timeline,
    draw_game_icon,
    draw_packet,
    draw_signal_link,
    game_act_for_state,
)
from pqc_sat.ui.theme import (
    C_ACCENT_BLUE,
    C_ACCENT_CYAN,
    C_ACCENT_GREEN,
    C_ACCENT_ORANGE,
    C_ACCENT_PURPLE,
    C_ACCENT_RED,
    C_PANEL_BORDER,
    C_TEXT_DIM,
    C_TEXT_PRIMARY,
    FONT_BODY,
    FONT_HEADER,
    FONT_LABEL,
    FONT_LARGE,
    FONT_SMALL,
    FONT_TITLE,
)

STEP_LABELS = {
    "ATTRACT": "SALVE A MENSAGEM EM ÓRBITA",
    "SELECT_MISSION": "ESCOLHA 1/4 • MENSAGEM",
    "SELECT_PROFILE": "ESCOLHA 2/4 • CPU",
    "SELECT_KEY_MODE": "ESCOLHA 3/4 • ABORDAGEM",
    "SELECT_GUARD": "ESCOLHA 4/4 • CRC",
    "PREPARE": "CHECKPOINT 1/4 • PREPARAR",
    "PROTECT": "CHECKPOINT 2/4 • PROTEGER",
    "TRANSMIT": "CHECKPOINT 3/4 • TRANSMITIR",
    "VERIFY": "CHECKPOINT 4/4 • VERIFICAR",
    "DIAGNOSE": "DECISÃO 1/2 • DIAGNÓSTICO",
    "SELECT_RESPONSE": "DECISÃO 2/2 • RESPOSTA",
    "RETRY": "OPERAÇÃO EXTRA • RETRANSMISSÃO",
    "DEBRIEF": "RELATÓRIO DA MISSÃO",
    "ERROR": "PROTOCOLO INTERROMPIDO",
}


def _format_elapsed(value):
    try:
        elapsed_us = int(value)
    except (TypeError, ValueError):
        return "--"
    if elapsed_us >= 1_000_000:
        return f"{elapsed_us / 1_000_000:.2f} s"
    if elapsed_us >= 1_000:
        return f"{elapsed_us / 1_000:.1f} ms"
    return f"{elapsed_us} us"


def _enum_value(value, default="--"):
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _approach_label(value, default="--"):
    key_mode = _enum_value(value, default=default)
    return {
        "ECDH": "CLÁSSICA • ECDH P-256",
        "MLKEM": "PÓS-QUÂNTICA • ML-KEM-512",
    }.get(key_mode, key_mode)


class InvestigationPresentationMixin:
    """View-only projection: drawing never selects, confirms or advances state."""

    def _investigation_action(self, action, rect):
        self.stand_action_rects[action] = pygame.Rect(rect)

    def _draw_investigation_presentation(self, surface, t):
        controller = self.stand_controller
        self.stand_action_rects = {}
        rect = self._stand_overlay_geometry()
        state_name = controller.state.value
        act = game_act_for_state(state_name)

        # A procedural world replaces the old opaque engineering panel.  It is
        # still drawn under solid local cards so 1366x768 remains legible.
        pygame.draw.rect(surface, (0, 3, 12), (0, 0, DISPLAY.width, DISPLAY.height))
        world_rect = pygame.Rect(0, 0, DISPLAY.width, DISPLAY.height)
        if controller.current_stage_measurement and self.replay_interaction.stage_key == state_name:
            world_progress = self.replay_interaction.display_progress
        else:
            world_progress = controller.animation_progress() if controller.current_stage_measurement else 0.0
        self.mission_world.draw(
            surface,
            world_rect,
            t,
            act=act,
            state=controller.state,
            online=self.satellite_online(),
            progress=world_progress,
        )

        self._draw_game_header(surface, rect, controller)
        body = pygame.Rect(rect.x + 24, rect.y + 62, rect.width - 48, rect.height - 82)
        body = self._draw_confirmed_loadout(surface, body, controller)
        renderer = {
            "ATTRACT": self._draw_game_attract,
            "SELECT_MISSION": self._draw_game_missions,
            "SELECT_PROFILE": self._draw_game_profiles,
            "SELECT_KEY_MODE": self._draw_game_key_modes,
            "SELECT_GUARD": self._draw_game_guards,
            "PREPARE": self._draw_game_prepare,
            "PROTECT": self._draw_game_protect,
            "TRANSMIT": self._draw_game_transmit,
            "VERIFY": self._draw_game_verify,
            "DIAGNOSE": self._draw_game_diagnose,
            "SELECT_RESPONSE": self._draw_game_response,
            "RETRY": self._draw_game_retry,
            "DEBRIEF": self._draw_game_debrief,
            "ERROR": self._draw_game_error,
        }.get(state_name, self._draw_game_error)
        renderer(surface, body, controller, t)

        if self.stand_diagnostic:
            self._draw_stand_diagnostic(surface, rect, controller)

    def _draw_game_header(self, surface, rect, controller):
        header = pygame.Rect(rect.x, rect.y, rect.width, 50)
        pygame.draw.rect(surface, (5, 15, 33), header, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_CYAN, header, width=2, border_radius=10)
        step = self._render_clipped(
            FONT_HEADER,
            STEP_LABELS.get(controller.state.value, controller.state.value),
            C_TEXT_PRIMARY,
            header.width - 36,
        )
        surface.blit(step, (header.centerx - step.get_width() // 2, header.centery - step.get_height() // 2))

    def _draw_confirmed_loadout(self, surface, body, controller):
        key_label = _approach_label(controller.selected_key_mode)
        values = (
            ("MISSÃO", controller.selected_mission.title if controller.selected_mission else "--", C_ACCENT_CYAN),
            ("CPU", f"{controller.selected_profile_mhz} MHz" if controller.selected_profile_mhz else "--", C_ACCENT_BLUE),
            ("ABORDAGEM", key_label, C_ACCENT_PURPLE),
            ("CRC APP", "LIGADO" if controller.selected_guard is GuardMode.CRC32 else "DESLIGADO" if controller.selected_guard is GuardMode.NONE else "--", C_ACCENT_GREEN),
        )
        if all(value == "--" for _, value, _ in values):
            return body
        gap = 8
        chip_w = (body.width - gap * 3) // 4
        for index, (label, value, color) in enumerate(values):
            chip = pygame.Rect(body.x + index * (chip_w + gap), body.y, chip_w, 36)
            pygame.draw.rect(surface, (5, 18, 35), chip, border_radius=5)
            pygame.draw.rect(surface, color if value != "--" else (45, 62, 80), chip, 1, border_radius=5)
            surface.blit(FONT_LABEL.render(label, True, C_TEXT_DIM), (chip.x + 8, chip.y + 10))
            rendered = self._render_clipped(FONT_LABEL, value, color if value != "--" else C_TEXT_DIM, chip.width - 86)
            surface.blit(rendered, (chip.right - rendered.get_width() - 8, chip.y + 10))
        return pygame.Rect(body.x, body.y + 43, body.width, body.height - 43)

    @staticmethod
    def _confirmation_label(controller):
        return {
            "SELECT_MISSION": "AVANÇAR",
            "SELECT_PROFILE": "CONFIRMAR ESCOLHA",
            "SELECT_KEY_MODE": "CONFIRMAR ESCOLHA",
            "SELECT_GUARD": "CONFIRMAR ESCOLHA",
            "PREPARE": "CONTINUAR",
            "PROTECT": "CONTINUAR",
            "TRANSMIT": "CONTINUAR",
            "VERIFY": "CONTINUAR",
            "DIAGNOSE": "CONFIRMAR ESCOLHA",
            "SELECT_RESPONSE": "CONFIRMAR ESCOLHA",
            "RETRY": "CONTINUAR",
            "DEBRIEF": "NOVA MISSÃO",
            "ERROR": "RECOMEÇAR",
        }.get(controller.state.value, "CONTINUAR")

    def _confirmation_hint(
        self,
        surface,
        body,
        controller,
        *,
        ready,
        waiting="",
        action="confirm",
        label=None,
    ):
        message = controller.blocked_choice_message or waiting
        if not ready:
            if message:
                color = C_ACCENT_ORANGE if controller.blocked_choice_message else C_TEXT_DIM
                self._draw_stand_centered(
                    surface,
                    FONT_SMALL,
                    message,
                    color,
                    body.centerx,
                    body.bottom - 28,
                    body.width - 80,
                    line_gap=2,
                )
            return

        width = min(520, max(300, int(body.width * 0.42)))
        rect = pygame.Rect(body.centerx - width // 2, body.bottom - 54, width, 46)
        retry = bool(controller.blocked_choice_message)
        color = C_ACCENT_ORANGE if retry else C_ACCENT_GREEN
        pygame.draw.rect(surface, (42, 28, 11) if retry else (7, 38, 32), rect, border_radius=9)
        pygame.draw.rect(surface, color, rect, width=2, border_radius=9)
        text = "TENTAR NOVAMENTE" if retry else (label or self._confirmation_label(controller))
        self._draw_stand_centered(
            surface,
            FONT_BODY,
            text,
            color,
            rect.centerx,
            rect.centery - FONT_BODY.get_height() // 2,
            rect.width - 20,
            line_gap=2,
        )
        self._investigation_action(action, rect)

    def _selected_action(self, controller):
        if not controller.pending_choice_kind or not controller.pending_choice:
            return ""
        prefixes = {
            "mission": "mission",
            "profile": "profile",
            "key_mode": "key",
            "guard": "guard",
            "diagnosis": "diagnosis",
            "response": "response",
        }
        return f"{prefixes[controller.pending_choice_kind]}:{controller.pending_choice}"

    def _draw_choice_cards(
        self,
        surface,
        body,
        controller,
        title,
        choices,
        t,
        *,
        columns=None,
        show_card_descriptions=False,
        show_selected_detail=True,
    ):
        choices = tuple(choices)
        self._draw_stand_centered(surface, FONT_TITLE, title, C_TEXT_PRIMARY, body.centerx, body.y, body.width - 50)

        columns = columns or len(choices)
        rows = math.ceil(len(choices) / columns)
        gap = 14
        hint_top = body.bottom - 58
        detail_h = 52 if show_selected_detail else 0
        detail_y = hint_top - detail_h - (8 if show_selected_detail else 0)
        cards_y = body.y + 40
        card_area_h = max(118, detail_y - cards_y - 8)
        max_card_w = (body.width - 42 - gap * (columns - 1)) // columns
        max_card_h = (card_area_h - gap * (rows - 1)) // rows
        card_size = max(112, min(max_card_w, max_card_h))
        grid_w = columns * card_size + gap * (columns - 1)
        grid_h = rows * card_size + gap * (rows - 1)
        grid_x = body.centerx - grid_w // 2
        grid_y = cards_y + max(0, (card_area_h - grid_h) // 2)
        selected_action = self._selected_action(controller)
        selected_choice = None

        for index, choice in enumerate(choices):
            col = index % columns
            row = index // columns
            card = pygame.Rect(
                grid_x + col * (card_size + gap),
                grid_y + row * (card_size + gap),
                card_size,
                card_size,
            )
            selected = choice.action == selected_action
            disabled = bool(choice.disabled_reason)
            fill = (13, 42, 58) if selected else (5, 17, 34)
            if disabled:
                fill = (28, 25, 32)
            accent = C_TEXT_DIM if disabled else choice.color
            pygame.draw.rect(surface, fill, card, border_radius=9)
            pygame.draw.rect(surface, accent, card, width=4 if selected else 2, border_radius=9)
            if selected:
                selected_choice = choice
                pulse = 0.5 + 0.5 * math.sin(t * 5.0)
                pygame.draw.rect(
                    surface,
                    tuple(int(component * (0.72 + 0.28 * pulse)) for component in C_ACCENT_GREEN),
                    card.inflate(-8, -8),
                    1,
                    border_radius=7,
                )
            icon_h = min(190, max(64, int(card.height * (0.34 if show_card_descriptions else 0.52))))
            icon_rect = pygame.Rect(card.x + 18, card.y + 18, card.width - 36, icon_h)
            draw_game_icon(
                surface,
                choice.icon,
                icon_rect,
                t,
                color=accent,
                active=selected,
                progress=0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 1.6)),
            )
            heading_y = icon_rect.bottom + 12
            heading = self._render_clipped(FONT_TITLE, choice.title, accent, card.width - 28)
            surface.blit(heading, (card.centerx - heading.get_width() // 2, heading_y))
            if show_card_descriptions:
                description_y = heading_y + heading.get_height() + 8
                if choice.card_frequency:
                    frequency = FONT_BODY.render(choice.card_frequency, True, accent)
                    surface.blit(frequency, (card.centerx - frequency.get_width() // 2, description_y))
                    description_y += frequency.get_height() + 6
                description_y = self._draw_stand_centered(
                    surface,
                    FONT_SMALL,
                    choice.summary,
                    C_TEXT_PRIMARY,
                    card.centerx,
                    description_y,
                    card.width - 30,
                    line_gap=2,
                )
                if choice.card_payload:
                    payload_top = description_y + 7
                    row_h = FONT_LABEL.get_height() + 2
                    payload = pygame.Rect(
                        card.x + 15,
                        payload_top,
                        card.width - 30,
                        len(choice.card_payload) * row_h + 12,
                    )
                    pygame.draw.rect(surface, (7, 25, 43), payload, border_radius=5)
                    pygame.draw.rect(surface, accent, payload, 1, border_radius=5)
                    for row_index, entry in enumerate(choice.card_payload):
                        field, separator, value = entry.partition("=")
                        row_y = payload.y + 6 + row_index * row_h
                        key = FONT_LABEL.render(field, True, accent)
                        rendered_value = FONT_LABEL.render(f"{separator}{value}", True, C_TEXT_PRIMARY)
                        surface.blit(key, (payload.x + 8, row_y))
                        surface.blit(rendered_value, (payload.right - rendered_value.get_width() - 8, row_y))
            if selected:
                tag = FONT_LABEL.render("SELECIONADO", True, C_ACCENT_GREEN)
                surface.blit(tag, (card.right - tag.get_width() - 8, card.y + 7))
            if not disabled:
                self._investigation_action(choice.action, card)

        detail = pygame.Rect(body.x + 22, detail_y, body.width - 44, detail_h)
        if selected_choice and show_selected_detail:
            pygame.draw.rect(surface, (4, 15, 31), detail, border_radius=6)
            pygame.draw.rect(surface, selected_choice.color, detail, 1, border_radius=6)
            self._draw_stand_centered(
                surface,
                FONT_SMALL,
                selected_choice.detail,
                C_TEXT_PRIMARY,
                detail.centerx,
                detail.y + 9,
                detail.width - 24,
                line_gap=2,
            )
        self._confirmation_hint(
            surface,
            body,
            controller,
            ready=bool(controller.pending_choice),
        )

    def _draw_game_attract(self, surface, body, controller, t):
        button_w = min(330, max(250, int(body.width * 0.28)))
        button = pygame.Rect(
            body.right - button_w - max(28, int(body.width * 0.06)),
            body.centery - 24,
            button_w,
            48,
        )
        ready = controller.ready_for_start
        color = C_ACCENT_CYAN if ready else C_TEXT_DIM
        pygame.draw.rect(surface, (7, 34, 47) if ready else (16, 24, 34), button, border_radius=10)
        pygame.draw.rect(surface, color, button, 2, border_radius=10)
        self._draw_stand_centered(
            surface,
            FONT_BODY,
            "INICIAR MISSÃO",
            color,
            button.centerx,
            button.centery - FONT_BODY.get_height() // 2,
            button.width - 20,
            line_gap=2,
        )
        if ready:
            self._investigation_action("confirm", button)

    def _draw_game_missions(self, surface, body, controller, t):
        colors = (C_ACCENT_CYAN, C_ACCENT_RED, C_ACCENT_PURPLE)
        icons = {"TELEMETRY": "telemetry", "SAFE_COMMAND": "safe_command", "CONFIG_UPDATE": "config"}
        choices = []
        for mission, color in zip(controller.config.missions, colors):
            payload = tuple(mission.payload.split("|"))
            choices.append(
                ChoiceVisual(
                    f"mission:{mission.mission_id}",
                    mission.title,
                    mission.description,
                    mission.consequence,
                    "",
                    color,
                    icons.get(mission.mission_id, "packet"),
                    card_payload=payload,
                )
            )
        self._draw_choice_cards(
            surface,
            body,
            controller,
            "Qual mensagem você quer enviar? Ela vai precisar chegar intacta!",
            choices,
            t,
            show_card_descriptions=True,
        )

    def _draw_game_profiles(self, surface, body, controller, t):
        choices = (
            ChoiceVisual(
                f"profile:{controller.config.baseline_mhz}",
                "CPU Normal",
                "Opera na frequência normal da Wisdom.",
                "",
                "",
                C_ACCENT_CYAN,
                "cpu_fast",
                card_frequency=f"{controller.config.baseline_mhz} MHz",
            ),
            ChoiceVisual(
                f"profile:{controller.config.limited_mhz}",
                "CPU Limitada",
                "Opera em ritmo reduzido.",
                "",
                "",
                C_ACCENT_PURPLE,
                "cpu_limited",
                card_frequency=f"{controller.config.limited_mhz} MHz",
            ),
        )
        self._draw_choice_cards(
            surface,
            body,
            controller,
            "Em que ritmo a Wisdom vai trabalhar?",
            choices,
            t,
            show_card_descriptions=True,
            show_selected_detail=False,
        )

    def _draw_game_key_modes(self, surface, body, controller, t):
        choices = (
            ChoiceVisual(
                "key:ECDH",
                "CLÁSSICA",
                "ECDH P-256 estabelece o segredo.",
                "Receptor e iniciador trocam pontos públicos P-256 e chegam ao mesmo segredo; HKDF deriva a chave do AES-GCM.",
                "ECDH P-256 • WOLFCRYPT",
                C_ACCENT_ORANGE,
                "classic_key",
            ),
            ChoiceVisual(
                "key:MLKEM",
                "PÓS-QUÂNTICA",
                "ML-KEM-512 estabelece o segredo.",
                "KeyGen, Encaps e Decaps usam chave pública e cápsula para chegar ao mesmo segredo; HKDF deriva a chave do AES-GCM.",
                "ML-KEM-512 • WOLFCRYPT",
                C_ACCENT_PURPLE,
                "quantum_atom",
            ),
        )
        self._draw_choice_cards(surface, body, controller, "QUAL ABORDAGEM VAI ESTABELECER O SEGREDO?", choices, t)

    def _draw_game_guards(self, surface, body, controller, t):
        choices = (
            ChoiceVisual(
                "guard:NONE",
                "SEM CRC DA APLICAÇÃO",
                "O plaintext segue direto ao AES-GCM.",
                "Uma corrupção posterior à verificação da tag pode ficar silenciosa. AES-GCM continua ativo.",
                "0 B EXTRA • GCM CONTINUA ATIVO",
                C_ACCENT_ORANGE,
                "no_crc",
            ),
            ChoiceVisual(
                "guard:CRC32",
                "CRC32 DA APLICAÇÃO",
                "Quatro bytes acompanham o plaintext.",
                "O CRC32 é anexado antes da cifra e ajuda a localizar corrupção de memória; CRC não autentica.",
                "+4 B • DETECTA, NÃO AUTENTICA",
                C_ACCENT_GREEN,
                "crc32",
            ),
        )
        self._draw_choice_cards(surface, body, controller, "ADICIONAR UM GUARDIÃO AO PLAINTEXT?", choices, t)

    def _stage_status(self, surface, body, controller, *, title, subtitle):
        title_surface = self._render_clipped(FONT_TITLE, title, C_TEXT_PRIMARY, body.width - 30)
        surface.blit(title_surface, (body.x + 8, body.y + 3))
        subtitle_surface = self._render_clipped(FONT_SMALL, subtitle, C_TEXT_DIM, body.width - 30)
        surface.blit(subtitle_surface, (body.x + 8, body.y + 34))
        measurement = controller.current_stage_measurement
        if controller.pending is not None:
            ready = False
            waiting = "PROCESSANDO…"
        elif measurement is None:
            ready = False
            waiting = "AGUARDANDO RESULTADO…"
        elif not controller.animation_complete:
            ready = False
            waiting = f"REPRODUZINDO ETAPA • {controller.animation_progress() * 100:.0f}%"
        else:
            ready = True
            waiting = ""
        self._confirmation_hint(surface, body, controller, ready=ready, waiting=waiting)
        return measurement

    def _draw_waiting_hardware(self, surface, visual, controller, t):
        pygame.draw.rect(surface, (4, 16, 33), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_ORANGE, visual, 2, border_radius=10)
        descriptions = {
            "PREPARE": ("payload", "ORGANIZANDO A MENSAGEM E O CRC ESCOLHIDO"),
            "PROTECT": ("aes_gcm", "CRIANDO A SESSÃO E PROTEGENDO A MENSAGEM"),
            "TRANSMIT": ("satellite", "ENVIANDO O PACOTE PELO ENLACE"),
            "VERIFY": ("channel", "VERIFICANDO QUADRO, TAG E CONTEÚDO"),
            "RETRY": ("retry", "PROTEGENDO E TRANSMITINDO NOVAMENTE"),
        }
        icon_name, operation = descriptions.get(controller.state.value, ("satellite", "EXECUTANDO A ETAPA"))
        icon = pygame.Rect(visual.centerx - 72, visual.y + 20, 144, min(104, visual.height - 100))
        draw_game_icon(surface, icon_name, icon, t, color=C_ACCENT_ORANGE, active=True, progress=0.45)
        text = "PROCESSANDO ETAPA" if controller.pending is not None else "PREPARANDO REPLAY"
        self._draw_stand_centered(surface, FONT_HEADER, text, C_ACCENT_ORANGE, visual.centerx, icon.bottom + 8, visual.width - 30)
        self._draw_stand_centered(surface, FONT_BODY, operation, C_TEXT_PRIMARY, visual.centerx, icon.bottom + 38, visual.width - 50)

    def _replay_rect(self, body):
        height = min(560, max(120, body.height - 139))
        return pygame.Rect(body.x + 18, body.y + 65, body.width - 36, height)

    def _draw_replay_label(self, surface, visual):
        if self.stand_controller.animation_complete:
            text = "REPLAY CONCLUÍDO • SEGURE E ARRASTE A MENSAGEM PARA REVER"
            color = C_ACCENT_GREEN
        else:
            text = "REPLAY AUTOMÁTICO • ANIMAÇÃO DIDÁTICA EM TEMPO AMPLIADO"
            color = C_ACCENT_ORANGE
        label = self._render_clipped(FONT_LABEL, text, color, visual.width - 24)
        surface.blit(label, (visual.x + 12, visual.y + 9))

    @staticmethod
    def _timeline_ratio(station_progresses, progress):
        values = tuple(station_progresses) or (0.0, 1.0)
        progress = max(0.0, min(1.0, float(progress)))
        if len(values) == 1 or progress <= values[0]:
            return 0.0
        for index, right in enumerate(values[1:], start=1):
            left = values[index - 1]
            if progress <= right:
                local = (progress - left) / max(1e-9, right - left)
                return ((index - 1) + local) / (len(values) - 1)
        return 1.0

    def _replay_content_rect(self, visual):
        narrative_top = visual.bottom - 153
        return pygame.Rect(visual.x + 16, visual.y + 34, visual.width - 32, max(72, narrative_top - visual.y - 40))

    def _cue_evidence(self, controller, cue, measurement):
        if cue.measured_us is not None:
            return "OPERAÇÃO EXECUTADA E VALIDADA PELA WISDOM"
        state = controller.state.value
        if state == "PREPARE":
            return "WISDOM VALIDOU O PAYLOAD E O CRC ESCOLHIDO"
        if state == "TRANSMIT" and controller.selection and cue.key == "bit":
            selection = controller.selection
            return (
                f"A39 REAL: BYTE {selection.byte_index} • BIT {selection.bit_position % 8} • "
                f"MÁSCARA 0x{selection.bit_mask:02X}"
            )
        if state == "VERIFY" and controller.result:
            rows = {label: value for label, value, _color, _icon in self._evidence_rows(controller.result)}
            label = {"frame": "CRC DO QUADRO", "gcm": "TAG AES-GCM", "app": "CRC DA APLICAÇÃO"}.get(cue.key)
            return f"RESULTADO REAL: {label} = {rows.get(label, '--')}"
        if state == "RETRY" and controller.retry_result:
            raw = controller.retry_result.raw_response
            values = {
                "payload": f"MESMO PAYLOAD = {raw.get('same_payload', '--')}",
                "keygen": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "encaps": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "decaps": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "ecdh_setup": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "ecdh_initiator": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "ecdh_responder": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "kdf": f"CHAVE NOVA = {raw.get('fresh_key', '--')}",
                "fresh_nonce": f"NONCE NOVO = {raw.get('fresh_nonce', '--')}",
                "protect": "PACOTE PROTEGIDO NOVAMENTE",
                "delivered": f"RESULTADO = {controller.retry_result.result}",
            }
            return values.get(cue.key, f"RESULTADO REAL: {controller.retry_result.result}")
        return "ETAPA EXECUTADA E VALIDADA PELA WISDOM"

    def _draw_cue_explanation(self, surface, visual, cue, evidence):
        card = pygame.Rect(visual.x + 14, visual.bottom - 151, visual.width - 28, 82)
        pygame.draw.rect(surface, (7, 25, 43), card, border_radius=7)
        pygame.draw.rect(surface, cue.color, card, 2, border_radius=7)
        title = self._render_clipped(FONT_BODY, f"AGORA: {cue.short_label}", cue.color, card.width // 2)
        surface.blit(title, (card.x + 12, card.y + 7))
        proof = self._render_clipped(FONT_LABEL, evidence, C_ACCENT_GREEN, card.width // 2 - 18)
        surface.blit(proof, (card.right - proof.get_width() - 12, card.y + 10))
        pygame.draw.line(surface, (38, 68, 91), (card.x + 10, card.y + 31), (card.right - 10, card.y + 31), 1)

        left_w = int(card.width * 0.23)
        right_w = left_w
        center_w = card.width - left_w - right_w - 30
        columns = (
            (card.x + 10, left_w, "ENTRA", cue.input_label, C_ACCENT_CYAN),
            (card.x + left_w + 15, center_w, "O QUE ACONTECE", cue.explanation, cue.color),
            (card.right - right_w - 10, right_w, "SAI", cue.output_label, C_ACCENT_GREEN),
        )
        for x, width, heading, text, color in columns:
            surface.blit(FONT_LABEL.render(heading, True, color), (x, card.y + 38))
            self._draw_wrapped_text(
                surface,
                FONT_LABEL,
                text,
                C_TEXT_PRIMARY,
                x,
                card.y + 55,
                width,
                line_spacing=15,
                max_lines=2,
            )

    def _draw_timeline_nodes(self, surface, visual, timeline, progress):
        if not timeline.cues:
            return
        controller = self.stand_controller
        active = timeline.active(progress)
        self._draw_cue_explanation(
            surface,
            visual,
            active,
            self._cue_evidence(controller, active, controller.current_stage_measurement),
        )

        left, right = visual.x + 54, visual.right - 54
        y = visual.bottom - 24
        pygame.draw.line(surface, (36, 68, 94), (left, y), (right, y), 2)
        values = timeline.station_progresses
        stations = (("ENTRADA", C_ACCENT_CYAN),) + tuple((cue.short_label, cue.color) for cue in timeline.cues)
        for index, ((label_text, station_color), station_progress) in enumerate(zip(stations, values)):
            ratio = index / max(1, len(stations) - 1)
            x = int(left + (right - left) * ratio)
            completed = progress >= station_progress
            color = C_ACCENT_GREEN if completed else station_color if index and stations[index][0] == active.short_label else C_TEXT_DIM
            pygame.draw.circle(surface, (5, 18, 35), (x, y), 8)
            pygame.draw.circle(surface, color, (x, y), 8, 2)
            max_label = max(54, (right - left) // len(stations) - 5)
            label = self._render_clipped(FONT_LABEL, label_text, color, max_label)
            label_x = max(visual.x + 5, min(x - label.get_width() // 2, visual.right - label.get_width() - 5))
            surface.blit(label, (label_x, y + 9))

        ratio = self._timeline_ratio(values, progress)
        packet_x = int(left + (right - left) * ratio)
        packet = pygame.Rect(packet_x - 38, y - 40, 76, 28)
        selected_bit = None
        if controller.state.value == "TRANSMIT" and controller.selection:
            bit_stage = next((cue for cue in timeline.cues if cue.key == "bit"), None)
            if bit_stage is not None and progress >= bit_stage.start:
                selected_bit = controller.selection.bit_position % 8
        packet_color = C_TEXT_PRIMARY if self.replay_interaction.dragging else active.color
        draw_packet(
            surface,
            packet,
            color=packet_color,
            t=controller.last_clock_at,
            selected_bit=selected_bit,
            sealed=controller.state.value != "PREPARE",
        )
        if self.replay_interaction.review_enabled:
            pygame.draw.rect(surface, C_ACCENT_GREEN, packet.inflate(8, 8), 2, border_radius=8)
        pygame.draw.line(surface, packet_color, (packet.centerx, packet.bottom + 3), (packet.centerx, y - 9), 2)
        self.replay_interaction.register_geometry(
            pygame.Rect(left, y - 2, right - left, 4),
            packet,
            values,
        )

    def _draw_game_prepare(self, surface, body, controller, t):
        source = "Wisdom" if controller.mode == "hardware" else "fixture de teste"
        measurement = self._stage_status(
            surface,
            body,
            controller,
            title="PREPARAR A MENSAGEM",
            subtitle=f"A {source} aplicou o perfil, serializou o payload e tratou o CRC escolhido.",
        )
        visual = self._replay_rect(body)
        if measurement is None:
            self._draw_waiting_hardware(surface, visual, controller, t)
            return
        pygame.draw.rect(surface, (4, 17, 34), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_CYAN, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_didactic_timeline(
            "PREPARE",
            measurement,
            key_mode=controller.selected_key_mode,
            guard=controller.selected_guard,
        )
        progress = self.replay_progress(timeline)
        content = self._replay_content_rect(visual)
        data = controller.selected_mission.payload_bytes if controller.selected_mission else b""
        serialize_cue = timeline.cues[0]
        serialize_progress = timeline.cue_progress(progress, serialize_cue)
        if progress >= serialize_cue.end:
            serialize_progress = 1.0
        visible = min(len(data), max(0, math.ceil(len(data) * serialize_progress)))
        max_columns = min(20, max(8, content.width // 42))
        tile_w = min(34, (content.width - 20) // max_columns)
        tile_h = 27
        rows = max(1, math.ceil(len(data) / max_columns))
        start_y = content.y + 5
        for index, byte in enumerate(data):
            col, row = index % max_columns, index // max_columns
            x = content.centerx - (min(max_columns, len(data)) * tile_w) // 2 + col * tile_w
            tile = pygame.Rect(x, start_y + row * (tile_h + 5), tile_w - 4, tile_h)
            color = C_ACCENT_CYAN if index < visible else (34, 54, 72)
            pygame.draw.rect(surface, (8, 30, 46), tile, border_radius=3)
            pygame.draw.rect(surface, color, tile, 1, border_radius=3)
            value = FONT_LABEL.render(f"{byte:02X}" if index < visible else "..", True, color)
            surface.blit(value, (tile.centerx - value.get_width() // 2, tile.y + 7))
        footer_y = start_y + rows * (tile_h + 5) + 5
        if controller.selected_guard is GuardMode.CRC32:
            crc_cue = next(cue for cue in timeline.cues if cue.key == "app_crc")
            crc_ready = progress >= crc_cue.end
            crc_active = progress >= crc_cue.start
            crc_color = C_ACCENT_GREEN if crc_ready else C_ACCENT_ORANGE if crc_active else C_TEXT_DIM
            crc = pygame.Rect(content.centerx - 98, footer_y, 196, 35)
            pygame.draw.rect(surface, (8, 46, 37) if crc_ready else (24, 30, 38), crc, border_radius=5)
            pygame.draw.rect(surface, crc_color, crc, 2 if crc_active else 1, border_radius=5)
            crc_text = "+ CRC32 ANEXADO (4 B)" if crc_ready else "CALCULANDO CRC32..." if crc_active else "CRC32 SERÁ ANEXADO"
            text = FONT_LABEL.render(crc_text, True, crc_color)
        else:
            crc = pygame.Rect(content.centerx - 98, footer_y, 196, 35)
            pygame.draw.rect(surface, (27, 29, 34), crc, border_radius=5)
            pygame.draw.rect(surface, C_TEXT_DIM, crc, 1, border_radius=5)
            text = FONT_LABEL.render("CRC DA APLICAÇÃO AUSENTE", True, C_TEXT_DIM)
        surface.blit(text, (crc.centerx - text.get_width() // 2, crc.y + 10))
        self._draw_timeline_nodes(surface, visual, timeline, progress)

    def _draw_game_protect(self, surface, body, controller, t):
        if _enum_value(controller.selected_key_mode) == "MLKEM":
            subtitle = "ML-KEM-512 estabelece o segredo; HKDF-SHA256 deriva a chave do AES-128-GCM."
        else:
            subtitle = "ECDH P-256 estabelece o segredo; HKDF-SHA256 deriva a chave do AES-128-GCM."
        measurement = self._stage_status(
            surface,
            body,
            controller,
            title="ESTABELECER A CHAVE E PROTEGER",
            subtitle=subtitle,
        )
        visual = self._replay_rect(body)
        if measurement is None:
            self._draw_waiting_hardware(surface, visual, controller, t)
            return
        pygame.draw.rect(surface, (4, 17, 34), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_PURPLE, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_didactic_timeline(
            "PROTECT",
            measurement,
            key_mode=controller.selected_key_mode,
            guard=controller.selected_guard,
        )
        progress = self.replay_progress(timeline)
        active = timeline.active(progress)
        cue_progress = timeline.cue_progress(progress, active)
        content = self._replay_content_rect(visual)
        center_y = content.centery - 8
        scale = min(1.15, max(0.72, content.height / 150.0))
        packet_w, packet_h = int(170 * scale), int(50 * scale)
        input_rect = pygame.Rect(content.x + 26, center_y - packet_h // 2, packet_w, packet_h)
        output_rect = pygame.Rect(content.right - packet_w - 26, center_y - packet_h // 2, packet_w, packet_h)
        draw_packet(surface, input_rect, color=C_ACCENT_CYAN, t=t, sealed=False)
        output_color = C_ACCENT_GREEN if progress >= 0.999 else C_TEXT_DIM
        draw_packet(surface, output_rect, color=output_color, t=t, sealed=progress >= 0.999)
        input_label = FONT_LABEL.render("MENSAGEM DE ENTRADA", True, C_ACCENT_CYAN)
        output_label = FONT_LABEL.render("PACOTE PROTEGIDO AO FINAL", True, output_color)
        surface.blit(input_label, (input_rect.centerx - input_label.get_width() // 2, input_rect.y - 18))
        surface.blit(output_label, (output_rect.centerx - output_label.get_width() // 2, output_rect.y - 18))
        pygame.draw.line(surface, active.color, input_rect.midright, (visual.centerx - 68, center_y), 2)
        pygame.draw.line(surface, active.color, (visual.centerx + 68, center_y), output_rect.midleft, 2)
        icon_w, icon_h = int(144 * scale), int(120 * scale)
        icon_rect = pygame.Rect(content.centerx - icon_w // 2, center_y - icon_h // 2 - 8, icon_w, icon_h)
        draw_game_icon(
            surface,
            active.icon,
            icon_rect,
            t,
            color=active.color,
            active=True,
            progress=cue_progress,
        )
        label = active.label
        self._draw_stand_centered(surface, FONT_BODY, label, active.color, content.centerx, icon_rect.bottom - 2, content.width - 430)
        self._draw_timeline_nodes(surface, visual, timeline, progress)

    def _draw_game_transmit(self, surface, body, controller, t):
        measurement = self._stage_status(
            surface,
            body,
            controller,
            title="TRANSMITIR PELO ENLACE",
            subtitle="O incidente real já foi aplicado; sua causa permanece oculta até o relatório.",
        )
        visual = self._replay_rect(body)
        if measurement is None:
            self._draw_waiting_hardware(surface, visual, controller, t)
            return
        pygame.draw.rect(surface, (3, 15, 31), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_BLUE, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_didactic_timeline("TRANSMIT", measurement, key_mode=controller.selected_key_mode, guard=controller.selected_guard)
        progress = self.replay_progress(timeline)
        active = timeline.active(progress)
        content = self._replay_content_rect(visual)
        left = (content.x + 88, content.bottom - 45)
        satellite = (content.centerx, content.y + 45)
        right = (content.right - 88, content.bottom - 45)
        draw_game_icon(surface, "ground", pygame.Rect(left[0] - 46, left[1] - 44, 92, 88), t, color=C_ACCENT_CYAN)
        draw_game_icon(surface, "satellite", pygame.Rect(satellite[0] - 55, satellite[1] - 42, 110, 84), t, color=C_ACCENT_BLUE, active=True)
        draw_game_icon(surface, "ground", pygame.Rect(right[0] - 46, right[1] - 44, 92, 88), t + 0.4, color=C_ACCENT_GREEN)
        link_progress = min(1.0, progress * 2)
        draw_signal_link(surface, left, satellite, t, progress=link_progress)
        draw_signal_link(surface, satellite, right, t + 0.5, color=C_ACCENT_BLUE, progress=max(0.0, progress * 2 - 1))
        path_progress = max(0.0, min(1.0, progress))
        if path_progress < 0.5:
            local = path_progress * 2
            packet_center = (int(left[0] + (satellite[0] - left[0]) * local), int(left[1] + (satellite[1] - left[1]) * local))
        else:
            local = (path_progress - 0.5) * 2
            packet_center = (int(satellite[0] + (right[0] - satellite[0]) * local), int(satellite[1] + (right[1] - satellite[1]) * local))
        bit_cue = next(cue for cue in timeline.cues if cue.key == "bit")
        selected_bit = (
            controller.selection.bit_position % 8
            if controller.selection and progress >= bit_cue.start
            else None
        )
        draw_packet(surface, pygame.Rect(packet_center[0] - 47, packet_center[1] - 18, 94, 36), color=active.color, t=t, selected_bit=selected_bit, sealed=True)
        if 0.56 <= progress <= 0.78:
            radius = int(15 + 9 * (0.5 + 0.5 * math.sin(t * 8)))
            pygame.draw.circle(surface, C_ACCENT_RED, packet_center, radius, 2)
            marker = FONT_LABEL.render("EVENTO OCULTO", True, C_ACCENT_RED)
            surface.blit(marker, (packet_center[0] - marker.get_width() // 2, packet_center[1] + 25))
        self._draw_timeline_nodes(surface, visual, timeline, progress)

    @staticmethod
    def _indicator_value(present, checked, match):
        if not present:
            return "NÃO INSTALADO", C_TEXT_DIM
        if not checked:
            return "NÃO VERIFICADO", C_ACCENT_ORANGE
        return ("OK", C_ACCENT_GREEN) if match else ("FALHOU", C_ACCENT_RED)

    def _evidence_rows(self, result):
        if result is None:
            return (
                ("CRC DO QUADRO", "AGUARDANDO", C_TEXT_DIM, "channel"),
                ("TAG AES-GCM", "AGUARDANDO", C_TEXT_DIM, "aes_gcm"),
                ("CRC DA APLICAÇÃO", "AGUARDANDO", C_TEXT_DIM, "crc32"),
            )
        app_text, app_color = self._indicator_value(result.app_crc_present, result.app_crc_checked, result.app_crc_match)
        return (
            ("CRC DO QUADRO", "OK" if result.frame_crc_match else "FALHOU", C_ACCENT_GREEN if result.frame_crc_match else C_ACCENT_RED, "channel"),
            ("TAG AES-GCM", "OK" if result.aead_match else "FALHOU", C_ACCENT_GREEN if result.aead_match else C_ACCENT_RED, "aes_gcm"),
            ("CRC DA APLICAÇÃO", app_text, app_color, "crc32" if result.app_crc_present else "no_crc"),
        )

    def _draw_evidence(self, surface, body, result, *, y, reveal_count=3, t=0.0, height=82):
        rows = self._evidence_rows(result)
        gap = 14
        metric_w = (body.width - 50 - gap * 2) // 3
        for index, (label, value, color, icon) in enumerate(rows):
            shown = index < reveal_count
            card = pygame.Rect(body.x + 25 + index * (metric_w + gap), y, metric_w, height)
            pygame.draw.rect(surface, (5, 18, 35), card, border_radius=7)
            pygame.draw.rect(surface, color if shown else (38, 57, 78), card, 2 if shown else 1, border_radius=7)
            icon_size = min(100, max(58, int(height * 0.32)), height - 14)
            draw_game_icon(surface, icon, pygame.Rect(card.x + 8, card.centery - icon_size // 2, icon_size + 10, icon_size), t, color=color, active=shown)
            label_surface = self._render_clipped(FONT_LABEL, label, C_TEXT_DIM, card.width - icon_size - 28)
            status = value if shown else "VERIFICANDO..."
            status_color = color if shown else C_TEXT_DIM
            status_surface = self._render_clipped(FONT_BODY, status, status_color, card.width - icon_size - 28)
            surface.blit(label_surface, (card.x + icon_size + 20, card.y + 17))
            surface.blit(status_surface, (card.x + icon_size + 20, card.y + 42))

    def _draw_game_verify(self, surface, body, controller, t):
        result = self._stage_status(
            surface,
            body,
            controller,
            title="VERIFICAR EM TRÊS CAMADAS",
            subtitle="Cada portal usa o resultado validado da Wisdom; nenhum indicador é sorteado.",
        )
        visual = self._replay_rect(body)
        if result is None:
            self._draw_waiting_hardware(surface, visual, controller, t)
            return
        pygame.draw.rect(surface, (4, 17, 34), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_GREEN, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_didactic_timeline("VERIFY", result, key_mode=controller.selected_key_mode, guard=controller.selected_guard)
        progress = self.replay_progress(timeline)
        reveal_count = sum(1 for cue in timeline.cues if progress > cue.start or progress >= 1.0)
        content = self._replay_content_rect(visual)
        gate_y = content.y + 2
        gate_h = max(78, content.height - 4)
        self._draw_evidence(surface, visual, result, y=gate_y, reveal_count=reveal_count, t=t, height=gate_h)
        self._draw_timeline_nodes(surface, visual, timeline, progress)

    def _draw_game_diagnose(self, surface, body, controller, t):
        self._draw_stand_centered(surface, FONT_TITLE, "LEIA AS EVIDÊNCIAS: ONDE A MENSAGEM MUDOU?", C_TEXT_PRIMARY, body.centerx, body.y, body.width - 50)
        self._draw_evidence(surface, body, controller.result, y=body.y + 35, t=t, height=72)
        choices = (
            ChoiceVisual(
                "diagnosis:CHANNEL",
                "CANAL",
                "O quadro mudou no enlace.",
                "O CRC do quadro localiza alterações durante armazenamento ou transmissão.",
                "PISTA: CRC DO QUADRO",
                C_ACCENT_CYAN,
                "channel",
            ),
            ChoiceVisual(
                "diagnosis:AUTH",
                "ADULTERAÇÃO",
                "A autenticação não fechou.",
                "Um CRC sem chave pode ser recalculado; a tag GCM exige a chave secreta.",
                "PISTA: TAG AES-GCM",
                C_ACCENT_RED,
                "tamper",
            ),
            ChoiceVisual(
                "diagnosis:MEMORY",
                "MEMÓRIA",
                "O plaintext mudou no receptor.",
                "A alteração ocorreu depois da tag; o CRC da aplicação observa esse conteúdo.",
                "PISTA: CRC DA APLICAÇÃO",
                C_ACCENT_PURPLE,
                "memory",
            ),
        )
        choice_body = pygame.Rect(body.x, body.y + 112, body.width, body.height - 112)
        self._draw_choice_cards(surface, choice_body, controller, "ESCOLHA SUA HIPÓTESE — A CAUSA AINDA ESTÁ OCULTA", choices, t)

    def _draw_game_response(self, surface, body, controller, t):
        result = controller.result
        status = result.result if result else "SEM RESULTADO"
        self._draw_stand_centered(surface, FONT_TITLE, "VOCÊ ESTÁ NO COMANDO: QUAL É A RESPOSTA?", C_TEXT_PRIMARY, body.centerx, body.y, body.width - 50)
        self._draw_stand_centered(surface, FONT_BODY, f"VERIFICAÇÃO REAL: {status}", C_ACCENT_ORANGE, body.centerx, body.y + 32, body.width - 70)
        accept_blocked = bool(result and result.cryptographically_rejected)
        choices = (
            ChoiceVisual(
                "response:ACCEPT",
                "ACEITAR",
                "Entregar o conteúdo aprovado.",
                "Só é permitido quando o protocolo não rejeitou criptograficamente o pacote.",
                "ENTREGA IMEDIATA",
                C_ACCENT_GREEN,
                "accept",
                "PACOTE REJEITADO: ACEITAR ESTÁ BLOQUEADO" if accept_blocked else "",
            ),
            ChoiceVisual(
                "response:RETRY",
                "RETRANSMITIR",
                "Executar uma nova proteção real.",
                "O mesmo payload recebe material criptográfico novo e segue sem falha injetada.",
                "MESMO PAYLOAD • CHAVE E NONCE NOVOS",
                C_ACCENT_CYAN,
                "retry",
            ),
            ChoiceVisual(
                "response:SAFE_MODE",
                "MODO SEGURO",
                "Não entregar o pacote.",
                "A missão solicita uma resposta conservadora sem aceitar conteúdo rejeitado.",
                "DECISÃO OPERACIONAL CONSERVADORA",
                C_ACCENT_PURPLE,
                "safe",
            ),
        )
        choice_body = pygame.Rect(body.x, body.y + 57, body.width, body.height - 57)
        self._draw_choice_cards(surface, choice_body, controller, "ESCOLHA A AÇÃO", choices, t)
        if controller.blocked_choice_message:
            warning = self._render_clipped(FONT_LABEL, controller.blocked_choice_message, C_ACCENT_RED, body.width - 80)
            surface.blit(warning, (body.centerx - warning.get_width() // 2, body.bottom - 122))

    def _draw_game_retry(self, surface, body, controller, t):
        result = self._stage_status(
            surface,
            body,
            controller,
            title="RETRANSMISSÃO REAL",
            subtitle="Mesmo payload, sem falha injetada, com nova chave de sessão e novo nonce.",
        )
        visual = self._replay_rect(body)
        if result is None:
            self._draw_waiting_hardware(surface, visual, controller, t)
            return
        pygame.draw.rect(surface, (4, 17, 34), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_GREEN, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_didactic_timeline("RETRY", result, key_mode=controller.selected_key_mode, guard=controller.selected_guard)
        progress = self.replay_progress(timeline)
        active = timeline.active(progress)
        cue_progress = timeline.cue_progress(progress, active)
        content = self._replay_content_rect(visual)
        scale = min(1.15, max(0.75, content.height / 150.0))
        icon_w, icon_h = int(180 * scale), int(118 * scale)
        icon_rect = pygame.Rect(content.centerx - icon_w // 2, content.centery - icon_h // 2 - 8, icon_w, icon_h)
        draw_game_icon(surface, active.icon, icon_rect, t, color=active.color, active=True, progress=cue_progress)
        self._draw_stand_centered(surface, FONT_HEADER, active.label, active.color, content.centerx, icon_rect.bottom - 2, content.width - 100)
        self._draw_timeline_nodes(surface, visual, timeline, progress)

    @staticmethod
    def _incident_public_text(incident):
        return {
            IncidentScenario.CHANNEL_BITFLIP: ("CORRUPÇÃO NO CANAL", "O quadro mudou sem atualizar o CRC transmitido.", "channel"),
            IncidentScenario.TAMPER: ("ADULTERAÇÃO", "O CRC sem chave foi recalculado, mas a tag GCM permaneceu inválida.", "tamper"),
            IncidentScenario.RX_MEMORY: ("CORRUPÇÃO NA MEMÓRIA", "O plaintext mudou depois que a tag GCM já havia sido validada.", "memory"),
            IncidentScenario.NORMAL: ("CONTROLE NORMAL", "Nenhuma falha foi aplicada.", "accept"),
        }.get(incident, ("INCIDENTE INDISPONÍVEL", "", "bit"))

    def _draw_game_debrief(self, surface, body, controller, t):
        if controller.end_receipt is None or not controller.animation_complete:
            pygame.draw.rect(surface, (4, 16, 33), pygame.Rect(body.x + 100, body.y + 45, body.width - 200, body.height - 135), border_radius=11)
            draw_game_icon(surface, "satellite", pygame.Rect(body.centerx - 90, body.y + 65, 180, 130), t, color=C_ACCENT_CYAN)
            self._draw_stand_centered(surface, FONT_LARGE, "ENCERRANDO A SESSÃO", C_ACCENT_CYAN, body.centerx, body.y + 198, body.width - 100)
            self._draw_stand_centered(
                surface,
                FONT_BODY,
                "O incidente só será revelado após GAME_END confirmar limpeza da sessão e restauração do perfil.",
                C_TEXT_DIM,
                body.centerx,
                body.y + 248,
                body.width - 150,
            )
            self._confirmation_hint(surface, body, controller, ready=False, waiting="FINALIZANDO…")
            return

        incident_title, incident_detail, incident_icon = self._incident_public_text(controller.incident)
        verdict = "DIAGNÓSTICO CONSISTENTE" if controller.diagnosis_correct else "HIPÓTESE REVISADA PELAS EVIDÊNCIAS"
        verdict_color = C_ACCENT_GREEN if controller.diagnosis_correct else C_ACCENT_ORANGE
        self._draw_stand_centered(surface, FONT_TITLE, verdict, verdict_color, body.centerx, body.y, body.width - 50)
        self._draw_stand_centered(
            surface,
            FONT_BODY,
            f"INCIDENTE REVELADO: {incident_title} • {incident_detail}",
            C_ACCENT_PURPLE,
            body.centerx,
            body.y + 31,
            body.width - 70,
        )

        result = controller.result
        delivery = controller.retry_result.result if controller.retry_result else (result.result if result else "--")
        elapsed = sum(item.elapsed_us for item in controller.stage_measurements.values())
        elapsed += (result.elapsed_us if result else 0) + (controller.retry_result.elapsed_us if controller.retry_result else 0)
        measured_result = controller.retry_result or result
        bytes_total = measured_result.bytes_total if measured_result else 0
        min_heap = measured_result.min_heap if measured_result else 0
        approach = _approach_label(controller.selected_key_mode)
        badges = (
            ("ABORDAGEM", approach, C_ACCENT_PURPLE),
            ("ENTREGA", delivery, C_ACCENT_GREEN if delivery == "DELIVERED" else C_ACCENT_ORANGE),
            ("SEGURANÇA", result.result if result else "--", C_ACCENT_CYAN),
            ("RECURSOS DESTA PARTIDA", f"{_format_elapsed(elapsed)} • {bytes_total} B • {min_heap / 1024:.1f} KiB mín.", verdict_color),
        )
        badge_gap = 8
        badge_w = (body.width - 46 - badge_gap * 3) // 4
        for index, (label, value, color) in enumerate(badges):
            x = body.x + 23 + index * (badge_w + badge_gap)
            self._draw_overlay_metric_box(surface, label, value, x, body.y + 62, badge_w, 52, color)

        if controller.incident is IncidentScenario.RX_MEMORY:
            counterfactual = (
                "COM CRC32, ESTA CORRUPÇÃO DE MEMÓRIA SERIA DETECTADA."
                if controller.selected_guard is GuardMode.NONE
                else "SEM CRC32, ESTA CORRUPÇÃO DE MEMÓRIA SERIA SILENCIOSA."
            )
        else:
            counterfactual = "CRC32 NÃO AUTENTICA: A TAG AES-GCM CONTINUA ESSENCIAL."
        self._draw_stand_centered(surface, FONT_LABEL, counterfactual, C_ACCENT_ORANGE, body.centerx, body.y + 118, body.width - 90)

        available_h = max(220, body.height - 205)
        visual_h = min(470, available_h)
        visual = pygame.Rect(
            body.x + 18,
            body.y + 139 + max(0, (available_h - visual_h) // 2),
            body.width - 36,
            visual_h,
        )
        pygame.draw.rect(surface, (4, 17, 34), visual, border_radius=10)
        pygame.draw.rect(surface, C_ACCENT_CYAN, visual, 2, border_radius=10)
        self._draw_replay_label(surface, visual)
        timeline = build_mission_review_timeline(controller.stage_measurements, controller.result, controller.retry_result)
        progress = self.replay_progress(timeline)
        active = timeline.active(progress)
        content = self._replay_content_rect(visual)
        gap = 7
        node_w = (content.width - gap * (len(timeline.cues) - 1)) // len(timeline.cues)
        for index, cue in enumerate(timeline.cues):
            node = pygame.Rect(content.x + index * (node_w + gap), content.y + 2, node_w, content.height - 4)
            selected = cue is active
            pygame.draw.rect(surface, (8, 29, 47) if selected else (5, 19, 35), node, border_radius=6)
            pygame.draw.rect(surface, cue.color if selected else (42, 64, 82), node, 2 if selected else 1, border_radius=6)
            icon_h = max(40, min(100, int(node.height * 0.55)))
            icon_y = node.y + max(3, (node.height - icon_h - 20) // 2)
            draw_game_icon(surface, cue.icon, pygame.Rect(node.x + 7, icon_y, node.width - 14, icon_h), t, color=cue.color, active=selected)
            label = self._render_clipped(FONT_LABEL, cue.short_label, cue.color if selected else C_TEXT_DIM, node.width - 10)
            surface.blit(label, (node.centerx - label.get_width() // 2, node.bottom - 19))
        self._draw_timeline_nodes(surface, visual, timeline, progress)
        self._confirmation_hint(surface, body, controller, ready=True, waiting="")

    def _draw_game_error(self, surface, body, controller, t):
        pulse = 0.68 + 0.32 * math.sin(t * 4.0)
        color = tuple(int(component * pulse) for component in C_ACCENT_RED)
        card = pygame.Rect(body.centerx - min(430, body.width // 2 - 40), body.y + 42, min(860, body.width - 80), body.height - 140)
        pygame.draw.rect(surface, (28, 7, 19), card, border_radius=11)
        pygame.draw.rect(surface, color, card, 3, border_radius=11)
        draw_game_icon(surface, "tamper", pygame.Rect(card.centerx - 85, card.y + 18, 170, 105), t, color=color, active=True)
        self._draw_stand_centered(surface, FONT_LARGE, "PARTIDA INTERROMPIDA", color, card.centerx, card.y + 123, card.width - 40)
        self._draw_stand_centered(
            surface,
            FONT_BODY,
            controller.error_message or "Erro de protocolo.",
            C_TEXT_PRIMARY,
            card.centerx,
            card.y + 176,
            card.width - 60,
        )
        self._draw_stand_centered(
            surface,
            FONT_SMALL,
            "A sessão e os resultados anteriores foram apagados. Um novo HELLO STAGED_V1 é obrigatório.",
            C_TEXT_DIM,
            card.centerx,
            card.bottom - 55,
            card.width - 70,
        )
        ready = controller.ready and controller.fresh_handshake_since_error
        self._confirmation_hint(
            surface,
            body,
            controller,
            ready=ready,
            waiting="AGUARDANDO RECONEXÃO…",
        )


__all__ = ("InvestigationPresentationMixin",)
