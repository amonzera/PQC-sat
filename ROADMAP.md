# Roadmap consolidado - PQC-SAT

Versão revisada em 2026-06-25.

## 1. Visão geral

O PQC-SAT deve demonstrar, em uma atividade de aproximadamente 20 minutos,
que segurança embarcada depende tanto do algoritmo criptográfico quanto da
integridade da implementação e do protocolo, e que a migração para PQC aumenta
o custo em hardware limitado.

A interface visual já existe e agora possui dois experimentos complementares.
O fluxo principal de apresentação envia uma mensagem curta pela Wisdom nos
cenários `CLASSIC`, `PQC` e `PQC_CRC32`, registrando tempo, bytes, heap,
confirmação, cifra AES-GCM e checksum. Esse fluxo pode usar payload vivo: o dashboard coleta
sensores reais da Wisdom, monta `payload_hex` e envia o dado para `MISSION`.
O fluxo de apoio muta um payload, registra eventos e compara `NONE` e `CRC32`
para explicar falha silenciosa versus erro detectado; quando a placa está
online, o potenciômetro pode selecionar fisicamente o bit-flip. O backend PQC
real já está instalado na Wisdom com ML-KEM-512 e medição nos perfis
`BASELINE` e `OBC-1U-LIMITED`. O firmware mantém `PQC_FAULT` como comando
técnico avançado para bancada ML-KEM, mas esse caminho não pertence aos popups
nem ao roteiro principal. A demonstração visual de falha usa payload com
`FAULT NONE` versus `FAULT CRC32`.

## 2. Baseline auditado

| Item | Estado |
|---|---|
| Dashboard Pygame | Funcional |
| Modo fullscreen | Funcional |
| Console | Funcional |
| Sorteio provisório de falhas | Removido do caminho de classificação |
| Seed isolada do experimento | Funcional |
| Mutação real de bytes | Funcional no dashboard |
| ML-KEM real | Funcional na Wisdom com `mlkem-native` v1.1.0, commit `d2cae2b` |
| AES-128-GCM em MISSION | Implementado no firmware; `CLASSIC` usa chave efêmera, `PQC` deriva chave de ML-KEM |
| Mensagem CLASSIC/PQC/PQC+CRC | Implementada no firmware por `MISSION CLASSIC|PQC|PQC_CRC32` |
| Interface serial PQC | `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP`, `PQC_FAULT` e `PQC_BENCH` funcionais |
| Medição PQC na placa | `PQC_BENCH 100` medido em `BASELINE` e `OBC-1U-LIMITED`; `PQC_KAT` passou no hardware gravado |
| Falha em ciphertext ML-KEM | `PQC_FAULT index mask [CONFIRM|NONE]` validado na placa e exportado no JSON |
| CRC/checksum real | CRC32 funcional no dashboard e no firmware |
| ESP32/serial | Funcional com `HELLO`, `STATUS`, sensores, OLED e `FAULT` |
| Payload vivo | Dashboard coleta `SENSOR_READ`, `ANALOG POT` e `DIGITAL BUTTON`, monta `MISSION ... payload_hex` e exibe os sensores no popup |
| Falha física didática | Potenciômetro da Wisdom seleciona byte/máscara do bit-flip quando o satélite está online |
| JSON/timeline/demo | Timeline, JSON, bateria A/B e `DEMO` visual automatizado funcionais |

## 2.1 Histórico de implementação

Este histórico deve ser usado para estudar a apresentação e para retomar o
projeto sem reconstruir decisões antigas:

- 2026-06-17: firmware Wisdom consolidado com transporte serial `V1`,
  inventário de placa, sensores, atuadores, OLED standby, perfis
  `BASELINE`/`OBC-1U-LIMITED`, `FAULT NONE|CRC32` e backend ML-KEM-512 real
  via `mlkem-native`.
- 2026-06-17: `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP` e
  `PQC_BENCH 5` validados em placa nos perfis baseline e limitado.
- 2026-06-18: dashboard ajustado para usar apenas blocos clicáveis ligados à
  apresentação; comandos de bancada ficaram no terminal textual e em
  `hardware_command_reference.md`.
- 2026-06-18: métricas superiores do dashboard foram enxugadas para a
  apresentação e hoje expõem CPU e RAM perto da animação; tempos e bytes dos
  cenários ficam no console, no overlay de mensagem e no painel `RESULTADOS`.
- 2026-06-18: a métrica de CPU passou a mostrar também `% ativo` em janela
  móvel de 5s, calculado por tempo de comando observado; a exportação JSON
  passou para `pqc-sat-run-v2` e inclui métricas agregadas de CPU, PQC e
  checksum.
- 2026-06-18: `PQC_FAULT index mask [CONFIRM|NONE]` passou a corromper
  ciphertext ML-KEM real, calcular confirmação HMAC-SHA256 e exportar
  `KEY_MISMATCH`, `PROTOCOL_REJECT`, `key_confirmed` e `tag_match` sem revelar
  segredos completos.
- 2026-06-18: build PlatformIO da revisão com `PQC_FAULT` passou para
  `robocore_wisdom_esp32`, com 56.556 bytes de RAM estimada e 914.229 bytes de
  flash; a revisão foi gravada em `/dev/ttyUSB0` e verificada por hash.
- 2026-06-18: validação real pós-upload: `PQC_KAT kat=pass`,
  `PQC_FAULT 0 0x01 CONFIRM` retornou `PROTOCOL_REJECT`,
  `PQC_FAULT 0 0x01 NONE` retornou `KEY_MISMATCH`, `PQC_BENCH 100` passou em
  `BASELINE` e `OBC-1U-LIMITED`, e `FAULT CRC32` retornou
  `DETECTED_GUARD`.
