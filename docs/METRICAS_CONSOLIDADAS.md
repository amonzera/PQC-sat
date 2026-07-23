# Métricas consolidadas da apresentação - PQC-SAT

Este documento define como medir e apresentar o impacto de segurança e
desempenho no hardware limitado usado como OBC educacional. Ele é a referência
para consolidar os resultados do seminário.

## 1. Objetivo atual do seminário

A comparação principal é entre dois mecanismos completos de estabelecimento
de segredo:

| Cenário | Estabelecimento | Componentes comuns | Comando |
|---|---|---|---|
| `ECDH` | ECDH P-256 efêmero | wolfCrypt RNG + HKDF-SHA256 + AES-128-GCM | `MISSION ECDH` |
| `MLKEM` | ML-KEM-512 efêmero | wolfCrypt RNG + HKDF-SHA256 + AES-128-GCM | `MISSION MLKEM` |

O contrato experimental é `KEX_FAIR_V1`: mesma biblioteca, versão, placa,
frequência, compilador, flags e política `portable-software`, sem assembly
específico do alvo nem aceleração criptográfica. A afirmação permitida é
sempre contextual:

> Nestas implementações e configurações específicas para ESP32, observamos
> estes custos de ECDH P-256 e ML-KEM-512.

`CRC32` continua sendo uma variável ortogonal do jogo (`NONE`/`CRC32`) e não
altera o mecanismo de estabelecimento. Os cenários `CLASSIC`,
`CLASSIC_CRC32`, `PQC` e `PQC_CRC32` permanecem apenas para reprodução
histórica e regressão. `CLASSIC` não executa ECDH e não pode mais ser usado
como baseline de criptografia assimétrica clássica.

> Estado dos números em 2026-07-23: a primeira bateria `KEX_FAIR_V1` na
> Wisdom foi concluída, mas é uma evidência exploratória parcial e não uma
> coleta oficial aprovada. Ela registrou 36 timeouts, portanto
> `official_candidate=false`. A consolidação humana, incluindo as 480 sessões
> válidas e a análise da falha, está em
> [`RESULTADOS_KEX_FAIR_20260723.md`](RESULTADOS_KEX_FAIR_20260723.md).
> O arquivo
> `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json` comprova o experimento
> legado AES-local versus ML-KEM, mas não responde ECDH versus ML-KEM.

### 1.1 Desenho FAIR_V1: sessão nova e custo amortizado

A bateria separa duas perguntas, sem misturar as distribuições:

| Família | Unidade experimental | Comando |
|---|---|---|
| `fresh` | um estabelecimento novo e uma mensagem | `MISSION ECDH|MLKEM payload_hex` |
| `session` | um estabelecimento novo e 1, 100, 500 ou 1000 mensagens sob a mesma chave de sessão | `SESSION_BENCH ECDH|MLKEM n payload_hex` |

Cada par usa o mesmo perfil, payload e quantidade de mensagens. A ordem
ECDH/ML-KEM é alternada dentro de cada célula para reduzir viés de aquecimento
e deriva temporal. `KEX_BENCH n` oferece ainda a decomposição pareada do KEX.

As amostras `fresh` registram:

| Campo | Interpretação |
|---|---|
| `setup_us` | Receptor prepara o primeiro material público: chave P-256 ou chave pública ML-KEM. |
| `initiator_us` | Iniciador gera sua resposta e seu segredo: ponto P-256 ou cápsula ML-KEM. |
| `responder_us` | Receptor obtém o mesmo segredo: ECDH ou decapsulação. |
| `kex_total_us` | Soma dos três subtempos do estabelecimento. |
| `kdf_us` | Duas derivações HKDF-SHA256 para verificar igualdade ponta a ponta. |
| `online_us` | Sessão completa menos o setup, útil quando a chave pública pode ser pré-distribuída. |
| `end_to_end_us` | Setup + resposta + HKDF + AES-GCM da mensagem. |
| `setup_bytes` / `response_bytes` | Material público inicial e resposta pública. |
| `data_bytes` | Ciphertext da mensagem + nonce + tag GCM. |
| `wire_total_fresh` | Setup + resposta + dados quando toda a sessão é nova. |
| `wire_total_preprovisioned` | Resposta + dados quando o setup já foi distribuído. |

As amostras `session` acrescentam:

