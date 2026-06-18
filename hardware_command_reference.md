# Referencia de comandos de hardware

Este arquivo concentra as possibilidades completas de comunicacao com a
BlackBoard Wisdom pelo protocolo serial `V1`.

Durante a demonstracao ao vivo, o dashboard deve expor apenas comandos ligados
ao enredo visual do projeto. Comandos de inventario, bancada, debug e expansao
ficam documentados aqui para desenvolvimento, testes e manutencao.

## Protocolo

```text
V1|request_id|COMMAND|arg1|arg2
V1|request_id|RESULT|status|key=value
```

Exemplo:

```text
V1|1|TELEMETRY
V1|1|RESULT|OK|seq=1|uptime_ms=12345|heap=233556
```

Para listar estes comandos no terminal:

```bash
python3 tools/serial_console.py --all-commands
```

Para listar apenas os comandos da demonstracao:

```bash
python3 tools/serial_console.py --commands
```

## Comandos usados na demonstracao

| Comando | Uso | Papel na demonstracao |
|---|---|---|
| `PING` | `PING` | Confirma que a placa esta respondendo. |
| `STATUS` | `STATUS` | Mostra perfil, CPU, heap, flash e radio. |
| `TELEMETRY` | `TELEMETRY` | Atualiza telemetria real da Wisdom no painel. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Comando serial tecnico usado para validar bit-flip e CRC32 na placa. No dashboard, use `INJECT_FAULT` e `CRC_CHECK`. |
| `SENSOR_READ` | `SENSOR_READ TEMP_HUM` | Mostra temperatura e umidade. |
| `SENSOR_READ` | `SENSOR_READ ACCEL` | Mostra movimento/orientacao pelo acelerometro. |
| `SENSOR_READ` | `SENSOR_READ APDS` | Mostra luz/proximidade pelo APDS-9960. |
| `OLED` | `OLED STANDBY` | Restaura o icone robo-satelite no display. |
| `LED` | `LED TEST`, `LED WHITE`, `LED RED`, `LED GREEN`, `LED BLUE`, `LED OFF` | Controla o indicador principal. |
| `RGB` | `RGB TEST`, `RGB R G B`, `RGB OFF` | Controla o LED RGB para efeitos visuais. |
| `BARGRAPH` | `BARGRAPH TEST`, `BARGRAPH 0`, `BARGRAPH 25`, `BARGRAPH 50`, `BARGRAPH 75`, `BARGRAPH 100` | Mostra progresso nos LEDs de porcentagem. |

## Comandos PQC de bancada

Estes comandos ainda **não** devem aparecer no `HELP` do dashboard. Eles
existem no firmware como superfície técnica para medir ML-KEM-512 na Wisdom.
O backend usado é `mlkem-native` v1.1.0, commit `d2cae2b`, licença
`Apache-2.0 OR ISC OR MIT`, em build C-only para `MLK_CONFIG_PARAMETER_SET=512`.

| Comando | Uso | Estado atual |
|---|---|---|
| `PQC_INFO` | `PQC_INFO` | Reporta backend, variante, commit, licença, tamanhos `pk=800`, `sk=1632`, `ct=768`, `ss=32`, CPU, heap, flash, perfil e tempo. |
| `PQC_KAT` | `PQC_KAT` | Executa vetor determinístico do projeto; validado em placa com `kat=pass` e `ss_crc32=0xD9DA8D6C`. |
| `PQC_KEYGEN` | `PQC_KEYGEN` | Gera par ML-KEM-512, armazena na RAM e retorna tempo/heap/digest curto da chave pública. |
| `PQC_ENCAP` | `PQC_ENCAP` | Encapsula usando chave pública armazenada e retorna tempo, digest curto do ciphertext e digest curto do segredo. |
| `PQC_DECAP` | `PQC_DECAP` | Decapsula ciphertext armazenado e retorna `key_match` sem imprimir segredo completo. |
| `PQC_BENCH` | `PQC_BENCH n` | Executa `n` rodadas keygen/encap/decap; `n` aceito de 1 a 20. |

Medição registrada em 2026-06-17:

