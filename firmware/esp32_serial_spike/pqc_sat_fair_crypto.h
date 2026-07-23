#pragma once

#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

static constexpr size_t FAIR_SHARED_SECRET_BYTES = 32;
static constexpr size_t FAIR_AES128_KEY_BYTES = 16;
static constexpr size_t FAIR_ECDH_PUBLIC_BYTES = 65;
static constexpr size_t FAIR_MLKEM_PUBLIC_BYTES = 800;
static constexpr size_t FAIR_MLKEM_CIPHERTEXT_BYTES = 768;
static constexpr size_t FAIR_MAX_SETUP_BYTES = FAIR_MLKEM_PUBLIC_BYTES;
static constexpr size_t FAIR_MAX_RESPONSE_BYTES = FAIR_MLKEM_CIPHERTEXT_BYTES;

enum FairKexAlgorithm : uint8_t {
  FAIR_KEX_ECDH_P256 = 0,
  FAIR_KEX_MLKEM512 = 1,
};

struct FairKexMetrics {
  uint32_t setup_us;
  uint32_t initiator_us;
  uint32_t responder_us;
  uint32_t kex_total_us;
  uint32_t setup_bytes;
  uint32_t response_bytes;
  bool key_match;
  int rc;
};

bool fair_crypto_available();
const char *fair_crypto_version();
const char *fair_crypto_backend();
const char *fair_kex_name(FairKexAlgorithm algorithm);

int fair_kex_establish(
    FairKexAlgorithm algorithm,
    uint8_t sender_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t receiver_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t setup_material[FAIR_MAX_SETUP_BYTES],
    size_t *setup_len,
    uint8_t response_material[FAIR_MAX_RESPONSE_BYTES],
    size_t *response_len,
    FairKexMetrics *metrics);

int fair_hkdf_aes128(
    const uint8_t *secret,
    size_t secret_len,
    const char *context,
    uint8_t out_key[FAIR_AES128_KEY_BYTES]);

int fair_random_bytes(uint8_t *out, size_t len);

int fair_aes128_gcm_encrypt(
    const uint8_t key[FAIR_AES128_KEY_BYTES],
    const uint8_t *nonce,
    size_t nonce_len,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *plaintext,
    size_t plaintext_len,
    uint8_t *ciphertext,
    uint8_t *tag,
    size_t tag_len);

int fair_aes128_gcm_decrypt(
    const uint8_t key[FAIR_AES128_KEY_BYTES],
    const uint8_t *nonce,
    size_t nonce_len,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *ciphertext,
    size_t ciphertext_len,
    const uint8_t *tag,
    size_t tag_len,
    uint8_t *plaintext);