| Campo | Interpretação |
|---|---|
| `session_setup_us` | KEX mais as duas derivações HKDF. |
| `data_total_us` | nonce inicial e processamento AES-GCM de todas as mensagens. |
| `amortized_us_per_message` | tempo ponta a ponta inteiro dividido por `n`. |
| `handshake_bytes` | material público inicial mais resposta pública. |
| `data_bytes_per_message` / `data_total_bytes` | nonce, ciphertext e tag por mensagem e no lote. |
| `wire_total_bytes` / `amortized_bytes_per_message` | handshake mais lote e custo médio inteiro. |
| `heap_before` / `heap_after` / `heap_delta` | heap livre antes e depois da amostra. |
| `min_heap_before` / `min_heap_global` | mínimo global desde o boot, útil como guarda de regressão, não como pico isolado do algoritmo. |
| `largest_block_before` / `largest_block_after` | maior bloco contíguo livre. |
| `stack_hwm_words` | menor folga de stack observada na task do loop. |

O contador de nonce ocupa os quatro bytes finais de um prefixo aleatório de
oito bytes e não se repete dentro da sessão. O benchmark mede custo do sistema
completo nos dois papéis lógicos; não mede rede real, energia elétrica,
resistência a side channel nem pico de heap isolado por algoritmo.

Antes da coleta, o upload cria um manifesto que vincula hash do binário, hashes
das fontes FAIR, hash determinístico da árvore wolfSSL local, porta,
ambiente PlatformIO e os handshakes anterior e posterior. A bateria oficial
recusa fonte, dependência ou binário alterado, porta diferente e firmware sem
`session_bench=FAIR_SESSION_V1`. O hash prova qual árvore local entrou no
artefato; ele não redistribui nem substitui a licença GPLv3 ou comercial
aplicável à árvore usada.

