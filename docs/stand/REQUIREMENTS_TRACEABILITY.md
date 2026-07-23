# Rastreabilidade — jogo por etapas `STAGED_V1`

Estados: `PASS` significa validado na camada indicada; `PARCIAL` exige
evidência adicional; `FAIL` é gate ainda não executado. Um `PASS` de software
não é automaticamente um `PASS` de hardware.

## Interação e jornada

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| busca sai somente por `HELLO` válido | PASS software / FAIL hardware | dashboard permanece aberto sem porta e busca avança automaticamente no modelo após `STAGED_V1` | observar busca e handshake na montagem real |
| narrativa preservada e confirmada | PASS software / FAIL hardware | Terra/CubeSat e chamada mínima vêm após a busca; `INICIAR MISSÃO` e D27 abrem diretamente as escolhas | confirmar sequência pelos dois controles |
| toque em cartão apenas seleciona | PASS software | controlador e teste de clique mantêm o estado e alteram `pending_choice` | confirmar em tela sensível ao toque final |
| verde ou D27 confirmam transição | PASS software / FAIL hardware | log v2 exige `button_seq` e origem; verde percorre todos os estados; teclado bloqueado | uma partida real por cada controle |
| resposta/animação não avançam | PASS software | testes mantêm estágio após resposta e após deadline da animação | deixar cada estado parado na Wisdom |
| D27 inválido não consome debounce | PASS software | cobertos comando pendente, animação, guarda, evento antigo e repetido | smoke físico com rebote/pressões prematuras |
| sem timeout ou reset público | PASS software | flags v3 desabilitadas e teste com relógio avançado | permanência física nos 14 estados |
| incidente oculto até debrief | PASS software | UI só renderiza causa após `GAME_END` aceito | observar fluxo real |
| sem voltar após confirmação | PASS | não há ação pública de retorno; `Home` aborta a partida | nenhum |
| duração alvo 120–180 s | PARCIAL | configuração e validador tipam a faixa | medir mediana com cinco visitantes |

## Escolhas e ciência

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| três missões com prazo em ms | PASS | configuração v3 e cartões nas duas resoluções | nenhum |
| perfis 240/80 MHz | PASS software | parsers exigem perfil/clock correspondentes | repetir ambos em `GAME_*` real |
| chave e CRC independentes | PASS software | `CLASSIC`, `CLASSIC_CRC32`, `PQC`, `PQC_CRC32` | executar as quatro combinações na Wisdom |
| todas usam AES-128-GCM | PASS código | parser e firmware exigem `cipher=AES-128-GCM` | confirmar respostas reais |
| `CLASSIC` não é ECDH | PASS | textos e precisão científica corrigidos | nenhum |
| ML-KEM estabelece segredo | PASS | UI separa KeyGen/Encaps/Decaps/KDF de AES-GCM | nenhum |
| CRC não autentica | PASS | cartões, debrief e guia dizem explicitamente | validar compreensão 4/5 |
| A39 seleciona bit | PASS software / PARCIAL histórico | D27 fornece `pot`; verde usa `ANALOG POT` assíncrono; ambos alimentam o mesmo mapeamento single-bit | observar os dois caminhos no protocolo atual |
| tabela de quatro incidentes | PASS software | 32 casos automatizados e fixture estrita | matriz curta física e bateria controlada opcional |
| `RX_MEMORY/NONE` silencioso | PASS software | teste e modelo retornam `SILENT_CORRUPTION` | confirmar na Wisdom |
| `RX_MEMORY/CRC32` rejeitado | PASS software | teste e modelo retornam `APP_REJECT` | confirmar na Wisdom |

## Firmware e protocolo

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| `HELLO game=STAGED_V1` | PASS código / FAIL hardware | firmware e fixture anunciam capacidade | flash e handshake reais |
| sessão única e ordem estrita | PASS software | fixture e testes retornam `BAD_GAME_STATE` | ordem/ID errados na placa |
| A39 não destrói sessão ativa | PASS código/fixture | `ANALOG POT` preserva `PROTECT` e o `GAME_TRANSMIT` seguinte é aceito | flash e repetir a sequência na Wisdom |
| `GAME_BEGIN…GAME_END` separados | PASS código | handlers, catálogo, parsers e controlador | smoke real completo |
| erro/abort/reconexão limpam sessão | PASS software | testes limpam resultados; reconexão exige `HELLO` e retorna automaticamente à narrativa | desconexão controlada na placa |
| segredos apagados após verify | PASS revisão estática | firmware chama limpeza e mantém contexto não secreto | revisão/ensaio físico não expõe segredos completos |
| retry usa payload igual e material novo | PASS fixture | parser exige `same_payload=fresh_key=fresh_nonce=1` | confirmação em hardware |
| `INVESTIGATE` preservado | PASS | comando, parser, ferramentas e testes legados permanecem | nenhuma regressão conhecida |
| interface visual legada removida | PASS | `dashboard.py` é o único entrypoint e não há seletor de fluxo | nenhum |

## UI, logs e ferramentas

| Requisito | Estado | Evidência atual | Fechamento restante |
|---|---|---|---|
| 14 estados renderizados | PASS | 14 PNGs em cada resolução | ensaio no monitor definitivo |
| escolhas compreensíveis | PASS software | cartões quadrados sem subtítulos internos, com título e arte causal em destaque; detalhes surgem após seleção | testar compreensão com cinco visitantes |
| replay compreensível e controlável | PASS software | pacote arrastável com entrada, operação, saída e evidência; 18 quadros extras por resolução | testar compreensão com cinco visitantes |
| animação orientada à resposta | PASS software | bytes, CRC, proteção, A39, verificação, retry e causalidade só depois da resposta aceita | observar timings reais |
| métricas reais continuam visíveis | PASS design | tempo/bytes/heap vêm de respostas tipadas | hardware atual ainda não executado |
| log v2 completo | PASS software | seleção/confirmação, origem D27/tela, fonte A39, estágio, decisão, retry e aborto | gerar JSONL físico |
| validador mantém leitura V1 | PASS | testes e ramo de compatibilidade | nenhum |
| diagnóstico/smoke/soak/captura/vídeo/bateria atualizados | PASS software | ferramentas compilam; soak/capturas/vídeo executados | diagnóstico e smoke reais |
| média <16,667 ms | PASS host | interface completa: 7,280 ms e 10,204 ms | não é garantia de todo host/monitor |

## Gates do estande

| Gate | Estado | Critério |
|---|---|---|
| firmware atual gravado | FAIL | upload do candidato e hash registrado |
| D27 observado | FAIL | repouso, pressionado e `BUTTON_PING` válido |
| duas partidas físicas | FAIL | uma integral por D27 e outra pelo verde, ambas com transições associadas |
| monitor definitivo | FAIL | legibilidade e toque verificados |
| 30 partidas / 3 h | FAIL | zero transições sem confirmação e zero dados reaproveitados |
| >100 D27 e >100 mudanças A39 | FAIL | contadores do validador; delta A39 mínimo de 16 ADC evita contar ruído |
| dez reconexões | FAIL | dez recuperações após desconexão real |
| cinco visitantes | FAIL | mediana 120–180 s e critérios 4/5 |
| tag final | FAIL | somente após todos os gates acima |

## Resultado

O escopo de software está implementado e verificado. A release pública segue
bloqueada pelos gates físicos; evidências históricas de `INVESTIGATE` não são
reclassificadas como evidência do protocolo `STAGED_V1`.
