# Runbook do estande SBPC — PQC-SAT

Este guia permite montar, testar, operar e recuperar a experiência sem
conhecer o código.

## Material

- notebook e fonte;
- monitor externo, se disponível;
- BlackBoard Wisdom/ESP32 com o firmware desta branch;
- cabo USB principal e reserva;
- filtro de linha/extensão;
- suporte transparente para deixar botão e potenciômetro visíveis;
- etiqueta do botão: `INICIAR / VIRAR BIT`;
- etiqueta do potenciômetro: `ESCOLHA O BIT`;
- velcro ou abraçadeira para aliviar tração do cabo;
- mouse e teclado guardados, mas acessíveis ao operador;
- cópia offline deste repositório e do vídeo de contingência.

Não dependa de internet, som, login, Bluetooth, celular ou rede do evento.

## Checklist de abertura

1. Conecte fonte e monitor.
2. Conecte a Wisdom por USB e proteja o cabo contra tração.
3. Desative manualmente suspensão/bloqueio de tela no sistema operacional.
4. Confirme a porta sem abrir a aplicação:

   ```bash
   python3 tools/stand_diagnostics.py --check-only --port /dev/ttyUSB0
   ```

5. Execute o diagnóstico curto completo:

   ```bash
   python3 tools/stand_diagnostics.py --port /dev/ttyUSB0 --full
   ```

6. Confirme no relatório: `HELLO`, `STATUS`, `ANALOG POT`, duas missões e o
   par `FAULT` com status `OK`.
7. Inicie em tela cheia:

   ```bash
   ./scripts/run_stand.sh --port /dev/ttyUSB0 --restart-on-crash
   ```

8. Confirme o selo verde `HARDWARE REAL — BLACKBOARD WISDOM CONECTADA`.
9. Faça um ciclo: botão, comparação, potenciômetro, botão, conclusão.
10. Confira que a tela volta à atração e que surgiu um JSONL em
    `logs/stand/AAAAMMDD/`.
11. Limpe a mesa, esconda teclado/mouse e deixe botão/potenciômetro acessíveis.

Nunca use `--simulated` por engano na abertura. O script não migra para a
fixture automaticamente se a Wisdom faltar.

## Operação normal

- O visitante pressiona o botão físico para iniciar.
- O fluxo de 240/80 MHz é automático.
- Na tela `BIT`, o visitante gira o potenciômetro e pressiona o botão.
- O segundo ensaio usa automaticamente a mesma seleção.
- A conclusão reinicia após 18 s ou quando o botão é pressionado.
- Ajude verbalmente o visitante a manter o ciclo dentro de 75–100 s.

Fala curta:

> O baseline usa AES-GCM. No caminho pós-quântico, ML-KEM estabelece a chave e
> AES-GCM continua cifrando. Depois você muda um bit por software: sem o
> guardião ele passa silenciosamente neste harness; com CRC32, a mesma mudança
> fica observável.

## Controles administrativos

| Controle | Ação |
|---|---|
| `Esc` | alterna tela cheia/janela |
| `Ctrl+Q` | encerra a interface |
| `F12` | mostra/oculta diagnóstico técnico |
| `Home` | volta à atração sem apagar o log |
| `R` na tela de erro | reinicia a sessão visual |
| Espaço/Enter | representa o botão para ensaio do operador |
| setas/PageUp/PageDown | alteram o potenciômetro apenas em `--simulated` |

O visitante não precisa usar esses controles.

## Recuperação rápida

### A interface travou ou fechou

1. preserve o JSONL atual;
2. encerre somente a aplicação com `Ctrl+Q` ou pelo terminal;
3. execute novamente `./scripts/run_stand.sh --port /dev/ttyUSB0`;
4. faça um ciclo rápido antes de chamar outro visitante.

Com `--restart-on-crash`, somente saídas não zero reiniciam automaticamente;
um encerramento normal não entra em loop.

### A placa desconectou

1. a tela deve ir para `ERROR` e parar de aceitar novos valores;
2. reconecte o cabo principal ou o reserva;
3. aguarde novo handshake; use `F12` para conferir `ready=True`;
4. volte ao início e refaça o ciclo;
5. não apresente resultados antigos como leitura atual.

### O firmware não responde

1. pressione reset físico da Wisdom;
2. encerre a interface;
3. rode `python3 tools/stand_diagnostics.py --port /dev/ttyUSB0 --full`;
4. troque cabo/porta se necessário;
5. se não recuperar, use conscientemente o fallback abaixo.

### A tela externa falhou

Execute em janela no notebook:

```bash
./scripts/run_stand.sh --port /dev/ttyUSB0 --windowed
```

### Fallback sem hardware

O modo visual de contingência usa a fixture oficial e fica permanentemente
marcado como simulado:

```bash
./scripts/run_stand.sh --simulated
```

Para exibir o vídeo offline já gerado:

```bash
ffplay -autoexit -fs docs/stand/evidence/stand_backup_simulated.mp4
```

O vídeo e a fixture não são leitura atual da placa. Diga isso ao público.

## Validação longa antes do evento — executar pelo operador

Não execute esta validação durante atendimento ao público.

1. Abra uma sessão exclusiva para o aceite, sem misturar logs de smoke ou
   simulação:

   ```bash
   ./scripts/run_stand.sh --port /dev/ttyUSB0 \
     --stand-log-dir logs/stand/acceptance
   ```

2. Mantenha essa mesma sessão por pelo menos 3 h: 2 h em atração contínua e
   1 h com ciclos periódicos.
3. Complete pelo menos 30 ciclos sem reiniciar a aplicação. Mire 34 ciclos e
   use o botão também em `SUMMARY` para recomeçar; assim as três ações físicas
   por ciclo alcançam naturalmente mais de 100 pressões.
4. Registre pelo menos 100 mudanças distintas do potenciômetro.
5. Faça dez desconexões/reconexões USB controladas entre ciclos, aguardando o
   novo handshake antes de continuar.
6. Encerre normalmente com `Ctrl+Q`, para registrar `session_end`.
7. Convide cinco pessoas externas e preencha
   `docs/stand/evidence/AUDIENCE_TEST_TEMPLATE.csv`.
8. Valide apenas os JSONL de hardware desse diretório:

   ```bash
   python3 tools/validate_stand_logs.py \
     logs/stand/acceptance/AAAAMMDD/*_stand_hardware_*.jsonl
   ```

O gate padrão exige modo hardware, handshake, 30 ciclos, 100 ações de botão,
100 mudanças do potenciômetro, dez recuperações USB, três horas contínuas,
zero erros e todos os invariantes de payload/falha. O resultado deve ser
`PASS` em `docs/stand/evidence/hardware_acceptance_summary.json`.

## Teste de compreensão

Pergunte, sem induzir:

1. O que o ML-KEM fez?
2. O que o AES-GCM fez?
3. O que o CRC32 fez?
4. Houve radiação real?
5. Qual foi o principal custo observado?

Aceite: pelo menos 4/5 dizem que ML-KEM estabelece chave; 4/5 não atribuem
segurança contra atacante ao CRC; 4/5 entendem que a falha foi simulada; e a
mediana dos ciclos fica abaixo de 100 s.

## Checklist de encerramento

1. Encerre com `Ctrl+Q`.
2. Confirme `session_end` no último JSONL.
3. Copie os logs do dia para a mídia de backup.
4. Registre incidentes e ações tomadas.
5. Desconecte a Wisdom e guarde placa/cabos.
6. Carregue o notebook.
7. Antes do dia seguinte, rode novamente o diagnóstico completo.
