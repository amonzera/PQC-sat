import contextlib
import io
from pathlib import Path
import sys
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


if __name__ == "__main__":
    unittest.main()
