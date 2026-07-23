# Validação final — jogo didático `STAGED_V1`

Última revisão: 2026-07-22.

## Decisão atual

Estado: **release candidate de software; não aprovado para uso público**.

O jogo por etapas está implementado e validado no host/fixture. O firmware
candidato compila, mas esta revisão `STAGED_V1` ainda não foi gravada nem
executada na Wisdom. Evidências físicas anteriores de `INVESTIGATE` e do fluxo
de nove estados continuam válidas como histórico, mas não validam os novos
comandos `GAME_*`, as confirmações D27/tela por partida ou o novo debrief.

## Evidência de software desta revisão

| Verificação | Resultado | Evidência |
|---|---|---|
| suíte integrada | PASS | 97 testes atuais; busca automática, narrativa direta, reconexão, controle de tela, A39 assíncrono, legado e jogo por etapas |
| matriz científica | PASS | 2 perfis × 2 modos de chave × 2 guardiões × 4 incidentes = 32 casos |
| confirmação explícita | PASS no modelo | transições v2 exigem `button_confirmed` de origem `physical|screen`; resposta/animação não avançam |
| busca automática | PASS no host/modelo | dashboard permanece aberto sem porta; somente `HELLO STAGED_V1` fecha o standby |
| narrativa direta | PASS no modelo | Terra/CubeSat, chamada única e `INICIAR MISSÃO`; clique ou D27 abrem as escolhas sem tela intermediária |
| reconexão | PASS no modelo | qualquer queda mostra busca; novo handshake apaga a partida e volta automaticamente à narrativa |
| A39 pelo verde | PASS no código/fixture; FAIL no hardware pós-fix | `ANALOG POT` preserva a sessão em `PROTECT` e o `GAME_TRANSMIT` seguinte é aceito; valor inválido ou timeout não avança; candidato corrigido ainda não foi gravado |
| ausência de timeout público | PASS | estados permanecem parados; flags públicas desabilitadas |
| retransmissão | PASS no fixture | mesmo payload, chave e nonce novos, resultado `DELIVERED` |
| soak offline | PASS | 50/50 partidas, 625 confirmações lógicas, 100 mudanças A39, 275 `GAME_*`, 25 retries, zero erros e zero crescimento RSS |
| renderização | PASS | por resolução: busca + 14 estados + 18 quadros dos replays; tela de tutorial ausente |
| orçamento médio | PASS | interface completa: 7,280 ms e 10,204 ms; limite 16,667 ms no host headless |
| vídeo offline | PASS | `staged_game_test_fixture.mp4`, permanentemente rotulado como fixture sem hardware |
| firmware | PASS apenas na compilação | 57.332 B RAM (17,5%), 932.173 B flash (71,1%), binário 938.752 B, SHA-256 `288d5f49…e5d51e`; nenhum upload |

O registro consolidado fica em
`docs/stand/evidence/software_validation.json`. Capturas ficam em
`states_staged_game/`, `states_staged_game_1920x1080/` e nos diretórios
`states_staged_game_replay*`; o soak fica em
`staged_game_soak.json`.

## Critérios automatizados cobertos

- toque em cartão seleciona sem mudar de fase; toque na faixa verde confirma;
- busca permanece sem placa e fecha automaticamente por handshake válido;
- D27 durante a busca não confirma a narrativa; depois dela, `INICIAR MISSÃO`
  ou D27 abrem diretamente a escolha da missão;
- D27 sem seleção não avança nem consome o próximo debounce;
- toda transição para a frente possui confirmação D27/tela correspondente no log;
- a faixa verde percorre todos os estados e, em `PROTECT`, espera A39 real;
- resposta serial e término de animação apenas liberam a confirmação;
- pacote só pode ser arrastado depois do replay automático e o gesto não muda
  controlador, resultado, estado ou liberação da confirmação;
- D27 antigo, repetido, durante comando, animação ou guarda é rejeitado;
- quatro proteções, quatro incidentes e dois perfis obedecem à tabela;
- `RX_MEMORY/NONE` produz `SILENT_CORRUPTION`;
- `RX_MEMORY/CRC32` produz `APP_REJECT`;
- `GAME_RETRY` usa o mesmo payload e fingerprints novos de chave/nonce;
- rejeição criptográfica bloqueia `ACCEPT`;
- erro, desconexão, ordem incorreta e `Home` apagam resultados da partida;
- desconexão cobre qualquer estado com a busca e a reconexão retorna à
  narrativa sem reutilizar resultado;