```text
python3 tools/kex_metrics_battery.py --dry-run

python3 tools/firmware_deploy.py --upload --port /dev/ttyUSB0

python3 tools/kex_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --deployment-manifest logs/firmware/<timestamp>_firmware_deploy_dev-ttyUSB0.json \
  --timeout 20 \
  --fresh-cycles 100 \
  --session-repeats 30 \
  --message-counts 1 100 500 1000 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

O JSON esperado usa `pqc-sat-kex-fair-metrics-v2`, preserva todas as amostras
brutas, calcula média, mediana, desvio padrão, p95 e intervalo de confiança de
95% das diferenças pareadas. Somente a configuração completa — dois perfis,
100 pares `fresh` por perfil, 30 pares por célula `session`, 1/100/500/1000
mensagens, três repetições de `KEX_BENCH 100`, pausa mínima de 0,25 s,
manifesto válido, versão 5.9.2 e payload padronizado — pode produzir
`official_candidate=true`.

O resumo oficial esperado tem `failed=0`, `fresh_mission_runs=400`,
`session_bench_runs=480`, `kex_bench_runs=6`, `invalid_pairs=0`,
`missing_cells=0` e `profile_mismatches=0`. Execuções menores continuam úteis
como smoke e retornam sucesso se os dados forem válidos, mas ficam
explicitamente não oficiais. Essa bateria longa é executada pelo operador,
nunca pelo dashboard ou pelo agente.

## 2. Experimento legado preservado

O comando `MISSION` roda na BlackBoard Wisdom/ESP32 e mede a entrega de uma
mensagem de missão.

Esses comandos permanecem na superfície textual de engenharia e nos logs
históricos. O dashboard público atual não possui modo `Payload vivo`, botão de
`STRESS` nem tela `RESULTADOS`; a atividade usa exclusivamente o protocolo
`STAGED_V1/FAIR_V1`. O comando técnico `STRESS PQC_LOOP 500 CONFIRM` também
continua disponível, mas não substitui nenhuma bateria consolidada.

### `MISSION CLASSIC`

Fluxo:

1. a placa pega o payload padrão `PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK`;
2. gera uma chave AES-128 efêmera e um nonce aleatório;
3. cifra o payload com `AES-128-GCM` e gera a tag GCM;
4. decifra/verifica a tag como se fosse o receptor;
5. retorna tempo, bytes, heap e resultado.

Esse cenário não executa PQC. Ele é o baseline clássico simétrico de mensagem
cifrada/autenticada, não uma pilha assimétrica completa.

### `MISSION PQC`

Fluxo:

1. a placa gera um par `ML-KEM-512`;
2. encapsula um segredo;
3. decapsula o ciphertext;
4. compara se os dois lados chegaram ao mesmo segredo;
5. deriva uma chave AES-128 a partir do segredo compartilhado;
6. cifra/verifica o payload com `AES-128-GCM`;
7. retorna tempo, bytes, heap e resultado.

Esse cenário demonstra o custo de introduzir PQC na sessão.

### `MISSION PQC_CRC32`

Fluxo:

1. executa o mesmo caminho do `MISSION PQC`;
2. calcula `CRC32` do payload;
3. inclui o CRC no material protegido antes da cifragem AES-GCM;
4. verifica se o CRC recebido bate após decifrar;
5. retorna o custo adicional do checksum.

Esse cenário demonstra o acúmulo de custo: PQC mais guardião de integridade.

## 3. Métricas exportadas

Cada resposta `MISSION` entra no JSON em:

```text
metrics.mission.scenarios.CLASSIC
metrics.mission.scenarios.PQC
metrics.mission.scenarios.PQC_CRC32
```

Campos principais:

| Campo | Como usar na apresentação |
|---|---|
| `elapsed_us` | Tempo total observado no cenário. |
| `keygen_us` | Custo de geração de chave ML-KEM; zero no cenário clássico. |
| `encap_us` | Custo de encapsulamento ML-KEM; zero no cenário clássico. |
| `decap_us` | Custo de decapsulação ML-KEM; zero no cenário clássico. |
| `rng_us` | Custo de gerar chave/nonce quando aplicável. |
| `kdf_us` | Custo de derivar chave AES a partir do segredo ML-KEM. |
| `encrypt_us` / `tag_us` | Custo de cifrar e gerar tag AES-GCM (`tag_us` fica como alias histórico). |
| `decrypt_us` / `verify_us` | Custo de decifrar/verificar AES-GCM (`verify_us` fica como alias histórico). |
| `crc_us` | Custo do CRC32; zero quando checksum está desligado. |
| `bytes_total` | Tamanho relativo transmitido para a entrega da mensagem. |
| `heap` / `min_heap` | RAM livre e menor RAM livre observada na amostra. |
| `cpu_mhz` | Frequência do perfil ativo. |
| `profile` | `BASELINE` ou `OBC-1U-LIMITED`. |
| `key_match` | Se os segredos ML-KEM bateram. |
| `aead_match` / `tag_match` | Se a verificação AES-GCM aceitou a mensagem. |
| `crc_match` | Se o checksum bateu. |
| `result` | `DELIVERED` ou `REJECTED`. |

O JSON também calcula:

```text
metrics.mission.ratios.pqc_vs_classic
metrics.mission.ratios.pqc_crc32_vs_classic
metrics.mission.ratios.crc32_over_pqc
```

Essas razões são as mais fáceis de explicar em sala.

## 4. Métricas na jornada pública

Durante `PREPARE`, `PROTECT`, `TRANSMIT`, `VERIFY` e `RETRY`, a interface
explica entrada, operação e saída sem exibir números de benchmark. A animação
didática é ampliada e não representa segundos de parede.

Somente `DEBRIEF` mostra os recursos da partida atual: tempo agregado, bytes do
resultado final e heap mínimo informado pela Wisdom. Esses três números servem
à conversa local com o visitante e não entram na consolidação científica.
Resultados oficiais vêm exclusivamente da bateria controlada no terminal.

## 4.5. Resultados reais consolidados do experimento legado

Fonte histórica do experimento AES-local versus ML-KEM:

```text
logs/20260702T044907Z_final_metrics_dev-ttyusb0.json
```

Essa é a bateria oficial mais recente do protocolo legado. Ela não deve ser
apresentada como ECDH versus ML-KEM. Embora tenha
sido produzida pelo runner geral, a validação foi recalculada diretamente dos
600 registros `MISSION`: todos retornaram `cipher=AES-128-GCM`,
`nonce_bytes=12`, `gcm_tag_bytes=16`, `aead_match=1` e `decrypt_ok=1`.

Resumo da bateria mais recente:

- 1.038 registros;
- 0 falhas de comando;
- 600 `MISSION runs`;
- 400 testes `FAULT`;
- 6 execuções `PQC_BENCH 100`;
- duração de 336,62 s;
- consolidação AES-GCM com `official_candidate=true`;
- `non_aes_gcm_records=0`;
- `missing_required_fields=0`;
- `aead_failures=0`;
- `nonce_crc32_duplicates=0`.

Validação AES-GCM:

- `cipher=AES-128-GCM`: 600/600 `MISSION`;
- `aead_match=1`: 600/600 `MISSION`;
- `decrypt_ok=1`: 600/600 `MISSION`;
- `nonce_crc32`: 600 valores únicos em 600 mensagens;
- `ciphertext_crc32`: 600 valores únicos em 600 mensagens;
- `gcm_tag_crc32`: 600 valores únicos em 600 mensagens.

Isso confirma que o payload fixo foi cifrado com nonce aleatório por mensagem:
mesmo com o mesmo plaintext, nonce, ciphertext e tag GCM variaram nas 600
execuções.

### MISSION AES-GCM — BASELINE (240 MHz, 100 amostras por cenário)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` (avg) | 611 | 14.152 | 14.097 |
| `bytes_total` | 69 | 837 | 841 |
| `bytes_payload` | 41 | 41 | 41 |
| `bytes_crypto` | 28 | 796 | 796 |
| `bytes_checksum` | 0 | 0 | 4 |
| `bytes_ciphertext` | 41 | 41 | 45 |
| `encrypt_us` (avg) | 365 | 389 | 416 |
| `decrypt_us` (avg) | 125 | 124 | 125 |
| `rng_us` (avg) | 19 | 19 | 19 |
| `kdf_us` (avg) | 0 | 831 | 814 |
| `keygen_us` (avg) | 0 | 3.743 | 3.678 |
| `encap_us` (avg) | 0 | 3.953 | 3.934 |
| `decap_us` (avg) | 0 | 5.029 | 5.019 |
| `crc_us` (avg) | 0 | 0 | 32 |
| `result` | DELIVERED | DELIVERED | DELIVERED |

