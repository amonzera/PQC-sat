import unittest

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


if __name__ == "__main__":
    unittest.main()
