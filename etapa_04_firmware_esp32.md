# Etapa 04 - Spike e firmware ESP32

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Determinar o que a placa real suporta e implementar somente o que for
demonstrado por build, teste conhecido e medição.

## Inventário obrigatório

Antes de criar o firmware, registrar:

```text
board_model
chip
cpu_arch
ram
flash
framework
toolchain_version
crypto_library
crypto_commit
license
```

Uma referência usa Kyber512-90s, ESP-IDF 5.0 e ESP32-S3. Outra demonstra
ML-KEM-512 em ESP32 no SBSeg 2025. Elas são pontos de partida concretos, mas
não fornecem automaticamente uma biblioteca pronta para a placa e o framework
deste projeto. O primeiro alvo operacional é ML-KEM-512; `pqm4` é voltado a
ARM Cortex-M4, não ao Xtensa do ESP32 clássico.

## Perfil OBC didático

Depois de identificar a placa real, implementar dois perfis:

### Baseline ESP32

- frequência máxima suportada pela placa;
- recursos disponíveis sem limitação adicional;
- rádio ainda desativado, pois a comunicação do experimento é UART.

### OBC-1U-LIMITED

- aplicação fixada a um core;
- CPU em 80 MHz;
- PSRAM proibida;
- orçamento de 256 KiB para aplicação e backend criptográfico;
- binário de aplicação com até 1 MiB;
- frames UART de até 256 bytes;
- ring buffer de 128 eventos;
- telemetria nominal a 1 Hz;
- uma operação criptográfica por vez;
- sem `malloc`/`new` no caminho crítico;
- watchdog e brownout ativos;
- free heap mínimo registrado.

Esses limites simulam uma política operacional conservadora. Eles não
representam uma especificação universal de CubeSat. Se a placa não suportar
algum item exatamente, documentar o equivalente aplicado.

## Marcos

### Implementacao inicial - transporte sem criptografia

Arquivos criados:

```text
firmware/README.md
firmware/esp32_serial_spike/esp32_serial_spike.ino
tools/serial_protocol.py
tools/serial_bridge.py
tools/serial_console.py
tests/test_serial_protocol.py
```

Escopo implementado inicialmente:

- protocolo serial `V1|request_id|COMMAND|arg`;
- respostas `V1|request_id|RESULT|status|key=value`;
- comandos `HELLO`, `PING`, `STATUS`, `TELEMETRY`, `FAULT`, `PROFILE`, `LED`,
  `RESET_STATS` e `HELP`;
- `crypto=none` e `fault=payload_crc32` reportados explicitamente;
- Wi-Fi e Bluetooth desativados no boot do sketch;
- perfil `OBC-1U-LIMITED` tentando fixar CPU em 80 MHz;
- perfil `BASELINE` retornando a frequencia observada no boot;
- parser do host coberto por testes unitarios.

Escopo atual do firmware Wisdom:

- mapa oficial da BlackBoard Wisdom incorporado ao firmware;
- comandos `FEATURES`, `BOARDMAP`, `PERIPHERALS` e `I2C_SCAN`;
- leitura analogica de potenciometro `A39` e sensor de som `A36`;
- leitura digital de botao `D27`, IR `D26` e interrupcoes do acelerometro;
- controle do bargraph em `D17`, `D16`, `D4` e `D13`;
- controle do LED RGB em `R19`, `G23` e `B18`;
- controle dos conectores de rele `D33` e servo `D25`;
- deteccao I2C de OLED, APDS-9960, HTU21D e MMA8452QT;
- leitura direta de HTU21D, MMA8452QT e APDS-9960;
- comando `FAULT NONE|CRC32 payload_hex index mask` para mutacao real de
  payload e comparacao de CRC32;
- suporte minimo ao OLED SSD1306 para inicializacao, limpeza, padrao de teste
  e standby com icone pixel-art do robo/satelite usado no dashboard;
- backend ML-KEM-512 real vendorizado em `firmware/lib/mlkem_native`, usando
  `mlkem-native` v1.1.0, commit `d2cae2b`, licença
  `Apache-2.0 OR ISC OR MIT`;
- build PlatformIO validado apos ML-KEM real: 55.724 bytes de RAM estimada
  e 912.541 bytes de flash;
- upload desta revisão executado em `/dev/ttyUSB0` e verificado por hash pelo
  `esptool.py`;
- validacao real em placa: `HELLO`, `STATUS`, `FAULT NONE ... 0 0x01` e
  `FAULT CRC32 ... 0 0x01`.
- perfis validados em placa: `PROFILE OBC-1U-LIMITED` reportou 80 MHz e
  `PROFILE BASELINE` reportou 240 MHz.
- validação real de ML-KEM em placa: `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`,
  `PQC_ENCAP`, `PQC_DECAP` e `PQC_BENCH 2` funcionais; `PQC_KAT` retornou
  `kat=pass`, `ss_crc32=0xD9DA8D6C`; `PQC_DECAP` retornou `key_match=1`.
- medição inicial de ML-KEM em placa nos dois perfis: `PQC_BENCH 5` em
  `BASELINE` e `OBC-1U-LIMITED`, mais `PQC_INFO` e `PQC_KAT` no perfil
  limitado.

Pendencias para coleta final e relatório:

- executar bateria maior que `PQC_BENCH 5` sem watchdog;
- registrar tabela final de tempo, heap, heap mínimo e flash no relatório;
- exportar amostras PQC no JSON da campanha sem segredos completos;
- decidir se Arduino/PlatformIO fica congelado como framework final.