### MISSION AES-GCM — OBC-1U-LIMITED (80 MHz, 100 amostras por cenário)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` (avg) | 1.028 | 40.197 | 40.077 |
| `bytes_total` | 69 | 837 | 841 |
| `bytes_payload` | 41 | 41 | 41 |
| `bytes_crypto` | 28 | 796 | 796 |
| `bytes_checksum` | 0 | 0 | 4 |
| `bytes_ciphertext` | 41 | 41 | 45 |
| `encrypt_us` (avg) | 554 | 600 | 607 |
| `decrypt_us` (avg) | 314 | 313 | 316 |
| `rng_us` (avg) | 29 | 24 | 23 |
| `kdf_us` (avg) | 0 | 1.498 | 1.478 |
| `keygen_us` (avg) | 0 | 10.524 | 10.450 |
| `encap_us` (avg) | 0 | 11.882 | 11.833 |
| `decap_us` (avg) | 0 | 15.259 | 15.221 |
| `crc_us` (avg) | 0 | 0 | 53 |
| `result` | DELIVERED | DELIVERED | DELIVERED |

Razões observadas na bateria AES-GCM:

| Comparação | BASELINE | OBC-1U-LIMITED |
|---|---:|---:|
| PQC / CLASSIC em tempo | 23,2x | 39,1x |
| PQC+CRC / CLASSIC em tempo | 23,1x | 39,0x |
| PQC / CLASSIC em bytes | 12,1x | 12,1x |
| bytes extras do CRC32 | +4 B | +4 B |

Falhas na bateria AES-GCM:

- `FAULT NONE`: 200/200 resultados `SILENT`;
- `FAULT CRC32`: 200/200 resultados `DETECTED_GUARD`.

`PQC_BENCH 100` na bateria AES-GCM:

| Perfil | keygen avg | encap avg | decap avg |
|---|---:|---:|---:|
| `BASELINE` 240 MHz | 3.302 us | 3.866 us | 4.990 us |
| `OBC-1U-LIMITED` 80 MHz | 10.067 us | 11.789 us | 15.217 us |

Bateria oficial anterior pós-AES, preservada para comparação de payload:

```text
logs/20260626T051412Z_aes_gcm_metrics_dev-ttyusb0.json
```

Ela usava payload de 34 B, contra 41 B na coleta atual. Por isso os totais
anteriores 62/830/834 B não devem substituir os atuais 69/837/841 B.

Bateria diagnóstica anterior:

```text
logs/20260626T044359Z_aes_gcm_metrics_dev-ttyusb0.json
```

