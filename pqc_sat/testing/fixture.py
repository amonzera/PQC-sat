"""Test-only serial-compatible transport backed by official fixture data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import zlib

from pqc_sat.stand.model import (
    FAIR_KEY_MODES,
    GuardMode,
    IncidentScenario,
    KeyMode,
    StandConfig,
    StandConfigError,
    expected_game_outcome,
    scenario_for,
)
from pqc_sat.stand.settings import ROOT


class FixtureSerialClient:
    """Small asynchronous-compatible offline transport backed by official data."""

    def __init__(self, fixture_path: str | Path, config: StandConfig, *, latency_seconds: float = 0.06):
        self.fixture_path = Path(fixture_path)
        try:
            self.fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StandConfigError(f"fixture inválida: {exc}") from exc
        fixture_schema = self.fixture.get("schema_version")
        if fixture_schema not in {
            "pqc-sat-stand-fixture-v1",
            "pqc-sat-stand-fixture-v2",
        }:
            raise StandConfigError("schema da fixture incompatível")
        if fixture_schema == "pqc-sat-stand-fixture-v2" and self.fixture.get("game_protocol") != "STAGED_V1":
            raise StandConfigError("fixture v2 não declara game_protocol=STAGED_V1")
        if not self.fixture.get("official_candidate") or int(self.fixture.get("failed", -1)) != 0:
            raise StandConfigError("fixture não representa campanha oficial aceita")
        if self.fixture.get("payload") != config.payload:
            raise StandConfigError("payload da fixture difere da configuração")
        source_path = ROOT / str(self.fixture.get("source_path", ""))
        source_sha = str(self.fixture.get("source_sha256", "")).lower()
        if len(source_sha) != 64:
            raise StandConfigError("fixture sem SHA-256 de origem")
        if source_path.is_file():
            actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
            if actual_sha != source_sha:
                raise StandConfigError("SHA-256 do log oficial diverge da fixture")
        self.config = config
        self.latency_seconds = max(0.0, latency_seconds)
        self.actual_port = "OFFLINE-FIXTURE"
        self.active_profile = config.baseline_name
        self.pot_value = (config.pot_minimum + config.pot_maximum) // 2
        self._scheduled: list[tuple[float, tuple[str, dict[str, object]]]] = []
        self._running = False
        self._game: dict[str, object] | None = None

    @property
    def source_label(self) -> str:
        model = self.fixture.get("investigation_model")
        suffix = f" model:{model}" if model else ""
        return f"{self.fixture.get('source_path')} sha256:{self.fixture.get('source_sha256')}{suffix}"

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._game = None
        hello = {
            "command": "HELLO",
            "status": "OK",
            "payload": {
                "node": "OFFLINE-FIXTURE",
                "board": "BlackBoard-Wisdom",
                "proto": "V1",
                "uptime_ms": "0",
                "game": "STAGED_V1",
                "kex": "FAIR_V1",
                "crypto_impl": "fixture-historical-proxy",
                "fixture_source": self.fixture.get("source_path"),
                "fixture_sha256": self.fixture.get("source_sha256"),
            },
            "raw_payload": "fixture oficial",
        }
        now = time.monotonic()
        self._scheduled.extend(
            [
                (now, ("response", hello)),
                (now, ("state", {"connected": True, "status": "FIXTURE OFICIAL OFFLINE"})),
            ]
        )

    def stop(self) -> None:
        self._running = False
        self._scheduled.clear()

    def set_pot(self, value: int) -> None:
        self.pot_value = max(self.config.pot_minimum, min(self.config.pot_maximum, int(value)))

    def send(self, command_line: str, *, timeout: float | None = None) -> None:
        del timeout
        command_line = command_line.strip()
        event = self._build_response(command_line)
        self._scheduled.append((time.monotonic() + self.latency_seconds, event))

    def poll(self) -> list[tuple[str, dict[str, object]]]:
        now = time.monotonic()
        ready = [event for due, event in self._scheduled if due <= now]
        self._scheduled = [(due, event) for due, event in self._scheduled if due > now]
        return ready

    def _response(self, command_line: str, payload: dict[str, object]) -> tuple[str, dict[str, object]]:
        return (
            "response",
            {
                "command": command_line.upper(),
                "status": "OK",
                "payload": {key: str(value) for key, value in payload.items()},
                "raw_payload": " ".join(f"{key}={value}" for key, value in payload.items()),
            },
        )

    @staticmethod
    def _status_response(
        command_line: str,
        status: str,
        payload: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        return (
            "response",
            {
                "command": command_line.upper(),
                "status": status,
                "payload": {key: str(value) for key, value in payload.items()},
                "raw_payload": " ".join(f"{key}={value}" for key, value in payload.items()),
            },
        )

    def _bad_game(self, command_line: str, detail: str) -> tuple[str, dict[str, object]]:
        self._game = None
        return self._status_response(
            command_line,
            "ERROR",
            {"code": "BAD_GAME_STATE", "detail": detail, "session_cleared": 1},
        )

    @staticmethod
    def _error(command_line: str, message: str) -> tuple[str, dict[str, object]]:
        return "error", {"command": command_line.upper(), "status": message}

    def _profile_data(self, profile: str) -> dict[str, object]:
        return dict(self.fixture.get("profiles", {}).get(profile, {}))

    def _reference_mission(self, profile: str, key_mode: str) -> dict[str, object]:
        reference_mode = {
            KeyMode.ECDH.value: "CLASSIC",
            KeyMode.MLKEM.value: "PQC",
        }.get(key_mode, key_mode)
        profile_data = self._profile_data(profile)
        mission = dict(profile_data.get("missions", {}).get(reference_mode, {}))
        if mission:
            return mission
        baseline = self._profile_data(self.config.baseline_name)
        mission = dict(baseline.get("missions", {}).get(reference_mode, {}))
        if profile == self.config.limited_name and mission:
            for key in (
                "elapsed_us",
                "keygen_us",
                "encap_us",
                "decap_us",
                "encrypt_us",
                "decrypt_us",
            ):
                if key in mission:
                    mission[key] = max(1, int(mission[key]) * 3)
        return mission

    def _game_common(self, *, stage: str, result: str, elapsed_us: int) -> dict[str, object]:
        assert self._game is not None
        payload = bytes(self._game["payload"])
        key_mode = str(self._game["key_mode"])
        guard = str(self._game["guard"])
        protected_len = len(payload) + (4 if guard == "CRC32" else 0)
        setup_bytes, response_bytes = {
            KeyMode.ECDH.value: (65, 65),
            KeyMode.MLKEM.value: (800, 768),
        }[key_mode]
        data_bytes = protected_len + 12 + 16 + 4
        bytes_total = setup_bytes + response_bytes + data_bytes
        profile = str(self._game["profile"])
        return {
            "game_id": self._game["id"],
            "stage": stage,
            "profile": profile,
            "cpu_mhz": self._profile_data(profile).get(
                "cpu_mhz",
                self.config.baseline_mhz if profile == self.config.baseline_name else self.config.limited_mhz,
            ),
            "key_mode": key_mode,
            "guard": guard,
            "result": result,
            "elapsed_us": max(1, int(elapsed_us)),
            "bytes_payload": len(payload),
            "bytes_total": bytes_total,
            "experiment": "KEX_FAIR_V1",
            "setup_bytes": setup_bytes,
            "response_bytes": response_bytes,
            "data_bytes": data_bytes,
            "heap": 201412,
            "min_heap": 197624,
            "fixture_source": "deterministic-offline-staged-v1",
            "fixture_model": "historical_proxy_not_measurement",
        }

    def _build_response(self, command_line: str) -> tuple[str, dict[str, object]]:
        parts = command_line.split()
        if not parts:
            return self._error(command_line, "comando vazio")
        command = parts[0].upper()
        game_controls = {
            "GAME_BEGIN",
            "GAME_PROTECT",
            "GAME_TRANSMIT",
            "GAME_VERIFY",
            "GAME_RETRY",
            "GAME_END",
            "GAME_ABORT",
        }
        safe_a39_read = command == "ANALOG" and len(parts) == 2 and parts[1].upper() == "POT"
        if (
            self._game is not None
            and command != "HELLO"
            and command not in game_controls
            and not safe_a39_read
        ):
            return self._bad_game(
                command_line,
                "sessão GAME ativa exige continuação GAME_*, HELLO ou ANALOG POT",
            )
        if command == "HELLO" and len(parts) == 1:
            self._game = None
            return self._response(
                command_line,
                {
                    "node": "OFFLINE-FIXTURE",
                    "board": "BlackBoard-Wisdom",
                    "proto": "V1",
                    "uptime_ms": 0,
                    "game": "STAGED_V1",
                    "kex": "FAIR_V1",
                    "session_bench": "FAIR_SESSION_V1",
                    "crypto_impl": "fixture-historical-proxy",
                    "fixture_source": self.fixture.get("source_path"),
                    "fixture_sha256": self.fixture.get("source_sha256"),
                },
            )
        if command == "PROFILE" and len(parts) == 2:
            profile = parts[1].upper()
            profile_data = self.fixture.get("profiles", {}).get(profile)
            if not profile_data:
                return self._error(command_line, "perfil ausente na fixture")
            self.active_profile = profile
            return self._response(command_line, {"profile": profile, "cpu_mhz": profile_data["cpu_mhz"], "radio": "off"})
        if command == "GAME_BEGIN" and len(parts) == 7:
            game_id, profile, key_mode, guard, incident, payload_hex = (
                parts[1],
                parts[2].upper(),
                parts[3].upper(),
                parts[4].upper(),
                parts[5].upper(),
                parts[6].upper(),
            )
            try:
                payload = bytes.fromhex(payload_hex)
                parsed_key_mode = KeyMode(key_mode)
                GuardMode(guard)
                IncidentScenario(incident)
                if (
                    parsed_key_mode not in FAIR_KEY_MODES
                    or
                    not game_id
                    or len(game_id) > 31
                    or any(char in game_id for char in "|\r\n")
                    or not payload
                    or len(payload) > 96
                ):
                    raise ValueError("ID ou payload inválido")
                if profile not in {self.config.baseline_name, self.config.limited_name}:
                    raise ValueError("perfil inválido")
            except ValueError as exc:
                self._game = None
                return self._status_response(
                    command_line,
                    "ERROR",
                    {"code": "BAD_ARGS", "detail": str(exc), "session_cleared": 1},
                )
            self.active_profile = profile
            self._game = {
                "id": game_id,
                "profile": profile,
                "key_mode": key_mode,
                "guard": guard,
                "incident": incident,
                "payload": payload,
                "state": "PREPARE",
            }
            protected = payload + (
                (zlib.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "big") if guard == "CRC32" else b""
            )
            response = self._game_common(stage="PREPARE", result="READY", elapsed_us=70 + len(payload))
            response.update(
                {
                    "bytes_protected": len(protected),
                    "app_crc_present": int(guard == "CRC32"),
                    "app_crc_tx": f"0x{zlib.crc32(payload) & 0xFFFFFFFF:08X}" if guard == "CRC32" else "0x00000000",
                    "payload_crc32": f"0x{zlib.crc32(payload) & 0xFFFFFFFF:08X}",
                }
            )
            return self._response(command_line, response)
        if command.startswith("GAME_"):
            if command == "GAME_ABORT" and len(parts) == 2:
                if self._game is None or parts[1] != self._game.get("id"):
                    return self._bad_game(command_line, "GAME_ABORT com sessão ausente ou ID divergente")
                game_id = str(self._game["id"])
                self._game = None
                self.active_profile = self.config.baseline_name
                return self._response(
                    command_line,
                    {
                        "game_id": game_id,
                        "stage": "ABORT",
                        "session_cleared": 1,
                        "restored_profile": self.config.baseline_name,
                        "restored_mhz": self.config.baseline_mhz,
                    },
                )
            if self._game is None:
                return self._bad_game(command_line, "nenhuma sessão ativa")
            if len(parts) < 2 or parts[1] != self._game.get("id"):
                return self._bad_game(command_line, "ID divergente")
            state = str(self._game["state"])
            game_id = str(self._game["id"])
            payload = bytes(self._game["payload"])
            key_mode = str(self._game["key_mode"])
            guard = str(self._game["guard"])
            incident = IncidentScenario(str(self._game["incident"]))
            reference = self._reference_mission(str(self._game["profile"]), key_mode)
            if command == "GAME_PROTECT" and len(parts) == 2:
                if state != "PREPARE":
                    return self._bad_game(command_line, f"GAME_PROTECT após {state}")
                nonce_crc = zlib.crc32(f"{game_id}|nonce|1".encode()) & 0xFFFFFFFF
                key_crc = zlib.crc32(f"{game_id}|key|1".encode()) & 0xFFFFFFFF
                self._game.update(state="PROTECT", nonce_crc=nonce_crc, key_crc=key_crc)
                setup_bytes, response_bytes = {
                    KeyMode.ECDH.value: (65, 65),
                    KeyMode.MLKEM.value: (800, 768),
                }[key_mode]
                if key_mode == KeyMode.MLKEM.value:
                    setup_us = max(1, int(reference.get("keygen_us", 1)))
                    initiator_us = max(1, int(reference.get("encap_us", 1)))
                    responder_us = max(1, int(reference.get("decap_us", 1)))
                else:
                    proxy_total = max(3, int(reference.get("elapsed_us", 900)))
                    setup_us = max(1, proxy_total * 35 // 100)
                    initiator_us = max(1, proxy_total * 35 // 100)
                    responder_us = max(1, proxy_total - setup_us - initiator_us)
                kex_total_us = setup_us + initiator_us + responder_us
                kdf_us = max(1, kex_total_us // 12)
                response = self._game_common(
                    stage="PROTECT",
                    result="PROTECTED",
                    elapsed_us=kex_total_us + kdf_us + max(1, int(reference.get("encrypt_us", 300))),
                )
                response.update(
                    {
                        "key_match": 1,
                        "aead_ready": 1,
                        "nonce_crc32": f"0x{nonce_crc:08X}",
                        "session_key_crc32": f"0x{key_crc:08X}",
                        "keygen_us": setup_us,
                        "encap_us": initiator_us,
                        "decap_us": responder_us,
                        "setup_us": setup_us,
                        "initiator_us": initiator_us,
                        "responder_us": responder_us,
                        "kex_total_us": kex_total_us,
                        "kdf_us": kdf_us,
                        "setup_bytes": setup_bytes,
                        "response_bytes": response_bytes,
                        "encrypt_us": max(1, int(reference.get("encrypt_us", 300))),
                        "experiment": "KEX_FAIR_V1",
                        "kex": "ECDH-P256" if key_mode == KeyMode.ECDH.value else "ML-KEM-512",
                        "crypto_impl": "wolfCrypt-fixture-proxy",
                        "crypto_version": "fixture-only",
                        "compiler": "8.4.0",
                        "framework": "arduino-esp32-2.0.17",
                        "build_profile": "robocore_wisdom_esp32_fair",
                        "kdf": "HKDF-SHA256",
                        "optimization": "portable-software",
                        "target_asm": 0,
                        "hw_crypto": 0,
                        "authenticated_kex": 0,
                    }
                )
                return self._response(command_line, response)
            if command == "GAME_TRANSMIT" and len(parts) == 4:
                if state != "PROTECT":
                    return self._bad_game(command_line, f"GAME_TRANSMIT após {state}")
                try:
                    byte_index = int(parts[2], 10)
                    bit_mask = int(parts[3], 0)
                    if not 0 <= byte_index < len(payload):
                        raise ValueError("índice fora do payload")
                    if bit_mask <= 0 or bit_mask > 0x80 or bit_mask & (bit_mask - 1):
                        raise ValueError("máscara não é single-bit")
                except ValueError as exc:
                    return self._bad_game(command_line, str(exc))
                wanted = expected_game_outcome(incident, guard)
                frame_tx = zlib.crc32(payload + game_id.encode()) & 0xFFFFFFFF
                frame_rx = frame_tx if wanted["frame_crc_match"] else frame_tx ^ bit_mask
                self._game.update(
                    state="TRANSMIT",
                    byte_index=byte_index,
                    bit_mask=bit_mask,
                    frame_crc_tx=frame_tx,
                    frame_crc_rx=frame_rx,
                )
                response = self._game_common(stage="TRANSMIT", result="IN_FLIGHT", elapsed_us=180)
                response.update(
                    {
                        "byte_index": byte_index,
                        "bit_mask": f"0x{bit_mask:02X}",
                        "frame_crc_tx": f"0x{frame_tx:08X}",
                        "frame_crc_rx": f"0x{frame_rx:08X}",
                        "frame_crc_match": int(bool(wanted["frame_crc_match"])),
                    }
                )
                return self._response(command_line, response)
            if command == "GAME_VERIFY" and len(parts) == 2:
                if state != "TRANSMIT":
                    return self._bad_game(command_line, f"GAME_VERIFY após {state}")
                wanted = expected_game_outcome(incident, guard)
                self._game.update(state="VERIFY", final_result=wanted["result"])
                response = self._game_common(
                    stage="VERIFY",
                    result=str(wanted["result"]),
                    elapsed_us=max(1, int(reference.get("decrypt_us", 150))) + 120,
                )
                response.update(
                    {
                        "byte_index": self._game["byte_index"],
                        "bit_mask": f"0x{int(self._game['bit_mask']):02X}",
                        "frame_crc_match": int(bool(wanted["frame_crc_match"])),
                        "aead_checked": 1,
                        "aead_match": int(bool(wanted["aead_match"])),
                        "app_crc_present": int(bool(wanted["app_crc_present"])),
                        "app_crc_checked": int(bool(wanted["app_crc_checked"])),
                        "app_crc_match": int(bool(wanted["app_crc_match"])),
                        "accepted": int(bool(wanted["accepted"])),
                    }
                )
                return self._response(command_line, response)
            if command == "GAME_RETRY" and len(parts) == 2:
                if state != "VERIFY":
                    return self._bad_game(command_line, f"GAME_RETRY após {state}")
                wanted = expected_game_outcome(IncidentScenario.NORMAL, guard)
                nonce_crc = zlib.crc32(f"{game_id}|nonce|2".encode()) & 0xFFFFFFFF
                key_crc = zlib.crc32(f"{game_id}|key|2".encode()) & 0xFFFFFFFF
                self._game.update(state="RETRY", retry_result="DELIVERED")
                response = self._game_common(
                    stage="RETRY",
                    result="DELIVERED",
                    elapsed_us=max(1, int(reference.get("elapsed_us", 1200))),
                )
                response.update(
                    {
                        "byte_index": self._game["byte_index"],
                        "bit_mask": f"0x{int(self._game['bit_mask']):02X}",
                        "frame_crc_match": int(bool(wanted["frame_crc_match"])),
                        "aead_checked": 1,
                        "aead_match": int(bool(wanted["aead_match"])),
                        "app_crc_present": int(bool(wanted["app_crc_present"])),
                        "app_crc_checked": int(bool(wanted["app_crc_checked"])),
                        "app_crc_match": int(bool(wanted["app_crc_match"])),
                        "accepted": 1,
                        "same_payload": 1,
                        "fresh_key": 1,
                        "fresh_nonce": 1,
                        "nonce_crc32": f"0x{nonce_crc:08X}",
                        "session_key_crc32": f"0x{key_crc:08X}",
                    }
                )
                return self._response(command_line, response)
            if command == "GAME_END" and len(parts) == 3:
                decision = parts[2].upper()
                if state not in {"VERIFY", "RETRY"} or decision not in {"ACCEPT", "SAFE_MODE"}:
                    return self._bad_game(command_line, f"GAME_END inválido após {state}")
                final_result = "DELIVERED" if state == "RETRY" else str(self._game.get("final_result"))
                self._game = None
                self.active_profile = self.config.baseline_name
                return self._response(
                    command_line,
                    {
                        "game_id": game_id,
                        "stage": "END",
                        "decision": decision,
                        "final_result": final_result,
                        "session_cleared": 1,
                        "restored_profile": self.config.baseline_name,
                        "restored_mhz": self.config.baseline_mhz,
                    },
                )
            return self._bad_game(command_line, f"ordem ou argumentos inválidos para {command}")
        if command == "MISSION" and len(parts) == 3:
            scenario, payload_hex = parts[1].upper(), parts[2].upper()
            if payload_hex != self.config.payload_hex:
                return self._error(command_line, "payload difere da campanha oficial")
            profile_data = self.fixture.get("profiles", {}).get(self.active_profile, {})
            reference_scenario = {
                "ECDH": "CLASSIC",
                "ECDH_CRC32": "CLASSIC",
                "MLKEM": "PQC",
                "MLKEM_CRC32": "PQC",
                "PQC_CRC32": "PQC",
                "CLASSIC_CRC32": "CLASSIC",
            }.get(scenario, scenario)
            mission = profile_data.get("missions", {}).get(reference_scenario)
            if not mission:
                mission = self._reference_mission(
                    self.active_profile,
                    "MLKEM" if scenario.startswith(("MLKEM", "PQC")) else "ECDH",
                )
            if not mission:
                return self._error(command_line, "cenário ausente na fixture")
            payload = {
                **mission,
                "scenario": scenario,
                "checksum": "CRC32" if scenario.endswith("CRC32") else "NONE",
                "bytes_checksum": 4 if scenario.endswith("CRC32") else 0,
                "bytes_total": int(mission.get("bytes_total", 0)) + (4 if scenario.endswith("CRC32") else 0),
                "profile": self.active_profile,
                "cpu_mhz": profile_data["cpu_mhz"],
                "fixture_source": self.fixture.get("source_path"),
                "fixture_sha256": self.fixture.get("source_sha256"),
                "fixture_model": "historical_proxy_not_measurement",
            }
            return self._response(command_line, payload)
        if command == "INVESTIGATE" and len(parts) == 7:
            scenario = parts[1].upper()
            incident = parts[2].upper()
            incident_id = parts[6]
            if scenario not in {"CLASSIC", "CLASSIC_CRC32", "PQC", "PQC_CRC32"}:
                return self._error(command_line, "cenário investigativo inválido")
            if incident not in {"NORMAL", "CHANNEL_BITFLIP", "TAMPER", "RX_MEMORY"}:
                return self._error(command_line, "incidente inválido")
            try:
                message = bytearray.fromhex(parts[3])
                byte_index = int(parts[4], 10)
                bit_mask = int(parts[5], 0)
                if not message or len(message) > 96 or not 0 <= byte_index < len(message):
                    raise ValueError("payload ou índice inválido")
                if bit_mask <= 0 or bit_mask > 0x80 or bit_mask & (bit_mask - 1):
                    raise ValueError("máscara não é single-bit")
            except ValueError as exc:
                return self._error(command_line, str(exc))

            use_pqc = scenario.startswith("PQC")
            use_app_crc = scenario.endswith("CRC32")
            before = message[byte_index]
            after = before if incident == "NORMAL" else before ^ bit_mask
            protected = bytes(message)
            if use_app_crc:
                protected += (zlib.crc32(message) & 0xFFFFFFFF).to_bytes(4, "big")
            pseudo_packet = bytearray(scenario.encode("ascii") + protected)
            packet_index = min(len(pseudo_packet) - 1, len(scenario) + byte_index)
            frame_crc_tx = zlib.crc32(pseudo_packet) & 0xFFFFFFFF
            frame_crc_rx = frame_crc_tx
            frame_match = True
            aead_match = True
            app_checked = use_app_crc
            app_match = use_app_crc
            accepted = True
            result = "DELIVERED"
            if incident == "CHANNEL_BITFLIP":
                pseudo_packet[packet_index] ^= bit_mask
                frame_crc_rx = zlib.crc32(pseudo_packet) & 0xFFFFFFFF
                frame_match = False
                aead_match = False
                app_checked = False
                app_match = False
                accepted = False
                result = "FRAME_REJECT"
            elif incident == "TAMPER":
                pseudo_packet[packet_index] ^= bit_mask
                frame_crc_tx = zlib.crc32(pseudo_packet) & 0xFFFFFFFF
                frame_crc_rx = frame_crc_tx
                aead_match = False
                app_checked = False
                app_match = False
                accepted = False
                result = "AUTH_REJECT"
            elif incident == "RX_MEMORY":
                app_match = False
                accepted = not use_app_crc
                result = "APP_REJECT" if use_app_crc else "SILENT_CORRUPTION"

            profile_data = self.fixture.get("profiles", {}).get(self.active_profile, {})
            reference_scenario = "PQC" if use_pqc else "CLASSIC"
            reference = profile_data.get("missions", {}).get(reference_scenario, {})
            elapsed_us = max(1, int(reference.get("elapsed_us", 1000)) + (32 if use_app_crc else 0))
            bytes_total = len(message) + 28 + (768 if use_pqc else 0) + (4 if use_app_crc else 0) + 4
            return self._response(
                command_line,
                {
                    "scenario": scenario,
                    "profile": self.active_profile,
                    "cpu_mhz": profile_data.get("cpu_mhz", 0),
                    "cipher": "AES-128-GCM",
                    "incident_id": incident_id,
                    "incident": incident,
                    "byte_index": byte_index,
                    "bit_mask": f"0x{bit_mask:02X}",
                    "before_byte": f"0x{before:02X}",
                    "after_byte": f"0x{after:02X}",
                    "frame_crc_tx": f"0x{frame_crc_tx:08X}",
                    "frame_crc_rx": f"0x{frame_crc_rx:08X}",
                    "frame_crc_match": int(frame_match),
                    "key_match": 1,
                    "aead_checked": 1,
                    "aead_match": int(aead_match),
                    "app_crc_present": int(use_app_crc),
                    "app_crc_checked": int(app_checked),
                    "app_crc_match": int(app_match),
                    "accepted": int(accepted),
                    "result": result,
                    "elapsed_us": elapsed_us,
                    "bytes_payload": len(message),
                    "bytes_total": bytes_total,
                    "heap": int(reference.get("heap", 201412)),
                    "min_heap": int(reference.get("min_heap", 197624)),
                    "fixture_source": "deterministic-offline-model",
                },
            )
        if command == "ANALOG" and len(parts) == 2 and parts[1].upper() == "POT":
            return self._response(command_line, {"pot": self.pot_value})
        if command == "FAULT" and len(parts) == 5:
            guard = parts[1].upper()
            try:
                payload = bytearray.fromhex(parts[2])
                byte_index = int(parts[3], 10)
                bit_mask = int(parts[4], 0)
                if not 0 <= byte_index < len(payload):
                    raise ValueError("índice fora do payload")
                if bit_mask <= 0 or bit_mask > 0x80 or bit_mask & (bit_mask - 1):
                    raise ValueError("máscara não é single-bit")
            except ValueError as exc:
                return self._error(command_line, str(exc))
            before = payload[byte_index]
            crc_before = zlib.crc32(payload) & 0xFFFFFFFF
            payload[byte_index] ^= bit_mask
            after = payload[byte_index]
            crc_after = zlib.crc32(payload) & 0xFFFFFFFF
            result = "DETECTED_GUARD" if guard == "CRC32" else "SILENT"
            return self._response(
                command_line,
                {
                    "result": result,
                    "guard": guard,
                    "payload_len": len(payload),
                    "byte_index": byte_index,
                    "bit_mask": f"0x{bit_mask:02X}",
                    "before_byte": f"0x{before:02X}",
                    "after_byte": f"0x{after:02X}",
                    "crc_before": f"0x{crc_before:08X}",
                    "crc_after": f"0x{crc_after:08X}",
                    "elapsed_us": 0,
                    "fixture_source": "deterministic-offline-model",
                },
            )
        if command == "STATUS":
            profile_data = self.fixture.get("profiles", {}).get(self.active_profile, {})
            return self._response(
                command_line,
                {
                    "profile": self.active_profile,
                    "cpu_mhz": profile_data.get("cpu_mhz", 0),
                    "pqc": "fixture",
                    "pqc_target": "ML-KEM-512",
                },
            )
        return self._error(command_line, "comando não disponível na fixture")

__all__ = ("FixtureSerialClient",)
