# Referência de comandos de hardware

Este arquivo concentra as possibilidades completas de comunicação com a
BlackBoard Wisdom pelo protocolo serial `V1`.

Durante a demonstração ao vivo, os blocos clicáveis do dashboard devem expor
apenas comandos ligados ao enredo visual do projeto. Comandos de inventário,
bancada, debug e expansão ficam documentados aqui para desenvolvimento, testes
e manutenção; eles podem ser enviados pelo console
`tools/serial_console.py`.

Nomes da interface visual legada, como `DEMO`, `DEMO_PAUSE`, `DEMO_RESUME`,
`DEMO_STOP`, `DEMO_RESTART`, `RUN_BATTERY`, `CHECKSUM`, `EXPORT_JSON` e
`TOGGLE_LIVE_PAYLOAD`, não existem no dashboard público atual nem são comandos
do firmware. O comando `MISSION` continua no firmware como ferramenta de
pesquisa. A apresentação pública usa `GAME_*` com `ECDH` ou `MLKEM`; os
cenários `CLASSIC`/`PQC` são compatibilidade histórica.

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
| `MISSION` | `MISSION ECDH`, `MISSION ECDH_CRC32`, `MISSION MLKEM`, `MISSION MLKEM_CRC32` | Entrega mensagem curta no contrato `KEX_FAIR_V1`, medindo tempo, bytes, heap e resultado. |
| `KEX_INFO` | `KEX_INFO` | Prova backend, versão, KDF, política de otimização, acelerações desligadas e tamanhos públicos. |
| `KEX_BENCH` | `KEX_BENCH n` | Executa `n` pares ECDH/ML-KEM em ordem alternada, com `1 <= n <= 100`. |
| `SESSION_BENCH` | `SESSION_BENCH ECDH\|MLKEM 1\|100\|500\|1000 payload_hex` | Mede uma sessão FAIR nova e o custo amortizado de várias mensagens. |
| `GAME_*` | `GAME_BEGIN` … `GAME_END` | Protocolo transacional `STAGED_V1` do jogo público; cada comando executa uma etapa real separada. |
| `INVESTIGATE` | `INVESTIGATE cenário incidente payload_hex índice máscara id` | Compatibilidade monolítica de bancada/fluxo legado para o mesmo experimento em camadas. |
| `TOGGLE_LIVE_PAYLOAD` | nome histórico, removido | Não é comando do firmware nem controle do dashboard público atual. |
| `DEMO` | nome histórico, removido | Não existe no dashboard público nem no firmware. |
| `FAULT` | `FAULT NONE payload_hex index mask`, `FAULT CRC32 payload_hex index mask` | Comando serial técnico usado para validar bit-flip e CRC32 na placa. |
| `OLED` | `OLED STANDBY` | Restaura o ícone robo-satélite no display. |

`PING`, `TELEMETRY`, sensores, LED, RGB e bargraph continuam disponíveis pelo
HELP/terminal textual e pelo `tools/serial_console.py`, mas não devem aparecer
como blocos clicáveis da apresentação para evitar ruído visual e serial.
O dashboard público não aciona essas funções como controles de apresentação.

## Sensores e payload vivo legado

O modo visual `Payload vivo` e o botão `ENVIAR MSG` foram removidos. As leituras
continuam disponíveis para diagnóstico pelo console:

```text
SENSOR_READ TEMP_HUM
SENSOR_READ ACCEL
SENSOR_READ APDS
ANALOG POT
DIGITAL BUTTON
```

No jogo por etapas, `ANALOG POT` é solicitado de forma assíncrona
quando a faixa verde confirma `PROTECT`; D27 já fornece o mesmo valor em
`BUTTON_PING`. O valor 0..4095 é mapeado para uma posição dentro do payload.

O OLED continua com `OLED STANDBY`. O firmware atual não possui comando para
escrever texto arbitrário no display. LED/RGB/bargraph permanecem recursos de
bancada e não representam custo científico.

## Comando MISSION

`MISSION` mede uma sessão nova para uma mensagem e alimenta a bateria FAIR de
terminal. Não é um botão da jornada pública.

| Uso FAIR_V1 | Significado |
|---|---|
| `MISSION ECDH [payload_hex]` | ECDH P-256 efêmero estabelece o segredo; HKDF-SHA256 deriva a chave AES-128-GCM. |
| `MISSION ECDH_CRC32 [payload_hex]` | Mesmo fluxo ECDH com CRC32 dentro do plaintext protegido. |
| `MISSION MLKEM [payload_hex]` | ML-KEM-512 efêmero estabelece o segredo; o mesmo HKDF e AES-GCM completam a sessão. |
| `MISSION MLKEM_CRC32 [payload_hex]` | Mesmo fluxo ML-KEM com CRC32 dentro do plaintext protegido. |

