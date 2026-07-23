# Changelog do modo estande SBPC

## 2026-07-23 — comparação FAIR ECDH P-256 versus ML-KEM-512

- superfície pública migrada de `CLASSIC/PQC` para `ECDH/MLKEM`, preservando
  os comandos antigos como `LEGACY_V1`;
- novo handshake de pesquisa anuncia
  `game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`;
- mesmo wolfCrypt 5.9.2 usado para os dois KEX e para RNG, HKDF-SHA256 e
  AES-128-GCM, com aceleração ESP32 e assembly específico desativados;
- `SESSION_BENCH ECDH|MLKEM` passou a medir uma sessão nova seguida por 1, 100,
  500 ou 1000 mensagens, separando setup, dados, total, amortização, bytes,
  heap, maior bloco e stack high-water mark;
- `tools/kex_metrics_battery.py` v2 agenda 400 missões frescas, 480 sessões
  amortizadas e 6 benchmarks, em pares de ordem alternada, e só marca uma
  coleta oficial com desenho completo, respostas válidas e manifesto de deploy;
- `tools/stage8_acceptance.py` v2 deixou de executar `CLASSIC/PQC`: o smoke e
  o long-run agora validam semanticamente `KEX_INFO`, ECDH/ML-KEM e
  `SESSION_BENCH`, mantendo esse aceite separado da coleta estatística;
- `tools/firmware_deploy.py --upload` agora grava manifesto JSON somente após
  validar o firmware FAIR recém-gravado, vinculando hashes do binário, fontes e
  árvore wolfSSL local, além de porta e handshakes;
- o dashboard mostra custo somente no debrief, depois de dados reais da
  Wisdom; o replay intermediário permanece qualitativo e repete o KEX
  selecionado no retry;
- 117 testes host passam, incluindo descoberta versionada, manifesto com
  dependência, equações de sessão, códigos de retorno KEX, aceite serial FAIR e
  rejeição de logs `STAGED_V1` com modo de chave legado;
- o perfil legado atual compila sem wolfSSL com 59.004 B de RAM, 940.421 B de
  flash e binário de 946.992 B
  (`8cfd774614d8162d4af8e06fdbf221891a31e1fe25a22f70f6ac36888d152188`);
- a árvore Arduino oficial wolfSSL 5.9.2, commit `ac01707f…`, foi instalada
  localmente sob GPLv3 e permanece ignorada pelo Git;
- o primeiro smoke FAIR real confirmou handshake, `KEX_INFO` e ML-KEM, mas
  `KEX_BENCH 1` registrou `ecdh_ok=0`, setup de 29 µs e os demais estágios
  zerados em `logs/stand/diagnostics/20260723T152842Z_stand_diagnostic.json`;
- a causa foi `WOLFSSL_SP_MATH` sem `WOLFSSL_HAVE_SP_ECC`, combinação em que o
  wolfSSL retorna `WC_KEY_SIZE_E (-234)` para P-256; o firmware agora ativa o
  backend SP ECC C de 32 bits, impede essa configuração inválida no build e
  publica `ecdh_rc`/`mlkem_rc`;
- a revisão `afa5724c…af0d47` foi gravada e o segundo smoke real confirmou
  `KEX_BENCH 1`, missões e sessões ECDH/ML-KEM, além de `FAULT`; o fluxo
  transacional chegou a `GAME_BEGIN`, mas `GAME_PROTECT` repetia a chave
  `experiment` já emitida pelo bloco comum;
- `GAME_PROTECT` agora preserva um único `experiment=KEX_FAIR_V1`, e o
  diagnóstico mostra o `BAD_GAME_STATE` deliberado como teste negativo
  aprovado;
- o novo build passou com 59.020 B de RAM, 1.005.497 B de flash e binário de
  1.012.080 B, SHA-256
  `9eba850f2ea493edbdb89d7103f85589456277426f50136a2e337f8dac32a18d`;
- essa revisão foi gravada pelo manifesto `20260723T155737Z` e o diagnóstico
  `20260723T160223Z` concluiu 27 registros com `result=PASS`: backend comum,
  ECDH/ML-KEM, sessões, falhas, caminho `GAME_*`, A39 ativo, retry,
  compatibilidade `INVESTIGATE` e `BUTTON_PING` físico;
