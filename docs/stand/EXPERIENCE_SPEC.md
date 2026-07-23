# Especificação — Missão Bit Flip por etapas

Estado: release candidate de software; firmware `STAGED_V1/FAIR_V1` ainda não validado
na Wisdom. Público: visitantes da 78ª Reunião Anual da SBPC. Duração alvo:
120–180 segundos por partida.

## Promessa ao visitante

> Uma mensagem crítica do CubeSat sofreu um incidente oculto. Escolha como
> protegê-la, interprete as evidências e tome uma decisão operacional.

A experiência não exige conhecimento prévio. A tela apresenta escolhas curtas;
a faixa verde ou o botão físico D27 confirmam cada fase; o potenciômetro A39
escolhe o bit usado no vetor single-bit. O incidente só é revelado no
encerramento.

## Direção visual em quatro atos

Os 14 estados continuam sendo estados transacionais distintos, mas o visitante
os percebe como quatro atos de uma única missão:

| Ato visual | Estados | Leitura pública |
|---|---|---|
| 1. Receber a missão | `ATTRACT`, `SELECT_MISSION` | Terra, órbita, CubeSat e mensagem crítica |
| 2. Montar o sistema | `SELECT_PROFILE`, `SELECT_KEY_MODE`, `SELECT_GUARD` | cartões ilustrados e loadout já confirmado |
| 3. Executar a operação | `PREPARE` a `VERIFY` | replays didáticos dos checkpoints reais |
| 4. Comandar a resposta | `DIAGNOSE` a `DEBRIEF`, mais `ERROR` | hipótese, ação e cadeia causal |

A Terra em rotação, a órbita e o CubeSat sorridente são procedurais e persistem
entre os atos; a torre que cobria o disco da Terra foi removida. Não há imagem,
áudio ou fonte externa. Cada escolha
possui um desenho animado próprio; a faixa de loadout mostra somente escolhas
já confirmadas e nunca transforma uma seleção pendente em decisão.

## Invariante de interação

O standby técnico não pertence à máquina pública: ele procura a Wisdom e sai
automaticamente após validar
`HELLO game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`. No modo hardware, nenhuma transição para a frente ocorre sem uma confirmação
explícita associada no log: um `BUTTON_PING` D27 válido ou a faixa verde da
tela. A abertura narrativa de `ATTRACT` permanece até `INICIAR MISSÃO` ou D27.

- toque em cartão altera somente `pending_choice`; toque na faixa verde confirma;
- resposta serial marca uma etapa como concluída;
- animação marca a apresentação como concluída;
- somente uma nova confirmação verde/D27, depois dessas duas condições, avança;
- D27 durante comando pendente, animação, guarda de tela ou restauração de
  perfil é ignorado sem consumir o debounce seguinte;
- teclado não representa D27 no hardware público, mesmo com diagnóstico;
- em `PROTECT`, a faixa verde solicita `ANALOG POT` sem bloquear o loop e só
  avança com A39 real válido; não reutiliza valor antigo ou padrão;
- qualquer desconexão reapresenta a busca; após novo `HELLO`, a partida
  interrompida é apagada e a abertura narrativa retorna automaticamente;
- `Home` é aborto administrativo e exige novo handshake para recuperação;
- não existe timeout de interação, avanço automático entre fases ou reset do
  resumo; busca e recuperação de conexão são as únicas transições técnicas automáticas.

## Arquitetura

```text
cartão ────── seleciona ──┐
D27 ou verde ─ confirma ───┼─> InvestigationController ─> WisdomSerialClient
A39 ──────── escolhe bit ─┘              |                       |
                                          v                       v
                                  JSONL log v2 <── USB ──> BlackBoard Wisdom
                                                                |
                                                                └─ GAME_* STAGED_V1
```

`python3 dashboard.py` é a única interface pública. O comando monolítico
`INVESTIGATE` permanece disponível somente no protocolo e nas ferramentas de
bancada; a jornada visual anterior foi removida.

## Jornada pública

