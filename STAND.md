# PQC-SAT no estande — guia técnico-científico da simulação e interação

> Estado deste documento: 26 de julho de 2026. Este texto descreve a interface
> `python3 dashboard.py` atual. O jogo é uma *release candidate de software*:
> o smoke curto na Wisdom foi comprovado, mas partidas visíveis completas, aceite
> longo, ensaio no monitor final e teste com visitantes ainda não foram fechados.
> Não se deve apresentá-lo como estande fisicamente aceito em definitivo.

## 1. Visão geral

O PQC-SAT é uma experiência guiada: a pessoa escolhe uma mensagem de CubeSat,
escolhe como criar a chave da sessão e decide se quer uma checagem adicional de
integridade. A BlackBoard Wisdom executa as operações criptográficas, o
experimento injeta por software uma falha controlada de um bit, e a pessoa
interpreta as evidências para decidir o que fazer.

A intenção não é fazer o visitante “quebrar” criptografia. É mostrar, numa
cadeia causal, que mecanismos distintos tratam problemas distintos:

- ECDH P-256 e ML-KEM-512 estabelecem um segredo compartilhado;
- HKDF-SHA256 deriva desse segredo a chave da sessão;
- AES-128-GCM cifra a mensagem e autentica o pacote protegido;
- CRC32 opcional detecta alteração acidental do conteúdo da aplicação em uma
  região definida;
- a pessoa toma uma decisão a partir de evidências retornadas pela placa.

## 2. O que é real, simulado e visual

| Elemento | O que ocorre de fato | O que não se deve concluir |
|---|---|---|
| Hardware | A BlackBoard Wisdom responde ao protocolo serial V1 e executa os comandos GAME_*, ECDH/ML-KEM, HKDF e AES-GCM. A produção exige HELLO válido. | A placa educacional não é um CubeSat qualificado para voo. |
| Criptografia | ECDH P-256 ou ML-KEM-512 estabelece o segredo; AES-128-GCM cifra e autentica a mensagem. | ML-KEM não cifra diretamente o payload mostrado na tela. |
| Incidente | O firmware aplica uma mutação controlada de um único bit, no objeto e instante definidos pelo cenário. O vetor fica no log. | Não há radiação real, enlace espacial real, ataque real ou atribuição forense de causa física. |
| CRC32 | O CRC opcional é calculado sobre a mensagem, anexado antes do AES-GCM e conferido depois da decriptação. | CRC32 não autentica, não bloqueia atacante que possa recalculá-lo e não substitui GCM. |
| Animação | O replay só é construído depois que a resposta GAME_* real passa pela validação do parser. | Duração visual não é tempo de execução, energia, latência de rádio ou benchmark. |
| Dados científicos | Tempos, tamanhos e observações da Wisdom são registrados. Baterias controladas de terminal são a fonte de métricas consolidadas. | Uma partida de visitante, vídeo ou fixture não é campanha experimental oficial. |

Em linguagem simples: a animação explica uma operação que já ocorreu e foi
validada; ela não inventa a operação nem mede seu tempo.

## 3. Arquitetura e interação

O único programa público é:

~~~bash
python3 dashboard.py
~~~

Ele mantém a renderização Pygame, a comunicação serial e a máquina de estados
separadas. A renderização não bloqueia esperando USB nem executa criptografia.

~~~text
cartão / faixa verde ─────────┐
botão físico D27 ─────────────┼─> controlador ─> serial USB ─> Wisdom
                              │        │                    │
RNG experimental registrado ──┘        └─> log JSONL v2      └─> GAME_* real

resposta validada da Wisdom ─> replay didático ─> próxima confirmação explícita
~~~

Antes da narrativa, o programa procura continuamente uma porta que responda:

~~~text
node=PQC-SAT-WISDOM
board=BlackBoard-Wisdom
proto=V1
game=STAGED_V1
kex=FAIR_V1
session_bench=FAIR_SESSION_V1
uptime_ms=<inteiro válido>
~~~

Encontrar uma porta USB, ou um adaptador de marca conhecida, não basta. A placa
precisa provar identidade e capacidades. Queda de conexão descarta a partida,
reexibe a busca e exige HELLO novo.

