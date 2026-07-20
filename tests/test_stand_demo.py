import json
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

import pygame

from stand_demo import (
    AnimationModel,
    DEFAULT_CONFIG_PATH,
    DEFAULT_FIXTURE_PATH,
    DemoState,
    FaultSelection,
    FixtureSerialClient,
    HardwareMeasurement,
    StandConfig,
    StandConfigError,
    StandController,
    StandProtocolError,
    StandRenderer,
    StandSessionLogger,
    fault_selection_from_pot,
    flip_selected_bit,
    parse_fault_response,
    parse_mission_response,
    safe_ratio,
)
from tools.validate_stand_logs import count_disconnect_recoveries, validate_cycle


class FastStandFlow:
    def __init__(self):
        base = StandConfig.load(DEFAULT_CONFIG_PATH)
        self.config = replace(
            base,
            intro_seconds=0.02,
            comparison_hold_seconds=0.02,
            fault_hold_seconds=0.02,
            auto_reset_seconds=0.05,
            pot_poll_interval_seconds=0.01,
            button_debounce_seconds=0.01,
        )
        self.client = FixtureSerialClient(DEFAULT_FIXTURE_PATH, self.config, latency_seconds=0)
        self.sent = []

        def send(command, *, timeout=None):
            self.sent.append(command)
            self.client.send(command, timeout=timeout)

        self.controller = StandController(self.config, send, mode="simulated", now=0.0)
        self.client.start()
        self.pump(0.0)

    def pump(self, now):
        for _ in range(20):
            events = self.client.poll()
            if not events:
                return
            for event_type, payload in events:
                self.controller.handle_serial_event(event_type, payload, now=now)
        raise AssertionError("fixture did not quiesce")

    def complete(self):
        self.assert_ready()
        self.controller.handle_button(now=0.1, origin="test")
        self.controller.update(now=0.2)
        self.pump(0.2)
        self.controller.update(now=0.3)
        self.pump(0.3)
        self.controller.update(now=0.4)
        self.pump(0.4)
        self.controller.update(now=0.5)
        self.pump(0.5)
        self.controller.update(now=0.51)
        self.pump(0.51)
        self.controller.handle_button(now=0.6, origin="test")
        self.pump(0.6)
        self.controller.update(now=0.7)
        self.pump(0.7)
        self.controller.update(now=0.8)
        self.pump(0.8)
        return self.controller

    def assert_ready(self):
        if not self.controller.ready:
            raise AssertionError("fixture handshake was not accepted")


