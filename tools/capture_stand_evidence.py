#!/usr/bin/env python3
"""Render one provenance-labelled screenshot for every stand state."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pygame

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pqc_sat.ui.capture import render_game_frame  # noqa: E402
from pqc_sat.testing.fixture import FixtureSerialClient  # noqa: E402
from pqc_sat.stand.investigation import InvestigationController  # noqa: E402
from pqc_sat.stand.model import InvestigationState, StandConfig  # noqa: E402
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH  # noqa: E402

INVESTIGATION_STATE_ORDER = (
    InvestigationState.ATTRACT,
    InvestigationState.SELECT_MISSION,
    InvestigationState.SELECT_KEY_MODE,
    InvestigationState.SELECT_GUARD,
    InvestigationState.NEXT_PREPARE,
    InvestigationState.PREPARE,
    InvestigationState.NEXT_PROTECT,
    InvestigationState.PROTECT,
    InvestigationState.NEXT_TRANSMIT,
    InvestigationState.TRANSMIT,
    InvestigationState.NEXT_VERIFY,
    InvestigationState.VERIFY,
    InvestigationState.DIAGNOSE,
    InvestigationState.SELECT_RESPONSE,
    InvestigationState.RETRY,
    InvestigationState.DEBRIEF,
    InvestigationState.ERROR,
)


def build_completed_investigation_controller(
    config_path: Path,
    fixture_path: Path,
    *,
    key_mode: str = "MLKEM",
    incident: str = "RX_MEMORY",
) -> InvestigationController:
    config = replace(
        StandConfig.load(config_path),
        button_debounce_seconds=0.01,
        screen_input_guard_seconds=0.01,
        checkpoint_animation_ms=tuple(
            (stage, 1) for stage in ("PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "DEBRIEF")
        ),
    )
    client = FixtureSerialClient(fixture_path, config, latency_seconds=0)

    def send(command, *, timeout=None):
        client.send(command, timeout=timeout)

    controller = InvestigationController(config, send, mode="simulated", now=0, experiment_seed=42)

    def pump(now):
        for _ in range(20):
            events = client.poll()
            if not events:
                return
            for event_type, payload in events:
                controller.handle_serial_event(event_type, payload, now=now)
        raise RuntimeError("fixture investigativa não estabilizou")

    client.start()
    pump(0)
    controller.set_forced_incident(incident)
    now = 0.1

    def press():
        nonlocal now
        now += 0.03
        if not controller.handle_button(now=now, origin="evidence"):
            raise RuntimeError(f"D27 simulado rejeitado em {controller.state.value}")
        pump(now + 0.001)

    def choose(action):
        nonlocal now
        now += 0.03
        if not controller.handle_action(action, now=now):
            raise RuntimeError(f"escolha rejeitada: {action}")
        press()

    def finish_stage():
        nonlocal now
        pump(now + 0.001)
        now = max(now + 0.03, (controller.animation_deadline or now) + 0.01)
        controller.update(now=now)
        press()
        if controller.state.value.startswith("NEXT_"):
            press()

    press()
    choose("mission:TELEMETRY")
    choose(f"key:{key_mode}")
    choose("guard:CRC32")
    press()  # NEXT_PREPARE -> GAME_BEGIN -> PREPARE
    finish_stage()  # PREPARE -> NEXT_PROTECT -> PROTECT
    finish_stage()  # PROTECT -> NEXT_TRANSMIT -> TRANSMIT
    finish_stage()  # TRANSMIT -> NEXT_VERIFY -> VERIFY
    finish_stage()  # VERIFY -> DIAGNOSE
    diagnosis = "NORMAL" if incident == "NORMAL" else "INTRUSION" if incident == "TAMPER" else "RADIATION"
    choose(f"diagnosis:{diagnosis}")
    choose("response:RETRY")
    finish_stage()  # RETRY -> DEBRIEF/GAME_END
    pump(now + 0.01)
    now = max(now + 0.03, (controller.animation_deadline or now) + 0.01)
    controller.update(now=now)
    if controller.state != InvestigationState.DEBRIEF:
        raise RuntimeError(f"fluxo investigativo terminou em {controller.state.value}")
    client.stop()
    return controller


def prepare_investigation_capture_state(controller: InvestigationController, state: InvestigationState) -> None:
    """Remove future choices from screenshots of earlier visitor states."""
    if not hasattr(controller, "_evidence_completed_context"):
        controller._evidence_completed_context = {
            "selected_mission": controller.selected_mission,
            "selected_profile": controller.selected_profile,
            "selected_profile_mhz": controller.selected_profile_mhz,
            "selected_key_mode": controller.selected_key_mode,
            "selected_guard": controller.selected_guard,
            "incident": controller.incident,
            "incident_id": controller.incident_id,
            "game_id": controller.game_id,
            "selection": controller.selection,
            "stage_measurements": dict(controller.stage_measurements),
            "result": controller.result,
            "retry_result": controller.retry_result,
            "end_receipt": controller.end_receipt,
            "selected_diagnosis": controller.selected_diagnosis,
            "diagnosis_correct": controller.diagnosis_correct,
            "operational_decision": controller.operational_decision,
        }
    for name, value in controller._evidence_completed_context.items():
        setattr(controller, name, value)

    controller.pending = None
    controller.pending_choice = ""
    controller.pending_choice_kind = ""
    controller.animation_complete = True
    if state in {InvestigationState.ATTRACT, InvestigationState.SELECT_MISSION, InvestigationState.ERROR}:
        controller.selected_mission = None
    if state in {
        InvestigationState.ATTRACT,
        InvestigationState.SELECT_MISSION,
        InvestigationState.ERROR,
    }:
        controller.selected_profile = ""
        controller.selected_profile_mhz = 0
    if state in {
        InvestigationState.ATTRACT,
        InvestigationState.SELECT_MISSION,
        InvestigationState.SELECT_KEY_MODE,
        InvestigationState.ERROR,
    }:
        controller.selected_key_mode = None
    if state in {
        InvestigationState.ATTRACT,
        InvestigationState.SELECT_MISSION,
        InvestigationState.SELECT_KEY_MODE,
        InvestigationState.SELECT_GUARD,
        InvestigationState.NEXT_PREPARE,
        InvestigationState.ERROR,
    }:
        controller.selected_guard = None
    if state in {
        InvestigationState.ATTRACT,
        InvestigationState.SELECT_MISSION,
        InvestigationState.SELECT_KEY_MODE,
        InvestigationState.SELECT_GUARD,
        InvestigationState.NEXT_PREPARE,
        InvestigationState.ERROR,
    }:
        controller.incident = None
        controller.incident_id = ""
        controller.game_id = ""
        controller.selection = None
        controller.stage_measurements = {}
        controller.result = None
        controller.retry_result = None
        controller.end_receipt = None
        controller.selected_diagnosis = ""
        controller.diagnosis_correct = None
        controller.operational_decision = None
    stage_limits = {
        InvestigationState.NEXT_PREPARE: set(),
        InvestigationState.PREPARE: {"PREPARE"},
        InvestigationState.NEXT_PROTECT: {"PREPARE"},
        InvestigationState.PROTECT: {"PREPARE", "PROTECT"},
        InvestigationState.NEXT_TRANSMIT: {"PREPARE", "PROTECT"},
        InvestigationState.TRANSMIT: {"PREPARE", "PROTECT", "TRANSMIT"},
        InvestigationState.NEXT_VERIFY: {"PREPARE", "PROTECT", "TRANSMIT"},
    }
    if state in stage_limits:
        allowed = stage_limits[state]
        controller.stage_measurements = {
            stage: value for stage, value in controller.stage_measurements.items() if stage.value in allowed
        }
        controller.result = None
        controller.retry_result = None
        controller.end_receipt = None
        controller.selected_diagnosis = ""
        controller.diagnosis_correct = None
        controller.operational_decision = None
    if state in {InvestigationState.NEXT_VERIFY, InvestigationState.VERIFY, InvestigationState.DIAGNOSE}:
        controller.retry_result = None
        controller.end_receipt = None
        controller.selected_diagnosis = ""
        controller.diagnosis_correct = None
        controller.operational_decision = None
    if state is InvestigationState.SELECT_RESPONSE:
        controller.retry_result = None
        controller.end_receipt = None
        controller.operational_decision = None
    if state is InvestigationState.RETRY:
        controller.end_receipt = None
    if state is InvestigationState.ERROR:
        controller.error_message = "Exemplo seguro: resposta fora de ordem; sessão apagada"
        controller.fresh_handshake_since_error = False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "stand" / "evidence" / "states_staged_game")
    parser.add_argument(
        "--replay-output-dir",
        type=Path,
        help="diretório opcional para quadros inicial/intermediário/final dos processos visuais",
    )
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    args = parser.parse_args(argv)

    pygame.init()
    controller = build_completed_investigation_controller(args.config, args.fixture)
    state_order = INVESTIGATION_STATE_ORDER
    args.output_dir.mkdir(parents=True, exist_ok=True)
    legacy_tutorial = args.output_dir / f"00b_tutorial_{args.width}x{args.height}.png"
    if legacy_tutorial.exists():
        legacy_tutorial.unlink()
    search_frame = render_game_frame(
        controller,
        size=(args.width, args.height),
        now=2.0,
        search_active=True,
    )
    search_output = args.output_dir / f"000_search_{args.width}x{args.height}.png"
    pygame.image.save(search_frame, search_output)
    print(search_output)
    for index, state in enumerate(state_order):
        prepare_investigation_capture_state(controller, state)
        controller.state = state
        controller.state_entered_at = 0.0
        controller.last_interaction_at = 2.0
        if hasattr(controller, "last_clock_at"):
            controller.last_clock_at = 2.0
        if state.value == "ERROR":
            controller.error_message = "Exemplo de recuperação: timeout aguardando a Wisdom"
            controller.connection_status = "USB desconectado — reconecte e tente novamente"
        frame = render_game_frame(
            controller,
            size=(args.width, args.height),
            now=2.0,
            replay_progress=0.6 if state is InvestigationState.TRANSMIT else None,
        )
        output = args.output_dir / f"{index:02d}_{state.value.lower()}_{args.width}x{args.height}.png"
        pygame.image.save(frame, output)
        print(output)
        selected_actions = {
            InvestigationState.SELECT_MISSION: "mission:TELEMETRY",
            InvestigationState.SELECT_KEY_MODE: "key:MLKEM",
        }
        if state in selected_actions:
            if not controller.handle_action(selected_actions[state], now=2.1):
                raise RuntimeError(f"captura da escolha selecionada foi rejeitada: {state.value}")
            selected_frame = render_game_frame(
                controller,
                size=(args.width, args.height),
                now=2.1,
            )
            selected_output = args.output_dir / f"{index:02d}b_{state.value.lower()}_selected_{args.width}x{args.height}.png"
            pygame.image.save(selected_frame, selected_output)
            print(selected_output)
    if args.replay_output_dir is not None:
        args.replay_output_dir.mkdir(parents=True, exist_ok=True)
        replay_states = (
            InvestigationState.PREPARE,
            InvestigationState.PROTECT,
            InvestigationState.TRANSMIT,
            InvestigationState.VERIFY,
            InvestigationState.RETRY,
            InvestigationState.DEBRIEF,
        )
        positions = (("inicio", 0.0), ("meio", 0.5), ("fim", 1.0))
        for state in replay_states:
            prepare_investigation_capture_state(controller, state)
            controller.state = state
            controller.state_entered_at = 0.0
            controller.last_clock_at = 2.0
            controller.animation_complete = True
            for label, progress in positions:
                capture_progress = 0.6 if state is InvestigationState.TRANSMIT and label == "meio" else progress
                frame = render_game_frame(
                    controller,
                    size=(args.width, args.height),
                    now=2.0,
                    replay_progress=capture_progress,
                )
                output = args.replay_output_dir / f"{state.value.lower()}_{label}_{args.width}x{args.height}.png"
                pygame.image.save(frame, output)
                print(output)

        ecdh_controller = build_completed_investigation_controller(
            args.config,
            args.fixture,
            key_mode="ECDH",
        )
        prepare_investigation_capture_state(ecdh_controller, InvestigationState.PROTECT)
        ecdh_controller.state = InvestigationState.PROTECT
        ecdh_controller.state_entered_at = 0.0
        ecdh_controller.last_clock_at = 2.0
        ecdh_controller.animation_complete = True
        for label, progress in positions:
            frame = render_game_frame(
                ecdh_controller,
                size=(args.width, args.height),
                now=2.0,
                replay_progress=progress,
            )
            output = args.replay_output_dir / f"protect_ecdh_{label}_{args.width}x{args.height}.png"
            pygame.image.save(frame, output)
            print(output)

        normal_controller = build_completed_investigation_controller(
            args.config,
            args.fixture,
            incident="NORMAL",
        )
        prepare_investigation_capture_state(normal_controller, InvestigationState.TRANSMIT)
        normal_controller.state = InvestigationState.TRANSMIT
        normal_controller.state_entered_at = 0.0
        normal_controller.last_clock_at = 2.0
        normal_controller.animation_complete = True
        for label, progress in positions:
            frame = render_game_frame(
                normal_controller,
                size=(args.width, args.height),
                now=2.0,
                replay_progress=progress,
            )
            output = args.replay_output_dir / f"transmit_normal_{label}_{args.width}x{args.height}.png"
            pygame.image.save(frame, output)
            print(output)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