- 2026-06-18: Etapa 07 implementada com comandos `DEMO`, `DEMO_PAUSE`,
  `DEMO_RESUME`, `DEMO_STOP` e `DEMO_RESTART`, overlay derivado dos eventos,
  snapshots A/B e exportação JSON cronometrada.
- 2026-06-18: Etapa 08 implementada no software com splash opcional,
  `--no-splash`, autosave no fechamento, cleanup com traceback preservado,
  cache de superfícies grandes, faixa superior reduzida a CPU/RAM, exportação
  de métricas do processo e teste headless para
  1920x1080 e 1366x768.
- 2026-06-18: criado `APRESENTACAO_ROTEIRO.md` com blocos narrativos do
  dashboard, roteiro de 20 minutos, sequência de comandos da demo, limites
  científicos e checklist pré-apresentação.
- 2026-06-18: verificação final detectou a Wisdom em `/dev/ttyUSB0` como
  CP2102N/Silicon Labs. Após liberação da porta, a aceitação de hardware da
  etapa 8 passou e foi consolidada com `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`:
  1.817,23 s de execução, 83 registros, 0 falhas, 27 MISSION runs,
  2 benchmarks PQC, 8 `DETECTED_GUARD` em payload CRC32 e demo headless do
  dashboard com 5/5 falhas silenciosas em A e 5/5 detectadas em B.
- 2026-06-18: polimento final de apresentação removeu polling automático de
  `TELEMETRY`, reduziu os blocos clicáveis aos comandos centrais da demo e
  manteve comandos de bancada no HELP/terminal textual.
- 2026-06-18: criado `GUIA_DIDATICO_APRESENTACAO.md` como material completo
  de estudo e condução da apresentação para público leigo em criptografia,
  consolidando objetivo, passo a passo, resultados, comandos, limites e fala
  sugerida.
- 2026-06-18: objetivo final do seminário consolidado como comparação de custo
  e segurança entre `CLASSIC`, `PQC` e `PQC_CRC32`; firmware ganhou
  `MISSION CLASSIC|PQC|PQC_CRC32 [payload_hex]`, dashboard ganhou botões
  correspondentes, overlay de mensagem entregue, exportação JSON em
  `metrics.mission` e efeitos lúdicos de LED/bargraph por cenário.
- 2026-06-18: criado `METRICAS_CONSOLIDADAS.md` com metodologia de coleta,
  campos do JSON, comandos curtos/longos e limites científicos para a
  comparação final.
- 2026-06-19: criado `PERGUNTAS_E_RESPOSTAS_SEMINARIO.md` com banco de
  perguntas prováveis, respostas curtas e respostas técnicas para defender
  objetivo, métricas, limitações, ML-KEM, HMAC, CRC32, bit-flips e próximos
  passos.
- 2026-06-19: criado `ALGORITMOS_DO_PROJETO.md` como material de estudo
  detalhado dos algoritmos do seminário, explicando `CLASSIC`, `PQC`,
  `PQC_CRC32`, HMAC-SHA256, SHA-256, ML-KEM-512, CRC32, bit-flip, comparação
  em tempo constante, KAT, `PQC_BENCH` e origem das métricas.
- 2026-06-19: consolidação final do seminário ajustou o dashboard para usar
  onboarding completo de cinco telas e botão `RESULTADOS` com a bateria real
  `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`; a documentação
  passou a registrar conclusões, próximos passos e a explicação correta de
  `bytes_total` então vigente como payload + ciphertext ML-KEM + tag HMAC +
  checksum. Essa composição ficou histórica após a etapa AES-GCM de 2026-06-25.
- 2026-06-25: `MISSION` passou a usar criptografia real de payload com
  `AES-128-GCM`. No `CLASSIC`, a Wisdom gera chave AES-128 efêmera e nonce por
  envio. Em `PQC`/`PQC_CRC32`, ML-KEM-512 estabelece o segredo e o firmware
  deriva a chave AES. O CRC32 de `PQC_CRC32` entra no plaintext protegido antes
  da cifragem. O dashboard passou a mostrar `RNG`, `KDF`, `AES-GCM`,
  `aead_match`, nonce e tag GCM; a bateria `20260625T005330Z` ficou marcada
  como histórica pré-AES-GCM até nova coleta oficial.
- 2026-06-19: fluxo de apresentação de mensagens passou a exigir resposta
  serial real da Wisdom. `ENVIAR MSG` não gera métricas por replay local quando
  a placa está ausente; o modo `--simulated` fica restrito a ensaio visual e
  testes de layout.
- 2026-06-21: apresentação de 20 minutos reforçada com momentos de impacto:
  comparador visual automático para popups `MISSION`, roteiro com perguntas de
  previsão para a turma, painel `RESULTADOS` reorganizado em custo, segurança e
  limites, e documentação orientada a conduzir descoberta em vez de apenas
  relatar números.
- 2026-06-22: dashboard ganhou animação lúdica passo a passo acionada por
  resposta real `MISSION` dentro do próprio popup de mensagem. A janela mostra
  `payload`, `KEYGEN`, `ENCAP`, `DECAP`, `HMAC`, `CRC32`, verificação, resultado,
  microexplicações e crescimento do pacote com os bytes medidos pela Wisdom. A
  animação não gera replay local quando a placa está ausente; ao final, o popup
  troca automaticamente para as métricas detalhadas.
