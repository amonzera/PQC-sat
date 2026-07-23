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

O programa público tem uma única camada operacional: jogo Pygame conectado à
Wisdom real. Fixture e relógio sintético existem somente em testes e evidências
offline; nunca são opções do entrypoint de produção.

Nunca apresente uma funcionalidade planejada como concluída.

## 2. Fontes de verdade

Use esta precedência quando houver divergência:

1. comportamento verificado por testes;
2. `docs/ROADMAP.md`, que consolida o plano técnico;
3. `docs/projeto_final_pqc_esp32_cubesat.docx`, que define o objetivo acadêmico;
4. documentos `etapa_*.md`, que detalham tarefas;
5. este guia e o `README.md`.

Se um documento de etapa divergir do roadmap, corrija o documento antes de
implementar.

## 3. Estado atual verificado

### Implementado

- interface única fullscreen em `dashboard.py`; somente o standby de busca
  funciona sem conexão, e o jogo exige a Wisdom validada;
- Terra, CubeSat, estrelas, nebulosa e partículas procedurais;
- fluxo público por cartões, 14 estados e confirmações por D27 ou faixa verde;
- firmware serial `V1` para a RoboCore BlackBoard Wisdom;
- bridge serial Python e console `tools/serial_console.py`;
- `dashboard.py` abre o standby e sonda todas as portas em worker por `HELLO`; exige
  `node=PQC-SAT-WISDOM`, `board=BlackBoard-Wisdom`, `proto=V1`,
  `game=STAGED_V1` e `uptime_ms` válido antes de mostrar a abertura narrativa;
- seed determinística exclusiva para incidentes de teste (`42`);
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
- guardião selecionável no jogo como `NONE` ou `CRC32`;
- amostras `PQC_*` exportadas em JSON com timings, KAT, `key_match`,
  `key_confirmed`, `tag_match`, tamanhos e CRCs curtos, sem segredos
  completos;
- eventos de payload exportam overhead do guardião em `guard_prepare_us`,
  `guard_verify_us` e `guard_overhead_us`.
- interface mostra tempos, bytes e heap apenas após respostas `GAME_*` reais;
- `PQC_FAULT index mask [CONFIRM|NONE]` implementado no firmware para
  corromper ciphertext ML-KEM real e classificar `KEY_MISMATCH` ou
  `PROTOCOL_REJECT` por confirmação HMAC-SHA256 da chave derivada.
- etapa 8 de software implementada com standby opcional, `--no-splash`,
  autosave no fechamento, cleanup preservando traceback, cache de superfícies
  grandes, faixa superior focada em CPU/RAM e testes
  headless para 1920x1080 e 1366x768;
- telemetria automática desligada no dashboard; `TELEMETRY`, `PING`, LED, RGB,
  bargraph, sensores e comandos de bancada ficam no HELP/terminal textual, não
  como botões da apresentação;
- aceitação hardware da etapa 8 validada e consolidada em
  `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`, com 1.817,23 s,
  83 registros, 0 falhas, 27 MISSION runs, 2 benchmarks PQC e demo headless OK;
- coleta oficial pós-AES-GCM concluída em
  `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`, com 1.038
  registros, 0 falhas, 600 MISSION runs, 6 benchmarks PQC e 400 testes de
  falha; essa é a fonte principal atual para `RESULTADOS`;
- preparação da apresentação centralizada em
  `GUIA_FINAL_APRESENTACAO.md`, com fundamentos, resultados, roteiro de demo,
  limites científicos e perguntas de defesa;
- metodologia de métricas consolidada em `docs/METRICAS_CONSOLIDADAS.md`;
- projetor/legibilidade confirmados pelo usuário em 2026-06-18 após ajuste de
  botões e métricas do dashboard.
- modo estande SBPC em release candidate de software na branch
  `sbpc-stand-demo`, com máquina de estados guiada, fixture oficial offline,
  logs JSONL, scripts operacionais, screenshots, vídeo de contingência, 50
  ciclos simulados e dois smokes completos na Wisdom em 2026-07-20;
- os smokes reais confirmaram CLASSIC/PQC a 240 MHz, PQC a 80 MHz, leitura do
  potenciômetro e a mesma falha em NONE/CRC32; o ciclo com timing de produção
  chegou a `SUMMARY` em 51,55 s;
- uma sessão adicional de 20 ciclos reais acelerados concluiu 60 missões e 40
  falhas sem erro, mas usou acionamento administrativo e não substitui o gate
  físico longo.
- arquitetura Python modular com `dashboard.py` como único entrypoint;
  `stand_demo.py`, dashboard manual legado, launchers Bash e flags de simulação
  de produção foram removidos; limites estão em
  `docs/DASHBOARD_ARCHITECTURE.md`;