Essa coleta terminou sem falhas de comando, mas foi rejeitada como fonte
oficial AES-GCM porque a placa ainda estava com firmware antigo: os `MISSION`
voltaram sem `cipher=AES-128-GCM`, sem `nonce_crc32` e sem `gcm_tag_crc32`. Ela
foi mantida apenas como histórico de diagnóstico do processo de atualização do
firmware.

Fonte histórica principal pré-AES:

```text
logs/20260625T005330Z_final_metrics_dev-ttyusb0.json
```

Coleta histórica: 3.074 registros, 0 falhas, 1.800 `MISSION runs`, 10
`PQC_BENCH` de 100 rounds, 1.200 testes `FAULT`, duracao 1.681,24 s.

Configuração:

- 300 ciclos por perfil;
- 300 amostras por cenário em `BASELINE` 240 MHz;
- 300 amostras por cenário em `OBC-1U-LIMITED` 80 MHz;
- 5 execuções `PQC_BENCH 100` por perfil;
- 300 `FAULT NONE` e 300 `FAULT CRC32` por perfil.

### Histórico pré-AES — MISSION BASELINE (240 MHz, 300 amostras por cenário)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` (avg) | 511 | 13.234 | 13.130 |
| `elapsed_us` (median) | 504 | 13.175 | 13.111 |
| `elapsed_us` (p95) | 509 | 13.545 | 13.123 |
| `elapsed_us` (min) | 498 | 13.161 | 13.083 |
| `elapsed_us` (max) | 922 | 14.155 | 14.084 |
| `elapsed_us` (stdev) | 39 | 214 | 136 |
| `keygen_us` (avg) | 0 | 3.684 | 3.586 |
| `encap_us` (avg) | 0 | 3.937 | 3.911 |
| `decap_us` (avg) | 0 | 5.029 | 5.012 |
| `tag_us` (avg) | 335 | 408 | 435 |
| `verify_us` (avg) | 168 | 168 | 168 |
| `crc_us` (avg) | 0 | 0 | 10 |
| `bytes_total` | 73 | 841 | 845 |
| `heap` | 201.412 | 201.412 | 201.412 |
| `min_heap` | 197.624 | 197.624 | 197.624 |
| `result` | DELIVERED | DELIVERED | DELIVERED |
| `runs OK` | 300/300 | 300/300 | 300/300 |
| `tag_match` | 100% | 100% | 100% |
| `key_match` | 100% | 100% | 100% |
| `crc_match` | 100% | 100% | 100% |

### Histórico pré-AES — MISSION OBC-1U-LIMITED (80 MHz, 300 amostras por cenário)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` (avg) | 1.139 | 38.837 | 38.738 |
| `elapsed_us` (median) | 1.130 | 38.689 | 38.643 |
| `elapsed_us` (p95) | 1.157 | 39.085 | 38.672 |
| `elapsed_us` (min) | 1.112 | 38.637 | 38.587 |
| `elapsed_us` (max) | 1.457 | 42.020 | 41.625 |
| `elapsed_us` (stdev) | 36 | 631 | 533 |
| `keygen_us` (avg) | 0 | 10.469 | 10.380 |
| `encap_us` (avg) | 0 | 11.869 | 11.838 |
| `decap_us` (avg) | 0 | 15.265 | 15.244 |
| `tag_us` (avg) | 648 | 740 | 751 |
| `verify_us` (avg) | 478 | 477 | 477 |
| `crc_us` | 0 | 0 | 30 |
| `bytes_total` | 73 | 841 | 845 |
| `heap` | 201.412 | 201.412 | 201.412 |
| `min_heap` | 197.624 | 197.624 | 197.624 |
| `result` | DELIVERED | DELIVERED | DELIVERED |
| `runs OK` | 300/300 | 300/300 | 300/300 |
| `tag_match` | 100% | 100% | 100% |
| `key_match` | 100% | 100% | 100% |
| `crc_match` | 100% | 100% | 100% |

### Razões históricas pré-AES

| Comparacao | Tempo | Bytes |
|---|---:|---:|
| PQC / CLASSIC (BASELINE) | 25,9x | 11,5x |
| PQC_CRC32 / CLASSIC (BASELINE) | 25,7x | 11,6x |
| PQC / CLASSIC (OBC-1U-LIMITED) | 34,1x | 11,5x |
| PQC_CRC32 / CLASSIC (OBC-1U-LIMITED) | 34,0x | 11,6x |
| CRC32 custo adicional sobre PQC (BASELINE) | ~10 us | +4 bytes |
| CRC32 custo adicional sobre PQC (OBC-1U-LIMITED) | ~30 us | +4 bytes |

