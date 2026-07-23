#!/usr/bin/env python3
"""Operator-run FAIR_V1 battery for fresh and amortized ECDH/ML-KEM sessions."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""}:
    sys.path.insert(0, str(ROOT))

from pqc_sat.infrastructure.wisdom import discover_wisdom  # noqa: E402
from tools.final_metrics_battery import (  # noqa: E402
    DEFAULT_LOG_DIR,
    DEFAULT_PROFILES,
    payload_of,
    profile_of,
    send_record,
    stats,
    utc_now_iso,
    write_document,
)
from tools.firmware_deploy import (  # noqa: E402
    DEPLOY_SCHEMA,
    FIRMWARE_BIN,
    PLATFORMIO_ENV,
    SOURCE_PATHS,
    WOLFSSL_EXPECTED_UPSTREAM_COMMIT,
    WOLFSSL_EXPECTED_VERSION,
    WOLFSSL_ROOT,
    directory_sha256,
    file_sha256,
)
from tools.serial_bridge import SerialBridge, SerialBridgeError  # noqa: E402


SCHEMA_VERSION = "pqc-sat-kex-fair-metrics-v2"
EXPERIMENT = "KEX_FAIR_V1"
SESSION_BENCH_CAPABILITY = "FAIR_SESSION_V1"
SCENARIOS = ("ECDH", "MLKEM")
PROFILE_CPU = {"BASELINE": 240, "OBC-1U-LIMITED": 80}
DEFAULT_MESSAGE_COUNTS = (1, 100, 500, 1000)
DEFAULT_PAYLOAD = b"PQC-SAT|KEX-FAIR|TEMP=24.5|STATUS=OK"
DEFAULT_PAYLOAD_HEX = DEFAULT_PAYLOAD.hex().upper()
FAIR_COMMON = {
    "experiment": EXPERIMENT,
    "crypto_impl": "wolfCrypt-portable",
    "crypto_version": "5.9.2",
    "compiler": "8.4.0",
    "framework": "arduino-esp32-2.0.17",
    "build_profile": "robocore_wisdom_esp32_fair",
    "kdf": "HKDF-SHA256",
    "cipher": "AES-128-GCM",
    "optimization": "portable-software",
    "target_asm": "0",
    "hw_crypto": "0",
    "authenticated_kex": "0",
}
MISSION_REQUIRED = {
    "result": "DELIVERED",
    "key_match": "1",
    "tag_match": "1",
    "aead_match": "1",
    "decrypt_ok": "1",
}
KEX_EXPECTED = {
    "ECDH": {"kex": "ECDH-P256", "setup_bytes": 65, "response_bytes": 65},
    "MLKEM": {"kex": "ML-KEM-512", "setup_bytes": 800, "response_bytes": 768},
}
TIMING_FIELDS = (
    "setup_us",
    "initiator_us",
    "responder_us",
    "kex_total_us",
    "kdf_us",
    "rng_us",
    "encrypt_us",
    "decrypt_us",
    "online_us",
    "end_to_end_us",
    "elapsed_us",
)
BYTE_FIELDS = (
    "setup_bytes",
    "response_bytes",
    "data_bytes",
    "wire_total_fresh",
    "wire_total_preprovisioned",
    "bytes_total",
)
SESSION_TIMING_FIELDS = (
    "setup_us",
    "initiator_us",
    "responder_us",
    "kex_total_us",
    "kdf_us",
    "session_setup_us",
    "rng_total_us",
    "encrypt_total_us",
    "decrypt_total_us",
    "data_total_us",
    "end_to_end_us",
    "amortized_us_per_message",
)
SESSION_BYTE_FIELDS = (
    "setup_bytes",
    "response_bytes",
    "handshake_bytes",
    "data_bytes_per_message",
    "data_total_bytes",
    "wire_total_bytes",
    "amortized_bytes_per_message",
)
SESSION_MEMORY_FIELDS = (
    "heap_before",
    "heap_after",
    "min_heap_before",
    "min_heap_global",
    "largest_block_before",
    "largest_block_after",
    "stack_hwm_words",
)


@dataclass(frozen=True)
class PlanStep:
    command: str
    phase: str
    profile: str | None = None
    pair_family: str = ""
    pair_id: str = ""
    scenario: str = ""
    message_count: int | None = None
    order_position: int | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="porta serial, por exemplo /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--fresh-cycles",
        "--cycles",
        dest="fresh_cycles",
        type=int,
        default=100,
        help="pares MISSION ECDH/MLKEM por perfil",
    )
    parser.add_argument(
        "--session-repeats",
        type=int,
        default=30,
        help="pares SESSION_BENCH por perfil e quantidade de mensagens",
    )
    parser.add_argument(
        "--message-counts",
        nargs="+",
        type=int,
        default=list(DEFAULT_MESSAGE_COUNTS),
    )
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--bench-rounds", type=int, default=100)
    parser.add_argument("--bench-repeats", type=int, default=3)
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=list(DEFAULT_PROFILES),
        choices=list(DEFAULT_PROFILES),
    )
    parser.add_argument("--payload-hex", default=DEFAULT_PAYLOAD_HEX)
    parser.add_argument("--deployment-manifest")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def validate_payload_hex(raw: str) -> str:
    value = raw.strip().upper()
    if not value or len(value) % 2:
        raise ValueError("payload hexadecimal deve ter quantidade par de caracteres")
    try:
        payload = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("payload não é hexadecimal válido") from exc
    if not 1 <= len(payload) <= 96:
        raise ValueError("payload deve ter 1..96 bytes")
    return value


def planned_steps(args: argparse.Namespace) -> list[PlanStep]:
    payload_hex = validate_payload_hex(args.payload_hex)
    steps = [
        PlanStep("HELLO", "preflight"),
        PlanStep("KEX_INFO", "preflight"),
        PlanStep("PING", "preflight"),
    ]
    for profile in args.profiles:
        steps.extend(
            (
                PlanStep(f"PROFILE {profile}", "profile", profile),
                PlanStep("STATUS", "preflight", profile),
                PlanStep("KEX_INFO", "preflight", profile),
            )
        )
        for _ in range(args.bench_repeats):
            steps.append(PlanStep(f"KEX_BENCH {args.bench_rounds}", "bench", profile))
        for cycle in range(args.fresh_cycles):
            order = SCENARIOS if cycle % 2 == 0 else tuple(reversed(SCENARIOS))
            pair_id = f"fresh:{profile}:{cycle + 1:03d}"
            for position, scenario in enumerate(order, 1):
                steps.append(
                    PlanStep(
                        f"MISSION {scenario} {payload_hex}",
                        "mission",
                        profile,
                        "fresh",
                        pair_id,
                        scenario,
                        None,
                        position,
                    )
                )
            if (cycle + 1) % 25 == 0:
                steps.append(PlanStep("STATUS", "health", profile))
        for count_index, message_count in enumerate(args.message_counts):
            for repeat in range(args.session_repeats):
                order = (
                    SCENARIOS
                    if (count_index + repeat) % 2 == 0
                    else tuple(reversed(SCENARIOS))
                )
                pair_id = f"session:{profile}:{message_count}:{repeat + 1:03d}"
                for position, scenario in enumerate(order, 1):
                    steps.append(
                        PlanStep(
                            f"SESSION_BENCH {scenario} {message_count} {payload_hex}",
                            "session",
                            profile,
                            "session",
                            pair_id,
                            scenario,
                            int(message_count),
                            position,
                        )
                    )
    steps.extend(
        (
            PlanStep("PROFILE BASELINE", "cleanup", "BASELINE"),
            PlanStep("OLED STANDBY", "cleanup", "BASELINE"),
        )
    )
    return steps


def planned_commands(args: argparse.Namespace) -> list[tuple[str, str, str | None]]:
    """Compatibility projection used by tests and dry-run consumers."""

    return [(step.command, step.phase, step.profile) for step in planned_steps(args)]


def run_battery(args: argparse.Namespace, port: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    plan = planned_steps(args)
    with SerialBridge(port, baudrate=args.baud, timeout=args.timeout) as bridge:
        for index, step in enumerate(plan, 1):
            record = send_record(bridge, step.command, step.phase, step.profile)
            record.update(
                sequence_index=index,
                sequence_total=len(plan),
                pair_family=step.pair_family,
                pair_id=step.pair_id,
                scenario_requested=step.scenario,
                message_count_requested=step.message_count,
                order_position=step.order_position,
            )
            records.append(record)
            print(f"[{index:04d}/{len(plan):04d}] {'OK' if record.get('ok') else 'FAIL'} {step.command}")
            if step.phase in {"mission", "bench", "session"} and args.pause > 0:
                time.sleep(args.pause)
    return records


def _int(payload: dict[str, str], field: str) -> int | None:
    try:
        return int(payload[field], 0)
    except (KeyError, TypeError, ValueError):
        return None


def _positive_fields(payload: dict[str, str], fields: tuple[str, ...]) -> list[str]:
    return [f"{field} não positivo" for field in fields if (_int(payload, field) or 0) <= 0]


def _validate_profile(payload: dict[str, str], expected_profile: str | None) -> list[str]:
    if expected_profile is None:
        return []
    errors: list[str] = []
    if payload.get("profile") != expected_profile:
        errors.append(f"profile={payload.get('profile')!r}, esperado {expected_profile!r}")
    if _int(payload, "cpu_mhz") != PROFILE_CPU[expected_profile]:
        errors.append(f"cpu_mhz divergente para {expected_profile}")
    return errors


def validate_kex_info(
    payload: dict[str, str],
    expected_profile: str | None = None,
) -> list[str]:
    errors: list[str] = []
    for field, expected in FAIR_COMMON.items():
        if payload.get(field) != expected:
            errors.append(f"{field}={payload.get(field)!r}, esperado {expected!r}")
    if payload.get("session_bench") != SESSION_BENCH_CAPABILITY:
        errors.append("SESSION_BENCH FAIR não anunciado")
    expected_sizes = {
        "ecdh_setup_bytes": 65,
        "ecdh_response_bytes": 65,
        "mlkem_setup_bytes": 800,
        "mlkem_response_bytes": 768,
    }
    for field, expected in expected_sizes.items():
        if _int(payload, field) != expected:
            errors.append(f"{field} divergente")
    errors.extend(_validate_profile(payload, expected_profile))
    return errors


def validate_mission(
    payload: dict[str, str],
    scenario: str,
    payload_len: int,
    expected_profile: str | None = None,
) -> list[str]:
    errors: list[str] = []
    for field, expected in {**FAIR_COMMON, **MISSION_REQUIRED}.items():
        if payload.get(field) != expected:
            errors.append(f"{field}={payload.get(field)!r}, esperado {expected!r}")
    expected = KEX_EXPECTED[scenario]
    if payload.get("scenario") != scenario or payload.get("kex") != expected["kex"]:
        errors.append("cenário ou KEX divergente")
    errors.extend(_positive_fields(payload, TIMING_FIELDS))
    errors.extend(_positive_fields(payload, BYTE_FIELDS))
    errors.extend(_positive_fields(payload, ("heap", "min_heap")))
    setup = _int(payload, "setup_bytes")
    response = _int(payload, "response_bytes")
    data = _int(payload, "data_bytes")
    fresh = _int(payload, "wire_total_fresh")
    preprovisioned = _int(payload, "wire_total_preprovisioned")
    if setup != expected["setup_bytes"] or response != expected["response_bytes"]:
        errors.append("tamanhos públicos do KEX divergentes")
    if _int(payload, "bytes_payload") != payload_len:
        errors.append("bytes_payload divergente")
    if None not in {setup, response, data, fresh} and fresh != setup + response + data:
        errors.append("wire_total_fresh não fecha")
    if None not in {response, data, preprovisioned} and preprovisioned != response + data:
        errors.append("wire_total_preprovisioned não fecha")
    if _int(payload, "bytes_total") != fresh:
        errors.append("bytes_total não coincide com wire_total_fresh")
    setup_us = _int(payload, "setup_us")
    initiator_us = _int(payload, "initiator_us")
    responder_us = _int(payload, "responder_us")
    kex_total_us = _int(payload, "kex_total_us")
    if (
        None not in {setup_us, initiator_us, responder_us, kex_total_us}
        and kex_total_us != setup_us + initiator_us + responder_us
    ):
        errors.append("kex_total_us não fecha")
    elapsed_us = _int(payload, "elapsed_us")
    online_us = _int(payload, "online_us")
    if (
        None not in {elapsed_us, setup_us, online_us}
        and online_us != elapsed_us - setup_us
    ):
        errors.append("online_us não fecha")
    heap = _int(payload, "heap")
    min_heap = _int(payload, "min_heap")
    if heap is not None and min_heap is not None and min_heap > heap:
        errors.append("min_heap maior que heap")
    errors.extend(_validate_profile(payload, expected_profile))
    return errors


def validate_bench(
    payload: dict[str, str],
    rounds: int,
    expected_profile: str,
) -> list[str]:
    errors: list[str] = []
    for field, expected in FAIR_COMMON.items():
        if payload.get(field) != expected:
            errors.append(f"{field} divergente")
    if payload.get("paired_order") != "alternating":
        errors.append("ordem pareada divergente")
    if _int(payload, "n") != rounds or _int(payload, "pairs") != rounds:
        errors.append("quantidade KEX_BENCH divergente")
    if _int(payload, "ok") != rounds * 2:
        errors.append("KEX_BENCH não concluiu os dois algoritmos")
    if _int(payload, "ecdh_ok") != rounds or _int(payload, "mlkem_ok") != rounds:
        errors.append("contagem por algoritmo divergente")
    if _int(payload, "ecdh_rc") != 0 or _int(payload, "mlkem_rc") != 0:
        errors.append("código de retorno KEX não é zero")
    errors.extend(
        _positive_fields(
            payload,
            (
                "ecdh_setup_avg_us",
                "ecdh_initiator_avg_us",
                "ecdh_responder_avg_us",
                "ecdh_total_avg_us",
                "mlkem_setup_avg_us",
                "mlkem_initiator_avg_us",
                "mlkem_responder_avg_us",
                "mlkem_total_avg_us",
                "elapsed_us",
                "heap",
                "min_heap",
            ),
        )
    )
    for field, expected in {
        "ecdh_setup_bytes": 65,
        "ecdh_response_bytes": 65,
        "mlkem_setup_bytes": 800,
        "mlkem_response_bytes": 768,
    }.items():
        if _int(payload, field) != expected:
            errors.append(f"{field} divergente")
    for prefix in ("ecdh", "mlkem"):
        parts = (
            _int(payload, f"{prefix}_setup_avg_us"),
            _int(payload, f"{prefix}_initiator_avg_us"),
            _int(payload, f"{prefix}_responder_avg_us"),
        )
        total = _int(payload, f"{prefix}_total_avg_us")
        if None not in {*parts, total} and abs(total - sum(parts)) > 2:
            errors.append(f"{prefix}_total_avg_us não fecha")
    errors.extend(_validate_profile(payload, expected_profile))
    return errors


def validate_session(
    payload: dict[str, str],
    scenario: str,
    messages: int,
    payload_len: int,
    expected_profile: str,
) -> list[str]:
    errors: list[str] = []
    for field, expected in FAIR_COMMON.items():
        if payload.get(field) != expected:
            errors.append(f"{field} divergente")
    expected = KEX_EXPECTED[scenario]
    if payload.get("session_bench") != SESSION_BENCH_CAPABILITY:
        errors.append("capacidade SESSION_BENCH divergente")
    if payload.get("scenario") != scenario or payload.get("kex") != expected["kex"]:
        errors.append("cenário ou KEX divergente")
    if payload.get("key_match") != "1" or payload.get("aead_match") != "1":
        errors.append("sessão não comprovou chave e AEAD")
    if _int(payload, "messages") != messages or _int(payload, "messages_ok") != messages:
        errors.append("quantidade de mensagens divergente")
    errors.extend(_positive_fields(payload, SESSION_TIMING_FIELDS))
    errors.extend(_positive_fields(payload, SESSION_BYTE_FIELDS))
    errors.extend(_positive_fields(payload, SESSION_MEMORY_FIELDS))
    if _int(payload, "bytes_payload") != payload_len:
        errors.append("bytes_payload divergente")
    setup = _int(payload, "setup_bytes")
    response = _int(payload, "response_bytes")
    handshake = _int(payload, "handshake_bytes")
    data_per_message = _int(payload, "data_bytes_per_message")
    data_total = _int(payload, "data_total_bytes")
    wire_total = _int(payload, "wire_total_bytes")
    if setup != expected["setup_bytes"] or response != expected["response_bytes"]:
        errors.append("tamanhos públicos do KEX divergentes")
    if None not in {setup, response, handshake} and handshake != setup + response:
        errors.append("handshake_bytes não fecha")
    if data_per_message != payload_len + 12 + 16:
        errors.append("data_bytes_per_message divergente")
    if None not in {data_per_message, data_total} and data_total != data_per_message * messages:
        errors.append("data_total_bytes não fecha")
    if None not in {handshake, data_total, wire_total} and wire_total != handshake + data_total:
        errors.append("wire_total_bytes não fecha")
    end_to_end = _int(payload, "end_to_end_us")
    kex_total = _int(payload, "kex_total_us")
    kdf = _int(payload, "kdf_us")
    session_setup = _int(payload, "session_setup_us")
    data_time = _int(payload, "data_total_us")
    if (
        None not in {kex_total, kdf, session_setup}
        and session_setup != kex_total + kdf
    ):
        errors.append("session_setup_us não fecha")
    if (
        None not in {end_to_end, session_setup, data_time}
        and end_to_end < session_setup + data_time
    ):
        errors.append("end_to_end_us menor que setup mais dados")
    if end_to_end is not None and _int(payload, "amortized_us_per_message") != end_to_end // messages:
        errors.append("amortized_us_per_message divergente")
    if wire_total is not None and _int(payload, "amortized_bytes_per_message") != wire_total // messages:
        errors.append("amortized_bytes_per_message divergente")
    heap_before = _int(payload, "heap_before")
    heap_after = _int(payload, "heap_after")
    if None not in {heap_before, heap_after} and _int(payload, "heap_delta") != heap_before - heap_after:
        errors.append("heap_delta divergente")
    min_before = _int(payload, "min_heap_before")
    min_global = _int(payload, "min_heap_global")
    if None not in {min_before, min_global} and min_global > min_before:
        errors.append("min_heap_global aumentou durante a amostra")
    if heap_before is not None and (_int(payload, "largest_block_before") or 0) > heap_before:
        errors.append("largest_block_before maior que heap_before")
    if heap_after is not None and (_int(payload, "largest_block_after") or 0) > heap_after:
        errors.append("largest_block_after maior que heap_after")
    errors.extend(_validate_profile(payload, expected_profile))
    return errors


def official_design_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if tuple(args.profiles) != DEFAULT_PROFILES:
        errors.append("a coleta oficial exige BASELINE e OBC-1U-LIMITED nesta ordem")
    if args.fresh_cycles != 100:
        errors.append("a coleta oficial exige exatamente 100 pares novos por perfil")
    if args.session_repeats != 30:
        errors.append("a coleta oficial exige exatamente 30 pares amortizados por célula")
    if tuple(args.message_counts) != DEFAULT_MESSAGE_COUNTS:
        errors.append("a coleta oficial exige 1, 100, 500 e 1000 mensagens nesta ordem")
    if args.bench_repeats != 3:
        errors.append("a coleta oficial exige exatamente 3 KEX_BENCH por perfil")
    if args.bench_rounds != 100:
        errors.append("a coleta oficial exige KEX_BENCH com 100 pares")
    if args.pause < 0.25:
        errors.append("a coleta oficial exige pausa de pelo menos 0,25 s")
    if validate_payload_hex(args.payload_hex) != DEFAULT_PAYLOAD_HEX:
        errors.append("a coleta oficial exige o payload FAIR padronizado")
    return errors


def load_deployment_manifest(path: str | None) -> dict[str, object] | None:
    if not path:
        return None
    manifest_path = Path(path)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"manifesto de deploy inválido: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("manifesto de deploy deve ser um objeto JSON")
    return document


def validate_deployment_manifest(
    manifest: dict[str, object] | None,
    *,
    expected_port: str | None = None,
) -> list[str]:
    if manifest is None:
        return ["coleta oficial exige manifesto do firmware gravado"]
    errors: list[str] = []
    if manifest.get("schema_version") != DEPLOY_SCHEMA:
        errors.append("schema do manifesto de deploy divergente")
    if manifest.get("platformio_env") != PLATFORMIO_ENV:
        errors.append("ambiente FAIR ausente no manifesto")
    if manifest.get("uploaded") is not True or manifest.get("verified") is not True:
        errors.append("manifesto não comprova upload e verificação")
    digest = str(manifest.get("firmware_sha256", ""))
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        errors.append("SHA-256 do firmware inválido")
    handshake = manifest.get("post_upload_handshake")
    if not isinstance(handshake, dict):
        errors.append("handshake pós-upload ausente")
    elif (
        handshake.get("game") != "STAGED_V1"
        or handshake.get("kex") != "FAIR_V1"
        or handshake.get("session_bench") != SESSION_BENCH_CAPABILITY
    ):
        errors.append(
            "handshake pós-upload não é STAGED_V1/FAIR_V1/FAIR_SESSION_V1"
        )
    if expected_port is not None:
        recorded_port = str(manifest.get("port_realpath") or manifest.get("port") or "")
        if not recorded_port or os.path.realpath(expected_port) != os.path.realpath(recorded_port):
            errors.append("porta da coleta diverge do manifesto de deploy")
    recorded_sources = manifest.get("source_sha256")
    if not isinstance(recorded_sources, dict):
        errors.append("hashes das fontes ausentes no manifesto")
    else:
        for source_path in SOURCE_PATHS:
            relative = str(source_path.relative_to(ROOT))
            recorded = str(recorded_sources.get(relative, ""))
            try:
                current = file_sha256(source_path)
            except OSError:
                errors.append(f"fonte FAIR ausente: {relative}")
                continue
            if recorded != current:
                errors.append(f"fonte FAIR mudou após o upload: {relative}")
    dependencies = manifest.get("dependency_provenance")
    wolfssl = dependencies.get("wolfssl") if isinstance(dependencies, dict) else None
    if not isinstance(wolfssl, dict):
        errors.append("proveniência da dependência wolfSSL ausente")
    else:
        if wolfssl.get("expected_version") != WOLFSSL_EXPECTED_VERSION:
            errors.append("versão esperada do wolfSSL diverge no manifesto")
        if wolfssl.get("expected_upstream_commit") != WOLFSSL_EXPECTED_UPSTREAM_COMMIT:
            errors.append("commit esperado do wolfSSL diverge no manifesto")
        try:
            current_count, current_tree_sha256 = directory_sha256(WOLFSSL_ROOT)
        except (OSError, ValueError):
            errors.append("árvore wolfSSL usada no build não está disponível localmente")
        else:
            if wolfssl.get("file_count") != current_count:
                errors.append("quantidade de arquivos wolfSSL mudou após o upload")
            if wolfssl.get("tree_sha256") != current_tree_sha256:
                errors.append("árvore wolfSSL mudou após o upload")
    try:
        current_firmware_sha256 = file_sha256(FIRMWARE_BIN)
    except OSError:
        errors.append("firmware.bin do manifesto não está disponível localmente")
    else:
        if digest.lower() != current_firmware_sha256.lower():
            errors.append("firmware.bin local diverge do manifesto de deploy")
    return errors


def confidence_interval_95(values: list[float]) -> dict[str, object]:
    if not values:
        return {"n": 0}
    mean = statistics.fmean(values)
    if len(values) == 1:
        return {"n": 1, "mean": round(mean, 3), "low": None, "high": None}
    margin = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return {
        "n": len(values),
        "mean": round(mean, 3),
        "low": round(mean - margin, 3),
        "high": round(mean + margin, 3),
        "method": "normal_approximation_paired_differences",
    }


def _pair_records(records: list[dict[str, object]]) -> tuple[dict[str, dict[str, dict[str, str]]], list[str]]:
    pairs: dict[str, dict[str, dict[str, str]]] = {}
    positions: dict[str, set[int]] = {}
    families: dict[str, set[str]] = {}
    errors: list[str] = []
    for record in records:
        pair_id = str(record.get("pair_id", ""))
        scenario = str(record.get("scenario_requested", ""))
        if not pair_id or scenario not in SCENARIOS:
            errors.append(f"registro {record.get('sequence_index')} sem identidade pareada")
            continue
        pair = pairs.setdefault(pair_id, {})
        if scenario in pair:
            errors.append(f"{pair_id} contém cenário duplicado {scenario}")
        pair[scenario] = payload_of(record)
        position = record.get("order_position")
        if not isinstance(position, int) or position not in {1, 2}:
            errors.append(f"{pair_id} contém posição de ordem inválida")
        else:
            positions.setdefault(pair_id, set()).add(position)
        families.setdefault(pair_id, set()).add(str(record.get("pair_family", "")))
    for pair_id, pair in pairs.items():
        if set(pair) != set(SCENARIOS):
            errors.append(f"{pair_id} não contém ECDH e MLKEM")
        if positions.get(pair_id, set()) != {1, 2}:
            errors.append(f"{pair_id} não contém as posições 1 e 2")
        if len(families.get(pair_id, set())) != 1 or "" in families.get(pair_id, set()):
            errors.append(f"{pair_id} contém família pareada divergente")
    return pairs, errors


def _paired_metrics(
    records: list[dict[str, object]],
    fields: tuple[str, ...],
) -> dict[str, object]:
    pairs, _errors = _pair_records(records)
    summary: dict[str, object] = {}
    for field in fields:
        differences: list[float] = []
        ratios: list[float] = []
        for pair in pairs.values():
            if set(pair) != set(SCENARIOS):
                continue
            ecdh_value = _int(pair["ECDH"], field)
            mlkem_value = _int(pair["MLKEM"], field)
            if ecdh_value is None or mlkem_value is None:
                continue
            differences.append(float(mlkem_value - ecdh_value))
            if ecdh_value > 0:
                ratios.append(float(mlkem_value) / float(ecdh_value))
        summary[field] = {
            "mlkem_minus_ecdh": stats(differences),
            "difference_mean_ci95": confidence_interval_95(differences),
            "mlkem_over_ecdh": stats(ratios),
        }
    return summary


def _distribution_counts(
    records: list[dict[str, object]],
    *,
    include_messages: bool,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        profile = str(record.get("profile_requested", ""))
        scenario = str(record.get("scenario_requested", ""))
        messages = record.get("message_count_requested")
        key = f"{profile}|{scenario}"
        if include_messages:
            key += f"|{messages}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def summarize(
    records: list[dict[str, object]],
    args: argparse.Namespace,
    elapsed_s: float,
    manifest: dict[str, object] | None = None,
) -> dict[str, object]:
    failed = [record for record in records if not record.get("ok")]
    payload_len = len(bytes.fromhex(validate_payload_hex(args.payload_hex)))
    design_errors = official_design_errors(args)
    manifest_errors = validate_deployment_manifest(manifest)

    info_records = [record for record in records if record.get("command") == "KEX_INFO"]
    info_errors: list[dict[str, object]] = []
    for record in info_records:
        expected_profile = str(record.get("profile_requested") or "") or None
        errors = validate_kex_info(payload_of(record), expected_profile)
        if errors:
            info_errors.append({"sequence_index": record.get("sequence_index"), "errors": errors})
    info_profiles = {
        str(record.get("profile_requested"))
        for record in info_records
        if record.get("profile_requested")
    }
    missing_info_profiles = sorted(set(args.profiles) - info_profiles)

    mission_records = [
        record for record in records if str(record.get("command", "")).startswith("MISSION ")
    ]
    mission_errors: list[dict[str, object]] = []
    for record in mission_records:
        scenario = str(record.get("scenario_requested", ""))
        profile = str(record.get("profile_requested", ""))
        errors = validate_mission(payload_of(record), scenario, payload_len, profile)
        if errors:
            mission_errors.append(
                {
                    "sequence_index": record.get("sequence_index"),
                    "pair_id": record.get("pair_id"),
                    "errors": errors,
                }
            )
    _fresh_pairs, fresh_pair_errors = _pair_records(mission_records)
    fresh_distribution = _distribution_counts(mission_records, include_messages=False)
    expected_fresh_distribution = {
        f"{profile}|{scenario}": args.fresh_cycles
        for profile in args.profiles
        for scenario in SCENARIOS
    }
    fresh_distribution_errors = [
        f"{cell}: observado={fresh_distribution.get(cell, 0)} esperado={expected}"
        for cell, expected in expected_fresh_distribution.items()
        if fresh_distribution.get(cell, 0) != expected
    ]
    fresh_distribution_errors.extend(
        f"célula inesperada {cell}" for cell in fresh_distribution if cell not in expected_fresh_distribution
    )

    session_records = [
        record
        for record in records
        if str(record.get("command", "")).startswith("SESSION_BENCH ")
    ]
    session_errors: list[dict[str, object]] = []
    for record in session_records:
        scenario = str(record.get("scenario_requested", ""))
        profile = str(record.get("profile_requested", ""))
        messages = int(record.get("message_count_requested") or 0)
        errors = validate_session(payload_of(record), scenario, messages, payload_len, profile)
        if errors:
            session_errors.append(
                {
                    "sequence_index": record.get("sequence_index"),
                    "pair_id": record.get("pair_id"),
                    "errors": errors,
                }
            )
    _session_pairs, session_pair_errors = _pair_records(session_records)
    session_distribution = _distribution_counts(session_records, include_messages=True)
    expected_session_distribution = {
        f"{profile}|{scenario}|{messages}": args.session_repeats
        for profile in args.profiles
        for messages in args.message_counts
        for scenario in SCENARIOS
    }
    session_distribution_errors = [
        f"{cell}: observado={session_distribution.get(cell, 0)} esperado={expected}"
        for cell, expected in expected_session_distribution.items()
        if session_distribution.get(cell, 0) != expected
    ]
    session_distribution_errors.extend(
        f"célula inesperada {cell}"
        for cell in session_distribution
        if cell not in expected_session_distribution
    )

    bench_records = [
        record for record in records if str(record.get("command", "")).startswith("KEX_BENCH ")
    ]
    bench_errors: list[dict[str, object]] = []
    bench_distribution: dict[str, int] = {}
    for record in bench_records:
        profile = str(record.get("profile_requested", ""))
        bench_distribution[profile] = bench_distribution.get(profile, 0) + 1
        errors = validate_bench(payload_of(record), args.bench_rounds, profile)
        if errors:
            bench_errors.append({"sequence_index": record.get("sequence_index"), "errors": errors})
    bench_distribution_errors = [
        f"{profile}: observado={bench_distribution.get(profile, 0)} esperado={args.bench_repeats}"
        for profile in args.profiles
        if bench_distribution.get(profile, 0) != args.bench_repeats
    ]
    bench_distribution_errors.extend(
        f"perfil inesperado {profile}"
        for profile in bench_distribution
        if profile not in args.profiles
    )

    profiles: dict[str, object] = {}
    for profile in args.profiles:
        fresh_profile = [
            record for record in mission_records if record.get("profile_requested") == profile
        ]
        session_profile = [
            record for record in session_records if record.get("profile_requested") == profile
        ]
        fresh_scenarios: dict[str, object] = {}
        for scenario in SCENARIOS:
            payloads = [
                payload_of(record)
                for record in fresh_profile
                if record.get("scenario_requested") == scenario
            ]
            fresh_scenarios[scenario] = {
                "runs": len(payloads),
                **{
                    field: stats(payload.get(field) for payload in payloads)
                    for field in TIMING_FIELDS + BYTE_FIELDS + ("heap", "min_heap")
                },
            }
        session_cells: dict[str, object] = {}
        for message_count in args.message_counts:
            cell_records = [
                record
                for record in session_profile
                if record.get("message_count_requested") == message_count
            ]
            cell_scenarios: dict[str, object] = {}
            for scenario in SCENARIOS:
                payloads = [
                    payload_of(record)
                    for record in cell_records
                    if record.get("scenario_requested") == scenario
                ]
                cell_scenarios[scenario] = {
                    "runs": len(payloads),
                    **{
                        field: stats(payload.get(field) for payload in payloads)
                        for field in SESSION_TIMING_FIELDS
                        + SESSION_BYTE_FIELDS
                        + SESSION_MEMORY_FIELDS
                        + ("heap_delta",)
                    },
                }
            session_cells[str(message_count)] = {
                "scenarios": cell_scenarios,
                "paired": _paired_metrics(
                    cell_records,
                    (
                        "session_setup_us",
                        "end_to_end_us",
                        "amortized_us_per_message",
                        "wire_total_bytes",
                        "amortized_bytes_per_message",
                        "heap_after",
                        "min_heap_global",
                    ),
                ),
            }
        profiles[profile] = {
            "fresh": {
                "scenarios": fresh_scenarios,
                "paired": _paired_metrics(
                    fresh_profile,
                    ("kex_total_us", "online_us", "end_to_end_us", "bytes_total", "heap", "min_heap"),
                ),
            },
            "sessions": session_cells,
        }

    expected_fresh_runs = len(args.profiles) * args.fresh_cycles * len(SCENARIOS)
    expected_session_runs = (
        len(args.profiles)
        * len(args.message_counts)
        * args.session_repeats
        * len(SCENARIOS)
    )
    expected_bench_runs = len(args.profiles) * args.bench_repeats
    data_errors = (
        failed,
        info_errors,
        missing_info_profiles,
        mission_errors,
        fresh_pair_errors,
        fresh_distribution_errors,
        session_errors,
        session_pair_errors,
        session_distribution_errors,
        bench_errors,
        bench_distribution_errors,
        len(mission_records) != expected_fresh_runs,
        len(session_records) != expected_session_runs,
        len(bench_records) != expected_bench_runs,
    )
    data_ok = not any(data_errors)
    official_candidate = not any(
        (
            not data_ok,
            design_errors,
            manifest_errors,
        )
    )
    return {
        "ok": data_ok,
        "official_candidate": official_candidate,
        "records": len(records),
        "failed": len(failed),
        "fresh_mission_runs": len(mission_records),
        "kex_bench_runs": len(bench_records),
        "session_bench_runs": len(session_records),
        "invalid_pairs": len(fresh_pair_errors) + len(session_pair_errors),
        "missing_cells": len(fresh_distribution_errors)
        + len(session_distribution_errors)
        + len(bench_distribution_errors),
        "profile_mismatches": sum(
            "profile=" in error or "cpu_mhz" in error
            for group in (info_errors, mission_errors, session_errors, bench_errors)
            for entry in group
            for error in entry["errors"]
        ),
        "elapsed_s": round(elapsed_s, 2),
        "design_errors": design_errors,
        "manifest_errors": manifest_errors,
        "info_errors": info_errors,
        "missing_info_profiles": missing_info_profiles,
        "mission_errors": mission_errors[:50],
        "fresh_pair_errors": fresh_pair_errors[:50],
        "fresh_distribution_errors": fresh_distribution_errors,
        "session_errors": session_errors[:50],
        "session_pair_errors": session_pair_errors[:50],
        "session_distribution_errors": session_distribution_errors,
        "bench_errors": bench_errors,
        "bench_distribution_errors": bench_distribution_errors,
        "profiles": profiles,
    }


def print_plan(args: argparse.Namespace) -> None:
    plan = planned_steps(args)
    design_errors = official_design_errors(args)
    print(f"planned_commands={len(plan)}")
    print(
        f"profiles={','.join(args.profiles)} fresh_pairs={args.fresh_cycles} "
        f"fresh_missions={sum(step.phase == 'mission' for step in plan)} "
        f"session_runs={sum(step.phase == 'session' for step in plan)} "
        f"kex_bench={sum(step.phase == 'bench' for step in plan)}"
    )
    print(
        "official_design=PASS"
        if not design_errors
        else "official_design=NON_OFFICIAL " + "; ".join(design_errors)
    )
    for index, step in enumerate(plan[:50], 1):
        print(f"{index:04d} {step.phase:9s} {step.profile or '-':15s} {step.command}")
    if len(plan) > 50:
        print(f"... {len(plan) - 50} more commands")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_payload_hex(args.payload_hex)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if (
        args.fresh_cycles < 1
        or args.session_repeats < 1
        or args.bench_repeats < 0
        or not 1 <= args.bench_rounds <= 100
        or any(count not in DEFAULT_MESSAGE_COUNTS for count in args.message_counts)
        or len(set(args.message_counts)) != len(args.message_counts)
    ):
        print("error: parâmetros de quantidade fora do contrato FAIR", file=sys.stderr)
        return 2
    if args.dry_run:
        print_plan(args)
        return 0

    try:
        manifest = load_deployment_manifest(args.deployment_manifest)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not official_design_errors(args):
        preliminary_manifest_errors = validate_deployment_manifest(manifest)
        if preliminary_manifest_errors:
            print(
                "error: coleta oficial recusada antes da serial: "
                + "; ".join(preliminary_manifest_errors),
                file=sys.stderr,
            )
            return 2
    started = time.monotonic()
    try:
        device = discover_wisdom(
            args.port,
            baudrate=args.baud,
            timeout=min(args.timeout, 3.0),
            require_staged_game=True,
            require_fair_kex=True,
            require_session_bench=True,
        )
        port = device.port
        preflight_manifest_errors = validate_deployment_manifest(
            manifest,
            expected_port=port,
        )
        if not official_design_errors(args) and preflight_manifest_errors:
            print(
                "error: coleta oficial recusada antes da bateria: "
                + "; ".join(preflight_manifest_errors),
                file=sys.stderr,
            )
            return 2
        records = run_battery(args, port)
    except SerialBridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    summary = summarize(records, args, time.monotonic() - started, manifest)
    document = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now_iso(),
        "experiment": EXPERIMENT,
        "claim_scope": "algorithm_plus_implementation_plus_compiler_plus_hardware_plus_configuration",
        "port": port,
        "baud": args.baud,
        "timeout_s": args.timeout,
        "profiles": list(args.profiles),
        "fresh_pairs_per_profile": args.fresh_cycles,
        "session_pairs_per_cell": args.session_repeats,
        "message_counts": list(args.message_counts),
        "order_policy": "alternating_within_each_pair_cell",
        "payload_hex": validate_payload_hex(args.payload_hex),
        "bench_rounds": args.bench_rounds,
        "bench_repeats_per_profile": args.bench_repeats,
        "deployment_manifest_path": args.deployment_manifest or "",
        "deployment_manifest": manifest,
        "memory_scope": (
            "heap_before_after_and_global_minimum_plus_largest_block_and_task_stack_watermark;"
            "not_isolated_algorithm_peak"
        ),
        "records": records,
        "summary": summary,
    }
    path = write_document(document, args.log_dir, "kex_fair_metrics")
    print(f"kex_fair_metrics_json={path}")
    print(
        "summary="
        + json.dumps(
            {
                key: summary[key]
                for key in (
                    "ok",
                    "official_candidate",
                    "failed",
                    "fresh_mission_runs",
                    "kex_bench_runs",
                    "session_bench_runs",
                    "invalid_pairs",
                    "missing_cells",
                    "profile_mismatches",
                    "elapsed_s",
                )
            },
            sort_keys=True,
        )
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
