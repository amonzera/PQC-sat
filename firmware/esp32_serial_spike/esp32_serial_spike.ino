/*
  PQC-SAT firmware for RoboCore BlackBoard Wisdom.

  Goal for this stage:
  - own the serial bridge protocol used by the notebook;
  - expose a reproducible inventory of the Wisdom board;
  - test every onboard feature;
  - run a small payload fault/CRC32 experiment;
  - preserve the historical CLASSIC/PQC mission modes;
  - compare ECDH P-256 and ML-KEM-512 through the same portable wolfCrypt stack;
  - run ML-KEM-512 through a vendored C-only mlkem-native backend.
*/

#include <Arduino.h>
#include <esp_arduino_version.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <WiFi.h>
#include <Wire.h>
#include <string.h>

#include "mbedtls/md.h"
#include "mbedtls/gcm.h"

#include <mlkem_native.h>

#include "pqc_sat_fair_crypto.h"

#if defined(CONFIG_BT_ENABLED)
#include "esp_bt.h"
#endif

SET_LOOP_TASK_STACK_SIZE(32768);

// ---- Protocol ---------------------------------------------------------------
static constexpr uint32_t SERIAL_BAUD = 115200;
// INVESTIGATE carries up to 96 payload bytes as hex plus the reproducible
// incident vector. Commands remain short; FAIR responses may use up to the
// independent 4096-character host response limit.
static constexpr size_t MAX_FRAME_LEN = 384;
static constexpr size_t MAX_FIELDS = 14;
static constexpr size_t MAX_EXPERIMENT_PAYLOAD = 96;

static constexpr const char *PQC_TARGET = "ML-KEM-512";
static constexpr const char *PQC_BACKEND = "mlkem-native";
static constexpr const char *PQC_VARIANT = "FIPS203-512";
static constexpr const char *PQC_STATUS = "ready";
static constexpr const char *PQC_SOURCE = "pq-code-package/mlkem-native";
static constexpr const char *PQC_COMMIT = "d2cae2b";
static constexpr const char *PQC_LICENSE = "Apache2-ISC-MIT";
static constexpr const char *PQC_CONFIRMATION = "HMAC-SHA256";
static constexpr size_t PQC_CONFIRM_TAG_BYTES = 32;
static constexpr const char *AEAD_CIPHER = "AES-128-GCM";
static constexpr size_t AES128_KEY_BYTES = 16;
static constexpr size_t AES_GCM_NONCE_BYTES = 12;
static constexpr size_t AES_GCM_TAG_BYTES = 16;
static constexpr size_t MISSION_CRC_BYTES = 4;
static constexpr const char *CLASSIC_TARGET = AEAD_CIPHER;
static constexpr const char *MISSION_DEFAULT_PAYLOAD = "PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK";
static constexpr const char *FAIR_EXPERIMENT = "KEX_FAIR_V1";
static constexpr const char *FAIR_KDF = "HKDF-SHA256";
static constexpr const char *FAIR_OPTIMIZATION = "portable-software";
static constexpr const char *FAIR_BUILD_PROFILE = "robocore_wisdom_esp32_fair";
static constexpr const char *FAIR_SESSION_BENCH = "FAIR_SESSION_V1";
#define PQC_SAT_STRINGIFY_INNER(value) #value
#define PQC_SAT_STRINGIFY(value) PQC_SAT_STRINGIFY_INNER(value)
static constexpr const char *FAIR_FRAMEWORK =
    "arduino-esp32-"
    PQC_SAT_STRINGIFY(ESP_ARDUINO_VERSION_MAJOR) "."
    PQC_SAT_STRINGIFY(ESP_ARDUINO_VERSION_MINOR) "."
    PQC_SAT_STRINGIFY(ESP_ARDUINO_VERSION_PATCH);

static_assert(CRYPTO_PUBLICKEYBYTES == 800, "unexpected ML-KEM-512 public key size");
static_assert(CRYPTO_SECRETKEYBYTES == 1632, "unexpected ML-KEM-512 secret key size");
static_assert(CRYPTO_CIPHERTEXTBYTES == 768, "unexpected ML-KEM-512 ciphertext size");
static_assert(CRYPTO_BYTES == 32, "unexpected ML-KEM shared-secret size");

// ---- BlackBoard Wisdom pin map ---------------------------------------------
static constexpr int PIN_I2C_SDA = 21;
static constexpr int PIN_I2C_SCL = 22;

static constexpr int PIN_BAR_100 = 17;
static constexpr int PIN_BAR_75 = 16;
static constexpr int PIN_BAR_50 = 4;
static constexpr int PIN_BAR_25 = 13;
static constexpr int BAR_PINS[] = {PIN_BAR_25, PIN_BAR_50, PIN_BAR_75, PIN_BAR_100};
static constexpr size_t BAR_PIN_COUNT = sizeof(BAR_PINS) / sizeof(BAR_PINS[0]);

static constexpr int PIN_RGB_R = 19;
static constexpr int PIN_RGB_G = 23;
static constexpr int PIN_RGB_B = 18;
static constexpr int RGB_CH_R = 0;
static constexpr int RGB_CH_G = 1;
static constexpr int RGB_CH_B = 2;
static constexpr int RGB_PWM_FREQ = 5000;
static constexpr int RGB_PWM_BITS = 8;

static constexpr int PIN_SERVO_SIGNAL = 25;
static constexpr int SERVO_CH = 4;
static constexpr int SERVO_PWM_FREQ = 50;
static constexpr int SERVO_PWM_BITS = 16;

static constexpr int PIN_RELAY_SIGNAL = 33;
static constexpr int PIN_BUTTON = 27;
static constexpr int PIN_IR = 26;
static constexpr int PIN_SOUND = 36;  // VP / A36
static constexpr int PIN_POT = 39;    // VN / A39
static constexpr int PIN_ACCEL_INT1 = 34;
static constexpr int PIN_ACCEL_INT2 = 35;
static constexpr uint32_t BUTTON_DEBOUNCE_MS = 40;

#if !defined(LED_BUILTIN)
#define LED_BUILTIN 2
#endif

// ---- I2C addresses ----------------------------------------------------------
static constexpr uint8_t ADDR_APDS9960 = 0x39;
static constexpr uint8_t ADDR_HTU21D = 0x40;
static constexpr uint8_t ADDR_OLED_PRIMARY = 0x3C;
static constexpr uint8_t ADDR_OLED_SECONDARY = 0x3D;
static constexpr uint8_t ADDR_MMA8452_PRIMARY = 0x1D;
static constexpr uint8_t ADDR_MMA8452_SECONDARY = 0x1C;

static constexpr uint8_t OLED_WIDTH = 128;
static constexpr uint8_t OLED_HEIGHT = 64;
static constexpr size_t OLED_BUFFER_SIZE = (OLED_WIDTH * OLED_HEIGHT) / 8;

// ---- State ------------------------------------------------------------------
static char rx_buffer[MAX_FRAME_LEN + 1];
static size_t rx_len = 0;

static uint32_t command_count = 0;
static uint32_t error_count = 0;
static uint32_t telemetry_seq = 0;
static uint32_t boot_cpu_mhz = 0;

static const char *active_profile = "BASELINE";
static bool builtin_led_state = false;
static bool relay_state = false;
static bool rgb_common_anode = false;
static bool bar_active_low = false;
static uint8_t rgb_r = 0;
static uint8_t rgb_g = 0;
static uint8_t rgb_b = 0;
static uint8_t bar_level = 0;
static uint8_t bar_percent = 0;
static bool button_stable_pressed = false;
static bool button_candidate_pressed = false;
static uint32_t button_candidate_since_ms = 0;
static int servo_angle = -1;

static bool apds_present = false;
static bool htu_present = false;
static bool oled_present = false;
static bool mma_present = false;
static uint8_t oled_addr = 0;
static uint8_t mma_addr = 0;
static uint8_t oled_buffer[OLED_BUFFER_SIZE];

static uint8_t pqc_pk[CRYPTO_PUBLICKEYBYTES];
static uint8_t pqc_sk[CRYPTO_SECRETKEYBYTES];
static uint8_t pqc_ct[CRYPTO_CIPHERTEXTBYTES];
static uint8_t pqc_fault_ct[CRYPTO_CIPHERTEXTBYTES];
static uint8_t pqc_ss_enc[CRYPTO_BYTES];
static uint8_t pqc_ss_dec[CRYPTO_BYTES];
static uint8_t pqc_fault_tag_enc[PQC_CONFIRM_TAG_BYTES];
static uint8_t pqc_fault_tag_dec[PQC_CONFIRM_TAG_BYTES];
static bool pqc_keypair_ready = false;
static bool pqc_ciphertext_ready = false;
static bool pqc_shared_secret_ready = false;

static uint8_t fair_sender_secret[FAIR_SHARED_SECRET_BYTES];
static uint8_t fair_receiver_secret[FAIR_SHARED_SECRET_BYTES];
static uint8_t fair_setup_material[FAIR_MAX_SETUP_BYTES];
static uint8_t fair_response_material[FAIR_MAX_RESPONSE_BYTES];
static size_t fair_setup_len = 0;
static size_t fair_response_len = 0;

enum StagedGameState : uint8_t {
  GAME_IDLE = 0,
  GAME_PREPARED,
  GAME_PROTECTED,
  GAME_TRANSMITTED,
  GAME_VERIFIED,
  GAME_RETRIED,
};

struct StagedGameSession {
  bool active;
  StagedGameState state;
  char id[32];
  char profile[24];
  char key_mode[8];
  char guard[8];
  char incident[20];
  bool use_pqc;
  bool use_fair;
  FairKexAlgorithm fair_algorithm;
  bool use_app_crc;
  uint8_t payload[MAX_EXPERIMENT_PAYLOAD];
  size_t payload_len;
  uint8_t protected_payload[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  size_t protected_len;
  uint8_t ciphertext[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t decrypted[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t aes_key_enc[AES128_KEY_BYTES];
  uint8_t aes_key_dec[AES128_KEY_BYTES];
  uint8_t nonce[AES_GCM_NONCE_BYTES];
  uint8_t gcm_tag[AES_GCM_TAG_BYTES];
  uint32_t app_crc_tx;
  uint32_t frame_crc_tx;
  uint32_t frame_crc_rx;
  uint8_t byte_index;
  uint8_t bit_mask;
  uint8_t before_byte;
  uint8_t after_byte;
  bool key_match;
  bool frame_crc_match;
  bool aead_checked;
  bool aead_match;
  bool app_crc_checked;
  bool app_crc_match;
  bool accepted;
  char final_result[24];
  uint32_t keygen_us;
  uint32_t encap_us;
  uint32_t decap_us;
  uint32_t setup_us;
  uint32_t initiator_us;
  uint32_t responder_us;
  uint32_t kex_total_us;
  uint32_t setup_bytes;
  uint32_t response_bytes;
  uint32_t kdf_us;
  uint32_t rng_us;
  uint32_t encrypt_us;
  uint32_t decrypt_us;
  uint32_t protect_elapsed_us;
  uint32_t nonce_crc32;
  uint32_t session_key_crc32;
};

static StagedGameSession staged_game = {};

struct FairBenchTotals {
  uint64_t setup_us;
  uint64_t initiator_us;
  uint64_t responder_us;
  uint64_t total_us;
  uint16_t ok;
  int failure_rc;
};

static void clear_staged_game(bool restore_profile);

static uint8_t pqc_kat_pk[CRYPTO_PUBLICKEYBYTES];
static uint8_t pqc_kat_sk[CRYPTO_SECRETKEYBYTES];
static uint8_t pqc_kat_ct[CRYPTO_CIPHERTEXTBYTES];
static uint8_t pqc_kat_ss_enc[CRYPTO_BYTES];
static uint8_t pqc_kat_ss_dec[CRYPTO_BYTES];

static constexpr uint8_t PQC_KAT_EXPECTED_SS[CRYPTO_BYTES] = {
    0xA0, 0x21, 0x91, 0x08, 0xC1, 0xBF, 0xF6, 0xDE,
    0xA0, 0x11, 0x3B, 0x89, 0x8D, 0xEC, 0x16, 0xBC,
    0x69, 0x62, 0x0F, 0x88, 0xEF, 0x21, 0xBD, 0x40,
    0xA3, 0x4F, 0xD4, 0xA9, 0xAD, 0x93, 0xE1, 0x05,
};

extern "C" int randombytes(uint8_t *out, size_t outlen) {
  if (out == nullptr) {
    return -1;
  }

  size_t offset = 0;
  while (offset < outlen) {
    uint32_t word = esp_random();
    for (uint8_t i = 0; i < 4 && offset < outlen; ++i) {
      out[offset++] = static_cast<uint8_t>(word & 0xFFU);
      word >>= 8;
    }
  }
  return 0;
}

struct RobotPixel {
  uint8_t col;
  uint8_t row;
  char key;
};

// Same 12x8 pixel-art robot map used by dashboard.py, rendered in monochrome.
static constexpr RobotPixel ROBOT_PIXELS[] = {
    {3, 0, 'A'}, {4, 0, 'A'}, {7, 0, 'A'}, {8, 0, 'A'},
    {2, 1, 'H'}, {3, 1, 'H'}, {4, 1, 'H'}, {5, 1, 'H'}, {6, 1, 'H'}, {7, 1, 'H'}, {8, 1, 'H'}, {9, 1, 'H'},
    {1, 2, 'H'}, {2, 2, 'B'}, {3, 2, 'B'}, {4, 2, 'B'}, {5, 2, 'B'}, {6, 2, 'B'}, {7, 2, 'B'}, {8, 2, 'B'}, {9, 2, 'B'}, {10, 2, 'H'},
    {1, 3, 'H'}, {2, 3, 'B'}, {3, 3, 'E'}, {4, 3, 'E'}, {5, 3, 'B'}, {6, 3, 'B'}, {7, 3, 'E'}, {8, 3, 'E'}, {9, 3, 'B'}, {10, 3, 'H'},
    {1, 4, 'H'}, {2, 4, 'B'}, {3, 4, 'B'}, {4, 4, 'B'}, {5, 4, 'B'}, {6, 4, 'B'}, {7, 4, 'B'}, {8, 4, 'B'}, {9, 4, 'B'}, {10, 4, 'H'},
    {1, 5, 'H'}, {2, 5, 'B'}, {3, 5, 'S'}, {4, 5, 'B'}, {5, 5, 'B'}, {6, 5, 'B'}, {7, 5, 'B'}, {8, 5, 'S'}, {9, 5, 'B'}, {10, 5, 'H'},
    {1, 6, 'H'}, {2, 6, 'B'}, {3, 6, 'B'}, {4, 6, 'S'}, {5, 6, 'S'}, {6, 6, 'S'}, {7, 6, 'S'}, {8, 6, 'B'}, {9, 6, 'B'}, {10, 6, 'H'},
    {2, 7, 'H'}, {3, 7, 'H'}, {4, 7, 'H'}, {5, 7, 'H'}, {6, 7, 'H'}, {7, 7, 'H'}, {8, 7, 'H'}, {9, 7, 'H'},
};
static constexpr size_t ROBOT_PIXEL_COUNT = sizeof(ROBOT_PIXELS) / sizeof(ROBOT_PIXELS[0]);

// ---- Small helpers ----------------------------------------------------------
static void disable_radios() {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

#if defined(CONFIG_BT_ENABLED)
  btStop();
#endif
}

static void begin_result(const char *request_id, const char *status) {
  Serial.print("V1|");
  Serial.print(request_id);
  Serial.print("|RESULT|");
  Serial.print(status);
}

static void print_kv(const char *key, const char *value) {
  Serial.print("|");
  Serial.print(key);
  Serial.print("=");
  Serial.print(value);
}

static void print_kv_u32(const char *key, uint32_t value) {
  Serial.print("|");
  Serial.print(key);
  Serial.print("=");
  Serial.print(value);
}

static void print_kv_i32(const char *key, int32_t value) {
  Serial.print("|");
  Serial.print(key);
  Serial.print("=");
  Serial.print(value);
}

static void print_kv_bool(const char *key, bool value) {
  print_kv(key, value ? "1" : "0");
}

static void end_result() {
  Serial.println();
}

static void print_error(const char *request_id, const char *code, const char *detail) {
  error_count++;
  begin_result(request_id, "ERROR");
  print_kv("code", code);
  print_kv("detail", detail);
  end_result();
}

static bool is_token_safe(const char *value) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  for (const char *p = value; *p != '\0'; ++p) {
    if (*p == '|' || *p == '\r' || *p == '\n') {
      return false;
    }
  }
  return true;
}

static void uppercase_ascii(char *value) {
  for (char *p = value; *p != '\0'; ++p) {
    if (*p >= 'a' && *p <= 'z') {
      *p = static_cast<char>(*p - 'a' + 'A');
    }
  }
}

static bool parse_u8(const char *value, uint8_t *out) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  char *end = nullptr;
  long parsed = strtol(value, &end, 10);
  if (*end != '\0' || parsed < 0 || parsed > 255) {
    return false;
  }
  *out = static_cast<uint8_t>(parsed);
  return true;
}

static bool parse_int_range(const char *value, int min_value, int max_value, int *out) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  char *end = nullptr;
  long parsed = strtol(value, &end, 10);
  if (*end != '\0' || parsed < min_value || parsed > max_value) {
    return false;
  }
  *out = static_cast<int>(parsed);
  return true;
}

static bool parse_u8_auto(const char *value, uint8_t *out) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  char *end = nullptr;
  long parsed = strtol(value, &end, 0);
  if (*end != '\0') {
    parsed = strtol(value, &end, 16);
  }
  if (*end != '\0' || parsed < 0 || parsed > 255) {
    return false;
  }
  *out = static_cast<uint8_t>(parsed);
  return true;
}

static bool is_single_bit_mask(uint8_t value) {
  return value != 0 && (value & static_cast<uint8_t>(value - 1U)) == 0;
}

static int hex_nibble(char c) {
  if (c >= '0' && c <= '9') {
    return c - '0';
  }
  if (c >= 'a' && c <= 'f') {
    return c - 'a' + 10;
  }
  if (c >= 'A' && c <= 'F') {
    return c - 'A' + 10;
  }
  return -1;
}

static bool parse_hex_payload(const char *hex, uint8_t *out, size_t max_len, size_t *out_len) {
  if (hex == nullptr) {
    return false;
  }
  const size_t hex_len = strlen(hex);
  if (hex_len == 0 || (hex_len % 2U) != 0 || hex_len / 2U > max_len) {
    return false;
  }
  for (size_t i = 0; i < hex_len; i += 2) {
    const int hi = hex_nibble(hex[i]);
    const int lo = hex_nibble(hex[i + 1]);
    if (hi < 0 || lo < 0) {
      return false;
    }
    out[i / 2U] = static_cast<uint8_t>((hi << 4) | lo);
  }
  *out_len = hex_len / 2U;
  return true;
}

static uint32_t crc32_bytes(const uint8_t *data, size_t len) {
  uint32_t crc = 0xFFFFFFFFUL;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      const uint32_t mask = static_cast<uint32_t>(-(static_cast<int32_t>(crc & 1U)));
      crc = (crc >> 1) ^ (0xEDB88320UL & mask);
    }
  }
  return ~crc;
}

static void print_kv_hex_u8(const char *key, uint8_t value) {
  char buffer[5];
  snprintf(buffer, sizeof(buffer), "0x%02X", value);
  print_kv(key, buffer);
}

static void print_kv_hex_u32(const char *key, uint32_t value) {
  char buffer[11];
  snprintf(buffer, sizeof(buffer), "0x%08lX", static_cast<unsigned long>(value));
  print_kv(key, buffer);
}

static size_t split_fields(char *line, char *fields[], size_t max_fields) {
  if (line == nullptr || line[0] == '\0' || max_fields == 0) {
    return 0;
  }

  size_t count = 1;
  fields[0] = line;

  for (char *p = line; *p != '\0'; ++p) {
    if (*p == '|') {
      if (count >= max_fields) {
        return 0;
      }
      *p = '\0';
      fields[count++] = p + 1;
    }
  }

  for (size_t i = 0; i < count; ++i) {
    if (!is_token_safe(fields[i])) {
      return 0;
    }
  }

  return count;
}

// ---- I2C helpers ------------------------------------------------------------
static bool i2c_present(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

static bool i2c_read_reg8(uint8_t address, uint8_t reg, uint8_t *value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(static_cast<int>(address), 1) != 1) {
    return false;
  }
  *value = Wire.read();
  return true;
}

