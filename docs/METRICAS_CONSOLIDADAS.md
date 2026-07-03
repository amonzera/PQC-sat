# Métricas consolidadas da apresentação - PQC-SAT

Este documento define como medir e apresentar o impacto de segurança e
desempenho no hardware limitado usado como OBC educacional. Ele é a referência
para consolidar os resultados do seminário.

## 1. Objetivo atual do seminário

O projeto deve mostrar como a migração para criptografia pós-quântica altera os
custos de processamento, comunicação e memória em hardware embarcado. Não se
presume que ML-KEM seja mais lento que toda implementação clássica: a conclusão
deve vir das medições da mesma placa, build e frequência.

A apresentação deve comparar três cenários de entrega de uma mensagem curta:

| Cenário | O que representa | Comando |
|---|---|---|
| `CLASSIC` | `ECDH P-256` efêmero estabelece a chave; `AES-128-GCM` cifra o payload | `MISSION CLASSIC` |
| `PQC` | `ML-KEM-512` estabelece a chave; `AES-128-GCM` cifra o payload | `MISSION PQC` |
| `PQC_CRC32` | `ML-KEM-512` + `AES-GCM` + `CRC32` protegido no payload | `MISSION PQC_CRC32` |

A tese visual é:

```text
CLASSIC  -> ECDH P-256 clássico para chave + AES-GCM
PQC      -> custo diferente de CPU, comunicação e memória; preparo para ameaça quântica
PQC+CRC  -> robustez diagnóstica contra corrupção acidental, com custo adicional
```

> Estado dos números: `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`
> é histórico pré-ECDH. Uma nova bateria na placa é obrigatória antes de
> promover números da comparação ECDH P-256 versus ML-KEM-512.

## 2. O que a placa realmente faz

O comando `MISSION` roda na BlackBoard Wisdom/ESP32 e mede a entrega de uma
mensagem de missão.

Na demo ao vivo, o dashboard pode acionar o modo `Payload vivo`: antes de
`MISSION`, ele lê sensores da Wisdom, monta um payload ASCII compacto, converte
para hexadecimal e envia `MISSION <cenario> <payload_hex>`. Isso torna a
apresentação mais fiel a uma telemetria de CubeSat. A bateria consolidada
abaixo continua sendo a fonte estatística oficial e usa campanhas balanceadas
com payload padronizado; portanto, compare os resultados consolidados entre
cenários e use o payload vivo como demonstração imersiva do mesmo fluxo.

O comando `STRESS PQC_LOOP 500 CONFIRM`, acionado pelo botão protegido
`STRESS PQC 500` dentro de `RESULTADOS`, é uma demonstração visual de limite:
ele repete ML-KEM 500 vezes para evidenciar espera, carga e consumo relativo.
Ele não substitui a bateria consolidada abaixo e não deve ser usado para mudar
as conclusões estatísticas oficiais da apresentação.

### `MISSION CLASSIC`

Fluxo:

1. a placa pega o payload padrão `PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK`;
2. gera dois pares ECDH P-256 efêmeros, um para cada ponta lógica;
3. transmite/contabiliza a chave pública não comprimida do emissor (65 B);
4. calcula e compara o segredo compartilhado nas duas pontas;
5. deriva a chave AES-128, gera nonce e executa AES-GCM;
6. retorna tempos ECDH/AES, bytes, heap e resultado.

Esse cenário é a pilha clássica equivalente usada para comparar o
estabelecimento de chave ECDH com ML-KEM.

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

## 2.1. Benchmark de sessão comparável a produção

`MISSION` continua sendo o fluxo visual de uma mensagem. Para comparar
estabelecimento clássico e pós-quântico sem gerar chaves a cada payload, use:

```text
SESSION_BENCH ECDH_P256|X25519|MLKEM512 1|100|500|1000
```

O comando força `BASELINE` a 240 MHz, desliga os rádios e só escreve na serial
depois das regiões cronometradas. Cada amostra faz um setup real, deriva a
chave AES uma vez e reutiliza a sessão para N mensagens com nonces únicos:

```text
ECDH: KeyGen receptor + KeyGen emissor + dois shared secrets + duas KDF
ML-KEM: KeyGen receptor + Encaps emissor + Decaps receptor + duas KDF
dados: N x (AES-GCM encrypt + AES-GCM decrypt)
```

P-256 usa chaves públicas não comprimidas de 65 B. No handshake completo são
contabilizadas as duas chaves públicas, totalizando 130 B. X25519 usa duas
chaves de 32 B, totalizando 64 B. ML-KEM-512 contabiliza a chave pública de
800 B e o ciphertext de 768 B, totalizando 1.568 B. Certificados, transporte e
autenticação de identidade permanecem fora do escopo nos três casos.

As métricas não confundem CPU agregada com latência:

