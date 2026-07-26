# PQC-SAT — Missão Bit Flip

Jogo didático em Python, executado com uma BlackBoard Wisdom real. Os cartões
selecionam opções; o botão verde ou o D27 confirmam cada avanço. A cada envio,
o experimento sorteia e registra se haverá um incidente e qual bit será usado.

Não existe modo simulado no programa de produção. A fixture determinística é
importada somente por testes e ferramentas de evidência offline.

## Executar

Instale as dependências:

```text
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-hardware.txt
```

Conecte a Wisdom com o firmware atual e execute, na raiz do repositório:

```text
python3 dashboard.py
```

O programa abre imediatamente uma tela de busca e sonda todas as portas
seriais em um worker não bloqueante. Essa tela avança automaticamente para a
abertura narrativa somente quando recebe:

```text
node=PQC-SAT-WISDOM board=BlackBoard-Wisdom proto=V1 game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1
```

Para indicar uma porta explicitamente:

```text
python3 dashboard.py --port /dev/ttyUSB0
```

Opções operacionais úteis:

```text
python3 dashboard.py --windowed
python3 dashboard.py --port /dev/ttyUSB0 --restart-on-crash
python3 dashboard.py --help
```

Se a interface não reconhecer a placa, rode a mesma sondagem sem abrir o
Pygame:

```text
python3 tools/stand_diagnostics.py --check-only
python3 -m serial.tools.list_ports -v
```

No Linux, confira também:

```text
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/*
```

Ausência de porta, permissão insuficiente, dispositivo errado e firmware sem
`game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` geram mensagens
diferentes. Informar `--port` não pula a validação: a porta explícita também
precisa responder ao `HELLO` correto.

## Interface única

`dashboard.py` é o único entrypoint público. O fluxo antigo do dashboard, o
runner `stand_demo.py`, os launchers Bash e as opções de produção simulada
foram removidos.

O jogo possui os estados:

1. `ATTRACT`;
2. `SELECT_MISSION`;
3. `SELECT_KEY_MODE`;
4. `SELECT_GUARD`;
5. `NEXT_PREPARE`;
6. `PREPARE`;
7. `NEXT_PROTECT`;
8. `PROTECT`;
9. `NEXT_TRANSMIT`;
10. `TRANSMIT`;
11. `NEXT_VERIFY`;
12. `VERIFY`;
13. `DIAGNOSE`;
14. `SELECT_RESPONSE`;
15. `RETRY` quando escolhida;
16. `DEBRIEF`;
17. `ERROR` em falha segura.

Na abertura, o standby serve somente para procurar a Wisdom: não tem botão e
desaparece automaticamente após o handshake válido. A tela seguinte preserva
Terra e CubeSat; o cabeçalho mostra `SALVE A MENSAGEM EM ÓRBITA` e a área
principal contém apenas o botão `INICIAR MISSÃO`, não avança por tempo e
também aceita D27. Essa confirmação
abre diretamente a escolha da missão em todas as partidas. Depois disso, toque
em cartão altera `pending_choice`, enquanto o controle contextual ou um novo
D27 confirmam a etapa.
Respostas seriais e fim de animação apenas liberam essa confirmação. `Home`
aborta a partida inteira; nenhuma tecla simula D27.

Na escolha 2/3, os cartões apresentam explicitamente
`ECDH P-256 + AES-GCM` e `ML-KEM-512 + AES-GCM`. Antes de cada etapa, uma tela
“A seguir” mostra imediatamente o que acontecerá, com ícones simples e o botão
`CONTINUAR`; D27 e faixa verde também confirmam.

Depois do replay de `PROTECT`, a pausa `NEXT_TRANSMIT` apresenta o próximo
movimento. D27 ou faixa verde confirmam o envio, e o dashboard sorteia um vetor
single-bit reproduzível sem solicitar A39. O firmware preserva `ANALOG POT` e
o mapeamento do potenciômetro somente para diagnóstico e engenharia.

Visualmente, a busca técnica fica fora dos 17 estados, que formam quatro atos:
receber a missão, montar o
sistema, executar a operação e comandar a resposta. Terra, CubeSat, órbita e
estações são desenhados proceduralmente. Os cartões de escolha permanecem
quadrados, mostram ícone, título e uma frase curta; a missão preserva o payload
em lista compacta. A apresentação pública fixa a CPU em `BASELINE/240 MHz`;
o perfil de 80 MHz permanece apenas nas ferramentas técnicas. A configuração
da partida aparece somente no relatório final. As etapas só reproduzem uma
animação didática depois de uma resposta `GAME_*` validada. O tempo real da
Wisdom permanece separado do replay ampliado.

Cada partida tem 70% de chance de incidente: 35% de radiação simulada na
mensagem recebida, 35% de tentativa de invasão simulada e 30% de envio normal.
A transmissão ampliada dura 8 s. Ida e volta exibem trechos de risco sempre
amarelos; quando há incidente, a surpresa visual ocorre somente no centro da
volta, depois que o pacote deixou o satélite. Vermelho fica restrito ao alerta,
à distorção, às ondas e às partículas do evento. A causa continua escondida
até o relatório final.

Na etapa de proteção, origem e receptor aparecem separados. Chave pública
ECDH ou ML-KEM, cápsula, segredo compartilhado, HKDF-SHA256, nonce e AES-GCM
são encadeados visualmente sem exibir segredos ou confundir o replay com tempo
real.

