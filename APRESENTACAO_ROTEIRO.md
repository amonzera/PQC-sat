# Roteiro de apresentação - PQC-SAT

Objetivo do seminário: mostrar, em 20 minutos, que a transição para
criptografia pós-quântica aumenta a demanda de hardware em sistemas
embarcados, e que a demanda cresce ainda mais quando adicionamos mecanismos de
integridade como checksum.

## Mensagem central

O ESP32/Wisdom representa um OBC COTS educacional inspirado em CubeSat. A
demonstração principal envia uma mensagem curta em três cenários:

- **CLASSIC**: mensagem autenticada com HMAC-SHA256;
- **PQC**: mensagem autenticada depois de acordo de segredo com ML-KEM-512;
- **PQC+CRC**: o mesmo fluxo PQC com CRC32 adicional no payload.

A parte de bit-flip continua como apoio visual para consistência: sem
guardião, a corrupção vira falha silenciosa; com CRC32, a mesma alteração é
detectada. Quando o bit-flip atinge ciphertext ML-KEM, a decapsulação não
"detecta" sozinha a falha: o harness observa `KEY_MISMATCH`, e a confirmação
HMAC-SHA256 transforma divergência de chave em `PROTOCOL_REJECT`.

## Cinco blocos narrativos no dashboard

1. **Problema**: CubeSats usam COTS; falhas transitórias podem inverter bits.
2. **Experimento**: Wisdom + notebook, mensagem de missão, ML-KEM-512,
   HMAC-SHA256, CRC32 e bit-flip manual.
3. **Demo visual**: enviar `CLASSIC`, `PQC` e `PQC+CRC`; depois mostrar
   falha silenciosa versus detecção por CRC32.
4. **Resultados medidos**: tempos, bytes, heap, benchmark PQC, falha ML-KEM
   com confirmação e campanha de aceite.
5. **Conclusão e limites**: PQC aumenta custo, checksum soma integridade, e
   energia real exigiria medidor externo.

Esses blocos aparecem no onboarding e no botão `RESULTADOS`; não há dependência
de slides externos para conduzir a apresentação.

## Resultados para apresentar

Fonte principal: `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`.

| Medida | Resultado |
|---|---|
| Coleta final | 1.681,24 s, 3.074 registros, 0 falhas |
| MISSION runs | 1.800 (600 CLASSIC, 600 PQC, 600 PQC_CRC32) |
| Falhas sem CRC32 | 600/600 `SILENT` |
| Falhas com CRC32 | 600/600 `DETECTED_GUARD` |
| `PQC_KAT` | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| `PQC_FAULT CONFIRM` | `PROTOCOL_REJECT`, `confirmation=HMAC-SHA256` |
| `PQC_FAULT NONE` | `KEY_MISMATCH` |

| Perfil | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|
| `BASELINE` 240 MHz | 3.302 | 3.866 | 4.990 |
| `OBC-1U-LIMITED` 80 MHz | 10.066 | 11.787 | 15.217 |

Leitura didática: limitar o ESP32 para 80 MHz aumenta o custo temporal do
ML-KEM-512, mas a operação continua funcional. O custo de checksum no payload
é baixo e suficiente para demonstrar a diferença entre falha silenciosa e erro
detectado.

Comparacao MISSION BASELINE (240 MHz, media de 300 amostras por cenário):

| Cenário | Tempo total (us) | Bytes | Heap livre | Resultado |
|---|---:|---:|---:|---|
| `CLASSIC` | 511 | 73 | 201.412 | DELIVERED |
| `PQC` | 13.234 | 841 | 201.412 | DELIVERED |
| `PQC_CRC32` | 13.130 | 845 | 201.412 | DELIVERED |

Razoes: PQC é 25,9x mais lento e 11,5x maior que CLASSIC.
CRC32 adiciona ~10 us e +4 bytes sobre PQC.

Conclusões:

- ML-KEM-512 real funciona na Wisdom, mas consome muito mais tempo que o
  baseline simetrico.
- O custo de trafego também cresce: 73 bytes em `CLASSIC` contra 841 bytes em
  `PQC`.
- CRC32 tem baixo custo no payload e é excelente para explicar falha silenciosa
  versus erro detectado.
- A heap ficou estável, então a apresentação deve enfatizar tempo, trafego e
  comportamento de integridade.

Próximos passos:

- medir energia real com instrumento externo;
- comparar contra uma pilha clássica assimetrica completa, como ECDH + HMAC;
- repetir a coleta com payloads maiores e perfis de clock adicionais;
- testar bursts de bit-flips, não apenas single-bit controlado.

## Sequência da demo