- o build emite o aviso genérico Xtensa do wolfSSL sobre implementações
  rápidas constant-time; side-channel não é objeto medido nem alegação desta
  pesquisa. Baterias longas, partida visual integral, matriz, ensaio e testes
  com visitantes continuam pendentes; o firmware não é ainda uma release
  aprovada para o estande.

## 2026-07-23 — abertura mínima e fluxo direto

- preservada a busca automática da Wisdom e a abertura narrativa com Terra e
  CubeSat;
- `ATTRACT` agora contém somente `SALVE A MENSAGEM EM ÓRBITA` e o botão
  `INICIAR MISSÃO`; clique ou D27 seguem diretamente para a escolha de missão;
- removida a tela intermediária de tutorial e seus estados, arte exclusiva,
  capturas e hashes;
- removidos cabeçalho de marca, abas de atos, barras de instrução e mensagens
  redundantes de confirmação; cada tela mantém apenas seu cabeçalho ativo e
  controles contextuais;
- cartões de escolha passaram a quadrados sem subtítulos internos, com arte e
  título em destaque e explicação somente após a seleção;
- 97 testes, soak de 50 partidas, 66 capturas e vídeo offline de 60 s passam;
  renderização média de 7,280 ms em 1366×768 e 10,204 ms em 1920×1080.

## 2026-07-22 — A39 preserva a sessão transacional

- corrigido o erro real `BAD_GAME_STATE` observado quando a faixa verde pedia
  `ANALOG POT` entre `GAME_PROTECT` e `GAME_TRANSMIT`;
- `ANALOG POT` passou a ser a única consulta somente-leitura permitida durante
  uma sessão ativa e não apaga mais o estado `PROTECT` nem os buffers do jogo;
- fixture e regressão agora exigem a sequência
  `GAME_PROTECT -> ANALOG POT -> GAME_TRANSMIT` sem perda de sessão;
- demais comandos de bancada continuam falhando de forma fechada;
- `tools/stand_diagnostics.py --full` agora lê A39 dentro da sessão e usa o
  vetor obtido no `GAME_TRANSMIT`, produzindo um gate físico curto reproduzível;
- 98 testes passam; o candidato compilou com 57.332 B de RAM, 932.173 B de
  flash e binário de 938.752 B (`288d5f49…e5d51e`), sem upload. A correção ainda
  exige novo flash para validação na Wisdom.

## 2026-07-22 — busca automática e restauração da abertura narrativa

- descoberta da Wisdom movida para o worker serial: o Pygame abre em standby e
  não encerra quando a porta está ausente;
- standby fecha automaticamente somente após `HELLO STAGED_V1`; D27 e toque
  recebidos durante a busca não iniciam a experiência;
- restaurada a abertura com Terra, CubeSat, problema e missão antes do tutorial;
- na primeira partida, verde ou D27 abrem o tutorial e uma nova confirmação
  inicia a missão; nas partidas seguintes, a abertura inicia diretamente;
- toda desconexão reapresenta a busca; um novo handshake apaga a partida
  interrompida e retorna automaticamente à abertura narrativa;
- evidência visual passou a separar busca, `ATTRACT` narrativo e tutorial;
  96 testes passam no host, sem mudança ou upload de firmware;
- benchmark headless de 300 quadros ficou em média 8,576 ms a 1366×768 e
  12,350 ms a 1920×1080, abaixo do orçamento médio de 16,667 ms.

## 2026-07-22 — splash D27, confirmação verde e onboarding causal

- removido o timer de 1,6 s: a splash agora vive no loop principal, espera um
  `BUTTON_PING` fresco e consome esse D27 sem iniciar a partida;
- a faixa verde tornou-se um controle real de confirmação em todos os estados,
  com a mesma guarda, debounce, sequência e associação de log do D27;
- em `PROTECT`, confirmação pela tela solicita `ANALOG POT` sem bloquear o
  Pygame e não avança com timeout ou leitura inválida;
- o tutorial passou a quatro cartões quadrados sem subtítulos, com animações
  causais de seleção, confirmação, A39 e revisão;
