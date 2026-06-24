import contextlib
import io
import unittest
from unittest import mock

from tools import serial_console
from tools import stage8_acceptance
from tools.serial_bridge import SerialBridgeError
from tools.serial_protocol import (
    MAX_FRAME_CHARS,
    ProtocolError,
    build_command,
    build_response,
    decode_key_values,
    parse_frame,
)
from tools.serial_commands import DEMO_FIRMWARE_COMMAND_NAMES, FIRMWARE_COMMAND_NAMES, command_help_lines


class SerialProtocolTests(unittest.TestCase):
    def test_build_command_uppercases_command(self):
        self.assertEqual(build_command(7, "ping"), "V1|7|PING\n")

    def test_build_command_with_arguments(self):
        self.assertEqual(
            build_command("12", "profile", "OBC-1U-LIMITED"),
            "V1|12|PROFILE|OBC-1U-LIMITED\n",
        )

    def test_parse_result_frame(self):
        frame = parse_frame("V1|3|RESULT|OK|pong=1|uptime_ms=42\n")
        self.assertTrue(frame.is_result)
        self.assertEqual(frame.request_id, "3")
        self.assertEqual(frame.status, "OK")
        self.assertEqual(decode_key_values(frame.payload_fields), {"pong": "1", "uptime_ms": "42"})

    def test_parse_event_frame(self):
        frame = parse_frame("V1|0|EVENT|BOOT|node=PQC-SAT-ESP32")
        self.assertFalse(frame.is_result)
        self.assertEqual(frame.message_type, "EVENT")
        self.assertEqual(frame.payload_fields, ("BOOT", "node=PQC-SAT-ESP32"))

    def test_build_response(self):
        self.assertEqual(build_response(9, "ok", "seq=1"), "V1|9|RESULT|OK|seq=1\n")

    def test_rejects_wrong_version(self):
        with self.assertRaises(ProtocolError):
            parse_frame("V2|1|RESULT|OK")

    def test_rejects_empty_field(self):
        with self.assertRaises(ProtocolError):
            parse_frame("V1||PING")

    def test_rejects_separator_in_command_token(self):
        with self.assertRaises(ProtocolError):
            build_command(1, "PIN|G")

    def test_rejects_oversized_frame(self):
        oversized = "V1|1|RESULT|OK|" + ("x" * MAX_FRAME_CHARS)
        with self.assertRaises(ProtocolError):
            parse_frame(oversized)

    def test_rejects_payload_without_key_value(self):
        with self.assertRaises(ProtocolError):
            decode_key_values(("seq=1", "bad_field"))

    def test_command_catalog_includes_help_and_oled(self):
        self.assertIn("HELP", FIRMWARE_COMMAND_NAMES)
        self.assertIn("MISSION", FIRMWARE_COMMAND_NAMES)
        self.assertIn("MISSION", DEMO_FIRMWARE_COMMAND_NAMES)
        lines = command_help_lines()
        rendered = "\n".join(lines)
        self.assertIn("OLED STANDBY", rendered)
        self.assertIn("MISSION PQC_CRC32", rendered)
        full_rendered = "\n".join(command_help_lines(demo_only=False))
        self.assertIn("OLED INIT|CLEAR|TEST|STANDBY", full_rendered)
        self.assertIn("MISSION CLASSIC|PQC|PQC_CRC32", full_rendered)

    def test_pqc_bench_commands_are_full_catalog_only(self):
        for command_name in ("PQC_INFO", "PQC_KAT", "PQC_KEYGEN", "PQC_ENCAP", "PQC_DECAP", "PQC_FAULT", "PQC_BENCH"):
            self.assertIn(command_name, FIRMWARE_COMMAND_NAMES)
            self.assertNotIn(command_name, DEMO_FIRMWARE_COMMAND_NAMES)

        full_rendered = "\n".join(command_help_lines(demo_only=False))
        demo_rendered = "\n".join(command_help_lines())
        self.assertIn("PQC_INFO", full_rendered)
        self.assertIn("PQC_FAULT", full_rendered)
        self.assertNotIn("PQC_INFO", demo_rendered)
        self.assertNotIn("PQC_FAULT", demo_rendered)

    def test_interactive_console_help_is_local_only(self):
        class FakeBridge:
            def __init__(self):
                self.sent = []

            def send(self, command, args):
                self.sent.append((command, args))
                raise AssertionError("HELP local não deve ser enviado à placa")

        bridge = FakeBridge()
        entries = iter(["HELP", "EXIT"])
        with mock.patch("builtins.input", lambda _prompt="": next(entries)):
            with contextlib.redirect_stdout(io.StringIO()):
                serial_console.interactive_loop(bridge)

        self.assertEqual(bridge.sent, [])

    def test_list_ports_without_devices_is_not_a_cli_failure(self):
        with mock.patch("tools.serial_console.list_serial_ports", return_value=[]):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                status = serial_console.print_ports()

        self.assertEqual(status, 0)
        self.assertIn("No serial ports found.", stdout.getvalue())

    def test_stage8_acceptance_reports_missing_port_without_traceback(self):
        with mock.patch("sys.argv", ["stage8_acceptance.py", "--skip-long-run"]):
            with mock.patch("tools.stage8_acceptance.choose_port", side_effect=SerialBridgeError("missing port")):
                with contextlib.redirect_stderr(io.StringIO()) as stderr:
                    status = stage8_acceptance.main()

        self.assertEqual(status, 1)
        self.assertIn("error: missing port", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
