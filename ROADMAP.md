# Roadmap consolidado - PQC-SAT

Versão revisada em 2026-06-18.

## 1. Visão geral

O PQC-SAT deve demonstrar, em uma atividade de aproximadamente 20 minutos,
que segurança embarcada depende tanto do algoritmo criptográfico quanto da
integridade da implementação e do protocolo.

A interface visual já existe e o primeiro experimento mensurável também: o
dashboard muta um payload determinístico, registra eventos e compara os
cenários `NONE` e `CRC32`. O backend PQC real já está instalado na Wisdom com
ML-KEM-512 e medição nos perfis `BASELINE` e `OBC-1U-LIMITED`. O firmware
também executa bit-flip manual em ciphertext ML-KEM e classifica o efeito com
comparação de segredos ou confirmação HMAC-SHA256 da chave derivada. O modo
`DEMO` automatiza a apresentação A/B. A etapa 8 foi consolidada com
fechamento de software, roteiro, material-base, aceitação serial, campanha
prolongada e validação física de projetor/legibilidade confirmada pelo usuário.

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
| Interface serial PQC | `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP`, `PQC_FAULT` e `PQC_BENCH` funcionais |
| Medição PQC na placa | `PQC_BENCH 100` medido em `BASELINE` e `OBC-1U-LIMITED`; `PQC_KAT` passou no hardware gravado |
| Falha em ciphertext ML-KEM | `PQC_FAULT index mask [CONFIRM|NONE]` validado na placa e exportado no JSON |
| CRC/checksum real | CRC32 funcional no dashboard e no firmware |
| ESP32/serial | Funcional com `HELLO`, `STATUS`, sensores, OLED e `FAULT` |
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
  apresentação e hoje expõem apenas CPU, RAM, PQC e checksum perto da animação.
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
  cache de superfícies grandes, faixa superior reduzida a CPU, RAM, PQC e
  checksum, exportação de métricas do processo e teste headless para
  1920x1080 e 1366x768.
- 2026-06-18: criado `APRESENTACAO_ROTEIRO.md` com cinco slides, roteiro de
  20 minutos, sequência de comandos da demo, limites científicos e checklist
  pré-apresentação.
- 2026-06-18: verificação final detectou a Wisdom em `/dev/ttyUSB0` como
  CP2102N/Silicon Labs. Após liberação da porta, a aceitação de hardware da
  etapa 8 passou com `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json`:
  1.816,87 s de execução, 77 registros, 0 falhas, 60 comandos no long-run,
  2 benchmarks PQC, 13 `DETECTED_GUARD` em payload CRC32 e demo headless do
  dashboard com 5/5 falhas silenciosas em A e 5/5 detectadas em B.
- 2026-06-18: polimento final de apresentação removeu polling automático de
  `TELEMETRY`, reduziu os blocos clicáveis aos comandos centrais da demo e
  manteve comandos de bancada no HELP/terminal textual.
- 2026-06-18: criado `GUIA_DIDATICO_APRESENTACAO.md` como material completo
  de estudo e condução da apresentação para público leigo em criptografia,
  consolidando objetivo, passo a passo, resultados, comandos, limites e fala
  sugerida.

O dashboard já pode demonstrar `SILENT` versus `DETECTED_GUARD` em payload,
executar `RUN_BATTERY` A/B, executar `DEMO` com overlay calculado e exportar
sessões em JSON. A coleta técnica, a campanha prolongada e a validação de
projetor/legibilidade já foram concluídas para a apresentação atual.

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
3. Manter `PQC_INFO` como fonte de alvo, backend, fonte, commit, licença,
   perfil, tempo e memória.
4. Medição inicial de tempo, heap, heap mínimo e flash nos perfis `BASELINE` e
   `OBC-1U-LIMITED` concluída em 2026-06-17.
5. Integrar os resultados no dashboard/JSON sem exportar segredos completos.

### Trilha software demonstrável

1. Manter payload/CRC32 e ciphertext ML-KEM com confirmação de chave como
   base de coleta. A antiga Etapa 06 foi consolidada neste roadmap.
2. Manter `DEMO` como campanha visual automatizada. A antiga Etapa 07 foi
   consolidada neste roadmap.
3. Etapa 08 consolidada neste roadmap: robustez de software, aceitação serial,
   campanha de 30 minutos e projetor concluídos.

Etapas 01 a 08 já estão implementadas e seus markdowns foram removidos. A
trilha PQC agora possui backend real medido; a demo deve continuar separando
dado medido, simulação e pendência.

### Trilha hardware

1. Manter firmware, bridge serial e comandos de bancada estáveis.
2. Usar `FAULT NONE|CRC32 payload_hex index mask` apenas como validação real
   do experimento de payload na Wisdom.
3. Medir `PROFILE BASELINE` e `PROFILE OBC-1U-LIMITED` antes de qualquer
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
- campanha prolongada validada por
  `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json`;
- projetor validado por confirmação do usuário em 2026-06-18, após ajuste
  visual para reduzir botões e métricas;
- roteiro de 20 minutos e base de até cinco slides em
  `APRESENTACAO_ROTEIRO.md`;
- limitações científicas registradas no README, roadmap e roteiro.

Não use a expressão "nenhum crash possível". O critério correto é "nenhuma
falha conhecida nos cenários testados".

## 8. Cronograma sugerido

### Próximos cortes

1. Levar para o relatório/slides a distinção: checksum protege transporte,
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
- campanha reproduzível;
- comparação A/B baseada em bytes;
- JSON;
- demo automatizada;
- documentação das limitações;
- slides e roteiro.

### Hardware já entregue para o MVP

- ESP32 conectado por bridge serial;
- ML-KEM-512 real;
- `PQC_FAULT` real em ciphertext ML-KEM com confirmação de chave;
- `PQC_BENCH 100` medido em `BASELINE` e `OBC-1U-LIMITED`;
- medição de tempo e memória no dispositivo.

O hardware, a campanha prolongada, o projetor validado e o modo `DEMO`
sustentam a demonstração.
O guia didático, o roteiro, a base de slides e os limites científicos já estão
documentados em `GUIA_DIDATICO_APRESENTACAO.md` e
`APRESENTACAO_ROTEIRO.md`.

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
