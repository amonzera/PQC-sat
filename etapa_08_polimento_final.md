# Etapa 08 - Polimento e entrega

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Transformar o protótipo validado em uma entrega demonstrável, auditável e
honesta sobre suas limitações.

## Software

1. Inicialização:
   - argumentos antes do display;
   - splash opcional;
   - `--no-splash` para testes;
   - mensagem clara de modo.
2. Help:
   - lista de comandos;
   - estado atual;
   - diferenças entre simulado e hardware.
3. Cleanup:
   - auto-save;
   - fechar serial;
   - `pygame.quit()`;
   - traceback preservado em erro inesperado.
4. Performance:
   - cache de superfícies estáticas;
   - evitar criar superfícies grandes a cada frame;
   - medir FPS e uso de memória.
5. Layout:
   - 1920x1080;
   - 1366x768;
   - teste físico no projetor.

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

- [ ] Dependências reproduzíveis.
- [ ] UI não mostra hardware inexistente.
- [ ] Campanha reproduzível.
- [ ] JSON auditável.
- [ ] Demo A/B cronometrada.
- [ ] Projetor validado.
- [ ] Slides e roteiro revisados.
- [ ] Limitações apresentadas.
