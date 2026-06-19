# Roteiro de apresentacao - PQC-SAT

Objetivo do seminario: mostrar, em 20 minutos, que a transição para
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

## Cinco slides

1. **Problema**: CubeSats usam COTS; falhas transitórias podem inverter bits.
2. **Experimento**: Wisdom + notebook, mensagem de missão, ML-KEM-512,
   HMAC-SHA256, CRC32 e bit-flip manual.
3. **Demo visual**: enviar `CLASSIC`, `PQC` e `PQC+CRC`; depois mostrar
   falha silenciosa versus detecção por CRC32.
4. **Resultados medidos**: tempos, bytes, heap, benchmark PQC, falha ML-KEM
   com confirmação e campanha de aceite.
5. **Conclusão e limites**: PQC aumenta custo, checksum soma integridade, e
   energia real exigiria medidor externo.

## Resultados para apresentar

Fonte principal: `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`.

| Medida | Resultado |
|---|---|
| Aceitacao final | 1.817,23 s, 83 registros, 0 falhas |
| MISSION runs | 27 (9 CLASSIC, 9 PQC, 9 PQC_CRC32) |
| Demo A/B | 5/5 falhas silenciosas em A; 5/5 detectadas em B |
| CRC32 payload | 8/8 `DETECTED_GUARD` no aceite final |
| `PQC_KAT` | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| `PQC_FAULT CONFIRM` | `PROTOCOL_REJECT`, `confirmation=HMAC-SHA256` |
| `PQC_FAULT NONE` | `KEY_MISMATCH` |

| Perfil | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|
| `BASELINE` 240 MHz | 3.298 | 3.861 | 4.985 |
| `OBC-1U-LIMITED` 80 MHz | 10.056 | 11.780 | 15.204 |

Leitura didatica: limitar o ESP32 para 80 MHz aumenta o custo temporal do
ML-KEM-512, mas a operacao continua funcional. O custo de checksum no payload
é baixo e suficiente para demonstrar a diferenca entre falha silenciosa e erro
detectado.

Comparacao MISSION BASELINE (240 MHz, media de 8 amostras):

| Cenario | Tempo total (us) | Bytes | Heap livre | Resultado |
|---|---:|---:|---:|---|
| `CLASSIC` | 721 | 73 | 201.412 | DELIVERED |
| `PQC` | 13.536 | 841 | 201.412 | DELIVERED |
| `PQC_CRC32` | 13.367 | 845 | 201.412 | DELIVERED |

Razoes: PQC e 18,8x mais lento e 11,5x maior que CLASSIC.
CRC32 adiciona ~10 us e +4 bytes sobre PQC.

## Sequencia da demo

1. Abrir:
   `python3 dashboard.py --port /dev/ttyUSB0`
2. Confirmar estado essencial:
   `STATUS`
3. Enviar mensagens:
   `MISSION CLASSIC`, `MISSION PQC`, `MISSION PQC_CRC32`
4. Executar apoio visual de falhas:
   `DEMO 5`
5. Mostrar manualmente:
   `CHECKSUM OFF`, `INJECT_FAULT`, `CHECKSUM ON`, `INJECT_FAULT`, `CRC_CHECK`
6. Exportar:
   `EXPORT_JSON`

O painel de botões deve ficar restrito ao fluxo acima. LED e bargraph são
acionados automaticamente pelos botões de missão como reforço lúdico do custo
relativo. Comandos de bancada como `PING`, `TELEMETRY`, `RUN_BATTERY`,
sensores, `PQC_KAT`, `PQC_FAULT` e `PQC_BENCH` ficam no HELP/terminal textual
ou no `tools/serial_console.py`.

## Roteiro de fala

| Tempo | Foco |
|---|---|
| 0-5 min | Contexto: COTS, CubeSat, falhas transitórias e PQC |
| 5-8 min | Modelo: mensagem, HMAC, ML-KEM, CRC32 e bit-flip |
| 8-11 min | Rodar `MISSION CLASSIC`, `MISSION PQC`, `MISSION PQC_CRC32` |
| 11-14 min | Interpretar CPU/RAM/tempo/bytes no topo do dashboard |
| 14-17 min | Rodar `DEMO 5` e explicar falha silenciosa versus CRC32 |
| 17-19 min | Explicar ML-KEM real, `KEY_MISMATCH` e `PROTOCOL_REJECT` |
| 19-20 min | Limites, conclusao e perguntas |

## Limites que devem ser ditos

- A Wisdom nao é um CubeSat real; ela representa um OBC COTS didatico.
- `OBC-1U-LIMITED` é uma politica experimental, nao uma especificacao
  universal de CubeSat.
- CRC32 detecta single-bit dentro da regiao coberta; comparar checksums exigiria
  falhas multiplas, bursts ou corrupcao fora da cobertura.
- ML-KEM nao rejeita automaticamente todo ciphertext corrompido. A deteccao
  operacional vem da confirmacao da chave derivada.
- O JSON usa proxy de energia por tempo de CPU. Watts/joules exigem medidor
  externo.

## Checklist final

- `python3 -m compileall -q dashboard.py tools tests`
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover`
- `python3 -m platformio run -e robocore_wisdom_esp32`
- Conferir `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`
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
