# Referência de comandos de hardware

Este arquivo concentra as possibilidades completas de comunicação com a
BlackBoard Wisdom pelo protocolo serial `V1`.

Durante a demonstração ao vivo, os blocos clicáveis do dashboard devem expor
apenas comandos ligados ao enredo visual do projeto. Comandos de inventário,
bancada, debug e expansão ficam documentados aqui para desenvolvimento, testes
e manutenção; eles podem ser enviados pelo terminal textual avançado do painel
ou pelo console `tools/serial_console.py`.

Comandos locais do dashboard, como `DEMO`, `DEMO_PAUSE`, `DEMO_RESUME`,
`DEMO_STOP`, `DEMO_RESTART`, `RUN_BATTERY`, `CHECKSUM`, `EXPORT_JSON` e
`TOGGLE_LIVE_PAYLOAD`, não são comandos do firmware. O comando `MISSION`, por
outro lado, existe no firmware e é o caminho principal da apresentação para
medir `CLASSIC`, `PQC` e `PQC_CRC32`.

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

Para listar apenas os comandos da demonstração:

```bash
python3 tools/serial_console.py --commands
```

## Comandos de apoio da demonstração

| Comando | Uso | Papel na demonstração |
|---|---|---|
| `STATUS` | `STATUS` | Mostra perfil, CPU, heap, flash e radio sob demanda. |
| `MISSION` | `MISSION CLASSIC`, `MISSION PQC`, `MISSION PQC_CRC32` | Entrega mensagem curta e mede tempo, bytes, heap e resultado nos três cenários centrais do seminário. |
| `TOGGLE_LIVE_PAYLOAD` | comando local do dashboard | Liga/desliga o modo em que sensores reais da Wisdom geram o payload antes de `MISSION`. |
| `DEMO` | `DEMO`, `DEMO_PAUSE`, `DEMO_RESUME`, `DEMO_STOP`, `DEMO_RESTART` | Comandos locais do dashboard para executar a apresentação A/B cronometrada. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Comando serial técnico usado para validar bit-flip e CRC32 na placa. No dashboard, use `INJECT_FAULT` e `CRC_CHECK`. |
| `OLED` | `OLED STANDBY` | Restaura o ícone robo-satélite no display. |

`PING`, `TELEMETRY`, sensores, LED, RGB e bargraph continuam disponíveis pelo
HELP/terminal textual e pelo `tools/serial_console.py`, mas não devem aparecer
como blocos clicáveis da apresentação para evitar ruído visual e serial.
O dashboard pode acionar LED/bargraph automaticamente depois de `MISSION` como
efeito lúdico de custo relativo; isso não transforma LED/bargraph em métrica.

## Payload vivo no dashboard

O modo `Payload vivo` é uma orquestração do dashboard, não um novo comando de
firmware. Quando ligado, antes de `ENVIAR MSG` o dashboard consulta:

```text
SENSOR_READ TEMP_HUM
SENSOR_READ ACCEL
SENSOR_READ APDS
ANALOG POT
DIGITAL BUTTON
```

Com essas respostas, ele monta um payload ASCII compacto e envia uma chamada
`MISSION` com payload hexadecimal:

```text
MISSION PQC_CRC32 5051432D5341547C533D34327C...
```

O firmware mede normalmente `bytes_payload`, `bytes_crypto`,
`bytes_checksum`, `bytes_total`, `cipher=AES-128-GCM`, `elapsed_us`, heap e
flags de validação. O
dashboard guarda também os metadados locais do payload vivo no popup e no JSON:

| Campo local | Significado |
|---|---|
| `payload_mode` | `LIVE` quando veio dos sensores; `FIXED` quando usa payload padrão. |
| `payload_text` | Payload ASCII montado antes de converter para hex. |
| `payload_seq` | Sequência do envio ao vivo. |
| `sensor_temp_c_x100`, `sensor_hum_x100` | Leituras do HTU21D em escala inteira. |
| `sensor_accel` | `x,y,z` do acelerômetro em mg. |
| `sensor_light` | Leitura de luz/proximidade do APDS-9960. |
| `sensor_pot` | Valor do potenciômetro A39. |
| `sensor_button` | Estado do botão D27. |
| `sensor_failures` | Lista de sensores que não responderam; o payload usa `NA`. |

Para falhas ao vivo, o dashboard também usa `ANALOG POT` como seletor físico
de bit-flip: o valor 0..4095 é mapeado para uma posição dentro do payload, e o
popup mostra `pot -> byte/mask -> resultado`.

