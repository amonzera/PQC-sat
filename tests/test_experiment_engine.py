import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json

import dashboard
import pygame
from tools.serial_protocol import parse_frame


class FakeSerialClient:
    def __init__(self):
        self.sent = []
        self.last_timeout = None
        self.events = []
        self.responses = {
            "SENSOR_READ TEMP_HUM": {"temp_c_x100": "2450", "hum_x100": "5530"},
            "SENSOR_READ ACCEL": {"x_mg": "12", "y_mg": "-34", "z_mg": "1001"},
            "SENSOR_READ APDS": {"clear": "321", "prox": "7"},
            "ANALOG POT": {"pot": "2048"},
            "DIGITAL BUTTON": {"button": "0"},
        }

    def start(self):
        pass

    def stop(self):
        pass

    def send(self, command_line, *, timeout=None):
        self.sent.append(command_line)
        self.last_timeout = timeout

    def request(self, command_line, *, timeout=1.25, emit_event=False):
        payload = self.responses.get(command_line)
        if payload is None:
            return {"command": command_line.upper(), "status": "ERROR", "payload": {}, "raw_payload": ""}
        return {"command": command_line.upper(), "status": "OK", "payload": dict(payload), "raw_payload": ""}

    def poll(self):
        events = list(self.events)
        self.events.clear()
        return events


class ExperimentEngineTests(unittest.TestCase):
    def test_import_does_not_initialize_fullscreen_display(self):
        self.assertIsNone(dashboard.screen)

    def test_parse_args_accepts_no_splash_for_headless_runs(self):
        old_argv = sys.argv
        try:
            sys.argv = ["dashboard.py", "--simulated", "--no-splash"]
            args = dashboard.parse_args()
        finally:
            sys.argv = old_argv

        self.assertTrue(args.simulated)
        self.assertTrue(args.no_splash)

    def test_serial_client_publishes_unsolicited_button_ping_event(self):
        client = dashboard.DashboardSerialClient()

        class FakeBridge:
            @staticmethod
            def poll_events():
                return [parse_frame("V1|0|EVENT|BUTTON_PING|button=1|uptime_ms=42")]

        client._publish_protocol_events(FakeBridge())

        self.assertEqual(
            client.poll(),
            [
                (
                    "event",
                    {
                        "name": "BUTTON_PING",
                        "payload": {"button": "1", "uptime_ms": "42"},
                        "raw_payload": "BUTTON_PING button=1 uptime_ms=42",
                    },
                )
            ],
        )

    def test_same_seed_repeats_fault_sequence(self):
        first = dashboard.ExperimentEngine(seed=123)
        second = dashboard.ExperimentEngine(seed=123)

        first_events = [first.run_fault() for _ in range(4)]
        second_events = [second.run_fault() for _ in range(4)]

        self.assertEqual(
            [(event.byte_index, event.bit_mask, event.after_hex) for event in first_events],
            [(event.byte_index, event.bit_mask, event.after_hex) for event in second_events],
        )

    def test_none_guard_classifies_changed_payload_as_silent(self):
        engine = dashboard.ExperimentEngine(seed=1)
        event = engine.run_fault(guard="NONE", spec=dashboard.FaultSpec(byte_index=0, bit_mask=0x01))

        self.assertEqual(event.result, "SILENT")
        self.assertNotEqual(event.before_hex, event.after_hex)
        self.assertEqual(event.guard, "NONE")
        self.assertEqual(event.guard_prepare_us, 0)
        self.assertEqual(event.guard_verify_us, 0)
        self.assertEqual(event.guard_overhead_us, 0)

    def test_crc32_detects_every_single_bit_in_payload(self):
        payload = b"PQC"
        engine = dashboard.ExperimentEngine(seed=1, payload=payload)

        for byte_index in range(len(payload)):
            for bit in range(8):
                event = engine.run_fault(
                    guard="CRC32",
                    spec=dashboard.FaultSpec(byte_index=byte_index, bit_mask=1 << bit),
                )
                self.assertEqual(event.result, "DETECTED_GUARD")
                self.assertGreaterEqual(event.guard_prepare_us, 1)
                self.assertGreaterEqual(event.guard_verify_us, 1)
                self.assertEqual(
                    event.guard_overhead_us,
                    event.guard_prepare_us + event.guard_verify_us,
                )

    def test_invalid_fault_spec_is_rejected(self):
        engine = dashboard.ExperimentEngine(seed=1)

        with self.assertRaises(ValueError):
            engine.run_fault(spec=dashboard.FaultSpec(byte_index=999, bit_mask=0x01))
        with self.assertRaises(ValueError):
            engine.run_fault(spec=dashboard.FaultSpec(byte_index=0, bit_mask=0x03))

    def test_reset_restarts_trial_and_fault_sequence(self):
        engine = dashboard.ExperimentEngine(seed=99)
        first = engine.run_fault()
        engine.run_fault()
        engine.reset()
        repeated = engine.run_fault()

        self.assertEqual(repeated.trial_id, 1)
        self.assertEqual(first.byte_index, repeated.byte_index)
        self.assertEqual(first.bit_mask, repeated.bit_mask)

    def test_live_payload_text_fits_firmware_buffer_and_hex_roundtrips(self):
        readings = {
            "temp_c_x100": "2450",
            "hum_x100": "5530",
            "x_mg": "12",
            "y_mg": "-34",
            "z_mg": "1001",
            "clear": "321",
            "pot": "2048",
            "button": "0",
        }

        payload_text = dashboard.live_payload_text_from_readings(42, readings)
        payload_hex = dashboard.payload_hex_from_text(payload_text)

        self.assertLessEqual(len(payload_text.encode("ascii")), dashboard.LIVE_PAYLOAD_MAX_BYTES)
        self.assertIn("PQC-SAT|S=42", payload_text)
        self.assertIn("|P=2048", payload_text)
        self.assertEqual(bytes.fromhex(payload_hex).decode("ascii"), payload_text)

    def test_fault_spec_from_pot_maps_full_range_to_payload_bits(self):
        low = dashboard.fault_spec_from_pot("0", 4)
        high = dashboard.fault_spec_from_pot("4095", 4)

        self.assertEqual((low.byte_index, low.bit_mask), (0, 0x01))
        self.assertEqual((high.byte_index, high.bit_mask), (3, 0x80))


