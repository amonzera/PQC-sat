# Validação final — jogo didático `STAGED_V1/FAIR_V1`

Última revisão: 2026-07-26.

## Decisão atual

Estado: **release candidate de software; não aprovado para uso público**.

O jogo por etapas está implementado e validado no host/fixture. O firmware
FAIR atual, incluindo `SESSION_BENCH`, compila do zero com a árvore wolfSSL
5.9.2 identificada. A revisão final `9eba850f…32a18d` foi gravada e o
diagnóstico curto completo passou com 27 registros: ECDH/ML-KEM, sessões,
falhas, caminho transacional, A39, retry, compatibilidade e `BUTTON_PING`.
Evidências físicas anteriores de
`INVESTIGATE` e do fluxo de nove estados continuam válidas como histórico, mas
não validam o par ECDH/ML-KEM no wolfCrypt, os novos comandos `GAME_*`, as
confirmações D27/tela por partida ou o novo debrief.

## Evidência de software desta revisão

| Verificação | Resultado | Evidência |
|---|---|---|
| suíte integrada | PASS software | testes host cobrem busca, reconexão, controle de tela, sorteio reproduzível, pausas, contrato FAIR, legado e jogo por etapas |
| matriz científica | PASS | 2 perfis × 2 modos de chave × 2 guardiões × 4 incidentes = 32 casos |
| confirmação explícita | PASS no modelo | transições v2 exigem `button_confirmed` de origem `physical|screen`; resposta/animação não avançam |
| busca automática | PASS no host/modelo | dashboard permanece aberto sem porta; somente `HELLO game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` fecha o standby |
| narrativa direta | PASS no modelo | Terra/CubeSat, chamada única e `INICIAR MISSÃO`; clique ou D27 abrem as escolhas sem tela intermediária |
| reconexão | PASS no modelo | qualquer queda mostra busca; novo handshake apaga a partida e volta automaticamente à narrativa |
| incidente probabilístico | PASS software | 70% de chance; causas públicas igualmente ponderadas; seed, rolls e vetor registrados |
| ausência de timeout público | PASS | estados permanecem parados; flags públicas desabilitadas |
| retransmissão | PASS no hardware curto | `same_payload=1`, `fresh_key=1`, `fresh_nonce=1`, `result=DELIVERED` |
| soak offline | PASS software | 50/50 partidas: 12 normais, 24 radiações simuladas, 14 invasões, 775 confirmações, 275 `GAME_*`, zero erros e zero crescimento RSS |
| renderização | PASS software | por resolução: busca + 17 estados + 18 quadros dos replays; tela de tutorial ausente |
| orçamento médio | PASS host | interface completa: 9,960 ms e 15,730 ms; limite 16,667 ms no host headless |
| vídeo offline | PASS | `staged_game_test_fixture.mp4`, permanentemente rotulado como fixture sem hardware |
| smoke FAIR anterior | FAIL parcial na placa | `logs/stand/diagnostics/20260723T152842Z_stand_diagnostic.json`: handshake, perfil, `KEX_INFO` e ML-KEM passaram; ECDH falhou no setup em 29 µs, antes de initiator/responder |
| segundo smoke FAIR | PASS criptográfico; FAIL no protocolo | `logs/stand/diagnostics/20260723T155138Z_stand_diagnostic.json`: `KEX_BENCH`, `MISSION` e `SESSION_BENCH` passaram para ECDH/ML-KEM; `FAULT` passou; `GAME_BEGIN` passou; `GAME_PROTECT` tinha `experiment` duplicado |
| firmware FAIR corrigido | PASS em build, flash e smoke curto | wolfSSL 5.9.2, 59.020 B RAM, 1.005.497 B flash, binário 1.012.080 B, SHA-256 `9eba850f…32a18d`; manifesto `20260723T155737Z`; diagnóstico `20260723T160223Z` com `result=PASS` |
| firmware legado atual | PASS apenas na compilação | ambiente isolado de wolfSSL: 59.004 B RAM (18,0%), 940.421 B flash (71,7%), binário 946.992 B, SHA-256 `8cfd7746…d152188`; nenhum upload |

O registro consolidado fica em
`docs/stand/evidence/software_validation.json`; esse artefato é anterior ao
perfil FAIR e permanece como histórico da UI. Capturas ficam em
`states_staged_game/`, `states_staged_game_1920x1080/` e nos diretórios
`states_staged_game_replay*`; o soak fica em
`staged_game_soak.json`.

## Critérios automatizados cobertos

- toque em cartão seleciona sem mudar de fase; toque na faixa verde confirma;
- busca permanece sem placa e fecha automaticamente por handshake válido;
- D27 durante a busca não confirma a narrativa; depois dela, `INICIAR MISSÃO`
  ou D27 abrem diretamente a escolha da missão;
