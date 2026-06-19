# Métricas consolidadas da apresentação - PQC-SAT

Este documento define como medir e apresentar o impacto de segurança e
desempenho no hardware limitado usado como OBC educacional. Ele é a referência
para consolidar os resultados do seminário.

## 1. Objetivo atual do seminário

O projeto deve mostrar que a migração para criptografia pós-quântica aumenta o
custo operacional em hardware embarcado e que esse custo cresce quando também
exigimos mecanismos explícitos de integridade.

A apresentação deve comparar três cenários de entrega de uma mensagem curta:

| Cenário | O que representa | Comando |
|---|---|---|
| `CLASSIC` | Mensagem autenticada por criptografia clássica simétrica (`HMAC-SHA256`) | `MISSION CLASSIC` |
| `PQC` | Mensagem autenticada após acordo de segredo com `ML-KEM-512` | `MISSION PQC` |
| `PQC_CRC32` | `ML-KEM-512` mais guardião `CRC32` no payload | `MISSION PQC_CRC32` |

A tese visual é:

```text
CLASSIC  -> menor custo, segurança clássica
PQC      -> maior custo, preparo para ameaça quântica
PQC+CRC  -> maior robustez de integridade, com custo adicional
```

## 2. O que a placa realmente faz

O comando `MISSION` roda na BlackBoard Wisdom/ESP32 e mede a entrega de uma
mensagem de missão.

### `MISSION CLASSIC`

Fluxo:

1. a placa pega o payload padrão `PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK`;
2. calcula uma tag `HMAC-SHA256` com chave simétrica didática fixa;
3. recalcula a tag como se fosse o receptor;
4. compara as tags em tempo constante;
5. retorna tempo, bytes, heap e resultado.

Esse cenário não executa PQC. Ele é o baseline clássico simétrico de mensagem
autenticada.

### `MISSION PQC`

Fluxo:

1. a placa gera um par `ML-KEM-512`;
2. encapsula um segredo;
3. decapsula o ciphertext;
4. compara se os dois lados chegaram ao mesmo segredo;
5. usa o segredo derivado para autenticar a mensagem com `HMAC-SHA256`;
6. retorna tempo, bytes, heap e resultado.

Esse cenário demonstra o custo de introduzir PQC na sessão.

### `MISSION PQC_CRC32`

Fluxo:

1. executa o mesmo caminho do `MISSION PQC`;
2. calcula também `CRC32` do payload;
3. verifica se o CRC recebido bate com o CRC transmitido;
4. retorna o custo adicional do checksum.

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
| `tag_us` | Custo para autenticar a mensagem. |
| `verify_us` | Custo para verificar a autenticação. |
| `crc_us` | Custo do CRC32; zero quando checksum está desligado. |
| `bytes_total` | Tamanho relativo transmitido para a entrega da mensagem. |
| `heap` / `min_heap` | RAM livre e menor RAM livre observada na amostra. |
| `cpu_mhz` | Frequência do perfil ativo. |
| `profile` | `BASELINE` ou `OBC-1U-LIMITED`. |
| `key_match` | Se os segredos ML-KEM bateram. |
| `tag_match` | Se a mensagem autenticada foi aceita. |
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

- `CPU`: frequência e porcentagem ativa observada em janela curta;
- `RAM`: heap livre e mínimo observado;
- `CLÁSSICA`: tempo e bytes do último `MISSION CLASSIC`;
- `PQC`: tempo e bytes do último `MISSION PQC`;
- `PQC+CRC`: tempo e bytes do último `MISSION PQC_CRC32`.

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

## 4.5. Resultados reais consolidados

Fonte principal:

```text
logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json
```

Aceite final: 83 registros, 0 falhas, 27 MISSION runs, 2 PQC_BENCH (100 rounds
cada), demo A/B headless OK, duracao 1.817,23 s.

### MISSION — BASELINE (240 MHz, 8 amostras)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` (avg) | 721 | 13.536 | 13.367 |
| `elapsed_us` (min) | 681 | 13.211 | 13.110 |
| `elapsed_us` (max) | 773 | 13.813 | 14.114 |
| `elapsed_us` (stdev) | 33 | 174 | 454 |
| `keygen_us` (avg) | 0 | 3.923 | 3.679 |
| `encap_us` (avg) | 0 | 3.975 | 3.988 |
| `decap_us` (avg) | 0 | 5.026 | 5.087 |
| `tag_us` (avg) | 528 | 421 | 435 |
| `verify_us` (avg) | 166 | 165 | 163 |
| `crc_us` (avg) | 0 | 0 | 10 |
| `bytes_total` | 73 | 841 | 845 |
| `heap` | 201.412 | 201.412 | 201.412 |
| `min_heap` | 197.624 | 197.624 | 197.624 |
| `result` | DELIVERED | DELIVERED | DELIVERED |
| `key_match` | 1 (100%) | 1 (100%) | 1 (100%) |
| `tag_match` | 1 (100%) | 1 (100%) | 1 (100%) |
| `crc_match` | 1 (100%) | 1 (100%) | 1 (100%) |

