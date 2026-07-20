# Rastreabilidade de requisitos do handover SBPC

Data da auditoria: 2026-07-20

Este documento confronta os critérios do
`HANDOVER_ESTANDE_SBPC_PQC_SAT.md` com evidência verificável da branch
`sbpc-stand-demo`. `PASS` significa requisito comprovado no escopo indicado;
`PARCIAL` ou `FAIL` mantém a release final bloqueada.

## P0 obrigatório

| # | Requisito | Estado | Evidência atual | Fechamento restante |
|---:|---|---|---|---|
| 1 | versão original preservada | PASS | `main` e `game` permanecem em `abd65a3`; ZIP local não foi alterado | nenhum |
| 2 | auditoria técnica concluída | PASS | `docs/stand/AUDIT_EXISTING.md` | nenhum |
| 3 | AES-128/256 resolvido pelo código | PASS | firmware usa chave de 16 B e retorna `cipher=AES-128-GCM`; smoke real aceito pelo parser | nenhum |
| 4 | baseline nomeado corretamente | PASS | UI usa `BASELINE AES-GCM`; `SCIENTIFIC_ACCURACY.md` proíbe chamá-lo de ECDH | nenhum |
| 5 | localização da falha CRC descrita corretamente | PASS | tela `FAULT_NONE`, tela `FAULT_CRC` e documentação identificam harness de payload separado de AES-GCM | nenhum |
| 6 | modo estande em tela cheia | PARCIAL | `pygame.FULLSCREEN`, alternância por `Esc` e renderização 1366×768/1920×1080 testados | ensaiar tela cheia no monitor definitivo |
| 7 | fluxo de até 100 segundos | PASS | ciclo real com configuração de produção: 51,55 s até `SUMMARY`; teste automatizado limita o pior caso visual a 100 s | nenhum |
| 8 | botão físico inicia e avança | FAIL | parser e firmware estão testados; duas janelas, de 30 s e 45 s, não observaram `BUTTON_PING` | repetir com acionamento físico observado |
| 9 | potenciômetro seleciona bit | PASS | smoke real: A39=2884 → byte 28, máscara `0x40`, bit global 230 | resistência física pendente, sem invalidar o ciclo curto |
| 10 | CLASSIC e PQC usam mesmo payload | PASS | JSONL real contém o mesmo payload hexadecimal nas três missões | nenhum |
| 11 | comparação 240/80 ao vivo ou campanha identificada | PASS | smoke real confirmou `BASELINE/240` e `OBC-1U-LIMITED/80`; fixture mantém selo de campanha | nenhum |
| 12 | mesma falha em NONE e CRC32 | PASS | JSONL real repete payload, byte 28, máscara `0x40`, `0x34 → 0x74` | nenhum |
| 13 | métricas de hardware ou fixture identificada | PASS | fontes tipadas `hardware-live` e `official-campaign-fixture`; UI mantém selo persistente | nenhum |
| 14 | modo simulado explicitamente rotulado | PASS | screenshots, vídeo e testes contêm `MODO VISUAL SIMULADO` | nenhum |
| 15 | reset automático | PASS | teste automatizado e temporizador de 18 s; perfil 240 MHz é restaurado | nenhum |
| 16 | funcionamento offline | PASS | inicializador e fluxo completo passaram sem rede usando fixture local vinculada por SHA-256 | testar também no notebook definitivo |
| 17 | 30 ciclos sem crash | FAIL | 20/20 ciclos reais administrativos e 50/50 offline passaram | executar 30+ ciclos físicos na campanha longa |
| 18 | runbook pronto | PASS | `docs/stand/RUNBOOK.md` isola logs de aceite e documenta abertura, operação e recuperação | revisão por segundo operador ainda recomendada |
| 19 | vídeo de backup pronto | PASS | `docs/stand/evidence/stand_backup_simulated.mp4`, 36 s, 1366×768, rótulo de simulação | testar reprodução no monitor definitivo |
| 20 | ensaio geral concluído | FAIL | smoke real administrativo não é ensaio completo de montagem e público | executar ensaio no conjunto físico final |

Resultado P0: **16 PASS, 1 PARCIAL e 3 FAIL**. A implementação permanece
release candidate e não deve receber tag final.

## Gates adicionais das etapas

| Gate | Estado | Evidência | Limitação |
|---|---|---|---|
| parser, estados, timeout e ordem | PASS | 123 testes Python | nenhum conhecido nos casos cobertos |
| 20 repetições coerentes do bit flip | PASS | 20/20 ciclos reais administrativos, zero divergências nos pares `NONE`/`CRC32` | ações físicas continuam no gate longo separado |
| recuperação USB | PARCIAL | cliente reconecta, handshake antigo é invalidado e há teste lógico | dez recuperações físicas pendentes |
| resistência de 3 h | FAIL | não executada | operador deve executar 2 h de atração + 1 h de ciclos |
| 100 ações de botão | FAIL | zero eventos físicos no JSONL de smoke | realizar pelo menos 100 ações físicas |
| 100 mudanças do potenciômetro | FAIL | sessão de 20 ciclos: 20 amostras, 6 transições e 2 posições sem giro deliberado | realizar pelo menos 100 mudanças físicas de posição |
| teste com cinco pessoas | FAIL | somente template CSV | coletar respostas e verificar os critérios 4/5 |

## Entregáveis exigidos

| Entregável | Estado | Caminho ou evidência |
|---|---|---|
| código, testes, fixture, scripts e configuração | PASS | `stand_demo.py`, `tests/test_stand_demo.py`, `fixtures/stand/`, `scripts/`, `config/stand_demo.json` |
| auditoria, especificação, runbook, precisão, validação e changelog | PASS | `docs/stand/` |
| screenshot de cada estado | PASS | `docs/stand/evidence/states/` |
| log de ciclo completo em hardware | PASS | `docs/stand/evidence/hardware_production_timing_cycle.jsonl` |
| resultado dos testes automatizados | PASS | `docs/stand/evidence/software_validation.json`: 123 testes e demais comandos obrigatórios |
| vídeo de backup | PASS | `docs/stand/evidence/stand_backup_simulated.mp4` |
| vídeo do fluxo completo em hardware | FAIL | não capturado | filmar o ensaio com botão físico |
| resultado dos 30 ciclos | FAIL | não produzido | executar validador sobre a campanha longa |
| tabela preenchida de cinco avaliações | FAIL | existe apenas `AUDIENCE_TEST_TEMPLATE.csv` | realizar teste de compreensão |
| hash e tag de release | PARCIAL | hashes de commits existem; tag foi corretamente retida | criar tag somente após todos os gates |

## Decisão de release

O software e o ciclo curto em hardware estão validados. O handover completo
ainda não está encerrado porque botão físico, monitor/montagem, resistência,
vídeo real e avaliação com público exigem ação presencial. O procedimento
exato para produzir essas evidências está em `docs/stand/RUNBOOK.md`.