static bool i2c_write_reg8(uint8_t address, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

static void refresh_peripheral_presence() {
  apds_present = i2c_present(ADDR_APDS9960);
  htu_present = i2c_present(ADDR_HTU21D);

  if (i2c_present(ADDR_OLED_PRIMARY)) {
    oled_present = true;
    oled_addr = ADDR_OLED_PRIMARY;
  } else if (i2c_present(ADDR_OLED_SECONDARY)) {
    oled_present = true;
    oled_addr = ADDR_OLED_SECONDARY;
  } else {
    oled_present = false;
    oled_addr = 0;
  }

  if (i2c_present(ADDR_MMA8452_PRIMARY)) {
    mma_present = true;
    mma_addr = ADDR_MMA8452_PRIMARY;
  } else if (i2c_present(ADDR_MMA8452_SECONDARY)) {
    mma_present = true;
    mma_addr = ADDR_MMA8452_SECONDARY;
  } else {
    mma_present = false;
    mma_addr = 0;
  }
}

// ---- Board outputs ----------------------------------------------------------
static void apply_rgb() {
  const uint8_t out_r = rgb_common_anode ? (255 - rgb_r) : rgb_r;
  const uint8_t out_g = rgb_common_anode ? (255 - rgb_g) : rgb_g;
  const uint8_t out_b = rgb_common_anode ? (255 - rgb_b) : rgb_b;
  ledcWrite(RGB_CH_R, out_r);
  ledcWrite(RGB_CH_G, out_g);
  ledcWrite(RGB_CH_B, out_b);
}

static void set_rgb(uint8_t r, uint8_t g, uint8_t b) {
  rgb_r = r;
  rgb_g = g;
  rgb_b = b;
  apply_rgb();
}

static void set_builtin_indicator(bool enabled) {
  builtin_led_state = enabled;
  digitalWrite(LED_BUILTIN, enabled ? HIGH : LOW);
}

static void set_main_led_rgb(uint8_t r, uint8_t g, uint8_t b) {
  set_builtin_indicator(r != 0 || g != 0 || b != 0);
  set_rgb(r, g, b);
}

static bool color_from_name(const char *name, uint8_t *r, uint8_t *g, uint8_t *b) {
  if (strcmp(name, "WHITE") == 0 || strcmp(name, "ON") == 0) {
    *r = 255;
    *g = 255;
    *b = 255;
  } else if (strcmp(name, "RED") == 0) {
    *r = 255;
    *g = 0;
    *b = 0;
  } else if (strcmp(name, "GREEN") == 0) {
    *r = 0;
    *g = 255;
    *b = 0;
  } else if (strcmp(name, "BLUE") == 0) {
    *r = 0;
    *g = 0;
    *b = 255;
  } else if (strcmp(name, "CYAN") == 0) {
    *r = 0;
    *g = 255;
    *b = 255;
  } else if (strcmp(name, "MAGENTA") == 0) {
    *r = 255;
    *g = 0;
    *b = 255;
  } else if (strcmp(name, "YELLOW") == 0) {
    *r = 255;
    *g = 180;
    *b = 0;
  } else {
    return false;
  }
  return true;
}

static void rgb_test_pattern() {
  const uint8_t saved_r = rgb_r;
  const uint8_t saved_g = rgb_g;
  const uint8_t saved_b = rgb_b;
  const bool saved_builtin = builtin_led_state;

  set_main_led_rgb(255, 0, 0);
  delay(120);
  set_main_led_rgb(0, 255, 0);
  delay(120);
  set_main_led_rgb(0, 0, 255);
  delay(120);
  set_main_led_rgb(255, 255, 255);
  delay(120);
  set_rgb(saved_r, saved_g, saved_b);
  set_builtin_indicator(saved_builtin);
}

static void apply_bargraph() {
  for (size_t i = 0; i < BAR_PIN_COUNT; ++i) {
    const bool enabled = i < bar_level;
    digitalWrite(BAR_PINS[i], enabled == bar_active_low ? LOW : HIGH);
  }
}

static void set_bar_level(uint8_t level) {
  if (level > BAR_PIN_COUNT) {
    level = BAR_PIN_COUNT;
  }
  bar_level = level;
  bar_percent = static_cast<uint8_t>(level * 25U);
  apply_bargraph();
}

static void set_bar_percent(uint8_t percent) {
  if (percent > 100) {
    percent = 100;
  }
  bar_percent = percent;
  bar_level = static_cast<uint8_t>((static_cast<uint16_t>(percent) * BAR_PIN_COUNT + 99U) / 100U);
  if (bar_level > BAR_PIN_COUNT) {
    bar_level = BAR_PIN_COUNT;
  }
  apply_bargraph();
}

static void bargraph_test_pattern() {
  const uint8_t saved_level = bar_level;
  const uint8_t saved_percent = bar_percent;
  for (uint8_t level = 0; level <= BAR_PIN_COUNT; ++level) {
    set_bar_level(level);
    delay(100);
  }
  for (int level = static_cast<int>(BAR_PIN_COUNT) - 1; level >= 0; --level) {
    set_bar_level(static_cast<uint8_t>(level));
    delay(80);
  }
  bar_level = saved_level;
  bar_percent = saved_percent;
  apply_bargraph();
}

static void set_relay(bool enabled) {
  relay_state = enabled;
  digitalWrite(PIN_RELAY_SIGNAL, enabled ? HIGH : LOW);
}

static void set_servo_angle(int angle) {
  if (angle < 0) {
    ledcWrite(SERVO_CH, 0);
    servo_angle = -1;
    return;
  }
  if (angle > 180) {
    angle = 180;
  }
  const uint32_t pulse_us = 500 + (static_cast<uint32_t>(angle) * 2000UL) / 180UL;
  const uint32_t duty = (pulse_us * ((1UL << SERVO_PWM_BITS) - 1UL)) / 20000UL;
  ledcWrite(SERVO_CH, duty);
  servo_angle = angle;
}

// ---- OLED minimal SSD1306 support ------------------------------------------
static bool oled_command(uint8_t command) {
  if (!oled_present) {
    return false;
  }
  Wire.beginTransmission(oled_addr);
  Wire.write(0x00);
  Wire.write(command);
  return Wire.endTransmission() == 0;
}

static bool oled_command2(uint8_t command, uint8_t value) {
  return oled_command(command) && oled_command(value);
}

static bool oled_data_chunk(uint8_t value, size_t count) {
  if (!oled_present) {
    return false;
  }
  while (count > 0) {
    const size_t chunk = min(static_cast<size_t>(16), count);
    Wire.beginTransmission(oled_addr);
    Wire.write(0x40);
    for (size_t i = 0; i < chunk; ++i) {
      Wire.write(value);
    }
    if (Wire.endTransmission() != 0) {
      return false;
    }
    count -= chunk;
  }
  return true;
}

static bool oled_data_buffer_chunk(const uint8_t *data, size_t count) {
  if (!oled_present) {
    return false;
  }
  size_t offset = 0;
  while (offset < count) {
    const size_t chunk = min(static_cast<size_t>(16), count - offset);
    Wire.beginTransmission(oled_addr);
    Wire.write(0x40);
    for (size_t i = 0; i < chunk; ++i) {
      Wire.write(data[offset + i]);
    }
    if (Wire.endTransmission() != 0) {
      return false;
    }
    offset += chunk;
  }
  return true;
}

static void oled_clear_buffer() {
  memset(oled_buffer, 0, sizeof(oled_buffer));
}

static void oled_set_pixel(int x, int y, bool on = true) {
  if (x < 0 || x >= OLED_WIDTH || y < 0 || y >= OLED_HEIGHT) {
    return;
  }
  const size_t index = static_cast<size_t>(x) + (static_cast<size_t>(y) / 8U) * OLED_WIDTH;
  const uint8_t mask = 1U << (static_cast<uint8_t>(y) & 7U);
  if (on) {
    oled_buffer[index] |= mask;
  } else {
    oled_buffer[index] &= ~mask;
  }
}

static void oled_fill_rect(int x, int y, int w, int h, bool on = true) {
  for (int yy = y; yy < y + h; ++yy) {
    for (int xx = x; xx < x + w; ++xx) {
      oled_set_pixel(xx, yy, on);
    }
  }
}

static void oled_draw_rect(int x, int y, int w, int h, bool on = true) {
  for (int xx = x; xx < x + w; ++xx) {
    oled_set_pixel(xx, y, on);
    oled_set_pixel(xx, y + h - 1, on);
  }
  for (int yy = y; yy < y + h; ++yy) {
    oled_set_pixel(x, yy, on);
    oled_set_pixel(x + w - 1, yy, on);
  }
}

static void oled_draw_hline(int x, int y, int w, bool on = true) {
  for (int xx = x; xx < x + w; ++xx) {
    oled_set_pixel(xx, y, on);
  }
}

static void oled_draw_vline(int x, int y, int h, bool on = true) {
  for (int yy = y; yy < y + h; ++yy) {
    oled_set_pixel(x, yy, on);
  }
}

static bool oled_flush_buffer() {
  if (!oled_present) {
    return false;
  }
  for (uint8_t page = 0; page < 8; ++page) {
    oled_command(0xB0 | page);
    oled_command(0x00);
    oled_command(0x10);
    if (!oled_data_buffer_chunk(&oled_buffer[static_cast<size_t>(page) * OLED_WIDTH], OLED_WIDTH)) {
      return false;
    }
  }
  return true;
}

static bool oled_clear() {
  if (!oled_present) {
    return false;
  }
  oled_clear_buffer();
  for (uint8_t page = 0; page < 8; ++page) {
    oled_command(0xB0 | page);
    oled_command(0x00);
    oled_command(0x10);
    if (!oled_data_chunk(0x00, 128)) {
      return false;
    }
  }
  return true;
}

static void oled_draw_robot_satellite_icon() {
  oled_clear_buffer();

  // Solar panels.
  oled_draw_rect(8, 24, 24, 18);
  oled_draw_rect(96, 24, 24, 18);
  oled_draw_vline(16, 24, 18);
  oled_draw_vline(24, 24, 18);
  oled_draw_vline(104, 24, 18);
  oled_draw_vline(112, 24, 18);
  oled_draw_hline(8, 30, 24);
  oled_draw_hline(8, 36, 24);
  oled_draw_hline(96, 30, 24);
  oled_draw_hline(96, 36, 24);

  // CubeSat body and connection arms.
  oled_draw_hline(32, 33, 9);
  oled_draw_hline(87, 33, 9);
  oled_draw_rect(39, 14, 50, 38);
  oled_draw_rect(42, 17, 44, 32);

  // Antenna and status beacon.
  oled_draw_vline(64, 7, 7);
  oled_set_pixel(63, 6);
  oled_set_pixel(64, 5);
  oled_set_pixel(65, 6);

  // Pixel-art robot from dashboard.py, scaled to 3x3 pixels.
  static constexpr int robot_x = 46;
  static constexpr int robot_y = 22;
  static constexpr int scale = 3;
  for (size_t i = 0; i < ROBOT_PIXEL_COUNT; ++i) {
    const RobotPixel &p = ROBOT_PIXELS[i];
    oled_fill_rect(robot_x + p.col * scale, robot_y + p.row * scale, scale, scale, true);
  }

  // Re-open a few monochrome details so eyes/smile remain readable on OLED.
  oled_fill_rect(robot_x + 3 * scale + 1, robot_y + 3 * scale + 1, scale - 1, scale - 1, false);
  oled_fill_rect(robot_x + 7 * scale + 1, robot_y + 3 * scale + 1, scale - 1, scale - 1, false);
  oled_draw_hline(robot_x + 4 * scale, robot_y + 6 * scale + 1, 4 * scale);

  // Minimal orbit cue.
  for (int x = 28; x <= 100; x += 6) {
    const int y = 58 + ((x / 6) % 2);
    oled_set_pixel(x, y);
    oled_set_pixel(x + 1, y);
  }
}

static bool oled_show_standby_icon() {
  if (!oled_present) {
    return false;
  }
  oled_draw_robot_satellite_icon();
  return oled_flush_buffer();
}

static bool oled_test_pattern() {
  if (!oled_present) {
    return false;
  }
  for (uint8_t page = 0; page < 8; ++page) {
    oled_command(0xB0 | page);
    oled_command(0x00);
    oled_command(0x10);
    for (uint8_t block = 0; block < 8; ++block) {
      Wire.beginTransmission(oled_addr);
      Wire.write(0x40);
      for (uint8_t i = 0; i < 16; ++i) {
        Wire.write(((block + page) % 2 == 0) ? 0xAA : 0x55);
      }
      if (Wire.endTransmission() != 0) {
        return false;
      }
    }
  }
  return true;
}

static bool oled_init() {
  if (!oled_present) {
    return false;
  }
  delay(20);
  oled_command(0xAE);
  oled_command2(0xD5, 0x80);
  oled_command2(0xA8, 0x3F);
  oled_command2(0xD3, 0x00);
  oled_command(0x40);
  oled_command2(0x8D, 0x14);
  oled_command2(0x20, 0x00);
  oled_command(0xA1);
  oled_command(0xC8);
  oled_command2(0xDA, 0x12);
  oled_command2(0x81, 0x7F);
  oled_command2(0xD9, 0xF1);
  oled_command2(0xDB, 0x40);
  oled_command(0xA4);
  oled_command(0xA6);
  oled_command(0xAF);
  return oled_show_standby_icon();
}

// ---- Sensors ----------------------------------------------------------------
static bool htu21d_read_temperature_c(float *temperature_c) {
  if (!htu_present) {
    return false;
  }
  Wire.beginTransmission(ADDR_HTU21D);
  Wire.write(0xF3);  // trigger temperature measurement, no hold master
  if (Wire.endTransmission() != 0) {
    return false;
  }
  delay(60);
  if (Wire.requestFrom(static_cast<int>(ADDR_HTU21D), 3) < 2) {
    return false;
  }
  const uint16_t raw = (static_cast<uint16_t>(Wire.read()) << 8) | Wire.read();
  *temperature_c = -46.85f + (175.72f * static_cast<float>(raw & 0xFFFC)) / 65536.0f;
  return true;
}

static bool htu21d_read_humidity(float *humidity_pct) {
  if (!htu_present) {
    return false;
  }
  Wire.beginTransmission(ADDR_HTU21D);
  Wire.write(0xF5);  // trigger humidity measurement, no hold master
  if (Wire.endTransmission() != 0) {
    return false;
  }
  delay(35);
  if (Wire.requestFrom(static_cast<int>(ADDR_HTU21D), 3) < 2) {
    return false;
  }
  const uint16_t raw = (static_cast<uint16_t>(Wire.read()) << 8) | Wire.read();
  *humidity_pct = -6.0f + (125.0f * static_cast<float>(raw & 0xFFFC)) / 65536.0f;
  return true;
}

static bool mma8452_init() {
  if (!mma_present) {
    return false;
  }
  uint8_t whoami = 0;
  if (!i2c_read_reg8(mma_addr, 0x0D, &whoami)) {
    return false;
  }
  i2c_write_reg8(mma_addr, 0x2A, 0x00);  // standby
  i2c_write_reg8(mma_addr, 0x0E, 0x00);  // +/- 2g
  i2c_write_reg8(mma_addr, 0x2A, 0x01);  // active
  return whoami == 0x2A;
}

static int16_t sign_extend_12(uint16_t value) {
  value &= 0x0FFF;
  if (value & 0x0800) {
    value |= 0xF000;
  }
  return static_cast<int16_t>(value);
}

static bool mma8452_read_xyz_mg(int16_t *x_mg, int16_t *y_mg, int16_t *z_mg) {
  if (!mma_present) {
    return false;
  }
  Wire.beginTransmission(mma_addr);
  Wire.write(0x01);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(static_cast<int>(mma_addr), 6) != 6) {
    return false;
  }
  const uint16_t x_raw = ((static_cast<uint16_t>(Wire.read()) << 8) | Wire.read()) >> 4;
  const uint16_t y_raw = ((static_cast<uint16_t>(Wire.read()) << 8) | Wire.read()) >> 4;
  const uint16_t z_raw = ((static_cast<uint16_t>(Wire.read()) << 8) | Wire.read()) >> 4;
  *x_mg = static_cast<int16_t>((static_cast<int32_t>(sign_extend_12(x_raw)) * 1000L) / 1024L);
  *y_mg = static_cast<int16_t>((static_cast<int32_t>(sign_extend_12(y_raw)) * 1000L) / 1024L);
  *z_mg = static_cast<int16_t>((static_cast<int32_t>(sign_extend_12(z_raw)) * 1000L) / 1024L);
  return true;
}

static bool apds9960_id(uint8_t *id) {
  if (!apds_present) {
    return false;
  }
  return i2c_read_reg8(ADDR_APDS9960, 0x92, id);
}

static bool apds9960_read_clear_light(uint16_t *clear_light) {
  if (!apds_present) {
    return false;
  }
  i2c_write_reg8(ADDR_APDS9960, 0x80, 0x03);  // PON + AEN
  delay(120);
  uint8_t low = 0;
  uint8_t high = 0;
  if (!i2c_read_reg8(ADDR_APDS9960, 0x94, &low) || !i2c_read_reg8(ADDR_APDS9960, 0x95, &high)) {
    return false;
  }
  *clear_light = (static_cast<uint16_t>(high) << 8) | low;
  return true;
}

static bool apds9960_read_proximity(uint8_t *proximity) {
  if (!apds_present) {
    return false;
  }
  i2c_write_reg8(ADDR_APDS9960, 0x80, 0x05);  // PON + PEN
  delay(20);
  return i2c_read_reg8(ADDR_APDS9960, 0x9C, proximity);
}

// ---- Board setup ------------------------------------------------------------
static void configure_board_io() {
  pinMode(LED_BUILTIN, OUTPUT);
  set_builtin_indicator(false);

  for (size_t i = 0; i < BAR_PIN_COUNT; ++i) {
    pinMode(BAR_PINS[i], OUTPUT);
    digitalWrite(BAR_PINS[i], LOW);
  }

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_IR, INPUT);
  pinMode(PIN_ACCEL_INT1, INPUT);
  pinMode(PIN_ACCEL_INT2, INPUT);
  pinMode(PIN_RELAY_SIGNAL, OUTPUT);
  digitalWrite(PIN_RELAY_SIGNAL, LOW);

  analogReadResolution(12);

  ledcSetup(RGB_CH_R, RGB_PWM_FREQ, RGB_PWM_BITS);
  ledcSetup(RGB_CH_G, RGB_PWM_FREQ, RGB_PWM_BITS);
  ledcSetup(RGB_CH_B, RGB_PWM_FREQ, RGB_PWM_BITS);
  ledcAttachPin(PIN_RGB_R, RGB_CH_R);
  ledcAttachPin(PIN_RGB_G, RGB_CH_G);
  ledcAttachPin(PIN_RGB_B, RGB_CH_B);
  set_rgb(0, 0, 0);

  ledcSetup(SERVO_CH, SERVO_PWM_FREQ, SERVO_PWM_BITS);
  ledcAttachPin(PIN_SERVO_SIGNAL, SERVO_CH);
  set_servo_angle(-1);
}

static void print_boot_event() {
  Serial.print("V1|0|EVENT|BOOT|node=PQC-SAT-WISDOM|proto=V1|baud=");
  Serial.print(SERIAL_BAUD);
  Serial.println("|crypto=ML-KEM-512|pqc=ready|fault=payload_crc32|board=BlackBoard-Wisdom");
}

static void initialize_button_event_state() {
  const bool pressed = digitalRead(PIN_BUTTON) == LOW;
  button_stable_pressed = pressed;
  button_candidate_pressed = pressed;
  button_candidate_since_ms = millis();
}

static void poll_button_ping_event() {
  const bool pressed = digitalRead(PIN_BUTTON) == LOW;
  const uint32_t now = millis();
  if (pressed != button_candidate_pressed) {
    button_candidate_pressed = pressed;
    button_candidate_since_ms = now;
    return;
  }
  if (pressed == button_stable_pressed || now - button_candidate_since_ms < BUTTON_DEBOUNCE_MS) {
    return;
  }

  button_stable_pressed = pressed;
  if (pressed) {
    Serial.print("V1|0|EVENT|BUTTON_PING|button=1|uptime_ms=");
    Serial.print(now);
    Serial.print("|pot=");
    Serial.println(analogRead(PIN_POT));
  }
}

// ---- Command handlers -------------------------------------------------------
static bool apply_profile(const char *profile_name) {
  if (strcmp(profile_name, "BASELINE") == 0) {
    const bool ok = setCpuFrequencyMhz(boot_cpu_mhz);
    if (ok) {
      active_profile = "BASELINE";
    }
    disable_radios();
    return ok;
  }

  if (strcmp(profile_name, "OBC-1U-LIMITED") == 0) {
    const bool ok = setCpuFrequencyMhz(80);
    if (ok) {
      active_profile = "OBC-1U-LIMITED";
    }
    disable_radios();
    return ok;
  }

  return false;
}

static void send_hello(const char *request_id) {
  clear_staged_game(true);
  begin_result(request_id, "OK");
  print_kv("node", "PQC-SAT-WISDOM");
  print_kv("board", "BlackBoard-Wisdom");
  print_kv("proto", "V1");
  print_kv_u32("uptime_ms", millis());
  print_kv("transport", "uart");
  print_kv("crypto", PQC_TARGET);
  print_kv("pqc", PQC_STATUS);
  print_kv("pqc_target", PQC_TARGET);
  print_kv("fault", "payload_crc32");
  print_kv(
      "mission",
      fair_crypto_available()
          ? "CLASSIC,CLASSIC_CRC32,PQC,PQC_CRC32,ECDH,ECDH_CRC32,MLKEM,MLKEM_CRC32"
          : "CLASSIC,CLASSIC_CRC32,PQC,PQC_CRC32");
  print_kv("game", "STAGED_V1");
  print_kv("kex", fair_crypto_available() ? "FAIR_V1" : "LEGACY_ONLY");
  print_kv("key_modes", fair_crypto_available() ? "ECDH,MLKEM" : "CLASSIC,PQC");
  print_kv("fair_backend", fair_crypto_backend());
  print_kv("fair_version", fair_crypto_version());
  print_kv("session_bench", fair_crypto_available() ? FAIR_SESSION_BENCH : "unavailable");
  end_result();
}

static void send_ping(const char *request_id) {
  begin_result(request_id, "OK");
  print_kv("pong", "1");
  print_kv_u32("seq", command_count);
  print_kv_u32("uptime_ms", millis());
  end_result();
}

static void send_status(const char *request_id) {
  begin_result(request_id, "OK");
  print_kv("profile", active_profile);
  print_kv("chip", ESP.getChipModel());
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  print_kv_u32("flash", ESP.getFlashChipSize());
  print_kv("radio", "off");
  print_kv("fault", "payload_crc32");
  print_kv("pqc", PQC_STATUS);
  print_kv("pqc_target", PQC_TARGET);
  print_kv("pqc_backend", PQC_BACKEND);
  print_kv(
      "mission",
      fair_crypto_available()
          ? "CLASSIC,CLASSIC_CRC32,PQC,PQC_CRC32,ECDH,ECDH_CRC32,MLKEM,MLKEM_CRC32"
          : "CLASSIC,CLASSIC_CRC32,PQC,PQC_CRC32");
  print_kv("kex", fair_crypto_available() ? "FAIR_V1" : "LEGACY_ONLY");
  print_kv("fair_backend", fair_crypto_backend());
  print_kv("session_bench", fair_crypto_available() ? FAIR_SESSION_BENCH : "unavailable");
  end_result();
}