Quando a reprodução automática termina, a própria mensagem fica destacada e
pode ser arrastada entre as estações de preparação, proteção, transmissão e
retry. A verificação final é um processo visual direto, sem timeline: pacote,
AES-GCM, CRC opcional e resultado. O payload fica centralizado na primeira etapa.
Esse arraste é somente visual: não muda escolha, resultado, liberação da
confirmação ou estado da sessão. Antes de cada uma das quatro etapas, uma tela
ilustrada antecipa a próxima ação e pede uma confirmação extra antes do próximo
`GAME_*`.

## Protocolo do jogo

O firmware mantém uma única sessão transacional:

```text
GAME_BEGIN <id> <profile> <ECDH|MLKEM> <NONE|CRC32> <incident> <payload_hex>
GAME_PROTECT <id>
GAME_TRANSMIT <id> <byte_index> <bit_mask>
GAME_VERIFY <id>
GAME_RETRY <id>
GAME_END <id> <ACCEPT|SAFE_MODE>
GAME_ABORT <id>
```

Comandos fora de ordem ou com ID divergente retornam `BAD_GAME_STATE`. O
firmware usa wolfCrypt nas quatro combinações de KEX e CRC. ECDH P-256 e
ML-KEM-512 estabelecem o segredo; ambos passam pelo mesmo HKDF-SHA256 e pelo
mesmo AES-128-GCM. O perfil primário usa código portátil, sem assembly
específico do alvo nem aceleração criptográfica. `GAME_RETRY` reutiliza o
payload, sem falha injetada, mas gera chave e nonce novos.

Os cenários `MISSION CLASSIC|PQC`, além de `FAULT`, `INVESTIGATE` e demais
comandos de bancada, continuam disponíveis no firmware e no console serial,
mas não têm
botões nem um segundo dashboard:

```text
python3 tools/serial_console.py --all-commands
```

## Arquitetura

```text
dashboard.py                         entrypoint Python único
pqc_sat/cli.py                       composição, descoberta e loop Pygame
pqc_sat/infrastructure/wisdom.py     sondagem HELLO e validação STAGED_V1/FAIR_V1/FAIR_SESSION_V1
pqc_sat/infrastructure/serial_client.py transporte serial não bloqueante
pqc_sat/stand/investigation.py       máquina de estados e confirmações explícitas
pqc_sat/stand/model.py               tipos e validação das respostas GAME_*
pqc_sat/ui/game.py                   interface pública única
pqc_sat/ui/game_art.py               atos, ícones e timelines didáticas
pqc_sat/ui/scene.py                  Terra, órbita e cenário procedural
pqc_sat/ui/panel/investigation_view.py telas do jogo
config/game.json                     configuração pública v3
firmware/                            implementação Arduino/PlatformIO
```

O código-fonte do wolfSSL não faz parte do Git do projeto. Instale localmente a
revisão GPLv3 oficial ou a distribuição comercial licenciada conforme
[`firmware/WOLFSSL_LOCAL.md`](firmware/WOLFSSL_LOCAL.md). O build
FAIR_V1 é:

```text
python3 -m platformio run -e robocore_wisdom_esp32_fair
```

A coleta estatística nova fica separada dos resultados históricos:

```text
python3 tools/kex_metrics_battery.py --dry-run
python3 tools/kex_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --deployment-manifest logs/firmware/<manifesto_deploy>.json \
  --timeout 20 \
  --fresh-cycles 100 \
  --session-repeats 30 \
  --message-counts 1 100 500 1000 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

A segunda execução mede sessões novas e amortizadas e é uma bateria longa para
o operador, não um passo da demo. O dashboard mostra tempo, bytes e heap apenas
no debrief da partida; nunca alimenta o resultado oficial.

Os logs novos usam `pqc-sat-stand-log-v2` e ficam, por padrão, em
`logs/stand/YYYYMMDD/`. Eles separam seleção, confirmação D27/tela, comandos,
respostas, animações, diagnóstico, decisão e encerramento.

## Testes sem hardware

A simulação existe apenas sob `tests/` e ferramentas explicitamente rotuladas
como teste:

```text
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
python3 tools/stand_soak.py --cycles 50
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/capture_stand_evidence.py
python3 tools/generate_game_evidence.py
```

Essas execuções não validam USB, D27, A39, heap ou criptografia na placa e não
podem ser apresentadas como partida real.

Validação mínima de software:

```text
python3 -m py_compile dashboard.py
python3 -m compileall -q pqc_sat
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import dashboard"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
git diff --check
```

Build do firmware, sem gravar a placa:

```text
python3 tools/firmware_deploy.py
```

Depois de revisar o build, o operador autoriza explicitamente a gravação e a
validação automática do novo handshake com:

```text
python3 tools/firmware_deploy.py --upload
```

O utilitário é Python, não usa shell/Bash, identifica a Wisdom por `HELLO`
antes de gravar e exige `game=STAGED_V1 kex=FAIR_V1` e
`session_bench=FAIR_SESSION_V1` depois do reset. Após o sucesso, ele imprime o
caminho de um manifesto JSON com hashes do binário e das fontes, porta e ambos
os handshakes. O manifesto inclui ainda um hash determinístico da árvore
wolfSSL local, sem copiar seu conteúdo. Para fixar uma porta:

```text
python3 tools/firmware_deploy.py --upload --port /dev/serial/by-id/<wisdom>
```

O agente não inicia baterias longas. O operador deve seguir
[`docs/stand/RUNBOOK.md`](docs/stand/RUNBOOK.md) para o smoke físico e os gates
de estande.
