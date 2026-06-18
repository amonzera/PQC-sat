import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json

import dashboard


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
        self.assertEqual(len(data["hardware_samples"]), 1)
        self.assertEqual(data["hardware_samples"][0]["energy_proxy"]["kind"], "relative_cpu_time")

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

    def test_pqc_status_queries_board_when_serial_is_online(self):
        fake = FakeSerialClient()
        panel = dashboard.DashboardPanel(serial_client=fake)
        panel.serial_connected = True

        panel._execute_command("PQC_STATUS")

        self.assertEqual(fake.sent[-1], "PQC_INFO")
        self.assertEqual(panel.command_history[-1]["cmd"], "PQC_INFO")
        self.assertEqual(panel.command_history[-1]["status"], "QUEUED")

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
            },
        )

        self.assertEqual(panel.pqc_algorithm, "ML-KEM-512 (READY)")
        self.assertEqual(panel.hardware_samples[-1]["source_command"], "PQC_INFO")
        self.assertEqual(panel.hardware_samples[-1]["pqc_backend"], "mlkem-native")
        data = panel._build_export_document()
        self.assertEqual(data["config"]["pqc_target"], "ML-KEM-512")
        self.assertEqual(data["config"]["pqc_backend"], "mlkem-native")
        self.assertEqual(data["config"]["pqc_status"], "ready")

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

    def test_multiple_batteries_have_distinct_run_ids(self):
        panel = dashboard.DashboardPanel()
        panel.export_session = lambda log_dir=dashboard.DEFAULT_LOG_DIR: Path("battery.json")

        panel._execute_command("RUN_BATTERY 1")
        panel._execute_command("RUN_BATTERY 1")

        run_ids = [event.campaign_run_id for event in panel.experiment_events]
        self.assertEqual(run_ids, ["battery-001", "battery-001", "battery-002", "battery-002"])


if __name__ == "__main__":
    unittest.main()