O OLED continua com `OLED STANDBY`. O firmware atual não possui comando para
escrever texto arbitrário no display; por isso fases como `KEYGEN`, `CRC` e
`FAULT` aparecem no popup, enquanto LED/RGB/bargraph dão feedback físico de
processamento e custo relativo.

## Comando MISSION

`MISSION` é o comando principal para consolidar a comparação do seminário.

| Uso | Significado |
|---|---|
| `MISSION CLASSIC` | Payload cifrado/autenticado por AES-128-GCM com chave efêmera gerada na placa. |
| `MISSION PQC` | ML-KEM-512 estabelece segredo; AES-128-GCM cifra e autentica a mensagem. |
| `MISSION PQC_CRC32` | Mesmo fluxo PQC com CRC32 inserido no material protegido antes da cifragem. |
| `MISSION CLASSIC payload_hex` | Executa o cenário clássico com payload hexadecimal escolhido. |
| `MISSION PQC payload_hex` | Executa PQC com payload hexadecimal escolhido. |
| `MISSION PQC_CRC32 payload_hex` | Executa PQC+CRC32 com payload hexadecimal escolhido. |

Campos retornados:

| Campo | Interpretação |
|---|---|
| `scenario` | `CLASSIC`, `PQC` ou `PQC_CRC32`. |
| `result` | `DELIVERED` ou `REJECTED`. |
| `crypto` | `AES-128-GCM` no clássico; `ML-KEM-512` nos cenários PQC. |
| `cipher` | Cifra AEAD usada no payload: `AES-128-GCM`. |
| `checksum` | `NONE` ou `CRC32`. |
| `key_source` | `RANDOM_SESSION` no clássico; `ML-KEM-512` no PQC. |
| `key_match` | Segredos ML-KEM bateram; sempre verdadeiro no clássico. |
| `aead_match` / `tag_match` | A tag AES-GCM foi aceita e o plaintext verificado. `tag_match` fica como alias para compatibilidade. |
| `crc_match` | CRC32 bateu quando checksum está ativo. |
| `bytes_total` | Ciphertext do payload + ciphertext ML-KEM quando houver + nonce + tag GCM + CRC quando ativo. |
| `elapsed_us` | Tempo total da entrega medida na placa. |
| `keygen_us`, `encap_us`, `decap_us` | Subtempos ML-KEM; zero no cenário clássico. |
| `rng_us`, `kdf_us`, `encrypt_us`, `decrypt_us`, `crc_us` | Custo de RNG, derivação, cifragem, decifragem/verificação e checksum. |
| `heap`, `min_heap`, `cpu_mhz`, `profile` | Métricas do ESP32 no cenário. |

`PQC_FAULT ... CONFIRM` permanece apenas como comando técnico de bancada para
auditar sessões ML-KEM antigas do projeto. Ele não abre popup no dashboard e
não faz parte da demonstração visual de falha. Na apresentação, a falha correta
é `FAULT NONE|CRC32`, isto é: bit-flip em payload, sem checksum versus com
CRC32. No fluxo `MISSION`, a autenticação da mensagem vem do AES-GCM.

## Comandos PQC de bancada

Estes comandos não devem virar blocos clicáveis da apresentação. Eles existem
no firmware como superfície técnica para medir e auditar ML-KEM-512 na Wisdom,
e podem aparecer no `HELP` avançado do terminal textual. O backend usado é
`mlkem-native` v1.1.0, commit `d2cae2b`, licença `Apache-2.0 OR ISC OR MIT`,
em build C-only para `MLK_CONFIG_PARAMETER_SET=512`.