Esses quatro comandos retornam `experiment=KEX_FAIR_V1`,
`crypto_impl=wolfCrypt-portable`, `crypto_version=5.9.2`,
`compiler=8.4.0`, `framework=arduino-esp32-2.0.17`,
`build_profile=robocore_wisdom_esp32_fair`, `kdf=HKDF-SHA256`,
`optimization=portable-software`, `target_asm=0`, `hw_crypto=0`,
`setup_us`, `initiator_us`, `responder_us`, `kex_total_us`,
`setup_bytes`, `response_bytes`, `data_bytes`, `wire_total_fresh` e
`wire_total_preprovisioned`. ECDH usa 65 + 65 bytes públicos; ML-KEM-512 usa
800 + 768 bytes.

## Comando SESSION_BENCH

```text
SESSION_BENCH ECDH 1 payload_hex
SESSION_BENCH MLKEM 100 payload_hex
SESSION_BENCH ECDH 500 payload_hex
SESSION_BENCH MLKEM 1000 payload_hex
```

Cada execução cria uma sessão FAIR, deriva as chaves AES-128 e processa a
quantidade indicada de mensagens com nonces únicos. A resposta separa
`session_setup_us`, `data_total_us`, `end_to_end_us`,
`amortized_us_per_message`, bytes de handshake/dados/fio e memória observável:
heap antes/depois, mínimo global, maior bloco e `stack_hwm_words`.

O mínimo de heap é global desde o boot e não representa pico isolado do
algoritmo. A consolidação oficial pareia ECDH/ML-KEM em ferramenta própria; não
use uma chamada manual como resultado estatístico.

### Compatibilidade histórica

| Uso | Significado |
|---|---|
| `MISSION CLASSIC` | Payload cifrado/autenticado por AES-128-GCM com chave efêmera gerada na placa. |
| `MISSION CLASSIC_CRC32` | Mesmo baseline local com CRC32 anexado ao plaintext antes da proteção AES-GCM. |
| `MISSION PQC` | ML-KEM-512 estabelece segredo; AES-128-GCM cifra e autentica a mensagem. |
| `MISSION PQC_CRC32` | Mesmo fluxo PQC com CRC32 inserido no material protegido antes da cifragem. |
| `MISSION CLASSIC payload_hex` | Executa o cenário clássico com payload hexadecimal escolhido. |
| `MISSION CLASSIC_CRC32 payload_hex` | Executa chave AES local + AES-GCM + CRC32 com payload hexadecimal escolhido. |
| `MISSION PQC payload_hex` | Executa PQC com payload hexadecimal escolhido. |
| `MISSION PQC_CRC32 payload_hex` | Executa PQC+CRC32 com payload hexadecimal escolhido. |

Campos retornados:

| Campo | Interpretação |
|---|---|
| `scenario` | `CLASSIC`, `CLASSIC_CRC32`, `PQC` ou `PQC_CRC32`. |
| `result` | `DELIVERED` ou `REJECTED`. |
| `crypto` | `AES-128-GCM` no clássico; `ML-KEM-512` nos cenários PQC. |
| `cipher` | Cifra AEAD usada no payload: `AES-128-GCM`. |
| `checksum` | `NONE` ou `CRC32`. |
| `key_source` | `RANDOM_SESSION` no clássico; `ML-KEM-512` no PQC. |
| `key_match` | Segredos ML-KEM bateram; sempre verdadeiro no clássico. |
| `aead_match` / `tag_match` | A tag AES-GCM foi aceita e o plaintext verificado. `tag_match` fica como alias para compatibilidade. |
| `crc_match` | CRC32 bateu quando checksum está ativo. |
| `bytes_total` | No legado, ciphertext do payload + ciphertext ML-KEM quando houver + nonce + tag GCM + CRC quando ativo. No FAIR_V1, coincide com `wire_total_fresh`. |
| `elapsed_us` | Tempo total da entrega medida na placa. |
| `keygen_us`, `encap_us`, `decap_us` | Subtempos ML-KEM; zero no cenário clássico. |
| `rng_us`, `kdf_us`, `encrypt_us`, `decrypt_us`, `crc_us` | Custo de RNG, derivação, cifragem, decifragem/verificação e checksum. |
| `heap`, `min_heap`, `cpu_mhz`, `profile` | Métricas do ESP32 no cenário. |

`PQC_FAULT ... CONFIRM` permanece apenas como comando técnico de bancada para
auditar sessões ML-KEM antigas do projeto. Ele não abre popup no dashboard e
não faz parte da demonstração visual de falha. Na apresentação, o incidente é
executado pelo protocolo `GAME_*`, com o guardião `NONE|CRC32`; `FAULT` fica
restrito à bancada. No fluxo `MISSION`, a autenticação da mensagem vem do
AES-GCM.

## Protocolo do jogo `STAGED_V1`

O `HELLO` atual anuncia
`game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`. A sequência válida
é:

```text
GAME_BEGIN G000001 BASELINE MLKEM CRC32 RX_MEMORY 54454D503D383443
GAME_PROTECT G000001
GAME_TRANSMIT G000001 0 0x01
GAME_VERIFY G000001
GAME_RETRY G000001
GAME_END G000001 ACCEPT
```

