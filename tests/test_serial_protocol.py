import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from tools import aes_gcm_metrics_battery
from tools import final_metrics_battery
from tools import kex_metrics_battery
from tools import serial_console
from tools import stage8_acceptance
from tools.serial_bridge import SerialBridgeError
from tools.serial_protocol import (
    MAX_COMMAND_CHARS,
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
    def test_fair_firmware_source_uses_one_portable_wolfcrypt_backend(self):
        repo_root = Path(__file__).resolve().parents[1]
        adapter = (
            repo_root / "firmware" / "esp32_serial_spike" / "pqc_sat_fair_crypto.cpp"
        ).read_text(encoding="utf-8")
        settings = (
            repo_root / "firmware" / "esp32_serial_spike" / "user_settings.h"
        ).read_text(encoding="utf-8")
        platformio = (repo_root / "platformio.ini").read_text(encoding="utf-8")

        self.assertIn("wc_ecc_shared_secret", adapter)
        self.assertIn("wc_MlKemKey_Encapsulate", adapter)
        self.assertIn("wc_HKDF", adapter)
        self.assertIn("wc_AesGcmEncrypt", adapter)
        self.assertIn("NO_ESP32_CRYPT", settings)
        self.assertIn("WOLFSSL_NO_ASM", settings)
        self.assertIn("#define SP_WORD_SIZE 32", settings)
        self.assertIn("#define WOLFSSL_HAVE_SP_ECC", settings)
        self.assertIn("requires the portable 32-bit SP ECC backend", adapter)
        self.assertIn("PQC_SAT_ENABLE_FAIR_CRYPTO=1", platformio)
        self.assertIn("robocore_wisdom_esp32_fair", platformio)
        firmware = (
            repo_root / "firmware" / "esp32_serial_spike" / "esp32_serial_spike.ino"
        ).read_text(encoding="utf-8")
        self.assertIn("SESSION_BENCH ECDH|MLKEM 1|100|500|1000 payload_hex", firmware)
        self.assertIn('print_kv("session_bench", FAIR_SESSION_BENCH);', firmware)
        self.assertIn('print_kv_i32("ecdh_rc", ecdh.failure_rc);', firmware)
        self.assertIn('print_kv_i32("mlkem_rc", mlkem.failure_rc);', firmware)
        self.assertIn(
            "print_fair_metadata(staged_game.fair_algorithm, false);",
            firmware,
        )

    def test_fair_bench_validator_requires_zero_algorithm_return_codes(self):
        payload = {
            **kex_metrics_battery.FAIR_COMMON,
            "paired_order": "alternating",
            "n": "1",
            "pairs": "1",
            "ok": "2",
            "ecdh_ok": "1",
            "ecdh_rc": "0",
            "ecdh_setup_avg_us": "10",
            "ecdh_initiator_avg_us": "20",
            "ecdh_responder_avg_us": "30",
            "ecdh_total_avg_us": "60",
            "ecdh_setup_bytes": "65",
            "ecdh_response_bytes": "65",
            "mlkem_ok": "1",
            "mlkem_rc": "0",
            "mlkem_setup_avg_us": "40",
            "mlkem_initiator_avg_us": "50",
            "mlkem_responder_avg_us": "60",
            "mlkem_total_avg_us": "150",
            "mlkem_setup_bytes": "800",
            "mlkem_response_bytes": "768",
            "profile": "BASELINE",
            "cpu_mhz": "240",
            "elapsed_us": "210",
            "heap": "200000",
            "min_heap": "190000",
        }

        self.assertEqual(
            kex_metrics_battery.validate_bench(payload, 1, "BASELINE"),
            [],
        )
        payload["ecdh_rc"] = "-234"
        self.assertIn(
            "código de retorno KEX não é zero",
            kex_metrics_battery.validate_bench(payload, 1, "BASELINE"),
        )

    def test_fair_metrics_plan_is_paired_and_alternates_order(self):
        args = kex_metrics_battery.parse_args(
            [
                "--cycles",
                "2",
                "--session-repeats",
                "2",
                "--message-counts",
                "1",
                "--bench-repeats",
                "1",
                "--bench-rounds",
                "3",
            ]
        )
        steps = kex_metrics_battery.planned_steps(args)
        commands = [step.command for step in steps if step.phase == "mission"]
        sessions = [step for step in steps if step.phase == "session"]

        self.assertEqual(len(commands), 8)
        self.assertIn("MISSION ECDH ", commands[0])
        self.assertIn("MISSION MLKEM ", commands[1])
        self.assertIn("MISSION MLKEM ", commands[2])
        self.assertIn("MISSION ECDH ", commands[3])
        self.assertEqual(len(sessions), 8)
        self.assertEqual(
            [step.scenario for step in sessions[:4]],
            ["ECDH", "MLKEM", "MLKEM", "ECDH"],
        )
        self.assertEqual(
            [step.order_position for step in sessions[:4]],
            [1, 2, 1, 2],
        )

    def test_fair_metrics_only_labels_full_balanced_design_official(self):
        full = kex_metrics_battery.parse_args([])
        smoke = kex_metrics_battery.parse_args(
            ["--cycles", "2", "--bench-repeats", "1", "--bench-rounds", "3"]
        )

        self.assertEqual(kex_metrics_battery.official_design_errors(full), [])
        self.assertTrue(kex_metrics_battery.official_design_errors(smoke))

    def test_official_fair_battery_refuses_missing_manifest_before_serial(self):
        with mock.patch.object(kex_metrics_battery, "discover_wisdom") as discover:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                status = kex_metrics_battery.main([])

        self.assertEqual(status, 2)
        discover.assert_not_called()
        self.assertIn("manifesto do firmware gravado", stderr.getvalue())

    def test_host_parser_accepts_large_fair_metrics_response(self):
        metrics = {f"metric_{index}": "x" * 40 for index in range(40)}
        frame = build_response("fair-large", "OK", metrics)

        self.assertGreater(len(frame), 1024)
        self.assertLess(len(frame), MAX_FRAME_CHARS)
        self.assertEqual(parse_frame(frame).request_id, "fair-large")

    def test_fair_metrics_validator_checks_wire_accounting(self):
        payload = {
            **kex_metrics_battery.FAIR_COMMON,
            **kex_metrics_battery.MISSION_REQUIRED,
            "scenario": "ECDH",
            "kex": "ECDH-P256",
            "bytes_payload": "8",
            "setup_bytes": "65",
            "response_bytes": "65",
            "data_bytes": "40",
            "wire_total_fresh": "170",
            "wire_total_preprovisioned": "105",
            "bytes_total": "170",
            "heap": "200000",
            "min_heap": "190000",
            **{field: "1" for field in kex_metrics_battery.TIMING_FIELDS},
            "kex_total_us": "3",
            "online_us": "9",
            "end_to_end_us": "10",
            "elapsed_us": "10",
        }
        self.assertEqual(kex_metrics_battery.validate_mission(payload, "ECDH", 8), [])
        payload["wire_total_fresh"] = "169"
        self.assertIn(
            "wire_total_fresh não fecha",
            kex_metrics_battery.validate_mission(payload, "ECDH", 8),
        )

    def test_fair_session_validator_checks_time_bytes_and_memory(self):
        payload = {
            **kex_metrics_battery.FAIR_COMMON,
            "session_bench": "FAIR_SESSION_V1",
            "scenario": "ECDH",
            "kex": "ECDH-P256",
            "key_match": "1",
            "aead_match": "1",
            "messages": "100",
            "messages_ok": "100",
            "bytes_payload": "8",
            "setup_us": "10",
            "initiator_us": "20",
            "responder_us": "30",
            "kex_total_us": "60",
            "kdf_us": "5",
            "session_setup_us": "65",
            "rng_total_us": "2",
            "encrypt_total_us": "100",
            "decrypt_total_us": "110",
            "data_total_us": "220",
            "end_to_end_us": "300",
            "amortized_us_per_message": "3",
            "setup_bytes": "65",
            "response_bytes": "65",
            "handshake_bytes": "130",
            "data_bytes_per_message": "36",
            "data_total_bytes": "3600",
            "wire_total_bytes": "3730",
            "amortized_bytes_per_message": "37",
            "heap_before": "200000",
            "heap_after": "199000",
            "heap_delta": "1000",
            "min_heap_before": "190000",
            "min_heap_global": "189000",
            "largest_block_before": "120000",
            "largest_block_after": "119000",
            "stack_hwm_words": "1000",
            "profile": "BASELINE",
            "cpu_mhz": "240",
        }

        self.assertEqual(
            kex_metrics_battery.validate_session(
                payload,
                "ECDH",
                100,
                8,
                "BASELINE",
            ),
            [],
        )
        payload["wire_total_bytes"] = "3729"
        self.assertIn(
            "wire_total_bytes não fecha",
            kex_metrics_battery.validate_session(
                payload,
                "ECDH",
                100,
                8,
                "BASELINE",
            ),
        )

    def test_fair_pair_validator_rejects_missing_order_position(self):
        records = [
            {
                "sequence_index": 1,
                "pair_id": "fresh:BASELINE:001",
                "pair_family": "fresh",
                "scenario_requested": "ECDH",
                "order_position": 1,
                "payload": {},
            },
            {
                "sequence_index": 2,
                "pair_id": "fresh:BASELINE:001",
                "pair_family": "fresh",
                "scenario_requested": "MLKEM",
                "order_position": 1,
                "payload": {},
            },
        ]

        _pairs, errors = kex_metrics_battery._pair_records(records)

        self.assertIn(
            "fresh:BASELINE:001 não contém as posições 1 e 2",
            errors,
        )

    def test_fair_manifest_binds_firmware_sources_port_and_capability(self):
        digest = "a" * 64
        manifest = {
            "schema_version": "pqc-sat-firmware-deploy-v1",
            "platformio_env": "robocore_wisdom_esp32_fair",
            "uploaded": True,
            "verified": True,
            "firmware_sha256": digest,
            "port": "/dev/ttyUSB9",
            "port_realpath": "/dev/ttyUSB9",
            "post_upload_handshake": {
                "game": "STAGED_V1",
                "kex": "FAIR_V1",
                "session_bench": "FAIR_SESSION_V1",
            },
            "source_sha256": {
                str(path.relative_to(kex_metrics_battery.ROOT)): digest
                for path in kex_metrics_battery.SOURCE_PATHS
            },
            "dependency_provenance": {
                "wolfssl": {
                    "expected_version": kex_metrics_battery.WOLFSSL_EXPECTED_VERSION,
                    "expected_upstream_commit": (
                        kex_metrics_battery.WOLFSSL_EXPECTED_UPSTREAM_COMMIT
                    ),
                    "file_count": 12,
                    "tree_sha256": digest,
                }
            },
        }

        with mock.patch.object(
            kex_metrics_battery,
            "file_sha256",
            return_value=digest,
        ):
            with mock.patch.object(
                kex_metrics_battery,
                "directory_sha256",
                return_value=(12, digest),
            ):
                self.assertEqual(
                    kex_metrics_battery.validate_deployment_manifest(
                        manifest,
                        expected_port="/dev/ttyUSB9",
                    ),
                    [],
                )
        manifest["post_upload_handshake"]["session_bench"] = "unavailable"
        with mock.patch.object(
            kex_metrics_battery,
            "file_sha256",
            return_value=digest,
        ):
            with mock.patch.object(
                kex_metrics_battery,
                "directory_sha256",
                return_value=(12, digest),
            ):
                errors = kex_metrics_battery.validate_deployment_manifest(manifest)
        self.assertIn(
            "handshake pós-upload não é STAGED_V1/FAIR_V1/FAIR_SESSION_V1",
            errors,
        )

    def test_staged_firmware_owns_and_clears_shared_mlkem_buffers(self):
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "firmware" / "esp32_serial_spike" / "esp32_serial_spike.ino").read_text(
            encoding="utf-8"
        )

        self.assertIn("is_staged_game_control_command", source)
        self.assertIn("is_staged_game_safe_read_command", source)
        self.assertIn('strcmp(fields[3], "POT") == 0', source)
        self.assertIn("active_GAME_session_requires_GAME_command_HELLO_or_ANALOG_POT", source)
        for buffer_name in (
            "pqc_pk",
            "pqc_sk",
            "pqc_ct",
            "pqc_ss_enc",
            "pqc_ss_dec",
            "pqc_fault_ct",
            "pqc_fault_tag_enc",
            "pqc_fault_tag_dec",
        ):
            self.assertIn(f"secure_wipe({buffer_name}, sizeof({buffer_name}));", source)

    def test_full_diagnostic_samples_a39_inside_the_game(self):
        repo_root = Path(__file__).resolve().parents[1]
        source = (repo_root / "tools" / "stand_diagnostics.py").read_text(encoding="utf-8")

        self.assertIn('"GAME_PROTECT DIAG-GAME",\n                "ANALOG POT",', source)
        self.assertIn('"GAME_TRANSMIT DIAG-GAME A39"', source)
        self.assertIn("fault_selection_from_pot", source)
        self.assertIn('record["purpose"] = "active_game_a39"', source)

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

    def test_rejects_command_larger_than_firmware_input_buffer(self):
        with self.assertRaisesRegex(ProtocolError, str(MAX_COMMAND_CHARS)):
            build_command(1, "MISSION", "x" * MAX_COMMAND_CHARS)

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
        self.assertIn("MISSION ECDH|ECDH_CRC32|MLKEM|MLKEM_CRC32", full_rendered)
        self.assertIn("GAME_BEGIN id profile ECDH|MLKEM|CLASSIC|PQC", full_rendered)
        self.assertIn("KEX_INFO", full_rendered)
        self.assertIn("KEX_BENCH n", full_rendered)
        self.assertIn("SESSION_BENCH ECDH|MLKEM 1|100|500|1000", full_rendered)
        self.assertIn("GAME_RETRY id", full_rendered)
        self.assertTrue(is_demo_firmware_command("MISSION CLASSIC_CRC32"))

    def test_dashboard_led_effect_commands_are_known(self):
        for command in ("LED YELLOW", "LED MAGENTA", "LED GREEN", "LED RED", "LED BLUE"):
            self.assertTrue(is_demo_firmware_command(command), command)

    def test_pqc_bench_commands_are_full_catalog_only(self):
        for command_name in ("PQC_INFO", "PQC_KAT", "PQC_KEYGEN", "PQC_ENCAP", "PQC_DECAP", "PQC_FAULT", "PQC_BENCH"):
            self.assertIn(command_name, FIRMWARE_COMMAND_NAMES)
            self.assertNotIn(command_name, DEMO_FIRMWARE_COMMAND_NAMES)
        self.assertIn("STRESS", FIRMWARE_COMMAND_NAMES)
        self.assertNotIn("STRESS", DEMO_FIRMWARE_COMMAND_NAMES)
        self.assertIn("SESSION_BENCH", FIRMWARE_COMMAND_NAMES)
        self.assertNotIn("SESSION_BENCH", DEMO_FIRMWARE_COMMAND_NAMES)

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

    def test_stage8_acceptance_uses_only_current_fair_measurements(self):
        commands = stage8_acceptance.SMOKE_COMMANDS + stage8_acceptance.LONG_COMMANDS
        measured = [
            command
            for command in commands
            if command.startswith(("MISSION ", "KEX_BENCH ", "SESSION_BENCH "))
        ]

        self.assertTrue(any(command.startswith("MISSION ECDH ") for command in measured))
        self.assertTrue(any(command.startswith("MISSION MLKEM ") for command in measured))
        self.assertTrue(any(command.startswith("SESSION_BENCH ECDH 1 ") for command in measured))
        self.assertTrue(any(command.startswith("SESSION_BENCH MLKEM 1 ") for command in measured))
        self.assertFalse(any("CLASSIC" in command or "PQC_BENCH" in command for command in measured))

    def test_stage8_acceptance_fails_closed_on_invalid_fair_payload(self):
        summary = stage8_acceptance.summarize(
            [{"ok": True, "command": "KEX_INFO", "payload": {}}]
        )

        self.assertFalse(summary["ok"])
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(
            summary["semantic_errors"][0]["error"],
            "profile FAIR ausente ou inválido",
        )

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
