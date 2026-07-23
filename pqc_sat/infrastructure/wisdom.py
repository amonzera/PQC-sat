"""Discovery and identity validation for the PQC-SAT BlackBoard Wisdom."""

from __future__ import annotations

from dataclasses import dataclass
import glob
import os
from typing import Callable, Iterable

from tools.serial_bridge import PortInfo, SerialBridge, SerialBridgeError, list_serial_ports
from tools.serial_protocol import ProtocolError, decode_key_values


EXPECTED_NODE = "PQC-SAT-WISDOM"
EXPECTED_BOARD = "BlackBoard-Wisdom"
EXPECTED_PROTOCOL = "V1"
EXPECTED_GAME = "STAGED_V1"
EXPECTED_KEX = "FAIR_V1"
EXPECTED_SESSION_BENCH = "FAIR_SESSION_V1"


@dataclass(frozen=True)
class WisdomDevice:
    """A serial endpoint that proved its identity through ``HELLO``."""

    port: str
    handshake: dict[str, str]


class WisdomFirmwareError(SerialBridgeError):
    """Raised after the board identity is proven but its firmware is incompatible."""


def validate_wisdom_handshake(
    payload: dict[str, str],
    *,
    require_staged_game: bool = True,
    require_fair_kex: bool = True,
    require_session_bench: bool = False,
) -> dict[str, str]:
    """Validate the fields required by the production game."""

    node = payload.get("node", "")
    board = payload.get("board", "")
    protocol = payload.get("proto", "")
    game = payload.get("game", "")
    kex = payload.get("kex", "")
    session_bench = payload.get("session_bench", "")
    if node != EXPECTED_NODE or board != EXPECTED_BOARD:
        raise SerialBridgeError(
            "dispositivo serial não é a Wisdom do PQC-SAT "
            f"(node={node or '-'}, board={board or '-'})"
        )
    if protocol != EXPECTED_PROTOCOL:
        raise WisdomFirmwareError(
            f"firmware incompatível: esperado proto={EXPECTED_PROTOCOL}, recebido proto={protocol or '-'}"
        )
    if require_staged_game and game != EXPECTED_GAME:
        raise WisdomFirmwareError(
            f"firmware sem o jogo por etapas: esperado game={EXPECTED_GAME}, recebido game={game or '-'}"
        )
    if require_fair_kex and kex != EXPECTED_KEX:
        raise WisdomFirmwareError(
            f"firmware sem o experimento justo: esperado kex={EXPECTED_KEX}, recebido kex={kex or '-'}"
        )
    if require_session_bench and session_bench != EXPECTED_SESSION_BENCH:
        raise WisdomFirmwareError(
            "firmware sem o benchmark de sessão: esperado "
            f"session_bench={EXPECTED_SESSION_BENCH}, "
            f"recebido session_bench={session_bench or '-'}"
        )
    try:
        uptime_ms = int(payload.get("uptime_ms", ""), 10)
    except (TypeError, ValueError) as exc:
        raise WisdomFirmwareError("HELLO sem uptime_ms uint32 válido") from exc
    if not 0 <= uptime_ms <= 0xFFFFFFFF:
        raise WisdomFirmwareError("HELLO retornou uptime_ms fora da faixa uint32")
    return dict(payload)