Leitura didática:

- A 240 MHz, PQC custa cerca de 26 vezes mais tempo que o baseline clássico.
- A 80 MHz, a mesma operação PQC custa cerca de 34 vezes mais que o clássico
  limitado. O ML-KEM sofre mais com CPU reduzida que o caminho simétrico.
- O CRC32 adiciona custo negligivel (~10 us a 240 MHz, ~30 us a 80 MHz),
  mostrando que verificação de integridade no payload é barata.
- Na bateria histórica pré-AES, o trafego PQC da missão foi 11,5x maior que o
  clássico porque o pacote de entrega contabilizava payload + ciphertext
  ML-KEM (768 bytes) + tag HMAC (32 bytes). Na versão atual, a composição
  passa a ser payload cifrado + ciphertext ML-KEM + nonce + tag GCM. A chave
  publica ML-KEM tem 800 bytes, mas não está sendo somada nesse `bytes_total`
  da mensagem consolidada.
- A heap permaneceu constante em todos os cenários: a criptografia PQC não
  causou fragmentacao perceptivel nos testes.

### PQC_BENCH histórico (100 rounds)

| Perfil | CPU | Runs | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|---:|---:|
| BASELINE | 240 MHz | 5 | 3.302 | 3.866 | 4.990 |
| OBC-1U-LIMITED | 80 MHz | 5 | 10.066 | 11.787 | 15.217 |

Fator de desaceleracao 80/240 MHz: keygen ~3,0x, encap ~3,0x, decap ~3,0x.

### Validações históricas

| Teste | Resultado |
|---|---|
| PQC_KAT | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| PQC_FAULT 0 0x01 CONFIRM | `PROTOCOL_REJECT`, `key_match=0` |
| PQC_FAULT 0 0x01 NONE | `KEY_MISMATCH`, `key_match=0` |
| FAULT NONE (coleta final) | 600/600 `SILENT` |
| FAULT CRC32 (coleta final) | 600/600 `DETECTED_GUARD` |

### Falhas de payload na coleta histórica

| Perfil | Sem CRC32 | Com CRC32 |
|---|---:|---:|
| BASELINE 240 MHz | 300/300 `SILENT` | 300/300 `DETECTED_GUARD` |
| OBC-1U-LIMITED 80 MHz | 300/300 `SILENT` | 300/300 `DETECTED_GUARD` |

Tempo médio da verificação de falha:

| Perfil | `FAULT NONE` | `FAULT CRC32` |
|---|---:|---:|
| BASELINE 240 MHz | 17 us | 13 us |
| OBC-1U-LIMITED 80 MHz | 44 us | 39 us |

### Conclusões para o seminário

1. O objetivo principal foi atingido: a Wisdom/ESP32 executou ML-KEM-512 real,
   entregou mensagens nos três cenários e exportou métricas de tempo, bytes e
   heap.
2. Na bateria oficial AES-GCM, `PQC` foi 23,2x mais lento que `CLASSIC` a
   240 MHz e 39,1x mais lento no perfil limitado de
   80 MHz.
3. O custo de tráfego também é didático: `PQC` saiu de 69 bytes para 837
   bytes por entrega consolidada.
4. CRC32 adicionou custo pequeno no payload (+4 bytes e 32 us em média a
   240 MHz), mas
   tornou visível a diferença entre falha silenciosa e erro detectado:
   200/200 `SILENT` sem CRC32 contra 200/200 `DETECTED_GUARD` com CRC32.
5. A RAM livre permaneceu estável, então a evidência principal desta versão é
   tempo/tráfego, não exaustão de heap.

### Próximos passos reais

Para o seminário atual:

- usar o botão `RESULTADOS` do dashboard como resumo final da bateria;
- usar `STRESS PQC 500` apenas como fechamento opcional de impacto visual;
- não rodar bateria longa durante a apresentação;
- demonstrar manualmente `CLÁSSICA`, `PQC`, `PQC+CRC`, `ENVIAR MSG` e
  `FALHA`;
- citar `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json` como fonte
  dos dados consolidados.

