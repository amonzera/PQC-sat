# Especificação — Missão Bit Flip por etapas

Estado: release candidate de software; firmware `STAGED_V1/FAIR_V1` ainda não validado
na Wisdom. Público: visitantes da 78ª Reunião Anual da SBPC. Duração alvo:
120–180 segundos por partida.

## Promessa ao visitante

> Uma mensagem crítica do CubeSat sofreu um incidente oculto. Escolha como
> protegê-la, interprete as evidências e tome uma decisão operacional.

A experiência não exige conhecimento prévio. A tela apresenta escolhas curtas;
a faixa verde ou o botão físico D27 confirmam cada fase. O controlador sorteia
e registra o incidente e o vetor single-bit; a causa só é revelada no
encerramento.

## Direção visual em quatro atos

Os 17 estados continuam sendo estados transacionais distintos, mas o visitante
os percebe como quatro atos de uma única missão:

| Ato visual | Estados | Leitura pública |
|---|---|---|
| 1. Receber a missão | `ATTRACT`, `SELECT_MISSION` | Terra, órbita, CubeSat e mensagem crítica |
| 2. Montar o sistema | `SELECT_KEY_MODE`, `SELECT_GUARD` | cartões ilustrados com frases curtas |
| 3. Executar a operação | `PREPARE` a `VERIFY` | replays didáticos das etapas reais |
| 4. Comandar a resposta | `DIAGNOSE` a `DEBRIEF`, mais `ERROR` | hipótese, ação e cadeia causal |

A Terra em rotação, a órbita e o CubeSat sorridente são procedurais e persistem
entre os atos; a torre que cobria o disco da Terra foi removida. Não há imagem,
áudio ou fonte externa. Cada escolha possui um desenho animado próprio e uma
frase curta; os parâmetros da partida aparecem somente no relatório final.

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
- em `NEXT_TRANSMIT`, D27 ou faixa verde confirmam o vetor RNG já registrado;
  nenhuma leitura A39 é solicitada pelo jogo público;
- qualquer desconexão reapresenta a busca; após novo `HELLO`, a partida
  interrompida é apagada e a abertura narrativa retorna automaticamente;
- `Home` é aborto administrativo e exige novo handshake para recuperação;
- não existe timeout de interação, avanço automático entre fases ou reset do
  resumo; busca e recuperação de conexão são as únicas transições técnicas automáticas.

## Arquitetura

```text
cartão ────── seleciona ──┐
D27 ou verde ─ confirma ───┼─> InvestigationController ─> WisdomSerialClient
RNG registrado ─ vetor ────┘              |                       |
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
| `ATTRACT` | Terra, CubeSat, cabeçalho `SALVE A MENSAGEM EM ÓRBITA` e botão isolado | `INICIAR MISSÃO` ou D27 abrem diretamente uma nova partida |
| `SELECT_MISSION` | telemetria, comando crítico ou configuração, cada qual com frase curta e payload | fixa a mensagem |
| `SELECT_KEY_MODE` | `ECDH P-256 + AES-GCM` ou `ML-KEM-512 + AES-GCM`, com uma frase causal | fixa como o segredo será criado |
| `SELECT_GUARD` | sem CRC32 ou com CRC32, com uma frase curta | fixa a checagem extra |
| `NEXT_PREPARE` | frase curta, mensagem, bytes, pacote e botão `CONTINUAR` já visíveis | envia `GAME_BEGIN` e abre a primeira etapa |
| `PREPARE` | payload centralizado, bytes serializados e CRC opcional | abre a pausa `NEXT_PROTECT` |
| `NEXT_PROTECT` | frase curta, payload, chave, proteção e botão `CONTINUAR` já visíveis | envia `GAME_PROTECT` |
| `PROTECT` | origem/receptor trocam chave pública ou cápsula; segredo, HKDF e AES-GCM completam a proteção | abre a pausa `NEXT_TRANSMIT` |
| `NEXT_TRANSMIT` | frase curta, origem, satélite, destino e dois trechos amarelos de risco; tudo é apenas ilustrativo | sorteia o vetor e envia `GAME_TRANSMIT` |
| `TRANSMIT` | ida e volta mantêm risco amarelo; a interferência só pode aparecer no centro da volta | abre a pausa `NEXT_VERIFY` |
| `NEXT_VERIFY` | frase curta, pacote, AES-GCM, CRC e botão `CONTINUAR` já visíveis | envia `GAME_VERIFY` |
| `VERIFY` | fluxo sem timeline: pacote → AES-GCM → CRC opcional → resultado | libera o diagnóstico |
| `DIAGNOSE` | radiação, invasão ou nenhum problema | fixa a hipótese |
| `SELECT_RESPONSE` | aceitar, retransmitir ou modo seguro | executa `GAME_RETRY` ou `GAME_END` |
| `RETRY` | mesma mensagem, nova chave e novo nonce, sem falha | envia `GAME_END ... ACCEPT` |
| `DEBRIEF` | configuração da partida, incidente, métricas, diagnóstico e contrafactual | encerra e volta a `ATTRACT` |
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
Durante a sessão, `ANALOG POT` continua disponível como leitura técnica sem
apagar `PROTECT`, mas não participa do fluxo público. O controlador sorteia e
registra o vetor enviado em `GAME_TRANSMIT`.
Segredos são apagados depois de `GAME_VERIFY`; somente contexto não secreto
mínimo fica disponível para `GAME_RETRY`, que usa chave e nonce novos. Nenhuma
resposta contém chave, segredo compartilhado, nonce ou ciphertext completos;
somente métricas e fingerprints CRC curtas.

## Modelo experimental

```text
payload → [CRC da mensagem] → estabelecimento de segredo → AES-128-GCM
        → transmissão → verificação GCM → possível alteração na recepção
        → CRC opcional da mensagem
