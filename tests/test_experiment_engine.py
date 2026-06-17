import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import dashboard


class ExperimentEngineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
