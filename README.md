# PQC-SAT Mission Control

Projeto didático da disciplina de Cibersegurança da Universidade Federal
Fluminense (UFF) sobre falhas transitórias, integridade e criptografia
pós-quântica em sistemas embarcados inspirados em CubeSats.

## Estado atual

O repositório contém hoje:

- um dashboard fullscreen em Pygame;
- um núcleo determinístico de mutação de payload com eventos auditáveis;
- comparação didática entre payload sem guardião e payload com CRC32;
- integração serial ESP32/notebook para comandos de bancada da Wisdom;
- backend ML-KEM-512 real no firmware, usando `mlkem-native` v1.1.0;
- medições de ML-KEM-512 até `PQC_BENCH 100` em `BASELINE` e
  `OBC-1U-LIMITED`;
- injeção manual de bit-flip em ciphertext ML-KEM com confirmação
  HMAC-SHA256 da chave derivada;
- modo `DEMO` A/B cronometrado, com pausa, retomada, parada, overlay calculado
  e exportação JSON;
- splash inicial opcional, autosave no encerramento, métricas superiores de
  CPU/RAM/flash/host e testes headless para 1920x1080 e 1366x768;
- roteiro de apresentação com cinco slides, sequência de demo e limites
  científicos;
- uma proposta acadêmica em DOCX;
- um roadmap consolidado e checklist final para validações físicas pendentes.

O dashboard não executa ML-KEM localmente; ele consulta a placa via
`PQC_STATUS`/`PQC_INFO` e exporta as respostas `PQC_*` como métricas. O
guardião CRC32 já existe para o experimento de payload, e a criptografia
pós-quântica real existe no firmware como comando de bancada, incluindo
`PQC_FAULT index mask [CONFIRM|NONE]` para corromper ciphertext e observar
`KEY_MISMATCH` ou `PROTOCOL_REJECT`. A interface identifica o estado retornado
pela placa e mantém `GUARD: NONE` ou `GUARD: CRC32` para o experimento de
payload.

A primeira integração real com a placa está em `firmware/`,
`tools/serial_console.py` e no modo serial do `dashboard.py`: ela valida
transporte serial, handshake, `PING`, `STATUS`, `TELEMETRY`, sensores,
atuadores, OLED, troca de perfil operacional, inventário da placa, ML-KEM-512
real e `fault=payload_crc32`.

## Objetivo experimental

A entrega final deve comparar, com a mesma campanha determinística de falhas:

1. dados sem proteção adicional;
2. dados protegidos por um mecanismo leve de integridade;
3. uma sessão ML-KEM-512 real em hardware, depois de build, vetor conhecido e
   medição de tempo/memória na Wisdom.

Os resultados devem ser classificados com critérios observáveis, e não por
percentuais inventados:

- `OK`: dado recebido sem alteração;
- `SILENT`: dado alterado e aceito sem detecção;
- `DETECTED_GUARD`: checksum/CRC detectou a alteração;
- `KEY_MISMATCH`: o harness comparou os segredos das duas pontas e encontrou
  diferença;
- `PROTOCOL_REJECT`: uma confirmação autenticada da sessão falhou.

O roadmap detalha a separação entre corrupção de payload, corrupção de
ciphertext ML-KEM e detecção no nível de protocolo.

O firmware também deverá comparar o ESP32 sem limitação adicional com o perfil
experimental `OBC-1U-LIMITED`: um core, 80 MHz, sem PSRAM, rádio desativado,
orçamento de 256 KiB, comandos UART curtos e telemetria a 1 Hz. Esse perfil
é uma política didática reproduzível, não uma especificação universal de
CubeSat.

## Execução

Ambiente do dashboard validado:

- Python 3.14.5;
- pygame-ce 2.5.7.

```bash
python3 -m pip install -r requirements.txt
python3 dashboard.py
```