- removida a torre de rádio que cobria a Terra; o CubeSat móvel foi preservado
  e recebeu rosto de alto contraste com sorriso angular original;
- log e validador v2 aceitam origem `physical|screen`, preservando a contagem
  separada de D27 para o gate físico; 93 testes passam no host;
- benchmark headless de 300 quadros ficou em média 10,419 ms a 1366×768 e
  14,696 ms a 1920×1080, abaixo do orçamento médio de 16,667 ms;
- nenhuma gravação ou execução `STAGED_V1` na Wisdom foi feita nesta revisão.

## 2026-07-22 — replay explicado pela própria mensagem

- o primeiro handshake da execução abre um tutorial ilustrado de tela, D27,
  A39 e arraste; partidas seguintes voltam à abertura curta;
- cartões agora distinguem consequência da opção e ação seguinte, inclusive
  seleção pronta para D27 e indisponibilidade com motivo;
- após o replay automático validado, a própria mensagem pode ser arrastada e
  encaixa na entrada ou no fim de cada operação sem alterar o controlador;
- cada estação explica entrada, transformação, saída e evidência real; bytes,
  CRC, saída AES-GCM, bit A39 e portais de verificação aparecem na ordem
  científica da etapa;
- `DEBRIEF` ganhou revisão global arrastável construída somente com as
  medições retidas da partida; o incidente continua oculto antes dele;
- ferramentas de evidência geram, além dos 14 estados, início/meio/fim dos
  seis painéis revisáveis em ambas as resoluções;
- suíte atual passa 85/85 testes; benchmark headless médio ficou em 5,130 ms a
  1366×768 e 6,571 ms a 1920×1080 no host atual;
- esta revisão é de software: não grava firmware nem fecha os gates físicos
  de `STAGED_V1`, D27, A39, monitor ou visitantes.

## 2026-07-22 — jornada visual em quatro atos

- reorganizada a leitura pública dos mesmos 14 estados em quatro atos visuais,
  sem alterar o controlador, a ordem `GAME_*` ou os gates D27;
- tela inicial substituída por Terra procedural em rotação, CubeSat em órbita,
  estação de solo, trilha e enlace animado persistentes entre as fases;
- cartões de missão, CPU, chave, CRC, diagnóstico e resposta receberam ícones
  procedurais e animação de seleção; o loadout exibe somente escolhas já
  confirmadas;
- checkpoints passaram a usar replays didáticos específicos: bytes e CRC,
  KeyGen/Encaps/Decaps/KDF/AES-GCM, pacote e A39, três portais de verificação e
  retransmissão com material novo;
- o replay não é construído antes de uma resposta serial validada; subtimings
  reais alimentam a timeline PQC e os valores de verificação vêm de
  `GameResult`;
- debrief redesenhado como cadeia causal qualitativa, sem pontuação ou ranking;
- adicionados testes de atos, ícones, timelines, gate de replay e mudança
  visual por progresso; suíte atual passa 81/81 testes;
- benchmark headless do host ficou em média 10,159 ms a 1366×768 e 14,096 ms
  a 1920×1080, abaixo do orçamento médio de 16,667 ms;
- nenhuma gravação ou validação física foi feita nesta revisão visual; os gates
  de firmware, D27, A39, monitor e visitantes permanecem pendentes.

## 2026-07-22 — firmware preparado para implantação Python

- sessão `GAME_*` passou a possuir uso exclusivo do perfil, indicadores e
  buffers ML-KEM; comando técnico concorrente falha fechado com
  `BAD_GAME_STATE`, limpa a sessão e restaura o baseline;
- limpeza integral agora apaga também chave pública, cápsula e fingerprints
  globais, mantendo após `GAME_VERIFY` somente o contexto não secreto mínimo
  necessário para a retransmissão;
- criado `tools/firmware_deploy.py`: build por padrão, upload somente com
  `--upload`, identificação prévia da Wisdom e validação pós-reset de
  `game=STAGED_V1`, sempre por subprocesso Python sem shell/Bash;