static void send_kex_info(const char *request_id) {
  if (!fair_crypto_available()) {
    print_error(request_id, "KEX_UNAVAILABLE", "build_robocore_wisdom_esp32_fair");
    return;
  }
  begin_result(request_id, "OK");
  print_kv("experiment", FAIR_EXPERIMENT);
  print_kv("algorithms", "ECDH-P256,ML-KEM-512");
  print_kv("security_target", "approximately_128-bit_classical_vs_NIST_level_1");
  print_kv("backend", fair_crypto_backend());
  print_kv("version", fair_crypto_version());
  print_kv("crypto_impl", fair_crypto_backend());
  print_kv("crypto_version", fair_crypto_version());
  print_kv("compiler", __VERSION__);
  print_kv("framework", FAIR_FRAMEWORK);
  print_kv("build_profile", FAIR_BUILD_PROFILE);
  print_kv("kdf", FAIR_KDF);
  print_kv("cipher", AEAD_CIPHER);
  print_kv("optimization", FAIR_OPTIMIZATION);
  print_kv_bool("target_asm", false);
  print_kv_bool("hw_crypto", false);
  print_kv_bool("authenticated_kex", false);
  print_kv("session_bench", FAIR_SESSION_BENCH);
  print_kv_u32("ecdh_setup_bytes", FAIR_ECDH_PUBLIC_BYTES);
  print_kv_u32("ecdh_response_bytes", FAIR_ECDH_PUBLIC_BYTES);
  print_kv_u32("mlkem_setup_bytes", FAIR_MLKEM_PUBLIC_BYTES);
  print_kv_u32("mlkem_response_bytes", FAIR_MLKEM_CIPHERTEXT_BYTES);
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void print_pqc_metrics() {
  print_kv("pqc_target", PQC_TARGET);
  print_kv("pqc_backend", PQC_BACKEND);
  print_kv("pqc_variant", PQC_VARIANT);
  print_kv("pqc_status", PQC_STATUS);
  print_kv("pqc_commit", PQC_COMMIT);
  print_kv("pqc_license", PQC_LICENSE);
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  print_kv_u32("flash", ESP.getFlashChipSize());
  print_kv("radio", "off");
}

static void fill_pqc_kat_coins(uint8_t *keygen_coins, uint8_t *encap_coins) {
  for (size_t i = 0; i < 2U * CRYPTO_SYMBYTES; ++i) {
    keygen_coins[i] = static_cast<uint8_t>(0xA5U ^ static_cast<uint8_t>(i * 17U + 3U));
  }
  for (size_t i = 0; i < CRYPTO_SYMBYTES; ++i) {
    encap_coins[i] = static_cast<uint8_t>(0x5AU ^ static_cast<uint8_t>(i * 29U + 7U));
  }
}

static bool pqc_shared_secrets_match(const uint8_t *left, const uint8_t *right) {
  uint8_t diff = 0;
  for (size_t i = 0; i < CRYPTO_BYTES; ++i) {
    diff |= static_cast<uint8_t>(left[i] ^ right[i]);
  }
  return diff == 0;
}

static bool bytes_equal_constant_time(const uint8_t *left, const uint8_t *right, size_t len) {
  uint8_t diff = 0;
  for (size_t i = 0; i < len; ++i) {
    diff |= static_cast<uint8_t>(left[i] ^ right[i]);
  }
  return diff == 0;
}

static bool hmac_sha256_tag(const uint8_t *key, size_t key_len, const uint8_t *data, size_t data_len, uint8_t *out_tag) {
  const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if (info == nullptr) {
    return false;
  }
  const int rc = mbedtls_md_hmac(info, key, key_len, data, data_len, out_tag);
  return rc == 0;
}

static bool pqc_confirmation_tag(const uint8_t *shared_secret, uint8_t *out_tag) {
  static constexpr const char transcript[] = "PQC-SAT|ML-KEM-512|KEY_CONFIRM|v1";
  return hmac_sha256_tag(
      shared_secret,
      CRYPTO_BYTES,
      reinterpret_cast<const unsigned char *>(transcript),
      strlen(transcript),
      out_tag);
}

static void secure_wipe(uint8_t *data, size_t len) {
  volatile uint8_t *p = data;
  while (len-- > 0) {
    *p++ = 0;
  }
}

static void clear_staged_game(bool restore_profile) {
  secure_wipe(reinterpret_cast<uint8_t *>(&staged_game), sizeof(staged_game));
  staged_game.state = GAME_IDLE;
  // The staged flow reuses the legacy ML-KEM work buffers while it owns the
  // serial transaction. Public material is kept only until retry/end; a full
  // session clear removes it together with every secret-bearing buffer.
  secure_wipe(pqc_pk, sizeof(pqc_pk));
  secure_wipe(pqc_sk, sizeof(pqc_sk));
  secure_wipe(pqc_ct, sizeof(pqc_ct));
  secure_wipe(pqc_ss_enc, sizeof(pqc_ss_enc));
  secure_wipe(pqc_ss_dec, sizeof(pqc_ss_dec));
  secure_wipe(pqc_fault_ct, sizeof(pqc_fault_ct));
  secure_wipe(pqc_fault_tag_enc, sizeof(pqc_fault_tag_enc));
  secure_wipe(pqc_fault_tag_dec, sizeof(pqc_fault_tag_dec));
  secure_wipe(fair_sender_secret, sizeof(fair_sender_secret));
  secure_wipe(fair_receiver_secret, sizeof(fair_receiver_secret));
  secure_wipe(fair_setup_material, sizeof(fair_setup_material));
  secure_wipe(fair_response_material, sizeof(fair_response_material));
  fair_setup_len = 0;
  fair_response_len = 0;
  pqc_keypair_ready = false;
  pqc_ciphertext_ready = false;
  pqc_shared_secret_ready = false;
  if (restore_profile && boot_cpu_mhz > 0) {
    apply_profile("BASELINE");
  }
  set_main_led_rgb(0, 0, 0);
  set_bar_percent(0);
}

static bool fill_random_bytes(uint8_t *out, size_t len) {
  return randombytes(out, len) == 0;
}

static void write_u32_be(uint8_t *out, uint32_t value) {
  out[0] = static_cast<uint8_t>((value >> 24) & 0xFFU);
  out[1] = static_cast<uint8_t>((value >> 16) & 0xFFU);
  out[2] = static_cast<uint8_t>((value >> 8) & 0xFFU);
  out[3] = static_cast<uint8_t>(value & 0xFFU);
}

static uint32_t read_u32_be(const uint8_t *data) {
  return (static_cast<uint32_t>(data[0]) << 24) |
         (static_cast<uint32_t>(data[1]) << 16) |
         (static_cast<uint32_t>(data[2]) << 8) |
         static_cast<uint32_t>(data[3]);
}

static bool derive_mission_aes128_key(
    const uint8_t *secret,
    size_t secret_len,
    const char *scenario,
    uint8_t *out_key) {
  char context[80];
  snprintf(context, sizeof(context), "PQC-SAT|MISSION|%s|AES-128-GCM|v1", scenario);

  uint8_t digest[32];
  const bool ok = hmac_sha256_tag(
      secret,
      secret_len,
      reinterpret_cast<const uint8_t *>(context),
      strlen(context),
      digest);
  if (ok) {
    memcpy(out_key, digest, AES128_KEY_BYTES);
  }
  secure_wipe(digest, sizeof(digest));
  return ok;
}

static bool aes128_gcm_encrypt(
    const uint8_t *key,
    const uint8_t *nonce,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *plaintext,
    size_t plaintext_len,
    uint8_t *ciphertext,
    uint8_t *tag) {
  mbedtls_gcm_context ctx;
  mbedtls_gcm_init(&ctx);
  int rc = mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, key, AES128_KEY_BYTES * 8U);
  if (rc == 0) {
    rc = mbedtls_gcm_crypt_and_tag(
        &ctx,
        MBEDTLS_GCM_ENCRYPT,
        plaintext_len,
        nonce,
        AES_GCM_NONCE_BYTES,
        aad,
        aad_len,
        plaintext,
        ciphertext,
        AES_GCM_TAG_BYTES,
        tag);
  }
  mbedtls_gcm_free(&ctx);
  return rc == 0;
}

static bool aes128_gcm_decrypt(
    const uint8_t *key,
    const uint8_t *nonce,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *ciphertext,
    size_t ciphertext_len,
    const uint8_t *tag,
    uint8_t *plaintext) {
  mbedtls_gcm_context ctx;
  mbedtls_gcm_init(&ctx);
  int rc = mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, key, AES128_KEY_BYTES * 8U);
  if (rc == 0) {
    rc = mbedtls_gcm_auth_decrypt(
        &ctx,
        ciphertext_len,
        nonce,
        AES_GCM_NONCE_BYTES,
        aad,
        aad_len,
        tag,
        AES_GCM_TAG_BYTES,
        ciphertext,
        plaintext);
  }
  mbedtls_gcm_free(&ctx);
  return rc == 0;
}

static bool fair_aes128_gcm_encrypt_message(
    const uint8_t *key,
    const uint8_t *nonce,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *plaintext,
    size_t plaintext_len,
    uint8_t *ciphertext,
    uint8_t *tag) {
  return fair_aes128_gcm_encrypt(
             key,
             nonce,
             AES_GCM_NONCE_BYTES,
             aad,
             aad_len,
             plaintext,
             plaintext_len,
             ciphertext,
             tag,
             AES_GCM_TAG_BYTES) == 0;
}

static bool fair_aes128_gcm_decrypt_message(
    const uint8_t *key,
    const uint8_t *nonce,
    const uint8_t *aad,
    size_t aad_len,
    const uint8_t *ciphertext,
    size_t ciphertext_len,
    const uint8_t *tag,
    uint8_t *plaintext) {
  return fair_aes128_gcm_decrypt(
             key,
             nonce,
             AES_GCM_NONCE_BYTES,
             aad,
             aad_len,
             ciphertext,
             ciphertext_len,
             tag,
             AES_GCM_TAG_BYTES,
             plaintext) == 0;
}

static bool establish_fair_session(
    FairKexAlgorithm algorithm,
    const char *context,
    uint8_t *sender_key,
    uint8_t *receiver_key,
    FairKexMetrics *metrics,
    uint32_t *kdf_us) {
  if (!fair_crypto_available()) {
    return false;
  }
  const int rc = fair_kex_establish(
      algorithm,
      fair_sender_secret,
      fair_receiver_secret,
      fair_setup_material,
      &fair_setup_len,
      fair_response_material,
      &fair_response_len,
      metrics);
  if (rc != 0 || !metrics->key_match) {
    return false;
  }
  const uint32_t started = micros();
  const int sender_rc = fair_hkdf_aes128(
      fair_sender_secret,
      FAIR_SHARED_SECRET_BYTES,
      context,
      sender_key);
  const int receiver_rc = fair_hkdf_aes128(
      fair_receiver_secret,
      FAIR_SHARED_SECRET_BYTES,
      context,
      receiver_key);
  *kdf_us = micros() - started;
  return sender_rc == 0 && receiver_rc == 0 &&
         bytes_equal_constant_time(sender_key, receiver_key, AES128_KEY_BYTES);
}

static void print_fair_metadata(
    FairKexAlgorithm algorithm,
    bool include_experiment = true) {
  if (include_experiment) {
    print_kv("experiment", FAIR_EXPERIMENT);
  }
  print_kv("kex", fair_kex_name(algorithm));
  print_kv("crypto_impl", fair_crypto_backend());
  print_kv("crypto_version", fair_crypto_version());
  print_kv("compiler", __VERSION__);
  print_kv("framework", FAIR_FRAMEWORK);
  print_kv("build_profile", FAIR_BUILD_PROFILE);
  print_kv("kdf", FAIR_KDF);
  print_kv("optimization", FAIR_OPTIMIZATION);
  print_kv_bool("target_asm", false);
  print_kv_bool("hw_crypto", false);
  print_kv_bool("authenticated_kex", false);
}

static bool mission_payload_from_fields(size_t field_count, char *fields[], uint8_t *payload, size_t max_len, size_t *payload_len) {
  if (field_count >= 5) {
    return parse_hex_payload(fields[4], payload, max_len, payload_len);
  }

  const size_t default_len = strlen(MISSION_DEFAULT_PAYLOAD);
  if (default_len > max_len) {
    return false;
  }
  memcpy(payload, MISSION_DEFAULT_PAYLOAD, default_len);
  *payload_len = default_len;
  return true;
}

static void staged_game_error(const char *request_id, const char *code, const char *detail) {
  print_error(request_id, code, detail);
  clear_staged_game(true);
}

static bool staged_game_matches(const char *game_id, StagedGameState expected) {
  return staged_game.active && staged_game.state == expected && strcmp(staged_game.id, game_id) == 0;
}

static bool is_staged_game_control_command(const char *command) {
  return strcmp(command, "GAME_BEGIN") == 0 ||
         strcmp(command, "GAME_PROTECT") == 0 ||
         strcmp(command, "GAME_TRANSMIT") == 0 ||
         strcmp(command, "GAME_VERIFY") == 0 ||
         strcmp(command, "GAME_RETRY") == 0 ||
         strcmp(command, "GAME_END") == 0 ||
         strcmp(command, "GAME_ABORT") == 0;
}

static bool is_staged_game_safe_read_command(
    const char *command,
    size_t field_count,
    char *fields[]) {
  // The green on-screen confirmation needs a fresh A39 sample between
  // GAME_PROTECT and GAME_TRANSMIT. This read is side-effect free and must not
  // clear the active transactional game or its ML-KEM/AES-GCM buffers.
  if (strcmp(command, "ANALOG") != 0 || field_count != 4) {
    return false;
  }
  uppercase_ascii(fields[3]);
  return strcmp(fields[3], "POT") == 0;
}

static const char *staged_game_scenario() {
  if (staged_game.use_fair) {
    if (strcmp(staged_game.key_mode, "ECDH") == 0) {
      return staged_game.use_app_crc ? "ECDH_CRC32" : "ECDH";
    }
    return staged_game.use_app_crc ? "MLKEM_CRC32" : "MLKEM";
  }
  if (staged_game.use_pqc) {
    return staged_game.use_app_crc ? "PQC_CRC32" : "PQC";
  }
  return staged_game.use_app_crc ? "CLASSIC_CRC32" : "CLASSIC";
}

static uint32_t staged_game_bytes_total() {
  return static_cast<uint32_t>(staged_game.protected_len) + AES_GCM_NONCE_BYTES + AES_GCM_TAG_BYTES +
         (staged_game.use_pqc ? CRYPTO_CIPHERTEXTBYTES : 0U) +
         staged_game.setup_bytes + staged_game.response_bytes + 4U;
}

static void staged_game_aad(char *out, size_t out_len) {
  snprintf(
      out,
      out_len,
      "PQC-SAT|GAME|%s|%s|%s|v1",
      staged_game.id,
      staged_game.key_mode,
      staged_game.guard);
}

static void print_staged_game_common(const char *stage, const char *result, uint32_t elapsed_us) {
  print_kv("game_id", staged_game.id);
  print_kv("stage", stage);
  print_kv("profile", staged_game.profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv("key_mode", staged_game.key_mode);
  print_kv("guard", staged_game.guard);
  print_kv("result", result);
  print_kv_u32("elapsed_us", elapsed_us > 0 ? elapsed_us : 1U);
  print_kv_u32("bytes_payload", staged_game.payload_len);
  print_kv_u32("bytes_total", staged_game_bytes_total());
  if (staged_game.use_fair) {
    print_kv("experiment", FAIR_EXPERIMENT);
    print_kv_u32("setup_bytes", staged_game.setup_bytes);
    print_kv_u32("response_bytes", staged_game.response_bytes);
    print_kv_u32(
        "data_bytes",
        static_cast<uint32_t>(staged_game.protected_len) +
            AES_GCM_NONCE_BYTES + AES_GCM_TAG_BYTES + 4U);
  } else {
    print_kv("experiment", "LEGACY_V1");
  }
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
}

static void wipe_staged_game_secrets() {
  secure_wipe(staged_game.aes_key_enc, sizeof(staged_game.aes_key_enc));
  secure_wipe(staged_game.aes_key_dec, sizeof(staged_game.aes_key_dec));
  secure_wipe(pqc_sk, sizeof(pqc_sk));
  secure_wipe(pqc_ss_enc, sizeof(pqc_ss_enc));
  secure_wipe(pqc_ss_dec, sizeof(pqc_ss_dec));
  secure_wipe(fair_sender_secret, sizeof(fair_sender_secret));
  secure_wipe(fair_receiver_secret, sizeof(fair_receiver_secret));
  pqc_keypair_ready = false;
  pqc_shared_secret_ready = false;
}

static bool build_staged_game_protection() {
  memset(staged_game.ciphertext, 0, sizeof(staged_game.ciphertext));
  memset(staged_game.decrypted, 0, sizeof(staged_game.decrypted));
  memset(staged_game.aes_key_enc, 0, sizeof(staged_game.aes_key_enc));
  memset(staged_game.aes_key_dec, 0, sizeof(staged_game.aes_key_dec));
  memset(staged_game.nonce, 0, sizeof(staged_game.nonce));
  memset(staged_game.gcm_tag, 0, sizeof(staged_game.gcm_tag));
  staged_game.keygen_us = 0;
  staged_game.encap_us = 0;
  staged_game.decap_us = 0;
  staged_game.setup_us = 0;
  staged_game.initiator_us = 0;
  staged_game.responder_us = 0;
  staged_game.kex_total_us = 0;
  staged_game.setup_bytes = 0;
  staged_game.response_bytes = 0;
  staged_game.kdf_us = 0;
  staged_game.rng_us = 0;
  staged_game.encrypt_us = 0;
  staged_game.decrypt_us = 0;
  staged_game.key_match = true;
  const uint32_t started = micros();

  if (staged_game.use_fair) {
    FairKexMetrics fair_metrics = {};
    char kdf_context[128];
    snprintf(
        kdf_context,
        sizeof(kdf_context),
        "PQC-SAT|GAME|%s|%s|%s|KEX_FAIR_V1",
        staged_game.id,
        staged_game.key_mode,
        staged_game.guard);
    if (!establish_fair_session(
            staged_game.fair_algorithm,
            kdf_context,
            staged_game.aes_key_enc,
            staged_game.aes_key_dec,
            &fair_metrics,
            &staged_game.kdf_us)) {
      return false;
    }
    staged_game.key_match = fair_metrics.key_match;
    staged_game.setup_us = fair_metrics.setup_us;
    staged_game.initiator_us = fair_metrics.initiator_us;
    staged_game.responder_us = fair_metrics.responder_us;
    staged_game.kex_total_us = fair_metrics.kex_total_us;
    staged_game.setup_bytes = fair_metrics.setup_bytes;
    staged_game.response_bytes = fair_metrics.response_bytes;
    staged_game.keygen_us = staged_game.setup_us;
    staged_game.encap_us = staged_game.initiator_us;
    staged_game.decap_us = staged_game.responder_us;
  } else if (staged_game.use_pqc) {
    uint32_t op_started = micros();
    int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
    staged_game.keygen_us = micros() - op_started;
    if (rc != 0) {
      return false;
    }
    op_started = micros();
    rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
    staged_game.encap_us = micros() - op_started;
    if (rc != 0) {
      return false;
    }
    op_started = micros();
    rc = crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk);
    staged_game.decap_us = micros() - op_started;
    if (rc != 0) {
      return false;
    }
    staged_game.key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
    op_started = micros();
    const char *scenario = staged_game_scenario();
    const bool key_a = derive_mission_aes128_key(pqc_ss_enc, CRYPTO_BYTES, scenario, staged_game.aes_key_enc);
    const bool key_b = derive_mission_aes128_key(pqc_ss_dec, CRYPTO_BYTES, scenario, staged_game.aes_key_dec);
    staged_game.kdf_us = micros() - op_started;
    if (!key_a || !key_b || !staged_game.key_match) {
      return false;
    }
    pqc_keypair_ready = true;
    pqc_ciphertext_ready = true;
    pqc_shared_secret_ready = true;
  } else {
    const uint32_t op_started = micros();
    if (!fill_random_bytes(staged_game.aes_key_enc, sizeof(staged_game.aes_key_enc))) {
      return false;
    }
    memcpy(staged_game.aes_key_dec, staged_game.aes_key_enc, sizeof(staged_game.aes_key_dec));
    staged_game.rng_us += micros() - op_started;
  }

  const uint32_t nonce_started = micros();
  const bool nonce_ok =
      staged_game.use_fair
          ? fair_random_bytes(staged_game.nonce, sizeof(staged_game.nonce)) == 0
          : fill_random_bytes(staged_game.nonce, sizeof(staged_game.nonce));
  if (!nonce_ok) {
    return false;
  }
  staged_game.rng_us += micros() - nonce_started;
  staged_game.nonce_crc32 = crc32_bytes(staged_game.nonce, sizeof(staged_game.nonce));
  staged_game.session_key_crc32 = crc32_bytes(staged_game.aes_key_enc, sizeof(staged_game.aes_key_enc));

  char aad[112];
  staged_game_aad(aad, sizeof(aad));
  const uint32_t encrypt_started = micros();
  const bool encrypt_ok =
      staged_game.use_fair
          ? fair_aes128_gcm_encrypt_message(
                staged_game.aes_key_enc,
                staged_game.nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                staged_game.protected_payload,
                staged_game.protected_len,
                staged_game.ciphertext,
                staged_game.gcm_tag)
          : aes128_gcm_encrypt(
                staged_game.aes_key_enc,
                staged_game.nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                staged_game.protected_payload,
                staged_game.protected_len,
                staged_game.ciphertext,
                staged_game.gcm_tag);
  staged_game.encrypt_us = micros() - encrypt_started;
  staged_game.protect_elapsed_us = micros() - started;
  return encrypt_ok;
}

