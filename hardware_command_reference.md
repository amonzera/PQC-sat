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

## Comandos PQC planejados

Estes comandos ainda **não** devem aparecer no `HELP` do dashboard. Eles
entram no firmware apenas depois de o backend ML-KEM-512/Kyber512 compilar,
passar vetor conhecido e reportar métricas na Wisdom.

| Comando | Uso previsto | Observação |
|---|---|---|
| `PQC_INFO` | `PQC_INFO` | Variante, parâmetros, fonte, commit, licença, tamanhos e backend. |
| `PQC_KAT` | `PQC_KAT` | Executa vetor conhecido e retorna status, tempo e métricas. |
| `PQC_KEYGEN` | `PQC_KEYGEN` | Mede geração de chaves sem imprimir chave completa. |
| `PQC_ENCAP` | `PQC_ENCAP` | Encapsula para chave pública de teste e retorna digest curto. |
| `PQC_DECAP` | `PQC_DECAP` | Decapsula ciphertext de teste e retorna digest curto. |
| `PQC_BENCH` | `PQC_BENCH n` | Executa `n` iterações e retorna tempo, heap, heap mínimo e resets. |

## Comandos completos de bancada

| Comando | Uso | Possibilidade de comunicacao |
|---|---|---|
| `HELLO` | `HELLO` | Handshake; identifica `PQC-SAT-WISDOM`, placa, protocolo e transporte. |
| `PING` | `PING` | Teste de ida e volta UART com `uptime_ms`. |
| `STATUS` | `STATUS` | Estado do ESP32: perfil, chip, CPU, heap, flash e radio. |
| `TELEMETRY` | `TELEMETRY` | Snapshot de uptime, CPU, heap, potenciometro, som, botao e rele. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Aplica bit-flip em payload hexadecimal e retorna `result`, byte antes/depois, CRC32 antes/depois e `elapsed_us`. |
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