- build atual aprovado com 57.332 B de RAM (17,5%), 932.089 B de flash (71,1%)
  e `firmware.bin` de 938.672 B, SHA-256
  `6986171a569ae9498d2ba0cf2c065b45c1eb13276659bd8c631cd25f787ecf72`;
- suíte atual passa 74/74 testes; `git diff --check`, import headless e ausência
  de arquivos `.sh`/`.bash` foram reconfirmados;
- a Wisdom real foi reconhecida no CP2102N e por `/dev/serial/by-id`, mas o
  firmware gravado ainda não anuncia `game`; upload e smoke permanecem
  pendentes e não foram executados nesta revisão.

## 2026-07-21 — interface Python única e hardware obrigatório

- `dashboard.py` tornou-se o único entrypoint público e sempre inicia o jogo
  `STAGED_V1` conectado à Wisdom;
- removidos o dashboard manual anterior, `stand_demo.py`, a máquina visual
  legado, os dois launchers Bash e as flags públicas de simulação/fluxo;
- fixture movida para `pqc_sat/testing/`; o composition root de produção não a
  importa, e `GamePanel` recusa controladores que não sejam hardware;
- descoberta serial passou a sondar cada candidata com `HELLO`, incluindo
  `/dev/serial/by-id`, `ttyUSB` e `ttyACM`, sem usar “CP210” como prova de
  identidade;
- validação pré-Pygame exige `node`, `board`, `proto=V1`, `game=STAGED_V1` e
  `uptime_ms` uint32; porta explícita também é validada;
- conectada ao host, a Wisdom foi reconhecida pelo caminho `by-id`, mas o
  firmware atualmente gravado não anuncia `game`; a aplicação agora informa
  “Wisdom reconhecida, firmware incompatível” em vez de “placa não encontrada”;
- firmware candidato compilado localmente com 57.332 B de RAM (17,5%) e
  931.833 B de flash (71,1%); upload permanece separado e não foi executado;
- ferramentas de captura, soak, benchmark, diagnóstico, smoke e aceite foram
  migradas para Python e para o fluxo por etapas;
- suíte atual passa 68/68 testes; soak exclusivo de teste passa 50/50 ciclos,
  com 625 confirmações sintéticas, 100 mudanças A39, 275 comandos `GAME_*` e
  zero eventos rejeitados;
- renderização isolada ficou em média 4,573 ms a 1366×768 e 6,516 ms a
  1920×1080 no host atual, abaixo do orçamento médio de 16,667 ms.

## 2026-07-21 — jogo didático transacional `STAGED_V1`

- substituída a jornada investigativa pública por 14 estados explícitos, de
  `ATTRACT` a `DEBRIEF`, com `ERROR` seguro;
- toque/clique agora somente seleciona; toda transição para a frente no modo
  hardware exige `BUTTON_PING` físico posterior ao handshake e vinculado por
  `button_seq` no log;
- removidos timeout público, avanço por resposta/animação e reset automático;
  `Home` aborta a partida e a recuperação exige `HELLO` novo mais D27;
- separadas as escolhas de estabelecimento de chave (`CLASSIC`/`PQC`) e CRC da
  aplicação (`NONE`/`CRC32`), incluindo `CLASSIC_CRC32`;
- adicionado ao firmware o protocolo transacional `GAME_BEGIN`,
  `GAME_PROTECT`, `GAME_TRANSMIT`, `GAME_VERIFY`, `GAME_RETRY`, `GAME_END` e
  `GAME_ABORT`, preservando `INVESTIGATE` e ferramentas legadas;
- `HELLO` passa a anunciar `game=STAGED_V1`; o firmware mantém uma sessão,
  rejeita ordem/ID incorreto, apaga segredos depois da verificação e cria
  chave/nonce novos no retry;
- implementadas animações de preparação, proteção, canal, verificação,
  retransmissão e linha causal no debrief, sempre separando tempo medido de
  animação ampliada;
- criado `pqc-sat-stand-log-v2`, mantendo o validador compatível com V1;
- diagnóstico, smoke, soak, capturas, vídeo, bateria e catálogo técnico foram
  migrados para os comandos por etapas;