static bool transmit_staged_game_incident(const char *incident) {
  char aad[112];
  staged_game_aad(aad, sizeof(aad));
  uint8_t frame[
      112 + FAIR_MAX_SETUP_BYTES + FAIR_MAX_RESPONSE_BYTES +
      AES_GCM_NONCE_BYTES + MAX_EXPERIMENT_PAYLOAD +
      MISSION_CRC_BYTES + AES_GCM_TAG_BYTES];
  size_t frame_len = 0;
  memcpy(&frame[frame_len], aad, strlen(aad));
  frame_len += strlen(aad);
  if (staged_game.use_fair) {
    memcpy(&frame[frame_len], fair_setup_material, fair_setup_len);
    frame_len += fair_setup_len;
    memcpy(&frame[frame_len], fair_response_material, fair_response_len);
    frame_len += fair_response_len;
  } else if (staged_game.use_pqc) {
    memcpy(&frame[frame_len], pqc_ct, CRYPTO_CIPHERTEXTBYTES);
    frame_len += CRYPTO_CIPHERTEXTBYTES;
  }
  memcpy(&frame[frame_len], staged_game.nonce, sizeof(staged_game.nonce));
  frame_len += sizeof(staged_game.nonce);
  const size_t cipher_offset = frame_len;
  memcpy(&frame[frame_len], staged_game.ciphertext, staged_game.protected_len);
  frame_len += staged_game.protected_len;
  memcpy(&frame[frame_len], staged_game.gcm_tag, sizeof(staged_game.gcm_tag));
  frame_len += sizeof(staged_game.gcm_tag);

  staged_game.frame_crc_tx = crc32_bytes(frame, frame_len);
  staged_game.frame_crc_rx = staged_game.frame_crc_tx;
  staged_game.before_byte = staged_game.ciphertext[staged_game.byte_index];
  staged_game.after_byte = staged_game.before_byte;
  const bool mutate_frame = strcmp(incident, "CHANNEL_BITFLIP") == 0 || strcmp(incident, "TAMPER") == 0;
  if (mutate_frame) {
    staged_game.ciphertext[staged_game.byte_index] ^= staged_game.bit_mask;
    staged_game.after_byte = staged_game.ciphertext[staged_game.byte_index];
    frame[cipher_offset + staged_game.byte_index] ^= staged_game.bit_mask;
    staged_game.frame_crc_rx = crc32_bytes(frame, frame_len);
    if (strcmp(incident, "TAMPER") == 0) {
      staged_game.frame_crc_tx = staged_game.frame_crc_rx;
    }
  }
  staged_game.frame_crc_match = staged_game.frame_crc_tx == staged_game.frame_crc_rx;
  return true;
}

static bool verify_staged_game_incident(const char *incident) {
  char aad[112];
  staged_game_aad(aad, sizeof(aad));
  memset(staged_game.decrypted, 0, sizeof(staged_game.decrypted));
  const uint32_t decrypt_started = micros();
  const bool decrypt_ok =
      staged_game.use_fair
          ? fair_aes128_gcm_decrypt_message(
                staged_game.aes_key_dec,
                staged_game.nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                staged_game.ciphertext,
                staged_game.protected_len,
                staged_game.gcm_tag,
                staged_game.decrypted)
          : aes128_gcm_decrypt(
                staged_game.aes_key_dec,
                staged_game.nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                staged_game.ciphertext,
                staged_game.protected_len,
                staged_game.gcm_tag,
                staged_game.decrypted);
  staged_game.decrypt_us = micros() - decrypt_started;
  staged_game.aead_checked = true;
  staged_game.aead_match = decrypt_ok;

  if (strcmp(incident, "RX_MEMORY") == 0 && decrypt_ok) {
    staged_game.before_byte = staged_game.decrypted[staged_game.byte_index];
    staged_game.decrypted[staged_game.byte_index] ^= staged_game.bit_mask;
    staged_game.after_byte = staged_game.decrypted[staged_game.byte_index];
  }
  staged_game.app_crc_checked = staged_game.use_app_crc && decrypt_ok;
  staged_game.app_crc_match = false;
  if (staged_game.app_crc_checked) {
    const uint32_t calculated = crc32_bytes(staged_game.decrypted, staged_game.payload_len);
    const uint32_t stored = read_u32_be(&staged_game.decrypted[staged_game.payload_len]);
    staged_game.app_crc_match = calculated == stored;
  }
  staged_game.accepted = staged_game.frame_crc_match && staged_game.aead_match &&
                         (!staged_game.use_app_crc || staged_game.app_crc_match);
  if (strcmp(incident, "CHANNEL_BITFLIP") == 0) {
    snprintf(staged_game.final_result, sizeof(staged_game.final_result), "FRAME_REJECT");
  } else if (strcmp(incident, "TAMPER") == 0) {
    snprintf(staged_game.final_result, sizeof(staged_game.final_result), "AUTH_REJECT");
  } else if (strcmp(incident, "RX_MEMORY") == 0) {
    snprintf(
        staged_game.final_result,
        sizeof(staged_game.final_result),
        "%s",
        staged_game.use_app_crc ? "APP_REJECT" : "SILENT_CORRUPTION");
  } else {
    snprintf(staged_game.final_result, sizeof(staged_game.final_result), "DELIVERED");
  }
  const bool expected_acceptance = strcmp(incident, "NORMAL") == 0 ||
                                   (strcmp(incident, "RX_MEMORY") == 0 && !staged_game.use_app_crc);
  return staged_game.accepted == expected_acceptance;
}

static void print_staged_game_verification(const char *stage, uint32_t elapsed_us) {
  print_staged_game_common(stage, staged_game.final_result, elapsed_us);
  if (strcmp(stage, "RETRY") == 0) {
    print_kv_u32("setup_us", staged_game.setup_us);
    print_kv_u32("initiator_us", staged_game.initiator_us);
    print_kv_u32("responder_us", staged_game.responder_us);
    print_kv_u32("kex_total_us", staged_game.kex_total_us);
    print_kv_u32("kdf_us", staged_game.kdf_us);
    print_kv_u32("rng_us", staged_game.rng_us);
    print_kv_u32("encrypt_us", staged_game.encrypt_us);
  }
  print_kv_u32("byte_index", staged_game.byte_index);
  print_kv_hex_u8("bit_mask", staged_game.bit_mask);
  print_kv_bool("frame_crc_match", staged_game.frame_crc_match);
  print_kv_bool("aead_checked", staged_game.aead_checked);
  print_kv_bool("aead_match", staged_game.aead_match);
  print_kv_bool("app_crc_present", staged_game.use_app_crc);
  print_kv_bool("app_crc_checked", staged_game.app_crc_checked);
  print_kv_bool("app_crc_match", staged_game.app_crc_match);
  print_kv_bool("accepted", staged_game.accepted);
}

static void print_pqc_sizes() {
  print_kv_u32("pk", CRYPTO_PUBLICKEYBYTES);
  print_kv_u32("sk", CRYPTO_SECRETKEYBYTES);
  print_kv_u32("ct", CRYPTO_CIPHERTEXTBYTES);
  print_kv_u32("ss", CRYPTO_BYTES);
}

static void print_pqc_error_result(const char *request_id, const char *operation, int rc, uint32_t elapsed_us) {
  begin_result(request_id, "ERROR");
  print_kv("code", "PQC_FAIL");
  print_kv("op", operation);
  print_kv_i32("rc", rc);
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void send_pqc_info(const char *request_id) {
  const uint32_t started = micros();
  begin_result(request_id, "OK");
  print_pqc_metrics();
  print_pqc_sizes();
  print_kv("source", PQC_SOURCE);
  print_kv("ready", "1");
  print_kv_u32("elapsed_us", micros() - started);
  end_result();
}

static void send_pqc_kat(const char *request_id) {
  uint8_t keygen_coins[2U * CRYPTO_SYMBYTES];
  uint8_t encap_coins[CRYPTO_SYMBYTES];
  fill_pqc_kat_coins(keygen_coins, encap_coins);

  const uint32_t started = micros();
  const int key_rc = crypto_kem_keypair_derand(pqc_kat_pk, pqc_kat_sk, keygen_coins);
  const int pk_rc = key_rc == 0 ? crypto_kem_check_pk(pqc_kat_pk) : key_rc;
  const int sk_rc = key_rc == 0 ? crypto_kem_check_sk(pqc_kat_sk) : key_rc;
  const int enc_rc = key_rc == 0 ? crypto_kem_enc_derand(pqc_kat_ct, pqc_kat_ss_enc, pqc_kat_pk, encap_coins) : key_rc;
  const int dec_rc = enc_rc == 0 ? crypto_kem_dec(pqc_kat_ss_dec, pqc_kat_ct, pqc_kat_sk) : enc_rc;
  const bool key_match = dec_rc == 0 && pqc_shared_secrets_match(pqc_kat_ss_enc, pqc_kat_ss_dec);
  const bool vector_match = key_match && pqc_shared_secrets_match(pqc_kat_ss_enc, PQC_KAT_EXPECTED_SS);
  const uint32_t elapsed_us = micros() - started;

  begin_result(request_id, vector_match ? "OK" : "ERROR");
  print_kv("kat", vector_match ? "pass" : "fail");
  print_kv_bool("key_match", key_match);
  print_kv_i32("key_rc", key_rc);
  print_kv_i32("pk_rc", pk_rc);
  print_kv_i32("sk_rc", sk_rc);
  print_kv_i32("enc_rc", enc_rc);
  print_kv_i32("dec_rc", dec_rc);
  print_kv_hex_u32("ss_crc32", crc32_bytes(pqc_kat_ss_enc, sizeof(pqc_kat_ss_enc)));
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  end_result();
}

static void send_pqc_keygen(const char *request_id) {
  const uint32_t started = micros();
  const int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
  const uint32_t elapsed_us = micros() - started;
  if (rc != 0) {
    pqc_keypair_ready = false;
    pqc_ciphertext_ready = false;
    pqc_shared_secret_ready = false;
    print_pqc_error_result(request_id, "keygen", rc, elapsed_us);
    return;
  }

  pqc_keypair_ready = true;
  pqc_ciphertext_ready = false;
  pqc_shared_secret_ready = false;
  begin_result(request_id, "OK");
  print_kv("op", "keygen");
  print_kv_bool("stored", pqc_keypair_ready);
  print_kv_hex_u32("pk_crc32", crc32_bytes(pqc_pk, sizeof(pqc_pk)));
  print_pqc_sizes();
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void send_pqc_encap(const char *request_id) {
  if (!pqc_keypair_ready) {
    print_error(request_id, "PQC_STATE", "run_PQC_KEYGEN_first");
    return;
  }

  const uint32_t started = micros();
  const int rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
  const uint32_t elapsed_us = micros() - started;
  if (rc != 0) {
    pqc_ciphertext_ready = false;
    pqc_shared_secret_ready = false;
    print_pqc_error_result(request_id, "encap", rc, elapsed_us);
    return;
  }

  pqc_ciphertext_ready = true;
  pqc_shared_secret_ready = false;
  begin_result(request_id, "OK");
  print_kv("op", "encap");
  print_kv_bool("ct_stored", pqc_ciphertext_ready);
  print_kv_hex_u32("ct_crc32", crc32_bytes(pqc_ct, sizeof(pqc_ct)));
  print_kv_hex_u32("ss_crc32", crc32_bytes(pqc_ss_enc, sizeof(pqc_ss_enc)));
  print_kv_u32("ct", CRYPTO_CIPHERTEXTBYTES);
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void send_pqc_decap(const char *request_id) {
  if (!pqc_keypair_ready || !pqc_ciphertext_ready) {
    print_error(request_id, "PQC_STATE", "run_PQC_KEYGEN_and_PQC_ENCAP_first");
    return;
  }

  const uint32_t started = micros();
  const int rc = crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk);
  const uint32_t elapsed_us = micros() - started;
  if (rc != 0) {
    pqc_shared_secret_ready = false;
    print_pqc_error_result(request_id, "decap", rc, elapsed_us);
    return;
  }

  const bool key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
  pqc_shared_secret_ready = key_match;
  begin_result(request_id, key_match ? "OK" : "ERROR");
  print_kv("op", "decap");
  print_kv_bool("key_match", key_match);
  print_kv_hex_u32("ss_crc32", crc32_bytes(pqc_ss_dec, sizeof(pqc_ss_dec)));
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void handle_pqc_fault(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count < 5 || field_count > 6) {
    print_error(request_id, "BAD_ARGS", "expected_index_mask_confirm");
    return;
  }

  int byte_index = 0;
  if (!parse_int_range(fields[3], 0, static_cast<int>(CRYPTO_CIPHERTEXTBYTES) - 1, &byte_index)) {
    print_error(request_id, "BAD_INDEX", "outside_ciphertext");
    return;
  }

  uint8_t bit_mask = 0;
  if (!parse_u8_auto(fields[4], &bit_mask) || !is_single_bit_mask(bit_mask)) {
    print_error(request_id, "BAD_MASK", "expected_single_bit");
    return;
  }

  bool confirmation_enabled = true;
  if (field_count == 6) {
    uppercase_ascii(fields[5]);
    if (strcmp(fields[5], "CONFIRM") == 0 || strcmp(fields[5], "HMAC") == 0) {
      confirmation_enabled = true;
    } else if (strcmp(fields[5], "NONE") == 0) {
      confirmation_enabled = false;
    } else {
      print_error(request_id, "BAD_CONFIRM", "expected_CONFIRM_or_NONE");
      return;
    }
  }

  const uint32_t started = micros();

  uint32_t op_started = micros();
  int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
  const uint32_t keygen_us = micros() - op_started;
  if (rc != 0) {
    print_pqc_error_result(request_id, "fault_keygen", rc, micros() - started);
    return;
  }

  op_started = micros();
  rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
  const uint32_t encap_us = micros() - op_started;
  if (rc != 0) {
    print_pqc_error_result(request_id, "fault_encap", rc, micros() - started);
    return;
  }

  const uint32_t ct_crc_before = crc32_bytes(pqc_ct, sizeof(pqc_ct));
  memcpy(pqc_fault_ct, pqc_ct, sizeof(pqc_fault_ct));
  const uint8_t before_byte = pqc_fault_ct[byte_index];
  pqc_fault_ct[byte_index] ^= bit_mask;
  const uint8_t after_byte = pqc_fault_ct[byte_index];
  const uint32_t ct_crc_after = crc32_bytes(pqc_fault_ct, sizeof(pqc_fault_ct));

  op_started = micros();
  rc = crypto_kem_dec(pqc_ss_dec, pqc_fault_ct, pqc_sk);
  const uint32_t decap_us = micros() - op_started;
  if (rc != 0) {
    print_pqc_error_result(request_id, "fault_decap", rc, micros() - started);
    return;
  }

  const bool key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
  bool tag_match = false;
  bool tag_ready = false;
  uint32_t confirm_us = 0;

  if (confirmation_enabled) {
    op_started = micros();
    const bool tag_a = pqc_confirmation_tag(pqc_ss_enc, pqc_fault_tag_enc);
    const bool tag_b = pqc_confirmation_tag(pqc_ss_dec, pqc_fault_tag_dec);
    confirm_us = micros() - op_started;
    tag_ready = tag_a && tag_b;
    tag_match = tag_ready && bytes_equal_constant_time(pqc_fault_tag_enc, pqc_fault_tag_dec, PQC_CONFIRM_TAG_BYTES);
  }

  const char *result = "OK";
  if (confirmation_enabled) {
    result = tag_match ? "OK" : "PROTOCOL_REJECT";
  } else if (!key_match) {
    result = "KEY_MISMATCH";
  }

  pqc_keypair_ready = true;
  pqc_ciphertext_ready = true;
  pqc_shared_secret_ready = key_match;

  begin_result(request_id, "OK");
  print_kv("op", "ciphertext_fault");
  print_kv("target", "CIPHERTEXT");
  print_kv("result", result);
  print_kv("confirmation", confirmation_enabled ? PQC_CONFIRMATION : "NONE");
  print_kv_bool("key_match", key_match);
  print_kv_bool("key_confirmed", confirmation_enabled && tag_match);
  print_kv_bool("tag_match", tag_match);
  print_kv_bool("tag_ready", tag_ready);
  print_kv_i32("dec_rc", rc);
  print_kv_u32("byte_index", static_cast<uint32_t>(byte_index));
  print_kv_hex_u8("bit_mask", bit_mask);
  print_kv_hex_u8("before", before_byte);
  print_kv_hex_u8("after", after_byte);
  print_kv_hex_u32("ct_crc_before", ct_crc_before);
  print_kv_hex_u32("ct_crc_after", ct_crc_after);
  print_kv_hex_u32("ss_enc_crc32", crc32_bytes(pqc_ss_enc, sizeof(pqc_ss_enc)));
  print_kv_hex_u32("ss_dec_crc32", crc32_bytes(pqc_ss_dec, sizeof(pqc_ss_dec)));
  if (confirmation_enabled && tag_ready) {
    print_kv_hex_u32("tag_enc_crc32", crc32_bytes(pqc_fault_tag_enc, sizeof(pqc_fault_tag_enc)));
    print_kv_hex_u32("tag_dec_crc32", crc32_bytes(pqc_fault_tag_dec, sizeof(pqc_fault_tag_dec)));
  }
  print_kv_u32("keygen_us", keygen_us);
  print_kv_u32("encap_us", encap_us);
  print_kv_u32("decap_us", decap_us);
  print_kv_u32("confirm_us", confirm_us);
  print_kv_u32("elapsed_us", micros() - started);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static bool run_pqc_round(uint32_t *keygen_us, uint32_t *encap_us, uint32_t *decap_us, bool *key_match) {
  uint32_t started = micros();
  int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
  *keygen_us = micros() - started;
  if (rc != 0) {
    return false;
  }

  started = micros();
  rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
  *encap_us = micros() - started;
  if (rc != 0) {
    return false;
  }

  started = micros();
  rc = crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk);
  *decap_us = micros() - started;
  if (rc != 0) {
    return false;
  }

  *key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
  pqc_keypair_ready = true;
  pqc_ciphertext_ready = true;
  pqc_shared_secret_ready = *key_match;
  return *key_match;
}

static void handle_pqc_bench(const char *request_id, size_t field_count, char *fields[]) {
  uint16_t rounds = 3;
  if (field_count >= 4) {
    int parsed = 0;
    if (!parse_int_range(fields[3], 1, 100, &parsed)) {
      print_error(request_id, "BAD_ARGS", "expected_1_to_100");
      return;
    }
    rounds = static_cast<uint16_t>(parsed);
  }

  const uint32_t started = micros();
  uint32_t total_keygen = 0;
  uint32_t total_encap = 0;
  uint32_t total_decap = 0;
  uint16_t ok = 0;
  bool last_match = false;

  for (uint16_t i = 0; i < rounds; ++i) {
    uint32_t keygen_us = 0;
    uint32_t encap_us = 0;
    uint32_t decap_us = 0;
    bool key_match = false;
    if (run_pqc_round(&keygen_us, &encap_us, &decap_us, &key_match)) {
      ok++;
    }
    last_match = key_match;
    total_keygen += keygen_us;
    total_encap += encap_us;
    total_decap += decap_us;
    delay(0);
  }

  begin_result(request_id, ok == rounds ? "OK" : "ERROR");
  print_kv_u32("n", rounds);
  print_kv_u32("ok", ok);
  print_kv_bool("key_match", last_match);
  print_kv_u32("keygen_avg_us", total_keygen / rounds);
  print_kv_u32("encap_avg_us", total_encap / rounds);
  print_kv_u32("decap_avg_us", total_decap / rounds);
  print_kv_u32("elapsed_us", micros() - started);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static bool run_fair_bench_round(
    FairKexAlgorithm algorithm,
    FairBenchTotals *totals) {
  FairKexMetrics metrics = {};
  const int rc = fair_kex_establish(
      algorithm,
      fair_sender_secret,
      fair_receiver_secret,
      fair_setup_material,
      &fair_setup_len,
      fair_response_material,
      &fair_response_len,
      &metrics);
  totals->setup_us += metrics.setup_us;
  totals->initiator_us += metrics.initiator_us;
  totals->responder_us += metrics.responder_us;
  totals->total_us += metrics.kex_total_us;
  if (rc == 0 && metrics.key_match) {
    totals->ok++;
    return true;
  }
  if (totals->failure_rc == 0) {
    totals->failure_rc = rc;
  }
  return false;
}

static void handle_kex_bench(const char *request_id, size_t field_count, char *fields[]) {
  if (!fair_crypto_available()) {
    print_error(request_id, "KEX_UNAVAILABLE", "build_robocore_wisdom_esp32_fair");
    return;
  }
  uint16_t rounds = 3;
  if (field_count >= 4) {
    int parsed = 0;
    if (!parse_int_range(fields[3], 1, 100, &parsed)) {
      print_error(request_id, "BAD_ARGS", "expected_1_to_100");
      return;
    }
    rounds = static_cast<uint16_t>(parsed);
  }

  FairBenchTotals ecdh = {};
  FairBenchTotals mlkem = {};
  const uint32_t started = micros();
  for (uint16_t i = 0; i < rounds; ++i) {
    if ((i & 1U) == 0U) {
      run_fair_bench_round(FAIR_KEX_ECDH_P256, &ecdh);
      run_fair_bench_round(FAIR_KEX_MLKEM512, &mlkem);
    } else {
      run_fair_bench_round(FAIR_KEX_MLKEM512, &mlkem);
      run_fair_bench_round(FAIR_KEX_ECDH_P256, &ecdh);
    }
    delay(0);
  }

  const bool all_ok = ecdh.ok == rounds && mlkem.ok == rounds;
  begin_result(request_id, all_ok ? "OK" : "ERROR");
  print_kv("op", "paired_kex_benchmark");
  print_kv("experiment", FAIR_EXPERIMENT);
  print_kv("order", "alternating_paired");
  print_kv("paired_order", "alternating");
  print_kv_u32("warmup_rounds", 0);
  print_kv_u32("n", rounds);
  print_kv_u32("pairs", rounds);
  print_kv_u32("ok", static_cast<uint32_t>(ecdh.ok) + mlkem.ok);
  print_kv_u32("ecdh_ok", ecdh.ok);
  print_kv_i32("ecdh_rc", ecdh.failure_rc);
  print_kv_u32("ecdh_setup_avg_us", static_cast<uint32_t>(ecdh.setup_us / rounds));
  print_kv_u32("ecdh_initiator_avg_us", static_cast<uint32_t>(ecdh.initiator_us / rounds));
  print_kv_u32("ecdh_responder_avg_us", static_cast<uint32_t>(ecdh.responder_us / rounds));
  print_kv_u32("ecdh_total_avg_us", static_cast<uint32_t>(ecdh.total_us / rounds));
  print_kv_u32("ecdh_setup_bytes", FAIR_ECDH_PUBLIC_BYTES);
  print_kv_u32("ecdh_response_bytes", FAIR_ECDH_PUBLIC_BYTES);
  print_kv_u32("mlkem_ok", mlkem.ok);
  print_kv_i32("mlkem_rc", mlkem.failure_rc);
  print_kv_u32("mlkem_setup_avg_us", static_cast<uint32_t>(mlkem.setup_us / rounds));
  print_kv_u32("mlkem_initiator_avg_us", static_cast<uint32_t>(mlkem.initiator_us / rounds));
  print_kv_u32("mlkem_responder_avg_us", static_cast<uint32_t>(mlkem.responder_us / rounds));
  print_kv_u32("mlkem_total_avg_us", static_cast<uint32_t>(mlkem.total_us / rounds));
  print_kv_u32("mlkem_setup_bytes", FAIR_MLKEM_PUBLIC_BYTES);
  print_kv_u32("mlkem_response_bytes", FAIR_MLKEM_CIPHERTEXT_BYTES);
  print_kv("backend", fair_crypto_backend());
  print_kv("version", fair_crypto_version());
  print_kv("crypto_impl", fair_crypto_backend());
  print_kv("crypto_version", fair_crypto_version());
  print_kv("compiler", __VERSION__);
  print_kv("framework", FAIR_FRAMEWORK);
  print_kv("build_profile", FAIR_BUILD_PROFILE);
  print_kv("kdf", FAIR_KDF);
  print_kv("cipher", AEAD_CIPHER);
  print_kv("optimization", FAIR_OPTIMIZATION);
  print_kv_bool("target_asm", false);
  print_kv_bool("hw_crypto", false);
  print_kv_bool("authenticated_kex", false);
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("elapsed_us", micros() - started);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
  secure_wipe(fair_sender_secret, sizeof(fair_sender_secret));
  secure_wipe(fair_receiver_secret, sizeof(fair_receiver_secret));
}

static bool valid_session_message_count(int value) {
  return value == 1 || value == 100 || value == 500 || value == 1000;
}

static void handle_session_bench(const char *request_id, size_t field_count, char *fields[]) {
  if (!fair_crypto_available()) {
    print_error(request_id, "KEX_UNAVAILABLE", "build_robocore_wisdom_esp32_fair");
    return;
  }
  if (field_count != 6) {
    print_error(request_id, "BAD_ARGS", "expected_ECDH_or_MLKEM_messages_payloadhex");
    return;
  }

  uppercase_ascii(fields[3]);
  FairKexAlgorithm algorithm = FAIR_KEX_ECDH_P256;
  if (strcmp(fields[3], "ECDH") == 0) {
    algorithm = FAIR_KEX_ECDH_P256;
  } else if (strcmp(fields[3], "MLKEM") == 0) {
    algorithm = FAIR_KEX_MLKEM512;
  } else {
    print_error(request_id, "BAD_ALGORITHM", "expected_ECDH_or_MLKEM");
    return;
  }

  int parsed_messages = 0;
  if (!parse_int_range(fields[4], 1, 1000, &parsed_messages) ||
      !valid_session_message_count(parsed_messages)) {
    print_error(request_id, "BAD_MESSAGES", "expected_1_100_500_or_1000");
    return;
  }
  const uint32_t messages = static_cast<uint32_t>(parsed_messages);

  uint8_t payload[MAX_EXPERIMENT_PAYLOAD] = {0};
  size_t payload_len = 0;
  if (!parse_hex_payload(fields[5], payload, sizeof(payload), &payload_len)) {
    print_error(request_id, "BAD_PAYLOAD", "expected_even_hex_payload");
    return;
  }

  uint8_t sender_key[AES128_KEY_BYTES] = {0};
  uint8_t receiver_key[AES128_KEY_BYTES] = {0};
  uint8_t nonce[AES_GCM_NONCE_BYTES] = {0};
  uint8_t ciphertext[MAX_EXPERIMENT_PAYLOAD] = {0};
  uint8_t decrypted[MAX_EXPERIMENT_PAYLOAD] = {0};
  uint8_t tag[AES_GCM_TAG_BYTES] = {0};
  FairKexMetrics kex_metrics = {};
  uint32_t kdf_us = 0;
  uint32_t rng_total_us = 0;
  uint32_t encrypt_total_us = 0;
  uint32_t decrypt_total_us = 0;
  uint32_t messages_ok = 0;

  const uint32_t heap_before = ESP.getFreeHeap();
  const uint32_t min_heap_before = ESP.getMinFreeHeap();
  const uint32_t largest_block_before =
      static_cast<uint32_t>(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));
  const uint32_t stack_hwm_before =
      static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr));
  const uint32_t started = micros();

  char context[72];
  snprintf(
      context,
      sizeof(context),
      "PQC-SAT|SESSION_BENCH|%s|v1",
      fair_kex_name(algorithm));
  bool session_ok = establish_fair_session(
      algorithm,
      context,
      sender_key,
      receiver_key,
      &kex_metrics,
      &kdf_us);

  const uint32_t data_started = micros();
  if (session_ok) {
    const uint32_t rng_started = micros();
    session_ok = fair_random_bytes(nonce, AES_GCM_NONCE_BYTES - sizeof(uint32_t)) == 0;
    rng_total_us = micros() - rng_started;
  }

  char aad[80];
  snprintf(
      aad,
      sizeof(aad),
      "PQC-SAT|SESSION_BENCH|%s|%lu|v1",
      fields[3],
      static_cast<unsigned long>(messages));
  for (uint32_t index = 0; session_ok && index < messages; ++index) {
    write_u32_be(
        &nonce[AES_GCM_NONCE_BYTES - sizeof(uint32_t)],
        index + 1U);
    uint32_t operation_started = micros();
    const bool encrypted = fair_aes128_gcm_encrypt_message(
        sender_key,
        nonce,
        reinterpret_cast<const uint8_t *>(aad),
        strlen(aad),
        payload,
        payload_len,
        ciphertext,
        tag);
    encrypt_total_us += micros() - operation_started;

    operation_started = micros();
    const bool decrypted_ok = encrypted && fair_aes128_gcm_decrypt_message(
        receiver_key,
        nonce,
        reinterpret_cast<const uint8_t *>(aad),
        strlen(aad),
        ciphertext,
        payload_len,
        tag,
        decrypted);
    decrypt_total_us += micros() - operation_started;
    const bool matched =
        decrypted_ok && bytes_equal_constant_time(payload, decrypted, payload_len);
    if (!matched) {
      session_ok = false;
      break;
    }
    messages_ok++;
    if ((index & 31U) == 31U) {
      delay(0);
    }
  }
  const uint32_t data_total_us = micros() - data_started;
  const uint32_t end_to_end_us = micros() - started;
  const uint32_t heap_after = ESP.getFreeHeap();
  const uint32_t min_heap_global = ESP.getMinFreeHeap();
  const uint32_t largest_block_after =
      static_cast<uint32_t>(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL));
  const uint32_t stack_hwm_after =
      static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr));
  const uint32_t stack_hwm_words =
      stack_hwm_after < stack_hwm_before ? stack_hwm_after : stack_hwm_before;

  const uint32_t setup_bytes = kex_metrics.setup_bytes;
  const uint32_t response_bytes = kex_metrics.response_bytes;
  const uint32_t handshake_bytes = setup_bytes + response_bytes;
  const uint32_t data_bytes_per_message =
      static_cast<uint32_t>(payload_len) + AES_GCM_NONCE_BYTES + AES_GCM_TAG_BYTES;
  const uint32_t data_total_bytes = data_bytes_per_message * messages;
  const uint32_t wire_total_bytes = handshake_bytes + data_total_bytes;
  const bool all_ok =
      session_ok && kex_metrics.key_match && messages_ok == messages;

  begin_result(request_id, all_ok ? "OK" : "ERROR");
  print_kv("op", "session_benchmark");
  print_kv("session_bench", FAIR_SESSION_BENCH);
  print_fair_metadata(algorithm);
  print_kv("cipher", AEAD_CIPHER);
  print_kv("scenario", fields[3]);
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("messages", messages);
  print_kv_u32("messages_ok", messages_ok);
  print_kv_bool("key_match", kex_metrics.key_match);
  print_kv_bool("aead_match", all_ok);
  print_kv_u32("setup_us", kex_metrics.setup_us);
  print_kv_u32("initiator_us", kex_metrics.initiator_us);
  print_kv_u32("responder_us", kex_metrics.responder_us);
  print_kv_u32("kex_total_us", kex_metrics.kex_total_us);
  print_kv_u32("kdf_us", kdf_us);
  print_kv_u32("session_setup_us", kex_metrics.kex_total_us + kdf_us);
  print_kv_u32("rng_total_us", rng_total_us);
  print_kv_u32("encrypt_total_us", encrypt_total_us);
  print_kv_u32("decrypt_total_us", decrypt_total_us);
  print_kv_u32("data_total_us", data_total_us);
  print_kv_u32("end_to_end_us", end_to_end_us);
  print_kv_u32("amortized_us_per_message", end_to_end_us / messages);
  print_kv_u32("bytes_payload", static_cast<uint32_t>(payload_len));
  print_kv_u32("setup_bytes", setup_bytes);
  print_kv_u32("response_bytes", response_bytes);
  print_kv_u32("handshake_bytes", handshake_bytes);
  print_kv_u32("data_bytes_per_message", data_bytes_per_message);
  print_kv_u32("data_total_bytes", data_total_bytes);
  print_kv_u32("wire_total_bytes", wire_total_bytes);
  print_kv_u32("amortized_bytes_per_message", wire_total_bytes / messages);
  print_kv_u32("heap_before", heap_before);
  print_kv_u32("heap_after", heap_after);
  print_kv_i32(
      "heap_delta",
      static_cast<int32_t>(heap_before) - static_cast<int32_t>(heap_after));
  print_kv_u32("min_heap_before", min_heap_before);
  print_kv_u32("min_heap_global", min_heap_global);
  print_kv_u32("largest_block_before", largest_block_before);
  print_kv_u32("largest_block_after", largest_block_after);
  print_kv_u32("stack_hwm_words", stack_hwm_words);
  end_result();

  secure_wipe(sender_key, sizeof(sender_key));
  secure_wipe(receiver_key, sizeof(receiver_key));
  secure_wipe(nonce, sizeof(nonce));
  secure_wipe(ciphertext, sizeof(ciphertext));
  secure_wipe(decrypted, sizeof(decrypted));
  secure_wipe(tag, sizeof(tag));
  secure_wipe(fair_sender_secret, sizeof(fair_sender_secret));
  secure_wipe(fair_receiver_secret, sizeof(fair_receiver_secret));
}