### MISSION — OBC-1U-LIMITED (80 MHz, 1 amostra)

| Campo | CLASSIC | PQC | PQC_CRC32 |
|---|---:|---:|---:|
| `elapsed_us` | 1.283 | 38.646 | 38.647 |
| `keygen_us` | 0 | 10.411 | 10.360 |
| `encap_us` | 0 | 11.821 | 11.793 |
| `decap_us` | 0 | 15.197 | 15.231 |
| `tag_us` | 794 | 738 | 723 |
| `verify_us` | 465 | 465 | 491 |
| `crc_us` | 0 | 0 | 30 |
| `bytes_total` | 73 | 841 | 845 |
| `heap` | 201.412 | 201.412 | 201.412 |
| `result` | DELIVERED | DELIVERED | DELIVERED |

### Razoes observadas

| Comparacao | Tempo | Bytes |
|---|---:|---:|
| PQC / CLASSIC (BASELINE) | 18,8x | 11,5x |
| PQC_CRC32 / CLASSIC (BASELINE) | 18,5x | 11,6x |
| PQC / CLASSIC (OBC-1U-LIMITED) | 30,1x | 11,5x |
| PQC_CRC32 / CLASSIC (OBC-1U-LIMITED) | 30,1x | 11,6x |
| CRC32 custo adicional sobre PQC (BASELINE) | ~10 us | +4 bytes |
| CRC32 custo adicional sobre PQC (OBC-1U-LIMITED) | ~30 us | +4 bytes |

Leitura didatica:

- A 240 MHz, PQC custa quase 19 vezes mais tempo que o baseline classico.
- A 80 MHz, a mesma operacao PQC custa 30 vezes mais, porque o ML-KEM sofre
  mais com CPU reduzida do que o HMAC puro.
- O CRC32 adiciona custo negligivel (~10 us a 240 MHz, ~30 us a 80 MHz),
  mostrando que verificacao de integridade no payload e barata.
- O trafego PQC e 11,5x maior que o classico porque inclui chave publica
  (800 bytes) e ciphertext (768 bytes).
- A heap permaneceu constante em todos os cenarios: a criptografia PQC nao
  causou fragmentacao perceptivel nos testes.

### PQC_BENCH (100 rounds)

| Perfil | CPU | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|---:|
| BASELINE | 240 MHz | 3.298 | 3.861 | 4.985 |
| OBC-1U-LIMITED | 80 MHz | 10.056 | 11.780 | 15.204 |

Fator de desaceleracao 80/240 MHz: keygen ~3,0x, encap ~3,1x, decap ~3,0x.

### Testes de seguranca

| Teste | Resultado |
|---|---|
| PQC_KAT | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| PQC_FAULT 0 0x01 CONFIRM | `PROTOCOL_REJECT`, `key_match=0` |
| PQC_FAULT 0 0x01 NONE | `KEY_MISMATCH`, `key_match=0` |
| FAULT CRC32 (aceite) | 8/8 `DETECTED_GUARD` |

### Demo A/B

| Cenario | Resultado |
|---|---|
| A, sem CRC32 | 5/5 falhas silenciosas |
| B, com CRC32 | 5/5 falhas detectadas |

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
- `tag_match=1`;
- `PQC` e `PQC_CRC32` devem ter `key_match=1`;
- `PQC_CRC32` deve ter `crc_match=1`;
- `elapsed_us` de `PQC` deve ser maior que `CLASSIC`;
- `elapsed_us` de `PQC_CRC32` deve ser maior ou próximo de `PQC`, com
  `crc_us` visível.

## 6. Coleta longa antes da apresentação

Baterias longas não devem ser iniciadas pelo agente. O operador roda no
terminal e depois chama o agente para analisar o JSON.

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
`APRESENTACAO_ROTEIRO.md`, `GUIA_DIDATICO_APRESENTACAO.md` e este documento.

## 7. O que não afirmar

Não afirmar:

- que `HMAC-SHA256` é equivalente a ECDH ou a uma pilha clássica completa;
- que o payload foi cifrado por ML-KEM;
- que CRC32 é criptografia;
- que os efeitos de LED/bargraph medem energia;
- que o proxy `MHz * us` é consumo real em watts ou joules;
- que a Wisdom é um CubeSat real.

Afirmar:

- `CLASSIC` é um baseline clássico simétrico de mensagem autenticada;
- `PQC` mede o custo de estabelecer segredo com `ML-KEM-512`;
- `PQC_CRC32` mede o acréscimo de checksum sobre o fluxo PQC;
- a Wisdom representa um OBC COTS educacional sob perfil limitado;
- energia real exigiria medição elétrica externa.