- suíte integrada passa com 159 testes; a matriz cobre 32 combinações;
- soak offline passa 50/50 partidas, 625 confirmações lógicas, 100 mudanças de
  A39, 275 comandos `GAME_*`, 25 retries e zero crescimento de RSS;
- geradas 14 capturas em cada resolução e vídeo offline rotulado; médias do
  overlay por fases de 6,565 ms em 1366×768 e 11,933 ms em 1920×1080;
- firmware candidato compila com 57.332 B de RAM (17,5%) e 931.833 B de flash
  (71,1%), mas **não foi gravado nem executado na Wisdom nesta revisão**;
  handshake `STAGED_V1`, D27 físico, smoke e gate longo permanecem pendentes.

## 2026-07-21 — correção do fluxo de interação

Esta seção descreve a revisão monolítica `INVESTIGATE` anterior e permanece
apenas como histórico; seus timeouts e estados não regem o fluxo atual.

- reproduzido o defeito em que `REVEAL` avançava para `SUMMARY` após 12 s sem
  confirmação e o resumo voltava ao início em seguida;
- `REVEAL` agora permanece até uma ação explícita; somente retornos de quiosque
  por inatividade/resumo continuam automáticos e exibem contagem na tela;
- no modo hardware público, clique e teclado não substituem D27 em iniciar,
  transmitir, concluir ou reiniciar; Espaço/Enter só funciona na simulação ou
  com diagnóstico administrativo ativo;
- adicionada guarda de 220 ms entre telas e trava até `KEYUP`, evitando duplo
  clique, tecla segurada e rebote atravessarem estados;
- `HELLO` passou a informar `uptime_ms`, e eventos `BUTTON_PING` anteriores ao
  handshake são rejeitados como entrada antiga;
- corrigidos início oferecido durante restauração de perfil, área inteira da
  tela de erro funcionando como botão, progresso de `TRANSMIT` e nomes internos
  em inglês no HUD;
- todas as telas interativas agora informam a ação esperada e quando existe
  retorno automático.
- o retorno de erro agora solicita um novo `HELLO`; pressionar D27 durante a
  restauração não consome o debounce da próxima ação válida;
- o parser e o validador exigem `key_match=true`, confirmação GCM e XOR
  single-bit coerente, impedindo que uma falha da sessão PQC seja confundida
  com o incidente didático;
- eventos D27 antigos ou ignorados não disparam mais o efeito visual de botão;
- rótulos de conexão, processamento, proteção e dados distinguem fixture,
  handshake não validado e hardware real sem alegar payload vivo indevidamente;
- as capturas de estados iniciais não carregam mais escolhas futuras;
- regressão fechada com 158 testes, 50 ciclos investigativos e 10 ciclos do
  fluxo legado; ambas as campanhas tiveram zero eventos rejeitados, zero
  entradas ignoradas e nenhum crescimento de RSS observado;
- renderização headless permaneceu dentro do orçamento médio de 60 FPS em
  1366×768 e 1920×1080; firmware recompilado com 56.684 B de RAM estática e
  925.301 B de flash.
- firmware atualizado na Wisdom em `/dev/ttyUSB0`; diagnóstico real aprovou
  `HELLO` com `uptime_ms`, `MISSION`, `FAULT` e os quatro casos de
  `INVESTIGATE`;
- smoke administrativo do fluxo investigativo percorreu todos os estados até
  `SUMMARY`, classificou `CHANNEL_BITFLIP` como `FRAME_REJECT` e passou no
  validador de invariantes; um teste real sem entrada permaneceu em `ATTRACT`;
- `BUTTON_PING` não foi observado nas janelas assistidas de 30 s e 45 s, por
  isso o acionamento/fiação de D27 e o gate físico longo continuam pendentes.

## 2026-07-21 — Missão Bit Flip investigativa

- transformado o modo estande padrão em uma investigação de 60–90 s dentro do
  dashboard existente, com três missões, dois perfis e três proteções;
- adicionado `InvestigationController` com seleção digital, D27, A39,
  diagnóstico do visitante, explicação rápida/técnica e reset seguro;
- adicionado ao firmware o comando `INVESTIGATE`, que reúne CRC externo do
  quadro, autenticação AES-GCM e CRC interno da aplicação na mesma execução;
