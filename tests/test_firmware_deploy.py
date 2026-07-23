import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import firmware_deploy


class FirmwareDeployTests(unittest.TestCase):
    def test_platformio_invocation_is_python_argv_without_shell(self):
        command = firmware_deploy.platformio_command(
            "-t",
            "upload",
            "--upload-port",
            "/dev/serial/by-id/wisdom",
        )

        self.assertEqual(command[:3], [sys.executable, "-m", "platformio"])
        self.assertEqual(command[-4:], ["-t", "upload", "--upload-port", "/dev/serial/by-id/wisdom"])

    def test_default_mode_builds_but_never_discovers_or_uploads(self):
        with mock.patch.object(firmware_deploy, "run_platformio", return_value=0) as run:
            with mock.patch.object(firmware_deploy, "artifact_summary", return_value=(123, "abc")):
                with mock.patch.object(firmware_deploy, "discover_wisdom") as discover:
                    with contextlib.redirect_stdout(io.StringIO()):
                        status = firmware_deploy.main([])

        self.assertEqual(status, 0)
        run.assert_called_once_with()
        discover.assert_not_called()

    def test_upload_requires_proven_wisdom_identity_before_build(self):
        with mock.patch.object(
            firmware_deploy,
            "discover_wisdom",
            side_effect=firmware_deploy.SerialBridgeError("dispositivo errado"),
        ):
            with mock.patch.object(firmware_deploy, "run_platformio") as run:
                with contextlib.redirect_stderr(io.StringIO()):
                    status = firmware_deploy.main(["--upload", "--port", "/dev/ttyUSB9"])

        self.assertEqual(status, 2)
        run.assert_not_called()

    def test_compiled_artifact_summary_uses_real_bytes(self):
        with mock.patch.object(Path, "read_bytes", return_value=b"firmware"):
            size, digest = firmware_deploy.artifact_summary(Path("firmware.bin"))

        self.assertEqual(size, 8)
        self.assertEqual(len(digest), 64)

    def test_directory_hash_binds_names_and_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "src").mkdir()
            (root / "src" / "a.h").write_text("one", encoding="utf-8")
            count, first = firmware_deploy.directory_sha256(root)
            (root / "src" / "a.h").write_text("two", encoding="utf-8")
            changed_count, second = firmware_deploy.directory_sha256(root)

        self.assertEqual(count, 1)
        self.assertEqual(changed_count, 1)
        self.assertNotEqual(first, second)

    def test_successful_upload_writes_verified_manifest(self):
        before = SimpleNamespace(
            port="/dev/ttyUSB9",
            handshake={
                "node": "PQC-SAT-WISDOM",
                "proto": "V1",
                "game": "OLD",
                "kex": "LEGACY_ONLY",
            },
        )
        after = SimpleNamespace(
            port="/dev/ttyUSB9",
            handshake={
                "node": "PQC-SAT-WISDOM",
                "proto": "V1",
                "game": "STAGED_V1",
                "kex": "FAIR_V1",
                "session_bench": "FAIR_SESSION_V1",
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "deploy.json"
            with mock.patch.object(firmware_deploy, "discover_wisdom", return_value=before):
                with mock.patch.object(firmware_deploy, "run_platformio", side_effect=[0, 0]):
                    with mock.patch.object(
                        firmware_deploy,
                        "artifact_summary",
                        return_value=(123, "a" * 64),
                    ):
                        with mock.patch.object(
                            firmware_deploy,
                            "wait_for_staged_firmware",
                            return_value=after,
                        ):
                            with mock.patch.object(
                                firmware_deploy,
                                "write_deployment_manifest",
                                return_value=manifest_path,
                            ) as write_manifest:
                                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                                    status = firmware_deploy.main(
                                        ["--upload", "--port", "/dev/ttyUSB9"]
                                    )

        self.assertEqual(status, 0)
        write_manifest.assert_called_once()
        self.assertIn(f"firmware_deploy_manifest={manifest_path}", stdout.getvalue())

    def test_manifest_contains_hashes_and_both_handshakes(self):
        handshake = {
            "node": "PQC-SAT-WISDOM",
            "game": "STAGED_V1",
            "kex": "FAIR_V1",
            "session_bench": "FAIR_SESSION_V1",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                firmware_deploy,
                "git_metadata",
                return_value=("f" * 40, True),
            ):
                with mock.patch.object(
                    firmware_deploy,
                    "wolfssl_provenance",
                    return_value={
                        "path": "firmware/lib/wolfssl",
                        "expected_version": "5.9.2",
                        "expected_upstream_commit": "a" * 40,
                        "file_count": 123,
                        "tree_sha256": "b" * 64,
                    },
                ):
                    path = firmware_deploy.write_deployment_manifest(
                        output_dir=Path(temp_dir),
                        firmware_size=321,
                        firmware_sha256="a" * 64,
                        port="/dev/ttyUSB9",
                        baudrate=115200,
                        pre_upload_handshake={"node": "PQC-SAT-WISDOM"},
                        post_upload_handshake=handshake,
                    )
            document = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(document["schema_version"], "pqc-sat-firmware-deploy-v1")
        self.assertEqual(document["firmware_sha256"], "a" * 64)
        self.assertTrue(document["uploaded"])
        self.assertTrue(document["verified"])
        self.assertEqual(document["post_upload_handshake"]["session_bench"], "FAIR_SESSION_V1")
        self.assertIn("firmware/esp32_serial_spike/user_settings.h", document["source_sha256"])
        self.assertEqual(
            document["dependency_provenance"]["wolfssl"]["tree_sha256"],
            "b" * 64,
        )


if __name__ == "__main__":
    unittest.main()
