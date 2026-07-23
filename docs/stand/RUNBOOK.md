# Runbook do jogo PQC-SAT

## 1. Pré-requisitos

- notebook com Python, pygame-ce e pyserial instalados;
- BlackBoard Wisdom conectada por USB;
- firmware candidato com `game=STAGED_V1` já gravado;
- D27 em repouso como `button=0` e pressionado como `button=1`;
- A39 variando de forma observável;
- suspensão de tela e do sistema desabilitada pelo operador.

Não existe fallback simulado no programa do evento. Se a placa não estiver
presente e validada, a interface não abre.

Se o diagnóstico reconhecer a Wisdom mas informar firmware sem `STAGED_V1`, o
operador deve compilar sem gravação e, depois de revisar o resultado, autorizar
o upload explicitamente:

```text
python3 tools/firmware_deploy.py
python3 tools/firmware_deploy.py --upload
```

O segundo comando identifica a placa por `HELLO`, grava o binário e só termina
com sucesso após o novo firmware responder `game=STAGED_V1`.

## 2. Identificar a placa

Na raiz do repositório:

```text
python3 -m serial.tools.list_ports -v
python3 tools/stand_diagnostics.py --check-only
```

O segundo comando sonda todas as portas por `HELLO`. O esperado é:

```text
porta selecionada: /dev/ttyUSB0
```

e retorno zero após confirmar `node=PQC-SAT-WISDOM`,
`board=BlackBoard-Wisdom`, `proto=V1`, `game=STAGED_V1` e `uptime_ms` válido.

Se houver duas Wisdoms, use:

```text
python3 tools/stand_diagnostics.py --check-only --port /dev/ttyUSB0
```

## 3. Diagnóstico curto

Sem executar bateria longa:

```text
python3 tools/stand_diagnostics.py --port /dev/ttyUSB0 --wait-button-seconds 30
```

Confirme fisicamente o D27 durante a janela. Para validar também a sequência
transacional e rejeição de ordem:

```text
python3 tools/stand_diagnostics.py --port /dev/ttyUSB0 --full --wait-button-seconds 30
```

Esse comando altera temporariamente o perfil, executa operações curtas e
restaura o baseline. O relatório deve registrar `active_game_a39` entre
`GAME_PROTECT` e `GAME_TRANSMIT`, com o mesmo ID chegando a `TRANSMIT`; isso
detecta a regressão em que `ANALOG POT` apagava a sessão. O diagnóstico não
substitui o gate longo.

## 4. Abrir a interface única

Tela cheia com descoberta automática:

```text
python3 dashboard.py
```

Ou com porta explícita e reinício Python após crash inesperado:

```text
python3 dashboard.py --port /dev/ttyUSB0 --restart-on-crash
```

Não há launcher Bash. O próprio Python faz descoberta, logging, loop visual e
reinício opcional.

Controles:

| Entrada | Efeito |
|---|---|
| toque/clique em cartão | seleciona ou troca a opção atual |
| faixa verde | confirma e pode avançar a fase; em `PROTECT`, lê `ANALOG POT` antes |
| D27 | confirma e pode avançar a fase |
| A39 | escolhe o bit capturado no checkpoint de transmissão |
| `Home` | aborta a sessão inteira |
| `F12` | mostra/oculta diagnóstico administrativo |
| `Esc` | alterna janela/tela cheia |
| `Ctrl+Q` | encerra o programa |

O standby não possui confirmação: ele avança automaticamente após validar a
Wisdom. A tela narrativa seguinte aceita `INICIAR MISSÃO` ou D27 e abre
diretamente a escolha da missão em todas as partidas. Espaço e Enter não
substituem os dois controles autorizados.

## 5. Smoke físico de uma partida

O script pré-seleciona cartões, mas todas as transições continuam dependendo
do D27 físico:

```text
python3 tools/stand_hardware_smoke.py --port /dev/ttyUSB0 --cycles 1 --production-timings
```

Resultado esperado: `result=PASS`, `completed_cycles=1`, transições cobrindo
`ATTRACT` até `DEBRIEF`, respostas `GAME_*` reais e confirmações D27 no log.
Esse smoke continua intencionalmente físico; depois dele, percorra manualmente
outra partida pela faixa verde e confirme `ANALOG POT` no JSONL.

## 6. Falhas comuns

### Nenhuma porta serial

Reconecte o USB e confira:

```text
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/*
```

### Permissão negada

Confira o grupo do dispositivo e do usuário. A correção persistente usual é
adicionar o usuário ao grupo responsável pela serial e iniciar nova sessão. Não
execute o dashboard como root.

### Porta existe, mas não é aceita

O programa agora mostra o motivo da sondagem. Se o retorno indicar firmware sem
`STAGED_V1`, compile e grave o candidato conforme `firmware/README.md`; não
mascare o problema com uma porta fixa.

### Desconexão durante uma partida

A missão entra em `ERROR`, descarta resultados e exige novo handshake. Reconecte
a placa; depois use D27 ou a faixa verde para a recuperação autorizada pela
tela. `Home` aborta administrativamente.

## 7. Evidência offline, somente testes

As ferramentas abaixo não fazem parte da execução pública:

```text
python3 tools/stand_soak.py --cycles 50
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/capture_stand_evidence.py
python3 tools/generate_game_evidence.py
```

Elas usam fixture determinística e devem permanecer rotuladas como teste.

## 8. Gate longo

O agente nunca inicia baterias longas. O operador executa conscientemente:

```text
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30
```

Depois, execute 30 partidas físicas, três horas de exposição, mais de 100
confirmações D27, 100 mudanças A39 e dez reconexões. Inclua ciclos pelo verde,
mas preserve a contagem física exigida. Registre zero transições sem
confirmação e zero resultados reaproveitados. O teste de compreensão exige cinco
visitantes e os critérios de `FINAL_VALIDATION.md`.
