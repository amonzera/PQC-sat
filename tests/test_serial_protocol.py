import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from tools import aes_gcm_metrics_battery
from tools import final_metrics_battery
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
from tools.serial_commands import (
    DEMO_FIRMWARE_COMMAND_NAMES,
    FIRMWARE_COMMAND_NAMES,
    command_help_lines,
    is_demo_firmware_command,
)


class SerialProtocolTests(unittest.TestCase):
    def test_serial_bridge_can_run_as_direct_script(self):
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "tools/serial_bridge.py"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

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
        self.assertIn("LED WHITE|RED|GREEN|BLUE|CYAN|MAGENTA|YELLOW|OFF", rendered)
        self.assertNotIn("YELLOW|OFF muda", rendered)
        self.assertIn("      muda a cor do indicador principal", rendered)
        full_rendered = "\n".join(command_help_lines(demo_only=False))
        self.assertIn("OLED INIT|CLEAR|TEST|STANDBY", full_rendered)
        self.assertIn("MISSION CLASSIC|PQC|PQC_CRC32", full_rendered)

    def test_dashboard_led_effect_commands_are_known(self):
        for command in ("LED YELLOW", "LED MAGENTA", "LED GREEN", "LED RED", "LED BLUE"):
            self.assertTrue(is_demo_firmware_command(command), command)

    def test_pqc_bench_commands_are_full_catalog_only(self):
        for command_name in ("PQC_INFO", "PQC_KAT", "PQC_KEYGEN", "PQC_ENCAP", "PQC_DECAP", "PQC_FAULT", "PQC_BENCH"):
            self.assertIn(command_name, FIRMWARE_COMMAND_NAMES)
            self.assertNotIn(command_name, DEMO_FIRMWARE_COMMAND_NAMES)
        self.assertIn("STRESS", FIRMWARE_COMMAND_NAMES)
        self.assertNotIn("STRESS", DEMO_FIRMWARE_COMMAND_NAMES)

        full_rendered = "\n".join(command_help_lines(demo_only=False))
        demo_rendered = "\n".join(command_help_lines())
        self.assertIn("PQC_INFO", full_rendered)
        self.assertIn("PQC_FAULT", full_rendered)
        self.assertIn("STRESS PQC_LOOP n CONFIRM", full_rendered)
        self.assertNotIn("PQC_INFO", demo_rendered)
        self.assertNotIn("PQC_FAULT", demo_rendered)
        self.assertNotIn("STRESS PQC_LOOP", demo_rendered)

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

    def test_final_metrics_battery_plans_balanced_profiles(self):
        args = mock.Mock(
            profiles=["BASELINE"],
            cycles=2,
            bench_repeats=1,
            bench_rounds=5,
            fault_payload_hex=final_metrics_battery.DEFAULT_FAULT_PAYLOAD_HEX,
        )

        plan = final_metrics_battery.planned_commands(args)
        commands = [command for command, _phase, _profile in plan]

        self.assertIn("PROFILE BASELINE", commands)
        self.assertEqual(commands.count("MISSION CLASSIC"), 2)
        self.assertEqual(commands.count("MISSION PQC"), 2)
        self.assertEqual(commands.count("MISSION PQC_CRC32"), 2)
        self.assertEqual(commands.count("PQC_BENCH 5"), 1)
        self.assertEqual(sum(command.startswith("FAULT NONE ") for command in commands), 2)
        self.assertEqual(sum(command.startswith("FAULT CRC32 ") for command in commands), 2)

    def test_final_metrics_battery_summarizes_presentation_ratios(self):
        records = [
            {
                "ok": True,
                "command": "MISSION CLASSIC",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "result": "DELIVERED",
                    "elapsed_us": "100",
                    "bytes_total": "10",
                    "tag_match": "1",
                },
            },
            {
                "ok": True,
                "command": "MISSION PQC",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "result": "DELIVERED",
                    "elapsed_us": "500",
                    "bytes_total": "50",
                    "key_match": "1",
                    "tag_match": "1",
                },
            },
            {
                "ok": True,
                "command": "MISSION PQC_CRC32",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "result": "DELIVERED",
                    "elapsed_us": "540",
                    "bytes_total": "54",
                    "key_match": "1",
                    "tag_match": "1",
                    "crc_match": "1",
                    "crc_us": "7",
                },
            },
            {
                "ok": True,
                "command": "PQC_BENCH 100",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "ok": "100",
                    "keygen_avg_us": "3300",
                    "encap_avg_us": "3860",
                    "decap_avg_us": "4990",
                },
            },
            {
                "ok": True,
                "command": "FAULT CRC32 5051 0 0x01",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "guard": "CRC32",
                    "result": "DETECTED_GUARD",
                    "elapsed_us": "12",
                },
            },
        ]

        summary = final_metrics_battery.summarize(records, actual_elapsed_s=3.2)

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["mission_runs"], 3)
        self.assertEqual(summary["pqc_bench_runs"], 1)
        self.assertEqual(summary["fault_runs"], 1)
        ratios = summary["mission"]["BASELINE"]["ratios"]
        self.assertEqual(ratios["pqc_vs_classic_elapsed"], 5.0)
        self.assertEqual(ratios["pqc_crc32_vs_classic_bytes"], 5.4)
        self.assertEqual(ratios["crc32_extra_bytes"], 4.0)
        self.assertEqual(ratios["crc32_avg_us"], 7.0)
        faults = summary["faults"]["BASELINE"]["guards"]["CRC32"]["results"]
        self.assertEqual(faults["DETECTED_GUARD"], 1)

    def test_final_metrics_battery_summarizes_payload_hex_missions_by_scenario(self):
        payload_hex = aes_gcm_metrics_battery.DEFAULT_AES_PAYLOAD_HEX
        records = [
            {
                "ok": True,
                "command": f"MISSION CLASSIC {payload_hex}",
                "profile_requested": "BASELINE",
                "payload": {"profile": "BASELINE", "scenario": "CLASSIC", "elapsed_us": "100", "bytes_total": "10"},
            },
            {
                "ok": True,
                "command": f"MISSION PQC {payload_hex}",
                "profile_requested": "BASELINE",
                "payload": {"profile": "BASELINE", "scenario": "PQC", "elapsed_us": "500", "bytes_total": "50"},
            },
            {
                "ok": True,
                "command": f"MISSION PQC_CRC32 {payload_hex}",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "scenario": "PQC_CRC32",
                    "elapsed_us": "540",
                    "bytes_total": "54",
                    "crc_us": "7",
                },
            },
        ]

        summary = final_metrics_battery.summarize(records, actual_elapsed_s=1.0)
        scenarios = summary["mission"]["BASELINE"]["scenarios"]

        self.assertEqual(scenarios["CLASSIC"]["runs"], 1)
        self.assertEqual(scenarios["PQC"]["runs"], 1)
        self.assertEqual(scenarios["PQC_CRC32"]["runs"], 1)
        self.assertEqual(summary["mission"]["BASELINE"]["ratios"]["pqc_vs_classic_elapsed"], 5.0)

    def test_aes_gcm_metrics_battery_plans_fixed_payload_missions(self):
        args = mock.Mock(
            profiles=["BASELINE"],
            cycles=2,
            bench_repeats=1,
            bench_rounds=5,
            payload_hex=aes_gcm_metrics_battery.DEFAULT_AES_PAYLOAD_HEX,
            skip_faults=False,
        )

        plan = aes_gcm_metrics_battery.planned_commands(args)
        commands = [command for command, _phase, _profile in plan]

        self.assertIn("PROFILE BASELINE", commands)
        self.assertEqual(sum(command.startswith("MISSION CLASSIC ") for command in commands), 2)
        self.assertEqual(sum(command.startswith("MISSION PQC ") for command in commands), 2)
        self.assertEqual(sum(command.startswith("MISSION PQC_CRC32 ") for command in commands), 2)
        self.assertTrue(all(aes_gcm_metrics_battery.DEFAULT_AES_PAYLOAD_HEX in command for command in commands if command.startswith("MISSION ")))
        self.assertEqual(commands.count("PQC_BENCH 5"), 1)
        self.assertEqual(sum(command.startswith("FAULT NONE ") for command in commands), 2)
        self.assertEqual(sum(command.startswith("FAULT CRC32 ") for command in commands), 2)

    def test_aes_gcm_metrics_battery_summarizes_aead_fields(self):
        records = []
        for index, nonce_crc in enumerate(("0x11111111", "0x22222222"), 1):
            records.append(
                {
                    "ok": True,
                    "command": "MISSION CLASSIC " + aes_gcm_metrics_battery.DEFAULT_AES_PAYLOAD_HEX,
                    "profile_requested": "BASELINE",
                    "payload": {
                        "profile": "BASELINE",
                        "scenario": "CLASSIC",
                        "result": "DELIVERED",
                        "cipher": "AES-128-GCM",
                        "nonce_bytes": "12",
                        "gcm_tag_bytes": "16",
                        "nonce_crc32": nonce_crc,
                        "ciphertext_crc32": f"0xC{index}",
                        "gcm_tag_crc32": f"0xA{index}",
                        "payload_crc32": "0xPAY",
                        "key_source": "RANDOM_SESSION",
                        "encrypt_us": "20",
                        "decrypt_us": "18",
                        "rng_us": "4",
                        "bytes_ciphertext": "36",
                        "bytes_total": "64",
                        "aead_match": "1",
                        "decrypt_ok": "1",
                        "tag_match": "1",
                    },
                }
            )

        summary = aes_gcm_metrics_battery.summarize_aes_gcm(records)
        checks = summary["checks"]
        classic = summary["profiles"]["BASELINE"]["scenarios"]["CLASSIC"]

        self.assertTrue(checks["official_candidate"])
        self.assertEqual(checks["missing_required_fields"], 0)
        self.assertEqual(checks["non_aes_gcm_records"], 0)
        self.assertEqual(checks["aead_failures"], 0)
        self.assertEqual(classic["cipher_aes_gcm_rate_pct"], 100.0)
        self.assertEqual(classic["nonce_12_bytes_rate_pct"], 100.0)
        self.assertEqual(classic["tag_16_bytes_rate_pct"], 100.0)
        self.assertEqual(classic["aead_match_rate_pct"], 100.0)
        self.assertEqual(classic["nonce_crc32"]["unique"], 2)
        self.assertEqual(classic["ciphertext_crc32"]["unique"], 2)
        self.assertEqual(classic["payload_crc32"]["unique"], 1)

    def test_aes_gcm_metrics_battery_does_not_merge_pqc_and_pqc_crc32(self):
        def record(scenario):
            return {
                "ok": True,
                "command": f"MISSION {scenario} {aes_gcm_metrics_battery.DEFAULT_AES_PAYLOAD_HEX}",
                "profile_requested": "BASELINE",
                "payload": {
                    "profile": "BASELINE",
                    "scenario": scenario,
                    "result": "DELIVERED",
                    "cipher": "AES-128-GCM",
                    "nonce_bytes": "12",
                    "gcm_tag_bytes": "16",
                    "nonce_crc32": f"0x{scenario[-1:] or '0'}1",
                    "ciphertext_crc32": f"0x{scenario[-1:] or '0'}2",
                    "gcm_tag_crc32": f"0x{scenario[-1:] or '0'}3",
                    "encrypt_us": "20",
                    "decrypt_us": "18",
                    "aead_match": "1",
                    "decrypt_ok": "1",
                    "tag_match": "1",
                },
            }

        summary = aes_gcm_metrics_battery.summarize_aes_gcm([record("PQC"), record("PQC_CRC32")])
        scenarios = summary["profiles"]["BASELINE"]["scenarios"]

        self.assertEqual(scenarios["PQC"]["runs"], 1)
        self.assertEqual(scenarios["PQC_CRC32"]["runs"], 1)
        self.assertTrue(summary["checks"]["official_candidate"])


if __name__ == "__main__":
    unittest.main()
