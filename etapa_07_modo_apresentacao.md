# Etapa 07 - Modo apresentação

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Executar uma campanha A/B reproduzível como segmento curto da aula de 20
minutos.

## Pré-requisitos

- eventos reais;
- timeline;
- CSV;
- guardião no simulador;
- comandos idempotentes.

## Sequência sugerida

```text
0s   nova campanha e exibição da seed
2s   explicar payload e fault specs
5s   cenário A: NONE
7s   executar 5-8 faults visíveis
22s  snapshot A
24s  cenário B: CRC32
26s  reaplicar exatamente os mesmos faults
41s  snapshot B
43s  overlay calculado
50s  exportar
53s  encerrar
```

A demo dura cerca de 53 segundos; o restante dos 20 minutos é introdução,
participação da turma e discussão.

## Regras

- Não gere uma campanha nova entre A e B.
- Não dependa de probabilidades favoráveis.
- Não apague o cenário A ao iniciar B.
- O overlay deve calcular taxas e texto a partir dos eventos.
- Se os dados não mostrarem melhora, não exiba uma conclusão positiva fixa.
- Hardware e simulação usam a mesma máquina de estados.

## Controles

- `DEMO`;
- `DEMO_PAUSE`;
- `DEMO_RESUME`;
- `DEMO_STOP`;
- `DEMO_RESTART`.

`ESC` fecha apenas o overlay, sem destruir os dados.

## Estados

```text
IDLE
RUNNING_A
SNAPSHOT_A
RUNNING_B
RESULTS
PAUSED
STOPPED
```

## Testes

- pausa em cada estado;
- stop durante request serial pendente;
- restart após conclusão;
- exportação falha sem travar a demo;
- hardware desconecta e UI informa fallback/abort;
- timer não pula múltiplas ações indevidamente em frame lento.

## Aceite

- [ ] A e B usam a mesma campanha.
- [ ] Overlay é derivado dos dados.
- [ ] Demo pode ser pausada e interrompida.
- [ ] CSV final contém os dois cenários.
- [ ] Duração foi cronometrada.