static void handle_stress(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 6) {
    print_error(request_id, "BAD_ARGS", "expected_PQC_LOOP_n_CONFIRM");
    return;
  }

  uppercase_ascii(fields[3]);
  uppercase_ascii(fields[5]);
  if (strcmp(fields[3], "PQC_LOOP") != 0) {
    print_error(request_id, "BAD_STRESS_MODE", "expected_PQC_LOOP");
    return;
  }
  if (strcmp(fields[5], "CONFIRM") != 0) {
    print_error(request_id, "CONFIRM_REQUIRED", "append_CONFIRM");
    return;
  }

  int parsed = 0;
  if (!parse_int_range(fields[4], 1, 500, &parsed)) {
    print_error(request_id, "BAD_ROUNDS", "expected_1_to_500");
    return;
  }

  const uint16_t rounds = static_cast<uint16_t>(parsed);
  const uint32_t started = micros();
  uint64_t total_keygen = 0;
  uint64_t total_encap = 0;
  uint64_t total_decap = 0;
  uint16_t ok = 0;
  bool last_match = false;

  set_rgb(255, 80, 0);
  set_bar_percent(5);

  for (uint16_t i = 0; i < rounds; ++i) {
    uint32_t keygen_us = 0;
    uint32_t encap_us = 0;
    uint32_t decap_us = 0;
    bool key_match = false;
    if (run_pqc_round(&keygen_us, &encap_us, &decap_us, &key_match)) {
      ok++;
    }
    last_match = key_match;
    total_keygen += keygen_us;
    total_encap += encap_us;
    total_decap += decap_us;
    if ((i % 25U) == 0U || i + 1U == rounds) {
      const uint8_t percent = static_cast<uint8_t>(((static_cast<uint32_t>(i) + 1U) * 100U) / rounds);
      set_bar_percent(percent);
    }
    delay(0);
  }

  const bool all_ok = ok == rounds;
  if (all_ok) {
    set_main_led_rgb(0, 255, 120);
  } else {
    set_main_led_rgb(255, 20, 40);
  }

  begin_result(request_id, all_ok ? "OK" : "ERROR");
  print_kv("op", "pqc_stress");
  print_kv("mode", "PQC_LOOP");
  print_kv_u32("n", rounds);
  print_kv_u32("ok", ok);
  print_kv_bool("key_match", last_match);
  print_kv_u32("keygen_avg_us", static_cast<uint32_t>(total_keygen / rounds));
  print_kv_u32("encap_avg_us", static_cast<uint32_t>(total_encap / rounds));
  print_kv_u32("decap_avg_us", static_cast<uint32_t>(total_decap / rounds));
  print_kv_u32("elapsed_us", micros() - started);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  end_result();
}

static void handle_mission(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count < 4 || field_count > 5) {
    print_error(request_id, "BAD_ARGS", "expected_legacy_or_ECDH_MLKEM_scenario_payloadhex");
    return;
  }

  uppercase_ascii(fields[3]);
  const bool scenario_classic = strcmp(fields[3], "CLASSIC") == 0;
  const bool scenario_classic_crc = strcmp(fields[3], "CLASSIC_CRC32") == 0;
  const bool scenario_pqc = strcmp(fields[3], "PQC") == 0;
  const bool scenario_pqc_crc = strcmp(fields[3], "PQC_CRC32") == 0 || strcmp(fields[3], "PQC+CRC32") == 0;
  const bool scenario_ecdh = strcmp(fields[3], "ECDH") == 0;
  const bool scenario_ecdh_crc = strcmp(fields[3], "ECDH_CRC32") == 0;
  const bool scenario_mlkem = strcmp(fields[3], "MLKEM") == 0;
  const bool scenario_mlkem_crc = strcmp(fields[3], "MLKEM_CRC32") == 0;
  const bool use_fair = scenario_ecdh || scenario_ecdh_crc || scenario_mlkem || scenario_mlkem_crc;
  if (!scenario_classic && !scenario_classic_crc && !scenario_pqc && !scenario_pqc_crc && !use_fair) {
    print_error(request_id, "BAD_SCENARIO", "expected_CLASSIC_PQC_ECDH_or_MLKEM_with_optional_CRC32");
    return;
  }
  if (use_fair && !fair_crypto_available()) {
    print_error(request_id, "KEX_UNAVAILABLE", "build_robocore_wisdom_esp32_fair");
    return;
  }

  uint8_t payload[MAX_EXPERIMENT_PAYLOAD];
  size_t payload_len = 0;
  if (!mission_payload_from_fields(field_count, fields, payload, sizeof(payload), &payload_len)) {
    print_error(request_id, "BAD_PAYLOAD", "expected_even_hex_payload");
    return;
  }

  const bool use_pqc = scenario_pqc || scenario_pqc_crc;
  const bool use_crc = scenario_classic_crc || scenario_pqc_crc || scenario_ecdh_crc || scenario_mlkem_crc;
  const FairKexAlgorithm fair_algorithm =
      (scenario_ecdh || scenario_ecdh_crc) ? FAIR_KEX_ECDH_P256 : FAIR_KEX_MLKEM512;
  const char *scenario =
      scenario_mlkem_crc ? "MLKEM_CRC32" :
      scenario_mlkem ? "MLKEM" :
      scenario_ecdh_crc ? "ECDH_CRC32" :
      scenario_ecdh ? "ECDH" :
      scenario_pqc_crc ? "PQC_CRC32" :
      scenario_pqc ? "PQC" :
      scenario_classic_crc ? "CLASSIC_CRC32" : "CLASSIC";

  bool key_match = true;
  bool tag_ready = false;
  bool tag_match = false;
  bool aead_match = false;
  bool decrypt_ok = false;
  bool crc_match = true;
  uint32_t keygen_us = 0;
  uint32_t encap_us = 0;
  uint32_t decap_us = 0;
  uint32_t setup_us = 0;
  uint32_t initiator_us = 0;
  uint32_t responder_us = 0;
  uint32_t kex_total_us = 0;
  uint32_t setup_bytes = 0;
  uint32_t response_bytes = 0;
  uint32_t rng_us = 0;
  uint32_t kdf_us = 0;
  uint32_t encrypt_us = 0;
  uint32_t decrypt_us = 0;
  uint32_t tag_us = 0;
  uint32_t verify_us = 0;
  uint32_t crc_us = 0;
  uint32_t crc_tx = 0;
  uint32_t crc_rx = 0;
  const uint32_t bytes_mlkem =
      use_pqc ? CRYPTO_CIPHERTEXTBYTES :
      (scenario_mlkem || scenario_mlkem_crc) ? FAIR_MLKEM_CIPHERTEXT_BYTES : 0U;
  const uint32_t bytes_nonce = AES_GCM_NONCE_BYTES;
  const uint32_t bytes_gcm_tag = AES_GCM_TAG_BYTES;
  const uint32_t checksum_bytes = use_crc ? MISSION_CRC_BYTES : 0U;
  const size_t ciphertext_len = payload_len + checksum_bytes;
  const uint32_t payload_crc = crc32_bytes(payload, payload_len);
  uint8_t protected_payload[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t ciphertext[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t decrypted[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t aes_key_enc[AES128_KEY_BYTES];
  uint8_t aes_key_dec[AES128_KEY_BYTES];
  uint8_t nonce[AES_GCM_NONCE_BYTES];
  uint8_t gcm_tag[AES_GCM_TAG_BYTES];
  memset(ciphertext, 0, sizeof(ciphertext));
  memset(decrypted, 0, sizeof(decrypted));
  memset(aes_key_enc, 0, sizeof(aes_key_enc));
  memset(aes_key_dec, 0, sizeof(aes_key_dec));
  memset(nonce, 0, sizeof(nonce));
  memset(gcm_tag, 0, sizeof(gcm_tag));
  memcpy(protected_payload, payload, payload_len);

  const uint32_t started = micros();
  if (use_crc) {
    const uint32_t crc_started = micros();
    crc_tx = payload_crc;
    write_u32_be(&protected_payload[payload_len], crc_tx);
    crc_us = micros() - crc_started;
  }

  if (use_fair) {
    FairKexMetrics fair_metrics = {};
    char kdf_context[96];
    snprintf(
        kdf_context,
        sizeof(kdf_context),
        "PQC-SAT|MISSION|%s|AES-128-GCM|KEX_FAIR_V1",
        scenario);
    if (!establish_fair_session(
            fair_algorithm,
            kdf_context,
            aes_key_enc,
            aes_key_dec,
            &fair_metrics,
            &kdf_us)) {
      secure_wipe(aes_key_enc, sizeof(aes_key_enc));
      secure_wipe(aes_key_dec, sizeof(aes_key_dec));
      print_error(request_id, "KEX_FAILED", fair_kex_name(fair_algorithm));
      return;
    }
    key_match = fair_metrics.key_match;
    setup_us = fair_metrics.setup_us;
    initiator_us = fair_metrics.initiator_us;
    responder_us = fair_metrics.responder_us;
    kex_total_us = fair_metrics.kex_total_us;
    setup_bytes = fair_metrics.setup_bytes;
    response_bytes = fair_metrics.response_bytes;
    keygen_us = setup_us;
    encap_us = initiator_us;
    decap_us = responder_us;
  } else if (use_pqc) {
    uint32_t op_started = micros();
    int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
    keygen_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "mission_keygen", rc, micros() - started);
      return;
    }

    op_started = micros();
    rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
    encap_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "mission_encap", rc, micros() - started);
      return;
    }

    op_started = micros();
    rc = crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk);
    decap_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "mission_decap", rc, micros() - started);
      return;
    }

    key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
    pqc_keypair_ready = true;
    pqc_ciphertext_ready = true;
    pqc_shared_secret_ready = key_match;

    op_started = micros();
    const bool key_a = derive_mission_aes128_key(pqc_ss_enc, CRYPTO_BYTES, scenario, aes_key_enc);
    const bool key_b = derive_mission_aes128_key(pqc_ss_dec, CRYPTO_BYTES, scenario, aes_key_dec);
    kdf_us = micros() - op_started;
    if (!key_a || !key_b) {
      secure_wipe(aes_key_enc, sizeof(aes_key_enc));
      secure_wipe(aes_key_dec, sizeof(aes_key_dec));
      print_error(request_id, "AEAD_KDF_FAILED", "aes_key_derivation");
      return;
    }
  } else {
    uint32_t op_started = micros();
    if (!fill_random_bytes(aes_key_enc, sizeof(aes_key_enc))) {
      print_error(request_id, "RNG_FAILED", "classic_session_key");
      return;
    }
    memcpy(aes_key_dec, aes_key_enc, sizeof(aes_key_dec));
    rng_us += micros() - op_started;
  }

  uint32_t op_started = micros();
  const bool nonce_ok = use_fair
                            ? fair_random_bytes(nonce, sizeof(nonce)) == 0
                            : fill_random_bytes(nonce, sizeof(nonce));
  if (!nonce_ok) {
    secure_wipe(aes_key_enc, sizeof(aes_key_enc));
    secure_wipe(aes_key_dec, sizeof(aes_key_dec));
    print_error(request_id, "RNG_FAILED", "gcm_nonce");
    return;
  }
  rng_us += micros() - op_started;

  char aad[80];
  snprintf(aad, sizeof(aad), "PQC-SAT|MISSION|%s|v1", scenario);

  op_started = micros();
  const bool encrypt_ok =
      use_fair
          ? fair_aes128_gcm_encrypt_message(
                aes_key_enc,
                nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                protected_payload,
                ciphertext_len,
                ciphertext,
                gcm_tag)
          : aes128_gcm_encrypt(
                aes_key_enc,
                nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                protected_payload,
                ciphertext_len,
                ciphertext,
                gcm_tag);
  encrypt_us = micros() - op_started;

  op_started = micros();
  decrypt_ok =
      use_fair
          ? fair_aes128_gcm_decrypt_message(
                aes_key_dec,
                nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                ciphertext,
                ciphertext_len,
                gcm_tag,
                decrypted)
          : aes128_gcm_decrypt(
                aes_key_dec,
                nonce,
                reinterpret_cast<const uint8_t *>(aad),
                strlen(aad),
                ciphertext,
                ciphertext_len,
                gcm_tag,
                decrypted);
  decrypt_us = micros() - op_started;

  tag_us = encrypt_us;
  verify_us = decrypt_us;
  tag_ready = encrypt_ok;
  aead_match = encrypt_ok && decrypt_ok && bytes_equal_constant_time(protected_payload, decrypted, ciphertext_len);
  tag_match = aead_match;

  if (use_crc) {
    const uint32_t crc_started = micros();
    if (decrypt_ok && ciphertext_len >= payload_len + MISSION_CRC_BYTES) {
      crc_rx = crc32_bytes(decrypted, payload_len);
      const uint32_t crc_field = read_u32_be(&decrypted[payload_len]);
      crc_match = crc_rx == crc_field;
    } else {
      crc_match = false;
    }
    crc_us += micros() - crc_started;
  }

  secure_wipe(aes_key_enc, sizeof(aes_key_enc));
  secure_wipe(aes_key_dec, sizeof(aes_key_dec));

  const bool delivered = key_match && tag_match && (!use_crc || crc_match);
  const uint32_t elapsed_us = micros() - started;
  if (!use_fair && use_pqc) {
    response_bytes = CRYPTO_CIPHERTEXTBYTES;
  }
  const uint32_t data_bytes =
      static_cast<uint32_t>(ciphertext_len) + bytes_nonce + bytes_gcm_tag;
  const uint32_t bytes_crypto =
      setup_bytes + response_bytes + bytes_nonce + bytes_gcm_tag;
  const uint32_t bytes_total = static_cast<uint32_t>(ciphertext_len) + bytes_crypto;
  const uint32_t bytes_preprovisioned = response_bytes + data_bytes;

  begin_result(request_id, "OK");
  print_kv("scenario", scenario);
  print_kv("op", "mission_message");
  print_kv("message", "HELLO_UFF");
  print_kv("result", delivered ? "DELIVERED" : "REJECTED");
  print_kv(
      "crypto",
      use_fair ? fair_kex_name(fair_algorithm) :
      use_pqc ? PQC_TARGET : CLASSIC_TARGET);
  print_kv("cipher", AEAD_CIPHER);
  print_kv("checksum", use_crc ? "CRC32" : "NONE");
  print_kv("confirmation", AEAD_CIPHER);
  print_kv(
      "key_source",
      use_fair ? fair_kex_name(fair_algorithm) :
      use_pqc ? PQC_TARGET : "RANDOM_SESSION");
  print_kv("key_policy", "ephemeral_per_message");
  if (use_fair) {
    print_fair_metadata(fair_algorithm);
  } else {
    print_kv("experiment", "LEGACY_V1");
  }
  print_kv_bool("key_match", key_match);
  print_kv_bool("tag_ready", tag_ready);
  print_kv_bool("tag_match", tag_match);
  print_kv_bool("aead_match", aead_match);
  print_kv_bool("decrypt_ok", decrypt_ok);
  print_kv_bool("crc_match", crc_match);
  print_kv_u32("payload_len", payload_len);
  print_kv_hex_u32("payload_crc32", payload_crc);
  if (use_crc) {
    print_kv_hex_u32("crc_tx", crc_tx);
    print_kv_hex_u32("crc_rx", crc_rx);
  }
  print_kv_u32("bytes_payload", payload_len);
  print_kv_u32("bytes_ciphertext", ciphertext_len);
  print_kv_u32("bytes_mlkem", bytes_mlkem);
  print_kv_u32("bytes_nonce", bytes_nonce);
  print_kv_u32("bytes_gcm_tag", bytes_gcm_tag);
  print_kv_u32("bytes_crypto", bytes_crypto);
  print_kv_u32("bytes_checksum", checksum_bytes);
  print_kv_u32("bytes_total", bytes_total);
  print_kv_u32("setup_bytes", setup_bytes);
  print_kv_u32("response_bytes", response_bytes);
  print_kv_u32("data_bytes", data_bytes);
  print_kv_u32("wire_total_fresh", bytes_total);
  print_kv_u32("wire_total_preprovisioned", bytes_preprovisioned);
  print_kv_u32("nonce_bytes", bytes_nonce);
  print_kv_u32("gcm_tag_bytes", bytes_gcm_tag);
  print_kv_u32("ciphertext_bytes", ciphertext_len);
  print_kv_hex_u32("nonce_crc32", crc32_bytes(nonce, sizeof(nonce)));
  print_kv_hex_u32("ciphertext_crc32", crc32_bytes(ciphertext, ciphertext_len));
  print_kv_hex_u32("gcm_tag_crc32", crc32_bytes(gcm_tag, sizeof(gcm_tag)));
  print_kv_u32("keygen_us", keygen_us);
  print_kv_u32("encap_us", encap_us);
  print_kv_u32("decap_us", decap_us);
  print_kv_u32("setup_us", setup_us);
  print_kv_u32("initiator_us", initiator_us);
  print_kv_u32("responder_us", responder_us);
  print_kv_u32("kex_total_us", kex_total_us);
  print_kv_u32("online_us", elapsed_us >= setup_us ? elapsed_us - setup_us : elapsed_us);
  print_kv_u32("end_to_end_us", elapsed_us);
  print_kv_u32("rng_us", rng_us);
  print_kv_u32("kdf_us", kdf_us);
  print_kv_u32("encrypt_us", encrypt_us);
  print_kv_u32("decrypt_us", decrypt_us);
  print_kv_u32("tag_us", tag_us);
  print_kv_u32("verify_us", verify_us);
  print_kv_u32("crc_us", crc_us);
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  end_result();
  secure_wipe(fair_sender_secret, sizeof(fair_sender_secret));
  secure_wipe(fair_receiver_secret, sizeof(fair_receiver_secret));
}