- 2026-06-22: auditoria de interfaces sem hardware corrigiu bugs de produção:
  `HELP` do console serial agora é local e não é enviado à placa, `--list-ports`
  não falha quando não há porta conectada, `stage8_acceptance.py` trata porta
  ausente sem traceback, comandos locais documentados (`EXPORT_JSON`,
  `SAVE_SESSION` e `DEMO*`) foram roteados no dashboard, e popups/comparador de
  mensagens foram ajustados para caber em 1366x768 e 1920x1080.
- 2026-06-22: animação interna de mensagem foi desacelerada e ganhou controle
  discreto `PAUSAR`/`PLAY` dentro do popup. O apresentador pode congelar o fluxo
  em `KEYGEN`, `ENCAP`, `DECAP`, `HMAC` ou `CRC32`, explicar o crescimento do
  pacote e retomar sem perder a resposta real da placa.
- 2026-06-22: falhas também ganharam popup didático persistente e pausável. O
  fluxo mostra `payload/ciphertext`, bit-flip, guardião, verificação e
  resultado, incluindo byte antes/depois, CRC antes/depois e diferença entre
  `SILENT`, `DETECTED_GUARD`, `KEY_MISMATCH` e `PROTOCOL_REJECT`.
- 2026-06-24: smoke test curto com hardware real passou em `/dev/ttyUSB0`,
  gerando `logs/20260624T233542Z_stage8_acceptance_dev-ttyusb0.json` com
  `failed=0`, `mission_runs=6`, `pqc_bench_runs=2` e `dashboard_demo_ok=true`.
- 2026-06-24: criado `tools/final_metrics_battery.py`, runner dedicado para
  coleta longa de resultados finais. Ele separa a coleta estatística do aceite
  de regressão, executa ciclos balanceados por perfil (`BASELINE` e
  `OBC-1U-LIMITED`), agrega `MISSION`, `PQC_BENCH` e `FAULT` no próprio JSON e
  deve ser rodado manualmente no terminal pelo operador.
- 2026-06-25: bateria final de métricas concluída em
  `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`: 1.681,24 s,
  3.074 registros, 0 falhas, 1.800 `MISSION runs`, 10 `PQC_BENCH` e 1.200
  testes `FAULT`. A fonte principal dos resultados da apresentação passou a
  ser esse JSON.
- 2026-06-26: criado `tools/aes_gcm_metrics_battery.py`, runner específico para
  a bateria oficial pós-AES-GCM. Ele usa payload fixo nos três cenários
  `MISSION`, valida `cipher=AES-128-GCM`, nonce de 12 bytes, tag de 16 bytes,
  `aead_match`, `decrypt_ok`, `tag_match`, variação de `nonce_crc32`,
  `ciphertext_crc32` e `gcm_tag_crc32`, e grava JSON
  `*_aes_gcm_metrics_*.json` pronto para atualização dos resultados.
- 2026-06-26: os popups de falha foram realinhados ao objetivo didático da
  apresentação. O dashboard deixou de abrir visualização para `PQC_FAULT` e
  removeu o caminho HMAC/confirmacao dos textos de falha; o fluxo visual agora
  demonstra apenas bit-flip em payload com `NONE` versus `CRC32`.
- 2026-06-26: bateria pós-runner AES concluída em
  `logs/20260626T044359Z_aes_gcm_metrics_dev-ttyusb0.json`: 324,5 s,
  1.038 registros, 0 falhas, 600 `MISSION runs`, 6 `PQC_BENCH` e 400 testes
  `FAULT`. A execução foi limpa, mas `summary.aes_gcm.checks.official_candidate`
  ficou `false`: os `MISSION` retornaram campos legados (`HMAC-SHA256` e
  confirmação HMAC), sem `cipher=AES-128-GCM`, `nonce_crc32` ou `gcm_tag_crc32`.
  Essa coleta foi reclassificada como diagnóstico de firmware antigo, não como
  resultado oficial.
- 2026-06-26: aba `RESULTADOS` reforçada para mostrar a validação AES-GCM
  diretamente no painel: `official_candidate=false`, `non_aes=600/600`, 6.000
  campos AES ausentes e 600 falhas AEAD esperadas para firmware legado. O
  consolidator agora recalcula esses contadores a partir dos `records`, em vez
  de confiar no `summary.aes_gcm` gerado antes da correção do parser de
  `MISSION ... payload_hex`.
- 2026-06-26: firmware regravado e nova bateria oficial AES-GCM concluída em
  `logs/20260626T051412Z_aes_gcm_metrics_dev-ttyusb0.json`: 343,16 s,
  1.038 registros, 0 falhas, 600 `MISSION runs`, 6 `PQC_BENCH` e 400 testes
  `FAULT`. A validação passou com `official_candidate=true`,
  `non_aes_gcm_records=0`, `missing_required_fields=0`, `aead_failures=0` e
  `nonce_crc32_duplicates=0`. O dashboard agora usa essa coleta na aba
  `RESULTADOS`, mostrando `CLASSIC` com AES-128-GCM, `PQC` com ML-KEM-512 +
  AES-GCM e `PQC_CRC32` com ML-KEM-512 + AES-GCM + CRC32.
- 2026-06-26: aba `RESULTADOS` recebeu bibliografia curta na própria tela,
  limitada a referências que sustentam as teses centrais da apresentação:
  NIST FIPS 203 para ML-KEM, NIST FIPS 197 para AES, NIST SP 800-38D para
  GCM/GMAC e Koopman & Chakravarty para CRC em redes embarcadas.
