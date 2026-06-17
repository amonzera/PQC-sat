# agents.md - Guia para agentes de IA

Leia este arquivo inteiro antes de alterar o projeto.

## 1. Escopo

PQC-SAT é uma demonstração didática sobre:

- falhas transitórias simuladas em um sistema embarcado;
- diferença entre corrupção silenciosa e erro detectado;
- uso de mecanismos leves de integridade;
- integração com uma sessão ML-KEM-512 em ESP32.

O projeto tem duas camadas que não podem ser confundidas:

1. **Baseline atual**: dashboard Pygame em modo simulado.
2. **Arquitetura alvo**: campanha determinística, exportação JSON, firmware e
   bridge serial.

Nunca apresente uma funcionalidade planejada como concluída.

## 2. Fontes de verdade

Use esta precedência quando houver divergência:

1. comportamento verificado por testes;
2. `ROADMAP.md`, que consolida o plano técnico;
3. `projeto_final_pqc_esp32_cubesat.docx`, que define o objetivo acadêmico;
4. documentos `etapa_*.md`, que detalham tarefas;
5. este guia e o `README.md`.

Se um documento de etapa divergir do roadmap, corrija o documento antes de
implementar.

## 3. Estado atual verificado

### Implementado

- dashboard fullscreen em `dashboard.py`;
- Terra, CubeSat, estrelas, nebulosa e partículas procedurais;
- painel de telemetria e console;
- comandos simulados: `INJECT_FAULT`, `BIT_FLIP`, `PQC_STATUS`,
  `CRC_CHECK`, `PING`, `TELEMETRY`, `RESET_SESSION` e `HELP`;
- firmware serial `V1` para a RoboCore BlackBoard Wisdom;
- bridge serial Python e console `tools/serial_console.py`;
- modo padrão de `dashboard.py` tenta detectar a Wisdom e encaminha comandos do
  console visual para a ESP32 sem bloquear o loop Pygame;
- seed exclusiva para os resultados de falha (`42`);
- indicadores explícitos de modo simulado.
- mutação real de payload com CRC32 no dashboard e no firmware via
  `FAULT NONE|CRC32 payload_hex index mask`.

### Não implementado

- operação ML-KEM-512 real;
- mutação real de ciphertext ML-KEM;
- campanha A/B completa com a mesma lista de fault specs;
- exportação JSON e bateria de testes;
- modo de apresentação;
- slides e roteiro final.

## 4. Stack

### Atual

| Componente | Tecnologia |
|---|---|
| Linguagem validada | Python 3.14.5 |
| Renderização | pygame-ce 2.5.7 |
| Aplicação | `dashboard.py` monolítico |
| Assets | desenho procedural, sem arquivos externos |

### Planejada

| Componente | Tecnologia candidata |
|---|---|
| Serial | pyserial 3.5+ opcional |
| Firmware | ESP-IDF preferencialmente; Arduino somente se a biblioteca escolhida suportar |
| PQC | ML-KEM-512 na Wisdom; Kyber512 identificado apenas como fallback rotulado |

`pqm4` é voltado a ARM Cortex-M4 e não deve ser tratado como drop-in para
ESP32 Xtensa. `liboqs` é útil para prototipagem no host, mas não há no projeto
uma integração pronta com Arduino/ESP32. Há referências de Kyber512-90s e
ML-KEM-512 em ESP32; nenhuma dispensa validar a placa, o framework, a variante
e os vetores conhecidos usados neste projeto. Não chame Kyber pré-FIPS de
ML-KEM/FIPS 203.

## 5. Regras de implementação

- Preserve o baseline funcional e trabalhe incrementalmente.
- Mantenha o dashboard em um único arquivo Python até que exista motivo
  concreto e aprovação para modularização.
- Firmware pode e deve ter arquivos próprios sob `firmware/`.
- Use constantes `C_*` para cores reutilizadas.
- Use `pygame.SRCALPHA` quando transparência for necessária.
- Não bloqueie o loop principal com `sleep`, I/O serial ou criptografia longa.
- Não carregue imagens, sons ou fontes externas sem decisão explícita.
- Não mostre `ESP32 ONLINE`, `CRC ON` ou `ML-KEM ativo` sem evidência real.
- Resultados experimentais devem vir de bytes mutados e verificações reais.
- Mantenha a aleatoriedade do experimento separada da aleatoriedade visual.
- Trate `OBC-1U-LIMITED` como perfil experimental, não como especificação
  universal de CubeSat.
- Compare medições limitadas com o baseline integral do ESP32.
- Preserve alterações locais do usuário que não pertençam à tarefa.

Os tamanhos atuais são:

| Fonte | Tamanho |
|---|---:|
| `FONT_TITLE` | 26 |
| `FONT_HEADER` | 22 |
| `FONT_BODY` | 17 |
| `FONT_SMALL` | 15 |
| `FONT_CMD` | 17 |
| `FONT_PIXEL` / `FONT_LABEL` | 13 |

Esses valores ainda precisam de validação em projetor. Não afirme
legibilidade a cinco metros sem teste físico.

## 6. Modelo experimental obrigatório

Antes de implementar o guardião, defina:

- objeto corrompido: payload, ciphertext ou estado interno;
- instante da corrupção;
- região coberta pelo guardião;
- condição objetiva de cada resultado;
- vetor de falha reproduzível.

Para ML-KEM:

- `Decaps` sempre produz um segredo para entradas de tamanho válido;
- `sharedSecretA != sharedSecretB` deve ser chamado de `KEY_MISMATCH` observado
  pelo harness, não de erro explicitamente detectado pela decapsulação;
- detecção operacional exige confirmação no protocolo, por exemplo um MAC/tag
  calculado com a chave derivada.

Para checksums:

- armazene ou transmita o valor de referência antes da falha;
- compute novamente depois da falha;
- compare valores;
- não substitua isso por taxas aleatórias atribuídas a CRC/XOR.

## 7. Validação

Comandos mínimos antes de concluir uma alteração:

```bash
python3 -m py_compile dashboard.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import dashboard"
git diff --check
```

Para mudanças visuais, execute também:

```bash
python3 dashboard.py
```

Valide o fluxo real usado na apresentação, não apenas importação ou
compilação.

## 8. Próxima ordem de trabalho

1. Etapa 04: portar/instalar ML-KEM-512 na placa, registrar fonte/commit/licença
   e validar KAT.
2. Etapa 06: ligar bit-flips manuais e checksum ativável/desativável ao fluxo
   de payload e, depois do KEM estável, ao ciphertext.
3. Etapa 03: exportação JSON e bateria de testes com eventos e métricas de
   hardware.
4. Etapa 07: demo com a mesma campanha nos cenários A e B.
5. Etapa 08: testes, projetor, slides, roteiro e relatório.

Última revisão: 2026-06-17.