### Marco 1 - transporte

- boot identificável;
- parser sem `String` para caminhos críticos;
- `PING`;
- framing versionado;
- `request_id`;
- timeout e erro explícito.

### Marco 2 - experimento de payload

- buffer fixo;
- CRC32 conhecido;
- mutação por índice/máscara;
- resposta com bytes antes/depois;
- testes single-bit.

### Marco 3 - backend criptográfico

Estado: **backend ML-KEM-512 real implementado, validado em placa e medido nos
perfis `BASELINE` e `OBC-1U-LIMITED`; bateria prolongada pendente**.

Objetivo imediato: executar ML-KEM-512 na Wisdom, com variante, fonte, commit
e licença registrados. Se a primeira porta viável for Kyber512 pré-FIPS, ela
deve ser rotulada como Kyber512 e não como ML-KEM/FIPS 203.

Escolher uma opção e rotular corretamente:

1. ML-KEM conforme FIPS 203;
2. Kyber de versão identificada;
3. KEM real executado no host;
4. emulador didático explicitamente marcado.

Não chamar AES, hash ou bytes aleatórios de ML-KEM.

Interface serial implementada:

| Comando | Função |
|---|---|
| `PQC_INFO` | Reporta `pqc_target=ML-KEM-512`, `pqc_backend=mlkem-native`, `pqc_status=ready`, variante, commit, licença, tamanhos, CPU, heap, flash, perfil e tempo. |
| `PQC_KAT` | Executa vetor determinístico do projeto com `*_derand`; compara o segredo esperado e retorna digests curtos. |
| `PQC_KEYGEN` | Gera par ML-KEM-512 real, armazena na RAM e retorna tempo, heap e digest curto da chave pública. |
| `PQC_ENCAP` | Encapsula usando a chave pública armazenada e retorna tempo, digest curto do ciphertext e digest curto do segredo. |
| `PQC_DECAP` | Decapsula o ciphertext armazenado e retorna `key_match` comparando os segredos. |
| `PQC_BENCH n` | Executa `n` rodadas keygen/encap/decap, limitado a 1..20 por comando. |

Esses comandos continuam fora do `HELP` visual do dashboard. Eles são comandos
de bancada; o dashboard usa `PQC_STATUS` para consultar `PQC_INFO` sem expor
opções técnicas demais durante a apresentação.

Medição real registrada em 2026-06-17:

| Perfil | CPU | Comando | Resultado |
|---|---:|---|---|
| `BASELINE` | 240 MHz | `PQC_BENCH 5` | `keygen_avg_us=3369`, `encap_avg_us=3878`, `decap_avg_us=5013`, `elapsed_us=62068`, `heap=202444`, `min_heap=198456` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24697`, `heap=202444`, `min_heap=198456`, `flash=4194304` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=39270` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_BENCH 5` | `keygen_avg_us=10101`, `encap_avg_us=11778`, `decap_avg_us=15214`, `elapsed_us=187371`, `heap=202444`, `min_heap=198456` |

### Marco 4 - validação

- [x] KAT/vetor conhecido;
- [x] encapsulação e decapsulação produzem o mesmo segredo sem falha;
- [x] versão e parâmetros aparecem na telemetria;
- [ ] 100 iterações sem watchdog;
- [x] RAM, flash e tempos registrados para a medição inicial.

Cada benchmark deve ser executado nos dois perfis. O relatório compara:

- tempo;
- pico de RAM;
- tamanho de firmware;
- resets/watchdog;
- possibilidade de cumprir a janela operacional.

## ML-KEM e falhas

Para ciphertext de tamanho válido:

- decapsulação produz um segredo;
- corrupção pode gerar segredo diferente;
- o harness pode registrar `KEY_MISMATCH`;
- o receptor precisa de confirmação autenticada para registrar
  `PROTOCOL_REJECT`.

Não use `DETECTED_BY_DECAPS` como se o KEM retornasse falha explícita.

## API de integridade

A referência deve ser armazenada antes da mutação:

```cpp
guard_prepare(data, len);
inject_fault(data, len, index, mask);
bool detected = guard_verify(data, len);
```

Uma função que compara contra checksums estáticos nunca inicializados é
inválida.

## Estrutura sugerida

```text
firmware/
  README.md
  sdkconfig.defaults
  main/
    app_main.c
    protocol.c
    protocol.h
    experiment.c
    experiment.h
    integrity.c
    integrity.h
    crypto_backend.c
    crypto_backend.h
```

Use a estrutura real do framework escolhido; não force `.ino` se a biblioteca
depender de ESP-IDF.

## Go/no-go

O marco ML-KEM no ESP32 só recebe `GO` se:

- compilar de forma reproduzível;
- passar vetor conhecido;
- caber na placa;
- executar dentro do tempo da atividade.

Caso contrário, use KEM no host e mantenha o ESP32 como alvo de falha e
telemetria.

## Aceite

- [x] Inventário da placa registrado.
- [x] Perfis `BASELINE` e `OBC-1U-LIMITED` reproduzíveis.
- [x] Protocolo serial inicial funciona no codigo antes da PQC.
- [x] CRC32 funciona antes da PQC.
- [x] Backend criptográfico identificado sem marketing indevido.
- [x] KAT e métricas iniciais anexados.
- [x] Fallback continua sendo tecnicamente honesto.