- 2026-06-26: a mesma aba recebeu referências curtas de motivação do problema:
  NIST PQC Project para ameaça quântica e migração, NASA SmallSat SoA para
  contexto de satélites pequenos e Mikaelian 2009 para radiação/charging como
  risco físico à eletrônica espacial.
- 2026-06-25: camada "satélite vivo" adicionada sem alterar firmware. O
  dashboard ganhou toggle `Payload vivo`, coleta curta de `SENSOR_READ
  TEMP_HUM`, `SENSOR_READ ACCEL`, `SENSOR_READ APDS`, `ANALOG POT` e
  `DIGITAL BUTTON`, montagem de payload ASCII compacto dentro do limite de 96
  bytes do firmware, envio `MISSION ... payload_hex`, popup com `PAYLOAD REAL
  DA PLACA`, exportação dos sensores no JSON e falha guiada pelo potenciômetro
  para escolher byte/máscara do bit-flip. LED/RGB/bargraph são acionados como
  feedback físico de fase/custo; OLED permanece em `STANDBY` porque o firmware
  atual não expõe escrita textual arbitrária.
- 2026-06-25: recurso opcional de fechamento `STRESS PQC_LOOP 500 CONFIRM`
  adicionado. O firmware executa até 500 rodadas ML-KEM controladas, exige
  `CONFIRM`, retorna tempo total, médias keygen/encap/decap, heap e perfil. O
  dashboard expõe a função apenas dentro de `RESULTADOS`, com confirmação em
  dois cliques e aviso de timeout didático após 8 s; não entra nos botões
  laterais nem substitui as métricas oficiais.
- 2026-06-26: animação dos popups de missão e falha refatorada para um
  diagrama limpo de três blocos `[ENTRADA] → [OPERAÇÃO] → [SAÍDA]` por etapa,
  com layout uniforme e sem texto cortado. Cada bloco mostra título, sub-título
  técnico e, abaixo, duas linhas de teoria. Facilitadores visuais discretos foram
  adicionados: ícones em line-art (escudo, cadeado, chave, hash, sensor, DRBG,
  satélite, lista, alerta) nos blocos de operação; selos `✓` verde/`✗` vermelho
  nos blocos de saída; partículas de dados fluindo pelas setas nos passos de
  payload; raio cósmico (emissora pulsante + raio irregular + faísca) atingindo
  o bit invertido no passo de bit-flip. Código morto removido: constantes de
  sprite PIX_*, primitivas de esquema e pintores de cena antigos.
- 2026-06-26: ordem das etapas do popup de mensagem corrigida para ser fiel à
  sequência real de uma mensagem. Antes o fluxo PQC mostrava
  `KEYGEN → ENCAP → DECAP → KDF → AES-GCM → VERIFICA`, com o DECAP (receptor)
  acontecendo antes de a chave ser derivada e antes de a mensagem ser cifrada.
  Agora segue lado emissor depois lado receptor:
  `payload → [CRC32] → KEYGEN (rx) → ENCAP (tx) → KDF (tx) → AES-GCM (tx) →
  DECAP (rx) → VERIFICA (rx) → RESULTADO`. As microexplicações foram marcadas
  com `(tx)`/`(rx)` para deixar claro quando cada operação ocorre no emissor ou
  no receptor.
- 2026-06-26: auditoria de dívida técnica em teoria + código. Correções de
  teoria nos popups e docs: a decapsulação ML-KEM **re-cifra** (FO), não
  "re-encapsula", e **não acusa erro** em ciphertext alterado (devolve um
  segredo de rejeição); o CRC-32 detecta "todo erro de 1 bit e a maioria das
  rajadas" (antes "até 1 bit"); removida a linguagem obsoleta de HMAC como
  autenticação da mensagem (agora AES-GCM; HMAC só confirma a chave ML-KEM no
  caminho de falha); adicionada a nuance de Grover (AES-128 ~64 bits). Bug
  corrigido: `_parse_u8_token` relançava `ValueError` em entrada não-hex.
  Remoção de funções não utilizadas, a pedido: o **comparador ao vivo** de
  mensagens (regressão do commit `1b02a9b`, nunca era chamado) e o **overlay de
  HELP/terminal em aba lateral** (`_console_help_lines`, `help_topic`,
  `help_scroll` e handlers de scroll — não renderizavam); o terminal de texto
  para digitar comandos avançados continua funcional. Outros símbolos mortos
  removidos (`_draw_event_timeline`, `_result_color`, `_history_command_label`,
  `_draw_metric_pair`, `_mission_tile_values`, `HELP_HINT_LINES`). Bytes
  canônicos padronizados para a bateria oficial AES-GCM
  (`logs/20260626T051412Z`): 62/830/834 (CLASSIC/PQC/PQC_CRC32, payload 34 B);
  removida a estimativa inventada 69/837/841; os números 73/841/845 e os tempos
  511/13.234/13.130 us ficam como histórico pré-AES. `dashboard.py` reduziu
  ~211 linhas; 84/84 testes passam.

O dashboard já pode demonstrar entrega de mensagem em `CLASSIC`, `PQC` e
`PQC_CRC32`, demonstrar `SILENT` versus `DETECTED_GUARD` em payload, executar
`RUN_BATTERY` A/B, executar `DEMO` com overlay calculado e exportar sessões em
JSON. A coleta técnica antiga, a campanha prolongada com `MISSION` e a
validação de projetor/legibilidade já foram concluídas; novas baterias longas
devem ser rodadas manualmente apenas se a montagem física mudar.

## 3. Gate 0 - protocolo experimental

Nenhuma fase de coleta deve começar antes destas decisões.

### 3.1 Objetos de teste