class StandConfigurationTests(unittest.TestCase):
    def test_default_config_and_official_fixture_match(self):
        config = StandConfig.load(DEFAULT_CONFIG_PATH)
        fixture = json.loads(Path(DEFAULT_FIXTURE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(config.payload, fixture["payload"])
        self.assertEqual(len(config.payload_bytes), 41)
        self.assertEqual(config.baseline_mhz, 240)
        self.assertEqual(config.limited_mhz, 80)
        self.assertTrue(fixture["official_candidate"])
        self.assertEqual(fixture["failed"], 0)

    def test_fixture_rejects_a_payload_without_official_metrics(self):
        config = replace(StandConfig.load(DEFAULT_CONFIG_PATH), payload="OUTRO PAYLOAD")
        with self.assertRaisesRegex(StandConfigError, "payload da fixture"):
            FixtureSerialClient(DEFAULT_FIXTURE_PATH, config)

    def test_config_rejects_non_ascii_payload(self):
        source = json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
        source["payload"] = "temperatura=24°"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(StandConfigError, "ASCII"):
                StandConfig.load(path)


class StandBitMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = StandConfig.load(DEFAULT_CONFIG_PATH)

    def test_pot_endpoints_cover_first_and_last_bit(self):
        first = fault_selection_from_pot(0, 4, self.config)
        last = fault_selection_from_pot(4095, 4, self.config)
        self.assertEqual((first.byte_index, first.bit_mask, first.bit_position), (0, 0x01, 0))
        self.assertEqual((last.byte_index, last.bit_mask, last.bit_position), (3, 0x80, 31))

    def test_mapping_clamps_outside_adc_range(self):
        low = fault_selection_from_pot(-100, 2, self.config)
        high = fault_selection_from_pot(9999, 2, self.config)
        self.assertEqual(low.pot_value, 0)
        self.assertEqual(high.pot_value, 4095)

    def test_flip_changes_exactly_one_bit(self):
        payload = b"PQC-SAT"
        selection = FaultSelection(byte_index=2, bit_mask=0x08, bit_position=19, pot_value=100)
        mutated = flip_selected_bit(payload, selection)
        xor = int.from_bytes(payload, "big") ^ int.from_bytes(mutated, "big")
        self.assertEqual(xor.bit_count(), 1)
        self.assertEqual(mutated[2], payload[2] ^ 0x08)

    def test_safe_ratio_handles_zero_and_missing_values(self):
        self.assertIsNone(safe_ratio(4, 0))
        self.assertIsNone(safe_ratio(None, 2))
        self.assertEqual(safe_ratio(10, 4), 2.5)

    def test_animation_is_proportional_but_clamped(self):
        base = {
            "command": "MISSION PQC",
            "scenario": "PQC",
            "profile": "BASELINE",
            "profile_mhz": 240,
            "bytes_total": 837,
            "result": "DELIVERED",
            "source": "hardware-live",
            "payload_hex": "50",
            "raw_response": {},
        }
        short = AnimationModel.for_measurement(HardwareMeasurement(elapsed_us=500, **base), self.config)
        long = AnimationModel.for_measurement(HardwareMeasurement(elapsed_us=50_000, **base), self.config)
        self.assertGreater(long.duration_ms, short.duration_ms)
        self.assertGreaterEqual(short.duration_ms, self.config.animation_min_ms)
        self.assertLessEqual(long.duration_ms, self.config.animation_max_ms)


class StandParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = StandConfig.load(DEFAULT_CONFIG_PATH)

    def mission_payload(self):
        return {
            "scenario": "PQC",
            "profile": "BASELINE",
            "cpu_mhz": "240",
            "cipher": "AES-128-GCM",
            "result": "DELIVERED",
            "elapsed_us": "14152",
            "bytes_total": "837",
            "bytes_payload": "41",
            "aead_match": "1",
        }

    def test_typed_mission_parser_preserves_raw_values(self):
        parsed = parse_mission_response(
            f"MISSION PQC {self.config.payload_hex}",
            self.mission_payload(),
            scenario="PQC",
            profile="BASELINE",
            profile_mhz=240,
            payload_hex=self.config.payload_hex,
            source="hardware-live",
        )
        self.assertIsInstance(parsed, HardwareMeasurement)
        self.assertEqual(parsed.elapsed_us, 14152)
        self.assertEqual(parsed.bytes_total, 837)
        self.assertEqual(parsed.source, "hardware-live")

    def test_mission_parser_rejects_wrong_cipher_and_incomplete_fields(self):
        payload = self.mission_payload()
        payload["cipher"] = "AES-256-GCM"
        with self.assertRaisesRegex(StandProtocolError, "cifra inesperada"):
            parse_mission_response(
                "MISSION PQC",
                payload,
                scenario="PQC",
                profile="BASELINE",
                profile_mhz=240,
                payload_hex=self.config.payload_hex,
                source="hardware-live",
            )
        payload = self.mission_payload()
        del payload["elapsed_us"]
        with self.assertRaisesRegex(StandProtocolError, "elapsed_us"):
            parse_mission_response(
                "MISSION PQC",
                payload,
                scenario="PQC",
                profile="BASELINE",
                profile_mhz=240,
                payload_hex=self.config.payload_hex,
                source="hardware-live",
            )

    def test_fault_parser_proves_xor_and_expected_outcome(self):
        selection = FaultSelection(0, 1, 0, 0)
        parsed = parse_fault_response(
            "FAULT CRC32 ...",
            {
                "guard": "CRC32",
                "result": "DETECTED_GUARD",
                "byte_index": "0",
                "bit_mask": "0x01",
                "before_byte": "0x50",
                "after_byte": "0x51",
                "crc_before": "0xD0997249",
                "crc_after": "0xBE156908",
                "elapsed_us": "13",
            },
            expected_guard="CRC32",
            selection=selection,
            source="hardware-live",
        )
        self.assertEqual(parsed.after_byte, parsed.before_byte ^ parsed.bit_mask)

    def test_fault_parser_rejects_a_different_second_fault(self):
        selection = FaultSelection(0, 1, 0, 0)
        with self.assertRaisesRegex(StandProtocolError, "alterou a falha"):
            parse_fault_response(
                "FAULT CRC32 ...",
                {
                    "guard": "CRC32",
                    "result": "DETECTED_GUARD",
                    "byte_index": "1",
                    "bit_mask": "0x01",
                    "before_byte": "0x51",
                    "after_byte": "0x50",
                    "crc_before": "0x1",
                    "crc_after": "0x2",
                    "elapsed_us": "13",
                },
                expected_guard="CRC32",
                selection=selection,
                source="hardware-live",
            )


class StandControllerTests(unittest.TestCase):
    def test_complete_fixture_flow_uses_same_payload_and_same_fault(self):
        flow = FastStandFlow()
        controller = flow.complete()
        self.assertEqual(controller.state, DemoState.SUMMARY)
        self.assertEqual(controller.completed_cycles, 1)
        mission_commands = [command for command in flow.sent if command.startswith("MISSION ")]
        self.assertEqual(len(mission_commands), 3)
        self.assertEqual({command.split()[2] for command in mission_commands}, {flow.config.payload_hex})
        fault_commands = [command for command in flow.sent if command.startswith("FAULT ")]
        self.assertEqual(len(fault_commands), 2)
        self.assertEqual(fault_commands[0].split()[2:], fault_commands[1].split()[2:])
        self.assertEqual(controller.fault_results["NONE"].result, "SILENT")
        self.assertEqual(controller.fault_results["CRC32"].result, "DETECTED_GUARD")
        self.assertEqual(controller.measurements["PQC_240"].bytes_total, controller.measurements["PQC_80"].bytes_total)

    def test_fixture_measurements_are_never_labelled_live(self):
        flow = FastStandFlow()
        controller = flow.complete()
        self.assertIn("SIMULADO", controller.persistent_mode_label)
        self.assertIn("CAMPANHA OFICIAL", controller.measurement_source_label)
        self.assertTrue(all(value.source == "official-campaign-fixture" for value in controller.measurements.values()))

    def test_button_debounce_blocks_duplicate_start(self):
        flow = FastStandFlow()
        self.assertTrue(flow.controller.handle_button(now=1.0, origin="test"))
        self.assertFalse(flow.controller.handle_button(now=1.001, origin="test"))
        self.assertEqual(flow.controller.state, DemoState.INTRO)
        self.assertEqual(flow.sent, [])

    def test_out_of_order_response_enters_safe_error_state(self):
        sent = []
        config = replace(StandConfig.load(DEFAULT_CONFIG_PATH), intro_seconds=0.01)
        controller = StandController(config, lambda command, **kwargs: sent.append(command), mode="hardware", now=0)
        controller.connected = True
        controller.handshake_ok = True
        controller.handle_button(now=0.1, origin="test")
        controller.update(now=0.2)
        self.assertTrue(sent[0].startswith("PROFILE BASELINE"))
        controller.handle_serial_event(
            "response",
            {"command": "MISSION PQC", "status": "OK", "payload": {}},
            now=0.21,
        )
        self.assertEqual(controller.state, DemoState.ERROR)
        self.assertGreater(controller.rejected_events, 0)

    def test_serial_timeout_has_recovery_screen_and_no_fabricated_metrics(self):
        sent = []
        config = replace(StandConfig.load(DEFAULT_CONFIG_PATH), intro_seconds=0.01, serial_timeout_seconds=0.05)
        controller = StandController(config, lambda command, **kwargs: sent.append(command), mode="hardware", now=0)
        controller.connected = True
        controller.handshake_ok = True
        controller.handle_button(now=0.1, origin="test")
        controller.update(now=0.2)
        controller.update(now=0.3)
        self.assertEqual(controller.state, DemoState.ERROR)
        self.assertIn("timeout", controller.error_message)
        self.assertEqual(controller.measurements, {})

    def test_auto_reset_clears_only_visual_cycle_data(self):
        flow = FastStandFlow()
        controller = flow.complete()
        completed = controller.completed_cycles
        controller.update(now=1.0)
        flow.pump(1.0)
        self.assertEqual(controller.state, DemoState.ATTRACT)
        self.assertEqual(controller.measurements, {})
        self.assertEqual(controller.fault_results, {})
        self.assertEqual(controller.completed_cycles, completed)

    def test_disconnect_during_cycle_stops_live_flow(self):
        flow = FastStandFlow()
        flow.controller.handle_button(now=0.1, origin="test")
        flow.controller.handle_serial_event("state", {"connected": False, "status": "USB removido"}, now=0.2)
        self.assertEqual(flow.controller.state, DemoState.ERROR)
        self.assertIn("desconectada", flow.controller.error_message)
        self.assertFalse(flow.controller.ready)
        self.assertEqual(flow.controller.handshake, {})

    def test_reconnect_requires_a_fresh_handshake(self):
        flow = FastStandFlow()
        flow.controller.reset_to_attract(reason="test_restore", now=0.05)
        self.assertIsNotNone(flow.controller.pending)
        flow.controller.handle_serial_event("state", {"connected": False, "status": "USB removido"}, now=0.1)
        self.assertIsNone(flow.controller.pending)
        flow.controller.handle_serial_event("state", {"connected": True, "status": "USB reconectado"}, now=0.2)
        self.assertFalse(flow.controller.ready)
        self.assertFalse(flow.controller.handle_button(now=0.3, origin="test"))


class StandLoggingAndRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def test_session_log_records_provenance_without_personal_input(self):
        config = StandConfig.load(DEFAULT_CONFIG_PATH)
        with tempfile.TemporaryDirectory() as directory:
            logger = StandSessionLogger(directory, mode="simulated", config=config, fixture_source="official fixture")
            logger.write("test_event", command="MISSION PQC")
            path = logger.path
            logger.close()
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["event"], "session_start")
            self.assertEqual(records[0]["mode"], "simulated")
            self.assertEqual(records[1]["command"], "MISSION PQC")
            self.assertEqual(records[-1]["event"], "session_end")

    def test_every_state_renders_at_required_resolutions(self):
        flow = FastStandFlow()
        controller = flow.complete()
        renderer = StandRenderer()
        for state in DemoState:
            controller.state = state
            if state == DemoState.ERROR:
                controller.error_message = "timeout de teste"
            frame = renderer.render(controller, now=1.0, diagnostic=True)
            self.assertEqual(frame.get_size(), (1366, 768))
            for resolution in ((1366, 768), (1920, 1080)):
                scaled = pygame.transform.smoothscale(frame, resolution)
                self.assertEqual(scaled.get_size(), resolution)


class StandAcceptanceValidatorTests(unittest.TestCase):
    def test_disconnect_gate_counts_only_a_later_recovery(self):
        records = [
            {"event": "connection", "session_id": "a", "connected": False},
            {"event": "connection", "session_id": "a", "connected": True},
            {"event": "connection", "session_id": "a", "connected": False},
            {"event": "connection", "session_id": "a", "connected": False},
        ]
        self.assertEqual(count_disconnect_recoveries(records), (1, 0))
        records.append({"event": "connection", "session_id": "a", "connected": True})
        self.assertEqual(count_disconnect_recoveries(records), (1, 1))

    def test_cycle_validator_accepts_only_complete_live_invariants(self):
        flow = FastStandFlow()
        controller = flow.complete()
        measurements = {key: asdict(value) for key, value in controller.measurements.items()}
        faults = {key: asdict(value) for key, value in controller.fault_results.items()}
        for measurement in measurements.values():
            measurement["source"] = "hardware-live"
        for fault in faults.values():
            fault["source"] = "hardware-live"
        record = {
            "measurements": measurements,
            "faults": faults,
            "duration_seconds": 82.0,
        }
        self.assertEqual(validate_cycle(record), [])

    def test_cycle_validator_rejects_fixture_and_changed_second_fault(self):
        flow = FastStandFlow()
        controller = flow.complete()
        measurements = {key: asdict(value) for key, value in controller.measurements.items()}
        faults = {key: asdict(value) for key, value in controller.fault_results.items()}
        faults["CRC32"]["byte_index"] += 1
        errors = validate_cycle({"measurements": measurements, "faults": faults, "duration_seconds": 101.0})
        self.assertTrue(any("não é hardware-live" in error for error in errors))
        self.assertTrue(any("mesma falha" in error for error in errors))
        self.assertTrue(any("100 s" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