| Comando | Uso | Estado atual |
|---|---|---|
| `PQC_INFO` | `PQC_INFO` | Reporta backend, variante, commit, licença, tamanhos `pk=800`, `sk=1632`, `ct=768`, `ss=32`, CPU, heap, flash, perfil e tempo. |
| `PQC_KAT` | `PQC_KAT` | Executa vetor determinístico do projeto; validado em placa com `kat=pass` e `ss_crc32=0xD9DA8D6C`. |
| `PQC_KEYGEN` | `PQC_KEYGEN` | Gera par ML-KEM-512, armazena na RAM e retorna tempo/heap/digest curto da chave pública. |
| `PQC_ENCAP` | `PQC_ENCAP` | Encapsula usando chave pública armazenada e retorna tempo, digest curto do ciphertext e digest curto do segredo. |
| `PQC_DECAP` | `PQC_DECAP` | Decapsula ciphertext armazenado e retorna `key_match` sem imprimir segredo completo. |
| `PQC_FAULT` | `PQC_FAULT index mask [CONFIRM\|NONE]` | Comando técnico de bancada para bit-flip em ciphertext ML-KEM; não é usado nos popups da apresentação. |
| `PQC_BENCH` | `PQC_BENCH n` | Executa `n` rodadas keygen/encap/decap; `n` aceito de 1 a 100. |
| `STRESS` | `STRESS PQC_LOOP n CONFIRM` | Executa ML-KEM em loop extremo, de 1 a 500 rodadas, para fechamento visual de limite. Exige `CONFIRM`. |

`STRESS` não é a fonte estatística oficial do seminário. Ele serve para
mostrar, ao vivo, uma carga agressiva e controlada no hardware depois dos
resultados consolidados.

Medição registrada em 2026-06-17:

| Perfil | Comando | Resultado |
|---|---|---|
| `BASELINE` 240 MHz | `PQC_BENCH 5` | `keygen_avg_us=3369`, `encap_avg_us=3878`, `decap_avg_us=5013`, `elapsed_us=62068`, `heap=202444`, `min_heap=198456` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24697`, `heap=202444`, `min_heap=198456`, `flash=4194304` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=39270` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_BENCH 5` | `keygen_avg_us=10101`, `encap_avg_us=11778`, `decap_avg_us=15214`, `elapsed_us=187371`, `heap=202444`, `min_heap=198456` |

Validação pós-upload registrada em 2026-06-18. As linhas `PQC_FAULT` abaixo
são registro técnico histórico; a demo visual atual usa `FAULT NONE|CRC32`.

| Perfil | Comando | Resultado |
|---|---|---|
| `BASELINE` 240 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=14117` |
| `BASELINE` 240 MHz | `PQC_FAULT 0 0x01 CONFIRM` | `result=PROTOCOL_REJECT`, `confirmation=HMAC-SHA256`, `key_match=0`, `tag_ready=1`, `confirm_us=960`, `elapsed_us=46579` |
| `BASELINE` 240 MHz | `PQC_FAULT 0 0x01 NONE` | `result=KEY_MISMATCH`, `confirmation=NONE`, `key_match=0`, `elapsed_us=35222` |
| `BASELINE` 240 MHz | `PQC_BENCH 100` | `ok=100`, `keygen_avg_us=3301`, `encap_avg_us=3864`, `decap_avg_us=4988`, `elapsed_us=1217337`, `heap=201512`, `min_heap=197624` |
| `OBC-1U-LIMITED` 80 MHz | `PQC_BENCH 100` | `ok=100`, `keygen_avg_us=10045`, `encap_avg_us=11769`, `decap_avg_us=15194`, `elapsed_us=3706253`, `heap=201512`, `min_heap=197624` |
| `OBC-1U-LIMITED` 80 MHz | `FAULT CRC32 5051432D534154 0 0x01` | `result=DETECTED_GUARD`, `crc_before=0xDFFEC3A1`, `crc_after=0x7989C815`, `elapsed_us=11` |

## Comandos completos de bancada

