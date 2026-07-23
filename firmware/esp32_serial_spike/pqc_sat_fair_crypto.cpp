#include "pqc_sat_fair_crypto.h"

#include <string.h>

#if defined(PQC_SAT_ENABLE_FAIR_CRYPTO) && __has_include(<wolfssl/wolfcrypt/settings.h>)
#define PQC_SAT_FAIR_CRYPTO_COMPILED 1
#include <wolfssl/wolfcrypt/settings.h>
#include <wolfssl/version.h>
#include <wolfssl/wolfcrypt/aes.h>
#include <wolfssl/wolfcrypt/ecc.h>
#include <wolfssl/wolfcrypt/error-crypt.h>
#include <wolfssl/wolfcrypt/hmac.h>
#include <wolfssl/wolfcrypt/random.h>
#include <wolfssl/wolfcrypt/wc_mlkem.h>
#else
#define PQC_SAT_FAIR_CRYPTO_COMPILED 0
#endif

#if defined(PQC_SAT_REQUIRE_FAIR_CRYPTO) && !PQC_SAT_FAIR_CRYPTO_COMPILED
#error "KEX_FAIR_V1 requires wolfSSL 5.9.2 at firmware/lib/wolfssl"
#endif

#if PQC_SAT_FAIR_CRYPTO_COMPILED
#if !defined(NO_ESP32_CRYPT) || !defined(WOLFSSL_NO_ASM) || !defined(WC_MLKEM_NO_ASM)
#error "KEX_FAIR_V1 must compile without ESP32 crypto acceleration or assembly"
#endif
#if !defined(WOLFSSL_HAVE_SP_ECC) || !defined(SP_WORD_SIZE) || SP_WORD_SIZE != 32
#error "KEX_FAIR_V1 requires the portable 32-bit SP ECC backend for P-256"
#endif

static bool constant_time_equal(const uint8_t *left, const uint8_t *right, size_t len) {
  uint8_t diff = 0;
  for (size_t i = 0; i < len; ++i) {
    diff |= static_cast<uint8_t>(left[i] ^ right[i]);
  }
  return diff == 0;
}

static void reset_outputs(
    uint8_t sender_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t receiver_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t setup_material[FAIR_MAX_SETUP_BYTES],
    size_t *setup_len,
    uint8_t response_material[FAIR_MAX_RESPONSE_BYTES],
    size_t *response_len,
    FairKexMetrics *metrics) {
  memset(sender_secret, 0, FAIR_SHARED_SECRET_BYTES);
  memset(receiver_secret, 0, FAIR_SHARED_SECRET_BYTES);
  memset(setup_material, 0, FAIR_MAX_SETUP_BYTES);
  memset(response_material, 0, FAIR_MAX_RESPONSE_BYTES);
  *setup_len = 0;
  *response_len = 0;
  memset(metrics, 0, sizeof(*metrics));
}

static int establish_ecdh(
    WC_RNG *rng,
    uint8_t sender_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t receiver_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t setup_material[FAIR_MAX_SETUP_BYTES],
    size_t *setup_len,
    uint8_t response_material[FAIR_MAX_RESPONSE_BYTES],
    size_t *response_len,
    FairKexMetrics *metrics) {
  ecc_key responder_private;
  ecc_key responder_public;
  ecc_key initiator_private;
  ecc_key initiator_public;
  wc_ecc_init(&responder_private);
  wc_ecc_init(&responder_public);
  wc_ecc_init(&initiator_private);
  wc_ecc_init(&initiator_public);

  int rc = 0;
  word32 encoded_len = FAIR_ECDH_PUBLIC_BYTES;
  uint32_t started = micros();
  rc = wc_ecc_make_key_ex(rng, 32, &responder_private, ECC_SECP256R1);
  if (rc == 0) {
    rc = wc_ecc_export_x963(&responder_private, setup_material, &encoded_len);
  }
  metrics->setup_us = micros() - started;
  if (rc == 0 && encoded_len != FAIR_ECDH_PUBLIC_BYTES) {
    rc = BUFFER_E;
  }
  if (rc == 0) {
    *setup_len = encoded_len;
  }

  word32 shared_len = FAIR_SHARED_SECRET_BYTES;
  if (rc == 0) {
    started = micros();
    rc = wc_ecc_import_x963_ex(
        setup_material,
        static_cast<word32>(*setup_len),
        &responder_public,
        ECC_SECP256R1);
    if (rc == 0) {
      rc = wc_ecc_check_key(&responder_public);
    }
    if (rc == 0) {
      rc = wc_ecc_make_key_ex(rng, 32, &initiator_private, ECC_SECP256R1);
    }
    encoded_len = FAIR_ECDH_PUBLIC_BYTES;
    if (rc == 0) {
      rc = wc_ecc_export_x963(&initiator_private, response_material, &encoded_len);
    }
    if (rc == 0 && encoded_len != FAIR_ECDH_PUBLIC_BYTES) {
      rc = BUFFER_E;
    }
    if (rc == 0) {
      *response_len = encoded_len;
      shared_len = FAIR_SHARED_SECRET_BYTES;
      rc = wc_ecc_shared_secret(
          &initiator_private,
          &responder_public,
          sender_secret,
          &shared_len);
    }
    if (rc == 0 && shared_len != FAIR_SHARED_SECRET_BYTES) {
      rc = BUFFER_E;
    }
    metrics->initiator_us = micros() - started;
  }

  if (rc == 0) {
    started = micros();
    rc = wc_ecc_import_x963_ex(
        response_material,
        static_cast<word32>(*response_len),
        &initiator_public,
        ECC_SECP256R1);
    if (rc == 0) {
      rc = wc_ecc_check_key(&initiator_public);
    }
    shared_len = FAIR_SHARED_SECRET_BYTES;
    if (rc == 0) {
      rc = wc_ecc_shared_secret(
          &responder_private,
          &initiator_public,
          receiver_secret,
          &shared_len);
    }
    if (rc == 0 && shared_len != FAIR_SHARED_SECRET_BYTES) {
      rc = BUFFER_E;
    }
    metrics->responder_us = micros() - started;
  }

  wc_ecc_free(&initiator_public);
  wc_ecc_free(&initiator_private);
  wc_ecc_free(&responder_public);
  wc_ecc_free(&responder_private);
  return rc;
}