- `Missão Bit Flip` oferece três missões, 240/80 MHz, chave CLASSIC/PQC,
  guardião NONE/CRC32, incidente oculto, diagnóstico e resposta operacional;
- comando `INVESTIGATE` implementado no firmware para instrumentar, na mesma
  execução, CRC do quadro, AES-GCM e CRC da aplicação em `NORMAL`,
  `CHANNEL_BITFLIP`, `TAMPER` e `RX_MEMORY`; build local pós-mudança usa 17,3%
  de RAM e 70,6% de flash.
- validação investigativa concluída em 2026-07-21 com 158 testes, soak offline
  de 50 ciclos, 22 screenshots e vídeo rotulado de 44 s; o firmware atual foi
  gravado na Wisdom e um smoke investigativo real percorreu `ATTRACT` até
  `SUMMARY`, com `CHANNEL_BITFLIP`/`PQC_CRC32` classificado `FRAME_REJECT`,
  zero eventos rejeitados e invariantes do log aprovados; o dashboard de
  produção conectado permaneceu oito segundos em `ATTRACT`, sem transição
  espontânea;
- o diagnóstico real executou os quatro casos curtos de `INVESTIGATE`; duas
  janelas assistidas de 30 s e 45 s não observaram `BUTTON_PING`, portanto o
  acionamento/fiação de D27 continua pendente e o smoke administrativo não é
  aceite físico longo.
- jogo didático `STAGED_V1` implementado em software com 14 estados: toque em
  cartão apenas seleciona, D27 ou faixa verde confirmam cada transição, A39 seleciona o bit, resposta
  serial e animação apenas liberam a confirmação, sem timeout ou reset público;
- primeiro handshake fecha automaticamente a busca e mostra a abertura com
  Terra/CubeSat, chamada única e botão `INICIAR MISSÃO`; clique ou D27 abrem
  diretamente as escolhas; depois do replay validado, a própria mensagem pode ser
  arrastada por estações explicadas sem alterar o controlador ou o gate de confirmação;
- standby permanece até `HELLO STAGED_V1` e fecha automaticamente; a abertura
  narrativa permanece até clique ou D27, e o controle de tela usa `ANALOG POT` antes
  de confirmar `PROTECT`;
- cartões de escolha são quadrados, sem subtítulos internos, com títulos e
  artes causais em destaque; a torre sobre a Terra foi removida e o CubeSat
  móvel preservado com sorriso angular;
- protocolo transacional `GAME_BEGIN`, `GAME_PROTECT`, `GAME_TRANSMIT`,
  `GAME_VERIFY`, `GAME_RETRY`, `GAME_END` e `GAME_ABORT` implementado no
  firmware, preservando `INVESTIGATE` e o fluxo legado; `CLASSIC_CRC32` permite
  escolher modo de chave e CRC da aplicação independentemente;
- validação host atual do jogo por etapas concluída com 97 testes, matriz de 32
  casos, soak offline de 50 partidas, 66 capturas, vídeo rotulado e benchmark
  abaixo de 16,667 ms em ambas as resoluções; o firmware candidato compila com
  57.332 B de RAM e 932.173 B de flash, mas ainda não foi gravado nem executado
  na Wisdom;
- corrigida no candidato a incompatibilidade observada em hardware na qual
  `ANALOG POT` retornava `BAD_GAME_STATE` durante `PROTECT` e apagava a sessão;
  a leitura A39 agora é a única consulta não `GAME_*` permitida e a regressão
  exige que `GAME_TRANSMIT` continue válido depois dela; falta novo flash para
  validar a correção na placa;
- `tools/firmware_deploy.py` prepara build e upload sem Bash: a gravação só
  ocorre com `--upload`, depois de provar a identidade da Wisdom por `HELLO`, e
  o comando só termina com sucesso após validar `game=STAGED_V1`;
- sondagem real em 2026-07-22 reconheceu a Wisdom pelo caminho estável
  `/dev/serial/by-id`, mas confirmou que a revisão atualmente gravada ainda não
  anuncia `game=STAGED_V1`; nenhum upload foi executado.

### Não implementado
Nenhuma etapa técnica permanece aberta para o MVP original do seminário. O
jogo `STAGED_V1` ainda precisa de flash, handshake e smoke reais, `BUTTON_PING`
observado, partida inteira por D27, ensaio no monitor definitivo, aceite físico
longo e teste de compreensão com cinco pessoas; não declarar a extensão pronta
antes de fechar esses gates em `docs/stand/FINAL_VALIDATION.md`.

