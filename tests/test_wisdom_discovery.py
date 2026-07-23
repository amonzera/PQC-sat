from types import SimpleNamespace
import unittest
from unittest import mock

from pqc_sat.infrastructure.serial_client import WisdomSerialClient
from pqc_sat.infrastructure.wisdom import (
    WisdomFirmwareError,
    candidate_ports,
    discover_wisdom,
    validate_wisdom_handshake,
)
from tools.serial_bridge import PortInfo, SerialBridgeError


def hello_fields(*, game="STAGED_V1", node="PQC-SAT-WISDOM"):
    return (
        f"node={node}",
        "board=BlackBoard-Wisdom",
        "proto=V1",
        f"game={game}",
        "uptime_ms=1234",
    )


class FakeBridge:
    payload_by_port = {}

    def __init__(self, port, **_kwargs):
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def send(self, command, args):
        assert command == "HELLO"
        assert args == []
        payload = self.payload_by_port[self.port]
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(status="OK", payload_fields=payload)


class WisdomDiscoveryTests(unittest.TestCase):
    def test_serial_worker_discovery_uses_explicit_probe_timeout(self):
        client = WisdomSerialClient(
            port="/dev/serial/by-id/wisdom",
            baudrate=115200,
            timeout=12,
            probe_timeout=1.25,
        )
        device = SimpleNamespace(port="/dev/serial/by-id/wisdom")
        with mock.patch(
            "pqc_sat.infrastructure.serial_client.discover_wisdom",
            return_value=device,
        ) as discover:
            self.assertEqual(client._choose_port(), device.port)
        discover.assert_called_once_with(
            "/dev/serial/by-id/wisdom",
            baudrate=115200,
            timeout=1.25,
            require_staged_game=True,
        )

    def test_candidate_list_does_not_depend_on_cp210_metadata(self):
        listed = [
            PortInfo("/dev/ttyS4", "Generic serial", "Unknown"),
            PortInfo("/dev/ttyUSB9", "USB UART", "Vendor"),
        ]
        with mock.patch("pqc_sat.infrastructure.wisdom._linux_fallback_ports", return_value=[]):
            self.assertEqual(candidate_ports(listed_ports=listed), ["/dev/ttyUSB9"])

    def test_discovery_probes_all_ports_and_selects_hello_identity(self):
        FakeBridge.payload_by_port = {
            "/dev/ttyACM0": hello_fields(node="OTHER"),
            "/dev/ttyUSB9": hello_fields(),
        }
        listed = [
            PortInfo("/dev/ttyACM0", "Generic", "Unknown"),
            PortInfo("/dev/ttyUSB9", "Generic", "Unknown"),
        ]
        with mock.patch("pqc_sat.infrastructure.wisdom._linux_fallback_ports", return_value=[]):
            device = discover_wisdom(listed_ports=listed, bridge_factory=FakeBridge)
        self.assertEqual(device.port, "/dev/ttyUSB9")
        self.assertEqual(device.handshake["game"], "STAGED_V1")

    def test_explicit_port_is_still_probed_and_rejects_old_firmware(self):
        FakeBridge.payload_by_port = {"/dev/ttyUSB0": hello_fields(game="")}
        with self.assertRaisesRegex(WisdomFirmwareError, "STAGED_V1"):
            discover_wisdom("/dev/ttyUSB0", bridge_factory=FakeBridge)

    def test_preflash_discovery_accepts_proven_wisdom_without_game_capability(self):
        FakeBridge.payload_by_port = {"/dev/ttyUSB0": hello_fields(game="")}

        device = discover_wisdom(
            "/dev/ttyUSB0",
            bridge_factory=FakeBridge,
            require_staged_game=False,
        )

        self.assertEqual(device.port, "/dev/ttyUSB0")
        self.assertEqual(device.handshake["game"], "")

    def test_builtin_ttys_are_skipped_when_usb_candidate_exists(self):
        listed = [
            PortInfo("/dev/ttyS0", "", ""),
            PortInfo("/dev/ttyS1", "", ""),
            PortInfo("/dev/ttyUSB0", "", ""),
        ]
        with mock.patch("pqc_sat.infrastructure.wisdom._linux_fallback_ports", return_value=[]):
            self.assertEqual(candidate_ports(listed_ports=listed), ["/dev/ttyUSB0"])

    def test_multiple_compatible_boards_require_explicit_port(self):
        FakeBridge.payload_by_port = {
            "/dev/ttyUSB0": hello_fields(),
            "/dev/ttyUSB1": hello_fields(),
        }
        listed = [
            PortInfo("/dev/ttyUSB0", "", ""),
            PortInfo("/dev/ttyUSB1", "", ""),
        ]
        with mock.patch("pqc_sat.infrastructure.wisdom._linux_fallback_ports", return_value=[]):
            with self.assertRaisesRegex(SerialBridgeError, "mais de uma Wisdom"):
                discover_wisdom(listed_ports=listed, bridge_factory=FakeBridge)

    def test_no_serial_candidates_has_actionable_error(self):
        with mock.patch("pqc_sat.infrastructure.wisdom._linux_fallback_ports", return_value=[]):
            with self.assertRaisesRegex(SerialBridgeError, "nenhuma porta serial"):
                discover_wisdom(listed_ports=[], bridge_factory=FakeBridge)

    def test_handshake_requires_valid_uptime(self):
        payload = dict(field.split("=", 1) for field in hello_fields())
        payload["uptime_ms"] = "invalid"
        with self.assertRaisesRegex(SerialBridgeError, "uptime_ms"):
            validate_wisdom_handshake(payload)


if __name__ == "__main__":
    unittest.main()
