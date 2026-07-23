# PQC-SAT — Missão Bit Flip

Jogo didático em Python, executado com uma BlackBoard Wisdom real. Os cartões
selecionam opções; o botão verde ou o D27 confirmam cada avanço; o
potenciômetro A39 seleciona o bit durante a transmissão.

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
node=PQC-SAT-WISDOM board=BlackBoard-Wisdom proto=V1 game=STAGED_V1
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
`game=STAGED_V1` geram mensagens diferentes. Informar `--port` não pula a
validação: a porta explícita também precisa responder ao `HELLO` correto.

## Interface única

`dashboard.py` é o único entrypoint público. O fluxo antigo do dashboard, o
runner `stand_demo.py`, os launchers Bash e as opções de produção simulada
foram removidos.

O jogo possui os estados:

1. `ATTRACT`;
2. `SELECT_MISSION`;
3. `SELECT_PROFILE`;
4. `SELECT_KEY_MODE`;
5. `SELECT_GUARD`;
6. `PREPARE`;
7. `PROTECT`;
8. `TRANSMIT`;
9. `VERIFY`;
10. `DIAGNOSE`;
11. `SELECT_RESPONSE`;
12. `RETRY` quando escolhida;
13. `DEBRIEF`;
14. `ERROR` em falha segura.

Na abertura, o standby serve somente para procurar a Wisdom: não tem botão e
desaparece automaticamente após o handshake válido. A tela seguinte preserva
Terra e CubeSat; ela mostra somente `SALVE A MENSAGEM EM ÓRBITA` e o botão
`INICIAR MISSÃO`, não avança por tempo e também aceita D27. Essa confirmação
abre diretamente a escolha da missão em todas as partidas. Depois disso, toque
em cartão altera `pending_choice`, enquanto o controle contextual ou um novo
D27 confirmam a etapa.
Respostas seriais e fim de animação apenas liberam essa confirmação. `Home`
aborta a partida inteira; nenhuma tecla simula D27.

No checkpoint `PROTECT`, o D27 traz o A39 no próprio `BUTTON_PING`; se o
visitante usar a faixa verde, o dashboard solicita `ANALOG POT` de forma
assíncrona e só avança após validar a leitura real. O firmware permite essa
consulta somente-leitura durante a sessão `GAME_*`, sem apagar o estado
`PROTECT`; os demais comandos de bancada continuam bloqueados.

Visualmente, a busca técnica fica fora dos 14 estados, que formam quatro atos:
receber a missão, montar o
sistema, executar a operação e comandar a resposta. Terra, CubeSat, órbita e
estações são desenhados proceduralmente. Os cartões de escolha são quadrados,
sem subtítulos internos, e destacam a arte causal e o título; a explicação da
opção aparece somente após a seleção. Os checkpoints só reproduzem uma
animação didática depois de uma resposta `GAME_*` validada. O tempo real da
Wisdom permanece separado do replay ampliado.

Quando a reprodução automática termina, a própria mensagem fica destacada e
pode ser arrastada entre as estações. Cada parada mostra o que entra, o que a
Wisdom fez, o que saiu e qual evidência real sustenta a explicação. Esse
arraste é somente visual: não muda escolha, resultado, liberação da confirmação ou
estado da sessão.

## Protocolo do jogo

O firmware mantém uma única sessão transacional:

```text
GAME_BEGIN <id> <profile> <CLASSIC|PQC> <NONE|CRC32> <incident> <payload_hex>
GAME_PROTECT <id>
GAME_TRANSMIT <id> <byte_index> <bit_mask>
GAME_VERIFY <id>
GAME_RETRY <id>
GAME_END <id> <ACCEPT|SAFE_MODE>
GAME_ABORT <id>
```

Comandos fora de ordem ou com ID divergente retornam `BAD_GAME_STATE`. O
firmware usa AES-128-GCM nas quatro combinações de chave e CRC; ML-KEM-512
estabelece o segredo no caminho PQC. `GAME_RETRY` reutiliza o payload, sem
falha injetada, mas gera chave e nonce novos.

Os comandos técnicos legados (`MISSION`, `FAULT`, `INVESTIGATE`, bancada e
baterias) continuam disponíveis no firmware e no console serial, mas não têm
botões nem um segundo dashboard:

```text
python3 tools/serial_console.py --all-commands
```

## Arquitetura

```text
dashboard.py                         entrypoint Python único
pqc_sat/cli.py                       composição, descoberta e loop Pygame
pqc_sat/infrastructure/wisdom.py     sondagem HELLO e validação STAGED_V1
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
antes de gravar e exige `game=STAGED_V1` depois do reset. Para fixar uma porta:

```text
python3 tools/firmware_deploy.py --upload --port /dev/serial/by-id/<wisdom>
```

O agente não inicia baterias longas. O operador deve seguir
[`docs/stand/RUNBOOK.md`](docs/stand/RUNBOOK.md) para o smoke físico e os gates
de estande.