def _linux_fallback_ports() -> list[str]:
    """Find common USB serial nodes even when udev metadata is incomplete."""

    patterns = (
        "/dev/serial/by-id/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    )
    return [path for pattern in patterns for path in sorted(glob.glob(pattern))]


def candidate_ports(
    explicit: str | None = None,
    *,
    listed_ports: Iterable[PortInfo] | None = None,
) -> list[str]:
    """Return de-duplicated candidates without guessing from USB descriptions."""

    if explicit:
        return [explicit]
    if listed_ports is None:
        listed_ports = list_serial_ports()
    listed_ports = list(listed_ports)
    fallback = _linux_fallback_ports()
    raw = [port.device for port in listed_ports]
    raw.extend(fallback)

    metadata_priority = {
        port.device
        for port in listed_ports
        if "cp210" in f"{port.description} {port.manufacturer}".lower()
        or "silicon labs" in f"{port.description} {port.manufacturer}".lower()
    }

    def priority(device: str) -> tuple[int, str]:
        if device.startswith("/dev/serial/by-id/"):
            return (0, device)
        if device in metadata_priority:
            return (1, device)
        if device.startswith(("/dev/ttyUSB", "/dev/ttyACM")):
            return (2, device)
        return (3, device)

    preferred = {
        device
        for device in raw
        if device.startswith(("/dev/serial/by-id/", "/dev/ttyUSB", "/dev/ttyACM"))
        or device in metadata_priority
        or not device.startswith("/dev/")
    }
    # Built-in ttyS endpoints are extremely common on Linux and usually do not
    # represent USB devices. Probe them only when there is no USB/metadata
    # candidate at all.
    if preferred:
        raw = list(preferred)

    selected: list[str] = []
    canonical_seen: set[str] = set()
    # Prefer stable /dev/serial/by-id aliases when both the alias and ttyUSB
    # node describe the same endpoint.
    ordered = sorted(set(raw), key=priority)
    for device in ordered:
        canonical = os.path.realpath(device)
        if canonical in canonical_seen:
            continue
        canonical_seen.add(canonical)
        selected.append(device)
    return selected


def probe_wisdom(
    port: str,
    *,
    baudrate: int = 115200,
    timeout: float = 2.0,
    bridge_factory: Callable[..., SerialBridge] = SerialBridge,
    require_staged_game: bool = True,
    require_fair_kex: bool = True,
    require_session_bench: bool = False,
) -> WisdomDevice:
    """Open one candidate and accept it only after a valid ``HELLO``."""

    with bridge_factory(port, baudrate=baudrate, timeout=timeout) as bridge:
        frame = bridge.send("HELLO", [])
    if frame.status != "OK":
        raise SerialBridgeError(f"HELLO rejeitado em {port}: status={frame.status}")
    try:
        payload = decode_key_values(frame.payload_fields)
    except ProtocolError as exc:
        raise SerialBridgeError(f"HELLO inválido em {port}: resposta sem campos key=value") from exc
    return WisdomDevice(
        port=port,
        handshake=validate_wisdom_handshake(
            payload,
            require_staged_game=require_staged_game,
            require_fair_kex=require_fair_kex,
            require_session_bench=require_session_bench,
        ),
    )


def discover_wisdom(
    explicit: str | None = None,
    *,
    baudrate: int = 115200,
    timeout: float = 2.0,
    listed_ports: Iterable[PortInfo] | None = None,
    bridge_factory: Callable[..., SerialBridge] = SerialBridge,
    require_staged_game: bool = True,
    require_fair_kex: bool = True,
    require_session_bench: bool = False,
) -> WisdomDevice:
    """Probe every candidate and return the single compatible Wisdom."""

    expected_label = (
        "Wisdom STAGED_V1/FAIR_V1/FAIR_SESSION_V1"
        if require_staged_game and require_fair_kex and require_session_bench
        else "Wisdom STAGED_V1/FAIR_V1"
        if require_staged_game and require_fair_kex
        else "Wisdom PQC-SAT"
    )

    candidates = candidate_ports(explicit, listed_ports=listed_ports)
    if not candidates:
        raise SerialBridgeError(
            "nenhuma porta serial encontrada; conecte a BlackBoard Wisdom e verifique /dev/ttyUSB* ou /dev/ttyACM*"
        )

    compatible: list[WisdomDevice] = []
    failures: list[str] = []
    firmware_failures: list[str] = []
    for port in candidates:
        try:
            compatible.append(
                probe_wisdom(
                    port,
                    baudrate=baudrate,
                    timeout=timeout,
                    bridge_factory=bridge_factory,
                    require_staged_game=require_staged_game,
                    require_fair_kex=require_fair_kex,
                    require_session_bench=require_session_bench,
                )
            )
        except WisdomFirmwareError as exc:
            firmware_failures.append(f"{port}: {exc}")
        except (OSError, SerialBridgeError) as exc:
            failures.append(f"{port}: {exc}")

    if len(compatible) == 1:
        return compatible[0]
    if len(compatible) > 1:
        ports = ", ".join(device.port for device in compatible)
        raise SerialBridgeError(f"mais de uma Wisdom compatível encontrada ({ports}); informe --port")

    if firmware_failures:
        detail = "; ".join(firmware_failures)
        purpose = "não atende ao jogo" if require_staged_game else "é incompatível com o protocolo de upload"
        raise WisdomFirmwareError(f"Wisdom reconhecida, mas o firmware {purpose}: {detail}")

    detail = "; ".join(failures)
    if explicit:
        raise SerialBridgeError(f"a porta {explicit} não confirmou uma {expected_label}: {detail}")
    raise SerialBridgeError(
        f"nenhuma {expected_label} respondeu ao HELLO"
        + (f"; sondagens: {detail}" if detail else "")
    )


__all__ = (
    "EXPECTED_BOARD",
    "EXPECTED_GAME",
    "EXPECTED_KEX",
    "EXPECTED_NODE",
    "EXPECTED_PROTOCOL",
    "WisdomDevice",
    "WisdomFirmwareError",
    "candidate_ports",
    "discover_wisdom",
    "probe_wisdom",
    "validate_wisdom_handshake",
)
