"""Procedural art, act mapping and measured didactic timelines for the game."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping

import pygame

from pqc_sat.ui.theme import (
    C_ACCENT_BLUE,
    C_ACCENT_CYAN,
    C_ACCENT_GREEN,
    C_ACCENT_ORANGE,
    C_ACCENT_PURPLE,
    C_ACCENT_RED,
    C_PANEL_BORDER,
    C_SAT_BODY,
    C_SAT_GOLD,
    C_SAT_PANEL_BLUE,
    C_SAT_PANEL_DARK,
    C_TEXT_DIM,
    C_TEXT_PRIMARY,
    FONT_LABEL,
    FONT_SMALL,
)


class GameAct(str, Enum):
    BRIEFING = "BRIEFING"
    LOADOUT = "LOADOUT"
    OPERATION = "OPERATION"
    COMMAND = "COMMAND"


ACT_LABELS = {
    GameAct.BRIEFING: "1  RECEBER A MISSÃO",
    GameAct.LOADOUT: "2  MONTAR O SISTEMA",
    GameAct.OPERATION: "3  EXECUTAR A OPERAÇÃO",
    GameAct.COMMAND: "4  COMANDAR A RESPOSTA",
}


STATE_ACTS = {
    "ATTRACT": GameAct.BRIEFING,
    "SELECT_MISSION": GameAct.BRIEFING,
    "SELECT_PROFILE": GameAct.LOADOUT,
    "SELECT_KEY_MODE": GameAct.LOADOUT,
    "SELECT_GUARD": GameAct.LOADOUT,
    "PREPARE": GameAct.OPERATION,
    "PROTECT": GameAct.OPERATION,
    "TRANSMIT": GameAct.OPERATION,
    "VERIFY": GameAct.OPERATION,
    "DIAGNOSE": GameAct.COMMAND,
    "SELECT_RESPONSE": GameAct.COMMAND,
    "RETRY": GameAct.COMMAND,
    "DEBRIEF": GameAct.COMMAND,
    "ERROR": GameAct.COMMAND,
}


def game_act_for_state(state: object) -> GameAct:
    value = getattr(state, "value", state)
    return STATE_ACTS.get(str(value).upper(), GameAct.BRIEFING)


@dataclass(frozen=True)
class ChoiceVisual:
    action: str
    title: str
    summary: str
    detail: str
    footer: str
    color: tuple[int, int, int]
    icon: str
    disabled_reason: str = ""


@dataclass(frozen=True)
class AnimationCue:
    key: str
    label: str
    icon: str
    color: tuple[int, int, int]
    start: float
    end: float
    measured_us: int | None = None
    short_label: str = ""
    explanation: str = ""
    input_label: str = ""
    output_label: str = ""


@dataclass(frozen=True)
class DidacticTimeline:
    stage: str
    cues: tuple[AnimationCue, ...]

    def active(self, progress: float) -> AnimationCue:
        progress = max(0.0, min(1.0, float(progress)))
        for cue in self.cues:
            if progress <= cue.end:
                return cue
        return self.cues[-1]

    def cue_progress(self, progress: float, cue: AnimationCue | None = None) -> float:
        cue = cue or self.active(progress)
        span = max(0.0001, cue.end - cue.start)
        return max(0.0, min(1.0, (float(progress) - cue.start) / span))

    @property
    def station_progresses(self) -> tuple[float, ...]:
        """Input plus the end of every operation, used by the draggable packet."""

        return (0.0,) + tuple(cue.end for cue in self.cues)


_CUE_NARRATIVES = {
    "serialize": (
        "TEXTO → BYTES",
        "A Wisdom transforma a mensagem escolhida em uma sequência exata de bytes.",
        "texto da missão",
        "bytes do payload",
    ),
    "app_crc": (
        "ANEXAR CRC32",
        "A Wisdom calcula o CRC32 do conteúdo e acrescenta quatro bytes antes da cifra.",
        "bytes do payload",
        "payload + CRC32",
    ),
    "packet": (
        "MONTAR PACOTE",
        "Campos e comprimentos são organizados para a próxima operação.",
        "payload preparado",
        "mensagem estruturada",
    ),
    "rng": (
        "CHAVE + NONCE",
        "A Wisdom gera uma chave AES-128 efêmera local e um nonce novo.",
        "aleatoriedade interna",
        "chave e nonce novos",
    ),
    "keygen": (
        "CRIAR PAR ML-KEM",
        "ML-KEM-512 cria as chaves pública e secreta; nenhum segredo é exibido.",
        "aleatoriedade interna",
        "par de chaves ML-KEM",
    ),
    "ecdh_setup": (
        "CHAVE EFÊMERA DO RECEPTOR",
        "O receptor cria um par P-256 efêmero e publica apenas o ponto de 65 bytes.",
        "aleatoriedade interna",
        "chave pública do receptor",
    ),
    "ecdh_initiator": (
        "SEGREDO NO INICIADOR",
        "O iniciador cria outro par efêmero e combina sua chave secreta com a chave pública recebida.",
        "chave pública do receptor",
        "chave pública do iniciador + segredo",
    ),
    "ecdh_responder": (
        "SEGREDO NO RECEPTOR",
        "O receptor combina sua chave secreta com a chave pública do iniciador e obtém o mesmo segredo.",
        "chave pública do iniciador",
        "segredo reconstruído",
    ),
    "encaps": (
        "CRIAR CÁPSULA",
        "Encaps usa a chave pública para produzir uma cápsula e um segredo compartilhado.",
        "chave pública ML-KEM",
        "cápsula + segredo",
    ),
    "decaps": (
        "RECUPERAR SEGREDO",
        "Decaps usa a cápsula e a chave secreta para reconstruir o segredo.",
        "cápsula + chave secreta",
        "segredo reconstruído",
    ),
    "kdf": (
        "DERIVAR CHAVE AES",
        "A função de derivação transforma o segredo compartilhado na chave usada pelo AES-GCM.",
        "segredo compartilhado",
        "chave AES-128",
    ),
    "nonce": (
        "CRIAR NONCE",
        "A Wisdom gera um nonce novo para esta proteção AES-GCM.",
        "aleatoriedade interna",
        "nonce novo",
    ),
    "aes": (
        "CIFRAR + AUTENTICAR",
        "AES-128-GCM cifra a mensagem e cria uma tag que permite verificar autenticidade.",
        "mensagem + chave + nonce",
        "ciphertext + tag GCM",
    ),
    "uplink": (
        "ENVIAR PACOTE",
        "A estação de origem coloca o pacote protegido no enlace.",
        "pacote protegido",
        "sinal em trânsito",
    ),
    "orbit": (
        "CRUZAR O ENLACE",
        "O pacote percorre o caminho didático entre estação, satélite e receptor.",
        "sinal transmitido",
        "pacote no canal",
    ),
    "bit": (
        "BIT ESCOLHIDO NO A39",
        "A Wisdom usa o byte e a máscara confirmados pelo controle físico; a causa continua oculta.",
        "pacote + posição A39",
        "pacote após evento oculto",
    ),
    "arrival": (
        "CHEGAR AO RECEPTOR",
        "O receptor recebe exatamente o quadro que será verificado na etapa seguinte.",
        "quadro recebido",
        "entrada da verificação",
    ),
    "frame": (
        "VERIFICAR O QUADRO",
        "O CRC do quadro procura mudanças ocorridas no armazenamento ou no canal.",
        "quadro recebido",
        "resultado do CRC do quadro",
    ),
    "gcm": (
        "VERIFICAR A TAG",
        "A tag AES-GCM verifica o conteúdo protegido usando a chave secreta da sessão.",
        "ciphertext + tag",
        "resultado de autenticação",
    ),
    "app": (
        "VERIFICAR O CONTEÚDO",
        "O CRC da aplicação observa o plaintext depois da autenticação, quando foi instalado.",
        "plaintext recuperado",
        "resultado do CRC da aplicação",
    ),
    "payload": (
        "MESMO PAYLOAD",
        "A retransmissão conserva a mensagem original da missão.",
        "payload original",
        "payload confirmado",
    ),
    "fresh_key": (
        "NOVA CHAVE",
        "A Wisdom cria material de sessão novo; a retransmissão não reutiliza a chave anterior.",
        "aleatoriedade interna",
        "chave de sessão nova",
    ),
    "fresh_nonce": (
        "NOVO NONCE",
        "A Wisdom cria outro nonce para evitar reutilizar a proteção anterior.",
        "aleatoriedade interna",
        "nonce novo",
    ),
    "protect": (
        "PROTEGER DE NOVO",
        "O mesmo payload recebe uma nova proteção AES-GCM, sem falha injetada.",
        "payload + material novo",
        "novo ciphertext + tag",
    ),
    "delivered": (
        "CONFIRMAR ENTREGA",
        "O receptor valida a retransmissão real e confirma o resultado operacional.",
        "novo pacote recebido",
        "entrega confirmada",
    ),
    "finish": (
        "REVISAR A MISSÃO",
        "O relatório reúne escolhas, evidências e decisão sem alterar o resultado real.",
        "medições da partida",
        "linha causal completa",
    ),
    "review_prepare": (
        "PREPARAR",
        "A mensagem escolhida virou bytes e recebeu o CRC da aplicação quando ele foi ativado.",
        "missão escolhida",
        "mensagem preparada",
    ),
    "review_protect": (
        "PROTEGER",
        "A chave da sessão foi obtida e o AES-GCM produziu ciphertext e tag.",
        "mensagem preparada",
        "pacote protegido",
    ),
    "review_transmit": (
        "TRANSMITIR",
        "O pacote atravessou o enlace e o evento oculto foi aplicado no ponto indicado pelo A39.",
        "pacote protegido",
        "quadro recebido",
    ),
    "review_verify": (
        "VERIFICAR",
        "CRC do quadro, tag GCM e CRC da aplicação produziram as evidências da missão.",
        "quadro recebido",
        "resultado de segurança",
    ),
    "review_retry": (
        "RETRANSMITIR",
        "O mesmo payload recebeu chave e nonce novos e foi enviado novamente sem falha.",
        "payload original",
        "entrega da retransmissão",
    ),
}


def _positive_int(raw: Mapping[str, object], key: str) -> int | None:
    try:
        value = int(str(raw.get(key, "")), 10)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _cue_specs(stage: str, key_mode: str, guard: str):
    stage = stage.upper()
    key_mode = key_mode.upper()
    guard = guard.upper()
    if stage == "PREPARE":
        specs = [
            ("serialize", "SERIALIZAR O PAYLOAD", "payload", C_ACCENT_CYAN, None),
        ]
        if guard == "CRC32":
            specs.append(("app_crc", "ANEXAR CRC32 DA APLICAÇÃO", "crc32", C_ACCENT_GREEN, None))
        specs.append(("packet", "MONTAR A MENSAGEM", "packet", C_ACCENT_BLUE, None))
        return specs
    if stage == "PROTECT" and key_mode == "MLKEM":
        return [
            ("keygen", "RECEPTOR: KEYGEN ML-KEM", "pqc_keygen", C_ACCENT_PURPLE, "setup_us"),
            ("encaps", "INICIADOR: ENCAPS", "capsule", C_ACCENT_CYAN, "initiator_us"),
            ("decaps", "RECEPTOR: DECAPS", "pqc_decaps", C_ACCENT_PURPLE, "responder_us"),
            ("kdf", "DERIVAR A CHAVE AES", "kdf", C_ACCENT_ORANGE, "kdf_us"),
            ("nonce", "GERAR NONCE", "nonce", C_ACCENT_BLUE, "rng_us"),
            ("aes", "AES-GCM: CIPHERTEXT + TAG", "aes_gcm", C_ACCENT_GREEN, "encrypt_us"),
        ]
    if stage == "PROTECT" and key_mode == "ECDH":
        return [
            ("ecdh_setup", "RECEPTOR: PAR ECDH P-256", "classic_key", C_ACCENT_ORANGE, "setup_us"),
            ("ecdh_initiator", "INICIADOR: SEGREDO ECDH", "classic_key", C_ACCENT_CYAN, "initiator_us"),
            ("ecdh_responder", "RECEPTOR: SEGREDO ECDH", "classic_key", C_ACCENT_ORANGE, "responder_us"),
            ("kdf", "DERIVAR A CHAVE AES", "kdf", C_ACCENT_PURPLE, "kdf_us"),
            ("nonce", "GERAR NONCE", "nonce", C_ACCENT_BLUE, "rng_us"),
            ("aes", "AES-GCM: CIPHERTEXT + TAG", "aes_gcm", C_ACCENT_GREEN, "encrypt_us"),
        ]
    if stage == "TRANSMIT":
        return [
            ("uplink", "ENVIAR O PACOTE", "ground", C_ACCENT_CYAN, None),
            ("orbit", "ATRAVESSAR O ENLACE", "satellite", C_ACCENT_BLUE, None),
            ("bit", "APLICAR O VETOR A39", "bit", C_ACCENT_ORANGE, None),
            ("arrival", "CHEGAR AO RECEPTOR", "packet", C_ACCENT_CYAN, None),
        ]
    if stage == "VERIFY":
        specs = [
            ("frame", "CRC DO QUADRO", "channel", C_ACCENT_CYAN, None),
            ("gcm", "TAG AES-GCM", "aes_gcm", C_ACCENT_PURPLE, None),
        ]
        if guard == "CRC32":
            specs.append(("app", "CRC DA APLICAÇÃO", "crc32", C_ACCENT_GREEN, None))
        else:
            specs.append(("app", "CRC DA APLICAÇÃO AUSENTE", "no_crc", C_TEXT_DIM, None))
        return specs
    if stage == "RETRY":
        specs = [("payload", "REUTILIZAR O PAYLOAD", "payload", C_ACCENT_CYAN, None)]
        if key_mode == "MLKEM":
            specs.extend(
                [
                    ("keygen", "NOVO KEYGEN ML-KEM", "pqc_keygen", C_ACCENT_PURPLE, "setup_us"),
                    ("encaps", "NOVA CÁPSULA", "capsule", C_ACCENT_CYAN, "initiator_us"),
                    ("decaps", "NOVO SEGREDO", "pqc_decaps", C_ACCENT_PURPLE, "responder_us"),
                ]
            )
        else:
            specs.extend(
                [
                    ("ecdh_setup", "NOVO PAR ECDH DO RECEPTOR", "classic_key", C_ACCENT_ORANGE, "setup_us"),
                    ("ecdh_initiator", "NOVO PAR ECDH DO INICIADOR", "classic_key", C_ACCENT_CYAN, "initiator_us"),
                    ("ecdh_responder", "NOVO SEGREDO ECDH", "classic_key", C_ACCENT_ORANGE, "responder_us"),
                ]
            )
        specs.extend(
            [
                ("kdf", "DERIVAR NOVA CHAVE AES", "kdf", C_ACCENT_ORANGE, "kdf_us"),
                ("fresh_nonce", "CRIAR NOVO NONCE", "nonce", C_ACCENT_BLUE, "rng_us"),
                ("protect", "PROTEGER NOVAMENTE", "aes_gcm", C_ACCENT_PURPLE, "encrypt_us"),
                ("delivered", "CONFIRMAR A ENTREGA", "accept", C_ACCENT_GREEN, None),
            ]
        )
        return specs
    return [("finish", "CONSOLIDAR A MISSÃO", "accept", C_ACCENT_GREEN, None)]


def build_didactic_timeline(
    stage: object,
    measurement: object | Mapping[str, object] | None,
    *,
    key_mode: object = "ECDH",
    guard: object = "NONE",
) -> DidacticTimeline:
    """Build a deterministic replay only from an already accepted response."""

    stage_value = str(getattr(stage, "value", stage)).upper()
    key_value = str(getattr(key_mode, "value", key_mode)).upper()
    guard_value = str(getattr(guard, "value", guard)).upper()
    if measurement is None:
        raise ValueError("replay didático exige uma resposta GAME_* validada")
    if isinstance(measurement, Mapping):
        raw = measurement
    else:
        raw = getattr(measurement, "raw_response", {})
    specs = _cue_specs(stage_value, key_value, guard_value)
    measured = [_positive_int(raw, timing_key) if timing_key else None for *_, timing_key in specs]
    numeric = [value if value is not None else 1 for value in measured]
    total = max(1, sum(numeric))
    minimum_share = min(0.12, 0.8 / max(1, len(specs)))
    shares = [max(minimum_share, value / total) for value in numeric]
    share_total = sum(shares)
    shares = [value / share_total for value in shares]
    cues: list[AnimationCue] = []
    cursor = 0.0
    for spec, timing, share in zip(specs, measured, shares):
        key, label, icon, color, _timing_key = spec
        short_label, explanation, input_label, output_label = _CUE_NARRATIVES[key]
        end = min(1.0, cursor + share)
        cues.append(
            AnimationCue(
                key,
                label,
                icon,
                color,
                cursor,
                end,
                timing,
                short_label,
                explanation,
                input_label,
                output_label,
            )
        )
        cursor = end
    if cues:
        last = cues[-1]
        cues[-1] = AnimationCue(
            last.key,
            last.label,
            last.icon,
            last.color,
            last.start,
            1.0,
            last.measured_us,
            last.short_label,
            last.explanation,
            last.input_label,
            last.output_label,
        )
    return DidacticTimeline(stage_value, tuple(cues))


def build_mission_review_timeline(
    stage_measurements: Mapping[object, object],
    result: object,
    retry_result: object | None = None,
) -> DidacticTimeline:
    """Build the debrief scrubber only from measurements retained this game."""

    by_name = {
        str(getattr(stage, "value", stage)).upper(): measurement
        for stage, measurement in stage_measurements.items()
    }
    ordered = [
        ("review_prepare", "PREPARAR A MENSAGEM", "payload", C_ACCENT_CYAN, by_name.get("PREPARE")),
        ("review_protect", "PROTEGER COM AES-GCM", "aes_gcm", C_ACCENT_PURPLE, by_name.get("PROTECT")),
        ("review_transmit", "TRANSMITIR PELO ENLACE", "satellite", C_ACCENT_BLUE, by_name.get("TRANSMIT")),
        ("review_verify", "VERIFICAR AS EVIDÊNCIAS", "channel", C_ACCENT_ORANGE, result),
    ]
    if retry_result is not None:
        ordered.append(("review_retry", "RETRANSMITIR", "retry", C_ACCENT_GREEN, retry_result))
    if any(measurement is None for *_, measurement in ordered):
        raise ValueError("revisão global exige todas as medições concluídas da partida")

    elapsed = [max(1, int(getattr(measurement, "elapsed_us", 1))) for *_, measurement in ordered]
    total = max(1, sum(elapsed))
    minimum_share = min(0.15, 0.8 / len(ordered))
    shares = [max(minimum_share, value / total) for value in elapsed]
    share_total = sum(shares)
    shares = [value / share_total for value in shares]

    cursor = 0.0
    cues: list[AnimationCue] = []
    for (key, label, icon, color, measurement), share in zip(ordered, shares):
        short_label, explanation, input_label, output_label = _CUE_NARRATIVES[key]
        end = min(1.0, cursor + share)
        cues.append(
            AnimationCue(
                key,
                label,
                icon,
                color,
                cursor,
                end,
                int(getattr(measurement, "elapsed_us", 0)),
                short_label,
                explanation,
                input_label,
                output_label,
            )
        )
        cursor = end
    last = cues[-1]
    cues[-1] = AnimationCue(
        last.key,
        last.label,
        last.icon,
        last.color,
        last.start,
        1.0,
        last.measured_us,
        last.short_label,
        last.explanation,
        last.input_label,
        last.output_label,
    )
    return DidacticTimeline("DEBRIEF", tuple(cues))


def _pulse(t: float, speed: float = 3.0, low: float = 0.72) -> float:
    return low + (1.0 - low) * (0.5 + 0.5 * math.sin(t * speed))


def _scaled(color, factor):
    return tuple(max(0, min(255, int(component * factor))) for component in color)


def _centered(surface, font, text, color, center, y):
    rendered = font.render(str(text), True, color)
    surface.blit(rendered, (int(center - rendered.get_width() / 2), int(y)))


def draw_packet(
    surface: pygame.Surface,
    rect: pygame.Rect,
    *,
    color=C_ACCENT_CYAN,
    t: float = 0.0,
    selected_bit: int | None = None,
    sealed: bool = False,
) -> None:
    rect = pygame.Rect(rect)
    glow = _scaled(color, _pulse(t, 4.0))
    pygame.draw.rect(surface, (8, 26, 48), rect, border_radius=max(4, rect.height // 7))
    pygame.draw.rect(surface, glow, rect, width=2, border_radius=max(4, rect.height // 7))
    slots = 8
    gap = max(2, rect.width // 70)
    slot_w = max(3, (rect.width - 18 - gap * (slots - 1)) // slots)
    for index in range(slots):
        slot = pygame.Rect(rect.x + 9 + index * (slot_w + gap), rect.centery - 6, slot_w, 12)
        slot_color = C_ACCENT_ORANGE if selected_bit == index else color
        pygame.draw.rect(surface, slot_color, slot, border_radius=2)
    if sealed:
        tag = pygame.Rect(rect.right - max(15, rect.width // 8), rect.y + 4, max(11, rect.width // 11), rect.height - 8)
        pygame.draw.rect(surface, C_ACCENT_GREEN, tag, width=2, border_radius=3)


def draw_satellite_glyph(
    surface: pygame.Surface,
    center: tuple[int, int],
    size: int,
    t: float,
    *,
    online: bool = True,
) -> None:
    cx, cy = center
    size = max(24, int(size))
    body = pygame.Rect(cx - size // 4, cy - size // 4, size // 2, size // 2)
    panel_w, panel_h = int(size * 0.54), max(8, int(size * 0.18))
    left = pygame.Rect(body.x - panel_w - 5, cy - panel_h // 2, panel_w, panel_h)
    right = pygame.Rect(body.right + 5, cy - panel_h // 2, panel_w, panel_h)
    for panel in (left, right):
        pygame.draw.rect(surface, C_SAT_PANEL_DARK, panel, border_radius=2)
        pygame.draw.rect(surface, C_SAT_PANEL_BLUE if online else C_TEXT_DIM, panel, width=2, border_radius=2)
        for divider in range(1, 4):
            x = panel.x + panel.width * divider // 4
            pygame.draw.line(surface, C_ACCENT_BLUE, (x, panel.y + 2), (x, panel.bottom - 2), 1)
    pygame.draw.line(surface, C_SAT_GOLD, left.midright, body.midleft, 2)
    pygame.draw.line(surface, C_SAT_GOLD, body.midright, right.midleft, 2)
    pygame.draw.rect(surface, (42, 55, 75), body, border_radius=4)
    pygame.draw.rect(surface, C_SAT_BODY, body.inflate(-7, -7), border_radius=3)
    pygame.draw.rect(surface, C_ACCENT_CYAN if online else C_TEXT_DIM, body, width=2, border_radius=4)
    face = C_ACCENT_GREEN if online else C_ACCENT_RED
    face = _scaled(face, _pulse(t, 5.5))
    eye_w = max(3, size // 22)
    eye_h = max(3, size // 28)
    pygame.draw.rect(
        surface,
        face,
        (cx - size // 9 - eye_w // 2, cy - size // 14, eye_w, eye_h),
        border_radius=1,
    )
    pygame.draw.rect(
        surface,
        face,
        (cx + size // 9 - eye_w // 2, cy - size // 14, eye_w, eye_h),
        border_radius=1,
    )
    # Original angular grin: a readable retro-computer face, not a copied logo.
    grin_y = cy + max(2, size // 18)
    grin_w = max(8, size // 5)
    grin_depth = max(3, size // 18)
    grin = (
        (cx - grin_w // 2, grin_y),
        (cx - grin_w // 4, grin_y + grin_depth),
        (cx + grin_w // 4, grin_y + grin_depth),
        (cx + grin_w // 2, grin_y),
    )
    pygame.draw.lines(surface, face, False, grin, max(2, size // 38))
    antenna_top = (cx, body.y - max(7, size // 8))
    pygame.draw.line(surface, C_SAT_GOLD, (cx, body.y), antenna_top, 2)
    pygame.draw.circle(surface, C_ACCENT_ORANGE, antenna_top, max(2, size // 28))
    if online:
        ring = max(5, int(size * (0.12 + 0.025 * _pulse(t, 7))))
        pygame.draw.circle(surface, (*C_ACCENT_CYAN, 140), antenna_top, ring, 1)


def draw_ground_station(surface: pygame.Surface, center: tuple[int, int], size: int, t: float) -> None:
    cx, cy = center
    size = max(28, int(size))
    base = pygame.Rect(cx - size // 3, cy + size // 5, size * 2 // 3, max(5, size // 10))
    pygame.draw.rect(surface, (30, 60, 78), base, border_radius=3)
    pygame.draw.line(surface, C_SAT_BODY, (cx, cy + size // 5), (cx, cy - size // 7), 3)
    dish = pygame.Rect(cx - size // 3, cy - size // 3, size * 2 // 3, size // 2)
    pygame.draw.arc(surface, C_ACCENT_CYAN, dish, math.pi * 0.08, math.pi * 0.92, 4)
    pygame.draw.line(surface, C_ACCENT_CYAN, (cx, cy - size // 10), (cx + size // 5, cy - size // 4), 2)
    for index in range(2):
        radius = int(size * (0.42 + index * 0.16 + 0.03 * _pulse(t + index, 5)))
        pygame.draw.arc(
            surface,
            _scaled(C_ACCENT_CYAN, 0.78 - index * 0.18),
            (cx - radius, cy - radius, radius * 2, radius * 2),
            math.pi * 1.12,
            math.pi * 1.42,
            1,
        )


def draw_signal_link(surface, start, end, t, *, color=C_ACCENT_CYAN, progress=1.0) -> None:
    progress = max(0.0, min(1.0, progress))
    sx, sy = start
    ex, ey = end
    segments = 22
    for index in range(segments):
        p0 = index / segments
        p1 = (index + 0.55) / segments
        if p0 > progress:
            break
        x0 = int(sx + (ex - sx) * p0)
        y0 = int(sy + (ey - sy) * p0 - math.sin(p0 * math.pi) * 30)
        x1 = int(sx + (ex - sx) * min(progress, p1))
        y1 = int(sy + (ey - sy) * min(progress, p1) - math.sin(min(progress, p1) * math.pi) * 30)
        pulse = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(t * 5 - index * 0.5))
        pygame.draw.line(surface, _scaled(color, pulse), (x0, y0), (x1, y1), 2)


def _draw_shield(surface, rect, color, *, check=False):
    points = [
        (rect.centerx, rect.y + 3),
        (rect.right - 6, rect.y + rect.height // 4),
        (rect.right - 10, rect.bottom - rect.height // 4),
        (rect.centerx, rect.bottom - 3),
        (rect.x + 10, rect.bottom - rect.height // 4),
        (rect.x + 6, rect.y + rect.height // 4),
    ]
    pygame.draw.polygon(surface, (12, 35, 58), points)
    pygame.draw.polygon(surface, color, points, 3)
    if check:
        pygame.draw.line(surface, C_ACCENT_GREEN, (rect.x + rect.width // 3, rect.centery), (rect.centerx - 2, rect.bottom - rect.height // 3), 4)
        pygame.draw.line(surface, C_ACCENT_GREEN, (rect.centerx - 2, rect.bottom - rect.height // 3), (rect.right - rect.width // 4, rect.y + rect.height // 3), 4)


def _draw_chip(surface, rect, color, t, *, limited=False):
    chip = rect.inflate(-rect.width // 4, -rect.height // 4)
    pygame.draw.rect(surface, (12, 31, 54), chip, border_radius=5)
    pygame.draw.rect(surface, color, chip, 3, border_radius=5)
    for index in range(5):
        ratio = (index + 1) / 6
        x = int(chip.x + chip.width * ratio)
        pygame.draw.line(surface, color, (x, chip.y - 7), (x, chip.y), 2)
        pygame.draw.line(surface, color, (x, chip.bottom), (x, chip.bottom + 7), 2)
    bars = 2 if limited else 5
    for index in range(5):
        height = int(chip.height * (0.15 + 0.1 * index) * _pulse(t + index * 0.4, 4))
        bar_color = color if index < bars else C_TEXT_DIM
        pygame.draw.rect(surface, bar_color, (chip.x + 10 + index * max(8, chip.width // 7), chip.bottom - 10 - height, 5, height), border_radius=2)


def _draw_gear(surface, center, radius, color, angle):
    points = []
    for index in range(24):
        current = radius * (1.18 if index % 3 == 0 else 1.0)
        a = angle + index * math.pi * 2 / 24
        points.append((center[0] + math.cos(a) * current, center[1] + math.sin(a) * current))
    pygame.draw.polygon(surface, color, points, 3)
    pygame.draw.circle(surface, color, center, max(4, radius // 3), 3)


def draw_game_icon(
    surface: pygame.Surface,
    icon: str,
    rect: pygame.Rect,
    t: float,
    *,
    color=C_ACCENT_CYAN,
    active: bool = False,
    progress: float = 1.0,
) -> None:
    """Draw a labelled-choice icon using only Pygame primitives."""

    rect = pygame.Rect(rect)
    color = _scaled(color, _pulse(t, 3.5, 0.82) if active else 0.88)
    cx, cy = rect.center
    inner = rect.inflate(-max(4, rect.width // 9), -max(4, rect.height // 9))

    if icon == "touch":
        card = pygame.Rect(inner.x + 4, inner.y + 7, inner.width - 8, inner.height - 14)
        pygame.draw.rect(surface, (8, 28, 48), card, border_radius=8)
        pygame.draw.rect(surface, color, card, 3, border_radius=8)
        finger = (card.right - card.width // 4, card.bottom - card.height // 4)
        pygame.draw.circle(surface, C_ACCENT_ORANGE, finger, max(7, inner.width // 12), 3)
        pygame.draw.line(surface, C_ACCENT_ORANGE, (finger[0], finger[1] + 7), (finger[0] + 10, card.bottom + 5), 5)
        pygame.draw.circle(surface, color, finger, int(12 + 4 * _pulse(t, 6)), 2)
    elif icon == "button":
        base = pygame.Rect(cx - inner.width // 3, cy, inner.width * 2 // 3, max(10, inner.height // 5))
        pygame.draw.rect(surface, (25, 48, 62), base, border_radius=5)
        cap = pygame.Rect(base.x + base.width // 6, cy - inner.height // 3, base.width * 2 // 3, inner.height // 3 + 5)
        pygame.draw.ellipse(surface, (44, 72, 90), cap)
        pygame.draw.ellipse(surface, C_ACCENT_GREEN if active else color, cap, 3)
        _centered(surface, FONT_LABEL, "D27", C_TEXT_PRIMARY, cx, base.bottom + 5)
    elif icon == "pot":
        radius = max(14, min(inner.width, inner.height) // 3)
        pygame.draw.circle(surface, (17, 39, 58), (cx, cy), radius)
        pygame.draw.circle(surface, color, (cx, cy), radius, 3)
        angle = -2.3 + max(0.0, min(1.0, progress)) * 4.6
        pygame.draw.line(
            surface,
            C_ACCENT_ORANGE,
            (cx, cy),
            (int(cx + math.cos(angle) * radius * 0.75), int(cy + math.sin(angle) * radius * 0.75)),
            4,
        )
        _centered(surface, FONT_LABEL, "A39", C_TEXT_PRIMARY, cx, cy + radius + 6)
    elif icon == "drag":
        packet = pygame.Rect(inner.x + 6, cy - 15, max(48, inner.width // 2), 30)
        draw_packet(surface, packet, color=color, t=t, sealed=True)
        start = packet.right + 8
        pygame.draw.line(surface, C_ACCENT_ORANGE, (start, cy), (inner.right - 6, cy), 3)
        pygame.draw.polygon(
            surface,
            C_ACCENT_ORANGE,
            [(inner.right - 6, cy), (inner.right - 18, cy - 8), (inner.right - 18, cy + 8)],
        )
        pygame.draw.circle(surface, C_TEXT_PRIMARY, (packet.centerx, packet.bottom + 10), 6, 2)
    elif icon == "satellite":
        draw_satellite_glyph(surface, (cx, cy), min(rect.width, rect.height), t, online=True)
    elif icon == "pqc_keygen":
        radius = max(10, min(inner.width, inner.height) // 5)
        for offset, key_color in ((-radius * 2, C_ACCENT_PURPLE), (radius * 2, C_ACCENT_CYAN)):
            key_center = (cx + offset, cy)
            pygame.draw.circle(surface, key_color, key_center, radius, 3)
            pygame.draw.line(surface, key_color, (key_center[0] + radius, cy), (key_center[0] + radius * 3, cy), 4)
            pygame.draw.line(surface, key_color, (key_center[0] + radius * 2, cy), (key_center[0] + radius * 2, cy + radius), 3)
        pygame.draw.line(surface, color, (cx - radius, cy - radius * 2), (cx + radius, cy - radius * 2), 2)
        pygame.draw.polygon(surface, color, [(cx + radius, cy - radius * 2), (cx + radius // 2, cy - radius * 2 - 5), (cx + radius // 2, cy - radius * 2 + 5)])
    elif icon == "pqc_decaps":
        radius = max(10, min(inner.width, inner.height) // 5)
        capsule = pygame.Rect(cx - radius * 3, cy - radius, radius * 3, radius * 2)
        pygame.draw.arc(surface, C_ACCENT_PURPLE, capsule, math.pi / 2, math.pi * 1.5, 4)
        pygame.draw.line(surface, C_ACCENT_PURPLE, (capsule.centerx, capsule.y), (capsule.right, capsule.y), 4)
        pygame.draw.line(surface, C_ACCENT_PURPLE, (capsule.centerx, capsule.bottom), (capsule.right, capsule.bottom), 4)
        key_center = (cx + radius * 2, cy)
        pygame.draw.circle(surface, C_ACCENT_GREEN, key_center, radius, 3)
        pygame.draw.line(surface, C_ACCENT_GREEN, (key_center[0] + radius, cy), (inner.right - 4, cy), 4)
        draw_signal_link(surface, (capsule.right, cy), (key_center[0] - radius, cy), t, color=color, progress=progress)
    elif icon == "ground":
        draw_ground_station(surface, (cx, cy), min(rect.width, rect.height), t)
    elif icon == "telemetry":
        pygame.draw.circle(surface, color, (cx - inner.width // 5, cy + inner.height // 4), max(7, inner.width // 10), 3)
        pygame.draw.line(surface, color, (cx - inner.width // 5, inner.y + 6), (cx - inner.width // 5, cy + inner.height // 4), 5)
        for index in range(3):
            pygame.draw.arc(surface, color, (cx, cy - 24 - index * 4, 22 + index * 16, 48 + index * 8), -0.8, 0.8, 2)
        pygame.draw.polygon(surface, C_ACCENT_RED, [(inner.right - 22, inner.y + 6), (inner.right - 4, inner.y + 38), (inner.right - 40, inner.y + 38)], 3)
    elif icon in {"safe_command", "safe"}:
        _draw_shield(surface, inner, color, check=icon == "safe")
        if icon == "safe_command":
            pygame.draw.line(surface, C_ACCENT_ORANGE, (cx + 4, inner.y + 18), (cx - 7, cy + 2), 5)
            pygame.draw.line(surface, C_ACCENT_ORANGE, (cx - 7, cy + 2), (cx + 6, cy - 1), 5)
            pygame.draw.line(surface, C_ACCENT_ORANGE, (cx + 6, cy - 1), (cx - 5, inner.bottom - 18), 5)
    elif icon == "config":
        scale = max(12, min(inner.width, inner.height) // 3)
        gear_center = (cx - scale, cy)
        clock_center = (cx + scale, cy)
        _draw_gear(surface, gear_center, scale, color, t * 0.45)
        pygame.draw.circle(surface, C_ACCENT_ORANGE, clock_center, scale, 2)
        pygame.draw.line(surface, C_ACCENT_ORANGE, clock_center, (clock_center[0], clock_center[1] - scale + 5), 2)
        pygame.draw.line(surface, C_ACCENT_ORANGE, clock_center, (clock_center[0] + scale - 5, clock_center[1] + scale // 3), 2)
    elif icon in {"cpu_fast", "cpu_limited"}:
        _draw_chip(surface, inner, color, t, limited=icon == "cpu_limited")
    elif icon in {"classic_key", "kdf"}:
        key_radius = max(10, min(inner.width, inner.height) // 3)
        key_center = (inner.x + key_radius + 5, cy)
        pygame.draw.circle(surface, color, key_center, key_radius, 4)
        pygame.draw.line(surface, color, (key_center[0] + key_radius, cy), (inner.right - 8, cy), 6)
        pygame.draw.line(surface, color, (inner.right - inner.width // 4, cy), (inner.right - inner.width // 4, cy + inner.height // 6), 5)
        pygame.draw.rect(surface, C_ACCENT_PURPLE if icon == "kdf" else C_SAT_GOLD, (inner.x + 5, inner.y + 5, inner.width // 4, inner.height // 4), 2, border_radius=3)
    elif icon == "capsule":
        left = (inner.x + 12, cy)
        right = (inner.right - 12, cy)
        pygame.draw.circle(surface, C_ACCENT_PURPLE, left, 10, 3)
        pygame.draw.circle(surface, C_ACCENT_GREEN, right, 10, 3)
        position = max(0.0, min(1.0, progress))
        px = int(left[0] + (right[0] - left[0]) * position)
        pygame.draw.polygon(surface, color, [(px, cy - 13), (px + 16, cy), (px, cy + 13), (px - 16, cy)])
        draw_signal_link(surface, left, right, t, color=color, progress=progress)
    elif icon in {"crc32", "no_crc", "payload"}:
        blocks = 4
        gap = max(2, inner.width // 30)
        if icon == "payload":
            block_w = max(5, (inner.width - gap * (blocks - 1)) // blocks)
            total_w = blocks * block_w + gap * (blocks - 1)
        else:
            block_w = max(5, (inner.width - gap * blocks - 6) // (blocks + 1))
            total_w = blocks * block_w + gap * blocks + block_w + 6
        start_x = cx - total_w // 2
        for index in range(blocks):
            block = pygame.Rect(start_x + index * (block_w + gap), cy - 12, block_w, 24)
            pygame.draw.rect(surface, C_ACCENT_CYAN, block, border_radius=3)
        extra = pygame.Rect(start_x + blocks * (block_w + gap), cy - 15, block_w + 6, 30)
        if icon == "crc32":
            pygame.draw.rect(surface, C_ACCENT_GREEN, extra, border_radius=3)
            _centered(surface, FONT_LABEL, "+4", (5, 20, 20), extra.centerx, extra.y + 7)
        elif icon == "no_crc":
            pygame.draw.rect(surface, C_TEXT_DIM, extra, 2, border_radius=3)
            pygame.draw.line(surface, C_ACCENT_RED, extra.topleft, extra.bottomright, 2)
            pygame.draw.line(surface, C_ACCENT_RED, extra.topright, extra.bottomleft, 2)
    elif icon in {"aes_gcm", "packet"}:
        packet = pygame.Rect(inner.x + 2, cy - inner.height // 5, inner.width - 4, inner.height * 2 // 5)
        draw_packet(surface, packet, color=color, t=t, sealed=icon == "aes_gcm")
        if icon == "aes_gcm":
            pygame.draw.arc(surface, C_ACCENT_GREEN, (cx - 13, packet.y - 24, 26, 30), math.pi, math.pi * 2, 3)
            pygame.draw.rect(surface, C_ACCENT_GREEN, (cx - 15, packet.y - 11, 30, 22), 3, border_radius=4)
    elif icon == "nonce":
        pygame.draw.circle(surface, color, (cx, cy), min(inner.width, inner.height) // 3, 3)
        for index in range(6):
            angle = t * 0.4 + index * math.pi / 3
            point = (int(cx + math.cos(angle) * inner.width / 4), int(cy + math.sin(angle) * inner.height / 4))
            pygame.draw.circle(surface, C_ACCENT_BLUE if index % 2 else C_ACCENT_CYAN, point, 4)
        _centered(surface, FONT_LABEL, "NONCE", color, cx, cy - 7)
    elif icon == "channel":
        draw_ground_station(surface, (inner.x + inner.width // 4, cy + 8), inner.height // 2, t)
        draw_signal_link(surface, (inner.x + inner.width // 3, cy), (inner.right - 5, cy - inner.height // 4), t, color=color, progress=progress)
        if active:
            pygame.draw.line(surface, C_ACCENT_RED, (cx + 8, cy - 16), (cx - 3, cy + 4), 4)
            pygame.draw.line(surface, C_ACCENT_RED, (cx - 3, cy + 4), (cx + 13, cy + 1), 4)
    elif icon == "tamper":
        draw_packet(surface, pygame.Rect(inner.x + 4, cy - 18, inner.width - 8, 36), color=color, t=t)
        warning = [(cx, inner.y + 4), (cx + 23, inner.y + 42), (cx - 23, inner.y + 42)]
        pygame.draw.polygon(surface, C_ACCENT_RED, warning, 3)
        pygame.draw.line(surface, C_ACCENT_RED, (cx, inner.y + 16), (cx, inner.y + 29), 3)
    elif icon == "memory":
        _draw_chip(surface, inner, color, t, limited=False)
        cell = pygame.Rect(cx + inner.width // 9, cy - inner.height // 9, max(8, inner.width // 7), max(8, inner.height // 7))
        pygame.draw.rect(surface, C_ACCENT_RED, cell, border_radius=2)
        pygame.draw.line(surface, C_TEXT_PRIMARY, cell.topleft, cell.bottomright, 2)
    elif icon == "accept":
        _draw_shield(surface, inner, color, check=True)
    elif icon == "retry":
        radius = min(inner.width, inner.height) // 3
        pygame.draw.arc(surface, color, (cx - radius, cy - radius, radius * 2, radius * 2), -0.2, math.pi * 1.65, 4)
        pygame.draw.polygon(surface, color, [(cx + radius, cy - 4), (cx + radius - 14, cy - 17), (cx + radius - 10, cy + 2)])
        draw_packet(surface, pygame.Rect(cx - radius // 2, cy - 10, radius, 20), color=C_ACCENT_CYAN, t=t, sealed=True)
    elif icon == "bit":
        draw_packet(surface, pygame.Rect(inner.x + 2, cy - 20, inner.width - 4, 40), color=color, t=t, selected_bit=3)
        pygame.draw.circle(surface, C_ACCENT_RED, (cx, cy), int(10 + 4 * _pulse(t, 7)), 2)
    else:
        pygame.draw.circle(surface, color, (cx, cy), min(inner.width, inner.height) // 3, 3)
        pygame.draw.circle(surface, C_TEXT_PRIMARY, (cx, cy), max(3, min(inner.width, inner.height) // 12))


__all__ = (
    "ACT_LABELS",
    "AnimationCue",
    "ChoiceVisual",
    "DidacticTimeline",
    "GameAct",
    "build_didactic_timeline",
    "build_mission_review_timeline",
    "draw_game_icon",
    "draw_ground_station",
    "draw_packet",
    "draw_satellite_glyph",
    "draw_signal_link",
    "game_act_for_state",
)