| Campo | Interpretação |
|---|---|
| `sender_setup_us`, `receiver_setup_us` | Trabalho medido em cada papel lógico. |
| `algorithm_init_us` | Inicialização do grupo ECDH; zero para o backend ML-KEM já ligado estaticamente. |
| `aggregate_setup_us` | Todo o trabalho de setup executado sequencialmente na única placa. |
| `critical_latency_us` / `setup_session_us` | Caminho causal modelado com endpoints paralelos e rede zero; não é a soma cega das pontas. |
| `data_total_us` | Encrypt + decrypt de N mensagens, com validação real. |
| `nonce_setup_us` | Geração do prefixo aleatório do nonce uma vez por sessão; o contador garante nonce único por mensagem. |
| `total_us` | Caminho crítico de setup + entrega dos dados. |
| `aggregate_total_us` | CPU agregada de setup + dados. |
| `amortized_us` | `total_us / N`, calculado com precisão no runner host. |
| `handshake_bytes` | Material de handshake efetivamente contabilizado acima. |
| `principal_crypto_buffers_bytes` | Buffers principais explícitos; não inclui todas as alocações internas da biblioteca. |
| `min_heap_after` | Watermark global de heap desde o boot; não é resetável por amostra. |

O Mbed TLS fornecido pelo framework ESP32 está pré-compilado em otimização de
tamanho (`-Os`) e tem `HARDWARE_MPI`, `HARDWARE_AES`, `HARDWARE_SHA`,
`ECP_NIST_OPTIM`, fixed-point ECP, P-256 e Curve25519 ativos. O código do
projeto e `mlkem-native` usam Release `-O2`. Não atribua `-O2` à biblioteca
Mbed TLS pré-compilada.

Conclusão metodológica esperada, sem impor o vencedor antes da coleta:

> O custo pós-quântico não deve ser analisado apenas por tempo bruto de CPU.
> Nesta plataforma, dependendo da biblioteca, ML-KEM pode ser mais rápido em
> processamento que ECDH P-256. Porém, ML-KEM possui maior custo de
> comunicação, artefatos criptográficos maiores e possível maior uso de
> memória. Em produção, o handshake deve ser amortizado por várias mensagens
> AES-GCM.

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
| `keygen_us` | Custo de preparar P-256, gerar dois pares ECDH e serializar a chave pública, ou gerar o par ML-KEM. |
| `encap_us` | Custo de encapsulamento ML-KEM; zero no cenário clássico. |
| `decap_us` | Custo de decapsulação ML-KEM; zero no cenário clássico. |
| `ecdh_tx_us` / `ecdh_rx_us` | Cálculo do segredo ECDH em cada ponta; zero em PQC. |
| `rng_us` | Custo do nonce aleatório fora das gerações de chave medidas. |
| `kdf_us` | Custo de derivar chave AES a partir do segredo ECDH ou ML-KEM. |
| `encrypt_us` / `tag_us` | Custo de cifrar e gerar tag AES-GCM (`tag_us` fica como alias histórico). |
| `decrypt_us` / `verify_us` | Custo de decifrar/verificar AES-GCM (`verify_us` fica como alias histórico). |
| `crc_us` | Custo do CRC32; zero quando checksum está desligado. |
| `bytes_total` | Tamanho relativo transmitido para a entrega da mensagem. |
| `heap` / `min_heap` | RAM livre e menor RAM livre observada na amostra. |
| `cpu_mhz` | Frequência do perfil ativo. |
| `profile` | `BASELINE` ou `OBC-1U-LIMITED`. |
| `key_match` | Se os segredos das duas pontas bateram em ECDH ou ML-KEM. |
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

## 4. Métricas visíveis no dashboard

A faixa superior da animação mostra:

- `CPU`: frequência e porcentagem ativa observada em janela móvel de 5s;
- `RAM`: consumo atual de heap / total disponível (célula de memória) e memória livre como detalhe.

As métricas de tempo e tráfego de cada cenário (`CLÁSSICA`, `PQC`, `PQC+CRC`) são exibidas diretamente no log do console do painel lateral assim que a mensagem é processada/recebida.

Quando um comando `MISSION` volta da placa, o dashboard mostra um overlay de
mensagem entregue, com cenário, criptografia, checksum, tempo e tráfego. Os
LEDs/bargraph da Wisdom também são usados como reforço lúdico:

| Cenário | Efeito visual |
|---|---|
| `CLASSIC` | Bargraph em 25% e LED azul. |
| `PQC` | Bargraph em 75% e LED magenta. |
| `PQC_CRC32` | Bargraph em 100% e LED verde. |

Esses efeitos não são métricas científicas; são apoio visual para a turma
perceber o crescimento de custo.

## 4.5. Resultados históricos pré-ECDH

Fonte histórica preservada para rastreabilidade:

```text
logs/20260702T044907Z_final_metrics_dev-ttyusb0.json
```