| Entrada | Papel público |
|---|---|
| Cartão | Apenas seleciona opção pendente; nunca muda de tela sozinho. |
| Faixa verde | Confirma escolha ou prossegue quando a etapa está realmente pronta. |
| D27 | Confirma como a faixa verde. O evento deve ser posterior ao HELLO, novo e fora do debounce. |
| A39/potenciômetro | Leitura técnica permitida pelo firmware; não participa do jogo atual nem escolhe o bit. |
| Arrastar mensagem | Revisa animação concluída; não muda estado, falha, resultado ou controlador. |
| Home | Aborta administrativamente a partida e exige recuperação por handshake. |
| F12 | Mostra/oculta diagnóstico administrativo; não é controle para visitante. |
| Esc / Ctrl+Q | Alterna janela/tela cheia / encerra o programa. |

Não existe tecla que emule D27. Não existe timeout de interação, avanço
automático entre estados ou reset automático do debrief. Resposta serial e fim
de animação apenas liberam a próxima confirmação; nunca avançam sozinhos.

## 4. Vocabulário explicado sem pré-requisito

### Bytes e bits

O texto TEMP=84C|STATUS=CRITICAL é enviado como **bytes**, valores de 0 a 255.
Cada byte contém oito **bits**, posições 0 ou 1. Uma falha *single-bit* altera
exatamente um desses bits. O log conserva índice de byte e máscara de bit, logo
a mutação é reprodutível e auditável.

### Chave de sessão e KEX

Uma **chave de sessão** é segredo temporário para proteger a troca. As duas
pontas devem chegar ao mesmo segredo sem transmiti-lo em aberto.

- **ECDH P-256** é o método clássico de curva elíptica. Ambos criam chaves
  temporárias, trocam partes públicas e calculam o mesmo segredo.
- **ML-KEM-512** é um mecanismo de encapsulamento de chave pós-quântico
  padronizado pelo NIST. O receptor cria um par de chaves; a origem usa a
  pública para gerar cápsula e segredo; o receptor abre a cápsula e recupera o
  mesmo segredo.

“Pós-quântico” significa projetado para resistir a certa classe de ataques de
computadores quânticos grandes contra esquemas clássicos. Não significa que a
Wisdom tenha computador quântico nem que esta demonstração mede segurança
absoluta.

A comparação atual é controlada: mesmos wolfCrypt, RNG, HKDF-SHA256,
AES-128-GCM, placa, 240 MHz e perfil portable-software, sem assembly do alvo e
sem aceleração criptográfica de hardware. A variável que muda é o KEX.

### HKDF-SHA256, AES-GCM, nonce e tag

**HKDF-SHA256** é uma função de derivação: transforma o segredo bruto do KEX em
material adequado à chave AES-128. Não se entrega o segredo de ECDH/ML-KEM
diretamente ao AES.

**AES-128-GCM** cifra a mensagem e produz uma **tag** de autenticação. Se
ciphertext, tag ou dados autenticados mudarem, a verificação falha. O **nonce**
é valor novo que deve ser usado uma única vez com uma chave AES; por isso a
retransmissão exige chave nova e nonce novo.

### CRC32 e CRC de quadro

**CRC32** é checksum de 32 bits para detectar corrupção acidental na região que
cobre. Escolhido o guardião, a Wisdom acrescenta quatro bytes de CRC ao payload
antes da cifra e, depois da decriptação, recalcula e compara. CRC32 não oferece
sigilo, não identifica invasor e não substitui a tag GCM.

O firmware também instrumenta CRC de **quadro** para localizar mudanças em
canal/armazenamento. O visitante só escolhe e vê o CRC opcional da mensagem.
CHANNEL_BITFLIP e CRC de quadro são instrumentação técnica, não cenário público.

## 5. Todas as telas e seus efeitos

Há uma tela técnica de busca e 17 estados públicos. As telas NEXT_* são pausas
de leitura: confirmar nelas dispara a etapa seguinte. As telas de execução
esperam resposta real, reproduzem visualmente a operação já validada e só então
aceitam confirmação.