| Estado | Seleção ou evidência | Verde ou D27 confirmado executa |
|---|---|---|
| `ATTRACT` | Terra, CubeSat e chamada `SALVE A MENSAGEM EM ÓRBITA` | `INICIAR MISSÃO` ou D27 abrem diretamente uma nova partida |
| `SELECT_MISSION` | telemetria, comando crítico ou configuração | fixa missão, payload, prioridade e prazo |
| `SELECT_PROFILE` | 240 ou 80 MHz | fixa o perfil experimental |
| `SELECT_KEY_MODE` | `CLÁSSICA — ECDH P-256` ou `PÓS-QUÂNTICA — ML-KEM-512` | fixa como o segredo será estabelecido |
| `SELECT_GUARD` | CRC da aplicação desligado ou CRC32 ligado | fixa o guardião e envia `GAME_BEGIN` |
| `PREPARE` | bytes serializados e CRC opcional anexado | envia `GAME_PROTECT` |
| `PROTECT` | chave/cápsula, KDF, AES-GCM, ciphertext e tag | captura A39 no D27 ou por `ANALOG POT` e envia `GAME_TRANSMIT` |
| `TRANSMIT` | pacote percorre satélite, antena e canal; causa segue oculta | envia `GAME_VERIFY` |
| `VERIFY` | CRC do quadro, tag GCM e CRC da aplicação, nessa ordem | libera o diagnóstico |
| `DIAGNOSE` | canal, adulteração ou memória | fixa a hipótese |
| `SELECT_RESPONSE` | aceitar, retransmitir ou modo seguro | executa `GAME_RETRY` ou `GAME_END` |
| `RETRY` | mesma mensagem, nova chave e novo nonce, sem falha | envia `GAME_END ... ACCEPT` |
| `DEBRIEF` | incidente, consequência, métricas, diagnóstico e contrafactual | encerra e volta a `ATTRACT` |
| `ERROR` | erro atual; nenhuma medição anterior é reutilizada | a busca cobre a tela e, após novo `HELLO`, volta automaticamente a `ATTRACT` |

Pacotes rejeitados criptograficamente não oferecem `ACCEPT` como escolha
válida. A opção permanece visível e bloqueada, com explicação. Escolhas já
confirmadas não têm “voltar”; `Home` aborta a partida inteira.

## Missões

| Cartão | Payload | Prioridade | Prazo tipado | Consequência pública |
|---|---|---|---:|---|
| Telemetria crítica | `TEMP=84C\|STATUS=CRITICAL\|SAFE=REQUEST` | alta | 2.000 ms | ocultar condição térmica crítica |
| Comando de emergência | `CMD=SAFE_MODE\|PRIORITY=CRITICAL\|SEQ=0042` | crítica | 500 ms | impedir ou disparar modo seguro incorretamente |
| Atualizar configuração | `CFG=COMMS_WINDOW\|VALUE=12MIN\|SEQ=0043` | média | 10.000 ms | perder a janela de comunicação |

Não há texto livre, imagem externa nem dado pessoal.

## Proteções independentes

Todas as quatro combinações usam AES-128-GCM:

| Estabelecimento | Guardião | Cenário protocolar |
|---|---|---|
| ECDH P-256 efêmero | nenhum | `ECDH` |
| ECDH P-256 efêmero | CRC32 da aplicação | `ECDH_CRC32` |
| ML-KEM-512 efêmero | nenhum | `MLKEM` |
| ML-KEM-512 efêmero | CRC32 da aplicação | `MLKEM_CRC32` |

Os dois caminhos usam wolfCrypt, RNG comum, HKDF-SHA256 e AES-128-GCM sob a
política `portable-software`. O CRC32 é anexado ao plaintext antes do AES-GCM,
detecta corrupção acidental na região coberta e não autentica. Os cenários
legados `CLASSIC`/`PQC` continuam aceitos pelo firmware apenas para regressão.

## Protocolo transacional

```text
GAME_BEGIN <id> <profile> <ECDH|MLKEM> <NONE|CRC32> <incident> <payload_hex>
GAME_PROTECT <id>
GAME_TRANSMIT <id> <byte_index> <bit_mask>
GAME_VERIFY <id>
GAME_RETRY <id>
GAME_END <id> <ACCEPT|SAFE_MODE>
GAME_ABORT <id>
```

O `HELLO` aceito pela superfície pública anuncia
`game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`. Há uma única sessão ativa. Ordem ou ID
incorreto retorna `BAD_GAME_STATE` e limpa a sessão. Novo `GAME_BEGIN`, erro
fatal, `GAME_ABORT`, `HELLO` ou reconexão também apagam o contexto anterior.
Durante a sessão, `ANALOG POT` é a única leitura não `GAME_*` permitida: ela
captura A39 sem apagar `PROTECT`, para que a faixa verde possa preparar o vetor
de `GAME_TRANSMIT`. Os demais comandos de bancada continuam bloqueados.
Segredos são apagados depois de `GAME_VERIFY`; somente contexto não secreto
mínimo fica disponível para `GAME_RETRY`, que usa chave e nonce novos. Nenhuma
resposta contém chave, segredo compartilhado, nonce ou ciphertext completos;
somente métricas e fingerprints CRC curtas.

## Modelo experimental

```text
payload → [CRC aplicação] → estabelecimento de segredo → AES-128-GCM
        → CRC do quadro → incidente de canal → verificação do quadro
        → verificação GCM → incidente de memória → CRC da aplicação
```