O projeto mistura três experimentos diferentes. Eles devem ser separados:

1. **Payload**: mensagem curta enviada entre duas pontas.
2. **Ciphertext ML-KEM**: saída de encapsulação entregue à decapsulação.
3. **Estado interno**: chave ou buffer em memória.

Para a apresentação curta, o experimento principal deve usar payload. A
corrupção de ciphertext ML-KEM pode ser uma extensão técnica. Corrupção de
estado interno exige instrumentação específica e fica fora do MVP.

### 3.2 Classificação dos resultados

| Resultado | Critério |
|---|---|
| `OK` | Os bytes recebidos são iguais aos originais. |
| `SILENT` | Os bytes mudaram e a aplicação aceitou o dado. |
| `DETECTED_GUARD` | O checksum/CRC divergiu do valor de referência. |
| `KEY_MISMATCH` | O harness observou segredos ML-KEM diferentes. |
| `PROTOCOL_REJECT` | Uma confirmação autenticada com a chave derivada falhou. |
| `INVALID_INPUT` | Tamanho ou formato foi rejeitado antes do algoritmo. |

ML-KEM não deve retornar um rótulo fictício `DETECTED_BY_DECAPS`. Para
ciphertexts com tamanho válido, a decapsulação produz um segredo. A detecção
operacional acontece no harness ou em um protocolo de confirmação.

### 3.3 Campanha de falhas

Cada evento deve conter:

```text
campaign_seed
trial_id
campaign_run_id
campaign_trial_id
target
byte_index
bit_mask
fault_width
guard
before_digest
after_digest
result
elapsed_us
mode
```

A mesma lista de falhas deve ser aplicada aos cenários A e B. A animação não
pode consumir a mesma fonte de aleatoriedade da campanha.

### 3.4 Comparação de guardiões

Para exatamente um bit-flip dentro da região protegida, XOR, CRC-16 e CRC-32
detectam a alteração. Percentuais como 15%, 5% e 1% não são justificáveis
nesse modelo.

Para comparar mecanismos, a campanha precisa incluir pelo menos um destes:

- dois ou mais bits alterados;
- bursts contíguos;
- bytes fora da região coberta;
- checksum também corrompido;
- truncamento ou reordenação.

O MVP pode comparar apenas `NONE` e `CRC32`, mantendo XOR/CRC-16 como extensão.

## 4. Arquitetura alvo

```text
Dashboard Pygame
    |
    +-- ExperimentEngine
    |     +-- gera campanha determinística
    |     +-- muta bytes
    |     +-- classifica resultados
    |     +-- produz eventos
    |
    +-- visualização / timeline / JSON
    |
    +-- SerialBridge opcional
          |
          +-- protocolo versionado
          +-- firmware ESP32
                +-- backend criptográfico identificado
                +-- guardião real
                +-- telemetria e tempos
```

Por enquanto, as classes Python podem permanecer em `dashboard.py`. O
firmware terá diretório próprio.

## 5. Perfil OBC didático

O ESP32 não deve representar genericamente "um CubeSat". Ele representa um
OBC COTS educacional de uma missão 1U com orçamento operacional explícito.

O perfil inicial será:

| Recurso | Limite do experimento |
|---|---|
| CPU | Um core dedicado à aplicação; frequência inicial de 80 MHz |
| RAM | Sem PSRAM; pico medido e limite de 256 KiB para aplicação + criptografia |
| Flash da aplicação | Máximo de 1 MiB |
| Rádio integrado | Wi-Fi e Bluetooth desativados |
| Comunicação | UART; comandos curtos no firmware e respostas host de até 1024 caracteres |
| Telemetria | 1 Hz no modo nominal; eventos críticos imediatos |
| Persistência local | Ring buffer de até 128 eventos; exportação completa no host |
| Criptografia | Uma operação por vez; sem alocação dinâmica no caminho crítico |
| Saúde do sistema | Watchdog, brownout e free heap reportados |
| Energia | Duty cycle registrado; consumo só pode ser afirmado se for medido |

Os números são um perfil experimental, não uma afirmação de que todo OBC de
CubeSat possui esses limites. O ESP32 oferece até 240 MHz e 520 KiB de SRAM;
OBCs comerciais atuais podem ter mais memória, armazenamento redundante e
ECC. O interesse do perfil é avaliar comportamento sob orçamento controlado.

O experimento deve executar também um baseline a 240 MHz. Isso permite separar
"efeito da limitação escolhida" de "limitação intrínseca do algoritmo".

## 6. Ordem recomendada

A numeração dos documentos representa áreas de entrega, não uma dependência
linear rígida.

### Trilha PQC na placa

1. Manter `mlkem-native` v1.1.0 vendorizado como backend ML-KEM-512 da
   Wisdom. A antiga Etapa 04 foi consolidada neste roadmap.
2. Manter `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP`,
   `PQC_FAULT` e `PQC_BENCH` como comandos de bancada, fora dos blocos
   clicáveis da demo.
   Eles podem ser digitados no terminal textual avançado quando a placa estiver
   conectada.
3. Manter `MISSION CLASSIC|PQC|PQC_CRC32` como comando principal da
   apresentação para entrega de mensagem e comparação de custo.
4. Manter `PQC_INFO` como fonte de alvo, backend, fonte, commit, licença,
   perfil, tempo e memória.
5. Medição inicial de tempo, heap, heap mínimo e flash nos perfis `BASELINE` e
   `OBC-1U-LIMITED` concluída em 2026-06-17.
6. Integrar os resultados no dashboard/JSON sem exportar segredos completos.

### Trilha software demonstrável

