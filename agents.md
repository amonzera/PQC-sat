# agents.md - Guia para agentes de IA

Leia este arquivo inteiro antes de alterar o projeto.

## 1. Escopo

PQC-SAT é uma demonstração didática sobre:

- falhas transitórias simuladas em um sistema embarcado;
- diferença entre corrupção silenciosa e erro detectado;
- uso de mecanismos leves de integridade;
- custo de implementação de PQC em hardware limitado;
- comparação de entrega de mensagem em `CLASSIC`, `PQC` e `PQC_CRC32`;
- integração com uma sessão ML-KEM-512 em ESP32.

O projeto tem duas camadas que não podem ser confundidas:

1. **Baseline atual**: dashboard Pygame em modo simulado.
2. **Arquitetura alvo**: campanha determinística, entrega de mensagem,
   exportação JSON, firmware e bridge serial.

Nunca apresente uma funcionalidade planejada como concluída.

## 2. Fontes de verdade

Use esta precedência quando houver divergência:

1. comportamento verificado por testes;
2. `ROADMAP.md`, que consolida o plano técnico;
3. `projeto_final_pqc_esp32_cubesat.docx`, que define o objetivo acadêmico;
4. documentos `etapa_*.md`, que detalham tarefas;
5. este guia e o `README.md`.

Se um documento de etapa divergir do roadmap, corrija o documento antes de
implementar.

## 3. Estado atual verificado

### Implementado

- dashboard fullscreen em `dashboard.py`;
- Terra, CubeSat, estrelas, nebulosa e partículas procedurais;
- painel de telemetria e console;
- comandos locais do dashboard: `INJECT_FAULT`, `BIT_FLIP`, `PQC_STATUS`,
  `CRC_CHECK`, `RUN_BATTERY`, `RESET_SESSION`, `SEND_MESSAGE`,
  `SET_PRESET_CLASSIC`, `SET_PRESET_PQC`, `SET_PRESET_PQC_CRC32`,
  `TOGGLE_CLASSIC`, `TOGGLE_PQC`, `TOGGLE_CHECKSUM` e `HELP`;
- firmware serial `V1` para a RoboCore BlackBoard Wisdom;
- bridge serial Python e console `tools/serial_console.py`;
- modo padrão de `dashboard.py` tenta detectar a Wisdom e encaminha comandos do
  console visual para a ESP32 sem bloquear o loop Pygame;
- seed exclusiva para os resultados de falha (`42`);
- indicadores explícitos de modo simulado;
- mutação real de payload com CRC32 no dashboard e no firmware via
  `FAULT NONE|CRC32 payload_hex index mask`;
- backend ML-KEM-512 real na Wisdom com `mlkem-native` v1.1.0, commit
  `d2cae2b`, vendorizado em `firmware/lib/mlkem_native`;
- comandos PQC de bancada: `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`,
  `PQC_DECAP`, `PQC_FAULT` e `PQC_BENCH`; validação real em placa teve
  `PQC_KAT kat=pass`, `PQC_FAULT CONFIRM result=PROTOCOL_REJECT` e
  `PQC_FAULT NONE result=KEY_MISMATCH`;
- medição em placa: `PQC_BENCH 100` em `BASELINE` a 240 MHz retornou
  `ok=100`, `keygen_avg_us=3301`, `encap_avg_us=3864`,
  `decap_avg_us=4988`; em `OBC-1U-LIMITED` a 80 MHz retornou `ok=100`,
  `keygen_avg_us=10045`, `encap_avg_us=11769`, `decap_avg_us=15194`;
- comando `MISSION CLASSIC|PQC|PQC_CRC32` implementado no firmware para
  entregar mensagem curta e medir tempo total, bytes, heap, confirmação,
  checksum e resultado por cenário;
- exportação JSON com eventos, resumo e amostras de hardware.
- checksum ativável/desativável no dashboard por `CHECKSUM ON|OFF|TOGGLE` e
  `GUARD NONE|CRC32`;
- amostras `PQC_*` exportadas em JSON com timings, KAT, `key_match`,
  `key_confirmed`, `tag_match`, tamanhos e CRCs curtos, sem segredos
  completos;
- eventos de payload exportam overhead do guardião em `guard_prepare_us`,
  `guard_verify_us` e `guard_overhead_us`.
- faixa superior mostra CPU em MHz e `% ativo` observado em janela móvel de
  5s, e a RAM formatada como consumo de heap / total disponível;
- modo apresentação interativo e manual com presets `CLÁSSICA`, `PQC` e
  `PQC+CRC`, seguidos por `ENVIAR MSG`;
