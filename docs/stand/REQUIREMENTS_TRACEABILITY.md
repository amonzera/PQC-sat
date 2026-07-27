# Rastreabilidade — jogo por etapas `STAGED_V1/FAIR_V1`

Estados: `PASS` significa validado na camada indicada; `PARCIAL` exige
evidência adicional; `FAIL` é gate ainda não executado. Um `PASS` de software
não é automaticamente um `PASS` de hardware.

## Interação e jornada

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| busca sai somente por `HELLO` válido | PASS software / FAIL hardware | dashboard permanece aberto sem porta e busca avança automaticamente no modelo após `game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` | observar busca e handshake na montagem real |
| narrativa preservada e confirmada | PASS software / FAIL hardware | Terra/CubeSat e chamada mínima vêm após a busca; `INICIAR MISSÃO` e D27 abrem diretamente as escolhas | confirmar sequência pelos dois controles |
| toque em cartão apenas seleciona | PASS software | controlador e teste de clique mantêm o estado e alteram `pending_choice` | confirmar em tela sensível ao toque final |
| verde ou D27 confirmam transição | PASS software / FAIL hardware | log v2 exige `button_seq` e origem; verde percorre todos os estados; teclado bloqueado | uma partida real por cada controle |
| resposta/animação não avançam | PASS software | testes mantêm estágio após resposta e após deadline da animação | deixar cada estado parado na Wisdom |
| D27 inválido não consome debounce | PASS software | cobertos comando pendente, animação, guarda, evento antigo e repetido | smoke físico com rebote/pressões prematuras |
| sem timeout ou reset público | PASS software | flags v3 desabilitadas e teste com relógio avançado | permanência física nos 17 estados |
| incidente oculto até debrief | PASS software | UI só renderiza causa após `GAME_END` aceito | observar fluxo real |
| sem voltar após confirmação | PASS | não há ação pública de retorno; `Home` aborta a partida | nenhum |
| duração alvo 120–180 s | PARCIAL | configuração e validador tipam a faixa | medir mediana com cinco visitantes |

## Escolhas e ciência

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| três missões com prazo em ms | PASS | configuração v3 e cartões nas duas resoluções | nenhum |
| CPU fixa no jogo público | PASS software | controlador sempre envia `BASELINE/240 MHz`; parsers e baterias técnicas preservam 240/80 MHz | confirmar a partida visual a 240 MHz |
| chave e CRC independentes | PASS software | `ECDH`, `ECDH_CRC32`, `MLKEM`, `MLKEM_CRC32` | executar as quatro combinações na Wisdom |
| todas usam AES-128-GCM | PASS código | parser e firmware exigem `cipher=AES-128-GCM` | confirmar respostas reais |
| backend comparável | PASS no hardware curto | ECDH P-256 e ML-KEM-512, RNG, HKDF e AES-GCM usam o mesmo wolfCrypt; `KEX_INFO` e o diagnóstico `20260723T160223Z` confirmaram a política FAIR na Wisdom | bateria controlada e análise estatística |
| protocolo legado não contamina o resultado | PASS software | `CLASSIC`/`PQC` continuam aceitos apenas nas ferramentas legadas e são rotulados `LEGACY_V1` | não misturar arquivos nem razões históricas |
| ML-KEM estabelece segredo | PASS | UI separa KeyGen/Encaps/Decaps/HKDF de AES-GCM | nenhum |
| CRC não autentica | PASS | cartões, debrief e guia dizem explicitamente | validar compreensão 4/5 |
| incidente e vetor probabilísticos | PASS software | evento público obrigatório; 50% radiação/50% invasão; seed, rolls e vetor RNG registrados; `NORMAL` preservado para engenharia | observar as duas causas na Wisdom |
| tabela de quatro incidentes | PASS software | 32 casos automatizados e fixture estrita | matriz curta física e bateria controlada opcional |
| `RX_MEMORY/NONE` silencioso | PASS software | teste e modelo retornam `SILENT_CORRUPTION` | confirmar na Wisdom |
| `RX_MEMORY/CRC32` rejeitado | PASS software | teste e modelo retornam `APP_REJECT` | confirmar na Wisdom |