Essa foi a bateria oficial AES-GCM anterior ao ECDH. Embora tenha
sido produzida pelo runner geral, a validação foi recalculada diretamente dos
600 registros `MISSION`: todos retornaram `cipher=AES-128-GCM`,
`nonce_bytes=12`, `gcm_tag_bytes=16`, `aead_match=1` e `decrypt_ok=1`.

Resumo da bateria histórica:

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

Razões históricas observadas na bateria AES-GCM sem ECDH:

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
  passa a ser payload cifrado + chave pública ECDH do emissor ou ciphertext
  ML-KEM + nonce + tag GCM. A chave pública do receptor não é somada em
  `bytes_total`, igualmente nos dois modelos.
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

### Conclusões históricas pré-ECDH

1. O objetivo principal foi atingido: a Wisdom/ESP32 executou ML-KEM-512 real,
   entregou mensagens nos três cenários e exportou métricas de tempo, bytes e
   heap.
2. Na bateria histórica pré-ECDH, `PQC` foi 23,2x mais lento que `CLASSIC` a
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
- citar `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json` apenas como
  histórico pré-ECDH até a nova bateria ser consolidada.

Para evolucao cientifica futura:

- medir energia real com instrumento externo, porque `MHz * us` não é watts;
- executar ECDH e ML-KEM entre duas placas com autenticação das chaves públicas;
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
- não existe requisito de que `PQC` seja mais lento que `CLASSIC`;
- diferenças de tempo devem ser reportadas mesmo quando ML-KEM for mais rápido;
- `PQC_CRC32` deve manter `crc_us` visível, sem exigir ordenação rígida entre
  duas amostras sujeitas a ruído.

## 6. Bateria final robusta para novos resultados

Para a comparação justa de sessão ECDH/ML-KEM, a fonte primária é:

```bash
python3 tools/session_benchmark.py --port /dev/ttyUSB0 --timeout 20 --repeats 10 --pause 0.25
```

Ela gera 120 amostras balanceadas: três algoritmos, quatro contagens de
mensagens e dez repetições. A ordem é rotacionada e toda amostra precisa ter
`profile=BASELINE`, `cpu_mhz=240`, `build_opt=O2`, `key_match=1` e
`aead_match=1`. O arquivo esperado é:

```text
logs/<timestamp>_session_benchmark_dev-ttyusb0.json
summary.ok=true
summary.session_runs=120
summary.invalid_session_runs=0
```

Confira o plano sem abrir a porta com
`python3 tools/session_benchmark.py --dry-run --repeats 10`. A tabela impressa
usa medianas e inclui setup crítico, AES-GCM médio, N, amortização, handshake,
watermark global de heap e flash. Os p95 e dados brutos ficam no JSON.

A bateria abaixo permanece necessária para regressão do fluxo visual,
AES-GCM, CRC32 e comparação entre perfis. Ela não substitui o benchmark de
sessão para afirmar latência de produção.

A bateria `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json` é histórica
pré-ECDH. A nova fonte da apresentação será a primeira coleta oficial que
passar nas validações ECDH/ML-KEM.

Baterias longas não devem ser iniciadas pelo agente. Se a montagem física
mudar e for necessário repetir a coleta, o operador roda no terminal e depois
chama o agente para analisar o JSON.

Para consolidar a seção `RESULTADOS` com ECDH P-256 versus ML-KEM-512, use o
runner dedicado:

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
  `tag_match=1`, `ecdh_invalid_records=0`, `pqc_invalid_records=0`, cenários
  balanceados e contagem de duplicatas de `nonce_crc32`.

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

```bash
python3 tools/consolidate_metrics.py --file logs/<timestamp>_aes_gcm_metrics_dev-ttyusb0.json
```

O consolidador só promove a coleta se `official_candidate=true`,
`ecdh_invalid_records=0`, `pqc_invalid_records=0` e os cenários estiverem
balanceados; o dashboard lê `logs/metrics_consolidated.json`.

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

Use `tools/stage8_acceptance.py` apenas para aceite/regressão geral. Para
métricas finais da apresentação ECDH/ML-KEM, prefira
`tools/aes_gcm_metrics_battery.py`.

## 6.1. Aceite longo da etapa 8

Comando:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30
```

O runner agora inclui `MISSION CLASSIC`, `MISSION PQC` e `MISSION PQC_CRC32`
no smoke test e no long-run. Depois da execução, procure no resumo:

```text
ok=true
failed=0
dashboard_demo_ok=true
pqc_bench_runs=2
mission_runs>=6
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

- `CLASSIC` usa ECDH P-256 efêmero para estabelecer a chave e AES-GCM para o payload;
- `PQC` mede ML-KEM-512 para estabelecer chave e AES-GCM para cifrar;
- `PQC_CRC32` mede o acréscimo de checksum protegido sobre o fluxo PQC;
- a Wisdom representa um OBC COTS educacional sob perfil limitado;
- energia real exigiria medição elétrica externa.
