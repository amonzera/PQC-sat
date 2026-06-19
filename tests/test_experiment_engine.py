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


class FakeSerialClient:
    def __init__(self):
        self.sent = []

    def start(self):
        pass

    def stop(self):
        pass

    def send(self, command_line):
        self.sent.append(command_line)

    def poll(self):
        return []


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


class DashboardCommandTests(unittest.TestCase):
    def test_fault_commands_update_metrics_from_events(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("INJECT_FAULT")
        self.assertEqual(panel.fault_injections, 1)
        self.assertEqual(panel.silent_failures, 1)
        self.assertEqual(panel.detected_errors, 0)
        self.assertEqual(panel.last_fault_event.result, "SILENT")

        panel._execute_command("CRC_CHECK")
        self.assertEqual(panel.fault_injections, 2)
        self.assertEqual(panel.silent_failures, 1)
        self.assertEqual(panel.detected_errors, 1)
        self.assertEqual(panel.last_fault_event.result, "DETECTED_GUARD")

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

    def test_invalid_manual_bit_flip_does_not_create_event(self):
        panel = dashboard.DashboardPanel()
        panel._execute_command("BIT_FLIP 999 0x01")

        self.assertEqual(panel.fault_injections, 0)
        self.assertEqual(panel.command_history[-1]["status"], "INVALID_INPUT")

    def test_timeline_layout_limits_window_and_keeps_summary_global(self):
        engine = dashboard.ExperimentEngine(seed=7)
        for index in range(20):
            guard = "CRC32" if index % 2 else "NONE"
            engine.run_fault(guard=guard)

        layout = dashboard.timeline_layout(engine.events, 20, 55, 272, 72)
        summary = dashboard.event_summary(engine.events)

        self.assertEqual(len(layout), dashboard.TIMELINE_WINDOW)
        self.assertEqual(summary["events"], 20)
        self.assertEqual(summary["silent"], 10)
        self.assertEqual(summary["detected_guard"], 10)
        for point in layout:
            self.assertGreaterEqual(point["x"], 20)
            self.assertLess(point["x"], 20 + 272)
            self.assertGreaterEqual(point["y"], 55)
            self.assertLess(point["y"], 55 + 72)

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

    def test_dashboard_help_contains_advanced_firmware_commands(self):
        panel = dashboard.DashboardPanel()

        panel._execute_command("HELP")
        rendered = "\n".join(panel._console_help_lines())

        self.assertTrue(panel.help_visible)
        self.assertIn("PQC_INFO", rendered)
        self.assertIn("I2C_SCAN", rendered)

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

        self.assertIn("SEND_MESSAGE", commands)
        self.assertIn("TOGGLE_CLASSIC", commands)
        self.assertIn("TOGGLE_PQC", commands)
        self.assertIn("TOGGLE_CHECKSUM", commands)
        self.assertIn("INJECT_FAULT", commands)
        self.assertNotIn("DEMO", commands)
        self.assertNotIn("DEMO_PAUSE", commands)
        self.assertNotIn("EXPORT_JSON", commands)
        self.assertNotIn("MISSION CLASSIC", commands)
        self.assertNotIn("MISSION PQC", commands)
        self.assertNotIn("MISSION PQC_CRC32", commands)
        self.assertNotIn("TELEMETRY", commands)
        self.assertNotIn("PING", commands)

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

    def test_dashboard_send_message_routes_to_correct_mission(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        # Case 1: PQC active, checksum disabled -> MISSION PQC
        panel.pqc_enabled = True
        panel.classic_enabled = False
        panel.checksum_enabled = False
        panel._execute_command("SEND_MESSAGE")
        self.assertIn("MISSION PQC", fake.sent)

        # Case 2: PQC active, checksum enabled -> MISSION PQC_CRC32
        fake.sent.clear()
        panel.pqc_enabled = True
        panel.classic_enabled = False
        panel.checksum_enabled = True
        panel._execute_command("SEND_MESSAGE")
        self.assertIn("MISSION PQC_CRC32", fake.sent)

        # Case 3: Classic active, checksum enabled -> MISSION CLASSIC (checksum ignored)
        fake.sent.clear()
        panel.pqc_enabled = False
        panel.classic_enabled = True
        panel.checksum_enabled = True
        panel._execute_command("SEND_MESSAGE")
        self.assertIn("MISSION CLASSIC", fake.sent)

    def test_dashboard_does_not_poll_telemetry_automatically(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True
        fake.sent.clear()

        for _ in range(40):
            panel.update(dashboard.TELEMETRY_POLL_SECONDS)

        self.assertNotIn("TELEMETRY", fake.sent)

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
                panel.draw_satellite_lock(surface, 0.5)
                nebula = dashboard.Nebula()
                nebula.draw(surface, 0.5)
                first_cache = nebula.surface_cache
                nebula.draw(surface, 0.7)

                self.assertIs(nebula.surface_cache, first_cache)
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

    def test_pqc_ciphertext_fault_exports_key_confirmation_result(self):
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

        self.assertEqual(fake.sent[:3], ["MISSION PQC_CRC32", "BARGRAPH 100", "LED GREEN"])
        self.assertEqual(panel.command_history[-1]["cmd"], "MISSION PQC_CRC32")
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
                "checksum": "CRC32",
                "confirmation": "HMAC-SHA256",
                "key_match": "1",
                "tag_ready": "1",
                "tag_match": "1",
                "crc_match": "1",
                "payload_len": "41",
                "bytes_payload": "41",
                "bytes_crypto": "800",
                "bytes_checksum": "4",
                "bytes_total": "845",
                "keygen_us": "10045",
                "encap_us": "11769",
                "decap_us": "15194",
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
        self.assertEqual(sample["mission"]["bytes_total"], 845)
        data = panel._build_export_document()
        scenario = data["metrics"]["mission"]["scenarios"]["PQC_CRC32"]
        self.assertEqual(scenario["elapsed_us"], 37180)

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