| Incidente | CRC quadro | GCM | CRC aplicação | Resultado |
|---|---|---|---|---|
| `NORMAL` | OK | OK | OK ou ausente | `DELIVERED` |
| `CHANNEL_BITFLIP` | falha | falha diagnóstica | não verificado | `FRAME_REJECT` |
| `TAMPER` | OK após recálculo | falha | não verificado | `AUTH_REJECT` |
| `RX_MEMORY` + CRC32 | OK | OK | falha | `APP_REJECT` |
| `RX_MEMORY` sem CRC | OK | OK | ausente | `SILENT_CORRUPTION` |

Quando o CRC do quadro falha, o harness ainda calcula a observação GCM para a
explicação didática, mas o pacote não é aceito. Os padrões localizam uma camada
provável; não provam radiação, ataque ou defeito físico.

## Animações e métricas

Antes da resposta `GAME_*`, a tela mostra apenas espera estática pela Wisdom.
O replay abaixo só é construído depois que o parser aceitou a resposta real;
portanto, movimento visual não antecipa nem inventa execução criptográfica.
As animações são então orientadas pelo estado e pela resposta aceita:

- `PREPARE`: bytes e CRC opcional;
- `PROTECT`: setup, iniciador, receptor, HKDF, nonce, AES-GCM e tag; a arte
  distingue o intercâmbio de pontos ECDH do par/cápsula ML-KEM;
- `TRANSMIT`: pacote, A39, bit e pulso do incidente ainda oculto;
- `VERIFY`: quadro, GCM e aplicação em ordem;
- `RETRY`: o KEX selecionado é repetido, seguido por nova chave derivada, novo
  nonce, novo envelope e entrega confirmada;
- `DEBRIEF`: linha causal entre escolhas, incidente, evidências e ação.

Depois de executar uma vez do início ao fim, o replay entra em modo de revisão.
O visitante segura a própria mensagem e a arrasta pela trilha; ela encaixa na
entrada ou no fim de uma operação. A estação ativa explica, em linguagem
pública, `ENTRA`, `O QUE ACONTECE`, `SAI` e a evidência medida. Não existem
botões de play/pause: a mensagem é o controle. O estado desse arraste pertence
somente à apresentação e nunca escreve em `InvestigationController`.

Voltar a mensagem não volta a missão nem bloqueia novamente a confirmação. Antes do
fim automático, o arraste está desabilitado. Antes da resposta serial, sequer
existe replay construído. Em `TRANSMIT`, a revisão mostra byte, bit e máscara
do A39, mas mantém a causa do incidente oculta até `DEBRIEF`.

A tela rotula “animação didática em tempo ampliado”. Os checkpoints explicam
causalidade sem mostrar números de recursos; somente o debrief exibe
tempo/bytes/heap da partida. `elapsed_us` é tempo de processamento, não
energia. Não há nota, ranking ou gamificação competitiva.

Nos dois caminhos, a duração relativa de setup, iniciador, receptor, HKDF, RNG
e AES-GCM usa os subtimings presentes na resposta validada. Etapas sem subtiming
individual continuam qualitativas e não recebem um número inventado. Em
`VERIFY`, o valor de cada portal vem exclusivamente de `GameResult`.

## Logs e privacidade

`pqc-sat-stand-log-v2` registra seleção e confirmação separadas, origem
`physical|screen`, controle, uptime de D27, fonte do A39, início/conclusão dos
estágios, respostas reais, diagnóstico,
decisão, retransmissão, resultado, erro e aborto. Logs V1 continuam legíveis
pelo validador, mas não satisfazem o gate físico `STAGED_V1`.

Sessões públicas não alimentam métricas oficiais. Baterias controladas são
executadas no terminal pelo operador. A fixture/modelo determinístico só pode
ser importada por testes e ferramentas offline; não existe flag de simulação
no programa de produção.

## Acessibilidade e contingência

- 1366×768 e 1920×1080 possuem busca, 14 estados e 18
  quadros adicionais de replay, cobrindo início, meio e fim dos seis painéis revisáveis;
- alto contraste, texto junto às cores e nenhuma dependência de áudio;
- cartões grandes para toque/mouse;
- o primeiro handshake abre automaticamente a narrativa mínima; `INICIAR
  MISSÃO` ou D27 seguem direto às escolhas; os cartões são quadrados, sem
  subtítulos internos, e mostram detalhes somente após seleção;
- `Esc` alterna janela/tela cheia, `F12` apenas mostra diagnóstico e `Ctrl+Q`
  encerra;
- timeout serial e resposta inválida levam a `ERROR`; desconexão mostra a busca
  e o handshake novo retorna à narrativa com a partida anterior apagada;
- a release pública depende dos gates físicos e de compreensão descritos em
  `RUNBOOK.md` e `FINAL_VALIDATION.md`.
