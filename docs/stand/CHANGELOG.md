# Changelog do modo estande SBPC

## 2026-07-21 — apresentação integrada ao dashboard

- corrigida a arquitetura visual: `dashboard.py --presentation` e o alias
  `--stand` agora permanecem no loop, cenário e `DashboardPanel` originais;
- substituído o desvio de produção para o shell visual separado por um overlay
  nativo com nove estados, progresso, instruções físicas, medições e erro seguro;
- preservados `StandController`, parsers, fixture, logs e invariantes seriais já
  validados, sem duplicar o protocolo nem mover criptografia para o notebook;
- eventos `BUTTON_PING` agora são encaminhados pelo próprio `DashboardPanel`
  para a apresentação guiada, mantendo também o efeito visual do dashboard;
- capturas e smoke de renderização passaram a usar a superfície integrada;
- adicionado teste de integração dashboard–botão físico; suíte passa com 124
  testes.

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