static int establish_mlkem(
    WC_RNG *rng,
    uint8_t sender_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t receiver_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t setup_material[FAIR_MAX_SETUP_BYTES],
    size_t *setup_len,
    uint8_t response_material[FAIR_MAX_RESPONSE_BYTES],
    size_t *response_len,
    FairKexMetrics *metrics) {
  MlKemKey responder;
  MlKemKey initiator;
  int rc = wc_MlKemKey_Init(&responder, WC_ML_KEM_512, nullptr, INVALID_DEVID);
  if (rc != 0) {
    return rc;
  }
  rc = wc_MlKemKey_Init(&initiator, WC_ML_KEM_512, nullptr, INVALID_DEVID);
  if (rc != 0) {
    wc_MlKemKey_Free(&responder);
    return rc;
  }

  uint32_t started = micros();
  rc = wc_MlKemKey_MakeKey(&responder, rng);
  word32 public_len = FAIR_MLKEM_PUBLIC_BYTES;
  if (rc == 0) {
    rc = wc_MlKemKey_EncodePublicKey(&responder, setup_material, public_len);
  }
  metrics->setup_us = micros() - started;
  if (rc == 0) {
    *setup_len = public_len;
  }

  if (rc == 0) {
    started = micros();
    rc = wc_MlKemKey_DecodePublicKey(&initiator, setup_material, public_len);
    if (rc == 0) {
      rc = wc_MlKemKey_Encapsulate(
          &initiator,
          response_material,
          sender_secret,
          rng);
    }
    metrics->initiator_us = micros() - started;
    if (rc == 0) {
      *response_len = FAIR_MLKEM_CIPHERTEXT_BYTES;
    }
  }

  if (rc == 0) {
    started = micros();
    rc = wc_MlKemKey_Decapsulate(
        &responder,
        receiver_secret,
        response_material,
        static_cast<word32>(*response_len));
    metrics->responder_us = micros() - started;
  }

  wc_MlKemKey_Free(&initiator);
  wc_MlKemKey_Free(&responder);
  return rc;
}
#endif

bool fair_crypto_available() {
  return PQC_SAT_FAIR_CRYPTO_COMPILED == 1;
}

const char *fair_crypto_version() {
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  return LIBWOLFSSL_VERSION_STRING;
#else
  return "unavailable";
#endif
}

const char *fair_crypto_backend() {
  return PQC_SAT_FAIR_CRYPTO_COMPILED ? "wolfCrypt-portable" : "unavailable";
}

const char *fair_kex_name(FairKexAlgorithm algorithm) {
  return algorithm == FAIR_KEX_ECDH_P256 ? "ECDH-P256" : "ML-KEM-512";
}