| Ordem | Estado/tela | O visitante vê/faz | O que ocorre tecnicamente |
|---:|---|---|---|
| 0 | **Busca da Wisdom** | Espera conexão; não aceita início por D27. | Worker sonda portas com HELLO; somente handshake válido encerra busca. |
| 1 | ATTRACT — “Salve a mensagem em órbita” | Terra, órbita, CubeSat e INICIAR MISSÃO; clique/D27 inicia. | Começa ciclo novo em BASELINE/240 MHz. |
| 2 | SELECT_MISSION | Três cartões; toque seleciona, verde/D27 confirma. | Retém payload da missão; ainda não envia GAME_*. |
| 3 | SELECT_KEY_MODE | Cartões clássica/ECDH P-256 e pós-quântica/ML-KEM-512. | Fixa KEX; AES-GCM permanece igual. |
| 4 | SELECT_GUARD | Cartões sem CRC32 e com CRC32. | Fixa guardião independente da escolha de KEX. |
| 5 | NEXT_PREPARE | “Preparar a mensagem”, bytes e pacote; CONTINUAR. | Confirmação escolhe incidente oculto, cria ID e manda GAME_BEGIN. |
| 6 | PREPARE | Bytes do payload; com CRC mostra “CRC32 anexado (4 B)”. | Wisdom valida payload, monta conteúdo e devolve checkpoint PREPARE. |
| 7 | NEXT_PROTECT | Pacote → segredo → protegido. | CONTINUAR envia GAME_PROTECT. |
| 8 | PROTECT | Origem/receptor, ECDH ou ML-KEM, HKDF, nonce e AES-GCM. | Wisdom executa KEX, deriva chave, gera nonce, cifra e cria tag. |
| 9 | NEXT_TRANSMIT | Origem → satélite → destino. | Confirmação sorteia vetor de um bit e manda GAME_TRANSMIT. A39 não participa. |
| 10 | TRANSMIT | Pacote viaja; incidente mostra interferência genérica, sem revelar causa. | Firmware monta quadro e aplica mutação definida pelo cenário. |
| 11 | NEXT_VERIFY | Pacote → AES-GCM → CRC. | CONTINUAR envia GAME_VERIFY. |
| 12 | VERIFY | Evidências de AES-GCM e CRC da mensagem. | Wisdom verifica tag GCM e CRC opcional; resposta passa pela tabela de validação. |
| 13 | DIAGNOSE | Hipótese: radiação, invasão ou normal. | Registra e compara diagnóstico com incidente oculto. |
| 14 | SELECT_RESPONSE | Aceitar, enviar de novo ou modo seguro. | Pacote rejeitado bloqueia aceitar; retry manda GAME_RETRY; demais decisões mandam GAME_END. |
| 15 | RETRY | Mesmo payload, nova chave, novo nonce e entrega. | Executa KEX/AES novamente, sem falha; confirmação posterior manda GAME_END ACCEPT. |
| 16 | DEBRIEF | Causa revelada, configuração, resultado, tempo/bytes e revisão arrastável. | Só abre após GAME_END confirmar limpeza e baseline restaurado; confirmação volta a ATTRACT. |
| 17 | ERROR | Partida interrompida e resultados apagados. | Timeout, resposta/ordem inválida, desconexão ou Home; GAME_ABORT é tentado; HELLO novo é obrigatório. |

### Busca, ATTRACT e escolhas

A busca não é fase da missão. A janela pode abrir sem placa apenas para exibir
essa busca, mas não há partida offline na produção. Ao chegar HELLO válido, ela
sai automaticamente para ATTRACT.

Terra, nebulosa, estrelas e CubeSat são arte procedural de contexto, não
telemetria. Em ATTRACT, INICIAR MISSÃO ou D27 abre diretamente as escolhas.

