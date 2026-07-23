#ifndef PQC_SAT_WOLFSSL_USER_SETTINGS_H
#define PQC_SAT_WOLFSSL_USER_SETTINGS_H

/*
 * Reproducible wolfCrypt-only configuration for KEX_FAIR_V1.
 *
 * Both P-256 and ML-KEM-512 use the same wolfCrypt release, RNG, SHA-256,
 * HKDF and AES-GCM implementation. Target-specific assembly and ESP32 crypto
 * acceleration are intentionally disabled. Generic compiler optimization is
 * kept equal for both algorithms.
 */
#define WOLFSSL_USER_SETTINGS_ID "PQC-SAT KEX_FAIR_V1 portable software"
#define WOLFSSL_IGNORE_FILE_WARN
#undef WOLFSSL_ESPIDF
#define WOLFCRYPT_ONLY
#define NO_TLS
#define NO_FILESYSTEM
#define WOLFSSL_NO_SOCK
#define NO_WRITEV
#define SINGLE_THREADED

#define NO_RSA
#define NO_DH
#define NO_DSA
#define NO_RC4
#define NO_MD4
#define NO_DES3
#define NO_PSK

#define HAVE_ECC
#define HAVE_ECC_DHE
#define HAVE_ECC_KEY_IMPORT
#define HAVE_ECC_KEY_EXPORT
#define ECC_USER_CURVES
#define ECC_TIMING_RESISTANT
#undef NO_ECC256
#define SP_WORD_SIZE 32
#define WOLFSSL_SP_MATH
#define WOLFSSL_SP_SMALL
#define WOLFSSL_HAVE_SP_ECC

#define WOLFSSL_HAVE_MLKEM
#define WOLFSSL_NO_ML_KEM_768
#define WOLFSSL_NO_ML_KEM_1024
#define WOLFSSL_MLKEM_DYNAMIC_KEYS
#define WOLFSSL_MLKEM_MAKEKEY_SMALL_MEM
#define WOLFSSL_MLKEM_ENCAPSULATE_SMALL_MEM
#define WOLFSSL_SHA3
#define WOLFSSL_SHAKE128
#define WOLFSSL_SHAKE256

#define HAVE_HKDF
#define HAVE_AESGCM
#define WOLFSSL_AES
#define WOLFSSL_SMALL_STACK

/* FAIR_V1 forbids target-specific crypto and assembly for every primitive. */
#define NO_ESP32_CRYPT
#define NO_WOLFSSL_ESP32_CRYPT_HASH
#define NO_WOLFSSL_ESP32_CRYPT_AES
#define NO_WOLFSSL_ESP32_CRYPT_RSA_PRI
#define WOLFSSL_NO_ASM
#define TFM_NO_ASM
#define WC_MLKEM_NO_ASM

#endif