- nenhum timeout de interação ou debrief altera a tela;
- fixture, log V1, fluxo legado, `INVESTIGATE`, comandos de bancada e fachadas
  continuam compatíveis.

## Fronteira da evidência física existente

Já foi verificado em 2026-07-21, com o firmware investigativo anterior:

- Wisdom identificada em `/dev/ttyUSB0`;
- firmware `INVESTIGATE` gravado;
- quatro incidentes curtos e um smoke administrativo até `SUMMARY`;
- dashboard conectado parado em `ATTRACT` por oito segundos;
- duas janelas de 30 s e 45 s sem observar `BUTTON_PING`.

Isso comprova a base AES-GCM/ML-KEM/CRC e o comando legado naquela revisão.
Não comprova `game=STAGED_V1`, `GAME_BEGIN…GAME_END`, botão D27 atual, A39 em
todas as combinações, material novo de retry ou ausência de avanço automático
em cada um dos 14 estados.

## Gates físicos obrigatórios

| Gate | Estado | Critério de fechamento |
|---|---|---|
| flash do candidato | FAIL | gravar exatamente o firmware atual e registrar hash/build |
| handshake novo | FAIL | observar `HELLO ... game=STAGED_V1` |
| D27 físico | FAIL | repouso `button=0`, pressionado `button=1`, evento com `pot` e uptime novo |
| protocolo transacional | FAIL | executar todos os `GAME_*`; rejeitar ordem e ID errados |
| partida visível D27 | FAIL | uma partida completa com todos os avanços por D27 físico no JSONL v2 |
| partida visível verde | FAIL | busca automática, abertura confirmada e uma partida completa pelo verde, inclusive `ANALOG POT` em `PROTECT` |
| permanência dos estados | FAIL | deixar cada estado parado e provar ausência de avanço/reset |
| A39 e matriz curta | FAIL | variar bit e testar quatro proteções e incidentes principais |
| retransmissão real | FAIL | mesmo payload, chave/nonce novos e `DELIVERED` |
| monitor definitivo | FAIL | confirmar legibilidade e controles na montagem final |
| 30 partidas / 3 h | FAIL | >100 D27, >100 mudanças A39 com delta ADC ≥16, dez reconexões, zero invariantes violados |
| cinco visitantes | FAIL | mediana 120–180 s e critérios 4/5 de compreensão |

Nenhum desses itens pode ser promovido por fixture, screenshot, vídeo ou
acionamento administrativo.

## Procedimento curto do operador

```text
python3 tools/firmware_deploy.py --upload
python3 tools/stand_diagnostics.py \
  --port /dev/ttyUSB0 --full --wait-button-seconds 30

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
python3 tools/stand_hardware_smoke.py \
  --port /dev/ttyUSB0 --cycles 1 --production-timings
```

O operador deve pressionar D27 durante o diagnóstico e em cada liberação do
smoke. Depois deve executar na interface uma partida completa por D27 e outra
pelo botão verde, conferindo a leitura A39 sob demanda, e testar permanência
dos estados conforme `RUNBOOK.md`.

## Gate longo do operador

O agente não inicia o gate longo. O operador usa:

```bash
python3 dashboard.py --port /dev/ttyUSB0 \
  --log-dir logs/stand/acceptance --restart-on-crash

python3 tools/validate_stand_logs.py \
  logs/stand/acceptance/AAAAMMDD/*_stand_hardware_*.jsonl
```

O relatório `hardware_acceptance_summary.json` precisa ter todos os gates em
`true`, inclusive `confirmation_transition_invariant` e
`median_duration_120_180`.

## Entregáveis

| Entregável | Estado |
|---|---|
| código, configuração v3, parsers, fixture v2 e firmware | PASS em software |
| testes, soak, benchmark, 66 capturas e vídeo offline | PASS |
| documentação, guia do apresentador e catálogo técnico | PASS |
| log de partida `STAGED_V1` em hardware | FAIL — ainda não produzido |
| vídeo físico com D27 | FAIL — ainda não produzido |
| aceite de três horas | FAIL — ainda não executado |
| avaliação com cinco visitantes | FAIL — ainda não executada |
| tag de release | RETIDA até todos os gates físicos passarem |

## Conclusão

A implementação atende ao contrato planejado no host e preserva o legado. A
extensão não deve ser descrita como pronta para o estande até o firmware atual
ser gravado e os gates físicos, de montagem e compreensão passarem.
