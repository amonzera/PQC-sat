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