class DashboardCommandTests(unittest.TestCase):
    def test_fault_commands_update_metrics_from_events(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("INJECT_FAULT")
        self.assertEqual(panel.fault_injections, 1)
        self.assertEqual(panel.silent_failures, 1)
        self.assertEqual(panel.detected_errors, 0)
        self.assertEqual(panel.last_fault_event.result, "SILENT")
        self.assertTrue(panel.fault_overlay_visible)
        self.assertEqual(panel.fault_overlay["result"], "SILENT")

        panel._execute_command("CRC_CHECK")
        self.assertEqual(panel.fault_injections, 2)
        self.assertEqual(panel.silent_failures, 1)
        self.assertEqual(panel.detected_errors, 1)
        self.assertEqual(panel.last_fault_event.result, "DETECTED_GUARD")
        self.assertEqual(panel.fault_overlay["guard"], "CRC32")
        self.assertEqual(panel.fault_overlay["result"], "DETECTED_GUARD")

    def test_fault_visualization_animates_can_scrub_and_requires_confirmation(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("BIT_FLIP 0 0x01")

        self.assertTrue(panel.fault_overlay_visible)
        self.assertIsNotNone(panel.fault_flow_animation)
        self.assertEqual(panel.fault_flow_animation["duration"], dashboard.FAULT_FLOW_ANIMATION_SECONDS)
        self.assertFalse(panel.fault_flow_animation["awaiting_confirm"])
        self.assertNotIn("paused", panel.fault_flow_animation)
        self.assertEqual(
            [step["label"] for step in panel.fault_flow_animation["steps"]],
            ["PAYLOAD", "BIT-FLIP", "SEM CRC", "ENTREGA", "RESULTADO"],
        )
        self.assertIn("Não existe checksum", panel.fault_flow_animation["steps"][2]["explain"])
        self.assertEqual(panel.fault_overlay["before_byte"], "0x50")
        self.assertEqual(panel.fault_overlay["after_byte"], "0x51")

        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            earth = dashboard.Earth()
            satellite = dashboard.Satellite(earth)
            panel.draw(surface, 0.5, satellite)
            self.assertIsNotNone(panel.fault_overlay_rect)
            self.assertIsNotNone(panel.fault_flow_control_rect)
            self.assertIsNotNone(panel.fault_flow_scrub_rect)

            scrub_rect = panel.fault_flow_scrub_rect
            scrub_start = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": (scrub_rect.x, scrub_rect.centery)},
            )
            self.assertTrue(panel._handle_fault_overlay_event(scrub_start))
            self.assertAlmostEqual(panel.fault_flow_animation["age"], 0.0)
            scrub_end = pygame.event.Event(
                pygame.MOUSEMOTION,
                {"pos": (scrub_rect.right, scrub_rect.centery)},
            )
            self.assertTrue(panel._handle_fault_overlay_event(scrub_end))
            self.assertEqual(panel.fault_flow_animation["age"], dashboard.FAULT_FLOW_ANIMATION_SECONDS)
            self.assertTrue(panel.fault_flow_animation["awaiting_confirm"])
            scrub_release = pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                {"button": 1, "pos": (scrub_rect.right, scrub_rect.centery)},
            )
            self.assertTrue(panel._handle_fault_overlay_event(scrub_release))
            self.assertTrue(panel.fault_flow_animation.get("paused"))

            # Like the message popup, dragging back pauses the flow at the
            # selected point instead of letting autoplay move the handle.
            scrub_middle = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": (scrub_rect.centerx, scrub_rect.centery)},
            )
            self.assertTrue(panel._handle_fault_overlay_event(scrub_middle))
            paused_age = panel.fault_flow_animation["age"]
            self.assertFalse(panel.fault_flow_animation["awaiting_confirm"])
            panel.update(0.5)
            self.assertEqual(panel.fault_flow_animation["age"], paused_age)
            self.assertTrue(
                panel._handle_fault_overlay_event(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONUP,
                        {"button": 1, "pos": (scrub_rect.centerx, scrub_rect.centery)},
                    )
                )
            )

            panel.fault_flow_animation["awaiting_confirm"] = False
            panel.fault_flow_animation["age"] = 0.0
            panel.fault_flow_animation["paused"] = False
            control_rect = panel.fault_flow_control_rect
            click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": control_rect.center})
            self.assertTrue(panel._handle_fault_overlay_event(click))
            self.assertIsNotNone(panel.fault_flow_animation)
            panel.update(2.0)
            self.assertGreater(panel.fault_flow_animation["age"], 0.0)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

        panel.update(dashboard.FAULT_FLOW_ANIMATION_SECONDS + 0.1)
        self.assertIsNotNone(panel.fault_flow_animation)
        self.assertTrue(panel.fault_flow_animation["awaiting_confirm"])
        self.assertTrue(panel.fault_overlay_visible)

        control_rect = panel.fault_flow_control_rect
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": control_rect.center})
        self.assertTrue(panel._handle_fault_overlay_event(click))
        self.assertIsNone(panel.fault_flow_animation)
        self.assertTrue(panel.fault_overlay_visible)

    def test_crc_fault_flow_shows_checksum_verification(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("CHECKSUM ON")
        panel._execute_command("BIT_FLIP 0 0x01")

        self.assertTrue(panel.fault_overlay_visible)
        self.assertEqual(panel.fault_overlay["result"], "DETECTED_GUARD")
        self.assertEqual(
            [step["label"] for step in panel.fault_flow_animation["steps"]],
            ["PAYLOAD", "BIT-FLIP", "CRC32", "VERIFICA", "RESULTADO"],
        )
        self.assertIn("CRC32 salvo", panel.fault_flow_animation["steps"][2]["explain"])
        self.assertIn("recalculamos o CRC", panel.fault_flow_animation["steps"][3]["explain"])

    def test_manual_bit_flip_uses_given_position_and_mask(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("BIT_FLIP 0 0x01")

        self.assertEqual(panel.last_fault_event.byte_index, 0)
        self.assertEqual(panel.last_fault_event.bit_mask, 0x01)
        self.assertEqual(panel.last_fault_event.result, "SILENT")

    def test_checksum_toggle_controls_manual_fault_guard(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("CHECKSUM ON")
        panel._execute_command("INJECT_FAULT")

        self.assertTrue(panel.checksum_enabled)
        self.assertEqual(panel.guard_mode, "CRC32")
        self.assertEqual(panel.last_fault_event.guard, "CRC32")
        self.assertEqual(panel.last_fault_event.result, "DETECTED_GUARD")

        panel._execute_command("CHECKSUM OFF")
        panel._execute_command("BIT_FLIP 0 0x01")

        self.assertFalse(panel.checksum_enabled)
        self.assertEqual(panel.guard_mode, "NONE")
        self.assertEqual(panel.last_fault_event.guard, "NONE")
        self.assertEqual(panel.last_fault_event.result, "SILENT")

    def test_guard_command_sets_exportable_checksum_without_events(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("GUARD CRC32")
        data = panel._build_export_document()

        self.assertEqual(panel.command_history[-1]["status"], "CRC32 ON")
        self.assertEqual(data["config"]["checksum"], "CRC32")

    def test_documented_dashboard_local_commands_are_routed(self):
        panel = dashboard.DashboardPanel()
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: Path("session.json")

        panel._execute_command("EXPORT_JSON")
        self.assertEqual(panel.command_history[-1]["status"], "JSON SALVO")
        self.assertEqual(panel.last_export_path, Path("session.json"))

        panel._execute_command("SAVE_SESSION")
        self.assertEqual(panel.command_history[-1]["status"], "JSON SALVO")

        panel._execute_command("DEMO 2")
        self.assertEqual(panel.command_history[-1]["status"], "DEMO START")
        self.assertEqual(panel.demo_state, "RUNNING_A")

        panel._execute_command("DEMO_PAUSE")
        self.assertEqual(panel.command_history[-1]["status"], "DEMO PAUSED")
        self.assertEqual(panel.demo_state, "PAUSED")

    def test_invalid_manual_bit_flip_does_not_create_event(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("BIT_FLIP 999 0x01")

        self.assertEqual(panel.fault_injections, 0)
        self.assertEqual(panel.command_history[-1]["status"], "INVALID_INPUT")

    def test_event_summary_ignores_duplicate_event_identity(self):
        engine = dashboard.ExperimentEngine(seed=3)
        event = engine.run_fault(guard="NONE")

        summary = dashboard.event_summary([event, event])

        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["silent"], 1)

    def test_export_session_writes_versioned_json_with_events_and_hardware(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("INJECT_FAULT")
        panel._execute_command("CRC_CHECK")
        panel._record_hardware_sample(
            "STATUS",
            {
                "uptime_ms": "1000",
                "profile": "BASELINE",
                "cpu_mhz": "240",
                "heap": "233556",
                "min_heap": "230000",
                "flash": "4194304",
                "radio": "off",
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            first = panel.export_session(log_dir=tmp)
            second = panel.export_session(log_dir=tmp)

            self.assertNotEqual(first, second)
            data = json.loads(first.read_text(encoding="utf-8"))

        self.assertEqual(data["schema_version"], dashboard.RUN_SCHEMA_VERSION)
        self.assertEqual(data["config"]["checksum"], "MIXED")
        self.assertEqual(data["summary"]["events"], 2)
        self.assertEqual(data["summary"]["silent"], 1)
        self.assertEqual(data["summary"]["detected_guard"], 1)
        self.assertEqual(len(data["events"]), 2)
        self.assertEqual(data["events"][0]["scenario"], "A_NONE")
        self.assertEqual(data["events"][1]["scenario"], "B_CRC32")
        self.assertEqual(data["events"][0]["guard_overhead_us"], 0)
        self.assertGreaterEqual(data["events"][1]["guard_prepare_us"], 1)
        self.assertGreaterEqual(data["events"][1]["guard_verify_us"], 1)
        self.assertEqual(len(data["hardware_samples"]), 1)
        self.assertEqual(data["hardware_samples"][0]["energy_proxy"]["kind"], "relative_cpu_time")
        self.assertIn("host", data["metrics"])
        self.assertIn("rss_bytes", data["metrics"]["host"])

    def test_board_export_info_accumulates_identity_across_responses(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True
        panel._apply_hardware_response(
            "HELLO",
            {"node": "PQC-SAT-WISDOM", "board": "BlackBoard-Wisdom", "chip": "ESP32-D0WD"},
        )
        panel._apply_hardware_response("TELEMETRY", {"uptime_ms": "1000", "heap": "233556"})

        data = panel._build_export_document()

        self.assertTrue(data["board"]["connected"])
        self.assertEqual(data["board"]["node"], "PQC-SAT-WISDOM")
        self.assertEqual(data["board"]["board"], "BlackBoard-Wisdom")
        self.assertEqual(data["board"]["chip"], "ESP32-D0WD")

    def test_reset_session_auto_saves_dirty_data_before_clearing(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("INJECT_FAULT")
        saved_path = Path("dummy.json")
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: saved_path

        panel._execute_command("RESET_SESSION")

        self.assertEqual(len(panel.experiment_events), 0)
        self.assertFalse(panel.session_dirty)
        self.assertEqual(panel.last_export_path, saved_path)

    def test_reset_session_auto_saves_hardware_only_samples(self):
        panel = dashboard.DashboardPanel()
        panel._record_hardware_sample("STATUS", {"uptime_ms": "1000", "heap": "233556"})
        saved_path = Path("hardware-only.json")
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: saved_path

        panel._execute_command("RESET_SESSION")

        self.assertEqual(panel.hardware_samples, [])
        self.assertFalse(panel.session_dirty)
        self.assertEqual(panel.last_export_path, saved_path)

    def test_close_auto_saves_dirty_session(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("INJECT_FAULT")
        saved_path = Path("close-auto.json")
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: saved_path

        panel.close()

        self.assertFalse(panel.session_dirty)
        self.assertEqual(panel.last_export_path, saved_path)

    def test_pqc_status_queries_board_when_serial_is_online(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._execute_command("PQC_STATUS")

        self.assertEqual(fake.sent[-1], "PQC_INFO")
        self.assertEqual(panel.command_history[-1]["cmd"], "PQC_INFO")
        self.assertEqual(panel.command_history[-1]["status"], "QUEUED")

    def test_advanced_firmware_command_from_dashboard_terminal_is_queued(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._execute_command("PQC_KAT")

        self.assertEqual(fake.sent[-1], "PQC_KAT")
        self.assertEqual(panel.command_history[-1]["cmd"], "PQC_KAT")
        self.assertEqual(panel.command_history[-1]["status"], "QUEUED")

    def test_help_opens_terminal_for_advanced_commands(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("HELP")

        # HELP abre o terminal textual; os comandos avançados continuam
        # digitáveis ali (a lista completa vive no console serial e em
        # hardware_command_reference.md).
        self.assertTrue(panel.help_visible)
        self.assertTrue(panel.terminal_visible)
        self.assertTrue(panel.input_active)
        self.assertIn("PQC_INFO", dashboard.FIRMWARE_COMMAND_NAMES)
        self.assertIn("I2C_SCAN", dashboard.FIRMWARE_COMMAND_NAMES)

    def test_terminal_toggle_button_removed_but_command_still_works(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            earth = dashboard.Earth()
            satellite = dashboard.Satellite(earth)
            panel = dashboard.DashboardPanel()

            panel._draw_left_panel(surface, 0.5, satellite)
            self.assertIsNone(panel.terminal_toggle_rect)
            self.assertFalse(panel.terminal_visible)

            panel._execute_command("TOGGLE_TERMINAL")
            self.assertTrue(panel.terminal_visible)
            self.assertTrue(panel.input_active)

            panel.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_h, "unicode": "H"}))
            self.assertEqual(panel.input_text, "H")

            panel._execute_command("TOGGLE_TERMINAL")
            self.assertFalse(panel.terminal_visible)
            self.assertFalse(panel.input_active)
            self.assertEqual(panel.input_text, "")
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_metric_tiles_render_core_presentation_metrics(self):
        panel = dashboard.DashboardPanel()
        panel._apply_hardware_response(
            "STATUS",
            {
                "profile": "OBC-1U-LIMITED",
                "cpu_mhz": "80",
                "heap": "202444",
                "min_heap": "198456",
                "flash": "4194304",
                "elapsed_us": "15214",
                "radio": "off",
            },
        )

        tiles = {label: (value, detail) for label, value, detail, _color in panel._metric_tiles()}

        self.assertTrue(tiles["CPU"][0].startswith("80 MHz "))
        self.assertIn("%", tiles["CPU"][0])
        self.assertIn("KB /", tiles["RAM"][0])
        self.assertIn("livre", tiles["RAM"][1])
        self.assertNotIn("PQC", tiles)
        self.assertNotIn("CLÁSSICA", tiles)
        self.assertNotIn("PQC+CRC", tiles)

    def test_presentation_buttons_focus_live_mission_scenarios(self):
        commands = [command for _label, command in dashboard.COMMAND_BUTTONS]

        self.assertEqual(
            commands,
            [
                "SET_PRESET_CLASSIC",
                "SET_PRESET_PQC",
                "SET_PRESET_PQC_CRC32",
                "SEND_MESSAGE",
                "INJECT_FAULT",
            ],
        )
        self.assertEqual([section for section, _buttons in dashboard.COMMAND_BUTTON_GROUPS], ["CONFIGURAÇÃO", "ENVIO"])
        self.assertIn("SEND_MESSAGE", commands)
        self.assertIn("SET_PRESET_CLASSIC", commands)
        self.assertIn("SET_PRESET_PQC", commands)
        self.assertIn("SET_PRESET_PQC_CRC32", commands)
        self.assertIn("INJECT_FAULT", commands)
        self.assertNotIn("TOGGLE_CHECKSUM", commands)
        self.assertNotIn("DEMO", commands)
        self.assertNotIn("DEMO_PAUSE", commands)
        self.assertNotIn("EXPORT_JSON", commands)
        self.assertNotIn("MISSION CLASSIC", commands)
        self.assertNotIn("MISSION PQC", commands)
        self.assertNotIn("MISSION PQC_CRC32", commands)
        self.assertNotIn("TELEMETRY", commands)
        self.assertNotIn("PING", commands)
        self.assertNotIn("STRESS", commands)

    def test_presentation_buttons_are_grouped_by_configuration_and_send_action(self):
        panel = dashboard.DashboardPanel()
        surface = pygame.Surface((600, 400), pygame.SRCALPHA)
        width = 439

        bottom = panel._draw_command_buttons(surface, 20, 20, width, 0.5)
        rects = {command: rect for rect, command in panel.command_button_rects}

        config_commands = ("SET_PRESET_CLASSIC", "SET_PRESET_PQC", "SET_PRESET_PQC_CRC32")
        self.assertEqual({rects[command].y for command in config_commands}, {rects["SET_PRESET_CLASSIC"].y})
        self.assertEqual(rects["SEND_MESSAGE"].y, rects["INJECT_FAULT"].y)
        self.assertGreater(rects["SEND_MESSAGE"].y, rects["SET_PRESET_CLASSIC"].y)
        self.assertEqual(bottom, 20 + panel._command_buttons_height(width))
        self.assertLessEqual(max(rect.bottom for rect in rects.values()), bottom)

    def test_live_payload_toggle_is_the_bottom_status_text(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            panel = dashboard.DashboardPanel()

            panel._draw_right_panel(surface, 0.5)
            self.assertIsNone(panel.live_payload_toggle_rect)

            panel._draw_bottom_bar(surface, 0.5)
            toggle_rect = panel.live_payload_toggle_rect
            self.assertIsNotNone(toggle_rect)
            self.assertGreaterEqual(toggle_rect.top, dashboard.HEIGHT - 32)
            self.assertLessEqual(toggle_rect.bottom, dashboard.HEIGHT)

            previous = panel.live_payload_enabled
            click = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": toggle_rect.center},
            )
            panel.handle_event(click)
            self.assertNotEqual(panel.live_payload_enabled, previous)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_stress_button_requires_second_click_and_uses_long_timeout(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._handle_stress_button_click()
        self.assertNotIn(dashboard.STRESS_COMMAND, fake.sent)
        self.assertEqual(panel.stress_state, "ARMED")
        self.assertEqual(panel.stress_status, "CONFIRME")

        panel._handle_stress_button_click()
        self.assertEqual(fake.sent[-1], dashboard.STRESS_COMMAND)
        self.assertEqual(fake.last_timeout, dashboard.STRESS_SERIAL_TIMEOUT_SECONDS)
        self.assertEqual(panel.stress_state, "RUNNING")
        self.assertNotIn("STRESS", [command for _label, command in dashboard.COMMAND_BUTTONS])

    def test_stress_button_remains_armed_until_second_click(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._handle_stress_button_click()
        panel.update(60.0)

        self.assertEqual(panel.stress_state, "ARMED")
        self.assertNotIn(dashboard.STRESS_COMMAND, fake.sent)

        panel._handle_stress_button_click()

        self.assertEqual(fake.sent[-1], dashboard.STRESS_COMMAND)
        self.assertEqual(panel.stress_state, "RUNNING")

    def test_results_overlay_stress_button_click_path_arms_and_runs(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        panel.results_overlay_visible = True
        surface = pygame.Surface((dashboard.WIDTH, dashboard.HEIGHT), pygame.SRCALPHA)
        panel._draw_results_overlay(surface, 0.5)
        click = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": panel.results_stress_btn_rect.center},
        )

        self.assertTrue(panel.handle_event(click))
        self.assertEqual(panel.stress_state, "ARMED")
        self.assertNotIn(dashboard.STRESS_COMMAND, fake.sent)

        self.assertTrue(panel.handle_event(click))
        self.assertEqual(fake.sent[-1], dashboard.STRESS_COMMAND)
        self.assertEqual(panel.stress_state, "RUNNING")

    def test_stress_command_from_terminal_requires_exact_confirmation(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._execute_command("STRESS PQC_LOOP 500")
        self.assertNotIn(dashboard.STRESS_COMMAND, fake.sent)
        self.assertEqual(panel.command_history[-1]["status"], "USE STRESS PQC_LOOP 500 CONFIRM")

        panel._execute_command(dashboard.STRESS_COMMAND)
        self.assertEqual(fake.sent[-1], dashboard.STRESS_COMMAND)
        self.assertEqual(fake.last_timeout, dashboard.STRESS_SERIAL_TIMEOUT_SECONDS)

    def test_stress_overlay_reports_didactic_timeout_without_cancelling(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._execute_command(dashboard.STRESS_COMMAND)
        panel.update(dashboard.STRESS_DIDACTIC_TIMEOUT_SECONDS + 0.1)

        self.assertEqual(panel.stress_state, "RUNNING")
        self.assertEqual(panel.stress_status, "TIMEOUT DIDÁTICO")
        self.assertEqual(fake.sent[-1], dashboard.STRESS_COMMAND)

    def test_stress_response_exports_structured_metrics(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True

        panel._apply_hardware_response(
            dashboard.STRESS_COMMAND,
            {
                "op": "pqc_stress",
                "mode": "PQC_LOOP",
                "n": "500",
                "ok": "500",
                "key_match": "1",
                "keygen_avg_us": "3301",
                "encap_avg_us": "3864",
                "decap_avg_us": "4988",
                "elapsed_us": "6100000",
                "heap": "201512",
                "min_heap": "197624",
                "profile": "BASELINE",
                "cpu_mhz": "240",
            },
        )

        self.assertEqual(panel.stress_state, "COMPLETE")
        self.assertEqual(panel.stress_status, "STRESS OK")
        sample = panel.hardware_samples[-1]
        self.assertEqual(sample["source_command"], "STRESS")
        self.assertEqual(sample["pqc"]["op"], "pqc_stress")
        self.assertEqual(sample["pqc"]["mode"], "PQC_LOOP")
        self.assertEqual(sample["pqc"]["n"], 500)
        self.assertEqual(sample["pqc"]["ok"], 500)

    def test_dashboard_toggle_classic_and_pqc_switches_exclusively(self):
        panel = dashboard.DashboardPanel()
        
        # Initial state should be: PQC active, classic inactive
        self.assertTrue(panel.pqc_enabled)
        self.assertFalse(panel.classic_enabled)

        # Toggle classic ON should disable PQC
        panel._execute_command("TOGGLE_CLASSIC")
        self.assertTrue(panel.classic_enabled)
        self.assertFalse(panel.pqc_enabled)

        # Toggle classic ON again (which means trying to turn it off) should switch to PQC
        panel._execute_command("TOGGLE_CLASSIC")
        self.assertFalse(panel.classic_enabled)
        self.assertTrue(panel.pqc_enabled)

        # Toggle PQC OFF should switch to Classic
        panel._execute_command("TOGGLE_PQC")
        self.assertTrue(panel.classic_enabled)
        self.assertFalse(panel.pqc_enabled)

    def test_mlkem_indicator_follows_selected_preset(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("SET_PRESET_CLASSIC")
        label, color = panel._pqc_indicator()
        self.assertEqual(label, "INATIVO")
        self.assertEqual(color, dashboard.C_ACCENT_ORANGE)

        panel._execute_command("SET_PRESET_PQC")
        label, color = panel._pqc_indicator()
        self.assertIn("ML-KEM-512", label)
        self.assertEqual(color, dashboard.C_ACCENT_PURPLE)

        panel._execute_command("SET_PRESET_PQC_CRC32")
        label, color = panel._pqc_indicator()
        self.assertIn("ML-KEM-512", label)
        self.assertEqual(color, dashboard.C_ACCENT_PURPLE)

    def test_dashboard_send_message_routes_to_correct_mission(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        # Case 1: PQC preset -> MISSION PQC
        panel._execute_command("SET_PRESET_PQC")
        panel._execute_command("SEND_MESSAGE")
        self.assertTrue(any(command.startswith("MISSION PQC ") for command in fake.sent))

        # Case 2: PQC+CRC preset -> MISSION PQC_CRC32
        fake.sent.clear()
        panel._execute_command("SET_PRESET_PQC_CRC32")
        panel._execute_command("SEND_MESSAGE")
        self.assertTrue(any(command.startswith("MISSION PQC_CRC32 ") for command in fake.sent))

        # Case 3: Classic preset -> MISSION CLASSIC
        fake.sent.clear()
        panel._execute_command("SET_PRESET_CLASSIC")
        panel._execute_command("SEND_MESSAGE")
        self.assertTrue(any(command.startswith("MISSION CLASSIC ") for command in fake.sent))
        self.assertEqual(panel.last_live_payload["readings"]["pot"], "2048")
        self.assertIn("|P=2048", panel.last_live_payload["payload_text"])

    def test_live_mission_context_is_attached_to_overlay_and_export(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        fake.sent.clear()

        panel._execute_command("MISSION PQC_CRC32")
        mission_command = next(command for command in fake.sent if command.startswith("MISSION PQC_CRC32 "))
        payload_len = len(bytes.fromhex(mission_command.split()[2]))
        panel._apply_hardware_response(
            mission_command,
            {
                "scenario": "PQC_CRC32",
                "result": "DELIVERED",
                "crypto": "ML-KEM-512",
                "cipher": "AES-128-GCM",
                "checksum": "CRC32",
                "confirmation": "AES-128-GCM",
                "elapsed_us": "15000",
                "payload_len": str(payload_len),
                "bytes_payload": str(payload_len),
                "bytes_ciphertext": str(payload_len + 4),
                "bytes_mlkem": "768",
                "bytes_nonce": "12",
                "bytes_gcm_tag": "16",
                "bytes_crypto": "796",
                "bytes_checksum": "4",
                "bytes_total": str(payload_len + 800),
                "key_match": "1",
                "tag_match": "1",
                "aead_match": "1",
                "crc_match": "1",
            },
        )

        mission = panel.mission_overlays["PQC_CRC32"]
        self.assertEqual(mission["payload_mode"], "LIVE")
        self.assertIn("|P=2048", mission["payload_text"])
        self.assertEqual(mission["sensor_pot"], "2048")
        sample = panel.hardware_samples[-1]["mission"]
        self.assertEqual(sample["payload_mode"], "LIVE")
        self.assertEqual(sample["sensor_pot"], 2048)

    def test_live_payload_collection_marks_missing_sensor_as_partial(self):
        fake = FakeSerialClient()
        fake.responses.pop("SENSOR_READ APDS")
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        snapshot = panel._collect_live_payload_snapshot()

        self.assertEqual(snapshot["status"], "PARTIAL")
        self.assertIn("APDS", snapshot["failures"])
        self.assertIn("|L=NA", snapshot["payload_text"])

    def test_inject_fault_uses_potentiometer_selector_when_satellite_is_online(self):
        fake = FakeSerialClient()
        fake.responses["ANALOG POT"] = {"pot": "4095"}
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        fake.sent.clear()

        panel._execute_command("INJECT_FAULT")

        event = panel.last_fault_event
        self.assertEqual(event.byte_index, len(panel.last_live_payload["payload_text"].encode("ascii")) - 1)
        self.assertEqual(event.bit_mask, 0x80)
        self.assertEqual(panel.fault_overlay["selector_pot"], "4095")
        self.assertIn("potenciômetro", panel.fault_flow_animation["steps"][1]["explain"])
        self.assertTrue(any(command.startswith("FAULT NONE ") for command in fake.sent))

    def test_crc_fault_button_uses_payload_crc_not_pqc_fault(self):
        fake = FakeSerialClient()
        fake.responses["ANALOG POT"] = {"pot": "2048"}
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        panel._execute_command("SET_PRESET_PQC_CRC32")
        fake.sent.clear()

        panel._execute_command("INJECT_FAULT")

        self.assertTrue(any(command.startswith("FAULT CRC32 ") for command in fake.sent))
        self.assertFalse(any(command.startswith("PQC_FAULT") for command in fake.sent))
        self.assertEqual(panel.fault_overlay["guard"], "CRC32")
        self.assertEqual(
            [step["label"] for step in panel.fault_flow_animation["steps"]],
            ["PAYLOAD", "BIT-FLIP", "CRC32", "VERIFICA", "RESULTADO"],
        )

    def test_mission_popup_persists_until_user_closes_it(self):
        panel = dashboard.DashboardPanel()
        panel._apply_hardware_response(
            "MISSION PQC_CRC32",
            {
                "scenario": "PQC_CRC32",
                "result": "DELIVERED",
                "crypto": "ML-KEM-512",
                "cipher": "AES-128-GCM",
                "checksum": "CRC32",
                "confirmation": "AES-128-GCM",
                "profile": "BASELINE",
                "cpu_mhz": "240",
                "heap": "201412",
                "elapsed_us": "13367",
                "bytes_payload": "41",
                "bytes_ciphertext": "45",
                "bytes_mlkem": "768",
                "bytes_nonce": "12",
                "bytes_gcm_tag": "16",
                "bytes_crypto": "796",
                "bytes_checksum": "4",
                "bytes_total": "841",
                "keygen_us": "3679",
                "encap_us": "3988",
                "decap_us": "5087",
                "rng_us": "4",
                "kdf_us": "39",
                "encrypt_us": "435",
                "decrypt_us": "163",
                "tag_us": "435",
                "verify_us": "163",
                "crc_us": "10",
                "key_match": "1",
                "tag_match": "1",
                "aead_match": "1",
                "crc_match": "1",
            },
        )

        self.assertTrue(panel.mission_overlay_visible)
        panel.update(60.0)
        self.assertTrue(panel.mission_overlay_visible)

        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            earth = dashboard.Earth()
            satellite = dashboard.Satellite(earth)
            panel.draw(surface, 0.5, satellite)
            self.assertIsNotNone(panel.mission_overlay_close_rect)

            close_event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": panel.mission_overlay_close_rect.center},
            )
            panel.handle_event(close_event)
            self.assertTrue(panel.mission_overlay_visible)
            panel.update(dashboard.POPUP_EXIT_SECONDS + 0.01)
            self.assertFalse(panel.mission_overlay_visible)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_mission_popups_can_be_opened_and_dragged_independently(self):
        panel = dashboard.DashboardPanel()

        def mission_payload(scenario, elapsed_us, bytes_crypto, bytes_checksum, crc_us):
            use_pqc = scenario != "CLASSIC"
            return {
                "scenario": scenario,
                "result": "DELIVERED",
                "crypto": "AES-128-GCM" if scenario == "CLASSIC" else "ML-KEM-512",
                "cipher": "AES-128-GCM",
                "checksum": "CRC32" if scenario == "PQC_CRC32" else "NONE",
                "confirmation": "AES-128-GCM",
                "profile": "BASELINE",
                "cpu_mhz": "240",
                "heap": "201412",
                "elapsed_us": str(elapsed_us),
                "bytes_payload": "41",
                "bytes_ciphertext": str(41 + bytes_checksum),
                "bytes_mlkem": "768" if use_pqc else "0",
                "bytes_nonce": "12",
                "bytes_gcm_tag": "16",
                "bytes_crypto": str(bytes_crypto),
                "bytes_checksum": str(bytes_checksum),
                "bytes_total": str(41 + bytes_crypto + bytes_checksum),
                "keygen_us": "0" if scenario == "CLASSIC" else "3679",
                "encap_us": "0" if scenario == "CLASSIC" else "3988",
                "decap_us": "0" if scenario == "CLASSIC" else "5087",
                "rng_us": "4",
                "kdf_us": "0" if scenario == "CLASSIC" else "39",
                "encrypt_us": "435",
                "decrypt_us": "163",
                "tag_us": "435",
                "verify_us": "163",
                "crc_us": str(crc_us),
                "key_match": "1",
                "tag_match": "1",
                "aead_match": "1",
                "crc_match": "1" if scenario == "PQC_CRC32" else "NA",
            }

        panel._apply_hardware_response("MISSION CLASSIC", mission_payload("CLASSIC", 721, 28, 0, 0))
        panel._apply_hardware_response("MISSION PQC", mission_payload("PQC", 13536, 796, 0, 0))
        panel._apply_hardware_response("MISSION PQC_CRC32", mission_payload("PQC_CRC32", 13367, 796, 4, 10))

        self.assertEqual(set(panel.mission_overlays), {"CLASSIC", "PQC", "PQC_CRC32"})
        self.assertTrue(panel.mission_overlay_visible)

        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            earth = dashboard.Earth()
            satellite = dashboard.Satellite(earth)
            panel.draw(surface, 0.5, satellite)
            self.assertEqual(set(panel.mission_overlay_rects), {"CLASSIC", "PQC", "PQC_CRC32"})

            panel._bring_mission_overlay_to_front("PQC")
            panel.draw(surface, 0.55, satellite)
            original_pqc_position = panel.mission_overlay_rects["PQC"].topleft
            drag_start = panel.mission_overlay_drag_rects["PQC"].center
            drag_end = (drag_start[0] - 120, drag_start[1] + 70)
            panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": drag_start}))
            panel.handle_event(
                pygame.event.Event(
                    pygame.MOUSEMOTION,
                    {"pos": drag_end, "rel": (-120, 70), "buttons": (1, 0, 0)},
                )
            )
            panel.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": drag_end}))
            self.assertNotEqual(panel.mission_overlay_positions["PQC"], original_pqc_position)

            panel.draw(surface, 0.6, satellite)
            panel.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"button": 1, "pos": panel.mission_overlay_close_rects["PQC"].center},
                )
            )

            self.assertIn("PQC", panel.mission_overlays)
            panel.update(dashboard.POPUP_EXIT_SECONDS + 0.01)
            self.assertNotIn("PQC", panel.mission_overlays)
            self.assertIn("CLASSIC", panel.mission_overlays)
            self.assertIn("PQC_CRC32", panel.mission_overlays)
            self.assertTrue(panel.mission_overlay_visible)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_aes_gcm_package_parts_split_nonce_tag_and_mlkem(self):
        panel = dashboard.DashboardPanel()
        mission = {
            "scenario": "PQC",
            "crypto": "ML-KEM-512",
            "cipher": "AES-128-GCM",
            "bytes_payload": "41",
            "bytes_mlkem": "768",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_crypto": "796",
            "bytes_checksum": "0",
        }

        parts = {label: value for label, value, _color in panel._mission_package_parts(mission)}

        self.assertEqual(parts["payload"], 41)
        self.assertEqual(parts["ML-KEM"], 768)
        self.assertEqual(parts["nonce"], 12)
        self.assertEqual(parts["GCM"], 16)
        self.assertEqual(parts["HMAC"], 0)

    def test_classic_package_parts_include_ecdh_public_key(self):
        panel = dashboard.DashboardPanel()
        mission = {
            "scenario": "CLASSIC",
            "cipher": "AES-128-GCM",
            "bytes_payload": "41",
            "bytes_ecdh": "65",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_crypto": "93",
        }

        parts = {label: value for label, value, _color in panel._mission_package_parts(mission)}

        self.assertEqual(parts["ECDH"], 65)
        self.assertEqual(parts["ML-KEM"], 0)

    def test_classic_aes_gcm_flow_uses_ephemeral_ecdh(self):
        panel = dashboard.DashboardPanel()
        mission = {
            "scenario": "CLASSIC",
            "result": "DELIVERED",
            "crypto": "ECDH-P256",
            "cipher": "AES-128-GCM",
            "checksum": "NONE",
            "key_source": "ECDH-P256",
            "bytes_payload": "41",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_ecdh": "65",
            "bytes_crypto": "93",
            "bytes_checksum": "0",
            "bytes_total": "134",
            "keygen_us": "400",
            "ecdh_tx_us": "160",
            "ecdh_rx_us": "161",
            "kdf_us": "30",
            "encrypt_us": "80",
            "decrypt_us": "81",
            "aead_match": "1",
        }

        steps = panel._mission_flow_steps(mission)

        self.assertEqual([step["label"] for step in steps], ["PAYLOAD", "KEYGEN", "ECDH", "KDF", "AES-GCM", "VERIFICA", "RESULTADO"])
        self.assertEqual(steps[2]["added_bytes"], 65)
        self.assertEqual(steps[4]["added_bytes"], 28)
        self.assertEqual(steps[-1]["packet_bytes"], 134)
        self.assertIn("P-256", steps[1]["explain"])

    def test_send_message_without_live_satellite_does_not_replay_metrics(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("SET_PRESET_PQC_CRC32")
        panel._execute_command("SEND_MESSAGE")

        self.assertEqual(panel.command_history[-1]["status"], "SAT OFF")
        self.assertEqual(panel.last_mission, {})
        self.assertFalse(panel.mission_overlay_visible)
        self.assertIsNone(panel.mission_flow_animation)
        self.assertEqual(panel.hardware_samples, [])
        self.assertEqual(panel.session_status, "AGUARDANDO SAT")

    def test_dashboard_does_not_poll_telemetry_automatically(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        fake.sent.clear()

        for _ in range(40):
            panel.update(30.0)

        self.assertNotIn("TELEMETRY", fake.sent)

    def test_physical_button_event_triggers_non_blocking_ping_animation(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        previous_status = panel.session_status
        previous_history = list(panel.command_history)
        fake.events.append(
            (
                "event",
                {
                    "name": "BUTTON_PING",
                    "payload": {"button": "1", "uptime_ms": "42"},
                },
            )
        )

        panel.update(0.01)

        self.assertEqual(panel.ping_effect_count, 1)
        self.assertGreater(panel.ping_effect_timer, 0.0)
        self.assertEqual(panel.session_status, previous_status)
        self.assertEqual(panel.command_history, previous_history)

        surface = pygame.Surface((dashboard.WIDTH, dashboard.HEIGHT), pygame.SRCALPHA)
        earth = dashboard.Earth()
        satellite = dashboard.Satellite(earth)
        panel._draw_ping_effect(surface, 0.5, satellite)
        self.assertIsNotNone(panel.ping_effect_last_segment)

        panel.update(dashboard.PING_ANIMATION_SECONDS + 0.1)
        self.assertEqual(panel.ping_effect_timer, 0.0)

    def test_dashboard_draws_in_projector_target_resolutions(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1920, 1080), (1366, 768)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                earth = dashboard.Earth()
                satellite = dashboard.Satellite(earth)
                panel = dashboard.DashboardPanel()
                panel._execute_command("INJECT_FAULT")

                panel.draw(surface, 0.5, satellite)
                panel.results_overlay_visible = True
                panel.draw(surface, 0.6, satellite)
                panel.draw_satellite_lock(surface, 0.5)
                nebula = dashboard.Nebula()
                nebula.draw(surface, 0.5)
                first_cache = nebula.surface_cache
                nebula.draw(surface, 0.7)

                self.assertIs(nebula.surface_cache, first_cache)
                self.assertEqual(surface.get_size(), (width, height))
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_top_bar_onboarding_button_requests_intro(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((1366, 768), pygame.SRCALPHA)
            panel = dashboard.DashboardPanel()

            panel._draw_top_bar(surface, 0.5)

            self.assertIsNotNone(panel.top_results_btn_rect)
            self.assertIsNotNone(panel.top_onboarding_btn_rect)
            self.assertGreater(panel.top_onboarding_btn_rect.left, panel.top_results_btn_rect.right)

            panel.results_overlay_visible = True
            click = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": panel.top_onboarding_btn_rect.center},
            )

            self.assertTrue(panel.handle_event(click))
            self.assertTrue(panel.request_onboarding)
            self.assertFalse(panel.results_overlay_visible)
            self.assertEqual(panel.session_status, "ONBOARDING")
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_top_bar_connection_label_fits_projector_target_resolutions(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1920, 1080), (1366, 768)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                panel = dashboard.DashboardPanel(serial_client=FakeSerialClient())
                panel.serial_connected = True

                panel._draw_top_bar(surface, 0.5)

                self.assertIsNotNone(panel.top_connection_text_rect)
                self.assertLessEqual(panel.top_connection_text_rect.right, width - 20)
                self.assertGreaterEqual(panel.top_connection_text_rect.left, 0)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_results_overlay_content_fits_projector_target_resolutions(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1920, 1080), (1366, 768)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                panel = dashboard.DashboardPanel()
                panel.results_overlay_visible = True

                panel._draw_results_overlay(surface, 0.5)

                panel_rect, _close_rect = panel._results_overlay_geometry()
                self.assertIsNotNone(panel.results_stress_btn_rect)
                self.assertLessEqual(panel.results_stress_btn_rect.bottom, panel_rect.bottom - 8)
                self.assertIsNotNone(panel.results_overlay_content_bottom)
                self.assertLessEqual(panel.results_overlay_content_bottom, panel_rect.bottom - 8)
                self.assertEqual(len(panel.results_insight_rects), 3)
                required_card_h = 48 + 2 * 25 + dashboard.FONT_BODY.get_height() + 8
                for rect in panel.results_insight_rects:
                    self.assertGreaterEqual(rect.height, required_card_h)
                    self.assertLessEqual(rect.bottom, panel_rect.bottom - 20)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_results_technical_overlay_has_clear_sections_and_fits(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1920, 1080), (1366, 768)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                panel = dashboard.DashboardPanel()
                panel.results_overlay_visible = True
                panel.results_overlay_mode = "technical"

                panel._draw_results_overlay(surface, 0.5)

                panel_rect, _close_rect = panel._results_overlay_geometry()
                self.assertGreaterEqual(len(panel.results_technical_sections), 8)
                self.assertLessEqual(panel.results_overlay_content_bottom, panel_rect.bottom - 18)
                for rect in panel.results_technical_sections:
                    self.assertGreater(rect.width, 100)
                    self.assertGreater(rect.height, 80)
                    self.assertTrue(panel_rect.contains(rect))

                self.assertIsNotNone(panel.results_technical_page_btn_rect)
                self.assertFalse(panel.results_technical_page_btn_rect.colliderect(panel.results_details_btn_rect))

                page_click = pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"button": 1, "pos": panel.results_technical_page_btn_rect.center},
                )
                self.assertTrue(panel.handle_event(page_click))
                self.assertEqual(panel.results_technical_page, 1)
                panel._draw_results_overlay(surface, 0.6)
                self.assertEqual(len(panel.results_technical_sections), 6)
                self.assertLessEqual(panel.results_overlay_content_bottom, panel_rect.bottom - 18)
                for rect in panel.results_technical_sections:
                    self.assertGreater(rect.width, 100)
                    self.assertGreater(rect.height, 80)
                    self.assertTrue(panel_rect.contains(rect))
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_results_overlay_keeps_short_core_bibliography(self):
        rendered = " ".join(f"{name} {detail}" for name, detail in dashboard.RESULTS_REFERENCES)
        motivation = " ".join(f"{name} {detail}" for name, detail in dashboard.MOTIVATION_REFERENCES)

        self.assertLessEqual(len(dashboard.RESULTS_REFERENCES), 4)
        self.assertLessEqual(len(dashboard.MOTIVATION_REFERENCES), 3)
        for expected in ("FIPS 203", "FIPS 197", "800-38D", "Koopman"):
            self.assertIn(expected, rendered)
        for expected in ("NIST PQC", "NASA SmallSat", "Mikaelian"):
            self.assertIn(expected, motivation)

    def test_onboarding_draws_all_slides_in_projector_target_resolutions(self):
        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1920, 1080), (1366, 768)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                stars = dashboard.StarField(12)
                earth = dashboard.Earth()
                satellite = dashboard.Satellite(earth)
                onboarding = dashboard.Onboarding(
                    stars,
                    earth,
                    satellite,
                    dashboard.Nebula(),
                    dashboard.CosmicDust(4),
                    dashboard.ShootingStars(),
                )

                self.assertEqual(onboarding.total_slides, 5)
                for slide in range(onboarding.total_slides):
                    onboarding.current_slide = slide
                    onboarding.draw(surface, 0.5 + slide)

                self.assertEqual(surface.get_size(), (width, height))
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

    def test_pqc_info_response_updates_label_and_exportable_metrics(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True

        panel._apply_hardware_response(
            "PQC_INFO",
            {
                "pqc_target": "ML-KEM-512",
                "pqc_backend": "mlkem-native",
                "pqc_status": "ready",
                "cpu_mhz": "240",
                "heap": "233556",
                "min_heap": "230000",
                "flash": "4194304",
                "elapsed_us": "11",
                "profile": "BASELINE",
                "radio": "off",
                "pk": "800",
                "sk": "1632",
                "ct": "768",
                "ss": "32",
            },
        )

        self.assertEqual(panel.pqc_algorithm, "ML-KEM-512 (READY)")
        self.assertEqual(panel.hardware_samples[-1]["source_command"], "PQC_INFO")
        self.assertEqual(panel.hardware_samples[-1]["pqc_backend"], "mlkem-native")
        self.assertEqual(panel.hardware_samples[-1]["pqc"]["pk"], 800)
        self.assertEqual(panel.hardware_samples[-1]["pqc"]["pqc_status"], "ready")
        data = panel._build_export_document()
        self.assertEqual(data["config"]["pqc_target"], "ML-KEM-512")
        self.assertEqual(data["config"]["pqc_backend"], "mlkem-native")
        self.assertEqual(data["config"]["pqc_status"], "ready")
        self.assertEqual(data["metrics"]["cpu"]["kind"], "observed_command_active_time")
        self.assertGreaterEqual(data["hardware_samples"][-1]["cpu_load_pct"], 0)

    def test_pqc_bench_response_exports_structured_metrics_without_secrets(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True

        panel._apply_hardware_response(
            "PQC_BENCH 5",
            {
                "n": "5",
                "ok": "5",
                "key_match": "1",
                "keygen_avg_us": "10101",
                "encap_avg_us": "11778",
                "decap_avg_us": "15214",
                "elapsed_us": "187371",
                "heap": "202444",
                "min_heap": "198456",
            },
        )

        sample = panel.hardware_samples[-1]
        self.assertEqual(sample["source_command"], "PQC_BENCH")
        self.assertEqual(sample["pqc"]["n"], 5)
        self.assertEqual(sample["pqc"]["key_match"], 1)
        self.assertEqual(sample["pqc"]["keygen_avg_us"], 10101)
        self.assertNotIn("shared_secret", json.dumps(sample))

    def test_pqc_ciphertext_fault_is_recorded_without_presentation_popup(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True

        panel._apply_hardware_response(
            "PQC_FAULT 0 0x01 CONFIRM",
            {
                "op": "ciphertext_fault",
                "target": "CIPHERTEXT",
                "result": "PROTOCOL_REJECT",
                "confirmation": "HMAC-SHA256",
                "key_match": "0",
                "key_confirmed": "0",
                "tag_match": "0",
                "tag_ready": "1",
                "byte_index": "0",
                "bit_mask": "0x01",
                "ct_crc_before": "0x11111111",
                "ct_crc_after": "0x22222222",
                "ss_enc_crc32": "0x33333333",
                "ss_dec_crc32": "0x44444444",
                "tag_enc_crc32": "0x55555555",
                "tag_dec_crc32": "0x66666666",
                "keygen_us": "1000",
                "encap_us": "1100",
                "decap_us": "1200",
                "confirm_us": "130",
                "elapsed_us": "3500",
                "heap": "202444",
            },
        )

        sample = panel.hardware_samples[-1]
        self.assertEqual(sample["source_command"], "PQC_FAULT")
        self.assertEqual(sample["pqc"]["result"], "PROTOCOL_REJECT")
        self.assertEqual(sample["pqc"]["confirmation"], "HMAC-SHA256")
        self.assertEqual(sample["pqc"]["key_confirmed"], 0)
        self.assertEqual(sample["pqc"]["tag_match"], 0)
        self.assertEqual(sample["pqc"]["ct_crc_after"], "0x22222222")
        self.assertEqual(sample["pqc"]["confirm_us"], 130)
        self.assertNotIn("pqc_ss", json.dumps(sample))
        self.assertFalse(panel.fault_overlay_visible)
        self.assertIsNone(panel.fault_flow_animation)

    def test_mission_command_requires_online_satellite(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("MISSION PQC")

        self.assertEqual(panel.command_history[-1]["status"], "SAT OFF")
        self.assertEqual(panel.session_status, "AGUARDANDO SAT")

    def test_mission_command_queues_scenario_and_visual_effects(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        fake.sent.clear()

        panel._execute_command("MISSION PQC_CRC32")

        self.assertEqual(fake.sent[0:2], ["LED YELLOW", "BARGRAPH 10"])
        self.assertTrue(fake.sent[2].startswith("MISSION PQC_CRC32 "))
        self.assertEqual(fake.sent[3:6], ["BARGRAPH 100", "LED GREEN", "RGB 0 255 120"])
        self.assertTrue(panel.command_history[-1]["cmd"].startswith("MISSION PQC_CRC32 "))
        self.assertEqual(panel.command_history[-1]["status"], "QUEUED")

    def test_mission_response_exports_consolidated_metrics(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True

        panel._apply_hardware_response(
            "MISSION PQC_CRC32",
            {
                "scenario": "PQC_CRC32",
                "op": "mission_message",
                "message": "HELLO_UFF",
                "result": "DELIVERED",
                "crypto": "ML-KEM-512",
                "cipher": "AES-128-GCM",
                "checksum": "CRC32",
                "confirmation": "AES-128-GCM",
                "key_match": "1",
                "tag_ready": "1",
                "tag_match": "1",
                "aead_match": "1",
                "decrypt_ok": "1",
                "crc_match": "1",
                "payload_len": "41",
                "bytes_payload": "41",
                "bytes_ciphertext": "45",
                "bytes_mlkem": "768",
                "bytes_nonce": "12",
                "bytes_gcm_tag": "16",
                "bytes_crypto": "796",
                "bytes_checksum": "4",
                "bytes_total": "841",
                "keygen_us": "10045",
                "encap_us": "11769",
                "decap_us": "15194",
                "rng_us": "5",
                "kdf_us": "44",
                "encrypt_us": "80",
                "decrypt_us": "81",
                "tag_us": "80",
                "verify_us": "81",
                "crc_us": "11",
                "elapsed_us": "37180",
                "heap": "201512",
                "min_heap": "197624",
                "profile": "OBC-1U-LIMITED",
                "cpu_mhz": "80",
            },
        )

        sample = panel.hardware_samples[-1]
        self.assertEqual(panel.last_mission["scenario"], "PQC_CRC32")
        self.assertEqual(sample["mission"]["result"], "DELIVERED")
        self.assertEqual(sample["mission"]["bytes_total"], 841)
        self.assertEqual(sample["mission"]["cipher"], "AES-128-GCM")
        self.assertEqual(sample["mission"]["aead_match"], 1)
        data = panel._build_export_document()
        scenario = data["metrics"]["mission"]["scenarios"]["PQC_CRC32"]
        self.assertEqual(scenario["elapsed_us"], 37180)

    def test_mission_response_starts_step_by_step_satellite_animation(self):
        panel = dashboard.DashboardPanel()
        panel.serial_connected = True
        payload = {
            "scenario": "PQC_CRC32",
            "op": "mission_message",
            "message": "HELLO_UFF",
            "result": "DELIVERED",
            "crypto": "ML-KEM-512",
            "cipher": "AES-128-GCM",
            "checksum": "CRC32",
            "confirmation": "AES-128-GCM",
            "key_match": "1",
            "tag_ready": "1",
            "tag_match": "1",
            "aead_match": "1",
            "decrypt_ok": "1",
            "crc_match": "1",
            "payload_len": "41",
            "bytes_payload": "41",
            "bytes_ciphertext": "45",
            "bytes_mlkem": "768",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_crypto": "796",
            "bytes_checksum": "4",
            "bytes_total": "841",
            "keygen_us": "3679",
            "encap_us": "3988",
            "decap_us": "5087",
            "rng_us": "4",
            "kdf_us": "39",
            "encrypt_us": "435",
            "decrypt_us": "163",
            "tag_us": "435",
            "verify_us": "163",
            "crc_us": "10",
            "elapsed_us": "13367",
            "heap": "201412",
            "min_heap": "197624",
            "profile": "BASELINE",
            "cpu_mhz": "240",
        }

        panel._apply_hardware_response("MISSION PQC_CRC32", payload)

        self.assertIsNotNone(panel.mission_flow_animation)
        self.assertEqual(panel.mission_flow_animation["duration"], dashboard.MISSION_FLOW_ANIMATION_SECONDS)
        self.assertLess(panel.mission_flow_animation["duration"], 12.0)
        self.assertFalse(panel.mission_flow_animation["awaiting_confirm"])
        self.assertNotIn("paused", panel.mission_flow_animation)
        steps = panel.mission_flow_animation["steps"]
        # Ordem fiel da mensagem: lado emissor (KEYGEN->ENCAP->KDF->AES-GCM)
        # e depois lado receptor (DECAP->VERIFICA). O DECAP só ocorre apos a
        # cifragem, pois depende do pacote ja transmitido.
        self.assertEqual(
            [step["label"] for step in steps],
            ["PAYLOAD", "CRC32", "KEYGEN", "ENCAP", "KDF", "AES-GCM", "DECAP", "VERIFICA", "RESULTADO"],
        )
        self.assertEqual(steps[-1]["packet_bytes"], 841)
        self.assertEqual(steps[1]["added_bytes"], 4)
        self.assertEqual(steps[3]["added_bytes"], 768)
        self.assertEqual(steps[5]["added_bytes"], 28)
        self.assertIn("ciphertext ML-KEM", steps[3]["explain"])
        self.assertTrue(panel._mission_overlay_is_animating("PQC_CRC32"))

        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            for width, height in ((1366, 768), (1920, 1080)):
                dashboard.WIDTH, dashboard.HEIGHT = width, height
                surface = pygame.Surface((width, height), pygame.SRCALPHA)
                earth = dashboard.Earth()
                satellite = dashboard.Satellite(earth)
                panel.draw(surface, 0.5, satellite)
                self.assertTrue(panel.mission_overlay_visible)
                self.assertIsNotNone(panel.mission_flow_animation)
                self.assertIn("PQC_CRC32", panel.mission_overlay_rects)
                self.assertIn("PQC_CRC32", panel.mission_flow_control_rects)
                self.assertIn("PQC_CRC32", panel.mission_flow_scrub_rects)
                self.assertIn("PQC_CRC32", panel.mission_flow_stage_rects)
                popup_rect = panel.mission_overlay_rects["PQC_CRC32"]
                stage_rect = panel.mission_flow_stage_rects["PQC_CRC32"]
                self.assertAlmostEqual(stage_rect.centerx, popup_rect.centerx, delta=1)
                self.assertLessEqual(stage_rect.bottom, popup_rect.bottom)
                self.assertLessEqual(panel.mission_flow_explanation_line_counts["PQC_CRC32"], 4)
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

        scrub_rect = panel.mission_flow_scrub_rects["PQC_CRC32"]
        scrub_start = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": (scrub_rect.x, scrub_rect.centery)},
        )
        self.assertTrue(panel._handle_mission_overlay_event(scrub_start))
        self.assertAlmostEqual(panel.mission_flow_animation["age"], 0.0)
        scrub_end = pygame.event.Event(
            pygame.MOUSEMOTION,
            {"pos": (scrub_rect.right, scrub_rect.centery)},
        )
        self.assertTrue(panel._handle_mission_overlay_event(scrub_end))
        self.assertEqual(panel.mission_flow_animation["age"], dashboard.MISSION_FLOW_ANIMATION_SECONDS)
        self.assertTrue(panel.mission_flow_animation["awaiting_confirm"])
        scrub_release = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            {"button": 1, "pos": (scrub_rect.right, scrub_rect.centery)},
        )
        self.assertTrue(panel._handle_mission_overlay_event(scrub_release))

        # Grabbing the scrub bar pauses the flow: it no longer auto-advances and
        # stays wherever it is dragged (regression guard for the pause behavior).
        self.assertTrue(panel.mission_flow_animation.get("paused"))
        grab = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (scrub_rect.centerx, scrub_rect.centery)}
        )
        self.assertTrue(panel._handle_mission_overlay_event(grab))
        self.assertFalse(panel.mission_flow_animation["awaiting_confirm"])
        paused_age = panel.mission_flow_animation["age"]
        self.assertGreater(paused_age, 0.0)
        panel.update(0.5)
        self.assertEqual(panel.mission_flow_animation["age"], paused_age)

        to_end = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (scrub_rect.right, scrub_rect.centery)})
        self.assertTrue(panel._handle_mission_overlay_event(to_end))
        panel._handle_mission_overlay_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (scrub_rect.right, scrub_rect.centery)})
        )
        self.assertIsNotNone(panel.mission_flow_animation)
        self.assertTrue(panel.mission_flow_animation["awaiting_confirm"])
        self.assertTrue(panel._mission_overlay_is_animating("PQC_CRC32"))
        self.assertTrue(panel.mission_overlay_visible)

        control_rect = panel.mission_flow_control_rects["PQC_CRC32"]
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": control_rect.center})
        self.assertTrue(panel._handle_mission_overlay_event(click))
        self.assertIsNone(panel.mission_flow_animation)
        self.assertFalse(panel._mission_overlay_is_animating("PQC_CRC32"))

    def test_opening_second_mission_keeps_first_popup_waiting_for_own_confirmation(self):
        panel = dashboard.DashboardPanel()
        classic = {
            "scenario": "CLASSIC",
            "result": "DELIVERED",
            "crypto": "CLASSIC",
            "cipher": "AES-128-GCM",
            "checksum": "NONE",
            "payload_len": "41",
            "bytes_payload": "41",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_crypto": "28",
            "bytes_checksum": "0",
            "bytes_total": "69",
            "rng_us": "5",
            "encrypt_us": "210",
            "decrypt_us": "180",
            "elapsed_us": "520",
            "heap": "201412",
        }
        pqc = {
            "scenario": "PQC",
            "result": "DELIVERED",
            "crypto": "ML-KEM-512",
            "cipher": "AES-128-GCM",
            "checksum": "NONE",
            "payload_len": "41",
            "bytes_payload": "41",
            "bytes_mlkem": "768",
            "bytes_nonce": "12",
            "bytes_gcm_tag": "16",
            "bytes_crypto": "796",
            "bytes_checksum": "0",
            "bytes_total": "837",
            "keygen_us": "3600",
            "encap_us": "3900",
            "decap_us": "5000",
            "kdf_us": "40",
            "encrypt_us": "230",
            "decrypt_us": "190",
            "elapsed_us": "13200",
            "heap": "201412",
        }

        panel._apply_hardware_response("MISSION CLASSIC", classic)
        self.assertTrue(panel._mission_overlay_is_animating("CLASSIC"))
        panel.mission_flow_animations["CLASSIC"]["age"] = dashboard.MISSION_FLOW_ANIMATION_SECONDS
        panel.mission_flow_animations["CLASSIC"]["awaiting_confirm"] = True

        panel._apply_hardware_response("MISSION PQC", pqc)

        self.assertTrue(panel._mission_overlay_is_animating("CLASSIC"))
        self.assertTrue(panel._mission_overlay_is_animating("PQC"))
        self.assertIn("CLASSIC", panel.mission_flow_animations)
        self.assertIn("PQC", panel.mission_flow_animations)

        old_size = (dashboard.WIDTH, dashboard.HEIGHT)
        try:
            dashboard.WIDTH, dashboard.HEIGHT = 1366, 768
            surface = pygame.Surface((dashboard.WIDTH, dashboard.HEIGHT), pygame.SRCALPHA)
            earth = dashboard.Earth()
            satellite = dashboard.Satellite(earth)
            panel.draw(surface, 0.5, satellite)
            self.assertIn("CLASSIC", panel.mission_flow_control_rects)
            self.assertIn("PQC", panel.mission_flow_control_rects)
            self.assertTrue(panel.mission_flow_animations["CLASSIC"]["awaiting_confirm"])
        finally:
            dashboard.WIDTH, dashboard.HEIGHT = old_size

        panel._confirm_mission_flow("CLASSIC")
        self.assertFalse(panel._mission_overlay_is_animating("CLASSIC"))
        self.assertTrue(panel._mission_overlay_is_animating("PQC"))

    def test_run_battery_pairs_none_and_crc32_with_same_fault_ids(self):
        panel = dashboard.DashboardPanel()
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: Path("battery.json")

        panel._execute_command("RUN_BATTERY 3")

        events = panel.experiment_events
        self.assertEqual(len(events), 6)
        for index in range(3):
            event_a = events[index]
            event_b = events[index + 3]
            self.assertEqual(event_a.campaign_run_id, "battery-001")
            self.assertEqual(event_b.campaign_run_id, "battery-001")
            self.assertEqual(event_a.campaign_trial_id, index + 1)
            self.assertEqual(event_b.campaign_trial_id, index + 1)
            self.assertEqual(event_a.byte_index, event_b.byte_index)
            self.assertEqual(event_a.bit_mask, event_b.bit_mask)
            self.assertEqual(event_a.guard, "NONE")
            self.assertEqual(event_b.guard, "CRC32")

        data = panel._build_export_document()
        self.assertEqual(data["config"]["checksum"], "MIXED")
        self.assertEqual(data["events"][0]["campaign_run_id"], "battery-001")
        self.assertEqual(data["events"][0]["campaign_trial_id"], 1)
        self.assertEqual(data["events"][3]["campaign_trial_id"], 1)
        self.assertEqual(data["metrics"]["checksum"]["events"], 3)
        self.assertEqual(data["metrics"]["checksum"]["detection_rate_pct"], 100.0)

    def test_multiple_batteries_have_distinct_run_ids(self):
        panel = dashboard.DashboardPanel()
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: Path("battery.json")

        panel._execute_command("RUN_BATTERY 1")
        panel._execute_command("RUN_BATTERY 1")

        run_ids = [event.campaign_run_id for event in panel.experiment_events]
        self.assertEqual(run_ids, ["battery-001", "battery-001", "battery-002", "battery-002"])




if __name__ == "__main__":
    unittest.main()
