/*
 * Host-side helper to derive the deterministic PQC-SAT ML-KEM-512 KAT.
 *
 * Build from the repository root with:
 *   gcc -std=c99 -O2 \
 *     -DMLK_CONFIG_PARAMETER_SET=512 \
 *     -DMLK_CONFIG_NAMESPACE_PREFIX=PQC_SAT_MLKEM512 \
 *     -DMLK_CONFIG_NO_RANDOMIZED_API \
 *     -Ifirmware/lib/mlkem_native/src \
 *     -Ifirmware/lib/mlkem_native/src/src \
 *     tools/mlkem_kat_vector.c \
 *     firmware/lib/mlkem_native/src/src/*.c \
 *     firmware/lib/mlkem_native/src/src/fips202/*.c \
 *     -o /tmp/pqc-sat-mlkem-kat
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "mlkem_native.h"

static uint32_t crc32_bytes(const uint8_t *data, size_t len) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      const uint32_t mask = (uint32_t)(-(int32_t)(crc & 1u));
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return ~crc;
}

static void print_bytes(const char *name, const uint8_t *data, size_t len) {
  printf("%s=", name);
  for (size_t i = 0; i < len; ++i) {
    printf("%02X", data[i]);
  }
  printf("\n");
}

int main(void) {
  uint8_t pk[CRYPTO_PUBLICKEYBYTES];
  uint8_t sk[CRYPTO_SECRETKEYBYTES];
  uint8_t ct[CRYPTO_CIPHERTEXTBYTES];
  uint8_t ss_enc[CRYPTO_BYTES];
  uint8_t ss_dec[CRYPTO_BYTES];
  uint8_t keygen_coins[2 * CRYPTO_SYMBYTES];
  uint8_t encap_coins[CRYPTO_SYMBYTES];

  for (size_t i = 0; i < sizeof(keygen_coins); ++i) {
    keygen_coins[i] = (uint8_t)(0xA5u ^ (uint8_t)(i * 17u + 3u));
  }
  for (size_t i = 0; i < sizeof(encap_coins); ++i) {
    encap_coins[i] = (uint8_t)(0x5Au ^ (uint8_t)(i * 29u + 7u));
  }

  if (crypto_kem_keypair_derand(pk, sk, keygen_coins) != 0) {
    fprintf(stderr, "keypair_derand failed\n");
    return 1;
  }
  if (crypto_kem_enc_derand(ct, ss_enc, pk, encap_coins) != 0) {
    fprintf(stderr, "enc_derand failed\n");
    return 1;
  }
  if (crypto_kem_dec(ss_dec, ct, sk) != 0) {
    fprintf(stderr, "dec failed\n");
    return 1;
  }
  if (memcmp(ss_enc, ss_dec, sizeof(ss_enc)) != 0) {
    fprintf(stderr, "shared-secret mismatch\n");
    return 1;
  }

  printf("pk_bytes=%u\n", (unsigned)sizeof(pk));
  printf("sk_bytes=%u\n", (unsigned)sizeof(sk));
  printf("ct_bytes=%u\n", (unsigned)sizeof(ct));
  printf("ss_bytes=%u\n", (unsigned)sizeof(ss_enc));
  printf("pk_crc32=0x%08X\n", crc32_bytes(pk, sizeof(pk)));
  printf("ct_crc32=0x%08X\n", crc32_bytes(ct, sizeof(ct)));
  printf("ss_crc32=0x%08X\n", crc32_bytes(ss_enc, sizeof(ss_enc)));
  print_bytes("expected_ss", ss_enc, sizeof(ss_enc));
  return 0;
}