| Cartão | Payload enviado | Prazo didático | Risco público |
|---|---|---:|---|
| Telemetria crítica | `TEMP=84C\|STATUS=CRITICAL\|SAFE=REQUEST` | 2.000 ms | Alteração pode ocultar condição térmica crítica. |
| Comando de emergência | `CMD=SAFE_MODE\|PRIORITY=CRITICAL\|SEQ=0042` | 500 ms | Pode impedir ou disparar modo seguro incorretamente. |
| Atualizar configuração | `CFG=COMMS_WINDOW\|VALUE=12MIN\|SEQ=0043` | 10.000 ms | Pode perder janela de comunicação. |

Esses prazos contextualizam criticidade; não são deadline de rádio, garantia de
tempo real nem requisito de voo. Tocar no cartão só seleciona. A confirmação
explícita registra a escolha antes de avançar, evitando que toque acidental
dispare operação na Wisdom.

“Clássica” significa ECDH P-256 + AES-GCM, não o cenário legado CLASSIC do
firmware. “Pós-quântica” significa ML-KEM-512 + AES-GCM, não ML-KEM cifrando a
mensagem. “Com CRC32” adiciona quatro bytes ao plaintext antes da cifra; GCM
continua protegendo o pacote cifrado.

### PREPARE e PROTECT

Em NEXT_PREPARE, a confirmação sorteia incidente, cria ID como G000001 e envia
GAME_BEGIN. Em PREPARE, os caracteres são mostrados como bytes hexadecimais:
a criptografia trabalha sobre valores exatos. Com CRC, a Wisdom calcula
CRC32(payload) e anexa quatro bytes; sem CRC, a tela declara que não existe a
checagem adicional.

NEXT_PROTECT envia GAME_PROTECT. O replay de PROTECT só aparece após resposta
real. Para ECDH, mostra chave temporária do receptor, chave da origem e segredo
comum. Para ML-KEM, mostra KeyGen, Encaps e Decaps. Nos dois casos, HKDF gera
chave AES-128, a Wisdom cria nonce novo e AES-GCM produz ciphertext+tag. As
setas representam partes públicas ou cápsula, nunca segredo.

Quando existem, subtimings setup_us, initiator_us, responder_us, kdf_us,
rng_us e encrypt_us orientam as proporções da explicação. Eles são mostrados em
uma duração didática de 5,25 s; essa duração não é escala temporal real.

### TRANSMIT e VERIFY

Em NEXT_TRANSMIT, a confirmação usa RNG experimental para escolher uma posição
de bit. O log grava byte_index, bit_mask, bit_position, seed e sorteios. A
máscara é potência de dois: exatamente um bit muda. A aleatoriedade visual é
separada da experimental.

TRANSMIT tem 8 s didáticos: 18% envio, 22% travessia, 40% trecho de risco e 20%
chegada. Incidente não normal causa tremor e alerta genérico. A estética não
prova radiação ou invasão e a causa permanece escondida.

NEXT_VERIFY envia GAME_VERIFY. VERIFY mostra:

1. **Proteção AES-GCM**: OK ou FALHOU.
2. **CRC da mensagem**: OK, FALHOU, NÃO ADICIONADO ou NÃO VERIFICADO.

Esses textos vêm de campos reais aceitos pelo parser. O parser também exige
key_match=1; uma resposta inconsistente vira erro de protocolo, não resultado
científico novo.

### DIAGNOSE, resposta, retry, debrief e erro

DIAGNOSE compara a hipótese da pessoa ao cenário oculto. É uma atividade
didática: o sintoma não atribui uma causa física real. Em RX_MEMORY sem CRC32,
a própria interface indica que não havia evidência suficiente, pois a alteração
é silenciosa.

Em SELECT_RESPONSE, ACCEPT fica bloqueado para FRAME_REJECT, AUTH_REJECT e
APP_REJECT; aceitar contrariaria a evidência real. SAFE_MODE é decisão didática,
não comando de voo certificado. ENVIAR DE NOVO chama GAME_RETRY: preserva o
payload, mas exige chave, nonce e pacote novos.

O debrief só revela incidente após GAME_END confirmar limpeza da sessão e
restauração do baseline. Exibe missão, 240 MHz, KEX, CRC, resultado, tempo
acumulado e bytes. Tempo é processamento em us/ms/s, proxy de custo
computacional; não é watt, joule ou energia medida. Heap fica registrado, mas
a tela prioriza tempo e bytes. min_heap é mínimo global desde boot, não pico
isolado de algoritmo.

