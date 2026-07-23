import json
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

import pygame

from pqc_sat.ui.capture import render_game_frame
from pqc_sat.ui.game import GamePanel
from pqc_sat.testing.fixture import FixtureSerialClient
from pqc_sat.stand.investigation import InvestigationController
from pqc_sat.stand.model import (
    FaultSelection,
    GameStage,
    GuardMode,
    IncidentScenario,
    InvestigationState,
    KeyMode,
    OperationalDecision,
    PendingCommand,
    StandConfig,
    StandProtocolError,
    expected_game_outcome,
    parse_game_end_response,
    parse_game_result_response,
    parse_game_stage_response,
    scenario_for,
)
from pqc_sat.stand.session import StandSessionLogger
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH
from tools.capture_stand_evidence import (
    INVESTIGATION_STATE_ORDER,
    build_completed_investigation_controller,
    prepare_investigation_capture_state,
)
from tools.investigation_metrics_battery import build_matrix
from tools.validate_stand_logs import count_pot_activity, load_records, validate_physical_transition_causes


class MemoryLogger:
    def __init__(self):
        self.records = []

    def write(self, event, **fields):
        self.records.append({"event": event, **fields})


def fast_config():
    return replace(
        StandConfig.load(DEFAULT_CONFIG_PATH),
        button_debounce_seconds=0.01,
        screen_input_guard_seconds=0.01,
        checkpoint_animation_ms=tuple(
            (stage, 1)
            for stage in ("PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "DEBRIEF")
        ),
    )


def connect_panel_to_wisdom(panel, *, now=10.0, uptime_ms=100):
    panel._handle_serial_input(
        "state",
        {"connected": False, "status": "ABRINDO /dev/ttyUSB0", "port": "/dev/ttyUSB0"},
        now=now,
    )
    panel._handle_serial_input(
        "response",
        {
            "command": "HELLO",
            "status": "OK",
            "payload": {
                "node": "PQC-SAT-WISDOM",
                "board": "BlackBoard-Wisdom",
                "proto": "V1",
                "game": "STAGED_V1",
                "uptime_ms": str(uptime_ms),
            },
        },
        now=now + 0.01,
    )
    panel._handle_serial_input(
        "state",
        {"connected": True, "status": "WISDOM /dev/ttyUSB0", "port": "/dev/ttyUSB0"},
        now=now + 0.02,
    )


class StagedHarness:
    def __init__(self, *, incident="RX_MEMORY", key_mode="PQC", guard="CRC32"):
        self.config = fast_config()
        self.client = FixtureSerialClient(DEFAULT_FIXTURE_PATH, self.config, latency_seconds=0)
        self.logger = MemoryLogger()
        self.commands = []

        def send(command, *, timeout=None):
            self.commands.append(command)
            self.client.send(command, timeout=timeout)

        self.controller = InvestigationController(
            self.config,
            send,
            mode="simulated",
            logger=self.logger,
            now=0,
        )
        self.now = 0.0
        self.client.start()
        self.pump()
        self.controller.set_forced_incident(incident)
        self.key_mode = key_mode
        self.guard = guard

    def pump(self):
        for _ in range(30):
            events = self.client.poll()
            if not events:
                return
            for event_type, payload in events:
                self.controller.handle_serial_event(event_type, payload, now=self.now)
        raise RuntimeError("fixture não estabilizou")

    def tick(self, delta=0.03):
        self.now += delta
        self.controller.update(now=self.now)
        self.pump()

    def press(self):
        self.tick()
        accepted = self.controller.handle_button(now=self.now, origin="test-d27")
        self.pump()
        return accepted

    def choose(self, action):
        self.tick()
        self.assert_action(action)
        self.assert_press()

    def assert_action(self, action):
        if not self.controller.handle_action(action, now=self.now):
            raise AssertionError(f"ação rejeitada: {action} em {self.controller.state.value}")

    def assert_press(self):
        if not self.press():
            raise AssertionError(f"D27 rejeitado em {self.controller.state.value}")

    def finish_animation_and_press(self):
        self.pump()
        self.now = max(self.now + 0.03, (self.controller.animation_deadline or self.now) + 0.01)
        self.controller.update(now=self.now)
        self.assert_press()

    def reach_prepare(self):
        self.assert_press()
        self.choose("mission:TELEMETRY")
        self.choose("profile:240")
        self.choose(f"key:{self.key_mode}")
        self.choose(f"guard:{self.guard}")
        self.pump()
        return self.controller

    def reach_verify(self):
        self.reach_prepare()
        self.finish_animation_and_press()
        self.controller.set_simulated_pot(4095)
        self.finish_animation_and_press()
        self.finish_animation_and_press()
        self.pump()
        return self.controller

    def reach_response(self):
        self.reach_verify()
        self.finish_animation_and_press()
        expected = self.controller._EXPECTED_DIAGNOSIS[self.controller.incident]
        self.choose(f"diagnosis:{expected}")
        return self.controller

    def finish(self, decision="SAFE_MODE"):
        self.reach_response()
        self.choose(f"response:{decision}")
        if decision == "RETRY":
            self.finish_animation_and_press()
        self.pump()
        self.now = max(self.now + 0.03, (self.controller.animation_deadline or self.now) + 0.01)
        self.controller.update(now=self.now)
        self.assert_press()
        return self.controller


class StagedConfigurationTests(unittest.TestCase):
    def test_v3_configuration_is_typed_and_disables_public_timeouts(self):
        config = StandConfig.load(DEFAULT_CONFIG_PATH)
        raw = json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], "pqc-sat-stand-config-v3")
        self.assertFalse(config.public_interaction_timeout_enabled)
        self.assertFalse(config.public_auto_reset_enabled)
        self.assertEqual([mission.deadline_ms for mission in config.missions], [2000, 500, 10000])
        self.assertEqual(set(dict(config.checkpoint_animation_ms)), {"PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "DEBRIEF"})

    def test_controlled_battery_covers_four_protections_four_incidents_two_profiles(self):
        rows = list(build_matrix(StandConfig.load(DEFAULT_CONFIG_PATH), 1))
        combinations = {(profile, key_mode.value, guard.value, incident.value) for profile, _, _, key_mode, guard, incident, _, _ in rows}
        self.assertEqual(len(rows), 32)
        self.assertEqual(len(combinations), 32)
        self.assertEqual(
            {scenario_for(key_mode, guard) for key_mode in KeyMode for guard in GuardMode},
            {"CLASSIC", "CLASSIC_CRC32", "PQC", "PQC_CRC32"},
        )

    def test_maximum_game_begin_fits_firmware_input_buffer(self):
        payload_hex = bytes(range(96)).hex().upper()
        command = f"V1|999999|GAME_BEGIN|G999999|OBC-1U-LIMITED|PQC|CRC32|CHANNEL_BITFLIP|{payload_hex}\n"
        self.assertLessEqual(len(command), 384)


class StagedTruthTableTests(unittest.TestCase):
    def test_fixture_and_strict_parsers_cover_full_scientific_matrix(self):
        config = fast_config()
        selection = FaultSelection(0, 1, 0, 0)
        for profile, profile_mhz in ((config.baseline_name, 240), (config.limited_name, 80)):
            for key_mode in KeyMode:
                for guard in GuardMode:
                    for incident in IncidentScenario:
                        with self.subTest(profile=profile, key=key_mode, guard=guard, incident=incident):
                            fixture = FixtureSerialClient(DEFAULT_FIXTURE_PATH, config, latency_seconds=0)
                            game_id = "MATRIX"
                            common = dict(
                                game_id=game_id,
                                profile=profile,
                                profile_mhz=profile_mhz,
                                key_mode=key_mode,
                                guard=guard,
                                payload_len=len(config.missions[0].payload_bytes),
                                source="deterministic-offline-model",
                            )
                            begin = f"GAME_BEGIN {game_id} {profile} {key_mode.value} {guard.value} {incident.value} {config.missions[0].payload_hex}"
                            prepare_payload = fixture._build_response(begin)[1]["payload"]
                            parse_game_stage_response(
                                begin,
                                prepare_payload,
                                stage=GameStage.PREPARE,
                                payload_bytes=config.missions[0].payload_bytes,
                                **common,
                            )
                            protect = f"GAME_PROTECT {game_id}"
                            protect_result = parse_game_stage_response(
                                protect, fixture._build_response(protect)[1]["payload"], stage=GameStage.PROTECT, **common
                            )
                            transmit = f"GAME_TRANSMIT {game_id} 0 0x01"
                            parse_game_stage_response(
                                transmit,
                                fixture._build_response(transmit)[1]["payload"],
                                stage=GameStage.TRANSMIT,
                                incident=incident,
                                selection=selection,
                                **common,
                            )
                            verify = f"GAME_VERIFY {game_id}"
                            parsed = parse_game_result_response(
                                verify,
                                fixture._build_response(verify)[1]["payload"],
                                stage=GameStage.VERIFY,
                                incident=incident,
                                selection=selection,
                                **common,
                            )
                            self.assertEqual(parsed.result, expected_game_outcome(incident, guard)["result"])
                            if incident is not IncidentScenario.NORMAL:
                                retry = f"GAME_RETRY {game_id}"
                                retried = parse_game_result_response(
                                    retry,
                                    fixture._build_response(retry)[1]["payload"],
                                    stage=GameStage.RETRY,
                                    incident=incident,
                                    selection=selection,
                                    initial_protect=protect_result,
                                    **common,
                                )
                                self.assertEqual(retried.result, "DELIVERED")

    def test_rx_memory_is_silent_without_crc_and_rejected_with_crc(self):
        self.assertEqual(expected_game_outcome("RX_MEMORY", "NONE")["result"], "SILENT_CORRUPTION")
        self.assertEqual(expected_game_outcome("RX_MEMORY", "CRC32")["result"], "APP_REJECT")

    def test_stage_parser_rejects_crc_values_that_contradict_the_payload_or_flag(self):
        config = fast_config()
        mission = config.missions[0]
        fixture = FixtureSerialClient(DEFAULT_FIXTURE_PATH, config, latency_seconds=0)
        game_id = "CRC-CHECK"
        common = dict(
            game_id=game_id,
            profile=config.baseline_name,
            profile_mhz=config.baseline_mhz,
            key_mode=KeyMode.PQC,
            guard=GuardMode.CRC32,
            payload_len=len(mission.payload_bytes),
            source="test",
        )
        begin = f"GAME_BEGIN {game_id} {config.baseline_name} PQC CRC32 CHANNEL_BITFLIP {mission.payload_hex}"
        prepare = dict(fixture._build_response(begin)[1]["payload"])
        prepare["payload_crc32"] = "0x00000000"
        with self.assertRaisesRegex(StandProtocolError, "CRC do payload"):
            parse_game_stage_response(
                begin,
                prepare,
                stage=GameStage.PREPARE,
                payload_bytes=mission.payload_bytes,
                **common,
            )
        protect = f"GAME_PROTECT {game_id}"
        fixture._build_response(protect)
        transmit = f"GAME_TRANSMIT {game_id} 0 0x01"
        transmitted = dict(fixture._build_response(transmit)[1]["payload"])
        transmitted["frame_crc_rx"] = transmitted["frame_crc_tx"]
        with self.assertRaisesRegex(StandProtocolError, "flag e valores"):
            parse_game_stage_response(
                transmit,
                transmitted,
                stage=GameStage.TRANSMIT,
                incident=IncidentScenario.CHANNEL_BITFLIP,
                selection=FaultSelection(0, 1, 0, 0),
                **common,
            )

    def test_fixture_rejects_wrong_order_and_clears_session(self):
        fixture = FixtureSerialClient(DEFAULT_FIXTURE_PATH, fast_config(), latency_seconds=0)
        response = fixture._build_response("GAME_VERIFY WRONG")[1]
        self.assertEqual(response["status"], "ERROR")
        self.assertEqual(response["payload"]["code"], "BAD_GAME_STATE")
        self.assertIsNone(fixture._game)

    def test_a39_read_during_protect_preserves_transactional_game(self):
        fixture = FixtureSerialClient(DEFAULT_FIXTURE_PATH, fast_config(), latency_seconds=0)
        fixture.set_pot(1469)
        begin = "GAME_BEGIN G-A39 BASELINE PQC CRC32 TAMPER 54454D503D383443"

        self.assertEqual(fixture._build_response(begin)[1]["status"], "OK")
        self.assertEqual(fixture._build_response("GAME_PROTECT G-A39")[1]["status"], "OK")

        a39 = fixture._build_response("ANALOG POT")[1]
        self.assertEqual(a39["status"], "OK")
        self.assertEqual(a39["payload"]["pot"], "1469")
        self.assertIsNotNone(fixture._game)
        self.assertEqual(fixture._game["state"], "PROTECT")

        transmitted = fixture._build_response("GAME_TRANSMIT G-A39 0 0x01")[1]
        self.assertEqual(transmitted["status"], "OK")
        self.assertEqual(transmitted["payload"]["stage"], "TRANSMIT")

    def test_game_end_rejects_a_final_result_that_contradicts_verify(self):
        payload = {
            "game_id": "G1",
            "stage": "END",
            "decision": "SAFE_MODE",
            "final_result": "DELIVERED",
            "session_cleared": "1",
            "restored_profile": "BASELINE",
            "restored_mhz": "240",
        }
        with self.assertRaisesRegex(StandProtocolError, "contradiz"):
            parse_game_end_response(
                "GAME_END G1 SAFE_MODE",
                payload,
                game_id="G1",
                decision=OperationalDecision.SAFE_MODE,
                expected_final_result="AUTH_REJECT",
                baseline_profile="BASELINE",
                baseline_mhz=240,
                source="test",
            )


class StagedControllerTests(unittest.TestCase):
    def test_touch_selects_but_never_changes_phase(self):
        harness = StagedHarness()
        harness.assert_press()
        before = harness.controller.state
        harness.tick()
        self.assertTrue(harness.controller.handle_action("mission:TELEMETRY", now=harness.now))
        self.assertEqual(harness.controller.state, before)
        self.assertEqual(harness.controller.pending_choice, "TELEMETRY")
        harness.tick(20)
        harness.controller.update(now=harness.now)
        self.assertEqual(harness.controller.state, before)

    def test_d27_without_pending_choice_does_not_advance_or_consume_debounce(self):
        harness = StagedHarness()
        harness.assert_press()
        accepted_at = harness.controller.last_button_at
        harness.tick()
        self.assertFalse(harness.controller.handle_button(now=harness.now, origin="test-d27"))
        self.assertEqual(harness.controller.state, InvestigationState.SELECT_MISSION)
        self.assertEqual(harness.controller.last_button_at, accepted_at)
        harness.assert_action("mission:TELEMETRY")
        harness.tick()
        self.assertTrue(harness.controller.handle_button(now=harness.now, origin="test-d27"))

    def test_response_and_animation_only_unlock_next_d27(self):
        harness = StagedHarness()
        controller = harness.reach_prepare()
        self.assertEqual(controller.state, InvestigationState.PREPARE)
        self.assertIsNotNone(controller.current_stage_measurement)
        deadline = controller.animation_deadline
        controller.update(now=deadline + 1)
        self.assertEqual(controller.state, InvestigationState.PREPARE)
        self.assertTrue(controller.animation_complete)
        harness.now = deadline + 1.1
        harness.assert_press()
        self.assertEqual(controller.state, InvestigationState.PROTECT)

    def test_green_control_confirms_a_selected_choice_and_logs_screen_origin(self):
        harness = StagedHarness()
        harness.assert_press()
        harness.tick()
        harness.assert_action("mission:TELEMETRY")
        harness.tick()
        self.assertTrue(harness.controller.handle_action("confirm", now=harness.now))
        self.assertEqual(harness.controller.state, InvestigationState.SELECT_PROFILE)
        confirmation = next(
            record
            for record in reversed(harness.logger.records)
            if record["event"] == "button_confirmed"
        )
        self.assertEqual(confirmation["origin"], "screen")
        self.assertEqual(confirmation["control"], "green_button")
        transition = next(
            record
            for record in reversed(harness.logger.records)
            if record["event"] == "transition"
        )
        self.assertEqual(transition["confirmation_origin"], "screen")

    def test_green_control_can_confirm_every_public_game_transition(self):
        harness = StagedHarness()

        def confirm():
            harness.tick()
            self.assertTrue(harness.controller.handle_action("confirm", now=harness.now))
            harness.pump()

        def select(action):
            harness.tick()
            harness.assert_action(action)
            confirm()

        def finish_stage():
            harness.pump()
            harness.now = max(
                harness.now + 0.03,
                (harness.controller.animation_deadline or harness.now) + 0.01,
            )
            harness.controller.update(now=harness.now)
            confirm()

        confirm()  # ATTRACT
        select("mission:TELEMETRY")
        select("profile:240")
        select("key:PQC")
        select("guard:CRC32")
        finish_stage()  # PREPARE
        harness.controller.set_simulated_pot(3072)
        finish_stage()  # PROTECT
        finish_stage()  # TRANSMIT
        finish_stage()  # VERIFY
        expected = harness.controller._EXPECTED_DIAGNOSIS[harness.controller.incident]
        select(f"diagnosis:{expected}")
        select("response:RETRY")
        finish_stage()  # RETRY
        harness.pump()
        harness.now = max(
            harness.now + 0.03,
            (harness.controller.animation_deadline or harness.now) + 0.01,
        )
        harness.controller.update(now=harness.now)
        confirm()  # DEBRIEF

        self.assertEqual(harness.controller.state, InvestigationState.ATTRACT)
        self.assertEqual(harness.controller.completed_cycles, 1)
        origins = {
            record["origin"]
            for record in harness.logger.records
            if record["event"] == "button_confirmed"
        }
        self.assertEqual(origins, {"screen"})

    def test_green_control_samples_real_a39_before_protect_transition(self):
        harness = StagedHarness()
        controller = harness.reach_prepare()
        harness.now = max(harness.now + 0.03, (controller.animation_deadline or harness.now) + 0.01)
        controller.update(now=harness.now)
        harness.assert_press()
        self.assertEqual(controller.state, InvestigationState.PROTECT)
        harness.now = max(harness.now + 0.03, (controller.animation_deadline or harness.now) + 0.01)
        controller.update(now=harness.now)
        harness.client.set_pot(3072)
        controller.mode = "hardware"

        self.assertTrue(controller.handle_action("confirm", now=harness.now))
        self.assertIsNotNone(controller.pending)
        self.assertEqual(controller.pending.purpose, "screen_pot")
        self.assertEqual(harness.commands[-1], "ANALOG POT")
        self.assertEqual(controller.state, InvestigationState.PROTECT)

        harness.pump()
        self.assertEqual(controller.state, InvestigationState.TRANSMIT)
        self.assertEqual(controller.selection.pot_value, 3072)
        confirmation = next(
            record
            for record in reversed(harness.logger.records)
            if record["event"] == "button_confirmed"
        )
        self.assertEqual(confirmation["origin"], "screen")
        self.assertEqual(confirmation["pot_source"], "ANALOG POT")

    def test_invalid_or_timed_out_screen_a39_never_advances(self):
        harness = StagedHarness()
        controller = harness.reach_prepare()
        harness.now = max(harness.now + 0.03, (controller.animation_deadline or harness.now) + 0.01)
        controller.update(now=harness.now)
        harness.assert_press()
        harness.now = max(harness.now + 0.03, (controller.animation_deadline or harness.now) + 0.01)
        controller.update(now=harness.now)
        controller.mode = "hardware"

        self.assertTrue(controller.handle_action("confirm", now=harness.now))
        controller.handle_serial_event(
            "response",
            {"command": "ANALOG POT", "status": "OK", "payload": {"pot": "9000"}},
            now=harness.now + 0.01,
        )
        self.assertEqual(controller.state, InvestigationState.PROTECT)
        self.assertIsNone(controller.pending)
        self.assertIn("A39 NÃO CONFIRMADO", controller.blocked_choice_message)
        self.assertTrue(controller.ready)

        harness.now += 0.03
        self.assertTrue(controller.handle_action("confirm", now=harness.now))
        deadline = controller.pending.deadline
        controller.update(now=deadline + 0.01)
        self.assertEqual(controller.state, InvestigationState.PROTECT)
        self.assertIsNone(controller.pending)
        self.assertIn("timeout", controller.blocked_choice_message)
        self.assertTrue(controller.ready)

    def test_every_forward_transition_is_logged_with_the_confirming_button(self):
        harness = StagedHarness()
        controller = harness.finish("RETRY")
        self.assertEqual(controller.state, InvestigationState.ATTRACT)
        self.assertEqual(controller.completed_cycles, 1)
        buttons = {record["button_seq"] for record in harness.logger.records if record["event"] == "button_confirmed"}
        transitions = [record for record in harness.logger.records if record["event"] == "transition" and record["state"] != "ERROR"]
        self.assertTrue(transitions)
        self.assertTrue(all(record["cause"] == "button" and record["button_seq"] in buttons for record in transitions))

    def test_retransmission_uses_same_payload_and_fresh_key_and_nonce(self):
        harness = StagedHarness()
        harness.finish("RETRY")
        completion = next(record for record in reversed(harness.logger.records) if record["event"] == "cycle_complete")
        retry = completion["retry_result"]
        self.assertEqual(retry["result"], "DELIVERED")
        self.assertEqual(retry["raw_response"]["same_payload"], "1")
        self.assertEqual(retry["raw_response"]["fresh_key"], "1")
        self.assertEqual(retry["raw_response"]["fresh_nonce"], "1")
        self.assertEqual(completion["decision"], "RETRY")
        operational = [record["decision"] for record in harness.logger.records if record["event"] == "operational_decision"]
        self.assertEqual(operational, ["RETRY"])

    def test_every_real_stage_logs_start_and_completion(self):
        harness = StagedHarness()
        harness.finish("RETRY")
        started = [record["stage"] for record in harness.logger.records if record["event"] == "stage_started"]
        completed = [record["stage"] for record in harness.logger.records if record["event"] == "stage_completed"]
        self.assertEqual(started, ["PREPARE", "PROTECT", "TRANSMIT", "VERIFY", "RETRY", "END"])
        self.assertEqual(completed, started)

    def test_cryptographically_rejected_packet_cannot_be_selected_for_acceptance(self):
        harness = StagedHarness(incident="TAMPER", guard="NONE")
        controller = harness.reach_response()
        harness.tick()
        self.assertFalse(controller.handle_action("response:ACCEPT", now=harness.now))
        self.assertEqual(controller.state, InvestigationState.SELECT_RESPONSE)
        self.assertFalse(controller.pending_choice)
        self.assertIn("NÃO PODE SER ACEITO", controller.blocked_choice_message)

    def test_no_inactivity_or_summary_timer_changes_the_screen(self):
        harness = StagedHarness()
        harness.assert_press()
        state = harness.controller.state
        harness.controller.update(now=100000.0)
        self.assertEqual(harness.controller.state, state)
        self.assertIsNone(harness.controller.auto_return_remaining())

    def test_incident_sequence_is_deterministic_and_balanced(self):
        first = StagedHarness()
        second = StagedHarness()
        self.assertEqual(first.controller._incident_order, second.controller._incident_order)
        self.assertEqual(set(first.controller._incident_order), {IncidentScenario.CHANNEL_BITFLIP, IncidentScenario.TAMPER, IncidentScenario.RX_MEMORY})

    def test_pending_command_and_animation_rejections_do_not_consume_next_press(self):
        harness = StagedHarness()
        controller = harness.reach_prepare()
        last = controller.last_button_at
        controller.pending = PendingCommand("GAME_PROTECT X", "test", harness.now + 10, {})
        harness.tick()
        self.assertFalse(controller.handle_button(now=harness.now, origin="test-d27"))
        self.assertEqual(controller.last_button_at, last)
        controller.pending = None
        controller.animation_complete = False
        controller.animation_deadline = harness.now + 10
        harness.tick()
        self.assertFalse(controller.handle_button(now=harness.now, origin="test-d27"))
        self.assertEqual(controller.last_button_at, last)
        controller.animation_complete = True
        harness.tick()
        self.assertTrue(controller.handle_button(now=harness.now, origin="test-d27"))

    def test_hardware_requires_capability_authorized_origin_and_fresh_button_uptime(self):
        config = fast_config()
        sent = []
        controller = InvestigationController(config, lambda command, **_: sent.append(command), mode="hardware", now=0)
        controller.handle_serial_event("state", {"connected": True, "status": "USB"}, now=0)
        hello = {
            "command": "HELLO",
            "status": "OK",
            "payload": {"node": "PQC-SAT-WISDOM", "board": "BlackBoard-Wisdom", "proto": "V1", "game": "STAGED_V1", "uptime_ms": "100"},
        }
        controller.handle_serial_event("response", hello, now=0)
        controller.update(now=0.1)
        self.assertFalse(controller.handle_button(now=0.1, origin="keyboard"))
        event = {"name": "BUTTON_PING", "payload": {"button": "1", "uptime_ms": "120", "pot": "2048"}}
        self.assertTrue(controller.handle_serial_event("event", event, now=0.2))
        self.assertEqual(controller.state, InvestigationState.SELECT_MISSION)
        self.assertFalse(controller.handle_serial_event("event", event, now=0.3))

    def test_search_advances_automatically_then_fresh_d27_starts_mission(self):
        logger = MemoryLogger()
        controller = InvestigationController(
            fast_config(),
            lambda *_args, **_kwargs: None,
            mode="hardware",
            logger=logger,
            now=0,
        )
        panel = GamePanel.for_test(controller, startup_splash=True)
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (100, 100)})
        self.assertTrue(panel.handle_event(click))
        self.assertTrue(panel.wisdom_search_active)
        controller.update(now=100000.0)
        self.assertTrue(panel.wisdom_search_active)
        self.assertEqual(controller.state, InvestigationState.ATTRACT)

        stale = {"name": "BUTTON_PING", "payload": {"button": "1", "uptime_ms": "90", "pot": "2048"}}
        panel._handle_serial_input("event", stale, now=100000.05)
        connect_panel_to_wisdom(panel, now=100000.1)
        self.assertFalse(panel.wisdom_search_active)
        self.assertEqual(controller.button_sequence, 0)

        controller.update(now=100000.2)
        event = {"name": "BUTTON_PING", "payload": {"button": "1", "uptime_ms": "120", "pot": "2048"}}
        panel._handle_serial_input("event", event, now=100000.2)
        self.assertEqual(controller.state, InvestigationState.SELECT_MISSION)
        self.assertEqual(controller.button_sequence, 1)
        self.assertNotIn("intro_confirmed", [record["event"] for record in logger.records])

    def test_outdated_hardware_enters_error(self):
        controller = InvestigationController(fast_config(), lambda *_args, **_kwargs: None, mode="hardware", now=0)
        controller.handle_serial_event("state", {"connected": True, "status": "USB"}, now=0)
        controller.handle_serial_event(
            "response",
            {"command": "HELLO", "status": "OK", "payload": {"node": "PQC-SAT-WISDOM", "board": "BlackBoard-Wisdom", "proto": "V1", "uptime_ms": "1"}},
            now=0.1,
        )
        self.assertEqual(controller.state, InvestigationState.ERROR)
        self.assertIn("STAGED_V1", controller.error_message)

    def test_home_abort_and_disconnect_erase_results(self):
        harness = StagedHarness()
        controller = harness.reach_verify()
        self.assertIsNotNone(controller.result)
        controller.abort(reason="operator_home_key", now=harness.now + 1)
        self.assertEqual(controller.state, InvestigationState.ERROR)
        self.assertIsNone(controller.result)
        self.assertFalse(controller.stage_measurements)

    def test_abort_enqueue_failure_still_requests_a_fresh_handshake(self):
        sent = []

        def send(command, **_kwargs):
            sent.append(command)
            if command.startswith("GAME_ABORT"):
                raise RuntimeError("fila de aborto indisponível")

        controller = InvestigationController(fast_config(), send, mode="hardware", now=0)
        controller.connected = True
        controller.game_id = "G000001"
        controller.abort(reason="test", now=1)
        self.assertEqual(sent, ["GAME_ABORT G000001", "HELLO"])
        self.assertIsNotNone(controller.pending)
        self.assertEqual(controller.pending.purpose, "handshake_retry")


class StagedLoggingAndRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def test_session_logger_writes_v2_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = StandSessionLogger(temp_dir, mode="simulated", config=fast_config(), flow="investigation")
            logger.write("choice_selected", kind="mission", value="TELEMETRY")
            path = logger.path
            logger.close()
            rows = load_records([path])
        self.assertTrue(rows)
        self.assertTrue(all(row["schema_version"] == "pqc-sat-stand-log-v2" for row in rows))
        self.assertEqual(rows[0]["protocol"], "STAGED_V1")
        self.assertFalse(rows[0]["public_auto_reset_enabled"])

    def test_transition_validator_accepts_physical_or_screen_confirmation(self):
        rows = [
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "transition", "state": "PREPARE", "cause": "button", "button_seq": 2}
        ]
        self.assertTrue(validate_physical_transition_causes(rows))
        rows.insert(0, {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "button_confirmed", "origin": "physical", "button_seq": 2})
        self.assertFalse(validate_physical_transition_causes(rows))
        rows[0]["origin"] = "screen"
        rows[1]["confirmation_origin"] = "screen"
        self.assertFalse(validate_physical_transition_causes(rows))
        rows[1]["confirmation_origin"] = "physical"
        self.assertTrue(validate_physical_transition_causes(rows))

    def test_v2_pot_gate_does_not_mix_adc_with_derived_bit_position(self):
        rows = [
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "button_confirmed", "origin": "physical", "pot": 2048},
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "fault_selection_confirmed", "bit_position": 144},
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "button_confirmed", "origin": "physical", "pot": 2048},
        ]
        self.assertEqual(count_pot_activity(rows), (2, 0, 1))
        rows.append(
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "button_confirmed", "origin": "physical", "pot": 2050}
        )
        self.assertEqual(count_pot_activity(rows), (3, 0, 2))
        rows.append(
            {"schema_version": "pqc-sat-stand-log-v2", "session_id": "S", "event": "button_confirmed", "origin": "physical", "pot": 3072}
        )
        self.assertEqual(count_pot_activity(rows), (4, 1, 3))
        rows.append(
            {
                "schema_version": "pqc-sat-stand-log-v2",
                "session_id": "S",
                "event": "button_confirmed",
                "origin": "screen",
                "pot": 1024,
                "pot_source": "ANALOG POT",
            }
        )
        self.assertEqual(count_pot_activity(rows), (5, 2, 4))

    def test_click_is_routed_as_selection_without_advancing(self):
        harness = StagedHarness()
        harness.assert_press()
        harness.tick()
        panel = GamePanel.for_test(harness.controller)
        frame = render_game_frame(harness.controller, size=(1366, 768), now=harness.now)
        panel._draw_investigation_presentation(frame, harness.now)
        rect = panel.stand_action_rects["mission:TELEMETRY"]
        self.assertEqual(rect.width, rect.height)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rect.center})
        self.assertTrue(panel.handle_event(event))
        self.assertEqual(harness.controller.state, InvestigationState.SELECT_MISSION)
        self.assertEqual(harness.controller.pending_choice, "TELEMETRY")

    def test_click_on_contextual_control_confirms_and_advances(self):
        harness = StagedHarness()
        harness.assert_press()
        harness.tick()
        panel = GamePanel.for_test(harness.controller)
        from pqc_sat.ui.display import DISPLAY

        DISPLAY.set_size(1366, 768)
        frame = pygame.Surface(DISPLAY.size)
        panel.draw(frame, harness.now)
        choice = panel.stand_action_rects["mission:TELEMETRY"]
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": choice.center}))
        panel.draw(frame, harness.now + 0.1)
        green = panel.stand_action_rects["confirm"]
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": green.center}))
        self.assertEqual(harness.controller.state, InvestigationState.SELECT_PROFILE)

    def test_completed_replay_packet_can_be_dragged_without_changing_game_state(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        prepare_investigation_capture_state(controller, InvestigationState.PROTECT)
        controller.state = InvestigationState.PROTECT
        controller.state_entered_at = 0
        controller.last_clock_at = 2
        controller.animation_complete = True
        panel = GamePanel.for_test(controller)
        frame = pygame.Surface((1366, 768))
        from pqc_sat.ui.display import DISPLAY

        DISPLAY.set_size(1366, 768)
        panel.draw(frame, 2.0)
        self.assertTrue(panel.replay_interaction.review_enabled)
        self.assertTrue(controller.stage_ready_for_confirmation)

        start = panel.replay_interaction.packet_rect.center
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": start})
        move = pygame.event.Event(
            pygame.MOUSEMOTION,
            {"pos": (panel.replay_interaction.track_rect.left, start[1]), "rel": (0, 0), "buttons": (1, 0, 0)},
        )
        up = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            {"button": 1, "pos": (panel.replay_interaction.track_rect.left, start[1])},
        )
        self.assertTrue(panel.handle_event(down))
        self.assertTrue(panel.handle_event(move))
        self.assertTrue(panel.handle_event(up))
        self.assertEqual(panel.replay_interaction.display_progress, 0.0)
        self.assertEqual(controller.state, InvestigationState.PROTECT)
        self.assertTrue(controller.animation_complete)
        self.assertTrue(controller.stage_ready_for_confirmation)

    def test_replay_cannot_be_dragged_before_automatic_animation_finishes(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        prepare_investigation_capture_state(controller, InvestigationState.PROTECT)
        controller.state = InvestigationState.PROTECT
        controller.state_entered_at = 0
        controller.animation_started_at = 0
        controller.animation_deadline = 4
        controller.animation_complete = False
        controller.last_clock_at = 2
        panel = GamePanel.for_test(controller)
        from pqc_sat.ui.display import DISPLAY

        DISPLAY.set_size(1366, 768)
        panel.draw(pygame.Surface((1366, 768)), 2.0)
        self.assertFalse(panel.replay_interaction.review_enabled)
        self.assertFalse(panel.replay_interaction.begin_drag(panel.replay_interaction.packet_rect.center))
        self.assertFalse(panel.replay_interaction.dragging)

    def test_attract_has_no_tutorial_subphase(self):
        controller = InvestigationController(fast_config(), lambda *_args, **_kwargs: None, mode="hardware", now=0)
        controller.connected = True
        controller.handshake_ok = True
        controller.state_entered_at = -1
        panel = GamePanel.for_test(controller)
        from pqc_sat.ui.display import DISPLAY

        DISPLAY.set_size(1366, 768)
        panel.draw(pygame.Surface(DISPLAY.size), 1.0)
        self.assertIn("confirm", panel.stand_action_rects)
        self.assertFalse(controller.handle_action("intro:continue", now=1))
        self.assertTrue(controller.handle_action("confirm", now=1))
        self.assertEqual(controller.state, InvestigationState.SELECT_MISSION)

    def test_persistent_wisdom_search_renders_at_both_resolutions(self):
        controller = InvestigationController(fast_config(), lambda *_args, **_kwargs: None, mode="hardware", now=0)
        panel = GamePanel.for_test(controller, startup_splash=True)
        from pqc_sat.ui.display import DISPLAY

        for size in ((1366, 768), (1920, 1080)):
            with self.subTest(size=size):
                DISPLAY.set_size(*size)
                frame = pygame.Surface(size)
                panel.draw(frame, 5000.0)
                self.assertTrue(panel.wisdom_search_active)
                self.assertGreater(len(set(pygame.image.tobytes(frame, "RGB"))), 3)

    def test_compact_start_button_begins_every_mission_directly(self):
        controller = InvestigationController(fast_config(), lambda *_args, **_kwargs: None, mode="hardware", now=0)
        controller.connected = True
        controller.handshake_ok = True
        controller.state_entered_at = -1
        panel = GamePanel.for_test(controller)
        from pqc_sat.ui.display import DISPLAY

        DISPLAY.set_size(1366, 768)
        frame = pygame.Surface(DISPLAY.size)
        panel.draw(frame, 1.0)
        start = panel.stand_action_rects["confirm"]
        panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": start.center}))
        self.assertEqual(controller.state, InvestigationState.SELECT_MISSION)

        controller.reset_to_attract(reason="test_setup", now=2.0)
        controller.update(now=2.1)
        panel._sync_presentation_state()
        panel.draw(frame, 2.1)
        self.assertIn("confirm", panel.stand_action_rects)

    def test_disconnect_always_searches_and_reconnects_to_clean_narrative(self):
        harness = StagedHarness()
        controller = harness.reach_verify()
        self.assertIsNotNone(controller.result)
        controller.mode = "hardware"
        panel = GamePanel.for_test(controller, startup_splash=True)
        panel.wisdom_search_active = False

        panel._handle_serial_input(
            "state",
            {"connected": False, "status": "USB DESCONECTADA", "port": "/dev/ttyUSB0"},
            now=harness.now + 1,
        )
        self.assertTrue(panel.wisdom_search_active)
        self.assertEqual(controller.state, InvestigationState.ERROR)

        connect_panel_to_wisdom(panel, now=harness.now + 2, uptime_ms=5000)
        panel._sync_presentation_state()
        self.assertFalse(panel.wisdom_search_active)
        self.assertEqual(controller.state, InvestigationState.ATTRACT)
        self.assertIsNone(controller.result)
        self.assertFalse(controller.stage_measurements)

    def test_live_hardware_keyboard_surrogate_is_disabled(self):
        controller = InvestigationController(fast_config(), lambda *_args, **_kwargs: None, mode="hardware", now=0)
        controller.connected = True
        controller.handshake_ok = True
        controller.state_entered_at = -1
        panel = GamePanel.for_test(controller, diagnostic=True)
        down = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE, "unicode": " "})
        panel.handle_event(down)
        self.assertEqual(controller.state, InvestigationState.ATTRACT)

    def test_f12_diagnostic_redacts_the_hidden_incident(self):
        harness = StagedHarness()
        harness.controller.pending = PendingCommand(
            "GAME_BEGIN G1 BASELINE PQC CRC32 RX_MEMORY DEADBEEF",
            "game_begin",
            10,
            {},
        )
        label = GamePanel._stand_diagnostic_pending_label(harness.controller)
        self.assertEqual(label, "GAME_BEGIN G1 [PARÂMETROS OCULTOS]")
        self.assertNotIn("RX_MEMORY", label)

    def test_every_staged_state_renders_at_both_validated_resolutions(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        for state in INVESTIGATION_STATE_ORDER:
            prepare_investigation_capture_state(controller, state)
            controller.state = state
            controller.state_entered_at = 0
            controller.last_clock_at = 2
            with self.subTest(state=state.value):
                for size in ((1366, 768), (1920, 1080)):
                    frame = render_game_frame(controller, size=size, now=2)
                    self.assertEqual(frame.get_size(), size)

    def test_public_hud_uses_portuguese_stage_labels(self):
        for internal in ("SELECT_KEY_MODE", "SELECT_GUARD", "SELECT_RESPONSE", "DEBRIEF"):
            label = GamePanel._stand_state_label(internal)
            self.assertNotEqual(label, internal.replace("_", " "))


if __name__ == "__main__":
    unittest.main()