- D27 sem seleção não avança nem consome o próximo debounce;
- toda transição para a frente possui confirmação D27/tela correspondente no log;
- a faixa verde percorre todos os estados sem solicitar A39;
- resposta serial e término de animação apenas liberam a confirmação;
- pacote só pode ser arrastado depois do replay automático e o gesto não muda
  controlador, resultado, estado ou liberação da confirmação;
- D27 antigo, repetido, durante comando, animação ou guarda é rejeitado;
- quatro proteções, quatro incidentes e dois perfis obedecem à tabela;
- `RX_MEMORY/NONE` produz `SILENT_CORRUPTION`;
- `RX_MEMORY/CRC32` produz `APP_REJECT`;
- `GAME_RETRY` usa o mesmo payload e fingerprints novos de chave/nonce;
- rejeição criptográfica bloqueia `ACCEPT`;
- erro, desconexão, ordem incorreta e `Home` apagam resultados da partida;
- desconexão cobre qualquer estado com a busca e a reconexão retorna à
  narrativa sem reutilizar resultado;
- nenhum timeout de interação ou debrief altera a tela;
- fixture, log V1, fluxo legado, `INVESTIGATE`, comandos de bancada e fachadas
  continuam compatíveis.

## Fronteira da evidência física existente

Já foi verificado em 2026-07-21, com o firmware investigativo anterior:

- Wisdom identificada em `/dev/ttyUSB0`;
- firmware `INVESTIGATE` gravado;
- quatro incidentes curtos e um smoke administrativo até `SUMMARY`;
- dashboard conectado parado em `ATTRACT` por oito segundos;
- duas janelas de 30 s e 45 s sem observar `BUTTON_PING`.

Isso comprova a base AES-GCM/ML-KEM/CRC e o comando legado naquela revisão.
Em 2026-07-23, a revisão FAIR seguinte também comprovou na Wisdom:

- `HELLO game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`;
- `STATUS`, `ANALOG POT`, `PROFILE BASELINE` e `KEX_INFO`;
- uma rodada ML-KEM-512 completa no wolfCrypt, com `mlkem_ok=1`;
- falha ECDH no primeiro `wc_ecc_make_key_ex`, observada como
  `ecdh_ok=0`, `setup_us=29` e demais estágios zerados.

O código do wolfSSL confirmou a causa: `WOLFSSL_SP_MATH` sem
`WOLFSSL_HAVE_SP_ECC` retorna `WC_KEY_SIZE_E (-234)` para P-256. A revisão
seguinte, gravada pelo manifesto
`logs/firmware/20260723T155122Z_firmware_deploy_dev-ttyUSB0.json`, comprovou
na placa:

- `KEX_BENCH 1` com `ecdh_ok=1`, `mlkem_ok=1` e ambos os códigos de retorno
  zerados;
- `MISSION ECDH`, `MISSION MLKEM` e ambos os `SESSION_BENCH ... 1`;
- `FAULT NONE` como corrupção silenciosa e `FAULT CRC32` como detecção;
- rejeição esperada de `GAME_VERIFY` fora de ordem e `GAME_BEGIN` válido.

O comando seguinte, `GAME_PROTECT`, emitia `experiment` duas vezes: uma no
bloco comum e outra nos metadados FAIR. A revisão final preservou o primeiro
campo, omitiu apenas a duplicata e foi gravada pelo manifesto
`logs/firmware/20260723T155737Z_firmware_deploy_dev-ttyUSB0.json`.
O diagnóstico `logs/stand/diagnostics/20260723T160223Z_stand_diagnostic.json`
comprovou:

- `result=PASS` em 27 registros;
- `KEX_BENCH`, missões e sessões ECDH/ML-KEM;
- `GAME_BEGIN -> PROTECT -> ANALOG POT -> TRANSMIT -> VERIFY -> RETRY -> END`;
- `RX_MEMORY/CRC32` classificado `APP_REJECT`;
- retry com mesmo payload, chave e nonce novos e entrega final;
- quatro casos `INVESTIGATE`;
- `BUTTON_PING` físico com `button=1`, `pot=1469` e uptime fresco.

Essa evidência ainda não comprova repouso `button=0`, uma partida visual
integral por D27 ou faixa verde, `GAME_ABORT`, matriz física, permanência em
todos os 17 estados, baterias longas ou compreensão de visitantes.

## Gates físicos obrigatórios