- `PQC_FAULT index mask [CONFIRM|NONE]` implementado no firmware para
  corromper ciphertext ML-KEM real e classificar `KEY_MISMATCH` ou
  `PROTOCOL_REJECT` por confirmação HMAC-SHA256 da chave derivada.
- etapa 8 de software implementada com splash opcional, `--no-splash`,
  autosave no fechamento, cleanup preservando traceback, cache de superfícies
  grandes, faixa superior focada em CPU/RAM e testes
  headless para 1920x1080 e 1366x768;
- telemetria automática desligada no dashboard; `TELEMETRY`, `PING`, LED, RGB,
  bargraph, sensores e comandos de bancada ficam no HELP/terminal textual, não
  como botões da apresentação;
- aceitação hardware da etapa 8 validada e consolidada em
  `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`, com 1.817,23 s,
  83 registros, 0 falhas, 27 MISSION runs, 2 benchmarks PQC e demo headless OK;
- roteiro de apresentação criado em `APRESENTACAO_ROTEIRO.md`, com cinco
  slides, sequência de demo, limites científicos e checklist pré-apresentação;
- metodologia de métricas consolidada em `METRICAS_CONSOLIDADAS.md`.
- projetor/legibilidade confirmados pelo usuário em 2026-06-18 após ajuste de
  botões e métricas do dashboard.

### Não implementado
Nenhuma etapa técnica de implementação permanece aberta para o MVP do
seminário. Extensões futuras devem ficar fora da superfície principal da demo.

## 4. Stack

### Atual

| Componente | Tecnologia |
|---|---|
| Linguagem validada | Python 3.14.5 |
| Renderização | pygame-ce 2.5.7 |
| Aplicação | `dashboard.py` monolítico |
| Assets | desenho procedural, sem arquivos externos |
| Serial | pyserial 3.5+ opcional |
| Firmware | Arduino/PlatformIO para BlackBoard Wisdom |
| PQC | ML-KEM-512 com `mlkem-native` v1.1.0 vendorizado |

### Planejada

| Componente | Tecnologia candidata |
|---|---|
| Firmware futuro | ESP-IDF se a apresentação exigir troca de framework |
| PQC futuro | Kyber512 apenas se identificado como fallback rotulado; ML-KEM-768+ fora do MVP |

`pqm4` é voltado a ARM Cortex-M4 e não deve ser tratado como drop-in para
ESP32 Xtensa. `liboqs` é útil para prototipagem no host, mas não há no projeto
uma integração pronta com Arduino/ESP32. Há referências de Kyber512-90s e
ML-KEM-512 em ESP32; nenhuma dispensa validar a placa, o framework, a variante
e os vetores conhecidos usados neste projeto. Não chame Kyber pré-FIPS de
ML-KEM/FIPS 203.

## 5. Regras de implementação

- Preserve o baseline funcional e trabalhe incrementalmente.
- Mantenha o dashboard em um único arquivo Python até que exista motivo
  concreto e aprovação para modularização.
- Firmware pode e deve ter arquivos próprios sob `firmware/`.
- Use constantes `C_*` para cores reutilizadas.
- Use `pygame.SRCALPHA` quando transparência for necessária.
- Não bloqueie o loop principal com `sleep`, I/O serial ou criptografia longa.
- Não carregue imagens, sons ou fontes externas sem decisão explícita.
- Não mostre `ESP32 ONLINE`, `CRC ON` ou `ML-KEM ativo` sem evidência real.
- O dashboard é a superfície da apresentação ao vivo. Mantenha como blocos
  clicáveis apenas os comandos do roteiro didático e manual: `"ENVIAR MSG"`,
  `"CLÁSSICA"`, `"PQC"`, `"PQC+CRC"` e `"FALHA"`. A simulação automatizada
  (`DEMO`), controle de pausa (`PAUSA`) e exportação direta (`EXPORT`) foram
  removidos do painel visual. O terminal textual do painel pode encaminhar
  comandos avançados de firmware quando a placa estiver conectada, inclusive
  bancada, inventário, debug e PQC técnico, desde que isso não vire botão ou
  fluxo principal da apresentação.
- O botão superior `RESULTADOS` e o onboarding fazem parte da apresentação:
  eles devem resumir a bateria real, conclusões e próximos passos, sem iniciar
  coletas demoradas nem adicionar comandos técnicos ao menu lateral.
- `ENVIAR MSG` e `MISSION ...` não podem simular/reproduzir métricas
  consolidadas quando a placa não estiver conectada. A demo principal deve
  usar resposta serial real da Wisdom; modo `--simulated` é apenas ensaio
  visual/layout.
