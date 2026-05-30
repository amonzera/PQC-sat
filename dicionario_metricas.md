# Dicionário de métricas

Este arquivo define os campos mínimos dos logs e do CSV.

## 1. Identificação

| Campo | Tipo | Origem | Obrigatório |
|---|---|---|---|
| `run_id` | string | host | sim |
| `iteration` | inteiro | host/ESP32 | sim |
| `timestamp_host` | string | host | sim |
| `board_id` | string | ESP32 | sim |
| `firmware_version` | string | ESP32 | recomendado |
| `host_script_version` | string | host | recomendado |

## 2. Configuração

| Campo | Tipo | Valores |
|---|---|---|
| `profile` | string | `obc_80mhz_basic` |
| `campaign` | string | `functional`, `classic_baseline`, `pqc_baseline`, `pqc_fault`, `pqc_fault_confirm` |
| `algorithm` | string | `none`, `ecdh_p256`, `ml_kem_512` |
| `fault_enabled` | booleano | `true`, `false` |
| `fault_bits` | inteiro | `0`, `1` |
| `key_confirmation_enabled` | booleano | `true`, `false` |

## 3. Tempos

| Campo | Unidade | Uso |
|---|---:|---|
| `classic_keygen_us` | microssegundos | geração ECDH no ESP32 |
| `classic_derive_us` | microssegundos | derivação ECDH no ESP32 |
| `pqc_keygen_us` | microssegundos | geração ML-KEM no ESP32 |
| `pqc_decap_us` | microssegundos | decap ML-KEM no ESP32 |
| `pqc_encap_host_us` | microssegundos | encapsulamento ML-KEM no notebook |
| `key_confirm_us` | microssegundos | HMAC/confirmacao no ESP32 |
| `total_iteration_us` | microssegundos | tempo total opcional |

Campos não aplicáveis devem usar `null` ou `0`, mas não devem desaparecer do CSV.

## 4. Comunicação

| Campo | Unidade | Uso |
|---|---:|---|
| `classic_public_key_bytes` | bytes | chave pública do ESP32 |
| `classic_peer_public_key_bytes` | bytes | chave pública do notebook |
| `classic_total_bytes` | bytes | soma do tráfego clássico relevante |
| `pqc_public_key_bytes` | bytes | chave pública ML-KEM |
| `pqc_ciphertext_bytes` | bytes | ciphertext ML-KEM |
| `pqc_total_bytes` | bytes | soma do tráfego PQC relevante |

## 5. Memória

| Campo | Unidade |
|---|---:|
| `free_heap_before` | bytes |
| `free_heap_after` | bytes |
| `heap_delta` | bytes |
| `reset_counter` | inteiro |

## 6. Falha e confirmação

| Campo | Tipo | Uso |
|---|---|---|
| `fault_positions` | lista | byte/bit alterado |
| `ciphertext_changed` | booleano | indica alteração efetiva |
| `decap_status` | string | `not_run`, `ok`, `error`, `timeout`, `reset` |
| `shared_secret_digest_device` | string/null | digest do segredo do ESP32 |
| `shared_secret_digest_host` | string/null | digest do segredo do host |
| `secret_match` | booleano/null | comparação dos digests |
| `key_confirmed` | booleano/null | resultado da confirmação |
| `fault_class` | string | classe final |
| `error_code` | string/null | erro estruturado |

## 7. Métricas derivadas

| Métrica | Fórmula |
|---|---|
| `classic_device_time_us` | `classic_keygen_us + classic_derive_us` |
| `pqc_device_time_us` | `pqc_keygen_us + pqc_decap_us` |
| `time_ratio_pqc_classic` | `median(pqc_device_time_us_C2) / median(classic_device_time_us_C1)` |
| `bytes_ratio_pqc_classic` | `pqc_total_bytes / classic_total_bytes` |
| `key_divergence_rate` | `key_divergence_C3 / ciphertext_changed_C3` |
| `explicit_failure_rate` | `explicit_failure_C3 / ciphertext_changed_C3` |
| `confirmation_detection_rate` | `confirmation_failed_C4 / divergencias_reais_C4`, onde divergencia real vem de `secret_match=false` por digest |
| `confirmation_overhead_ratio` | `median(key_confirm_us_C4) / median(pqc_decap_us_C2)` |

## 8. Gráficos obrigatórios

1. Tempo no ESP32: clássico vs PQC.
2. Bytes trafegados: clássico vs PQC.
3. Classes de falha em C3.
4. Confirmação de chave em C4.
5. Overhead da confirmação.

## 9. Tabelas obrigatórias

1. Estatísticas de tempo por campanha.
2. Tamanho de mensagens por algoritmo.
3. Contagem por `fault_class`.
4. Razões PQC/clássico.
5. Decisão da hipótese.