| Comando | Uso | Possibilidade de comunicação |
|---|---|---|
| `HELLO` | `HELLO` | Handshake; identifica `PQC-SAT-WISDOM`, placa, protocolo e transporte. |
| `PING` | `PING` | Teste de ida e volta UART com `uptime_ms`. |
| `STATUS` | `STATUS` | Estado do ESP32: perfil, chip, CPU, heap, flash e radio. |
| `TELEMETRY` | `TELEMETRY` | Snapshot de uptime, CPU, heap, potenciômetro, som, botão e relé. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Aplica bit-flip em payload hexadecimal e retorna `result`, byte antes/depois, CRC32 antes/depois e `elapsed_us`. |
| `PQC_INFO` | `PQC_INFO` | Reporta contrato PQC atual, backend real e métricas. |
| `PQC_KAT` | `PQC_KAT` | Executa vetor conhecido determinístico e retorna digests curtos. |
| `PQC_KEYGEN` | `PQC_KEYGEN` | Gera par ML-KEM-512 real e mede tempo/heap. |
| `PQC_ENCAP` | `PQC_ENCAP` | Encapsula para a chave pública armazenada. |
| `PQC_DECAP` | `PQC_DECAP` | Decapsula ciphertext armazenado e compara segredo compartilhado. |
| `PQC_FAULT` | `PQC_FAULT index mask [CONFIRM\|NONE]` | Comando avançado de bancada para corromper ciphertext ML-KEM. Mantido fora da demo visual; use `FAULT NONE|CRC32` para o popup didático. |
| `PQC_BENCH` | `PQC_BENCH n` | Executa benchmark de bancada para 1 a 100 rodadas. |
| `STRESS` | `STRESS PQC_LOOP n CONFIRM` | Executa carga extrema de ML-KEM para demonstrar limite operacional; use `n=500` no fechamento visual. |
| `MISSION` | `MISSION CLASSIC\|PQC\|PQC_CRC32 [payload_hex]` | Entrega mensagem curta e mede custo/bytes/segurança por cenário. |
| `PERIPHERALS` | `PERIPHERALS` | Detecta OLED, APDS-9960, HTU21D e MMA8452 no I2C. |
| `I2C_SCAN` | `I2C_SCAN` | Varre o barramento I2C em SDA21/SCL22. |
| `FEATURES` | `FEATURES`, `FEATURES CORE`, `FEATURES I2C`, `FEATURES GPIO`, `FEATURES ANALOG`, `FEATURES EXPANSION` | Lista grupos de recursos conhecidos pela firmware. |
| `BOARDMAP` | `BOARDMAP`, `BOARDMAP I2C`, `BOARDMAP GPIO`, `BOARDMAP ANALOG`, `BOARDMAP EXPANSION` | Reporta pinos, barramentos e endereços usados. |
| `SENSOR_READ` | `SENSOR_READ TEMP_HUM`, `SENSOR_READ ACCEL`, `SENSOR_READ APDS` | Lê sensores I2C embarcados. |
| `ANALOG` | `ANALOG`, `ANALOG POT`, `ANALOG SOUND` | Lê potenciômetro A39 e sensor de som A36. |
| `DIGITAL` | `DIGITAL`, `DIGITAL BUTTON`, `DIGITAL IR` | Lê botão, receptor IR e interrupções do acelerômetro. |
| `RGB` | `RGB R G B`, `RGB OFF`, `RGB TEST`, `RGB COMMON_ANODE`, `RGB COMMON_CATHODE` | Controla LED RGB e polaridade. |
| `BARGRAPH` | `BARGRAPH 0..4`, `BARGRAPH 0..100`, `BARGRAPH LEVEL n`, `BARGRAPH PERCENT n`, `BARGRAPH TEST`, `BARGRAPH ACTIVE_HIGH`, `BARGRAPH ACTIVE_LOW` | Controla LEDs de porcentagem e polaridade. |
| `LED` | `LED ON`, `LED OFF`, `LED TOGGLE`, `LED TEST`, `LED WHITE`, `LED RED`, `LED GREEN`, `LED BLUE`, `LED CYAN`, `LED MAGENTA`, `LED YELLOW` | Controla indicador principal via LED interno mais RGB onboard. |
| `RELAY` | `RELAY ON`, `RELAY OFF`, `RELAY TOGGLE` | Controla saída de relé em D33. |
| `SERVO` | `SERVO 0..180`, `SERVO DETACH`, `SERVO OFF` | Gera PWM para servo em D25 ou solta o canal. |
| `OLED` | `OLED INIT`, `OLED CLEAR`, `OLED TEST`, `OLED STANDBY` | Controla display OLED e ícone standby. |
| `PROFILE` | `PROFILE BASELINE`, `PROFILE OBC-1U-LIMITED` | Alterna perfil operacional do ESP32. |
| `RESET_STATS` | `RESET_STATS` | Zera contadores internos da firmware. |
| `HELP` | `HELP`, `HELP LED`, `HELP BARGRAPH`, `HELP RGB`, `HELP OLED` | Lista grupos ou explica um comando específico. |

## Política de uso

- Dashboard da apresentação: somente comandos ligados ao roteiro visual
  principal. Comandos de apoio e bancada ficam no HELP/terminal textual.
- Bancada, debug e desenvolvimento: qualquer comando desta referência pode ser
  enviado por `tools/serial_console.py`.
- Comandos que acionam expansões físicas, como `RELAY` e `SERVO`, não devem
  aparecer no console da apresentação sem necessidade explícita.