Depois do replay automático, a pessoa arrasta a mensagem pela revisão. Isso
move apenas a apresentação: não reexecuta criptografia, não altera estado,
falha ou resultado. ERROR apaga dados de missão e requer novo HELLO; se havia
sessão, o controlador tenta GAME_ABORT.

## 6. Modelo de incidente e tabela de resultados

O jogo público sorteia 30% NORMAL, 35% TAMPER e 35% RX_MEMORY. São pesos
didáticos configurados, não frequência medida em órbita.

~~~text
payload → CRC32 opcional → KEX/HKDF → chave AES → AES-128-GCM
        → transmissão/quadro → verificação GCM → plaintext
        → possível alteração em memória → CRC opcional
~~~

| Incidente | Onde/quando muda | Evidência prevista | Resultado | Leitura científica correta |
|---|---|---|---|---|
| NORMAL | Não há mutação. | GCM OK; CRC de aplicação OK quando existe. | DELIVERED | Mensagem íntegra neste ensaio. |
| TAMPER | Ciphertext muda; CRC de quadro é recalculado sem chave. | Quadro coincide; tag GCM falha. | AUTH_REJECT | Autenticação rejeitou adulteração simulada; não prova invasor real. |
| RX_MEMORY + CRC32 | Bit muda no plaintext depois de GCM aceitar. | GCM OK; CRC da mensagem falha. | APP_REJECT | CRC adicional detectou alteração posterior ao transporte autenticado. |
| RX_MEMORY + NONE | Mesma alteração em memória, sem CRC da aplicação. | GCM OK; nenhum CRC para conferir. | SILENT_CORRUPTION | Ausência de alarme não garante correção. |
| CHANNEL_BITFLIP (técnico) | Ciphertext muda após CRC de quadro. | CRC de quadro e GCM divergem. | FRAME_REJECT | Instrumentação técnica, não cenário sorteado/publicamente exibido. |

SILENT_CORRUPTION é resultado deliberado do modelo: a alteração ocorre depois
da autenticação criptográfica e não havia CRC de aplicação para comparar o
conteúdo atual com a referência.

## 7. Protocolo transacional

Uma partida usa um ID ativo e a ordem abaixo. ID ou ordem errados retornam
BAD_GAME_STATE e limpam a sessão.

~~~text
GAME_BEGIN <id> <BASELINE> <ECDH|MLKEM> <NONE|CRC32> <incidente> <payload_hex>
GAME_PROTECT <id>
GAME_TRANSMIT <id> <byte_index> <bit_mask>
GAME_VERIFY <id>
GAME_RETRY <id>                 # somente se a pessoa retransmitir
GAME_END <id> <ACCEPT|SAFE_MODE>

GAME_ABORT <id>                 # recuperação administrativa
~~~

| Comando | Responsabilidade | Prova exigida pela interface |
|---|---|---|
| GAME_BEGIN | Cria contexto e prepara CRC opcional. | ID, perfil, KEX, guardião, tamanho e checkpoint PREPARE coerentes. |
| GAME_PROTECT | Executa KEX, derivação, nonce, cifra e tag. | Checkpoint PROTECT e métricas positivas da sessão correta. |
| GAME_TRANSMIT | Monta quadro e injeta vetor conforme incidente. | Mesmo ID/vetor e checkpoint TRANSMIT. |
| GAME_VERIFY | Verifica GCM e CRC opcional. | Tabela de evidências coerente com incidente/guardião. |
| GAME_RETRY | Protege mesmo payload com material novo, sem falha. | DELIVERED, same_payload=1, fresh_key=1 e fresh_nonce=1. |
| GAME_END | Registra decisão, limpa sessão e restaura baseline. | ID, decisão, resultado, limpeza e 240 MHz restaurados. |
| GAME_ABORT | Descarta sessão ativa. | Usado para recuperação; não preserva resultado. |

As respostas não expõem segredo compartilhado, chave AES, nonce completo ou
ciphertext completo. Ficam métricas, flags, tamanhos e fingerprints curtos.

