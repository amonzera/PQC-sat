# Arquitetura da interface única

## Decisão vigente

Existe um único programa público: `python3 dashboard.py`. Ele sempre exige uma
BlackBoard Wisdom real com `proto=V1`, `game=STAGED_V1`, `kex=FAIR_V1` e
`session_bench=FAIR_SESSION_V1`.

Foram removidos:

- o dashboard manual/simulado anterior;
- o entrypoint `stand_demo.py`;
- a máquina de estados legado;
- os launchers Bash;
- flags de produção que escolhiam simulação ou fluxo.

A fixture determinística continua disponível somente para testes, screenshots,
soak offline e benchmark de renderização.

## Composição

```text
dashboard.py
  -> pqc_sat.cli
       -> pqc_sat.infrastructure.serial_client
            worker serial não bloqueante
            -> pqc_sat.infrastructure.wisdom
                 enumera portas + fallbacks Linux
                 sonda e valida HELLO continuamente
       -> pqc_sat.stand.investigation
            escolhas pendentes, GAME_* e confirmação D27/tela
       -> pqc_sat.ui.game
            busca automática, introdução, eventos e única superfície pública
            -> pqc_sat.ui.panel.investigation_view
```

## Limites

| Camada | Responsabilidade | Não faz |
|---|---|---|
| `infrastructure/wisdom.py` | descobrir e autenticar a identidade operacional da placa | não escolhe por descrição USB |
| `infrastructure/serial_client.py` | transportar frames sem bloquear o Pygame | não avança estado |
| `stand/model.py` | tipar escolhas e validar respostas reais | não desenha |
| `stand/investigation.py` | aplicar confirmação explícita, ler A39 sob demanda e ordenar `GAME_*` | não trata eventos Pygame |
| `ui/game.py` | manter a busca até `HELLO`, separar busca/narrativa e rotear cartões | não emula D27 por teclado |
| `ui/replay.py` | controlar somente a posição visual da mensagem após o replay validado | não confirma, não libera o próximo avanço e não altera a sessão |
| `ui/panel/investigation_view.py` | desenhar as 14 telas | não muda o controlador |

## Descoberta da Wisdom

A descoberta combina as portas do pyserial com `/dev/serial/by-id/*`,
`/dev/ttyUSB*` e `/dev/ttyACM*`. Todas são sondadas; `CP210` e fabricante não
são mais usados como prova de identidade.

Uma porta só é aceita após responder:

```text
node=PQC-SAT-WISDOM
board=BlackBoard-Wisdom
proto=V1
game=STAGED_V1
kex=FAIR_V1
uptime_ms=<uint32>
```

Se duas placas válidas responderem, o operador deve escolher com `--port`. Uma
porta explícita também é sondada, portanto não contorna o requisito de firmware.

O Pygame abre antes da descoberta. O worker serial sonda continuamente sem
bloquear o loop; a tela de busca desaparece automaticamente apenas após um
`HELLO` válido. Qualquer desconexão reapresenta essa camada. Depois de um novo
handshake, uma partida interrompida é apagada e o controlador retorna
administrativamente a `ATTRACT`. `--no-splash` oculta apenas essa visualização
administrativa e nunca elimina a exigência da placa.

Em `ATTRACT`, `INICIAR MISSÃO` ou D27 abrem diretamente a escolha de missão em
todas as partidas. Depois disso, `confirm` pode vir de D27 ou do controle
contextual da tela. Em `PROTECT`, a
origem de tela cria um `PendingCommand("ANALOG POT", "screen_pot", ...)`; a
transição só acontece quando a resposta traz A39 dentro da faixa configurada.

## Regra de produção versus teste

`pqc_sat.ui.game.GamePanel.__init__` recusa um controlador que não esteja em
`mode="hardware"`. O parser público não possui `--simulated`, fixture ou seletor
de fluxo.

Testes usam `GamePanel.for_test()` e `FixtureSerialClient` diretamente. Esses
pontos ficam fora do composition root de produção e são rotulados como teste em
seus relatórios.

## Execução e validação

```text
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
python3 tools/stand_diagnostics.py --check-only
```

```text
python3 -m py_compile dashboard.py
python3 -m compileall -q pqc_sat
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/benchmark_dashboard.py --width 1366 --height 768
git diff --check
```

O benchmark mede apenas renderização do host. Build local do firmware não prova
reconhecimento USB nem execução física; esses limites devem aparecer no handoff.