static void handle_game_begin(const char *request_id, size_t field_count, char *fields[]) {
  clear_staged_game(true);
  if (field_count != 9) {
    staged_game_error(request_id, "BAD_ARGS", "expected_id_profile_keymode_guard_incident_payloadhex");
    return;
  }
  uppercase_ascii(fields[4]);
  uppercase_ascii(fields[5]);
  uppercase_ascii(fields[6]);
  uppercase_ascii(fields[7]);
  if (!is_token_safe(fields[3]) || strlen(fields[3]) >= sizeof(staged_game.id)) {
    staged_game_error(request_id, "BAD_GAME_ID", "expected_safe_id_up_to_31_chars");
    return;
  }
  const bool key_classic = strcmp(fields[5], "CLASSIC") == 0;
  const bool key_pqc = strcmp(fields[5], "PQC") == 0;
  const bool key_ecdh = strcmp(fields[5], "ECDH") == 0;
  const bool key_mlkem = strcmp(fields[5], "MLKEM") == 0;
  const bool key_fair = key_ecdh || key_mlkem;
  const bool guard_none = strcmp(fields[6], "NONE") == 0;
  const bool guard_crc = strcmp(fields[6], "CRC32") == 0;
  const bool incident_valid = strcmp(fields[7], "NORMAL") == 0 ||
                              strcmp(fields[7], "CHANNEL_BITFLIP") == 0 ||
                              strcmp(fields[7], "TAMPER") == 0 ||
                              strcmp(fields[7], "RX_MEMORY") == 0;
  if ((!key_classic && !key_pqc && !key_fair) || (!guard_none && !guard_crc) || !incident_valid) {
    staged_game_error(request_id, "BAD_ARGS", "expected_CLASSIC_PQC_ECDH_or_MLKEM_NONE_or_CRC32_valid_incident");
    return;
  }
  if (key_fair && !fair_crypto_available()) {
    staged_game_error(request_id, "KEX_UNAVAILABLE", "build_robocore_wisdom_esp32_fair");
    return;
  }
  if (!apply_profile(fields[4])) {
    staged_game_error(request_id, "BAD_PROFILE", "unsupported_or_rejected");
    return;
  }
  const uint32_t started = micros();
  if (!parse_hex_payload(
          fields[8],
          staged_game.payload,
          sizeof(staged_game.payload),
          &staged_game.payload_len)) {
    staged_game_error(request_id, "BAD_PAYLOAD", "expected_even_hex_payload_up_to_96_bytes");
    return;
  }
  snprintf(staged_game.id, sizeof(staged_game.id), "%s", fields[3]);
  snprintf(staged_game.profile, sizeof(staged_game.profile), "%s", fields[4]);
  snprintf(staged_game.key_mode, sizeof(staged_game.key_mode), "%s", fields[5]);
  snprintf(staged_game.guard, sizeof(staged_game.guard), "%s", fields[6]);
  snprintf(staged_game.incident, sizeof(staged_game.incident), "%s", fields[7]);
  staged_game.use_pqc = key_pqc;
  staged_game.use_fair = key_fair;
  staged_game.fair_algorithm = key_ecdh ? FAIR_KEX_ECDH_P256 : FAIR_KEX_MLKEM512;
  staged_game.use_app_crc = guard_crc;
  staged_game.protected_len = staged_game.payload_len + (guard_crc ? MISSION_CRC_BYTES : 0U);
  memcpy(staged_game.protected_payload, staged_game.payload, staged_game.payload_len);
  staged_game.app_crc_tx = 0;
  if (guard_crc) {
    staged_game.app_crc_tx = crc32_bytes(staged_game.payload, staged_game.payload_len);
    write_u32_be(&staged_game.protected_payload[staged_game.payload_len], staged_game.app_crc_tx);
  }
  staged_game.active = true;
  staged_game.state = GAME_PREPARED;
  set_main_led_rgb(0, 80, 255);
  set_bar_percent(20);

  begin_result(request_id, "OK");
  print_staged_game_common("PREPARE", "READY", micros() - started);
  print_kv_u32("bytes_protected", staged_game.protected_len);
  print_kv_bool("app_crc_present", staged_game.use_app_crc);
  print_kv_hex_u32("app_crc_tx", staged_game.app_crc_tx);
  print_kv_hex_u32("payload_crc32", crc32_bytes(staged_game.payload, staged_game.payload_len));
  end_result();
}

static void handle_game_protect(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4 || !staged_game_matches(fields[3], GAME_PREPARED)) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_PROTECT_requires_matching_PREPARE");
    return;
  }
  const bool public_key_kex = staged_game.use_pqc || staged_game.use_fair;
  set_main_led_rgb(public_key_kex ? 180 : 0, 0, public_key_kex ? 255 : 220);
  set_bar_percent(45);
  if (!build_staged_game_protection()) {
    staged_game_error(request_id, "GAME_PROTECT_FAILED", "key_or_aes_gcm_setup");
    return;
  }
  staged_game.state = GAME_PROTECTED;
  set_main_led_rgb(0, 220, 255);
  set_bar_percent(60);
  begin_result(request_id, "OK");
  print_staged_game_common("PROTECT", "PROTECTED", staged_game.protect_elapsed_us);
  print_kv_bool("key_match", staged_game.key_match);
  print_kv_bool("aead_ready", true);
  print_kv_hex_u32("nonce_crc32", staged_game.nonce_crc32);
  print_kv_hex_u32("session_key_crc32", staged_game.session_key_crc32);
  print_kv_u32("keygen_us", staged_game.keygen_us);
  print_kv_u32("encap_us", staged_game.encap_us);
  print_kv_u32("decap_us", staged_game.decap_us);
  print_kv_u32("setup_us", staged_game.setup_us);
  print_kv_u32("initiator_us", staged_game.initiator_us);
  print_kv_u32("responder_us", staged_game.responder_us);
  print_kv_u32("kex_total_us", staged_game.kex_total_us);
  print_kv_u32("kdf_us", staged_game.kdf_us);
  print_kv_u32("rng_us", staged_game.rng_us);
  print_kv_u32("encrypt_us", staged_game.encrypt_us);
  if (staged_game.use_fair) {
    // print_staged_game_common already emitted experiment=KEX_FAIR_V1.
    print_fair_metadata(staged_game.fair_algorithm, false);
  }
  end_result();
}

static void handle_game_transmit(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 6 || !staged_game_matches(fields[3], GAME_PROTECTED)) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_TRANSMIT_requires_matching_PROTECT");
    return;
  }
  int byte_index = 0;
  uint8_t bit_mask = 0;
  if (!parse_int_range(fields[4], 0, static_cast<int>(staged_game.payload_len) - 1, &byte_index) ||
      !parse_u8_auto(fields[5], &bit_mask) || !is_single_bit_mask(bit_mask)) {
    staged_game_error(request_id, "BAD_FAULT_VECTOR", "expected_payload_index_and_single_bit_mask");
    return;
  }
  const uint32_t started = micros();
  staged_game.byte_index = static_cast<uint8_t>(byte_index);
  staged_game.bit_mask = bit_mask;
  set_main_led_rgb(255, 255, 255);
  set_bar_percent(78);
  if (!transmit_staged_game_incident(staged_game.incident)) {
    staged_game_error(request_id, "GAME_TRANSMIT_FAILED", "frame_construction");
    return;
  }
  staged_game.state = GAME_TRANSMITTED;
  begin_result(request_id, "OK");
  print_staged_game_common("TRANSMIT", "IN_FLIGHT", micros() - started);
  print_kv_u32("byte_index", staged_game.byte_index);
  print_kv_hex_u8("bit_mask", staged_game.bit_mask);
  print_kv_hex_u32("frame_crc_tx", staged_game.frame_crc_tx);
  print_kv_hex_u32("frame_crc_rx", staged_game.frame_crc_rx);
  print_kv_bool("frame_crc_match", staged_game.frame_crc_match);
  end_result();
}

static void handle_game_verify(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4 || !staged_game_matches(fields[3], GAME_TRANSMITTED)) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_VERIFY_requires_matching_TRANSMIT");
    return;
  }
  const uint32_t started = micros();
  if (!verify_staged_game_incident(staged_game.incident)) {
    staged_game_error(request_id, "INTERNAL_CONTRADICTION", "verification_truth_table");
    return;
  }
  staged_game.state = GAME_VERIFIED;
  if (staged_game.accepted) {
    set_main_led_rgb(0, 255, 100);
  } else {
    set_main_led_rgb(255, 20, 40);
  }
  set_bar_percent(100);
  begin_result(request_id, "OK");
  print_staged_game_verification("VERIFY", micros() - started);
  print_kv_u32("decrypt_us", staged_game.decrypt_us);
  end_result();
  wipe_staged_game_secrets();
}

static void handle_game_retry(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4 || !staged_game_matches(fields[3], GAME_VERIFIED)) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_RETRY_requires_matching_VERIFY");
    return;
  }
  const uint32_t old_nonce_crc32 = staged_game.nonce_crc32;
  const uint32_t old_key_crc32 = staged_game.session_key_crc32;
  const uint32_t payload_crc_before = crc32_bytes(staged_game.payload, staged_game.payload_len);
  const uint32_t started = micros();
  set_main_led_rgb(0, 130, 255);
  set_bar_percent(35);
  if (!build_staged_game_protection()) {
    staged_game_error(request_id, "GAME_RETRY_FAILED", "fresh_protection");
    return;
  }
  const bool fresh_nonce = staged_game.nonce_crc32 != old_nonce_crc32;
  const bool fresh_key = staged_game.session_key_crc32 != old_key_crc32;
  if (!fresh_nonce || !fresh_key || !transmit_staged_game_incident("NORMAL") ||
      !verify_staged_game_incident("NORMAL")) {
    staged_game_error(request_id, "GAME_RETRY_FAILED", "freshness_or_delivery");
    return;
  }
  const bool same_payload = payload_crc_before == crc32_bytes(staged_game.payload, staged_game.payload_len);
  staged_game.state = GAME_RETRIED;
  set_main_led_rgb(0, 255, 100);
  set_bar_percent(100);
  begin_result(request_id, "OK");
  print_staged_game_verification("RETRY", micros() - started);
  print_kv_bool("same_payload", same_payload);
  print_kv_bool("fresh_key", fresh_key);
  print_kv_bool("fresh_nonce", fresh_nonce);
  print_kv_hex_u32("nonce_crc32", staged_game.nonce_crc32);
  print_kv_hex_u32("session_key_crc32", staged_game.session_key_crc32);
  end_result();
  wipe_staged_game_secrets();
}

static void handle_game_end(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 5 || !staged_game.active || strcmp(fields[3], staged_game.id) != 0 ||
      (staged_game.state != GAME_VERIFIED && staged_game.state != GAME_RETRIED)) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_END_requires_matching_VERIFY_or_RETRY");
    return;
  }
  uppercase_ascii(fields[4]);
  const bool accept = strcmp(fields[4], "ACCEPT") == 0;
  const bool safe_mode = strcmp(fields[4], "SAFE_MODE") == 0;
  if (!accept && !safe_mode) {
    staged_game_error(request_id, "BAD_DECISION", "expected_ACCEPT_or_SAFE_MODE");
    return;
  }
  if (accept && staged_game.state == GAME_VERIFIED &&
      (strcmp(staged_game.final_result, "FRAME_REJECT") == 0 ||
       strcmp(staged_game.final_result, "AUTH_REJECT") == 0 ||
       strcmp(staged_game.final_result, "APP_REJECT") == 0)) {
    staged_game_error(request_id, "BAD_DECISION", "cryptographically_rejected_packet_cannot_be_accepted");
    return;
  }
  char game_id[sizeof(staged_game.id)];
  char final_result[sizeof(staged_game.final_result)];
  snprintf(game_id, sizeof(game_id), "%s", staged_game.id);
  snprintf(final_result, sizeof(final_result), "%s", staged_game.final_result);
  char decision[12];
  snprintf(decision, sizeof(decision), "%s", fields[4]);
  clear_staged_game(true);
  begin_result(request_id, "OK");
  print_kv("game_id", game_id);
  print_kv("stage", "END");
  print_kv("decision", decision);
  print_kv("final_result", final_result);
  print_kv_bool("session_cleared", true);
  print_kv("restored_profile", active_profile);
  print_kv_u32("restored_mhz", ESP.getCpuFreqMHz());
  end_result();
}

static void handle_game_abort(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4 || !staged_game.active || strcmp(fields[3], staged_game.id) != 0) {
    staged_game_error(request_id, "BAD_GAME_STATE", "GAME_ABORT_requires_matching_active_session");
    return;
  }
  char game_id[sizeof(staged_game.id)];
  snprintf(game_id, sizeof(game_id), "%s", staged_game.id);
  clear_staged_game(true);
  begin_result(request_id, "OK");
  print_kv("game_id", game_id);
  print_kv("stage", "ABORT");
  print_kv_bool("session_cleared", true);
  print_kv("restored_profile", active_profile);
  print_kv_u32("restored_mhz", ESP.getCpuFreqMHz());
  end_result();
}

