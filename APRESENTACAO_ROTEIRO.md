# Roteiro de apresentacao - PQC-SAT

Objetivo do seminario: mostrar, em 20 minutos, que em um sistema embarcado a
seguranca depende do algoritmo criptografico, da integridade do protocolo e do
comportamento sob falhas transitórias simuladas.

## Mensagem central

O ESP32/Wisdom representa um OBC COTS educacional. O dashboard injeta
bit-flips controlados e compara dois cenarios didaticos:

- **A / sem guardiao**: a corrupcao do payload passa como falha silenciosa.
- **B / CRC32**: a mesma falha é detectada.

Em paralelo, a placa executa ML-KEM-512 real. Quando o bit-flip atinge um
ciphertext ML-KEM, a decapsulacao nao "detecta" sozinha a falha: o harness
observa `KEY_MISMATCH`, e a confirmacao HMAC-SHA256 transforma divergencia de
chave em `PROTOCOL_REJECT`.

## Cinco slides

1. **Problema**: CubeSats usam COTS; falhas transitórias podem inverter bits.
2. **Experimento**: Wisdom + notebook, payload, ML-KEM-512, bit-flip manual e
   guardiao CRC32.
3. **Demo visual**: A/B com a mesma campanha de falhas: sem checksum versus
   CRC32.
4. **Resultados medidos**: benchmarks PQC, falha ML-KEM com confirmacao e
   campanha de 30 minutos.
5. **Conclusao e limites**: checksum protege transporte; confirmacao protege a
   aceitacao da sessao; energia real exige medidor externo.

## Resultados para apresentar

Fonte principal: `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json`.

| Medida | Resultado |
|---|---|
| Aceitacao final | 1.816,87 s, 77 registros, 0 falhas |
| Long-run | 60 comandos seriais, sem timeout |
| Demo A/B | 5/5 falhas silenciosas em A; 5/5 detectadas em B |
| CRC32 payload | 13/13 `DETECTED_GUARD` no aceite final |
| `PQC_KAT` | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| `PQC_FAULT CONFIRM` | `PROTOCOL_REJECT`, `confirmation=HMAC-SHA256` |
| `PQC_FAULT NONE` | `KEY_MISMATCH` |

| Perfil | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|
| `BASELINE` 240 MHz | 3304 | 3867 | 4991 |
| `OBC-1U-LIMITED` 80 MHz | 10064 | 11789 | 15214 |

Leitura didatica: limitar o ESP32 para 80 MHz aumenta o custo temporal do
ML-KEM-512, mas a operacao continua funcional. O custo de checksum no payload
é baixo e suficiente para demonstrar a diferenca entre falha silenciosa e erro
detectado.

## Sequencia da demo

1. Abrir:
   `python3 dashboard.py --port /dev/ttyUSB0`
2. Confirmar estado essencial:
   `STATUS`, `PQC_STATUS`
3. Executar:
   `DEMO 5`
4. Mostrar manualmente:
   `CHECKSUM OFF`, `INJECT_FAULT`, `CHECKSUM ON`, `INJECT_FAULT`, `CRC_CHECK`
5. Exportar:
   `EXPORT_JSON`

O painel de botoes deve ficar restrito ao fluxo acima. Comandos de bancada
como `PING`, `TELEMETRY`, `RUN_BATTERY`, sensores, LED, RGB, bargraph,
`PQC_KAT`, `PQC_FAULT` e `PQC_BENCH` ficam no HELP/terminal textual ou no
`tools/serial_console.py`.

## Roteiro de fala

| Tempo | Foco |
|---|---|
| 0-5 min | Contexto: COTS, CubeSat, falhas transitórias e PQC |
| 5-8 min | Modelo: payload, ciphertext, bit-flip e classificacoes |
| 8-10 min | Rodar `DEMO 5` |
| 10-15 min | Interpretar timeline, JSON e tabela de resultados |
| 15-18 min | Explicar ML-KEM real, `KEY_MISMATCH` e `PROTOCOL_REJECT` |
| 18-20 min | Limites, conclusao e perguntas |

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
- Conferir `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json`
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
summary={"dashboard_demo_ok": true, "failed": 0, "ok": true, "pqc_bench_runs": 2, "records": 77}
```

Depois de rodar, chame o agente apenas para analisar o JSON gerado e atualizar
as conclusões, se os números mudarem.