Por padrão, o dashboard tenta detectar a BlackBoard Wisdom automaticamente. A
arte do CubeSat só é desenhada depois que a placa responde `HELLO` como
`PQC-SAT-WISDOM`; sem esse handshake, a órbita fica travada e o painel mostra
que está aguardando o satélite. O timeout padrão para resposta serial é de
5 segundos.

Para informar a porta manualmente:

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

Para desenvolvimento sem placa, use explicitamente:

```bash
python3 dashboard.py --simulated
```

Para testes automatizados ou captura direta sem a tela inicial curta:

```bash
python3 dashboard.py --simulated --no-splash
```

Use `Ctrl+Q` para encerrar.

## Integração ESP32 inicial

Grave o firmware de transporte:

```text
firmware/esp32_serial_spike/esp32_serial_spike.ino
```

Depois, no computador:

```bash
python3 -m pip install -r requirements.txt
python3 tools/serial_console.py --list-ports
python3 tools/serial_console.py --commands
python3 tools/serial_console.py --port /dev/ttyUSB0
python3 tools/serial_console.py --port /dev/ttyUSB0 --interactive
```

Troque `/dev/ttyUSB0` pela porta real da placa. Se houver uma unica porta
serial conectada, `--port` pode ser omitido.

Em Linux, se `/dev/ttyUSB0` aparecer mas abrir com `Permission denied`, use a
correção temporária:

```bash
sudo chmod 666 /dev/ttyUSB0
```

Para corrigir de forma permanente, adicione seu usuário ao grupo da porta,
normalmente `dialout`, e entre de novo na sessão:

```bash
sudo usermod -a -G dialout $USER
```

Exemplos de comandos no modo interativo:

```text
HELP
PING
STATUS
TELEMETRY
OLED STANDBY
SENSOR_READ ACCEL
FAULT CRC32 5051432D534154 0 0x01
LED TEST
RGB TEST
BARGRAPH 75
```

O protocolo serial desta etapa usa uma linha por frame:

```text
V1|request_id|COMMAND|arg1
V1|request_id|RESULT|OK|key=value
```

O firmware mantém comandos recebidos curtos; o parser do host aceita respostas
de até 1024 caracteres para acomodar `PQC_INFO`, `PQC_FAULT` e helps de
bancada.

## Comandos do dashboard

| Comando | Comportamento atual |
|---|---|
| `INJECT_FAULT` | Aplica bit-flip determinístico usando o guardião ativo (`NONE` ou `CRC32`). |
| `BIT_FLIP [index mask]` | Aplica bit-flip manual usando o guardião ativo, por exemplo `BIT_FLIP 0 0x01`. |
| `CHECKSUM ON\|OFF\|TOGGLE\|STATUS` | Liga/desliga o guardião CRC32 do fluxo manual. |
| `GUARD NONE\|CRC32` | Define explicitamente o guardião ativo. |
| `PQC_STATUS` | Consulta `PQC_INFO` quando a placa está online; sem placa, informa pendência local. |
| `CRC_CHECK` | Atalho que aplica uma tentativa forçada com CRC32; divergência vira `DETECTED_GUARD`. |
| `EXPORT_JSON` | Salva a sessão atual em `logs/` com eventos, resumo e métricas de hardware. |
| `SAVE_SESSION` | Alias de `EXPORT_JSON`. |
| `RUN_BATTERY n` | Executa bateria A/B com `n` tentativas por cenário, reaplica os mesmos fault specs e exporta JSON. |
| `DEMO [n]` | Executa campanha A/B visual cronometrada com overlay calculado. |
| `DEMO_PAUSE\|DEMO_RESUME` | Pausa ou retoma o modo apresentação. |
| `DEMO_STOP\|DEMO_RESTART` | Para sem apagar dados ou reinicia a demo com a mesma seed. |
| `RESET_SESSION` | Zera contadores e reinicia a seed da campanha. |
| `HELP` | Exibe a ajuda avançada do terminal textual do painel. |