- implementados `NORMAL`, `CHANNEL_BITFLIP`, `TAMPER` com CRC recalculado e
  `RX_MEMORY`, incluindo `FRAME_REJECT`, `AUTH_REJECT`, `APP_REJECT` e
  `SILENT_CORRUPTION`;
- mantidos AES-128-GCM, ML-KEM-512, `MISSION`, `FAULT` e todo o roteiro anterior;
  `--stand-flow legacy` seleciona explicitamente a contingência;
- atualizado o modelo offline, catálogo de comandos, diagnóstico, smoke de
  hardware, validador de logs, capturas 1366×768/1920×1080 e runbook;
- suíte integrada concluída inicialmente com 142 testes, soak investigativo de 50 ciclos,
  22 capturas e vídeo de contingência de 44 s;
- build do firmware após a mudança: 17,3% de RAM e 70,6% de flash;
- validação física do novo comando permanece pendente até a Wisdom reaparecer
  como porta serial.

## 2026-07-21 — apresentação integrada ao dashboard

- separada a implementação Python no pacote `pqc_sat/`: o controlador guiado,
  fixture e logger ficam em `pqc_sat/stand/`, enquanto a camada visual nativa
  fica nas facetas de `pqc_sat/ui/panel/`;
- `dashboard.py` e `stand_demo.py` passaram a ser fachadas compatíveis, sem
  alterar os comandos operacionais existentes;
- corrigida a arquitetura visual: `dashboard.py --presentation` e o alias
  `--stand` agora permanecem no loop, cenário e `DashboardPanel` originais;
- substituído o desvio de produção para o shell visual separado por um overlay
  nativo com nove estados, progresso, instruções físicas, medições e erro seguro;
- preservados `StandController`, parsers, fixture, logs e invariantes seriais já
  validados, sem duplicar o protocolo nem mover criptografia para o notebook;
- eventos `BUTTON_PING` agora são encaminhados pelo próprio `DashboardPanel`
  para a apresentação guiada, mantendo também o efeito visual do dashboard;
- capturas e smoke de renderização passaram a usar a superfície integrada;
- adicionado teste de integração dashboard–botão físico e testes de fronteira
  arquitetural; suíte passa com 129 testes.

## 2026-07-20 — release candidate de software

- preservada a versão do seminário na branch original e criado o trabalho em
  `sbpc-stand-demo`;
- auditados AES-128-GCM, baseline simétrico, localização da falha, perfil de
  80 MHz, botão, potenciômetro e campanha oficial;
- adicionado `dashboard.py --stand` e o shell visual `stand_demo.py`;
- implementada máquina de estados sem bloqueio, timeout, rejeição de eventos
  fora de ordem, debounce, erro seguro e reset automático;
- integrados `BUTTON_PING`, `ANALOG POT`, `PROFILE`, `MISSION` e `FAULT` pelo
  cliente serial existente;
- garantidos payload idêntico nas missões e índice/máscara idênticos nos dois
  ensaios de falha;
- adicionada fixture offline vinculada por SHA-256 à campanha oficial;
- adicionado log JSONL datado com revisão, comandos, respostas e proveniência;
- criados inicializador, diagnóstico, soak offline, capturas de estados,
  gerador de vídeo e validador dos logs de aceite físico;
- adicionados testes de parser, estados, timeout, reconexão lógica, mapeamento
  do potenciômetro, XOR, fixture, logs, reset e resoluções;
- criados runbook, especificação, precisão científica e relatório de validação.
- validado um ciclo real de 51,55 s com os tempos exatos da configuração de
  produção e registrado seu JSONL autocontido;
- adicionada rastreabilidade explícita de todos os itens P0 e entregáveis,
  sem converter gates presenciais pendentes em `PASS`.
- executados 20 ciclos reais acelerados, com 60 missões, 40 falhas, zero erros
  e 20/20 pares `NONE`/`CRC32` coerentes;
- endurecido o gate do potenciômetro para contar mudanças de posição, e não
  uma amostra inicial repetida a cada ciclo.

Pendente para a release do evento: executar e anexar aceite físico, ensaio com
cinco pessoas e evidência de montagem no estande.