Regra da apresentação: **não usar replay para envio de mensagens**. O botão
`ENVIAR MSG` deve produzir métricas apenas quando a Wisdom estiver conectada e
respondendo pela serial. Sem `SAT CONECTADO`, o painel deve recusar o envio.

1. Abrir em modo hardware:
   `python3 dashboard.py --port /dev/ttyUSB0`
2. Esperar o canto superior indicar `SAT CONECTADO`. Se aparecer `AGUARDANDO
   SAT`, não prosseguir com a demo de mensagens.
3. Enviar mensagem em modo clássico:
   - Clique em `CLÁSSICA` (o botão fica azul) e em seguida clique em `ENVIAR MSG`.
   - Mantenha o popup aberto e destaque tempo total, bytes, tag e heap.
   - Feche no `X`.
4. Enviar mensagem em modo pós-quântico (PQC) sem integridade:
   - Clique em `PQC` (o botão fica roxo).
   - Clique em `ENVIAR MSG`.
   - Mantenha o popup aberto e destaque `keygen`, `encap`, `decap`, bytes e heap.
   - Feche no `X`.
5. Enviar mensagem em modo pós-quântico (PQC) com integridade:
   - Clique em `PQC+CRC` (o botão fica verde).
   - Clique em `ENVIAR MSG`.
   - Mantenha o popup aberto e destaque o campo `crc`, +4 bytes e validações.
   - Feche no `X`.
6. Apoio visual de falhas transitórias (Bit-Flips) de forma manual:
   - **Caso A (Corrupção Silenciosa):** Clique em `PQC`, depois em `FALHA` -> Observar erro silencioso (`SILENT` na timeline).
   - **Caso B (Erro Detectado):** Clique em `PQC+CRC`, depois em `FALHA` -> Observar detecção do erro pelo guardião (`DETECTED_GUARD` na timeline).
7. Fechar com resultados consolidados:
   - Clique em `RESULTADOS`.
   - Mostre a bateria real: 3.074 registros, 0 falhas, 1.800 `MISSION runs`.
   - Compare `CLASSIC`, `PQC` e `PQC_CRC32` com os números finais.

> [!NOTE]
> Todos os logs oficiais e dados numéricos consolidados foram gravados através de baterias automatizadas de longa duração via terminal (como o script `tools/stage8_acceptance.py`), garantindo rigor científico sem poluir o dashboard visual.

O painel de botões do dashboard agora é puramente manual e focado no roteiro interativo acima. Comandos técnicos adicionais ficam no HELP/terminal ou no console serial.
Cada cenário de mensagem abre seu próprio popup de métricas. Durante a comparação,
mantenha `CLASSIC`, `PQC` e `PQC+CRC` abertos, arraste os cartões pelo topo e
posicione-os lado a lado; feche cada um apenas pelo `X` depois de comparar tempo,
bytes, heap e etapas ML-KEM/HMAC/CRC.

## Sequência impactante para alunos de Ciência da Computação

### 1. Introdução curta (2-4 min)

Pergunta de abertura:

> O que acontece quando um sistema embarcado pequeno precisa migrar para
> criptografia pós-quântica e ainda detectar corrupção de dados?

Conduza a turma por três ideias:

- **restrição de hardware**: CPU, RAM, tráfego e energia são recursos críticos
  em sistemas inspirados em CubeSat;
- **mudança criptográfica**: HMAC simétrico é barato, mas acordo de segredo
  pós-quântico exige operações mais pesadas;
- **integridade operacional**: bit-flip sem guardião pode virar falha
  silenciosa; com CRC32, a corrupção do payload fica visível.

### 2. Demonstração ao vivo (8-10 min)

Use apenas a placa conectada. Não use `--simulated` para a apresentação final.

1. Mostre `SAT CONECTADO`, CPU/RAM no topo e explique que o dashboard está
   conversando com a Wisdom.
   Antes de enviar qualquer mensagem, pergunte: "O que vocês acham que vai
   crescer mais: tempo de CPU, bytes transmitidos ou RAM?"
2. Clique `CLÁSSICA` -> `ENVIAR MSG`.
   Fala: “Este é o baseline: autenticação simétrica com HMAC-SHA256.”
3. Clique `PQC` -> `ENVIAR MSG`.
   Fala: “Agora o mesmo envio inclui ML-KEM-512. Observem `keygen`, `encap` e
   `decap`: o custo não está na animação, está no hardware.”
4. Clique `PQC+CRC` -> `ENVIAR MSG`.
   Fala: “Agora somamos um guardião simples de integridade no payload. O custo
   em bytes e tempo aparece junto com a validação.”
   Arraste os três popups lado a lado e use o comparador ao vivo para destacar
   payload, HMAC, ciphertext ML-KEM e CRC32.