Os resultados desses comandos saem de bytes antes/depois e do CRC32, não de
probabilidades. O backend PQC real está instalado no firmware como comando de
bancada. Os comandos técnicos `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`,
`PQC_DECAP`, `PQC_FAULT`, `PQC_BENCH`, inventário e debug não viram botões da
apresentação, mas podem ser digitados no terminal textual do painel quando a
placa está conectada.

## Comandos da demonstração ao vivo

O painel direito tem blocos clicáveis para os comandos centrais da
apresentação. O terminal textual continua disponível abaixo dos blocos para
comandos avançados, inclusive comandos fora do escopo visual da demo:

| Bloco/comando | Uso na demonstração |
|---|---|
| `PING` | Testa a comunicação com a placa. |
| `STATUS` | Mostra CPU, heap e rádio. |
| `TELEM` / `TELEMETRY` | Atualiza sensores rápidos. |
| `PQC` / `PQC_STATUS` | Mostra alvo, backend e estado PQC sem afirmar criptografia ativa. |
| `DEMO` | Executa a apresentação A/B automatizada. |
| `PAUSA` / `DEMO_PAUSE` | Pausa a apresentação A/B. |
| `CHK ON` / `CHECKSUM ON` | Liga o guardião CRC32 para as próximas falhas manuais. |
| `CHK OFF` / `CHECKSUM OFF` | Desliga o guardião e volta ao cenário sem proteção. |
| `FALHA` / `INJECT_FAULT` | Injeta falha determinística respeitando o guardião ativo. |
| `CRC32` / `CRC_CHECK` | Demonstra uma tentativa forçada com detecção real por CRC32. |
| `BATERIA` / `RUN_BATTERY 5` | Executa bateria A/B curta e exporta JSON. |
| `EXPORT` / `EXPORT_JSON` | Salva a sessão atual em JSON. |
| `OLED STANDBY` | Restaura o ícone no display. |
| `LED GREEN` | Liga o indicador principal em verde. |
| `RGB TEST` | Executa ciclo RGB. |
| `BARGRAPH 75` | Mostra progresso visual em 75%. |
| `BIT_FLIP [i m]` | Inverte um bit escolhido manualmente. |
| `SAVE_SESSION` | Alias de exportação. |
| `RESET_SESSION` | Zera a sessão da demonstração. |
| `HELP` | Mostra ajuda completa do terminal avançado no painel. |

Comandos de bancada, inventário, debug e expansão ficam centralizados em
[`hardware_command_reference.md`](hardware_command_reference.md). Eles podem
ser usados pelo `tools/serial_console.py` ou digitados no terminal textual do
dashboard; eles não aparecem como blocos clicáveis da demonstração visual.

Durante a animação, a faixa superior central mostra métricas básicas e
experimentais: CPU em MHz mais `% ativo` observado na janela móvel de 5s, RAM
livre, flash como disco, memória do processo host, FPS, perfil operacional,
rádio, tempo do último comando, tempos médios PQC e detecção/overhead de
checksum. Sem telemetria real, a faixa mostra valores pendentes em vez de
preencher números artificiais.
Respostas `PQC_*` também entram no JSON como métricas estruturadas, incluindo
tempos médios, KAT, `key_match`, `key_confirmed`, `tag_match`, tamanhos e CRCs
curtos, sem exportar segredos completos.

## Próximas etapas

Estado atual:

- Etapas 01 a 07: concluídas no código e consolidadas no `ROADMAP.md`; os
  markdowns dessas etapas foram removidos para não duplicar a fonte de verdade.
- Etapa 04: validada em hardware com firmware gravado, `PQC_KAT`,
  `PQC_FAULT`, `PQC_BENCH 100` em `BASELINE` e `OBC-1U-LIMITED`, payload
  `FAULT CRC32` e OLED standby.
- Etapa 06: funcional para payload com `CHECKSUM ON/OFF`, `GUARD NONE/CRC32`,
  CRC32 real, overhead do guardião no JSON, `RUN_BATTERY` A/B, `PQC_FAULT` em
  ciphertext ML-KEM com confirmação HMAC-SHA256 e exportação JSON de métricas
  PQC.