static void handle_investigate(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 9) {
    print_error(request_id, "BAD_ARGS", "expected_scenario_incident_payload_index_mask_incidentid");
    return;
  }

  uppercase_ascii(fields[3]);
  uppercase_ascii(fields[4]);
  const bool scenario_classic = strcmp(fields[3], "CLASSIC") == 0;
  const bool scenario_classic_crc = strcmp(fields[3], "CLASSIC_CRC32") == 0;
  const bool scenario_pqc = strcmp(fields[3], "PQC") == 0;
  const bool scenario_pqc_crc = strcmp(fields[3], "PQC_CRC32") == 0;
  if (!scenario_classic && !scenario_classic_crc && !scenario_pqc && !scenario_pqc_crc) {
    print_error(request_id, "BAD_SCENARIO", "expected_CLASSIC_CLASSIC_CRC32_PQC_PQC_CRC32");
    return;
  }
  const bool incident_normal = strcmp(fields[4], "NORMAL") == 0;
  const bool incident_channel = strcmp(fields[4], "CHANNEL_BITFLIP") == 0;
  const bool incident_tamper = strcmp(fields[4], "TAMPER") == 0;
  const bool incident_memory = strcmp(fields[4], "RX_MEMORY") == 0;
  if (!incident_normal && !incident_channel && !incident_tamper && !incident_memory) {
    print_error(request_id, "BAD_INCIDENT", "expected_NORMAL_CHANNEL_BITFLIP_TAMPER_RX_MEMORY");
    return;
  }
  if (!is_token_safe(fields[8]) || strlen(fields[8]) > 63U) {
    print_error(request_id, "BAD_INCIDENT_ID", "expected_safe_token_up_to_63_chars");
    return;
  }

  uint8_t payload[MAX_EXPERIMENT_PAYLOAD];
  size_t payload_len = 0;
  if (!parse_hex_payload(fields[5], payload, sizeof(payload), &payload_len)) {
    print_error(request_id, "BAD_PAYLOAD", "expected_even_hex_payload");
    return;
  }
  int byte_index = 0;
  if (!parse_int_range(fields[6], 0, static_cast<int>(payload_len) - 1, &byte_index)) {
    print_error(request_id, "BAD_INDEX", "outside_payload");
    return;
  }
  uint8_t bit_mask = 0;
  if (!parse_u8_auto(fields[7], &bit_mask) || !is_single_bit_mask(bit_mask)) {
    print_error(request_id, "BAD_MASK", "expected_single_bit");
    return;
  }

  const bool use_pqc = scenario_pqc || scenario_pqc_crc;
  const bool use_app_crc = scenario_classic_crc || scenario_pqc_crc;
  const char *scenario = scenario_pqc_crc ? "PQC_CRC32" :
                         (scenario_pqc ? "PQC" : (scenario_classic_crc ? "CLASSIC_CRC32" : "CLASSIC"));
  const char *incident = fields[4];
  const size_t protected_len = payload_len + (use_app_crc ? MISSION_CRC_BYTES : 0U);
  const uint32_t started = micros();
  set_main_led_rgb(0, 80, 255);
  set_bar_percent(10);

  uint8_t protected_payload[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t ciphertext[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t decrypted[MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES];
  uint8_t aes_key_enc[AES128_KEY_BYTES];
  uint8_t aes_key_dec[AES128_KEY_BYTES];
  uint8_t nonce[AES_GCM_NONCE_BYTES];
  uint8_t gcm_tag[AES_GCM_TAG_BYTES];
  uint8_t frame[112 + CRYPTO_CIPHERTEXTBYTES + AES_GCM_NONCE_BYTES + MAX_EXPERIMENT_PAYLOAD + MISSION_CRC_BYTES + AES_GCM_TAG_BYTES];
  memset(protected_payload, 0, sizeof(protected_payload));
  memset(ciphertext, 0, sizeof(ciphertext));
  memset(decrypted, 0, sizeof(decrypted));
  memset(aes_key_enc, 0, sizeof(aes_key_enc));
  memset(aes_key_dec, 0, sizeof(aes_key_dec));
  memset(nonce, 0, sizeof(nonce));
  memset(gcm_tag, 0, sizeof(gcm_tag));
  memcpy(protected_payload, payload, payload_len);

  uint32_t app_crc_tx = 0;
  uint32_t app_crc_rx = 0;
  if (use_app_crc) {
    set_main_led_rgb(255, 180, 0);
    app_crc_tx = crc32_bytes(payload, payload_len);
    write_u32_be(&protected_payload[payload_len], app_crc_tx);
  }

  bool key_match = true;
  uint32_t keygen_us = 0;
  uint32_t encap_us = 0;
  uint32_t decap_us = 0;
  uint32_t kdf_us = 0;
  uint32_t rng_us = 0;
  if (use_pqc) {
    set_main_led_rgb(180, 0, 255);
    set_bar_percent(35);
    uint32_t op_started = micros();
    int rc = crypto_kem_keypair(pqc_pk, pqc_sk);
    keygen_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "investigate_keygen", rc, micros() - started);
      return;
    }
    op_started = micros();
    rc = crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk);
    encap_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "investigate_encap", rc, micros() - started);
      return;
    }
    op_started = micros();
    rc = crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk);
    decap_us = micros() - op_started;
    if (rc != 0) {
      print_pqc_error_result(request_id, "investigate_decap", rc, micros() - started);
      return;
    }
    key_match = pqc_shared_secrets_match(pqc_ss_enc, pqc_ss_dec);
    op_started = micros();
    const bool key_a = derive_mission_aes128_key(pqc_ss_enc, CRYPTO_BYTES, scenario, aes_key_enc);
    const bool key_b = derive_mission_aes128_key(pqc_ss_dec, CRYPTO_BYTES, scenario, aes_key_dec);
    kdf_us = micros() - op_started;
    if (!key_a || !key_b) {
      secure_wipe(aes_key_enc, sizeof(aes_key_enc));
      secure_wipe(aes_key_dec, sizeof(aes_key_dec));
      print_error(request_id, "AEAD_KDF_FAILED", "investigation_key_derivation");
      return;
    }
  } else {
    uint32_t op_started = micros();
    if (!fill_random_bytes(aes_key_enc, sizeof(aes_key_enc))) {
      print_error(request_id, "RNG_FAILED", "classic_session_key");
      return;
    }
    memcpy(aes_key_dec, aes_key_enc, sizeof(aes_key_dec));
    rng_us += micros() - op_started;
  }

  uint32_t op_started = micros();
  if (!fill_random_bytes(nonce, sizeof(nonce))) {
    secure_wipe(aes_key_enc, sizeof(aes_key_enc));
    secure_wipe(aes_key_dec, sizeof(aes_key_dec));
    print_error(request_id, "RNG_FAILED", "gcm_nonce");
    return;
  }
  rng_us += micros() - op_started;

  char aad[112];
  snprintf(aad, sizeof(aad), "PQC-SAT|INVESTIGATE|%s|%s|v1", scenario, incident);
  set_main_led_rgb(0, 220, 255);
  set_bar_percent(60);
  op_started = micros();
  const bool encrypt_ok = aes128_gcm_encrypt(
      aes_key_enc,
      nonce,
      reinterpret_cast<const uint8_t *>(aad),
      strlen(aad),
      protected_payload,
      protected_len,
      ciphertext,
      gcm_tag);
  const uint32_t encrypt_us = micros() - op_started;
  if (!encrypt_ok) {
    secure_wipe(aes_key_enc, sizeof(aes_key_enc));
    secure_wipe(aes_key_dec, sizeof(aes_key_dec));
    print_error(request_id, "AEAD_ENCRYPT_FAILED", "investigation_encrypt");
    return;
  }

  size_t frame_len = 0;
  memcpy(&frame[frame_len], aad, strlen(aad));
  frame_len += strlen(aad);
  if (use_pqc) {
    memcpy(&frame[frame_len], pqc_ct, CRYPTO_CIPHERTEXTBYTES);
    frame_len += CRYPTO_CIPHERTEXTBYTES;
  }
  memcpy(&frame[frame_len], nonce, sizeof(nonce));
  frame_len += sizeof(nonce);
  const size_t frame_cipher_offset = frame_len;
  memcpy(&frame[frame_len], ciphertext, protected_len);
  frame_len += protected_len;
  memcpy(&frame[frame_len], gcm_tag, sizeof(gcm_tag));
  frame_len += sizeof(gcm_tag);
  const uint32_t frame_crc_original = crc32_bytes(frame, frame_len);
  uint32_t frame_crc_tx = frame_crc_original;
  uint32_t frame_crc_rx = frame_crc_original;
  uint8_t before_byte = payload[byte_index];
  uint8_t after_byte = before_byte;

  set_main_led_rgb(255, 255, 255);
  set_bar_percent(78);
  if (incident_channel || incident_tamper) {
    before_byte = ciphertext[byte_index];
    ciphertext[byte_index] ^= bit_mask;
    after_byte = ciphertext[byte_index];
    frame[frame_cipher_offset + static_cast<size_t>(byte_index)] ^= bit_mask;
    frame_crc_rx = crc32_bytes(frame, frame_len);
    if (incident_tamper) {
      frame_crc_tx = frame_crc_rx;
    }
  }
  const bool frame_crc_match = frame_crc_tx == frame_crc_rx;

  op_started = micros();
  const bool decrypt_ok = aes128_gcm_decrypt(
      aes_key_dec,
      nonce,
      reinterpret_cast<const uint8_t *>(aad),
      strlen(aad),
      ciphertext,
      protected_len,
      gcm_tag,
      decrypted);
  const uint32_t decrypt_us = micros() - op_started;
  const bool aead_checked = true;
  const bool aead_match = decrypt_ok;

  if (incident_memory && decrypt_ok) {
    before_byte = decrypted[byte_index];
    decrypted[byte_index] ^= bit_mask;
    after_byte = decrypted[byte_index];
  }

  const bool app_crc_present = use_app_crc;
  const bool app_crc_checked = use_app_crc && decrypt_ok;
  bool app_crc_match = false;
  if (app_crc_checked) {
    app_crc_rx = crc32_bytes(decrypted, payload_len);
    const uint32_t stored_crc = read_u32_be(&decrypted[payload_len]);
    app_crc_match = app_crc_rx == stored_crc;
  }

  const bool accepted = frame_crc_match && aead_match && (!app_crc_present || app_crc_match);
  const char *result = "DELIVERED";
  if (incident_channel) {
    result = "FRAME_REJECT";
  } else if (incident_tamper) {
    result = "AUTH_REJECT";
  } else if (incident_memory) {
    result = use_app_crc ? "APP_REJECT" : "SILENT_CORRUPTION";
  }
  const bool expected_acceptance = incident_normal || (incident_memory && !use_app_crc);
  if (accepted != expected_acceptance) {
    result = "INTERNAL_CONTRADICTION";
  }

  secure_wipe(aes_key_enc, sizeof(aes_key_enc));
  secure_wipe(aes_key_dec, sizeof(aes_key_dec));
  const uint32_t elapsed_us = micros() - started;
  const uint32_t bytes_total = static_cast<uint32_t>(frame_len) + 4U;
  if (accepted) {
    set_main_led_rgb(0, 255, 100);
    set_bar_percent(100);
  } else {
    set_main_led_rgb(255, 20, 40);
    set_bar_percent(100);
  }

  begin_result(request_id, strcmp(result, "INTERNAL_CONTRADICTION") == 0 ? "ERROR" : "OK");
  print_kv("op", "investigate_message");
  print_kv("scenario", scenario);
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv("cipher", AEAD_CIPHER);
  print_kv("incident_id", fields[8]);
  print_kv("incident", incident);
  print_kv_u32("byte_index", static_cast<uint32_t>(byte_index));
  print_kv_hex_u8("bit_mask", bit_mask);
  print_kv_hex_u8("before_byte", before_byte);
  print_kv_hex_u8("after_byte", after_byte);
  print_kv_hex_u32("frame_crc_original", frame_crc_original);
  print_kv_hex_u32("frame_crc_tx", frame_crc_tx);
  print_kv_hex_u32("frame_crc_rx", frame_crc_rx);
  print_kv_bool("frame_crc_match", frame_crc_match);
  print_kv_bool("aead_checked", aead_checked);
  print_kv_bool("aead_match", aead_match);
  print_kv_bool("app_crc_present", app_crc_present);
  print_kv_bool("app_crc_checked", app_crc_checked);
  print_kv_bool("app_crc_match", app_crc_match);
  print_kv_bool("key_match", key_match);
  print_kv_bool("accepted", accepted);
  print_kv("result", result);
  print_kv_u32("bytes_payload", payload_len);
  print_kv_u32("bytes_total", bytes_total);
  print_kv_u32("bytes_frame_crc", 4);
  print_kv_hex_u32("app_crc_tx", app_crc_tx);
  print_kv_hex_u32("app_crc_rx", app_crc_rx);
  print_kv_u32("keygen_us", keygen_us);
  print_kv_u32("encap_us", encap_us);
  print_kv_u32("decap_us", decap_us);
  print_kv_u32("kdf_us", kdf_us);
  print_kv_u32("rng_us", rng_us);
  print_kv_u32("encrypt_us", encrypt_us);
  print_kv_u32("decrypt_us", decrypt_us);
  print_kv_u32("elapsed_us", elapsed_us);
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("min_heap", ESP.getMinFreeHeap());
  end_result();
}

static void send_peripherals(const char *request_id) {
  refresh_peripheral_presence();
  begin_result(request_id, "OK");
  print_kv_bool("oled", oled_present);
  print_kv_bool("apds9960", apds_present);
  print_kv_bool("htu21d", htu_present);
  print_kv_bool("mma8452", mma_present);
  print_kv("i2c", "sda21_scl22");
  end_result();
}

static void send_telemetry(const char *request_id) {
  telemetry_seq++;
  begin_result(request_id, "OK");
  print_kv_u32("seq", telemetry_seq);
  print_kv_u32("uptime_ms", millis());
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv_u32("heap", ESP.getFreeHeap());
  print_kv_u32("pot", analogRead(PIN_POT));
  print_kv_u32("sound", analogRead(PIN_SOUND));
  print_kv_bool("button", digitalRead(PIN_BUTTON) == LOW);
  print_kv_bool("relay", relay_state);
  end_result();
}

static void handle_fault(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 7) {
    print_error(request_id, "BAD_ARGS", "expected_guard_payloadhex_index_mask");
    return;
  }

  char *guard = fields[3];
  uppercase_ascii(guard);
  if (strcmp(guard, "NONE") != 0 && strcmp(guard, "CRC32") != 0) {
    print_error(request_id, "BAD_GUARD", "expected_NONE_or_CRC32");
    return;
  }

  uint8_t payload[MAX_EXPERIMENT_PAYLOAD];
  size_t payload_len = 0;
  if (!parse_hex_payload(fields[4], payload, sizeof(payload), &payload_len)) {
    print_error(request_id, "BAD_PAYLOAD", "expected_even_hex_payload");
    return;
  }

  int byte_index = 0;
  if (!parse_int_range(fields[5], 0, static_cast<int>(payload_len) - 1, &byte_index)) {
    print_error(request_id, "BAD_INDEX", "outside_payload");
    return;
  }

  uint8_t bit_mask = 0;
  if (!parse_u8_auto(fields[6], &bit_mask) || !is_single_bit_mask(bit_mask)) {
    print_error(request_id, "BAD_MASK", "expected_single_bit");
    return;
  }

  const uint32_t started = micros();
  const uint8_t before_byte = payload[byte_index];
  const uint32_t crc_before = crc32_bytes(payload, payload_len);
  payload[byte_index] ^= bit_mask;
  const uint8_t after_byte = payload[byte_index];
  const uint32_t crc_after = crc32_bytes(payload, payload_len);
  const uint32_t elapsed_us = micros() - started;

  const char *result = "OK";
  if (after_byte != before_byte) {
    result = (strcmp(guard, "CRC32") == 0 && crc_after != crc_before) ? "DETECTED_GUARD" : "SILENT";
  }

  begin_result(request_id, "OK");
  print_kv("result", result);
  print_kv("guard", guard);
  print_kv_u32("payload_len", payload_len);
  print_kv_u32("byte_index", static_cast<uint32_t>(byte_index));
  print_kv_hex_u8("bit_mask", bit_mask);
  print_kv_hex_u8("before_byte", before_byte);
  print_kv_hex_u8("after_byte", after_byte);
  print_kv_hex_u32("crc_before", crc_before);
  print_kv_hex_u32("crc_after", crc_after);
  print_kv_u32("elapsed_us", elapsed_us);
  end_result();
}

static void handle_features(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count == 3) {
    begin_result(request_id, "OK");
    print_kv("groups", "CORE,I2C,GPIO,ANALOG,EXPANSION");
    end_result();
    return;
  }

  uppercase_ascii(fields[3]);
  begin_result(request_id, "OK");
  if (strcmp(fields[3], "CORE") == 0) {
    print_kv("cpu", "ESP32-D0WD");
    print_kv("usb", "CP2102");
    print_kv("flash", "4MB");
  } else if (strcmp(fields[3], "I2C") == 0) {
    print_kv("bus", "SDA21,SCL22");
    print_kv("dev", "OLED,APDS9960,HTU21D,MMA8452,BRIICK");
  } else if (strcmp(fields[3], "GPIO") == 0) {
    print_kv("dev", "BARGRAPH,RGB,BUTTON,IR,RELAY,SERVO");
  } else if (strcmp(fields[3], "ANALOG") == 0) {
    print_kv("dev", "POT_A39,SOUND_A36");
  } else if (strcmp(fields[3], "EXPANSION") == 0) {
    print_kv("dev", "BRIICK_I2C,RELAY_D33,SERVO_D25");
  } else {
    print_kv("groups", "CORE,I2C,GPIO,ANALOG,EXPANSION");
  }
  end_result();
}

static void handle_boardmap(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count == 3) {
    begin_result(request_id, "OK");
    print_kv("groups", "I2C,GPIO,ANALOG,EXPANSION");
    end_result();
    return;
  }

  uppercase_ascii(fields[3]);
  begin_result(request_id, "OK");
  if (strcmp(fields[3], "I2C") == 0) {
    print_kv("sda", "21");
    print_kv("scl", "22");
    print_kv("addr", "OLED3C,APDS39,HTU40,MMA1D");
  } else if (strcmp(fields[3], "GPIO") == 0) {
    print_kv("bar", "17,16,4,13");
    print_kv("rgb", "R19,G23,B18");
    print_kv("button", "27");
    print_kv("ir", "26");
  } else if (strcmp(fields[3], "ANALOG") == 0) {
    print_kv("pot", "39");
    print_kv("sound", "36");
  } else if (strcmp(fields[3], "EXPANSION") == 0) {
    print_kv("servo", "25");
    print_kv("relay", "33");
    print_kv("briick", "I2C");
  } else {
    print_kv("groups", "I2C,GPIO,ANALOG,EXPANSION");
  }
  end_result();
}

static void handle_i2c_scan(const char *request_id) {
  char addrs[128];
  addrs[0] = '\0';
  uint8_t count = 0;

  for (uint8_t addr = 1; addr < 127; ++addr) {
    if (i2c_present(addr)) {
      char chunk[8];
      snprintf(chunk, sizeof(chunk), "%s%02X", count == 0 ? "" : ",", addr);
      strncat(addrs, chunk, sizeof(addrs) - strlen(addrs) - 1);
      count++;
      if (strlen(addrs) > 110) {
        break;
      }
    }
  }

  begin_result(request_id, "OK");
  print_kv_u32("count", count);
  print_kv("addr_hex", count == 0 ? "none" : addrs);
  end_result();
}

static void handle_profile(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_profile");
    return;
  }

  uppercase_ascii(fields[3]);
  if (!apply_profile(fields[3])) {
    print_error(request_id, "BAD_PROFILE", "unsupported_or_rejected");
    return;
  }

  begin_result(request_id, "OK");
  print_kv("profile", active_profile);
  print_kv_u32("cpu_mhz", ESP.getCpuFreqMHz());
  print_kv("radio", "off");
  end_result();
}

static void handle_led(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_on_off_toggle_color_test");
    return;
  }

  uppercase_ascii(fields[3]);
  if (strcmp(fields[3], "ON") == 0) {
    set_main_led_rgb(255, 255, 255);
  } else if (strcmp(fields[3], "OFF") == 0) {
    set_main_led_rgb(0, 0, 0);
  } else if (strcmp(fields[3], "TOGGLE") == 0) {
    if (rgb_r != 0 || rgb_g != 0 || rgb_b != 0 || builtin_led_state) {
      set_main_led_rgb(0, 0, 0);
    } else {
      set_main_led_rgb(255, 255, 255);
    }
  } else if (strcmp(fields[3], "TEST") == 0) {
    rgb_test_pattern();
  } else {
    uint8_t r = 0, g = 0, b = 0;
    if (!color_from_name(fields[3], &r, &g, &b)) {
      print_error(request_id, "BAD_LED_MODE", "expected_on_off_toggle_color_test");
      return;
    }
    set_main_led_rgb(r, g, b);
  }

  begin_result(request_id, "OK");
  print_kv("led", builtin_led_state ? "on" : "off");
  print_kv("target", "builtin_plus_rgb");
  print_kv_u32("r", rgb_r);
  print_kv_u32("g", rgb_g);
  print_kv_u32("b", rgb_b);
  end_result();
}

static void handle_rgb(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count == 4) {
    uppercase_ascii(fields[3]);
    if (strcmp(fields[3], "COMMON_ANODE") == 0) {
      rgb_common_anode = true;
      apply_rgb();
    } else if (strcmp(fields[3], "COMMON_CATHODE") == 0) {
      rgb_common_anode = false;
      apply_rgb();
    } else if (strcmp(fields[3], "OFF") == 0) {
      set_rgb(0, 0, 0);
    } else if (strcmp(fields[3], "TEST") == 0) {
      rgb_test_pattern();
    } else {
      print_error(request_id, "BAD_RGB_MODE", "expected_r_g_b_mode_or_test");
      return;
    }
  } else if (field_count == 6) {
    uint8_t r = 0, g = 0, b = 0;
    if (!parse_u8(fields[3], &r) || !parse_u8(fields[4], &g) || !parse_u8(fields[5], &b)) {
      print_error(request_id, "BAD_RGB_VALUE", "expected_0_255");
      return;
    }
    set_rgb(r, g, b);
  } else {
    print_error(request_id, "BAD_ARGS", "expected_rgb_values");
    return;
  }

  begin_result(request_id, "OK");
  print_kv_u32("r", rgb_r);
  print_kv_u32("g", rgb_g);
  print_kv_u32("b", rgb_b);
  print_kv("mode", rgb_common_anode ? "common_anode" : "common_cathode");
  end_result();
}

static void handle_bargraph(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count < 4 || field_count > 5) {
    print_error(request_id, "BAD_ARGS", "expected_level_percent_mode_test");
    return;
  }

  uppercase_ascii(fields[3]);
  if (field_count == 4) {
    if (strcmp(fields[3], "OFF") == 0) {
      set_bar_level(0);
    } else if (strcmp(fields[3], "ON") == 0) {
      set_bar_level(4);
    } else if (strcmp(fields[3], "TEST") == 0) {
      bargraph_test_pattern();
    } else if (strcmp(fields[3], "ACTIVE_LOW") == 0) {
      bar_active_low = true;
      apply_bargraph();
    } else if (strcmp(fields[3], "ACTIVE_HIGH") == 0) {
      bar_active_low = false;
      apply_bargraph();
    } else {
      int value = 0;
      if (!parse_int_range(fields[3], 0, 100, &value)) {
        print_error(request_id, "BAD_BAR_VALUE", "expected_0_4_or_0_100");
        return;
      }
      if (value <= 4) {
        set_bar_level(static_cast<uint8_t>(value));
      } else {
        set_bar_percent(static_cast<uint8_t>(value));
      }
    }
  } else {
    uppercase_ascii(fields[4]);
    if (strcmp(fields[3], "LEVEL") == 0) {
      int level = 0;
      if (!parse_int_range(fields[4], 0, 4, &level)) {
        print_error(request_id, "BAD_LEVEL", "expected_0_4");
        return;
      }
      set_bar_level(static_cast<uint8_t>(level));
    } else if (strcmp(fields[3], "PERCENT") == 0) {
      int percent = 0;
      if (!parse_int_range(fields[4], 0, 100, &percent)) {
        print_error(request_id, "BAD_PERCENT", "expected_0_100");
        return;
      }
      set_bar_percent(static_cast<uint8_t>(percent));
    } else {
      print_error(request_id, "BAD_BAR_MODE", "expected_LEVEL_PERCENT");
      return;
    }
  }

  begin_result(request_id, "OK");
  print_kv_u32("level", bar_level);
  print_kv_u32("percent", bar_percent);
  print_kv("pins", "13,4,16,17");
  print_kv("mode", bar_active_low ? "active_low" : "active_high");
  end_result();
}