int fair_kex_establish(
    FairKexAlgorithm algorithm,
    uint8_t sender_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t receiver_secret[FAIR_SHARED_SECRET_BYTES],
    uint8_t setup_material[FAIR_MAX_SETUP_BYTES],
    size_t *setup_len,
    uint8_t response_material[FAIR_MAX_RESPONSE_BYTES],
    size_t *response_len,
    FairKexMetrics *metrics) {
  if (sender_secret == nullptr || receiver_secret == nullptr ||
      setup_material == nullptr || setup_len == nullptr ||
      response_material == nullptr || response_len == nullptr ||
      metrics == nullptr) {
    return -1;
  }
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  reset_outputs(
      sender_secret,
      receiver_secret,
      setup_material,
      setup_len,
      response_material,
      response_len,
      metrics);
  WC_RNG rng = {};
  int rc = wc_InitRng(&rng);
  if (rc == 0) {
    rc = algorithm == FAIR_KEX_ECDH_P256
             ? establish_ecdh(
                   &rng,
                   sender_secret,
                   receiver_secret,
                   setup_material,
                   setup_len,
                   response_material,
                   response_len,
                   metrics)
             : establish_mlkem(
                   &rng,
                   sender_secret,
                   receiver_secret,
                   setup_material,
                   setup_len,
                   response_material,
                   response_len,
                   metrics);
  }
  wc_FreeRng(&rng);
  metrics->setup_bytes = *setup_len;
  metrics->response_bytes = *response_len;
  metrics->kex_total_us =
      metrics->setup_us + metrics->initiator_us + metrics->responder_us;
  metrics->key_match =
      rc == 0 && constant_time_equal(
                     sender_secret,
                     receiver_secret,
                     FAIR_SHARED_SECRET_BYTES);
  metrics->rc = rc;
  return metrics->key_match ? 0 : (rc == 0 ? -2 : rc);
#else
  (void)algorithm;
  return -3;
#endif
}

int fair_hkdf_aes128(
    const uint8_t *secret,
    size_t secret_len,
    const char *context,
    uint8_t out_key[FAIR_AES128_KEY_BYTES]) {
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  static const uint8_t salt[] = "PQC-SAT|KEX_FAIR_V1|HKDF-SHA256";
  if (secret == nullptr || context == nullptr || out_key == nullptr) {
    return BAD_FUNC_ARG;
  }
  return wc_HKDF(
      WC_SHA256,
      secret,
      static_cast<word32>(secret_len),
      salt,
      sizeof(salt) - 1U,
      reinterpret_cast<const uint8_t *>(context),
      static_cast<word32>(strlen(context)),
      out_key,
      FAIR_AES128_KEY_BYTES);
#else
  (void)secret;
  (void)secret_len;
  (void)context;
  (void)out_key;
  return -3;
#endif
}

int fair_random_bytes(uint8_t *out, size_t len) {
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  if (out == nullptr || len > UINT32_MAX) {
    return BAD_FUNC_ARG;
  }
  WC_RNG rng = {};
  int rc = wc_InitRng(&rng);
  if (rc == 0) {
    rc = wc_RNG_GenerateBlock(&rng, out, static_cast<word32>(len));
  }
  wc_FreeRng(&rng);
  return rc;
#else
  (void)out;
  (void)len;
  return -3;
#endif
}

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
    size_t tag_len) {
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  Aes aes = {};
  int rc = wc_AesInit(&aes, nullptr, INVALID_DEVID);
  if (rc == 0) {
    rc = wc_AesGcmSetKey(&aes, key, FAIR_AES128_KEY_BYTES);
  }
  if (rc == 0) {
    rc = wc_AesGcmEncrypt(
        &aes,
        ciphertext,
        plaintext,
        static_cast<word32>(plaintext_len),
        nonce,
        static_cast<word32>(nonce_len),
        tag,
        static_cast<word32>(tag_len),
        aad,
        static_cast<word32>(aad_len));
  }
  wc_AesFree(&aes);
  return rc;
#else
  (void)key; (void)nonce; (void)nonce_len; (void)aad; (void)aad_len;
  (void)plaintext; (void)plaintext_len; (void)ciphertext; (void)tag; (void)tag_len;
  return -3;
#endif
}

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
    uint8_t *plaintext) {
#if PQC_SAT_FAIR_CRYPTO_COMPILED
  Aes aes = {};
  int rc = wc_AesInit(&aes, nullptr, INVALID_DEVID);
  if (rc == 0) {
    rc = wc_AesGcmSetKey(&aes, key, FAIR_AES128_KEY_BYTES);
  }
  if (rc == 0) {
    rc = wc_AesGcmDecrypt(
        &aes,
        plaintext,
        ciphertext,
        static_cast<word32>(ciphertext_len),
        nonce,
        static_cast<word32>(nonce_len),
        tag,
        static_cast<word32>(tag_len),
        aad,
        static_cast<word32>(aad_len));
  }
  wc_AesFree(&aes);
  return rc;
#else
  (void)key; (void)nonce; (void)nonce_len; (void)aad; (void)aad_len;
  (void)ciphertext; (void)ciphertext_len; (void)tag; (void)tag_len; (void)plaintext;
  return -3;
#endif
}