- Etapa 07: funcional com `DEMO [n]`, pausa, retomada, parada, reinício,
  snapshots A/B, overlay derivado dos eventos e exportação JSON.
- Etapa 08: implementada no software com `--no-splash`, splash opcional,
  autosave no fechamento, cleanup preservando traceback, cache de superfícies,
  métricas host, testes headless de resoluções e roteiro em
  `APRESENTACAO_ROTEIRO.md`.

Próximos cortes, nesta ordem:

1. Validar fisicamente projetor, porta serial e campanha prolongada de 30
   minutos na sala/equipamento da apresentação.

Validação real em placa após upload em 2026-06-18: `PQC_KAT` retornou
`kat=pass` com `ss_crc32=0xD9DA8D6C`; `PQC_FAULT 0 0x01 CONFIRM` retornou
`PROTOCOL_REJECT`; `PQC_FAULT 0 0x01 NONE` retornou `KEY_MISMATCH`;
`PQC_BENCH 100` em `BASELINE` retornou `ok=100`, `keygen_avg_us=3301`,
`encap_avg_us=3864`, `decap_avg_us=4988`; `PQC_BENCH 100` em
`OBC-1U-LIMITED` retornou `ok=100`, `keygen_avg_us=10045`,
`encap_avg_us=11769`, `decap_avg_us=15194`; `FAULT CRC32 ... 0 0x01`
retornou `DETECTED_GUARD`. Nenhum comando imprime chave privada, segredo
compartilhado completo ou material suficiente para reconstruir a sessão.

## Estrutura

| Arquivo | Papel |
|---|---|
| `dashboard.py` | Aplicação Pygame e baseline simulado. |
| `firmware/` | Spike de firmware ESP32 para transporte serial. |
| `tools/` | Parser, bridge e console serial no computador. |
| `tests/` | Testes automatizados do protocolo serial Python. |
| `hardware_blackboard_wisdom.md` | Inventário e procedimento de bancada da placa RoboCore Wisdom. |
| `hardware_command_reference.md` | Referência única de comandos completos de hardware/bancada. |
| `APRESENTACAO_ROTEIRO.md` | Roteiro de 20 minutos, slides, sequência da demo e limites. |
| `projeto_final_pqc_esp32_cubesat.docx` | Proposta acadêmica formal. |
| `ROADMAP.md` | Plano consolidado, critérios e ordem recomendada. |
| `etapa_08_*.md` | Checklist de validações físicas finais da etapa 8. |
| `agents.md` | Regras e contexto para agentes de IA. |
| `requirements.txt` | Dependência reproduzível do dashboard. |

## Limites científicos

- ML-KEM é um KEM: a decapsulação produz um segredo e não retorna um simples
  `DETECTED` para todo ciphertext corrompido.
- Comparar `sharedSecretA` e `sharedSecretB` é válido no harness de teste, mas
  não representa detecção autônoma pelo receptor.
- Em um modelo de exatamente um bit-flip dentro da região protegida, XOR,
  CRC-16 e CRC-32 detectam a alteração. Para comparar esses mecanismos, a
  campanha precisa incluir falhas múltiplas, bursts ou corrupção fora da
  cobertura.
- Uma emulação que não execute ML-KEM deve ser identificada como emulação, sem
  alegar resultados de PQC real.

## Referências centrais

- NIST, FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard.
- Segatz e Al Hafiz, *Efficient Implementation of CRYSTALS-KYBER Key
  Encapsulation Mechanism on ESP32*, arXiv:2503.10207.

Segatz e Al Hafiz avaliam Kyber512-90s em ESP-IDF e ESP32-S3. Azevedo,
Lagrota e Ribeiro demonstram ML-KEM-512 em ESP32 no SBSeg 2025. Os dois
trabalhos sustentam a viabilidade geral, mas nenhum deles deve ser tratado
como uma biblioteca pronta para a placa e o framework deste projeto. O
primeiro alvo operacional deste repositório é ML-KEM-512; ML-KEM-768 fica como
extensão após a viabilidade medida.