| Comando | Pré-condição | Efeito |
|---|---|---|
| `GAME_BEGIN id profile key guard incident payload_hex` | nenhuma sessão, ou início explícito novo | restaura o baseline, aplica perfil, serializa payload e CRC opcional |
| `GAME_PROTECT id` | `PREPARE` do mesmo ID | obtém chave, executa AES-GCM e monta o envelope |
| `GAME_TRANSMIT id index mask` | `PROTECT` do mesmo ID | fixa vetor single-bit, monta quadro e aplica incidente oculto |
| `GAME_VERIFY id` | `TRANSMIT` do mesmo ID | verifica quadro, GCM e CRC da aplicação; apaga segredos |
| `GAME_RETRY id` | `VERIFY` do mesmo ID | mesmo payload, nova chave/nonce, sem falha, resultado `DELIVERED` |
| `GAME_END id ACCEPT\|SAFE_MODE` | `VERIFY` ou `RETRY` do mesmo ID | registra decisão, preserva o resultado verificado, apaga sessão e restaura 240 MHz; `ACCEPT` não converte rejeição em entrega |
| `GAME_ABORT id` | qualquer estágio ativo do mesmo ID | apaga sessão e restaura o baseline |

ID ou ordem incorreta retorna `BAD_GAME_STATE` e limpa a sessão. `HELLO`, erro
fatal e reconexão também limpam. Respostas fornecem métricas, estados e CRCs
curtos de material; nunca chaves, segredos, nonce ou ciphertext completos.
`ANALOG POT` é a única consulta de bancada permitida enquanto a sessão está
ativa: ela lê A39 sem alterar o estágio e viabiliza a confirmação verde em
`PROTECT`. Outros comandos não `GAME_*` continuam falhando de forma fechada.

## Comando INVESTIGATE legado

O fluxo legado usa uma única execução real na Wisdom:

```text
INVESTIGATE PQC_CRC32 RX_MEMORY 54454D503D383443 0 0x01 C0001-RX_MEMORY-0
```

Os cenários são `CLASSIC`, `CLASSIC_CRC32`, `PQC` e `PQC_CRC32`. Os incidentes
são `NORMAL`, `CHANNEL_BITFLIP`, `TAMPER` e `RX_MEMORY`. A resposta inclui o vetor single-bit,
`frame_crc_tx/rx/match`, `aead_checked/match`,
`app_crc_present/checked/match`, aceitação, resultado, tempo, bytes e heap.
`TAMPER` recalcula o CRC não autenticado depois da mutação, mas não consegue
produzir uma tag GCM válida. `RX_MEMORY` ocorre depois da verificação GCM e só
é rejeitado pelo CRC da aplicação quando esse mecanismo está presente.

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
| `HELLO` | `HELLO` | Handshake; identifica placa/protocolo, anuncia `game=STAGED_V1`, traz `uptime_ms` e limpa qualquer sessão de jogo anterior. |
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
| `MISSION` | `MISSION CLASSIC\|CLASSIC_CRC32\|PQC\|PQC_CRC32 [payload_hex]` | Entrega mensagem curta e mede custo/bytes/segurança por cenário. |
| `GAME_BEGIN` | `GAME_BEGIN id profile CLASSIC\|PQC NONE\|CRC32 incident payload_hex` | Inicia sessão transacional e prepara o plaintext. |
| `GAME_PROTECT` | `GAME_PROTECT id` | Estabelece chave, protege com AES-GCM e monta envelope. |
| `GAME_TRANSMIT` | `GAME_TRANSMIT id index mask` | Confirma o vetor e aplica o incidente na camada definida. |
| `GAME_VERIFY` | `GAME_VERIFY id` | Produz as três evidências e apaga segredos. |
| `GAME_RETRY` | `GAME_RETRY id` | Retransmite mesmo payload com chave/nonce novos e sem falha. |
| `GAME_END` | `GAME_END id ACCEPT\|SAFE_MODE` | Encerra a sessão e restaura o baseline. |
| `GAME_ABORT` | `GAME_ABORT id` | Aborta, limpa a sessão e restaura o baseline. |
| `INVESTIGATE` | `INVESTIGATE scenario incident payload_hex index mask incident_id` | Instrumenta, na mesma execução, CRC externo do quadro, autenticação GCM e CRC interno da aplicação. |
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

Enquanto uma sessão `GAME_*` está ativa, ela possui uso exclusivo do perfil,
dos indicadores e dos buffers de trabalho ML-KEM. Nesse intervalo o firmware
aceita apenas a continuação `GAME_*`, um novo `GAME_BEGIN` (que substitui a
sessão) ou `HELLO` (reconexão e limpeza). Qualquer outro comando retorna
`BAD_GAME_STATE`, apaga a sessão e restaura o perfil baseline. Execute comandos
de bancada somente antes de `GAME_BEGIN` ou depois de `GAME_END`/`GAME_ABORT`.

## Política de uso

- Dashboard da apresentação: somente comandos ligados ao roteiro visual
  principal. Comandos de apoio e bancada ficam no HELP/terminal textual.
- Bancada, debug e desenvolvimento: qualquer comando desta referência pode ser
  enviado por `tools/serial_console.py`.
- Comandos que acionam expansões físicas, como `RELAY` e `SERVO`, não devem
  aparecer no console da apresentação sem necessidade explícita.
