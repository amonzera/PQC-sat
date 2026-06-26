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
| `CLASSIC` | Mensagem cifrada/autenticada por `AES-128-GCM` com chave efêmera | `MISSION CLASSIC` |
| `PQC` | `ML-KEM-512` estabelece a chave; `AES-128-GCM` cifra o payload | `MISSION PQC` |
| `PQC_CRC32` | `ML-KEM-512` + `AES-GCM` + `CRC32` protegido no payload | `MISSION PQC_CRC32` |

A tese visual é:

```text
CLASSIC  -> menor custo, cifra clássica simétrica com chave efêmera
PQC      -> maior custo, preparo para ameaça quântica
PQC+CRC  -> maior robustez contra corrupção acidental, com custo adicional
```

> Estado dos números: a bateria consolidada registrada neste arquivo foi
> coletada antes da inclusão de AES-128-GCM no fluxo `MISSION`. Ela continua
> útil como histórico metodológico e comparação pré-AES, mas a versão atual
> exige uma nova bateria para gerar os números oficiais finais.

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

## 4.5. Resultados reais consolidados

Fonte principal:

```text
logs/20260625T005330Z_final_metrics_dev-ttyusb0.json
```

Coleta final: 3.074 registros, 0 falhas, 1.800 `MISSION runs`, 10
`PQC_BENCH` de 100 rounds, 1.200 testes `FAULT`, duracao 1.681,24 s.

Configuração:

- 300 ciclos por perfil;
- 300 amostras por cenário em `BASELINE` 240 MHz;
- 300 amostras por cenário em `OBC-1U-LIMITED` 80 MHz;
- 5 execuções `PQC_BENCH 100` por perfil;
- 300 `FAULT NONE` e 300 `FAULT CRC32` por perfil.

### MISSION — BASELINE (240 MHz, 300 amostras por cenário)

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

### MISSION — OBC-1U-LIMITED (80 MHz, 300 amostras por cenário)

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

### Razoes observadas

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

### PQC_BENCH (100 rounds)

| Perfil | CPU | Runs | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|---:|---:|
| BASELINE | 240 MHz | 5 | 3.302 | 3.866 | 4.990 |
| OBC-1U-LIMITED | 80 MHz | 5 | 10.066 | 11.787 | 15.217 |

Fator de desaceleracao 80/240 MHz: keygen ~3,0x, encap ~3,0x, decap ~3,0x.

### Testes de segurança

| Teste | Resultado |
|---|---|
| PQC_KAT | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| PQC_FAULT 0 0x01 CONFIRM | `PROTOCOL_REJECT`, `key_match=0` |
| PQC_FAULT 0 0x01 NONE | `KEY_MISMATCH`, `key_match=0` |
| FAULT NONE (coleta final) | 600/600 `SILENT` |
| FAULT CRC32 (coleta final) | 600/600 `DETECTED_GUARD` |

### Falhas de payload na coleta final

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
2. O custo temporal de PQC e o resultado mais forte: `PQC` foi 25,9x mais
   lento que `CLASSIC` a 240 MHz e 34,1x mais lento no perfil limitado de
   80 MHz.
3. O custo de trafego também é didático: `PQC` saiu de 73 bytes para 841
   bytes por entrega consolidada.
4. CRC32 adicionou custo pequeno no payload (+4 bytes e ~10 us a 240 MHz), mas
   tornou visível a diferença entre falha silenciosa e erro detectado:
   600/600 `SILENT` sem CRC32 contra 600/600 `DETECTED_GUARD` com CRC32.
5. A RAM livre permaneceu estável, então a evidencia principal desta versão e
   tempo/trafego, não exaustao de heap.

### Próximos passos reais

Para o seminário atual:

- usar o botão `RESULTADOS` do dashboard como resumo final da bateria;
- usar `STRESS PQC 500` apenas como fechamento opcional de impacto visual;
- não rodar bateria longa durante a apresentação;
- demonstrar manualmente `CLÁSSICA`, `PQC`, `PQC+CRC`, `ENVIAR MSG` e
  `FALHA`;
- citar `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json` como fonte
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

A bateria longa usada como fonte atual da apresentação foi realizada e
consolidada em `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`. Não
rode outra bateria durante o seminário.

Baterias longas não devem ser iniciadas pelo agente. Se a montagem física
mudar e for necessário repetir a coleta, o operador roda no terminal e depois
chama o agente para analisar o JSON.

Para consolidar um resultado novo e mais sólido para a seção `RESULTADOS`, use
o runner dedicado:

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
métricas finais da apresentação, prefira `tools/final_metrics_battery.py`.

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
`APRESENTACAO_ROTEIRO.md`, `GUIA_DIDATICO_APRESENTACAO.md` e este documento.

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