- Todo comando útil que não pertença à apresentação deve continuar registrado
  para uso técnico em outro lugar: `hardware_command_reference.md`,
  `tools/serial_console.py --all-commands`, documentação de etapa ou scripts de
  bancada. Não apague capacidade técnica só porque ela não aparece no
  conjunto de botões; apenas separe a superfície visual da demo da superfície
  textual de engenharia.
- Os logs oficiais e métricas consolidadas do projeto devem ser registrados e
  coletados exclusivamente através de baterias de testes longas e controladas
  no terminal (como o script `tools/stage8_acceptance.py`), e NUNCA a partir de
  demonstrações manuais ou campanhas visuais ao vivo no dashboard.
- Resultados experimentais devem vir de bytes mutados e verificações reais.
- Mantenha a aleatoriedade do experimento separada da aleatoriedade visual.
- Trate `OBC-1U-LIMITED` como perfil experimental, não como especificação
  universal de CubeSat.
- Compare medições limitadas com o baseline integral do ESP32.
- Baterias longas na placa para consolidação final, aceite da apresentação ou
  coleta de dados demorados não devem ser iniciadas pelo agente. O agente deve
  indicar exatamente os comandos para o operador executar no terminal, os
  resultados esperados e o arquivo JSON esperado; depois, quando o usuário
  chamar o agente novamente, o agente deve analisar os logs/resultados gerados.
  Smoke tests curtos podem ser executados pelo agente apenas quando forem
  necessários e autorizados.
  Para repetir o aceite longo deste projeto, indique ao operador:
  `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30`.
  O resumo esperado é `ok=true`, `failed=0`, `dashboard_demo_ok=true` e
  `pqc_bench_runs=2`; depois do comando `MISSION`, também deve haver
  `mission_runs>=6`.
- Preserve alterações locais do usuário que não pertençam à tarefa.

Os tamanhos atuais são:

| Fonte | Tamanho |
|---|---:|
| `FONT_TITLE` | 26 |
| `FONT_HEADER` | 22 |
| `FONT_BODY` | 17 |
| `FONT_SMALL` | 15 |
| `FONT_CMD` | 17 |
| `FONT_PIXEL` / `FONT_LABEL` | 13 |

Esses valores foram validados em projetor para a apresentação atual. Se a sala,
resolução ou projetor mudarem, revalidar antes de afirmar legibilidade.

## 6. Modelo experimental obrigatório

Antes de implementar o guardião, defina:

- objeto corrompido: payload, ciphertext ou estado interno;
- instante da corrupção;
- região coberta pelo guardião;
- condição objetiva de cada resultado;
- vetor de falha reproduzível.

Para ML-KEM:

- `Decaps` sempre produz um segredo para entradas de tamanho válido;
- `sharedSecretA != sharedSecretB` deve ser chamado de `KEY_MISMATCH` observado
  pelo harness, não de erro explicitamente detectado pela decapsulação;
- detecção operacional exige confirmação no protocolo, por exemplo um MAC/tag
  calculado com a chave derivada.

Para `MISSION`:

- `CLASSIC` é baseline clássico simétrico com `HMAC-SHA256`; não o apresente
  como ECDH nem como criptografia assimétrica clássica completa;
- `PQC` é ML-KEM-512 para estabelecer segredo e HMAC-SHA256 para autenticar a
  mensagem;
- `PQC_CRC32` adiciona CRC32 ao payload sobre o fluxo PQC;
- compare `elapsed_us`, `bytes_total`, `heap`, `min_heap`, `key_match`,
  `tag_match`, `crc_match` e `result`;
- energia só pode ser proxy por tempo de CPU, exceto se houver medição elétrica
  externa.

Para checksums:

- armazene ou transmita o valor de referência antes da falha;
- compute novamente depois da falha;
- compare valores;
- não substitua isso por taxas aleatórias atribuídas a CRC/XOR.

## 7. Validação

Comandos mínimos antes de concluir uma alteração:

```bash
python3 -m py_compile dashboard.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import dashboard"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
git diff --check
```

Para mudanças visuais, execute também:

```bash
python3 dashboard.py
```

Valide o fluxo real usado na apresentação, não apenas importação ou
compilação.

## 8. Próxima ordem de trabalho

1. Atualizar relatório/slides finais com os resultados JSON medidos.
2. Ensaiar a apresentação sem reintroduzir comandos ruidosos nos botões.

Última revisão: 2026-06-18.