Para evolucao cientifica futura:

- medir energia real com instrumento externo, porque `MHz * us` não é watts;
- comparar com uma pilha clássica assimetrica mais completa, como ECDH + HMAC;
- repetir a coleta em outros perfis de clock e com payloads maiores;
- testar bursts de bit-flips e corrupções fora da regiao coberta pelo CRC32.

## 5. Coleta curta para ensaio

Depois de gravar o firmware atualizado:

```bash
python3 tools/serial_console.py --port /dev/ttyUSB0 --interactive
```

No console:

```text
PROFILE BASELINE
STATUS
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
PROFILE OBC-1U-LIMITED
STATUS
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
PROFILE BASELINE
OLED STANDBY
```

Resultado esperado:

- todos os comandos `MISSION` devem retornar `status=OK`;
- `result=DELIVERED`;
- `aead_match=1` e `tag_match=1` como alias de compatibilidade;
- `PQC` e `PQC_CRC32` devem ter `key_match=1`;
- `PQC_CRC32` deve ter `crc_match=1`;
- `elapsed_us` de `PQC` deve ser maior que `CLASSIC`;
- `elapsed_us` de `PQC_CRC32` deve ser maior ou próximo de `PQC`, com
  `crc_us` visível.

## 6. Bateria final robusta para novos resultados

A bateria usada como fonte atual da apresentação foi consolidada em
`logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`. Não rode outra
bateria durante o seminário.

Baterias longas não devem ser iniciadas pelo agente. Se a montagem física
mudar e for necessário repetir a coleta, o operador roda no terminal e depois
chama o agente para analisar o JSON.

Para consolidar um resultado novo e mais sólido para a seção `RESULTADOS` com
o fluxo atual, isto é, `MISSION` já cifrando payload com `AES-128-GCM`, use o
runner dedicado pós-AES:

```bash
python3 tools/aes_gcm_metrics_battery.py --port /dev/ttyUSB0 --timeout 12 --cycles 100 --pause 0.25 --bench-repeats 3 --bench-rounds 100
```

Esse comando executa, em `BASELINE` 240 MHz e `OBC-1U-LIMITED` 80 MHz:

- 100 ciclos por perfil;
- 300 `MISSION` por perfil, sendo 100 `CLASSIC`, 100 `PQC` e 100
  `PQC_CRC32`;
- todos os `MISSION` com o mesmo payload hexadecimal fixo, para evidenciar que
  `nonce_crc32`, `ciphertext_crc32` e `gcm_tag_crc32` mudam mesmo quando o
  plaintext é igual;
- 200 testes de falha por perfil, alternando `FAULT NONE` e `FAULT CRC32`;
- 3 execuções `PQC_BENCH 100` por perfil;
- validações específicas em `summary.aes_gcm`, incluindo `cipher=AES-128-GCM`,
  `nonce_bytes=12`, `gcm_tag_bytes=16`, `aead_match=1`, `decrypt_ok=1`,
  `tag_match=1` e contagem de duplicatas de `nonce_crc32`.

Resultado esperado no terminal:

```text
aes_gcm_metrics_json=logs/YYYYMMDDTHHMMSSZ_aes_gcm_metrics_dev-ttyusb0.json
summary={"aead_failures": 0, "failed": 0, "mission_runs": 600, "non_aes_gcm_records": 0, "official_candidate": true, ...}
```

Antes de iniciar a coleta real, confira o plano sem abrir a porta serial:

```bash
python3 tools/aes_gcm_metrics_battery.py --dry-run --cycles 100 --bench-repeats 3 --bench-rounds 100
```

Para uma coleta curta de validação antes da bateria longa:

```bash
python3 tools/aes_gcm_metrics_battery.py --port /dev/ttyUSB0 --timeout 12 --cycles 10 --pause 0.2 --bench-repeats 1 --bench-rounds 20
```

Depois que o JSON for gerado, chame o agente para consolidar o arquivo novo em
tabelas. Os campos principais para atualização da apresentação são:

- `summary.aes_gcm.checks.official_candidate`;
- `summary.aes_gcm.profiles.<perfil>.scenarios.<cenário>.encrypt_us`;
- `summary.aes_gcm.profiles.<perfil>.scenarios.<cenário>.decrypt_us`;
- `summary.aes_gcm.profiles.<perfil>.scenarios.<cenário>.nonce_crc32`;
- `summary.mission.<perfil>.ratios`;
- `summary.pqc_bench`;
- `summary.faults`.