1. Manter payload/CRC32 e ciphertext ML-KEM com confirmação de chave como
   base de coleta. A antiga Etapa 06 foi consolidada neste roadmap.
2. Manter `MISSION` como fluxo visual central da apresentação: `CLASSIC`,
   `PQC` e `PQC_CRC32`, com console/overlay de mensagem e painel
   `RESULTADOS` para a consolidação.
3. Manter `DEMO` como campanha visual automatizada de apoio. A antiga Etapa 07 foi
   consolidada neste roadmap.
4. Etapa 08 consolidada neste roadmap: robustez de software, aceitação serial,
   campanha de 30 minutos e projetor concluídos.

Etapas 01 a 08 já estão implementadas e seus markdowns foram removidos. A
trilha PQC agora possui backend real medido; a demo deve continuar separando
dado medido, simulação e pendência.

### Trilha hardware

1. Manter firmware, bridge serial e comandos de bancada estáveis.
2. Usar `MISSION CLASSIC|PQC|PQC_CRC32` como coleta curta principal antes da
   apresentação.
3. Usar `FAULT NONE|CRC32 payload_hex index mask` apenas como validação real
   do experimento de payload na Wisdom.
4. Medir `PROFILE BASELINE` e `PROFILE OBC-1U-LIMITED` antes de qualquer
   afirmação de limitação operacional.

### Fora do caminho crítico

- radiação física;
- corrupção de estado interno do KEM;
- ML-KEM-768 ou ML-KEM-1024;
- otimizações multicore além do necessário para a apresentação.

Esses itens continuam válidos como extensão. O núcleo agora é: Wisdom
conectada, ML-KEM-512 medido, bit-flips manuais, checksum ativável/desativável
e coleta JSON.

## 7. Etapas e critérios

### Etapa 01 - núcleo e efeitos visuais

Estado: **implementada**.

Entregas:

- `ExperimentEngine` com RNG própria;
- geração e aplicação de bit-flips em `bytearray`;
- eventos estruturados;
- efeitos visuais acionados pelo resultado real;
- nenhuma mudança de resultado feita pela camada de desenho.

Aceite:

- repetir a seed reproduz a mesma campanha;
- bytes antes/depois podem ser inspecionados;
- `RESET_SESSION` reinicia a campanha;
- testes headless cobrem classificação.

### Etapa 02 - timeline

Estado: **implementada**.

Entregas:

- timeline limitada por quantidade de eventos;
- cor por resultado, não por comando;
- legenda e contadores;
- layout testado em 1920x1080 e 1366x768.

Aceite:

- um evento gera exatamente um ponto;
- reset visual não apaga indevidamente dados da campanha;
- legenda permanece visível;
- layout validado por teste para 1920x1080 e 1366x768;
- não há overflow do painel.

### Etapa 03 - JSON

Estado: **implementada**.

Entregas:

- exportação atômica para `logs/`;
- schema versionado;
- seed, modo, alvo, posição, máscara, `campaign_run_id` e
  `campaign_trial_id`;
- overhead do guardião por evento: `guard_prepare_us`, `guard_verify_us` e
  `guard_overhead_us`;
- métricas agregadas: CPU ativo em janela de 5s, checksum e PQC;
- resumo derivado dos eventos;
- amostras de hardware com CPU, heap, heap mínimo, flash, perfil e tempo;
- proxy de energia explicitamente rotulado enquanto não houver medidor real;
- auto-save opcional.

Aceite:

- o JSON permite reproduzir cada mutação;
- exportar não altera a campanha;
- falha de escrita aparece na interface;
- `RESET_SESSION` não destrói resultados já registrados sem confirmação.

### Etapa 04 - firmware

Estado: **implementada para transporte, periféricos, payload/CRC32,
ML-KEM-512 real, `PQC_FAULT` e medição nos perfis baseline/limitado**.

Primeiro deve ser registrado:

- modelo exato da placa;
- arquitetura da CPU;
- RAM e flash disponíveis;
- framework escolhido;
- biblioteca/commit criptográfico;
- licença;
- resultado de um KAT ou vetor conhecido.

Depois do inventário, aplique o perfil OBC didático. Toda medição deve
registrar:

```text
cpu_mhz
active_cores
free_heap_before
min_free_heap
app_flash_bytes
radio_enabled
elapsed_us
```

Uma referência do projeto usa Kyber512-90s, ESP-IDF e ESP32-S3. Outra
implementa ML-KEM-512 em ESP32 no SBSeg 2025. Isso demonstra viabilidade
relacionada, mas não equivale a uma biblioteca pronta para a Wisdom e o
framework deste projeto. `pqm4` é direcionado a Cortex-M4.

O spike foi implementado nesta ordem:

1. `PING` e framing serial;
2. mutação de payload + CRC32;
3. ML-KEM-512 na placa ou fallback identificado de Kyber512;
4. KAT/vetor conhecido;
5. benchmark de KEM nos dois perfis;
6. somente então integração com a demo.

Medição real registrada em 2026-06-17:

