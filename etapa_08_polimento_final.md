# Etapa 08 - Polimento e entrega

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Transformar o protótipo validado em uma entrega demonstrável, auditável e
honesta sobre suas limitações.

## Software

1. Inicialização:
   - argumentos antes do display (implementado);
   - splash opcional (implementado);
   - `--no-splash` para testes (implementado);
   - mensagem clara de modo (implementado).
2. Help:
   - lista de comandos;
   - estado atual;
   - diferenças entre simulado e hardware.
3. Cleanup:
   - auto-save (implementado no reset e no fechamento);
   - fechar serial (implementado);
   - `pygame.quit()` (implementado);
   - traceback preservado em erro inesperado (implementado).
4. Performance:
   - cache de superfícies estáticas (implementado para nebulosa e overlay);
   - evitar criar superfícies grandes a cada frame (implementado);
   - medir FPS e uso de memória (implementado no topo, barra inferior e JSON).
5. Layout:
   - 1920x1080 (teste headless implementado);
   - 1366x768 (teste headless implementado);
   - teste físico no projetor (pendente de sala/equipamento).

Não envolva cada comando em `except Exception` que esconda bugs. Valide input
esperado e mantenha um handler de topo para cleanup e diagnóstico.

## Testes finais

```text
py_compile
import headless
testes do ExperimentEngine
testes de CRC
replay de JSON
demo simulada completa
demo hardware completa, se disponível
30 minutos de execução
desconexão serial
projetor
```

O critério é "nenhuma falha conhecida nos cenários testados", não "nenhum
crash possível".

## Material didático

Até cinco slides:

1. CubeSat, COTS e falhas transitórias;
2. ML-KEM e o que um KEM faz;
3. modelo de falha e classificação;
4. cenário A vs B;
5. resultados, limitações e conclusão.

Roteiro de 20 minutos:

```text
0-5 min   contexto e hipótese
5-8 min   explicar payload, fault e guard
8-10 min  executar demo
10-15 min interpretar JSON/timeline
15-18 min conectar com ML-KEM/ESP32
18-20 min limitações e perguntas
```

## Documentação final

- atualizar README;
- atualizar `agents.md`;
- marcar roadmap;
- anexar resultados ao relatório;
- identificar placa, firmware e commits;
- distinguir dados simulados e medidos;
- listar ameaças à validade.

## Checklist

- [x] Dependências reproduzíveis.
- [x] UI não mostra hardware inexistente.
- [x] Campanha reproduzível.
- [x] JSON auditável.
- [x] Demo A/B cronometrada.
- [ ] Projetor validado.
- [x] Slides e roteiro revisados em `APRESENTACAO_ROTEIRO.md`.
- [x] Limitações apresentadas no README, roadmap e roteiro.

## Estado em 2026-06-18

Software da etapa 8 implementado e coberto por testes headless. O arquivo
permanece aberto apenas porque projetor, campanha de 30 minutos e eventual
demo hardware dependem de validação física no equipamento da apresentação.

Na verificação de 2026-06-18, `/dev/ttyUSB0` foi detectada como CP2102N/Silicon
Labs, mas a abertura ficou bloqueada por permissões `root:dialout`. Para a
validação hardware final, libere temporariamente com `sudo chmod 666
/dev/ttyUSB0` ou adicione o usuário ao grupo `dialout` e entre novamente na
sessão.