| Gate | Estado | Critério de fechamento |
|---|---|---|
| flash do candidato corrigido | PASS | binário SHA-256 `9eba850f…32a18d` gravado |
| manifesto de deploy | PASS | `20260723T155737Z_firmware_deploy_dev-ttyUSB0.json`, hashes, porta e handshakes válidos |
| handshake novo | PASS | `HELLO ... game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` |
| backend comum | PASS | `KEX_INFO` confirmou wolfCrypt, HKDF-SHA256, AES-128-GCM, `target_asm=0` e `hw_crypto=0` |
| benchmark pareado curto | PASS | `KEX_BENCH 1`, `MISSION ECDH|MLKEM` e `SESSION_BENCH ECDH|MLKEM 1` fecharam sem erro |
| bateria FAIR oficial | FAIL | JSON v2 com 400 fresh, 480 session, 6 benches, pares/células/perfis válidos e `official_candidate=true` |
| regressão serial longa FAIR | FAIL | JSON `pqc-sat-stage8-acceptance-v2` sem falhas semânticas, com ECDH/ML-KEM e sessão nos dois perfis |
| D27 físico | PARCIAL | `BUTTON_PING button=1 pot=1469` e uptime novo observados; falta provar repouso `button=0` e partida integral |
| protocolo transacional | PARCIAL | caminho principal, retry e ordem inválida passaram; falta `GAME_ABORT` e partida visual |
| partida visível D27 | FAIL | uma partida completa com todos os avanços por D27 físico no JSONL v2 |
| partida visível verde | FAIL | busca automática, abertura confirmada e uma partida completa pelo verde |
| permanência dos estados | FAIL | deixar cada estado parado e provar ausência de avanço/reset |
| RNG e matriz curta | FAIL | executar normal, radiação e invasão no fluxo visual e conferir seed/vetor no JSONL |
| retransmissão real | PASS | mesmo payload, chave/nonce novos e `DELIVERED` |
| monitor definitivo | FAIL | confirmar legibilidade e controles na montagem final |
| 30 partidas / 3 h | FAIL | >100 D27, dez reconexões e zero invariantes violados |
| cinco visitantes | FAIL | mediana 120–180 s e critérios 4/5 de compreensão |

Nenhum desses itens pode ser promovido por fixture, screenshot, vídeo ou
acionamento administrativo.

## Procedimento curto do operador

```text
python3 tools/firmware_deploy.py --upload
python3 tools/stand_diagnostics.py \
  --port /dev/ttyUSB0 --full --wait-button-seconds 30

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
python3 tools/stand_hardware_smoke.py \
  --port /dev/ttyUSB0 --cycles 1 --production-timings
```

O operador deve pressionar D27 durante o diagnóstico e em cada liberação do
smoke. Depois deve executar na interface uma partida completa por D27 e outra
pelo botão verde, conferindo seed, causa e vetor no JSONL, e testar permanência
dos estados conforme `RUNBOOK.md`.

O comando de upload imprime um manifesto. Depois do smoke curto, a bateria FAIR
oficial deve ser executada pelo operador exatamente como descrito na seção 8
do `RUNBOOK.md`; o agente apenas analisa o JSON resultante.

O aceite serial longo da seção 9 do `RUNBOOK.md` é separado da coleta
estatística e deve produzir `pqc-sat-stage8-acceptance-v2`; ele também não é
iniciado pelo agente.

## Gate longo do operador

O agente não inicia o gate longo. O operador usa:

```bash
python3 dashboard.py --port /dev/ttyUSB0 \
  --log-dir logs/stand/acceptance --restart-on-crash

python3 tools/validate_stand_logs.py \
  logs/stand/acceptance/AAAAMMDD/*_stand_hardware_*.jsonl
```

O relatório `hardware_acceptance_summary.json` precisa ter todos os gates em
`true`, inclusive `confirmation_transition_invariant` e
`median_duration_120_180`.

## Entregáveis

| Entregável | Estado |
|---|---|
| código, configuração v3, parsers, fixture v2 e firmware | PASS em software |
| testes, soak, benchmark, 66 capturas e vídeo offline | PASS |
| documentação, guia do apresentador e catálogo técnico | PASS |
| JSON FAIR v2 oficial ECDH/ML-KEM | FAIL — bateria do operador ainda não executada |
| log de partida `STAGED_V1/FAIR_V1` em hardware | FAIL — ainda não produzido |
| vídeo físico com D27 | FAIL — ainda não produzido |
| aceite de três horas | FAIL — ainda não executado |
| avaliação com cinco visitantes | FAIL — ainda não executada |
| tag de release | RETIDA até todos os gates físicos passarem |

## Conclusão

A implementação atende ao contrato planejado no host e preserva o legado. A
extensão não deve ser descrita como pronta para o estande até o firmware atual
ser gravado e os gates físicos, de montagem e compreensão passarem.
