import unittest

from tools.consolidate_metrics import AES_REQUIRED_FIELDS, aes_checks, metrics_status, mission_profile_stats


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
        }
    )
    payload.update(overrides)
    return {"payload": payload}


class ConsolidatedMetricsTests(unittest.TestCase):
    def test_generic_battery_with_valid_aes_records_is_official(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        checks = aes_checks(data, [mission_record(nonce_crc32="0x1"), mission_record(nonce_crc32="0x2")])

        self.assertTrue(checks["official_candidate"])
        self.assertEqual(checks["nonce_crc32_duplicates"], 0)
        self.assertEqual(metrics_status(data, checks), "versão cifrada oficial com AES-128-GCM")

    def test_duplicate_nonce_crc_is_counted(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        checks = aes_checks(data, [mission_record(), mission_record()])

        self.assertEqual(checks["nonce_crc32_duplicates"], 1)

    def test_missing_aes_fields_rejects_generic_battery(self):
        data = {"schema_version": "pqc-sat-final-metrics-v1", "summary": {}}
        checks = aes_checks(data, [{"payload": {"cipher": "HMAC-SHA256"}}])

        self.assertFalse(checks["official_candidate"])
        self.assertEqual(
            metrics_status(data, checks),
            "bateria geral incompatível com a consolidação AES-GCM",
        )

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