5. Clique `PQC` -> `FALHA`.
   Fala: “Sem guardião no payload, uma mutação pode passar silenciosamente.”
6. Clique `PQC+CRC` -> `FALHA`.
   Fala: “Com CRC32, o mesmo tipo de corrupção vira evento detectado.”

Opcional para público mais técnico, se houver tempo:

```text
PQC_FAULT 0 0x01 CONFIRM
```

Use esse comando apenas no terminal textual para mostrar que, quando o
ciphertext ML-KEM é corrompido, a detecção operacional vem da confirmação de
chave (`PROTOCOL_REJECT`), não de uma “mágica” automática da decapsulação.

### 3. Resultados finais comparados (4-6 min)

Clique `RESULTADOS` e feche a narrativa:

- `CLASSIC`: 511 us, 73 bytes;
- `PQC`: 13.234 us, 841 bytes;
- `PQC_CRC32`: 13.130 us, 845 bytes;
- PQC ficou 25,9x mais lento e 11,5x maior em bytes que o baseline;
- a bateria teve 3.074 registros, 0 falhas, 1.800 envios de missão e 10
  benchmarks PQC;
- falhas de payload: 600/600 silenciosas sem CRC32 e 600/600 detectadas com
  CRC32;
- CRC32 não é criptografia, mas é excelente para demonstrar detecção de
  corrupção no payload;
- energia real ainda exigiria medição elétrica externa.

## Roteiro de fala

| Tempo | Foco |
|---|---|
| 0-2 min | Provocação: "segurança pós-quântica cabe em hardware pequeno sem custo?" |
| 2-5 min | Contexto: COTS, CubeSat, falhas transitórias e ameaça quântica |
| 5-7 min | Modelo mental: HMAC autentica, ML-KEM estabelece segredo, CRC32 detecta corrupção |
| 7-8 min | Pergunta para a turma: prever se cresce mais CPU, bytes ou RAM |
| 8-12 min | Enviar `CLÁSSICA`, `PQC`, `PQC+CRC`; arrastar popups e usar o comparador ao vivo |
| 12-15 min | Demonstrar falha silenciosa vs. detecção (`PQC -> FALHA`, `PQC+CRC -> FALHA`) |
| 15-18 min | Abrir `RESULTADOS`: custo, segurança e limites com a bateria real |
| 18-20 min | Demo técnica opcional `PQC_FAULT 0 0x01 CONFIRM`, próximos passos e perguntas |

## Perguntas para criar descoberta

- Antes dos envios: "O que vai pesar mais: CPU, bytes ou RAM?"
- Depois de `PQC`: "Por que a mensagem pequena virou um pacote muito maior?"
- Antes de `PQC+CRC`: "CRC32 é criptografia ou detecção de erro?"
- Antes de `FALHA`: "Se um bit mudar e ninguém conferir, o sistema percebe?"
- Antes de `RESULTADOS`: "O que vocês esperam que tenha ficado estável?"

## Limites que devem ser ditos

- A Wisdom não é um CubeSat real; ela representa um OBC COTS didático.
- `OBC-1U-LIMITED` é uma política experimental, não uma especificação
  universal de CubeSat.
- CRC32 detecta single-bit dentro da regiao coberta; comparar checksums exigiria
  falhas multiplas, bursts ou corrupção fora da cobertura.
- ML-KEM não rejeita automaticamente todo ciphertext corrompido. A detecção
  operacional vem da confirmação da chave derivada.
- O JSON usa proxy de energia por tempo de CPU. Watts/joules exigem medidor
  externo.

## Checklist final

- `python3 -m compileall -q dashboard.py tools tests`
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover`
- `python3 -m platformio run -e robocore_wisdom_esp32`
- Conferir `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`
- Projetor/legibilidade: validado em 2026-06-18

Baterias longas de hardware para consolidação final não devem ser iniciadas por
agentes. O operador deve rodar os comandos indicados no terminal e depois
chamar o agente para verificar os JSONs/resultados.

Comando manual para repetir a bateria longa, caso a montagem física mude:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30
```

Resultado esperado:

```text
stage8_acceptance_json=logs/<timestamp>_stage8_acceptance_dev-ttyusb0.json
summary={"dashboard_demo_ok": true, "failed": 0, "mission_runs": <n>, "ok": true, "pqc_bench_runs": 2, ...}
```

Depois de rodar, chame o agente apenas para analisar o JSON gerado e atualizar
as conclusões, se os números mudarem.