```

| Incidente público | GCM | CRC da mensagem | Resultado |
|---|---|---|---|
| `NORMAL` | OK | OK ou não adicionado | `DELIVERED` |
| invasão simulada (`TAMPER`) | falha | não verificado ou não adicionado | `AUTH_REJECT` |
| radiação simulada (`RX_MEMORY`) + CRC32 | OK | falha | `APP_REJECT` |
| radiação simulada (`RX_MEMORY`) sem CRC | OK | não adicionado | `SILENT_CORRUPTION` |

`CHANNEL_BITFLIP` e o CRC de quadro permanecem na instrumentação técnica, mas
não são sorteados nem exibidos no jogo. Os sintomas públicos sustentam apenas
hipóteses dentro da simulação; não provam radiação, ataque ou defeito físico.

## Animações e métricas

Antes da resposta `GAME_*`, a tela mostra apenas espera estática pela Wisdom.
O replay abaixo só é construído depois que o parser aceitou a resposta real;
portanto, movimento visual não antecipa nem inventa execução criptográfica.
As animações são então orientadas pelo estado e pela resposta aceita:

- `PREPARE`: bytes e CRC opcional;
- `PROTECT`: cinco estações entre origem e receptor. ECDH troca partes públicas;
  ML-KEM usa `KeyGen`, `Encaps` e `Decaps`; ambos terminam em segredo comum,
  HKDF-SHA256, nonce e AES-GCM;
- `TRANSMIT`: 9 s de viagem; o segundo adicional é reservado ao trecho de
  risco da volta. Ida e volta ficam sempre amarelas, mas os efeitos genéricos
  só aparecem no centro da volta;
- `VERIFY`: processo visual sequencial sem timeline; AES-GCM vem primeiro e
  somente uma mensagem aberta segue ao CRC opcional;
- `RETRY`: o KEX selecionado é repetido, seguido por nova chave derivada, novo
  nonce, novo envelope e entrega confirmada;
- `DEBRIEF`: revelação incremental de causa, tecnologias, diagnóstico e ação,
  terminando em CubeSat feliz somente quando diagnóstico e ação estão corretos,
  ou em explosão didática caso contrário.

Depois de executar uma vez do início ao fim, os replays de `PREPARE`,
`PROTECT`, `TRANSMIT` e `RETRY` entram em modo de revisão. O visitante segura
a própria mensagem e a arrasta pela trilha; ela encaixa na entrada ou no fim
de uma operação. `VERIFY` é a exceção: apresenta AES-GCM e CRC como processo
visual sequencial, sem timeline ou arraste. O estado de revisão pertence
somente à apresentação e nunca escreve em `InvestigationController`.

Voltar a mensagem não volta a missão nem bloqueia novamente a confirmação. Antes do
fim automático, o arraste está desabilitado. Antes da resposta serial, sequer
existe replay construído. Em `TRANSMIT`, a causa permanece oculta até
`DEBRIEF`; seed, sorteios e vetor ficam apenas no log técnico.

A tela rotula “animação didática em tempo ampliado”. As etapas explicam
causalidade sem mostrar números de recursos. O debrief também omite
tempo/bytes/heap e mantém apenas as escolhas e o diagnóstico da missão.
`elapsed_us` continua registrado tecnicamente como tempo de processamento, não
energia. Não há nota, ranking ou gamificação competitiva.

Nos dois caminhos, a duração relativa de setup, iniciador, receptor, HKDF, RNG
e AES-GCM usa os subtimings presentes na resposta validada. Etapas sem subtiming
individual continuam qualitativas e não recebem um número inventado. Em
`VERIFY`, cada resultado visual vem exclusivamente de `GameResult`; sem CRC,
a interface não afirma que a mensagem ficou íntegra.

## Logs e privacidade

`pqc-sat-stand-log-v2` registra seleção e confirmação separadas, origem
`physical|screen`, controle, uptime de D27, seed, sorteios, vetor, início/conclusão dos
estágios, respostas reais, diagnóstico,
decisão, retransmissão, resultado, erro e aborto. Logs V1 continuam legíveis
pelo validador, mas não satisfazem o gate físico `STAGED_V1`.

Sessões públicas não alimentam métricas oficiais. Baterias controladas são
executadas no terminal pelo operador. A fixture/modelo determinístico só pode
ser importada por testes e ferramentas offline; não existe flag de simulação
no programa de produção.

## Acessibilidade e contingência

- 1366×768 e 1920×1080 possuem busca, 17 estados e 24
  quadros adicionais de replay, cobrindo início, meio e fim dos seis painéis
  revisáveis, o estabelecimento clássico e a transmissão normal sem efeitos
  de interferência;
- alto contraste, texto junto às cores e nenhuma dependência de áudio;
- cartões grandes para toque/mouse;
- o primeiro handshake abre automaticamente a narrativa mínima; `INICIAR
  MISSÃO` ou D27 seguem direto às escolhas; os cartões são quadrados e, na
  escolha de missão, mostram descrição e payload em lista antes da seleção;
  a consequência surge sem metadados depois da escolha. A CPU permanece fixa
  em 240 MHz e não aparece como decisão pública;
- `Esc` alterna janela/tela cheia, `F12` apenas mostra diagnóstico e `Ctrl+Q`
  encerra;
- timeout serial e resposta inválida levam a `ERROR`; desconexão mostra a busca
  e o handshake novo retorna à narrativa com a partida anterior apagada;
- a release pública depende dos gates físicos e de compreensão descritos em
  `RUNBOOK.md` e `FINAL_VALIDATION.md`.