| Perfil | Comando | Resultado |
|---|---|---|
| `BASELINE` 240 MHz | `PQC_BENCH 5` | `keygen_avg_us=3369`, `encap_avg_us=3878`, `decap_avg_us=5013`, `elapsed_us=62068`, `heap=202444`, `min_heap=198456` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24697`, `heap=202444`, `min_heap=198456`, `flash=4194304` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=39270` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_BENCH 5` | `keygen_avg_us=10101`, `encap_avg_us=11778`, `decap_avg_us=15214`, `elapsed_us=187371`, `heap=202444`, `min_heap=198456` |

## Comandos completos de bancada

| Comando | Uso | Possibilidade de comunicacao |
|---|---|---|
| `HELLO` | `HELLO` | Handshake; identifica `PQC-SAT-WISDOM`, placa, protocolo e transporte. |
| `PING` | `PING` | Teste de ida e volta UART com `uptime_ms`. |
| `STATUS` | `STATUS` | Estado do ESP32: perfil, chip, CPU, heap, flash e radio. |
| `TELEMETRY` | `TELEMETRY` | Snapshot de uptime, CPU, heap, potenciometro, som, botao e rele. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Aplica bit-flip em payload hexadecimal e retorna `result`, byte antes/depois, CRC32 antes/depois e `elapsed_us`. |
| `PQC_INFO` | `PQC_INFO` | Reporta contrato PQC atual, backend real e métricas. |
| `PQC_KAT` | `PQC_KAT` | Executa vetor conhecido determinístico e retorna digests curtos. |
| `PQC_KEYGEN` | `PQC_KEYGEN` | Gera par ML-KEM-512 real e mede tempo/heap. |
| `PQC_ENCAP` | `PQC_ENCAP` | Encapsula para a chave pública armazenada. |
| `PQC_DECAP` | `PQC_DECAP` | Decapsula ciphertext armazenado e compara segredo compartilhado. |
| `PQC_BENCH` | `PQC_BENCH n` | Executa benchmark de bancada para `n` rodadas. |
| `PERIPHERALS` | `PERIPHERALS` | Detecta OLED, APDS-9960, HTU21D e MMA8452 no I2C. |
| `I2C_SCAN` | `I2C_SCAN` | Varre o barramento I2C em SDA21/SCL22. |
| `FEATURES` | `FEATURES`, `FEATURES CORE`, `FEATURES I2C`, `FEATURES GPIO`, `FEATURES ANALOG`, `FEATURES EXPANSION` | Lista grupos de recursos conhecidos pela firmware. |
| `BOARDMAP` | `BOARDMAP`, `BOARDMAP I2C`, `BOARDMAP GPIO`, `BOARDMAP ANALOG`, `BOARDMAP EXPANSION` | Reporta pinos, barramentos e enderecos usados. |
| `SENSOR_READ` | `SENSOR_READ TEMP_HUM`, `SENSOR_READ ACCEL`, `SENSOR_READ APDS` | Le sensores I2C embarcados. |
| `ANALOG` | `ANALOG`, `ANALOG POT`, `ANALOG SOUND` | Le potenciometro A39 e sensor de som A36. |
| `DIGITAL` | `DIGITAL`, `DIGITAL BUTTON`, `DIGITAL IR` | Le botao, receptor IR e interrupcoes do acelerometro. |
| `RGB` | `RGB R G B`, `RGB OFF`, `RGB TEST`, `RGB COMMON_ANODE`, `RGB COMMON_CATHODE` | Controla LED RGB e polaridade. |
| `BARGRAPH` | `BARGRAPH 0..4`, `BARGRAPH 0..100`, `BARGRAPH LEVEL n`, `BARGRAPH PERCENT n`, `BARGRAPH TEST`, `BARGRAPH ACTIVE_HIGH`, `BARGRAPH ACTIVE_LOW` | Controla LEDs de porcentagem e polaridade. |
| `LED` | `LED ON`, `LED OFF`, `LED TOGGLE`, `LED TEST`, `LED WHITE`, `LED RED`, `LED GREEN`, `LED BLUE`, `LED CYAN`, `LED MAGENTA`, `LED YELLOW` | Controla indicador principal via LED interno mais RGB onboard. |
| `RELAY` | `RELAY ON`, `RELAY OFF`, `RELAY TOGGLE` | Controla saida de rele em D33. |
| `SERVO` | `SERVO 0..180`, `SERVO DETACH`, `SERVO OFF` | Gera PWM para servo em D25 ou solta o canal. |
| `OLED` | `OLED INIT`, `OLED CLEAR`, `OLED TEST`, `OLED STANDBY` | Controla display OLED e icone standby. |
| `PROFILE` | `PROFILE BASELINE`, `PROFILE OBC-1U-LIMITED` | Alterna perfil operacional do ESP32. |
| `RESET_STATS` | `RESET_STATS` | Zera contadores internos da firmware. |
| `HELP` | `HELP`, `HELP LED`, `HELP BARGRAPH`, `HELP RGB`, `HELP OLED` | Lista grupos ou explica um comando especifico. |

## Politica de uso

- Dashboard da apresentacao: somente comandos da secao "Comandos usados na
  demonstracao".
- Bancada, debug e desenvolvimento: qualquer comando desta referencia pode ser
  enviado por `tools/serial_console.py`.
- Comandos que acionam expansoes fisicas, como `RELAY` e `SERVO`, nao devem
  aparecer no console da apresentacao sem necessidade explicita.