| Perfil | CPU | Comando | Resultado |
|---|---:|---|---|
| `BASELINE` | 240 MHz | `PQC_BENCH 5` | `keygen_avg_us=3369`, `encap_avg_us=3878`, `decap_avg_us=5013`, `elapsed_us=62068`, `heap=202444`, `min_heap=198456` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24697`, `heap=202444`, `min_heap=198456`, `flash=4194304` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=39270` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_BENCH 5` | `keygen_avg_us=10101`, `encap_avg_us=11778`, `decap_avg_us=15214`, `elapsed_us=187371`, `heap=202444`, `min_heap=198456` |

Medição real pós-upload registrada em 2026-06-18:

| Perfil | CPU | Comando | Resultado |
|---|---:|---|---|
| `BASELINE` | 240 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=21892`, `heap=201612`, `min_heap=197624`, `flash=4194304` |
| `BASELINE` | 240 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=14117` |
| `BASELINE` | 240 MHz | `PQC_FAULT 0 0x01 CONFIRM` | `result=PROTOCOL_REJECT`, `confirmation=HMAC-SHA256`, `key_match=0`, `tag_ready=1`, `confirm_us=960`, `elapsed_us=46579` |
| `BASELINE` | 240 MHz | `PQC_FAULT 0 0x01 NONE` | `result=KEY_MISMATCH`, `confirmation=NONE`, `key_match=0`, `elapsed_us=35222` |
| `BASELINE` | 240 MHz | `PQC_BENCH 100` | `ok=100`, `keygen_avg_us=3301`, `encap_avg_us=3864`, `decap_avg_us=4988`, `elapsed_us=1217337`, `heap=201512`, `min_heap=197624` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24688`, `heap=201512`, `min_heap=197624`, `flash=4194304` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_BENCH 100` | `ok=100`, `keygen_avg_us=10045`, `encap_avg_us=11769`, `decap_avg_us=15194`, `elapsed_us=3706253`, `heap=201512`, `min_heap=197624` |
| `OBC-1U-LIMITED` | 80 MHz | `FAULT CRC32 5051432D534154 0 0x01` | `result=DETECTED_GUARD`, `crc_before=0xDFFEC3A1`, `crc_after=0x7989C815`, `elapsed_us=11` |

Fallback aceitável:

- emulador claramente rotulado;
- ou KEM real executado no notebook, com ESP32 responsável pela mutação e
  telemetria.

Fallback inaceitável:

- chamar bytes aleatórios ou AES de "ML-KEM";
- usar funções de hash diferentes em encapsulação/decapsulação e esperar
  segredos iguais;
- alegar conformidade FIPS sem vetores e versão identificada.

### Etapa 05 - bridge serial

Estado: **implementada para a demo atual**.

Requisitos:

- `pygame.init()` e display dentro de `main()`;
- import opcional de pyserial;
- leitura bloqueante com timeout em thread ou espera eficiente;
- fila thread-safe;
- estados `SIMULATED`, `CONNECTING`, `CONNECTED`, `LOST`;
- reconexão preservando o objeto bridge;
- fechamento idempotente;
- protocolo com versão e `request_id`.

Formato implementado para experimento de payload:

```text
PC>  V1|17|FAULT|CRC32|payload_hex|12|0x04
ESP> V1|17|RESULT|OK|result=DETECTED_GUARD|elapsed_us=83
```

Aceite:

- nenhuma resposta é atribuída ao comando errado;
- desconectar o cabo não trava o Pygame;
- falha inicial continua elegível para reconexão;
- modo simulado não depende de pyserial.

### Etapa 06 - guardião

Estado: **implementada para payload, checksum ativável/desativável,
ciphertext ML-KEM com confirmação de chave, overhead do guardião e exportação
PQC**.

Implementação mínima:

1. compute o valor de referência antes da falha;
2. aplique a falha;
3. compute novamente;
4. compare;
5. registre cobertura, overhead e métricas PQC exportáveis.

Implementado no dashboard:

- `CHECKSUM ON|OFF|TOGGLE|STATUS`;
- `GUARD NONE|CRC32`;
- `INJECT_FAULT` e `BIT_FLIP` respeitando o guardião ativo;
- `CRC_CHECK` como atalho de uma tentativa forçada com CRC32;
- `PQC_FAULT index mask [CONFIRM|NONE]` no firmware para aplicar bit-flip em
  ciphertext ML-KEM real;
- confirmação de chave por HMAC-SHA256 usando o segredo derivado, com
  `PROTOCOL_REJECT` quando os tags não batem;
- eventos JSON com `guard_prepare_us`, `guard_verify_us` e
  `guard_overhead_us` para medir overhead do CRC32 em vez de inventar custo;
- amostras `PQC_*` exportadas em JSON com tempos, KAT, `key_match`,
  tamanhos, `key_confirmed`, `tag_match` e CRCs curtos, sem segredos
  completos.
- comando `MISSION CLASSIC|PQC|PQC_CRC32` exportado em
  `metrics.mission.scenarios`, permitindo comparar tempo total, subtempos,
  bytes, heap, `key_match`, `aead_match`, `tag_match`, `crc_match` e `result`.

O firmware antigo proposto chamava `checkIntegrity()` sem inicializar os
valores armazenados. Isso deve ser impedido por uma API explícita:

```text
guard.prepare(data)
mutate(data, fault)
guard.verify(data)
```

Aceite:

- teste conhecido para cada checksum;
- single-bit detectado em toda posição coberta;
- campanhas multi-bit documentadas;
- overhead do guardião medido por evento;
- nenhuma taxa é hard-coded como resultado científico.

### Etapa 07 - modo apresentação

Estado: **implementada no dashboard**.

A demo automatizada é um segmento de cerca de 45-60 segundos dentro da aula
de 20 minutos.

Implementado:

- `DEMO [n]`, `DEMO_PAUSE`, `DEMO_RESUME`, `DEMO_STOP` e `DEMO_RESTART`;
- estados `RUNNING_A`, `SNAPSHOT_A`, `RUNNING_B`, `RESULTS`, `PAUSED` e
  `STOPPED`;
- mesma lista de fault specs em A (`NONE`) e B (`CRC32`);
- overlay calculado a partir dos eventos, com silenciosas em A, detectadas em
  B, taxa de detecção e overhead médio do CRC32;
- exportação JSON automática ao fim da demo;
- testes automatizados para A/B, pausa, retomada e parada.

### Etapa 08 - fechamento

Estado: **implementada e validada em software, hardware e projetor**.

Entregas:

- splash opcional com `--no-splash` implementado;
- help completo mantido no terminal avançado, com comandos de dashboard e
  firmware documentados;
- resumo, auto-save no reset/fechamento e JSON versionado implementados;
- tratamento de exceções com cleanup sem mascarar traceback implementado;
- cache de superfícies grandes e métrica de memória/FPS do host implementados;
- polling automático de `TELEMETRY` desligado no dashboard; telemetria fica
  manual pelo terminal/HELP;
- teste headless de layout em 1920x1080 e 1366x768 implementado;
- runner `tools/stage8_acceptance.py` implementado para aceitação serial,
  benchmark, campanha prolongada e demo headless com exportação JSON;
- runner `tools/final_metrics_battery.py` implementado para nova coleta longa
  de métricas finais, com ciclos balanceados por perfil, resumo estatístico e
  JSON pronto para consolidação em tabelas da apresentação;
- runner `tools/aes_gcm_metrics_battery.py` implementado para nova bateria
  oficial da versão cifrada com AES-128-GCM, incluindo validações específicas
  de AEAD, nonce, tag e ciphertext;
- campanha final de métricas validada por
  `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`;
- projetor validado por confirmação do usuário em 2026-06-18, após ajuste
  visual para reduzir botões e métricas;
- roteiro de 20 minutos, onboarding do dashboard e painel de resultados
  descritos em `APRESENTACAO_ROTEIRO.md`;
- limitações científicas registradas no README, roadmap e roteiro.

Não use a expressão "nenhum crash possível". O critério correto é "nenhuma
falha conhecida nos cenários testados".

## 8. Cronograma sugerido

### Próximos cortes

1. Levar para a fala e para o botão de resultados a distinção: checksum protege transporte,
   confirmação de chave protege aceitação de sessão, e consumo de energia só
   será afirmado se houver medição externa.

## 9. Riscos e decisões

| Risco | Mitigação |
|---|---|
| Regressão de build/flash do ML-KEM na placa | Manter `mlkem-native` vendorizado, KAT host e build PlatformIO como validação obrigatória. |
| Resposta serial grande de `PQC_FAULT` rejeitada no host | Limite de resposta do parser aumentado para 1024 caracteres e coberto por testes do protocolo. |
| Biblioteca implementa Kyber antigo, não FIPS 203 | Identificar variante e não chamá-la de ML-KEM. |
| Cinco amostras geram conclusão fraca | Usar campanha determinística maior na coleta e subconjunto visual na demo. |
| Serial perde ou reordena respostas | `request_id`, timeout e parser estrito. |
| Layout não cabe no projetor | Testar duas resoluções e reduzir conteúdo, não a fonte indiscriminadamente. |
| Resultado simulado é confundido com medição | Campo `mode` em UI e JSON. |
| Limite artificial é tratado como característica de todo CubeSat | Nomear o perfil e comparar com o baseline sem limitação. |

## 10. Entrega final

### Obrigatória

- dashboard funcional sem hardware e com hardware conectado;
- entrega de mensagem demonstrável em `CLASSIC`, `PQC` e `PQC_CRC32`;
- popup independente e arrastável por cenário para comparação visual lado a lado;
- campanha reproduzível;
- bateria final dedicada em `tools/final_metrics_battery.py` para gerar
  resultados estatísticos novos quando necessário;
- comparação A/B baseada em bytes;
- JSON;
- demo automatizada;
- documentação das limitações;
- onboarding, botão de resultados e roteiro.
- banco de perguntas e respostas para treino da defesa.

### Hardware já entregue para o MVP

- ESP32 conectado por bridge serial;
- ML-KEM-512 real;
- `MISSION CLASSIC|PQC|PQC_CRC32` compilado no firmware para coleta
  comparativa;
- `PQC_FAULT` real em ciphertext ML-KEM com confirmação de chave;
- `PQC_BENCH 100` medido em `BASELINE` e `OBC-1U-LIMITED`;
- medição de tempo e memória no dispositivo.

O hardware, a campanha prolongada anterior, o projetor validado, `MISSION` e o
modo `DEMO` sustentam a demonstração.
O guia didático, o roteiro, a metodologia de métricas e os limites científicos
já estão documentados em `GUIA_DIDATICO_APRESENTACAO.md`,
`METRICAS_CONSOLIDADAS.md` e `APRESENTACAO_ROTEIRO.md`.

## 11. Referências técnicas para decisões

- NIST FIPS 203:
  <https://csrc.nist.gov/pubs/fips/203/final>
- Implementação de Kyber512-90s em ESP32-S3:
  <https://arxiv.org/abs/2503.10207>
- ML-KEM-512 multicore em ESP32:
  <https://doi.org/10.5753/sbseg.2025.9783>
- pqm4, alvo ARM Cortex-M4:
  <https://github.com/mupq/pqm4>
- liboqs, biblioteca de prototipagem:
  <https://github.com/open-quantum-safe/liboqs>
- ESP32 Series Datasheet:
  <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>
- Exemplo de OBC comercial com Cortex-M7, FRAM ECC e armazenamento redundante:
  <https://www.endurosat.com/cubesat-store/cubesat-obc/onboard-computer-obc/>
