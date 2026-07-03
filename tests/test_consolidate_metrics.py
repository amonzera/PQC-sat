import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import consolidate_metrics
from tools.consolidate_metrics import AES_REQUIRED_FIELDS, aes_checks, metrics_status, mission_profile_stats
from tools.aes_gcm_metrics_battery import summarize_aes_gcm


def mission_record(**overrides):
    payload = {field: "1" for field in AES_REQUIRED_FIELDS}
    payload.update(
        {
            "cipher": "AES-128-GCM",
            "nonce_bytes": "12",
            "gcm_tag_bytes": "16",
            "nonce_crc32": "0x00000001",
            "aead_match": "1",
            "decrypt_ok": "1",
            "tag_match": "1",
            "scenario": "CLASSIC",
            "crypto": "ECDH-P256",
            "key_source": "ECDH-P256",
            "bytes_ecdh": "65",
            "keygen_us": "200",
            "ecdh_tx_us": "100",
            "ecdh_rx_us": "101",
            "key_match": "1",
            "result": "DELIVERED",
        }
    )
    payload.update(overrides)
    payload.setdefault("profile", "BASELINE")
    return {
        "ok": True,
        "command": "MISSION CLASSIC",
        "profile_requested": payload["profile"],
        "payload": payload,
    }


def complete_mission_records():
    records = [mission_record(nonce_crc32="0x1")]
    for scenario, nonce in (("PQC", "0x2"), ("PQC_CRC32", "0x3")):
        records.append(mission_record(
            scenario=scenario,
            nonce_crc32=nonce,
            crypto="ML-KEM-512",
            key_source="ML-KEM-512",
            bytes_mlkem="768",
            keygen_us="300",
            encap_us="301",
            decap_us="302",
        ))
    return records


def official_mission_records():
    records = []
    nonce = 0
    for profile in ("BASELINE", "OBC-1U-LIMITED"):
        for _cycle in range(100):
            for scenario in ("CLASSIC", "PQC", "PQC_CRC32"):
                nonce += 1
                fields = {"scenario": scenario, "profile": profile, "nonce_crc32": f"0x{nonce:08X}"}
                if scenario != "CLASSIC":
                    fields.update(
                        crypto="ML-KEM-512",
                        key_source="ML-KEM-512",
                        bytes_mlkem="768",
                        keygen_us="300",
                        encap_us="301",
                        decap_us="302",
                    )
                records.append(mission_record(**fields))
    return records


class ConsolidatedMetricsTests(unittest.TestCase):
    def test_generic_battery_with_valid_aes_records_is_official(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        checks = aes_checks(data, official_mission_records())

        self.assertTrue(checks["official_candidate"])
        self.assertEqual(checks["nonce_crc32_duplicates"], 0)
        self.assertEqual(metrics_status(data, checks), "comparação oficial ECDH P-256 vs ML-KEM-512")

    def test_runner_and_consolidator_use_identical_official_checks(self):
        records = official_mission_records()
        runner_checks = summarize_aes_gcm(records)["checks"]
        data = {"summary": {"aes_gcm": {"checks": runner_checks}}}

        consolidated_checks = aes_checks(data, records)

        self.assertEqual(consolidated_checks, runner_checks)
        self.assertNotIn("recomputed_from_records", consolidated_checks)

    def test_duplicate_nonce_crc_is_counted(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        records = complete_mission_records()
        records[1]["payload"]["nonce_crc32"] = records[0]["payload"]["nonce_crc32"]
        checks = aes_checks(data, records)

        self.assertEqual(checks["nonce_crc32_duplicates"], 1)

    def test_missing_aes_fields_rejects_generic_battery(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        checks = aes_checks(data, [{"payload": {"cipher": "HMAC-SHA256"}}])

        self.assertFalse(checks["official_candidate"])
        self.assertEqual(
            metrics_status(data, checks),
            "bateria incompatível com a consolidação ECDH vs ML-KEM",
        )

    def test_pre_ecdh_classic_log_is_not_official(self):
        record = mission_record()
        for field in ("bytes_ecdh", "ecdh_tx_us", "ecdh_rx_us"):
            record["payload"].pop(field)
        record["payload"].update(crypto="AES-128-GCM", key_source="RANDOM_SESSION")

        checks = aes_checks({"schema_version": "pqc-sat-aes-gcm-metrics-v1"}, [record])

        self.assertFalse(checks["official_candidate"])
        self.assertEqual(checks["ecdh_invalid_records"], 1)

    def test_incomplete_or_invalid_pqc_campaign_is_not_official(self):
        records = complete_mission_records()
        records.pop()
        checks = aes_checks({"schema_version": "pqc-sat-aes-gcm-metrics-v2"}, records)
        self.assertFalse(checks["balanced_scenarios"])
        self.assertFalse(checks["official_candidate"])

        records = complete_mission_records()
        records[1]["payload"]["bytes_mlkem"] = "0"
        checks = aes_checks({"schema_version": "pqc-sat-aes-gcm-metrics-v2"}, records)
        self.assertEqual(checks["pqc_invalid_records"], 1)
        self.assertFalse(checks["official_candidate"])

    def test_consolidator_refuses_to_overwrite_results_with_short_campaign(self):
        document = {
            "schema_version": "pqc-sat-aes-gcm-metrics-v2",
            "records": complete_mission_records(),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "short.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with mock.patch.object(sys, "argv", ["consolidate_metrics.py", "--file", str(path)]):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
                    status = consolidate_metrics.main()

        self.assertEqual(status, 1)
        self.assertIn("refusing to overwrite consolidated metrics", stderr.getvalue())

    def test_profile_stats_preserve_limited_mission_values(self):
        record = mission_record(
            scenario="PQC",
            elapsed_us="40197",
            bytes_total="837",
            bytes_payload="41",
            bytes_crypto="796",
            bytes_checksum="0",
            keygen_us="10524",
            encap_us="11882",
            decap_us="15259",
            encrypt_us="600",
            decrypt_us="313",
            crc_us="0",
            heap="201412",
            min_heap="197624",
            result="DELIVERED",
            crypto="ML-KEM-512",
        )

        profile = mission_profile_stats([record])

        self.assertEqual(profile["PQC"]["elapsed_us"], 40197)
        self.assertEqual(profile["PQC"]["keygen_us"], 10524)
        self.assertEqual(profile["PQC"]["min_heap"], 197624)


if __name__ == "__main__":
    unittest.main()
