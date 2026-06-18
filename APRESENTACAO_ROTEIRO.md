# Roteiro de apresentacao - PQC-SAT

Este roteiro organiza a demonstracao de 20 minutos. Ele separa o que sera
mostrado visualmente no dashboard do que fica como evidencia tecnica de
bancada.

## Slides

1. **Contexto**: CubeSats usam componentes COTS sujeitos a falhas
   transitorias. O experimento mostra como uma alteracao de bit pode virar
   corrupcao silenciosa quando nao ha verificacao.
2. **Criptografia**: ML-KEM e um KEM. Ele estabelece segredo compartilhado; a
   aceitacao operacional da sessao precisa de confirmacao de chave ou protocolo
   acima da decapsulacao.
3. **Modelo de falha**: payload e ciphertext sao objetos diferentes. No
   payload, `NONE` aceita a corrupcao e `CRC32` detecta. No ciphertext ML-KEM,
   o harness observa `KEY_MISMATCH` ou `PROTOCOL_REJECT`.
4. **Demo A/B**: a mesma lista deterministica de bit-flips roda em A sem
   checksum e em B com CRC32. O dashboard mostra eventos, integridade, CPU,
   RAM, flash, perfil, tempos PQC e exporta JSON.
5. **Resultados e limites**: dados medidos na Wisdom para `PQC_BENCH 100`,
   KAT e `PQC_FAULT`; checksum protege transporte de payload; energia so deve
   ser afirmada com medidor externo.

## Roteiro de 20 minutos

| Tempo | Conteudo | Evidencia |
|---|---|---|
| 0-5 min | Contexto, problema e hipotese. | Slide 1. |
| 5-8 min | Payload, bit-flip manual, guardiao CRC32 e classificacoes. | Slide 3. |
| 8-10 min | Executar `DEMO 5`. | Overlay A/B, timeline e contadores. |
| 10-15 min | Interpretar JSON e metricas. | `logs/*.json`, CPU, RAM, checksum e PQC. |
| 15-18 min | Conectar ML-KEM real na Wisdom. | `PQC_INFO`, `PQC_KAT`, `PQC_FAULT`, `PQC_BENCH`. |
| 18-20 min | Limites e perguntas. | Slide 5. |

## Sequencia sugerida no dashboard

1. Abrir com hardware conectado:
   `python3 dashboard.py --port /dev/ttyUSB0`
2. Confirmar telemetria visual:
   `PING`, `STATUS`, `TELEMETRY`, `PQC_STATUS`.
3. Executar demonstracao automatizada:
   `DEMO 5`.
4. Mostrar controles manuais:
   `CHECKSUM OFF`, `INJECT_FAULT`, `CHECKSUM ON`, `INJECT_FAULT`, `CRC_CHECK`.
5. Exportar:
   `EXPORT_JSON`.

Comandos de bancada como `PQC_KAT`, `PQC_FAULT 0 0x01 CONFIRM` e
`PQC_BENCH 100` podem ser digitados no terminal textual do dashboard ou no
`tools/serial_console.py`; eles nao devem virar blocos clicaveis da demo.

## Limites que devem ser ditos

- A Wisdom nao e um CubeSat real; ela representa um OBC COTS educacional sob
  perfil experimental.
- `OBC-1U-LIMITED` e uma politica didatica de 80 MHz, radio desligado e
  orcamento explicito. A comparacao correta e contra `BASELINE`.
- CRC32 detecta single-bit dentro da regiao coberta. Comparar checksums exige
  falhas multiplas, bursts, truncamento ou corrupcao fora da cobertura.
- ML-KEM nao detecta sozinho todo ciphertext corrompido. O projeto mede
  diferenca de segredo e confirmacao HMAC-SHA256 da chave derivada.
- O dashboard exporta proxy de energia baseado em tempo de CPU. Consumo em
  watts ou joules so deve ser afirmado com medicao externa.

## Checklist antes da apresentacao

- Rodar `python3 -m compileall -q dashboard.py tools tests`.
- Rodar `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover`.
- Rodar `python3 -m platformio run -e robocore_wisdom_esp32`.
- Confirmar permissao serial para `/dev/ttyUSB0`; se aparecer
  `root:dialout`, usar `sudo chmod 666 /dev/ttyUSB0` na sessão ou adicionar o
  usuario ao grupo `dialout` antes da apresentação.
- Validar dashboard em 1920x1080 e 1366x768.
- Testar projetor com a resolucao real da sala.
- Executar uma demo completa com `DEMO 5` e exportar JSON.
- Rodar uma campanha de 30 minutos antes da apresentacao, se houver tempo de
  bancada.
