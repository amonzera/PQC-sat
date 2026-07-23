"""Physical-confirmation staged game used by the public stand experience."""

from __future__ import annotations

from dataclasses import asdict
import math
import random
import time

from pqc_sat.stand.model import (
    FaultSelection,
    GameEndReceipt,
    GameResult,
    GameStage,
    GuardMode,
    IncidentScenario,
    InvestigationState,
    KeyMode,
    MissionCard,
    OperationalDecision,
    PendingCommand,
    StageMeasurement,
    StandConfig,
    StandError,
    StandProtocolError,
    _required_int,
    fault_selection_from_pot,
    parse_button_press_event,
    parse_game_end_response,
    parse_game_result_response,
    parse_game_stage_response,
    scenario_for,
)
from pqc_sat.stand.session import StandSessionLogger


class InvestigationController:
    """Non-blocking GAME_* state machine driven by explicit confirmations."""

    flow_name = "investigation"
    protocol_capability = "STAGED_V1"
    KEY_MODES = tuple(mode.value for mode in KeyMode)
    GUARDS = tuple(mode.value for mode in GuardMode)
    PROTECTIONS = tuple(
        scenario_for(key_mode, guard)
        for key_mode in KeyMode
        for guard in GuardMode
    )
    DIAGNOSES = ("CHANNEL", "AUTH", "MEMORY")
    RESPONSES = tuple(decision.value for decision in OperationalDecision)
    _EXPECTED_DIAGNOSIS = {
        IncidentScenario.CHANNEL_BITFLIP: "CHANNEL",
        IncidentScenario.TAMPER: "AUTH",
        IncidentScenario.RX_MEMORY: "MEMORY",
        IncidentScenario.NORMAL: "NORMAL",
    }
    _STAGE_BY_STATE = {
        InvestigationState.PREPARE: GameStage.PREPARE,
        InvestigationState.PROTECT: GameStage.PROTECT,
        InvestigationState.TRANSMIT: GameStage.TRANSMIT,
        InvestigationState.VERIFY: GameStage.VERIFY,
        InvestigationState.RETRY: GameStage.RETRY,
    }
    _FORWARD_STATES = {
        InvestigationState.ATTRACT,
        InvestigationState.SELECT_MISSION,
        InvestigationState.SELECT_PROFILE,
        InvestigationState.SELECT_KEY_MODE,
        InvestigationState.SELECT_GUARD,
        InvestigationState.PREPARE,
        InvestigationState.PROTECT,
        InvestigationState.TRANSMIT,
        InvestigationState.VERIFY,
        InvestigationState.DIAGNOSE,
        InvestigationState.SELECT_RESPONSE,
        InvestigationState.RETRY,
        InvestigationState.DEBRIEF,
        InvestigationState.ERROR,
    }

    def __init__(
        self,
        config: StandConfig,
        send_command,
        *,
        mode: str,
        logger: StandSessionLogger | None = None,
        now: float | None = None,
    ) -> None:
        if mode not in {"hardware", "simulated"}:
            raise ValueError("mode deve ser hardware ou simulated")
        if not config.missions:
            raise ValueError("modo investigativo exige missões configuradas")
        self.config = config
        self.send_command = send_command
        self.mode = mode
        self.logger = logger
        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        self.state = InvestigationState.ATTRACT
        self.state_entered_at = now
        self.last_interaction_at = now
        self.last_button_at = -math.inf
        self.last_button_uptime_ms: int | None = None
        self.last_seen_button_uptime_ms: int | None = None
        self.button_sequence = 0
        self.last_confirmation_origin = ""
        self.connection_status = (
            "AGUARDANDO HANDSHAKE" if mode == "hardware" else "CARREGANDO MODELO OFFLINE"
        )
        self.connected = False
        self.handshake_ok = False
        self.handshake: dict[str, str] = {}
        self.handshake_uptime_ms: int | None = None
        self.handshake_generation = 0
        self.error_handshake_generation = 0
        self.fresh_handshake_since_error = False
        self.pending: PendingCommand | None = None
        self._ignored_response_commands: set[str] = set()
        self.error_message = ""
        self.rejected_events = 0
        self.ignored_inputs = 0
        self.cycle_index = 0
        self.cycle_started_at: float | None = None
        self.cycle_target_logged = False
        self.last_cycle_duration: float | None = None
        self.completed_cycles = 0
        self.pending_choice = ""
        self.pending_choice_kind = ""
        self.blocked_choice_message = ""
        self.selected_mission: MissionCard | None = None
        self.selected_profile = ""
        self.selected_profile_mhz = 0
        self.selected_key_mode: KeyMode | None = None
        self.selected_guard: GuardMode | None = None
        self.incident: IncidentScenario | None = None
        self.incident_id = ""
        self.game_id = ""
        self.selection: FaultSelection | None = None
        self.live_pot_value = (config.pot_minimum + config.pot_maximum) // 2
        self.stage_measurements: dict[GameStage, StageMeasurement] = {}
        self.result: GameResult | None = None
        self.retry_result: GameResult | None = None
        self.end_receipt: GameEndReceipt | None = None
        self.selected_diagnosis = ""
        self.diagnosis_correct: bool | None = None
        self.operational_decision: OperationalDecision | None = None
        self.end_decision: OperationalDecision | None = None
        self.explanation_mode = "quick"
        self.animation_stage: str = ""
        self.animation_started_at: float | None = None
        self.animation_deadline: float | None = None
        self.animation_complete = False
        self.forced_incident: IncidentScenario | None = None
        incident_order = list(config.incident_sequence)
        random.Random(config.incident_seed).shuffle(incident_order)
        self._incident_order = tuple(IncidentScenario(value) for value in incident_order)
        self._log("controller_ready", state=self.state.value, protocol=self.protocol_capability)

    @property
    def ready(self) -> bool:
        return self.connected and self.handshake_ok

    @property
    def ready_for_start(self) -> bool:
        return self.ready and self.pending is None and self.input_ready()

    @property
    def selected_scenario(self) -> str:
        if self.selected_key_mode is None or self.selected_guard is None:
            return ""
        return scenario_for(self.selected_key_mode, self.selected_guard)

    @property
    def current_stage_measurement(self) -> StageMeasurement | GameResult | None:
        stage = self._STAGE_BY_STATE.get(self.state)
        if stage is GameStage.VERIFY:
            return self.result
        if stage is GameStage.RETRY:
            return self.retry_result
        return self.stage_measurements.get(stage) if stage else None

    @property
    def stage_ready_for_confirmation(self) -> bool:
        return (
            self.pending is None
            and self.current_stage_measurement is not None
            and self.animation_complete
        )

    def state_elapsed(self, now: float | None = None) -> float:
        now = self.last_clock_at if now is None else now
        return max(0.0, now - self.state_entered_at)

    def input_ready(self, now: float | None = None) -> bool:
        return self.state_elapsed(now) >= self.config.screen_input_guard_seconds

    def animation_progress(self, now: float | None = None) -> float:
        now = self.last_clock_at if now is None else now
        if self.animation_started_at is None or self.animation_deadline is None:
            return 0.0
        duration = max(0.001, self.animation_deadline - self.animation_started_at)
        return max(0.0, min(1.0, (now - self.animation_started_at) / duration))

    def auto_return_remaining(self, now: float | None = None) -> None:
        del now
        return None

    def _log(self, event: str, **fields: object) -> None:
        if self.logger is not None:
            self.logger.write(event, flow=self.flow_name, **fields)

    def transition(
        self,
        new_state: InvestigationState,
        *,
        reason: str,
        now: float | None = None,
        cause: str = "administrative",
        button_seq: int | None = None,
        confirmation_origin: str = "",
    ) -> None:
        now = time.monotonic() if now is None else now
        previous = self.state
        if new_state == previous:
            return
        if cause != "button" and new_state not in {InvestigationState.ERROR, InvestigationState.ATTRACT}:
            raise StandError(f"avanço sem confirmação bloqueado: {previous.value} -> {new_state.value}")
        self.state = new_state
        self.state_entered_at = now
        self.last_interaction_at = now
        self.last_clock_at = now
        self._log(
            "transition",
            previous=previous.value,
            state=new_state.value,
            reason=reason,
            cause=cause,
            button_seq=button_seq,
            confirmation_origin=confirmation_origin,
        )
        if new_state in self._STAGE_BY_STATE:
            self._log(
                "stage_started",
                game_id=self.game_id,
                stage=self._STAGE_BY_STATE[new_state].value,
                button_seq=button_seq,
            )

    def _advance(self, new_state: InvestigationState, *, reason: str, now: float) -> None:
        self.transition(
            new_state,
            reason=reason,
            now=now,
            cause="button",
            button_seq=self.button_sequence,
            confirmation_origin=self.last_confirmation_origin,
        )

    def _parse_physical_button(
        self,
        event: dict[str, object],
        *,
        now: float,
    ) -> tuple[int, int | None] | None:
        """Validate one post-handshake D27 event and consume its serial uptime."""

        try:
            if self.mode != "hardware":
                raise StandProtocolError("BUTTON_PING físico indisponível fora do hardware")
            if self.handshake_uptime_ms is None:
                raise StandProtocolError("BUTTON_PING recebido antes do handshake")
            uptime_ms = parse_button_press_event(
                event,
                handshake_uptime_ms=self.handshake_uptime_ms,
            )
            if self.last_seen_button_uptime_ms is not None:
                delta = (uptime_ms - self.last_seen_button_uptime_ms) & 0xFFFFFFFF
                if delta == 0 or delta >= 0x80000000:
                    raise StandProtocolError("BUTTON_PING antigo ou repetido")
            nested = event.get("payload")
            if not isinstance(nested, dict):
                raise StandProtocolError("BUTTON_PING sem payload estruturado")
            pot_value = int(nested["pot"]) if "pot" in nested else None
            if pot_value is not None and not self.config.pot_minimum <= pot_value <= self.config.pot_maximum:
                raise StandProtocolError("pot do BUTTON_PING fora da faixa")
            self.last_seen_button_uptime_ms = uptime_ms
            return uptime_ms, pot_value
        except (KeyError, TypeError, ValueError, StandProtocolError) as exc:
            self._ignore_input("physical", str(exc), now=now)
            return None

    def complete_wisdom_search(self, *, now: float | None = None) -> bool:
        """Leave technical search and recover an interrupted game to ATTRACT."""

        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        if not self.ready:
            return False
        recovered = self.state is InvestigationState.ERROR
        interrupted_state = self.state.value
        interrupted_game_id = self.game_id
        if recovered:
            self._reset_cycle_data()
            self.error_message = ""
            self.fresh_handshake_since_error = False
            self.last_confirmation_origin = ""
            self.transition(
                InvestigationState.ATTRACT,
                reason="wisdom_reconnected",
                now=now,
                cause="administrative",
            )
        self._log(
            "wisdom_search_completed",
            recovery=recovered,
            interrupted_state=interrupted_state if recovered else None,
            interrupted_game_id=interrupted_game_id or None,
            handshake_generation=self.handshake_generation,
        )
        return True

    def _send(
        self,
        command: str,
        purpose: str,
        *,
        expected: dict[str, object] | None = None,
        now: float | None = None,
    ) -> bool:
        now = time.monotonic() if now is None else now
        if self.pending is not None:
            return False
        if not self.ready:
            self._enter_error("hardware/fixture sem handshake STAGED_V1", now=now)
            return False
        normalized = command.upper()
        self.pending = PendingCommand(
            command=normalized,
            purpose=purpose,
            deadline=now + self.config.serial_timeout_seconds,
            expected=dict(expected or {}),
        )
        self._log(
            "command_sent",
            command=command,
            purpose=purpose,
            state=self.state.value,
            game_id=self.game_id or None,
        )
        try:
            self.send_command(command, timeout=self.config.serial_timeout_seconds)
        except Exception as exc:
            self.pending = None
            self._enter_error(f"falha ao enfileirar comando: {exc}", now=now)
            return False
        return True

    def handle_serial_event(
        self,
        event_type: str,
        event: dict[str, object],
        *,
        now: float | None = None,
    ) -> bool | None:
        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        if event_type == "state":
            self._handle_connection_state(event, now=now)
            return None
        if event_type == "event":
            if str(event.get("name", "")).upper() != "BUTTON_PING":
                self.rejected_events += 1
                return None
            if self.mode != "hardware":
                return self.handle_button(now=now, origin="fixture-event")
            parsed = self._parse_physical_button(event, now=now)
            if parsed is None:
                return False
            uptime_ms, pot_value = parsed
            return self.handle_button(
                now=now,
                origin="physical",
                uptime_ms=uptime_ms,
                pot_value=pot_value,
                control="D27",
            )
        if event_type == "error":
            self._enter_error(str(event.get("status", "erro serial")), now=now)
            return None
        if event_type != "response":
            self.rejected_events += 1
            return None

        command = str(event.get("command", "")).upper()
        status = str(event.get("status", "UNKNOWN")).upper()
        payload_obj = event.get("payload", {})
        payload = payload_obj if isinstance(payload_obj, dict) else {}
        self._log("response_received", command=command, status=status, raw_response=payload)
        if command in self._ignored_response_commands:
            self._ignored_response_commands.discard(command)
            return None
        if command == "HELLO" and (self.pending is None or self.pending.purpose == "handshake_retry"):
            if self.pending is not None:
                self.pending = None
            if status != "OK":
                self._enter_error(f"HELLO retornou {status}", now=now, request_handshake=False)
                return None
            self._handle_hello(payload, now=now)
            return None
        if self.pending is None:
            self.rejected_events += 1
            return None
        pending = self.pending
        if command != pending.command:
            self.pending = None
            self._enter_error(f"resposta fora de ordem: {command}", now=now)
            return None
        self.pending = None
        if status != "OK":
            if pending.purpose == "screen_pot":
                self._reject_screen_pot(f"{command} retornou {status}", now=now)
                return None
            self._enter_error(f"{command.split()[0]} retornou {status}", now=now)
            return None
        try:
            self._accept_response(pending, payload, now=now)
        except (KeyError, StandProtocolError, ValueError) as exc:
            if pending.purpose == "screen_pot":
                self._reject_screen_pot(str(exc), now=now)
            else:
                self._enter_error(str(exc), now=now)
        return None

    def _handle_hello(self, payload: dict[str, object], *, now: float) -> None:
        node = str(payload.get("node", ""))
        board = str(payload.get("board", ""))
        proto = str(payload.get("proto", ""))
        capability = str(payload.get("game", ""))
        valid_hardware = node == "PQC-SAT-WISDOM" and board == "BlackBoard-Wisdom" and proto == "V1"
        valid_fixture = self.mode == "simulated" and node == "OFFLINE-FIXTURE" and proto == "V1"
        if not (valid_hardware or valid_fixture) or capability != self.protocol_capability:
            self.handshake_ok = False
            self.error_message = (
                f"firmware incompatível: node={node} proto={proto} game={capability or 'ausente'}; "
                "grave STAGED_V1"
            )
            if self.state is not InvestigationState.ERROR:
                self.transition(InvestigationState.ERROR, reason="handshake_rejected", now=now, cause="error")
            self._log("error", message=self.error_message, state=self.state.value)
            return
        handshake_uptime_ms = _required_int(payload, "uptime_ms")
        if not 0 <= handshake_uptime_ms <= 0xFFFFFFFF:
            raise StandProtocolError("uptime_ms inválido no HELLO")
        self.handshake_uptime_ms = handshake_uptime_ms
        self.last_seen_button_uptime_ms = None
        self.last_button_uptime_ms = None
        self.handshake_ok = True
        self.handshake_generation += 1
        self.handshake = {key: str(value) for key, value in payload.items()}
        if self.state is InvestigationState.ERROR:
            self.fresh_handshake_since_error = self.handshake_generation > self.error_handshake_generation
        self.state_entered_at = now
        self.last_interaction_at = now
        self._log(
            "handshake",
            mode=self.mode,
            generation=self.handshake_generation,
            payload=self.handshake,
        )

    def _handle_connection_state(self, payload: dict[str, object], *, now: float) -> None:
        was_connected = self.connected
        self.connected = bool(payload.get("connected"))
        self.connection_status = str(payload.get("status", "SERIAL"))
        self._log(
            "connection",
            connected=self.connected,
            status=self.connection_status,
            port=payload.get("port"),
        )
        if not self.connected:
            self.handshake_ok = False
            self.handshake = {}
            self.handshake_uptime_ms = None
            self.pending = None
        if was_connected and not self.connected and self.state not in {
            InvestigationState.ATTRACT,
            InvestigationState.ERROR,
        }:
            self._enter_error(
                "Wisdom desconectada; partida interrompida",
                now=now,
                request_handshake=False,
            )

    def _source_label(self) -> str:
        return "hardware-live" if self.mode == "hardware" else "deterministic-offline-model"

    def _accept_response(self, pending: PendingCommand, payload: dict[str, object], *, now: float) -> None:
        if pending.purpose == "screen_pot":
            if self.state is not InvestigationState.PROTECT:
                raise StandProtocolError("leitura A39 chegou fora do checkpoint PROTECT")
            pot_value = _required_int(payload, "pot")
            if not self.config.pot_minimum <= pot_value <= self.config.pot_maximum:
                raise StandProtocolError("leitura A39 fora da faixa")
            self._log(
                "screen_pot_sampled",
                source="ANALOG POT",
                pot=pot_value,
                state=self.state.value,
            )
            self.blocked_choice_message = ""
            if not self.handle_button(
                now=now,
                origin="screen",
                pot_value=pot_value,
                control="green_button",
            ):
                self._reject_screen_pot("confirmação deixou de estar disponível", now=now)
            return
        if self.selected_mission is None or self.selected_key_mode is None or self.selected_guard is None:
            raise StandProtocolError("resposta GAME_* sem escolhas confirmadas")
        common = dict(
            game_id=self.game_id,
            profile=self.selected_profile,
            profile_mhz=self.selected_profile_mhz,
            key_mode=self.selected_key_mode,
            guard=self.selected_guard,
            payload_len=len(self.selected_mission.payload_bytes),
            source=self._source_label(),
        )
        if pending.purpose in {"game_begin", "game_protect", "game_transmit"}:
            stage = {
                "game_begin": GameStage.PREPARE,
                "game_protect": GameStage.PROTECT,
                "game_transmit": GameStage.TRANSMIT,
            }[pending.purpose]
            measurement = parse_game_stage_response(
                pending.command,
                payload,
                stage=stage,
                incident=self.incident,
                selection=self.selection,
                payload_bytes=self.selected_mission.payload_bytes if stage is GameStage.PREPARE else None,
                **common,
            )
            self.stage_measurements[stage] = measurement
            self._arm_animation(stage.value, now=now)
            self._log("stage_completed", game_id=self.game_id, stage=stage.value, measurement=asdict(measurement))
            return
        if self.selection is None or self.incident is None:
            raise StandProtocolError("resultado GAME_* sem vetor de falha")
        if pending.purpose in {"game_verify", "game_retry"}:
            stage = GameStage.VERIFY if pending.purpose == "game_verify" else GameStage.RETRY
            parsed = parse_game_result_response(
                pending.command,
                payload,
                stage=stage,
                incident=self.incident,
                selection=self.selection,
                initial_protect=self.stage_measurements.get(GameStage.PROTECT),
                **common,
            )
            if stage is GameStage.VERIFY:
                self.result = parsed
            else:
                self.retry_result = parsed
            self._arm_animation(stage.value, now=now)
            self._log("stage_completed", game_id=self.game_id, stage=stage.value, result=asdict(parsed))
            return
        if pending.purpose == "game_end":
            if self.end_decision is None:
                raise StandProtocolError("GAME_END sem decisão confirmada")
            validated_result = self.retry_result or self.result
            if validated_result is None:
                raise StandProtocolError("GAME_END sem resultado previamente validado")
            self.end_receipt = parse_game_end_response(
                pending.command,
                payload,
                game_id=self.game_id,
                decision=self.end_decision,
                expected_final_result=validated_result.result,
                baseline_profile=self.config.baseline_name,
                baseline_mhz=self.config.baseline_mhz,
                source=self._source_label(),
            )
            self._arm_animation("DEBRIEF", now=now)
            self._log("stage_completed", game_id=self.game_id, stage=GameStage.END.value, receipt=asdict(self.end_receipt))
            return
        raise StandProtocolError(f"propósito de resposta desconhecido: {pending.purpose}")

    def _arm_animation(self, stage: str, *, now: float) -> None:
        self.animation_stage = stage
        self.animation_started_at = now
        self.animation_deadline = now + self.config.animation_duration_ms(stage) / 1000.0
        self.animation_complete = False
        self._log(
            "animation_started",
            stage=stage,
            didactic_duration_ms=self.config.animation_duration_ms(stage),
        )

    def handle_action(self, action: str, *, now: float | None = None) -> bool:
        """Handle a screen selection or an explicit green-button confirmation."""
        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        if not self.input_ready(now):
            self._ignore_input("screen", "tela ainda não armada", now=now, action=action)
            return False
        if action == "confirm":
            return self.handle_screen_confirmation(now=now)
        self.note_interaction(now=now)
        choice_kind = ""
        choice_value = ""
        valid = False
        if action.startswith("mission:") and self.state is InvestigationState.SELECT_MISSION:
            choice_kind = "mission"
            choice_value = action.split(":", 1)[1].upper()
            valid = any(mission.mission_id == choice_value for mission in self.config.missions)
        elif action.startswith("profile:") and self.state is InvestigationState.SELECT_PROFILE:
            choice_kind = "profile"
            choice_value = action.split(":", 1)[1]
            valid = choice_value in {str(self.config.baseline_mhz), str(self.config.limited_mhz)}
        elif action.startswith("key:") and self.state is InvestigationState.SELECT_KEY_MODE:
            choice_kind = "key_mode"
            choice_value = action.split(":", 1)[1].upper()
            valid = choice_value in self.KEY_MODES
        elif action.startswith("guard:") and self.state is InvestigationState.SELECT_GUARD:
            choice_kind = "guard"
            choice_value = action.split(":", 1)[1].upper()
            valid = choice_value in self.GUARDS
        elif action.startswith("diagnosis:") and self.state is InvestigationState.DIAGNOSE:
            choice_kind = "diagnosis"
            choice_value = action.split(":", 1)[1].upper()
            valid = choice_value in self.DIAGNOSES
        elif action.startswith("response:") and self.state is InvestigationState.SELECT_RESPONSE:
            choice_kind = "response"
            choice_value = action.split(":", 1)[1].upper()
            valid = choice_value in self.RESPONSES
            if valid and choice_value == OperationalDecision.ACCEPT.value and self.result and self.result.cryptographically_rejected:
                self.blocked_choice_message = "PACOTE REJEITADO PELA CRIPTOGRAFIA NÃO PODE SER ACEITO"
                self._log("choice_blocked", kind=choice_kind, value=choice_value, reason="cryptographic_reject")
                return False
        elif action in {"explain:quick", "explain:technical"} and self.state is InvestigationState.DEBRIEF:
            self.explanation_mode = action.split(":", 1)[1]
            self._log("explanation_mode", value=self.explanation_mode)
            return True
        if not valid:
            self._ignore_input("screen", "ação sem efeito nesta fase", now=now, action=action)
            return False
        self.pending_choice_kind = choice_kind
        self.pending_choice = choice_value
        self.blocked_choice_message = ""
        self._log("choice_selected", kind=choice_kind, value=choice_value, state=self.state.value)
        return True

    def handle_screen_confirmation(self, *, now: float | None = None) -> bool:
        """Confirm with the green control, sampling A39 first when required."""

        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        allowed, reason = self._button_can_advance(
            pot_value=None,
            allow_screen_pot_request=True,
        )
        if not allowed:
            self._ignore_input("screen", reason, now=now, action="confirm")
            return False
        if self.mode == "hardware" and self.state is InvestigationState.PROTECT:
            self.blocked_choice_message = "LENDO O A39 REAL NA WISDOM"
            return self._send("ANALOG POT", "screen_pot", now=now)
        return self.handle_button(
            now=now,
            origin="screen",
            control="green_button",
        )

    def _reject_screen_pot(self, reason: str, *, now: float) -> None:
        self.blocked_choice_message = f"A39 NÃO CONFIRMADO: {reason}"
        self._log(
            "screen_confirmation_rejected",
            state=self.state.value,
            reason=reason,
        )
        self.note_interaction(now=now)

    def _button_can_advance(
        self,
        *,
        pot_value: int | None,
        allow_screen_pot_request: bool = False,
    ) -> tuple[bool, str]:
        if self.pending is not None:
            return False, "comando serial ainda pendente"
        if not self.input_ready():
            return False, "tela ainda não armada"
        if self.state is InvestigationState.ATTRACT:
            return (self.ready, "handshake STAGED_V1 ainda não confirmado")
        expected_choice = {
            InvestigationState.SELECT_MISSION: "mission",
            InvestigationState.SELECT_PROFILE: "profile",
            InvestigationState.SELECT_KEY_MODE: "key_mode",
            InvestigationState.SELECT_GUARD: "guard",
            InvestigationState.DIAGNOSE: "diagnosis",
            InvestigationState.SELECT_RESPONSE: "response",
        }.get(self.state)
        if expected_choice is not None:
            valid = self.pending_choice_kind == expected_choice and bool(self.pending_choice)
            return valid, "selecione uma opção na tela antes de confirmar"
        if self.state in self._STAGE_BY_STATE:
            if not self.stage_ready_for_confirmation:
                return False, "resposta real ou animação ainda incompleta"
            if (
                self.state is InvestigationState.PROTECT
                and pot_value is None
                and self.mode == "hardware"
                and not allow_screen_pot_request
            ):
                return False, "BUTTON_PING sem leitura A39"
            return True, ""
        if self.state is InvestigationState.DEBRIEF:
            return (
                self.end_receipt is not None and self.animation_complete,
                "encerramento real ainda não confirmado",
            )
        if self.state is InvestigationState.ERROR:
            return (
                self.ready and self.fresh_handshake_since_error,
                "recuperação exige handshake novo",
            )
        return False, "botão sem ação nesta tela"

    def handle_button(
        self,
        *,
        now: float | None = None,
        origin: str = "operator",
        uptime_ms: int | None = None,
        pot_value: int | None = None,
        control: str = "",
    ) -> bool:
        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        if self.state not in self._FORWARD_STATES:
            self._ignore_input(origin, "botão sem ação nesta tela", now=now, uptime_ms=uptime_ms)
            return False
        if self.mode == "hardware" and origin not in {"physical", "screen"}:
            self._ignore_input(origin, "origem de confirmação não autorizada", now=now, uptime_ms=uptime_ms)
            return False
        allowed, reason = self._button_can_advance(pot_value=pot_value)
        if not allowed:
            self._ignore_input(origin, reason, now=now, uptime_ms=uptime_ms)
            return False
        if now - self.last_button_at < self.config.button_debounce_seconds:
            self._ignore_input(origin, "debounce", now=now, uptime_ms=uptime_ms)
            return False
        self.last_button_at = now
        self.last_button_uptime_ms = uptime_ms
        self.button_sequence += 1
        self.last_confirmation_origin = origin
        self.note_interaction(now=now)
        self._log(
            "button_confirmed",
            button_seq=self.button_sequence,
            state=self.state.value,
            origin=origin,
            control=control or ("D27" if origin == "physical" else "green_button" if origin == "screen" else origin),
            uptime_ms=uptime_ms,
            pot=pot_value,
            pot_source="BUTTON_PING" if origin == "physical" and pot_value is not None else "ANALOG POT" if origin == "screen" and pot_value is not None else None,
        )
        return self._apply_confirmed_button(now=now, pot_value=pot_value)

    def _confirm_choice(self) -> str:
        value = self.pending_choice
        self._log(
            "choice_confirmed",
            kind=self.pending_choice_kind,
            value=value,
            button_seq=self.button_sequence,
        )
        self.pending_choice = ""
        self.pending_choice_kind = ""
        return value

    def _apply_confirmed_button(self, *, now: float, pot_value: int | None) -> bool:
        if self.state is InvestigationState.ATTRACT:
            self._start_cycle(now)
            return True
        if self.state is InvestigationState.SELECT_MISSION:
            mission_id = self._confirm_choice()
            self.selected_mission = next(mission for mission in self.config.missions if mission.mission_id == mission_id)
            self._advance(InvestigationState.SELECT_PROFILE, reason="mission_confirmed", now=now)
            return True
        if self.state is InvestigationState.SELECT_PROFILE:
            value = self._confirm_choice()
            if value == str(self.config.baseline_mhz):
                self.selected_profile = self.config.baseline_name
                self.selected_profile_mhz = self.config.baseline_mhz
            else:
                self.selected_profile = self.config.limited_name
                self.selected_profile_mhz = self.config.limited_mhz
            self._advance(InvestigationState.SELECT_KEY_MODE, reason="profile_confirmed", now=now)
            return True
        if self.state is InvestigationState.SELECT_KEY_MODE:
            self.selected_key_mode = KeyMode(self._confirm_choice())
            self._advance(InvestigationState.SELECT_GUARD, reason="key_mode_confirmed", now=now)
            return True
        if self.state is InvestigationState.SELECT_GUARD:
            self.selected_guard = GuardMode(self._confirm_choice())
            self._begin_game(now)
            return True
        if self.state is InvestigationState.PREPARE:
            if self._send(f"GAME_PROTECT {self.game_id}", "game_protect", now=now):
                self._reset_animation()
                self._advance(InvestigationState.PROTECT, reason="prepare_confirmed", now=now)
                return True
            return False
        if self.state is InvestigationState.PROTECT:
            assert self.selected_mission is not None
            selected_pot = self.live_pot_value if pot_value is None else pot_value
            self.live_pot_value = selected_pot
            self.selection = fault_selection_from_pot(
                selected_pot,
                len(self.selected_mission.payload_bytes),
                self.config,
            )
            self._log("fault_selection_confirmed", button_seq=self.button_sequence, **asdict(self.selection))
            if self._send(
                f"GAME_TRANSMIT {self.game_id} {self.selection.byte_index} 0x{self.selection.bit_mask:02X}",
                "game_transmit",
                now=now,
            ):
                self._reset_animation()
                self._advance(InvestigationState.TRANSMIT, reason="protect_confirmed", now=now)
                return True
            return False
        if self.state is InvestigationState.TRANSMIT:
            if self._send(f"GAME_VERIFY {self.game_id}", "game_verify", now=now):
                self._reset_animation()
                self._advance(InvestigationState.VERIFY, reason="transmit_confirmed", now=now)
                return True
            return False
        if self.state is InvestigationState.VERIFY:
            self._reset_animation()
            self._advance(InvestigationState.DIAGNOSE, reason="evidence_confirmed", now=now)
            return True
        if self.state is InvestigationState.DIAGNOSE:
            self.selected_diagnosis = self._confirm_choice()
            assert self.incident is not None
            expected = self._EXPECTED_DIAGNOSIS[self.incident]
            self.diagnosis_correct = self.selected_diagnosis == expected
            self._log(
                "diagnosis_confirmed",
                selected=self.selected_diagnosis,
                expected=expected,
                correct=self.diagnosis_correct,
                button_seq=self.button_sequence,
            )
            self._advance(InvestigationState.SELECT_RESPONSE, reason="diagnosis_confirmed", now=now)
            return True
        if self.state is InvestigationState.SELECT_RESPONSE:
            decision = OperationalDecision(self._confirm_choice())
            self.operational_decision = decision
            self._log("operational_decision", decision=decision.value, button_seq=self.button_sequence)
            if decision is OperationalDecision.RETRY:
                if self._send(f"GAME_RETRY {self.game_id}", "game_retry", now=now):
                    self._reset_animation()
                    self._advance(InvestigationState.RETRY, reason="retry_confirmed", now=now)
                    return True
                return False
            self.end_decision = decision
            if self._send(f"GAME_END {self.game_id} {decision.value}", "game_end", now=now):
                self._log(
                    "stage_started",
                    game_id=self.game_id,
                    stage=GameStage.END.value,
                    button_seq=self.button_sequence,
                )
                self._reset_animation()
                self._advance(InvestigationState.DEBRIEF, reason="response_confirmed", now=now)
                return True
            return False
        if self.state is InvestigationState.RETRY:
            self.end_decision = OperationalDecision.ACCEPT
            self._log("game_end_decision", decision="ACCEPT", after_retry=True, button_seq=self.button_sequence)
            if self._send(f"GAME_END {self.game_id} ACCEPT", "game_end", now=now):
                self._log(
                    "stage_started",
                    game_id=self.game_id,
                    stage=GameStage.END.value,
                    button_seq=self.button_sequence,
                )
                self._reset_animation()
                self._advance(InvestigationState.DEBRIEF, reason="retry_result_confirmed", now=now)
                return True
            return False
        if self.state is InvestigationState.DEBRIEF:
            self._finish_cycle(now)
            return True
        if self.state is InvestigationState.ERROR:
            self._reset_cycle_data()
            self.error_message = ""
            self.fresh_handshake_since_error = False
            self.transition(
                InvestigationState.ATTRACT,
                reason="confirmed_recovery",
                now=now,
                cause="button",
                button_seq=self.button_sequence,
                confirmation_origin=self.last_confirmation_origin,
            )
            return True
        return False

    def _start_cycle(self, now: float) -> None:
        self._reset_cycle_data()
        self.cycle_index += 1
        self.cycle_started_at = now
        self.cycle_target_logged = False
        self._advance(InvestigationState.SELECT_MISSION, reason="confirmed_start", now=now)
        self._log("cycle_start", cycle=self.cycle_index, mode=self.mode, button_seq=self.button_sequence)

    def _begin_game(self, now: float) -> None:
        assert self.selected_mission is not None
        assert self.selected_key_mode is not None
        assert self.selected_guard is not None
        self.incident = self.forced_incident or self._incident_order[(self.cycle_index - 1) % len(self._incident_order)]
        self.game_id = f"G{self.cycle_index:06d}"
        self.incident_id = f"{self.game_id}-{self.incident.value}"
        command = (
            f"GAME_BEGIN {self.game_id} {self.selected_profile} {self.selected_key_mode.value} "
            f"{self.selected_guard.value} {self.incident.value} {self.selected_mission.payload_hex}"
        )
        self._log("incident_armed", game_id=self.game_id, incident=self.incident.value)
        if self._send(command, "game_begin", now=now):
            self._reset_animation()
            self._advance(InvestigationState.PREPARE, reason="guard_confirmed", now=now)

    def _finish_cycle(self, now: float) -> None:
        self.completed_cycles += 1
        self.last_cycle_duration = now - self.cycle_started_at if self.cycle_started_at is not None else None
        self._log(
            "cycle_complete",
            cycle=self.cycle_index,
            game_id=self.game_id,
            duration_seconds=self.last_cycle_duration,
            incident=self.incident.value if self.incident else None,
            diagnosis=self.selected_diagnosis,
            diagnosis_correct=self.diagnosis_correct,
            decision=self.operational_decision.value if self.operational_decision else None,
            result=asdict(self.result) if self.result else None,
            retry_result=asdict(self.retry_result) if self.retry_result else None,
        )
        self._reset_cycle_data()
        self.transition(
            InvestigationState.ATTRACT,
            reason="debrief_confirmed",
            now=now,
            cause="button",
            button_seq=self.button_sequence,
            confirmation_origin=self.last_confirmation_origin,
        )

    def note_interaction(self, *, now: float | None = None) -> None:
        self.last_interaction_at = time.monotonic() if now is None else now
        self.last_clock_at = self.last_interaction_at

    def _ignore_input(
        self,
        origin: str,
        reason: str,
        *,
        now: float,
        action: str = "",
        uptime_ms: int | None = None,
    ) -> None:
        self.ignored_inputs += 1
        self._log(
            "input_ignored",
            origin=origin,
            action=action,
            reason=reason,
            state=self.state.value,
            state_elapsed=self.state_elapsed(now),
            uptime_ms=uptime_ms,
        )

    def set_forced_incident(self, incident: str | None) -> None:
        self.forced_incident = IncidentScenario(incident) if incident else None

    def set_simulated_pot(self, value: int) -> None:
        self.live_pot_value = max(self.config.pot_minimum, min(self.config.pot_maximum, int(value)))

    def abort(self, *, reason: str, now: float | None = None) -> None:
        self._enter_error(f"partida abortada: {reason}", now=now)

    def _best_effort_abort_and_handshake(self, now: float) -> None:
        if not self.connected:
            return
        if self.game_id:
            try:
                abort_command = f"GAME_ABORT {self.game_id}".upper()
                self._ignored_response_commands.add(abort_command)
                self.send_command(abort_command, timeout=self.config.serial_timeout_seconds)
            except Exception as exc:
                self._ignored_response_commands.discard(abort_command)
                self._log("abort_enqueue_failed", message=str(exc), game_id=self.game_id)
        try:
            self.pending = PendingCommand(
                command="HELLO",
                purpose="handshake_retry",
                deadline=now + self.config.serial_timeout_seconds,
                expected={},
            )
            self.send_command("HELLO", timeout=self.config.serial_timeout_seconds)
            self._log("command_sent", command="HELLO", purpose="handshake_retry", state=self.state.value)
        except Exception as exc:
            self.pending = None
            self._log("recovery_enqueue_failed", message=str(exc))

    def _enter_error(
        self,
        message: str,
        *,
        now: float | None = None,
        request_handshake: bool = True,
    ) -> None:
        now = time.monotonic() if now is None else now
        if self.cycle_started_at is not None:
            self._log("cycle_aborted", cycle=self.cycle_index, game_id=self.game_id, state=self.state.value, reason=message)
        self.error_message = message
        self.pending = None
        self.error_handshake_generation = self.handshake_generation
        self.fresh_handshake_since_error = False
        self.handshake_ok = False
        if self.state is not InvestigationState.ERROR:
            self.transition(InvestigationState.ERROR, reason="fatal_error", now=now, cause="error")
        self._log("error", message=message, state=self.state.value)
        self._clear_outcomes_after_error()
        if request_handshake:
            self._best_effort_abort_and_handshake(now)

    def _clear_outcomes_after_error(self) -> None:
        self.stage_measurements = {}
        self.result = None
        self.retry_result = None
        self.end_receipt = None
        self.selection = None
        self.animation_stage = ""
        self.animation_started_at = None
        self.animation_deadline = None
        self.animation_complete = False

    def _reset_animation(self) -> None:
        self.animation_stage = ""
        self.animation_started_at = None
        self.animation_deadline = None
        self.animation_complete = False

    def _reset_cycle_data(self) -> None:
        self.pending = None
        self.pending_choice = ""
        self.pending_choice_kind = ""
        self.blocked_choice_message = ""
        self.selected_mission = None
        self.selected_profile = ""
        self.selected_profile_mhz = 0
        self.selected_key_mode = None
        self.selected_guard = None
        self.incident = None
        self.incident_id = ""
        self.game_id = ""
        self.selection = None
        self.stage_measurements = {}
        self.result = None
        self.retry_result = None
        self.end_receipt = None
        self.selected_diagnosis = ""
        self.diagnosis_correct = None
        self.operational_decision = None
        self.end_decision = None
        self.explanation_mode = "quick"
        self.blocked_choice_message = ""
        self.cycle_started_at = None
        self.cycle_target_logged = False
        self._reset_animation()

    def reset_to_attract(self, *, reason: str, now: float | None = None) -> None:
        """Compatibility hook: active public games are aborted, never silently reset."""
        now = time.monotonic() if now is None else now
        if self.state is InvestigationState.ATTRACT and not self.game_id:
            return
        if reason in {"debrief_complete", "test_setup"}:
            self._reset_cycle_data()
            self.transition(InvestigationState.ATTRACT, reason=reason, now=now, cause="administrative")
            return
        self.abort(reason=reason, now=now)

    def update(self, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.last_clock_at = now
        if self.pending is not None and now >= self.pending.deadline:
            command = self.pending.command
            purpose = self.pending.purpose
            self.pending = None
            if purpose == "screen_pot":
                self._reject_screen_pot(f"timeout aguardando {command}", now=now)
                return
            self._enter_error(f"timeout aguardando {command.split()[0]}", now=now)
            return
        if self.animation_deadline is not None and not self.animation_complete and now >= self.animation_deadline:
            self.animation_complete = True
            self._log("animation_completed", stage=self.animation_stage)
        if (
            self.cycle_started_at is not None
            and not self.cycle_target_logged
            and now - self.cycle_started_at >= self.config.target_max_seconds
        ):
            self.cycle_target_logged = True
            self._log(
                "cycle_time_target_exceeded",
                cycle=self.cycle_index,
                elapsed_seconds=now - self.cycle_started_at,
                target_seconds=self.config.target_max_seconds,
            )
        # Deliberately no inactivity timeout and no summary auto-reset.


__all__ = ("InvestigationController",)