## 8. Logs, rastreabilidade e privacidade

Cada partida gera JSONL no esquema pqc-sat-stand-log-v2. Ele registra handshake,
seleção e confirmação separadas, origem physical|screen, sequência D27, uptime,
seed, sorteios, vetor de bit, comandos, respostas reais, animações,
diagnóstico, decisão, retry, erro e encerramento.

Isso permite demonstrar que:

- uma transição adiante possui button_confirmed físico ou de tela;
- a causa e o vetor foram sorteados antes de GAME_TRANSMIT;
- a animação só veio depois de stage_completed com resposta validada;
- retry usou payload igual e material criptográfico novo;
- a tela não avançou por inatividade.

As mensagens são payloads fixos, sem texto livre ou dados pessoais. Sessões de
visitantes não entram nas métricas oficiais. Fixture determinística, screenshots
e vídeos existem somente para testes/offline e não estão disponíveis no
entrypoint público.

## 9. Perguntas de banca e respostas seguras

**O que está sendo comparado?** ECDH P-256 e ML-KEM-512 para estabelecer
segredo, mantendo wolfCrypt, RNG, HKDF-SHA256, AES-128-GCM, placa e perfil
iguais. Não é CLASSIC versus ML-KEM.

**ML-KEM cifra a telemetria?** Não. ML-KEM estabelece segredo; HKDF deriva chave
AES; AES-GCM cifra e autentica a telemetria.

**Por que CRC se GCM já autentica?** GCM protege o pacote cifrado. CRC opcional
cobre o conteúdo da aplicação no modelo em que o bit muda depois da
decriptação. CRC não protege contra atacante.

**A demonstração prova radiação?** Não. A falha é injetada por software e
representa um tipo de efeito. O sintoma não prova causa física ou intenção.

**A animação mede o protocolo?** Não. É didática. Os tempos retornados pela
Wisdom são outra coisa; resultados oficiais requerem baterias controladas.

**Mediu energia?** Não. elapsed_us é proxy de custo computacional; watts/joules
exigiriam medição elétrica externa.

**80 MHz é especificação de CubeSat?** Não. OBC-1U-LIMITED é perfil experimental
de bancada e não é escolha pública. A Wisdom não é satélite qualificado.

## 10. Estado de evidência e limites

Há validação de host/fixture para a máquina de 17 estados, matriz de 32 casos,
soak offline, capturas e benchmark de renderização. O diagnóstico curto da
revisão FAIR atual na Wisdom confirmou handshake, ECDH/ML-KEM, missões, sessões,
falhas, caminho GAME_BEGIN → PROTECT → TRANSMIT → VERIFY → RETRY → END, retry e
BUTTON_PING físico observado.

Ainda faltam: D27 em repouso e uma partida visual somente por D27; partida
integral pela faixa verde e GAME_ABORT; prova de permanência em cada estado;
matriz física curta; monitor definitivo; bateria FAIR oficial; aceite longo,
três horas/reconexões e compreensão com cinco visitantes.

A formulação correta é: **há evidência de software e smoke curto de hardware,
mas a aceitação física final do estande permanece pendente**. Screenshot, vídeo
offline, fixture ou partida manual não substituem bateria científica nem gates
físicos.

## 11. Documentos relacionados

- docs/stand/EXPERIENCE_SPEC.md — interação e telas.
- docs/stand/SCIENTIFIC_ACCURACY.md — linguagem científica permitida.
- docs/stand/FINAL_VALIDATION.md — evidência e gates pendentes.
- docs/stand/RUNBOOK.md — preparação e procedimentos físicos.
- docs/DASHBOARD_ARCHITECTURE.md — limites entre UI, controlador, serial e fixture.
- GUIA_FINAL_APRESENTACAO.md — roteiro de apresentação e defesa.

As referências conceituais adotadas pelo projeto são NIST FIPS 203 (ML-KEM),
NIST SP 800-38D (GCM/GMAC) e material NASA sobre efeitos de radiação. Elas
fundamentam conceitos, mas não convertem a injeção de software em ensaio físico.