O runner antigo abaixo continua útil como bateria geral, mas para os números
oficiais da versão cifrada prefira `tools/aes_gcm_metrics_battery.py`:

```bash
python3 tools/final_metrics_battery.py --port /dev/ttyUSB0 --timeout 12 --cycles 100 --pause 0.25 --bench-repeats 3 --bench-rounds 100
```

Esse comando executa, em `BASELINE` 240 MHz e `OBC-1U-LIMITED` 80 MHz:

- 100 ciclos por perfil;
- 300 `MISSION` por perfil, sendo 100 `CLASSIC`, 100 `PQC` e 100
  `PQC_CRC32`;
- 200 testes de falha por perfil, alternando `FAULT NONE` e `FAULT CRC32`;
- 3 execuções `PQC_BENCH 100` por perfil;
- `PQC_KAT`, `PQC_INFO`, `STATUS` e `TELEMETRY` como preflight/saúde.

Resultado esperado no terminal:

```text
final_metrics_json=logs/YYYYMMDDTHHMMSSZ_final_metrics_dev-ttyusb0.json
summary={"ok": true, "failed": 0, "mission_runs": 600, "pqc_bench_runs": 6, "fault_runs": 400, ...}
```

Se quiser uma coleta mais forte, mas mais demorada, use:

```bash
python3 tools/final_metrics_battery.py --port /dev/ttyUSB0 --timeout 12 --cycles 300 --pause 0.5 --bench-repeats 5 --bench-rounds 100
```

Resultado esperado:

```text
mission_runs=1800
pqc_bench_runs=10
fault_runs=1200
failed=0
ok=true
```

Antes de iniciar a coleta real, confira o plano sem abrir a porta serial:

```bash
python3 tools/final_metrics_battery.py --dry-run --cycles 100 --bench-repeats 3 --bench-rounds 100
```

Depois que o JSON for gerado, chame o agente para consolidar o arquivo novo em
tabelas. O campo principal para análise é `summary`, que já contém:

- estatísticas por perfil e cenário em `summary.mission`;
- razões `PQC/CLASSIC`, `PQC+CRC/CLASSIC` e overhead de CRC32;
- estatísticas de `PQC_BENCH` em `summary.pqc_bench`;
- contagem de falhas silenciosas/detectadas em `summary.faults`;
- lista dos comandos com falha em `summary.failed_commands`.

Use `tools/stage8_acceptance.py` apenas para aceite/regressão geral do firmware
FAIR atual. Para a conclusão estatística ECDH/ML-KEM, use
`tools/kex_metrics_battery.py`; a bateria AES-GCM anterior permanece histórica.

## 6.1. Aceite longo da etapa 8

Comando:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30
```

O runner usa `KEX_INFO`, `KEX_BENCH`, `MISSION ECDH|MLKEM` e
`SESSION_BENCH ECDH|MLKEM 1` nos dois perfis no smoke; o long-run repete as
operações FAIR em `BASELINE`. Depois da execução, procure no resumo:

```text
ok=true
failed=0
semantic_errors=[]
kex_bench_runs=2
fresh_mission_runs>=4
session_bench_runs>=4
```

Se os números mudarem, use o JSON novo como fonte principal e atualize
`../GUIA_FINAL_APRESENTACAO.md` e este documento. Execute os comandos deste
arquivo a partir da raiz do repositório.

## 7. O que não afirmar

Não afirmar:

- que `HMAC-SHA256` é equivalente a ECDH ou a uma pilha clássica completa;
- que o payload foi cifrado por ML-KEM;
- que ML-KEM substitui AES-GCM na cifragem do payload;
- que CRC32 é criptografia;
- que os efeitos de LED/bargraph medem energia;
- que o proxy `MHz * us` é consumo real em watts ou joules;
- que a Wisdom é um CubeSat real.

Afirmar:

- `CLASSIC` é um baseline clássico simétrico com AES-GCM e chave efêmera;
- `PQC` mede ML-KEM-512 para estabelecer chave e AES-GCM para cifrar;
- `PQC_CRC32` mede o acréscimo de checksum protegido sobre o fluxo PQC;
- a Wisdom representa um OBC COTS educacional sob perfil limitado;
- energia real exigiria medição elétrica externa.
