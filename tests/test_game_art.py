import unittest
from unittest.mock import patch

import pygame

from pqc_sat.stand.model import GameStage, InvestigationState
from pqc_sat.ui.display import DISPLAY
from pqc_sat.ui.game import GamePanel
from pqc_sat.ui.game_art import (
    GameAct,
    build_didactic_timeline,
    build_mission_review_timeline,
    draw_game_icon,
    game_act_for_state,
)
from pqc_sat.ui.theme import C_ACCENT_CYAN
from tools.capture_stand_evidence import (
    build_completed_investigation_controller,
    prepare_investigation_capture_state,
)
from pqc_sat.stand.settings import DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH


class GameArtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_four_acts_cover_every_public_state(self):
        expected = {
            GameAct.BRIEFING: {"ATTRACT", "SELECT_MISSION"},
            GameAct.LOADOUT: {"SELECT_PROFILE", "SELECT_KEY_MODE", "SELECT_GUARD"},
            GameAct.OPERATION: {"PREPARE", "PROTECT", "TRANSMIT", "VERIFY"},
            GameAct.COMMAND: {"DIAGNOSE", "SELECT_RESPONSE", "RETRY", "DEBRIEF", "ERROR"},
        }
        for act, states in expected.items():
            for state in states:
                with self.subTest(state=state):
                    self.assertIs(game_act_for_state(state), act)
        self.assertEqual(set().union(*expected.values()), {state.value for state in InvestigationState})

    def test_pqc_timeline_uses_real_substage_timings(self):
        raw = {
            "keygen_us": "3100",
            "encap_us": "3700",
            "decap_us": "4900",
            "kdf_us": "120",
            "rng_us": "80",
            "encrypt_us": "390",
        }
        timeline = build_didactic_timeline("PROTECT", raw, key_mode="PQC", guard="CRC32")
        self.assertEqual([cue.key for cue in timeline.cues], ["keygen", "encaps", "decaps", "kdf", "nonce", "aes"])
        self.assertEqual([cue.measured_us for cue in timeline.cues], [3100, 3700, 4900, 120, 80, 390])
        self.assertEqual(timeline.cues[0].start, 0.0)
        self.assertEqual(timeline.cues[-1].end, 1.0)
        self.assertTrue(all(cue.short_label for cue in timeline.cues))
        self.assertTrue(all(cue.explanation for cue in timeline.cues))
        self.assertTrue(all(cue.input_label and cue.output_label for cue in timeline.cues))
        self.assertEqual(timeline.station_progresses[0], 0.0)
        self.assertEqual(timeline.station_progresses[-1], 1.0)

    def test_classic_and_crc_choices_change_the_replay_content(self):
        classic = build_didactic_timeline(
            "PROTECT",
            {"rng_us": "91", "encrypt_us": "411"},
            key_mode="CLASSIC",
            guard="NONE",
        )
        self.assertEqual([cue.key for cue in classic.cues], ["rng", "aes"])
        with_crc = build_didactic_timeline("PREPARE", {}, key_mode="PQC", guard="CRC32")
        without_crc = build_didactic_timeline("PREPARE", {}, key_mode="PQC", guard="NONE")
        self.assertIn("app_crc", [cue.key for cue in with_crc.cues])
        self.assertNotIn("app_crc", [cue.key for cue in without_crc.cues])

    def test_timeline_rejects_missing_validated_measurement(self):
        with self.assertRaisesRegex(ValueError, "resposta GAME_\\*"):
            build_didactic_timeline("PROTECT", None, key_mode="PQC", guard="CRC32")

    def test_every_procedural_icon_draws_without_external_assets(self):
        icons = (
            "telemetry",
            "safe_command",
            "config",
            "cpu_fast",
            "cpu_limited",
            "classic_key",
            "pqc_keygen",
            "capsule",
            "pqc_decaps",
            "kdf",
            "crc32",
            "no_crc",
            "payload",
            "aes_gcm",
            "packet",
            "nonce",
            "channel",
            "tamper",
            "memory",
            "accept",
            "retry",
            "safe",
            "bit",
            "satellite",
            "ground",
            "touch",
            "button",
            "pot",
            "drag",
        )
        for icon in icons:
            with self.subTest(icon=icon):
                surface = pygame.Surface((180, 120))
                surface.fill((1, 1, 1))
                draw_game_icon(
                    surface,
                    icon,
                    pygame.Rect(5, 5, 170, 110),
                    1.25,
                    color=C_ACCENT_CYAN,
                    active=True,
                    progress=0.6,
                )
                self.assertGreater(len(set(pygame.image.tobytes(surface, "RGB"))), 3)

    def test_stage_replay_is_not_built_before_a_validated_response(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        prepare_investigation_capture_state(controller, InvestigationState.PROTECT)
        controller.state = InvestigationState.PROTECT
        measurement = controller.stage_measurements.pop(GameStage.PROTECT)
        controller.last_clock_at = 0.4
        DISPLAY.set_size(1366, 768)
        surface = pygame.Surface(DISPLAY.size)
        panel = GamePanel.for_test(controller)
        with patch("pqc_sat.ui.panel.investigation_view.build_didactic_timeline") as builder:
            panel.draw(surface, 1.0)
            builder.assert_not_called()
        controller.stage_measurements[GameStage.PROTECT] = measurement
        controller.animation_started_at = 0.0
        controller.animation_deadline = 4.0
        controller.animation_complete = False
        with patch(
            "pqc_sat.ui.panel.investigation_view.build_didactic_timeline",
            wraps=build_didactic_timeline,
        ) as builder:
            panel.draw(surface, 1.0)
            builder.assert_called_once()

    def test_measured_replay_changes_with_checkpoint_progress(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        prepare_investigation_capture_state(controller, InvestigationState.PROTECT)
        controller.state = InvestigationState.PROTECT
        controller.animation_started_at = 0.0
        controller.animation_deadline = 4.0
        controller.animation_complete = False
        DISPLAY.set_size(1366, 768)
        panel = GamePanel.for_test(controller)

        controller.last_clock_at = 0.4
        first = pygame.Surface(DISPLAY.size)
        first.fill((0, 0, 0))
        panel.draw(first, 1.0)

        controller.last_clock_at = 3.4
        second = pygame.Surface(DISPLAY.size)
        second.fill((0, 0, 0))
        panel.draw(second, 1.0)
        self.assertNotEqual(pygame.image.tobytes(first, "RGB"), pygame.image.tobytes(second, "RGB"))

    def test_debrief_review_uses_only_completed_real_stage_objects(self):
        controller = build_completed_investigation_controller(DEFAULT_CONFIG_PATH, DEFAULT_FIXTURE_PATH)
        timeline = build_mission_review_timeline(
            controller.stage_measurements,
            controller.result,
            controller.retry_result,
        )
        self.assertEqual(
            [cue.key for cue in timeline.cues],
            ["review_prepare", "review_protect", "review_transmit", "review_verify", "review_retry"],
        )
        self.assertTrue(all(cue.measured_us and cue.measured_us > 0 for cue in timeline.cues))
        with self.assertRaisesRegex(ValueError, "todas as medições"):
            build_mission_review_timeline({}, controller.result)


if __name__ == "__main__":
    unittest.main()