## Firmware e protocolo

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| `HELLO STAGED_V1/FAIR_V1/FAIR_SESSION_V1` | PASS hardware | manifesto e diagnóstico confirmaram as três capacidades na Wisdom gravada | preservar manifesto junto aos resultados |
| `KEX_INFO` comum | PASS hardware curto | Wisdom confirmou wolfCrypt, HKDF-SHA256, AES-128-GCM e política portable sem asm/hardware | repetir como preflight das baterias |
| `KEX_BENCH` pareado | PASS hardware curto | `KEX_BENCH 1` concluiu ECDH/ML-KEM com `ok=1` e códigos de retorno zero | bateria pareada do operador |
| `SESSION_BENCH` fresh/amortizado | PASS hardware curto | `SESSION_BENCH ECDH 1` e `MLKEM 1` passaram com tempo, bytes e memória separados | bateria oficial em 1/100/500/1000 mensagens |
| rastreabilidade do binário | PASS hardware | manifesto `20260723T155737Z` registra upload, hashes, porta e handshakes do binário `9eba850f…32a18d` | anexar o manifesto à coleta oficial |
| sessão única e ordem estrita | PASS software | fixture e testes retornam `BAD_GAME_STATE` | ordem/ID errados na placa |
| A39 não destrói sessão ativa | PASS hardware curto | `GAME_PROTECT -> ANALOG POT -> GAME_TRANSMIT` foi aceito na mesma sessão | repetir no fluxo visual |
| `GAME_BEGIN…GAME_END` separados | PASS hardware curto | diagnóstico concluiu caminho transacional, incluindo verify, retry e end | exercitar `GAME_ABORT` e o fluxo visual completo |
| erro/abort/reconexão limpam sessão | PASS software | testes limpam resultados; reconexão exige `HELLO` e retorna automaticamente à narrativa | desconexão controlada na placa |
| segredos apagados após verify | PASS revisão estática | firmware chama limpeza e mantém contexto não secreto | revisão/ensaio físico não expõe segredos completos |
| retry usa payload igual e material novo | PASS hardware curto | Wisdom retornou `same_payload=1`, `fresh_key=1`, `fresh_nonce=1` e `DELIVERED` | observar a mesma retransmissão na UI |
| `INVESTIGATE` preservado | PASS | comando, parser, ferramentas e testes legados permanecem | nenhuma regressão conhecida |
| interface visual legada removida | PASS | `dashboard.py` é o único entrypoint e não há seletor de fluxo | nenhum |

## UI, logs e ferramentas

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| 17 estados renderizados | PASS software | 17 PNGs em cada resolução, incluindo quatro pausas antes das etapas | ensaio no monitor definitivo |
| escolhas compreensíveis | PASS software | cartões quadrados com título e arte causal; nas três missões, descrição e payload em lista ficam visíveis antes da seleção e somente a consequência surge depois; CPU fixa em 240 MHz não aparece como escolha | testar compreensão com cinco visitantes |
| replay compreensível e controlável | PASS software | pacote arrastável nas etapas com timeline; `VERIFY` usa processo GCM→CRC sem arraste; debrief incremental não é timeline | testar compreensão com cinco visitantes |
| animação orientada à resposta | PASS software | dois riscos amarelos no enlace; incidente vermelho só no risco da volta; GCM e CRC refletem `GameResult` depois da resposta aceita | observar timings reais |
| relatório final simples | PASS design | mostra apenas causa, tecnologias, diagnóstico e ação; final feliz exige diagnóstico e ação corretos | observar no monitor definitivo |
| log v2 completo | PASS software | seleção/confirmação, origem D27/tela, seed, rolls, vetor RNG, estágio, decisão, correção final, retry e aborto | gerar JSONL físico |
| validador mantém leitura V1 | PASS | testes e ramo de compatibilidade | nenhum |
| diagnóstico/smoke/soak/captura/vídeo/bateria atualizados | PARCIAL hardware | diagnóstico curto FAIR passou 27 registros; ferramentas longas e artefatos offline estão preparados | smoke visual, aceite longo e coleta FAIR reais |
| média <16,667 ms | PASS host | interface completa: 6,373 ms e 8,546 ms | não é garantia de todo host/monitor |

## Gates do estande

| Gate | Estado | Critério |
|---|---|---|
| firmware atual gravado | PASS | manifesto `20260723T155737Z`, hash `9eba850f…32a18d` e handshake pós-upload registrados |
| coleta FAIR v2 | FAIL | manifesto válido e `official_candidate=true` com 400 fresh, 480 session e 6 benches |
| D27 observado | PARCIAL | `BUTTON_PING button=1 pot=1469` e uptime fresco; falta registrar repouso `button=0` e partida integral |
| duas partidas físicas | FAIL | uma integral por D27 e outra pelo verde, ambas com transições associadas |
| monitor definitivo | FAIL | legibilidade e toque verificados |
| 30 partidas / 3 h | FAIL | zero transições sem confirmação e zero dados reaproveitados |
| >100 D27 | FAIL | confirmações físicas associadas às transições, sem exigir mudanças A39 |
| dez reconexões | FAIL | dez recuperações após desconexão real |
| cinco visitantes | FAIL | mediana 120–180 s e critérios 4/5 |
| tag final | FAIL | somente após todos os gates acima |

## Resultado

O escopo de software está implementado e verificado. A release pública segue
bloqueada pelos gates físicos; evidências históricas de `INVESTIGATE` e
`CLASSIC/PQC` não são reclassificadas como evidência do protocolo
`STAGED_V1/FAIR_V1`.
