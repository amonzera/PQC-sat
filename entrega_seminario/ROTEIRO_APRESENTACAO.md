# Roteiro de apresentacao - PQC-SAT

Tempo planejado: 18-20 minutos.

Este roteiro reflete o estado final do projeto, com ML-KEM-512 executando no
hardware, MISSION nos tres cenarios funcionando, e metricas consolidadas.

## Slide 1 — Problema (3-5 min)

Contexto: CubeSats usam COTS; falhas transitorias podem inverter bits. O mundo
esta migrando para criptografia pos-quantica, mas hardware embarcado tem CPU,
RAM e energia limitadas.

Frase de abertura sugerida:

> Nosso projeto mostra um desafio atual: o mundo esta migrando para
> criptografia pos-quantica, mas hardware embarcado tem recursos limitados. Em
> um contexto inspirado em CubeSat, queremos ver quanto custa sair de uma
> mensagem classica autenticada para PQC e depois para PQC com checksum.

## Slide 2 — Experimento (3 min)

Explique a montagem: Wisdom/ESP32 + dashboard Python + notebook.

Tres cenarios de entrega de mensagem:

- CLASSIC: mensagem autenticada com HMAC-SHA256 (baseline classico);
- PQC: mensagem autenticada apos acordo de segredo com ML-KEM-512;
- PQC+CRC: o mesmo fluxo PQC com CRC32 adicional no payload.

Alem disso, bit-flips demonstram a diferenca entre falha silenciosa e erro
detectado.

## Slide 3 — Demo visual (3-6 min)

Sequencia da demo ao vivo:

1. Abrir: `python3 dashboard.py --port /dev/ttyUSB0`
2. Enviar mensagem clássica: selecionar `CLÁSSICA` (botão azul) e clicar em `ENVIAR MSG`.
3. Enviar mensagem PQC sem integridade: selecionar `PQC` (botão roxo), desativar `CHECKSUM` (botão apagado) e clicar em `ENVIAR MSG`.
4. Enviar mensagem PQC com integridade: selecionar `PQC`, ativar `CHECKSUM` (botão verde) e clicar em `ENVIAR MSG`.
5. Injetar falhas manualmente:
   - Com `CHECKSUM` desativado, clicar em `FALHA` -> Observar erro silencioso (`SILENT`).
   - Com `CHECKSUM` ativado, clicar em `FALHA` -> Observar detecção (`DETECTED_GUARD`).

> [!NOTE]
> Os logs oficiais e dados numéricos consolidados foram gravados através de baterias automatizadas de longa duração via terminal (como o script `tools/stage8_acceptance.py`), garantindo rigor científico sem poluir o dashboard visual.

## Slide 4 — Resultados medidos (3 min)

Fonte: `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`

Aceite final: 83 registros, 0 falhas, 27 MISSION runs.

| Cenario | Tempo (us) | Bytes | Resultado |
|---|---:|---:|---|
| CLASSIC | 721 | 73 | DELIVERED |
| PQC | 13.536 | 841 | DELIVERED |
| PQC_CRC32 | 13.367 | 845 | DELIVERED |

Razoes: PQC e 18,8x mais lento e 11,5x maior que CLASSIC em bytes.
CRC32 adiciona ~10 us e +4 bytes sobre PQC.

Benchmark ML-KEM-512 (100 rounds):

| Perfil | keygen (us) | encap (us) | decap (us) |
|---|---:|---:|---:|
| BASELINE 240 MHz | 3.298 | 3.861 | 4.985 |
| OBC-1U-LIMITED 80 MHz | 10.056 | 11.780 | 15.204 |

Testes de seguranca:

- PQC_KAT: kat=pass
- PQC_FAULT CONFIRM: PROTOCOL_REJECT
- PQC_FAULT NONE: KEY_MISMATCH
- FAULT CRC32: 8/8 DETECTED_GUARD
- Demo A/B: 5/5 silenciosas sem CRC, 5/5 detectadas com CRC

## Slide 5 — Conclusao e limites (2 min)

PQC aumenta custo, checksum soma integridade, e a demonstracao funciona em
hardware real.

Limites que devem ser ditos:

- A Wisdom nao e um CubeSat real; ela representa um OBC COTS didatico.
- OBC-1U-LIMITED e uma politica experimental, nao uma especificacao universal.
- ML-KEM nao rejeita automaticamente todo ciphertext corrompido. A deteccao
  operacional vem da confirmacao da chave derivada.
- O JSON usa proxy de energia por tempo de CPU. Watts/joules exigem medidor
  externo.
- Bit-flips por software nao reproduzem radiacao real.

Frase de fechamento:

> O experimento e didatico e reproduzivel. A contribuicao do projeto e tornar
> visivel que a seguranca depende do algoritmo, da implementacao, do protocolo
> e do hardware. PQC em hardware limitado e possivel, mas tem custo.

Abra para perguntas.

## Checklist final

- `python3 -m compileall -q dashboard.py tools tests`
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover`
- Conferir `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`
- Projetor/legibilidade validada