## 4. Stack

### Atual

| Componente | Tecnologia |
|---|---|
| Linguagem validada | Python 3.14.6 |
| Renderização | pygame-ce 2.5.7 |
| Aplicação | pacote `pqc_sat/`; `dashboard.py` é fachada/entrypoint |
| Assets | desenho procedural, sem arquivos externos |
| Serial | pyserial 3.5+ obrigatório em produção |
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
- Mantenha `dashboard.py` como fachada fina e entrypoint estável. Código novo
  deve respeitar as camadas de `pqc_sat/` documentadas em
  `docs/DASHBOARD_ARCHITECTURE.md`; não reintroduza implementação no entrypoint.
- Firmware pode e deve ter arquivos próprios sob `firmware/`.
- Use constantes `C_*` para cores reutilizadas.
- Use `pygame.SRCALPHA` quando transparência for necessária.
- Não bloqueie o loop principal com `sleep`, I/O serial ou criptografia longa.
- Não carregue imagens, sons ou fontes externas sem decisão explícita.
- Não mostre `ESP32 ONLINE`, `CRC ON` ou `ML-KEM ativo` sem evidência real.
- `dashboard.py` é a única superfície pública: a busca sai automaticamente por
  `HELLO`; na abertura, `INICIAR MISSÃO` ou D27 avançam; no jogo, cartão
  seleciona e o controle contextual ou D27 confirmam.
  Não reintroduza painel manual, console visual, onboarding paralelo, segundo
  entrypoint ou seletor de fluxo.
- Produção exige a Wisdom. Não adicione fallback, fixture, tecla de D27 ou
  métricas simuladas ao parser/CLI público.
- Todo comando útil que não pertença à apresentação deve continuar registrado
  para uso técnico em outro lugar: `docs/hardware_command_reference.md`,
  `tools/serial_console.py --all-commands`, documentação de etapa ou scripts de
  bancada. Não apague capacidade técnica só porque ela não aparece no
  conjunto de botões; apenas separe a superfície visual da demo da superfície
  textual de engenharia.
- Fixtures podem ser usadas somente por testes e ferramentas offline
  explicitamente rotuladas; nunca pelo composition root em `pqc_sat/cli.py`.
- Os logs oficiais e métricas consolidadas do projeto devem ser registrados e
  coletados exclusivamente através de baterias de testes longas e controladas
  no terminal (como `tools/final_metrics_battery.py` para resultados finais e
  `tools/stage8_acceptance.py` para aceite/regressão), e NUNCA a partir de
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
  Para gerar uma nova coleta estatística final, indique ao operador:
  `python3 tools/aes_gcm_metrics_battery.py --port /dev/ttyUSB0 --timeout 12 --cycles 100 --pause 0.25 --bench-repeats 3 --bench-rounds 100`.
  O resumo esperado inclui `official_candidate=true`, `failed=0`,
  `mission_runs=600`, `pqc_bench_runs=6`, `fault_runs=400`,
  `aead_failures=0` e `non_aes_gcm_records=0`.
  Para repetir o aceite longo deste projeto, indique ao operador:
  `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30`.
  O resumo esperado é `ok=true`, `failed=0` e `pqc_bench_runs=2`; depois do
  comando `MISSION`, também deve haver
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

- `CLASSIC` é baseline clássico simétrico com `AES-128-GCM`, chave efêmera e
  nonce aleatório gerados na Wisdom; não o apresente como ECDH nem como
  criptografia assimétrica clássica completa;
- `PQC` é ML-KEM-512 para estabelecer segredo e `AES-128-GCM` para cifrar e
  autenticar a mensagem;
- `PQC_CRC32` adiciona CRC32 ao plaintext protegido antes da cifragem AES-GCM;
- compare `elapsed_us`, `bytes_total`, `heap`, `min_heap`, `key_match`,
  `aead_match`, `tag_match`, `crc_match` e `result`;
- os resultados consolidados anteriores à implementação de AES-GCM devem ser
  tratados como históricos pré-AES até uma nova bateria oficial;
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
python3 -m compileall -q pqc_sat
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

1. Flashar o firmware candidato e confirmar `HELLO game=STAGED_V1` na Wisdom.
2. Executar diagnóstico curto, observar `BUTTON_PING` com A39 e validar ordem/ID.
3. Percorrer uma partida física completa, inclusive retry, somente com D27.
4. Provar permanência sem avanço em cada estado e ensaiar no monitor definitivo.
5. Executar pelo operador o gate longo descrito em `docs/stand/RUNBOOK.md`.
6. Testar compreensão com cinco visitantes e fechar a validação final.

Última revisão: 2026-07-22.