static void handle_relay(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_on_off_toggle");
    return;
  }

  uppercase_ascii(fields[3]);
  if (strcmp(fields[3], "ON") == 0) {
    set_relay(true);
  } else if (strcmp(fields[3], "OFF") == 0) {
    set_relay(false);
  } else if (strcmp(fields[3], "TOGGLE") == 0) {
    set_relay(!relay_state);
  } else {
    print_error(request_id, "BAD_RELAY_MODE", "expected_on_off_toggle");
    return;
  }

  begin_result(request_id, "OK");
  print_kv("relay", relay_state ? "on" : "off");
  print_kv_u32("pin", PIN_RELAY_SIGNAL);
  end_result();
}

static void handle_servo(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_angle_or_detach");
    return;
  }

  uppercase_ascii(fields[3]);
  if (strcmp(fields[3], "DETACH") == 0 || strcmp(fields[3], "OFF") == 0) {
    set_servo_angle(-1);
  } else {
    int angle = 0;
    if (!parse_int_range(fields[3], 0, 180, &angle)) {
      print_error(request_id, "BAD_ANGLE", "expected_0_180");
      return;
    }
    set_servo_angle(angle);
  }

  begin_result(request_id, "OK");
  print_kv_i32("angle", servo_angle);
  print_kv_u32("pin", PIN_SERVO_SIGNAL);
  end_result();
}

static void handle_analog(const char *request_id, size_t field_count, char *fields[]) {
  begin_result(request_id, "OK");
  if (field_count == 3) {
    print_kv_u32("pot", analogRead(PIN_POT));
    print_kv_u32("sound", analogRead(PIN_SOUND));
  } else {
    uppercase_ascii(fields[3]);
    if (strcmp(fields[3], "POT") == 0) {
      print_kv_u32("pot", analogRead(PIN_POT));
    } else if (strcmp(fields[3], "SOUND") == 0) {
      print_kv_u32("sound", analogRead(PIN_SOUND));
    } else {
      print_kv("valid", "POT,SOUND");
    }
  }
  end_result();
}

static void handle_digital(const char *request_id, size_t field_count, char *fields[]) {
  begin_result(request_id, "OK");
  if (field_count == 3) {
    print_kv_bool("button", digitalRead(PIN_BUTTON) == LOW);
    print_kv_bool("ir", digitalRead(PIN_IR) == HIGH);
    print_kv_bool("accel_int1", digitalRead(PIN_ACCEL_INT1) == HIGH);
    print_kv_bool("accel_int2", digitalRead(PIN_ACCEL_INT2) == HIGH);
  } else {
    uppercase_ascii(fields[3]);
    if (strcmp(fields[3], "BUTTON") == 0) {
      print_kv_bool("button", digitalRead(PIN_BUTTON) == LOW);
    } else if (strcmp(fields[3], "IR") == 0) {
      print_kv_bool("ir", digitalRead(PIN_IR) == HIGH);
    } else {
      print_kv("valid", "BUTTON,IR");
    }
  }
  end_result();
}

static void handle_sensor_read(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_TEMP_HUM_ACCEL_APDS");
    return;
  }

  uppercase_ascii(fields[3]);
  if (strcmp(fields[3], "TEMP_HUM") == 0) {
    float temp = 0.0f;
    float hum = 0.0f;
    if (!htu21d_read_temperature_c(&temp) || !htu21d_read_humidity(&hum)) {
      print_error(request_id, "SENSOR_UNAVAILABLE", "htu21d");
      return;
    }
    begin_result(request_id, "OK");
    print_kv_i32("temp_c_x100", static_cast<int32_t>(temp * 100.0f));
    print_kv_i32("hum_x100", static_cast<int32_t>(hum * 100.0f));
    end_result();
  } else if (strcmp(fields[3], "ACCEL") == 0) {
    int16_t x = 0, y = 0, z = 0;
    if (!mma8452_read_xyz_mg(&x, &y, &z)) {
      print_error(request_id, "SENSOR_UNAVAILABLE", "mma8452");
      return;
    }
    begin_result(request_id, "OK");
    print_kv_i32("x_mg", x);
    print_kv_i32("y_mg", y);
    print_kv_i32("z_mg", z);
    end_result();
  } else if (strcmp(fields[3], "APDS") == 0) {
    uint8_t id = 0;
    uint16_t clear_light = 0;
    uint8_t prox = 0;
    if (!apds9960_id(&id)) {
      print_error(request_id, "SENSOR_UNAVAILABLE", "apds9960");
      return;
    }
    apds9960_read_clear_light(&clear_light);
    apds9960_read_proximity(&prox);
    begin_result(request_id, "OK");
    print_kv_u32("id", id);
    print_kv_u32("clear", clear_light);
    print_kv_u32("prox", prox);
    end_result();
  } else {
    print_error(request_id, "BAD_SENSOR", "expected_TEMP_HUM_ACCEL_APDS");
  }
}

static void handle_oled(const char *request_id, size_t field_count, char *fields[]) {
  refresh_peripheral_presence();
  if (!oled_present) {
    print_error(request_id, "OLED_UNAVAILABLE", "not_detected");
    return;
  }
  if (field_count != 4) {
    print_error(request_id, "BAD_ARGS", "expected_CLEAR_TEST_INIT");
    return;
  }

  uppercase_ascii(fields[3]);
  bool ok = false;
  if (strcmp(fields[3], "INIT") == 0) {
    ok = oled_init();
  } else if (strcmp(fields[3], "CLEAR") == 0) {
    ok = oled_clear();
  } else if (strcmp(fields[3], "TEST") == 0) {
    ok = oled_test_pattern();
  } else if (strcmp(fields[3], "STANDBY") == 0) {
    ok = oled_show_standby_icon();
  } else {
    print_error(request_id, "BAD_OLED_CMD", "expected_INIT_CLEAR_TEST_STANDBY");
    return;
  }

  if (!ok) {
    print_error(request_id, "OLED_ERROR", "i2c_write_failed");
    return;
  }

  begin_result(request_id, "OK");
  print_kv("oled", fields[3]);
  print_kv_u32("addr", oled_addr);
  end_result();
}

static void reset_stats(const char *request_id) {
  command_count = 0;
  error_count = 0;
  telemetry_seq = 0;
  begin_result(request_id, "OK");
  print_kv_u32("commands", 0);
  print_kv_u32("errors", 0);
  print_kv_u32("telemetry_seq", 0);
  end_result();
}

static void send_help_detail(const char *request_id, const char *command) {
  begin_result(request_id, "OK");
  if (strcmp(command, "HELLO") == 0) {
    print_kv("usage", "HELLO");
    print_kv("does", "identifica placa e protocolo");
  } else if (strcmp(command, "PING") == 0) {
    print_kv("usage", "PING");
    print_kv("does", "testa ida e volta UART");
  } else if (strcmp(command, "STATUS") == 0) {
    print_kv("usage", "STATUS");
    print_kv("does", "cpu heap flash perfil radio");
  } else if (strcmp(command, "TELEMETRY") == 0) {
    print_kv("usage", "TELEMETRY");
    print_kv("does", "uptime heap pot som botao rele");
  } else if (strcmp(command, "FAULT") == 0) {
    print_kv("usage", "FAULT NONE|CRC32 payload_hex index mask");
    print_kv("does", "aplica bit-flip e compara CRC32");
  } else if (strcmp(command, "PQC_INFO") == 0) {
    print_kv("usage", "PQC_INFO");
    print_kv("does", "reporta backend ML-KEM e tamanhos");
  } else if (strcmp(command, "PQC_KAT") == 0) {
    print_kv("usage", "PQC_KAT");
    print_kv("does", "executa vetor conhecido deterministico");
  } else if (strcmp(command, "PQC_KEYGEN") == 0) {
    print_kv("usage", "PQC_KEYGEN");
    print_kv("does", "gera par ML-KEM-512 e mede tempo");
  } else if (strcmp(command, "PQC_ENCAP") == 0) {
    print_kv("usage", "PQC_ENCAP");
    print_kv("does", "encapsula usando pk armazenada");
  } else if (strcmp(command, "PQC_DECAP") == 0) {
    print_kv("usage", "PQC_DECAP");
    print_kv("does", "decapsula ct armazenado e compara");
  } else if (strcmp(command, "PQC_FAULT") == 0) {
    print_kv("usage", "PQC_FAULT index mask CONFIRM|NONE");
    print_kv("does", "bit-flip em ciphertext e confirmacao");
  } else if (strcmp(command, "PQC_BENCH") == 0) {
    print_kv("usage", "PQC_BENCH n");
    print_kv("does", "benchmark keygen encap decap");
  } else if (strcmp(command, "KEX_INFO") == 0) {
    print_kv("usage", "KEX_INFO");
    print_kv("does", "reporta configuração portátil ECDH/MLKEM FAIR_V1");
  } else if (strcmp(command, "KEX_BENCH") == 0) {
    print_kv("usage", "KEX_BENCH n");
    print_kv("does", "benchmark pareado ECDH P-256 e ML-KEM-512");
  } else if (strcmp(command, "SESSION_BENCH") == 0) {
    print_kv("usage", "SESSION_BENCH ECDH|MLKEM 1|100|500|1000 payload_hex");
    print_kv("does", "mede uma sessao e amortiza AES-GCM em varias mensagens");
  } else if (strcmp(command, "STRESS") == 0) {
    print_kv("usage", "STRESS PQC_LOOP n CONFIRM");
    print_kv("does", "executa ML-KEM em loop extremo");
  } else if (strcmp(command, "MISSION") == 0) {
    print_kv("usage", "MISSION CLASSIC|PQC|ECDH|MLKEM [_CRC32] [payload_hex]");
    print_kv("does", "cifra com AES-GCM e mede custo por cenario");
  } else if (strcmp(command, "INVESTIGATE") == 0) {
    print_kv("usage", "INVESTIGATE scenario incident payload_hex index mask incident_id");
    print_kv("does", "instrumenta CRC de quadro GCM e CRC de aplicacao");
  } else if (strcmp(command, "GAME_BEGIN") == 0) {
    print_kv("usage", "GAME_BEGIN id profile CLASSIC|PQC|ECDH|MLKEM NONE|CRC32 incident payload_hex");
    print_kv("does", "inicia sessao STAGED_V1 e prepara payload");
  } else if (strcmp(command, "GAME_PROTECT") == 0) {
    print_kv("usage", "GAME_PROTECT id");
    print_kv("does", "estabelece chave e cria envelope AES-GCM");
  } else if (strcmp(command, "GAME_TRANSMIT") == 0) {
    print_kv("usage", "GAME_TRANSMIT id byte_index bit_mask");
    print_kv("does", "aplica incidente oculto e mede CRC de quadro");
  } else if (strcmp(command, "GAME_VERIFY") == 0) {
    print_kv("usage", "GAME_VERIFY id");
    print_kv("does", "verifica quadro GCM e CRC de aplicacao");
  } else if (strcmp(command, "GAME_RETRY") == 0) {
    print_kv("usage", "GAME_RETRY id");
    print_kv("does", "retransmite mesmo payload com chave e nonce novos");
  } else if (strcmp(command, "GAME_END") == 0) {
    print_kv("usage", "GAME_END id ACCEPT|SAFE_MODE");
    print_kv("does", "encerra limpa segredos e restaura baseline");
  } else if (strcmp(command, "GAME_ABORT") == 0) {
    print_kv("usage", "GAME_ABORT id");
    print_kv("does", "aborta limpa sessao e restaura baseline");
  } else if (strcmp(command, "PERIPHERALS") == 0) {
    print_kv("usage", "PERIPHERALS");
    print_kv("does", "detecta OLED APDS HTU MMA");
  } else if (strcmp(command, "I2C_SCAN") == 0) {
    print_kv("usage", "I2C_SCAN");
    print_kv("does", "varre I2C SDA21 SCL22");
  } else if (strcmp(command, "FEATURES") == 0) {
    print_kv("usage", "FEATURES CORE I2C GPIO ANALOG EXPANSION");
    print_kv("does", "lista recursos por grupo");
  } else if (strcmp(command, "BOARDMAP") == 0) {
    print_kv("usage", "BOARDMAP I2C GPIO ANALOG EXPANSION");
    print_kv("does", "mostra pinos e enderecos");
  } else if (strcmp(command, "SENSOR_READ") == 0) {
    print_kv("usage", "SENSOR_READ TEMP_HUM ACCEL APDS");
    print_kv("does", "le sensores I2C");
  } else if (strcmp(command, "ANALOG") == 0) {
    print_kv("usage", "ANALOG POT SOUND");
    print_kv("does", "le entradas analogicas");
  } else if (strcmp(command, "DIGITAL") == 0) {
    print_kv("usage", "DIGITAL BUTTON IR");
    print_kv("does", "le entradas digitais");
  } else if (strcmp(command, "RGB") == 0) {
    print_kv("usage", "RGB R G B OFF TEST COMMON_ANODE COMMON_CATHODE");
    print_kv("does", "controla LED RGB onboard");
  } else if (strcmp(command, "BARGRAPH") == 0) {
    print_kv("usage", "BARGRAPH 0..4 0..100 LEVEL n PERCENT n TEST");
    print_kv("does", "controla LEDs de porcentagem");
  } else if (strcmp(command, "LED") == 0) {
    print_kv("usage", "LED ON OFF TOGGLE TEST WHITE RED GREEN BLUE CYAN MAGENTA YELLOW");
    print_kv("does", "controla indicador principal e RGB");
  } else if (strcmp(command, "RELAY") == 0) {
    print_kv("usage", "RELAY ON OFF TOGGLE");
    print_kv("does", "controla saida D33");
  } else if (strcmp(command, "SERVO") == 0) {
    print_kv("usage", "SERVO 0..180 DETACH");
    print_kv("does", "gera PWM no D25");
  } else if (strcmp(command, "OLED") == 0) {
    print_kv("usage", "OLED INIT CLEAR TEST STANDBY");
    print_kv("does", "controla display e icone standby");
  } else if (strcmp(command, "PROFILE") == 0) {
    print_kv("usage", "PROFILE BASELINE OBC-1U-LIMITED");
    print_kv("does", "altera perfil de CPU");
  } else if (strcmp(command, "RESET_STATS") == 0) {
    print_kv("usage", "RESET_STATS");
    print_kv("does", "zera contadores");
  } else if (strcmp(command, "HELP") == 0) {
    print_kv("usage", "HELP [COMMAND]");
    print_kv("does", "lista comandos ou detalhe");
  } else {
    print_kv("usage", "HELP [COMMAND]");
    print_kv("valid", "HELP sem argumento lista grupos");
  }
  end_result();
}

static void send_help(const char *request_id, size_t field_count, char *fields[]) {
  if (field_count >= 4) {
    uppercase_ascii(fields[3]);
    send_help_detail(request_id, fields[3]);
    return;
  }

  begin_result(request_id, "OK");
  print_kv("usage", "HELP [COMMAND]");
  print_kv("cmd1", "HELLO,PING,STATUS,TELEMETRY,FAULT,PERIPHERALS");
  print_kv("cmd2", "PQC_INFO,PQC_KAT,PQC_KEYGEN,PQC_ENCAP,PQC_DECAP,PQC_FAULT,PQC_BENCH,KEX_INFO");
  print_kv("cmd3", "KEX_BENCH,SESSION_BENCH,MISSION,INVESTIGATE,GAME_BEGIN,GAME_PROTECT,GAME_TRANSMIT");
  print_kv("cmd4", "GAME_VERIFY,GAME_RETRY,GAME_END,GAME_ABORT,I2C_SCAN,FEATURES,BOARDMAP");
  print_kv("cmd5", "SENSOR_READ,ANALOG,DIGITAL,RGB,BARGRAPH,LED,RELAY,SERVO,OLED,PROFILE,RESET_STATS,HELP");
  end_result();
}

static void process_frame(char *line) {
  char *fields[MAX_FIELDS] = {0};
  const size_t field_count = split_fields(line, fields, MAX_FIELDS);

  if (field_count < 3) {
    print_error("0", "BAD_FRAME", "expected_v1_request_command");
    return;
  }

  if (strcmp(fields[0], "V1") != 0) {
    print_error(fields[1], "BAD_VERSION", "expected_v1");
    return;
  }

  const char *request_id = fields[1];
  char *command = fields[2];
  uppercase_ascii(command);
  command_count++;

  // A GAME_* session has exclusive ownership of the profile, LEDs and the
  // global key-establishment work buffers. HELLO is the reconnect/reset primitive and a
  // new GAME_BEGIN intentionally replaces the previous session. ANALOG POT is
  // the sole read-only exception because it captures A39 for GAME_TRANSMIT.
  if (staged_game.active && strcmp(command, "HELLO") != 0 &&
      !is_staged_game_control_command(command) &&
      !is_staged_game_safe_read_command(command, field_count, fields)) {
    staged_game_error(
        request_id,
        "BAD_GAME_STATE",
        "active_GAME_session_requires_GAME_command_HELLO_or_ANALOG_POT");
    return;
  }

  if (strcmp(command, "HELLO") == 0) {
    send_hello(request_id);
  } else if (strcmp(command, "PING") == 0) {
    send_ping(request_id);
  } else if (strcmp(command, "STATUS") == 0) {
    send_status(request_id);
  } else if (strcmp(command, "TELEMETRY") == 0) {
    send_telemetry(request_id);
  } else if (strcmp(command, "FAULT") == 0) {
    handle_fault(request_id, field_count, fields);
  } else if (strcmp(command, "PQC_INFO") == 0) {
    send_pqc_info(request_id);
  } else if (strcmp(command, "PQC_KAT") == 0) {
    send_pqc_kat(request_id);
  } else if (strcmp(command, "PQC_KEYGEN") == 0) {
    send_pqc_keygen(request_id);
  } else if (strcmp(command, "PQC_ENCAP") == 0) {
    send_pqc_encap(request_id);
  } else if (strcmp(command, "PQC_DECAP") == 0) {
    send_pqc_decap(request_id);
  } else if (strcmp(command, "PQC_FAULT") == 0) {
    handle_pqc_fault(request_id, field_count, fields);
  } else if (strcmp(command, "PQC_BENCH") == 0) {
    handle_pqc_bench(request_id, field_count, fields);
  } else if (strcmp(command, "KEX_INFO") == 0) {
    send_kex_info(request_id);
  } else if (strcmp(command, "KEX_BENCH") == 0) {
    handle_kex_bench(request_id, field_count, fields);
  } else if (strcmp(command, "SESSION_BENCH") == 0) {
    handle_session_bench(request_id, field_count, fields);
  } else if (strcmp(command, "STRESS") == 0) {
    handle_stress(request_id, field_count, fields);
  } else if (strcmp(command, "MISSION") == 0) {
    handle_mission(request_id, field_count, fields);
  } else if (strcmp(command, "INVESTIGATE") == 0) {
    handle_investigate(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_BEGIN") == 0) {
    handle_game_begin(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_PROTECT") == 0) {
    handle_game_protect(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_TRANSMIT") == 0) {
    handle_game_transmit(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_VERIFY") == 0) {
    handle_game_verify(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_RETRY") == 0) {
    handle_game_retry(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_END") == 0) {
    handle_game_end(request_id, field_count, fields);
  } else if (strcmp(command, "GAME_ABORT") == 0) {
    handle_game_abort(request_id, field_count, fields);
  } else if (strcmp(command, "PERIPHERALS") == 0) {
    send_peripherals(request_id);
  } else if (strcmp(command, "I2C_SCAN") == 0) {
    handle_i2c_scan(request_id);
  } else if (strcmp(command, "FEATURES") == 0) {
    handle_features(request_id, field_count, fields);
  } else if (strcmp(command, "BOARDMAP") == 0) {
    handle_boardmap(request_id, field_count, fields);
  } else if (strcmp(command, "PROFILE") == 0) {
    handle_profile(request_id, field_count, fields);
  } else if (strcmp(command, "LED") == 0) {
    handle_led(request_id, field_count, fields);
  } else if (strcmp(command, "RGB") == 0) {
    handle_rgb(request_id, field_count, fields);
  } else if (strcmp(command, "BARGRAPH") == 0) {
    handle_bargraph(request_id, field_count, fields);
  } else if (strcmp(command, "RELAY") == 0) {
    handle_relay(request_id, field_count, fields);
  } else if (strcmp(command, "SERVO") == 0) {
    handle_servo(request_id, field_count, fields);
  } else if (strcmp(command, "ANALOG") == 0) {
    handle_analog(request_id, field_count, fields);
  } else if (strcmp(command, "DIGITAL") == 0) {
    handle_digital(request_id, field_count, fields);
  } else if (strcmp(command, "SENSOR_READ") == 0) {
    handle_sensor_read(request_id, field_count, fields);
  } else if (strcmp(command, "OLED") == 0) {
    handle_oled(request_id, field_count, fields);
  } else if (strcmp(command, "RESET_STATS") == 0) {
    reset_stats(request_id);
  } else if (strcmp(command, "HELP") == 0) {
    send_help(request_id, field_count, fields);
  } else {
    print_error(request_id, "UNKNOWN_COMMAND", command);
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);

  boot_cpu_mhz = ESP.getCpuFreqMHz();
  disable_radios();
  configure_board_io();
  initialize_button_event_state();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(100000);
  refresh_peripheral_presence();
  mma8452_init();
  oled_init();

  print_boot_event();
}

void loop() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      rx_buffer[rx_len] = '\0';
      if (rx_len > 0) {
        process_frame(rx_buffer);
      }
      rx_len = 0;
      continue;
    }

    if (rx_len >= MAX_FRAME_LEN) {
      rx_len = 0;
      error_count++;
      Serial.print("V1|0|EVENT|RX_OVERFLOW|limit=");
      Serial.println(MAX_FRAME_LEN);
      continue;
    }

    rx_buffer[rx_len++] = c;
  }
  poll_button_ping_event();
}
