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
- uma proposta acadêmica em DOCX;
- um roadmap e especificações para as próximas etapas.

O dashboard atual **não executa ML-KEM**. O guardião CRC32 já existe para o
experimento de payload; a criptografia pós-quântica real é o próximo marco
técnico. A interface identifica esse estado como `PQC: ALVO ML-KEM-512` e
`GUARD: NONE` ou `GUARD: CRC32`.

A primeira integração real com a placa está em `firmware/`,
`tools/serial_console.py` e no modo serial do `dashboard.py`: ela valida
transporte serial, handshake, `PING`, `STATUS`, `TELEMETRY`, sensores,
atuadores, OLED, troca de perfil operacional e inventário da placa, ainda com
`crypto=none` e `fault=payload_crc32`.

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
orçamento de 256 KiB, frames UART de 256 bytes e telemetria a 1 Hz. Esse perfil
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

## Comandos do dashboard

| Comando | Comportamento atual |
|---|---|
| `INJECT_FAULT` | Aplica bit-flip determinístico no payload sem guardião; payload alterado aceito vira `SILENT`. |
| `BIT_FLIP [index mask]` | Aplica bit-flip manual, por exemplo `BIT_FLIP 0 0x01`. |
| `PQC_STATUS` | Informa que o alvo criptográfico é ML-KEM-512 na placa e que ainda está pendente. |
| `CRC_CHECK` | Aplica bit-flip e compara CRC32 real; divergência vira `DETECTED_GUARD`. |
| `RESET_SESSION` | Zera contadores e reinicia a seed da campanha. |
| `HELP` | Exibe uma lista única com os comandos mais relevantes da demonstração. |

Os resultados desses comandos saem de bytes antes/depois e do CRC32, não de
probabilidades. O backend PQC real ainda não está instalado no firmware.

## Comandos da demonstração ao vivo

O `HELP` do dashboard não é dividido por menus. Ele mostra uma lista única,
curta e voltada para a apresentação:

| Comando | Uso na demonstração |
|---|---|
| `HELP` | Mostra a lista única de comandos. |
| `PING` | Testa a comunicação com a placa. |
| `STATUS` | Mostra CPU, heap e rádio. |
| `TELEMETRY` | Atualiza sensores rápidos. |
| `SENSOR_READ ACCEL` | Demonstra movimento da placa. |
| `SENSOR_READ TEMP_HUM` | Lê temperatura e umidade. |
| `SENSOR_READ APDS` | Lê luz e proximidade. |
| `OLED STANDBY` | Restaura o ícone no display. |
| `LED TEST` | Testa o indicador principal. |
| `LED GREEN` | Liga o indicador em verde. |
| `LED OFF` | Apaga o indicador. |
| `RGB TEST` | Executa ciclo RGB. |
| `RGB 0 255 0` | Mostra uma cor RGB livre. |
| `RGB OFF` | Apaga o RGB. |
| `BARGRAPH TEST` | Anima LEDs de porcentagem. |
| `BARGRAPH 75` | Mostra progresso visual em 75%. |
| `INJECT_FAULT` | Injeta falha determinística sem guardião. |
| `BIT_FLIP [i m]` | Inverte um bit escolhido manualmente. |
| `CRC_CHECK` | Demonstra detecção real por CRC32. |
| `PQC_STATUS` | Mostra o alvo PQC e o estado da instalação na placa. |
| `RESET_SESSION` | Zera a sessão da demonstração. |

Comandos de bancada, inventário, debug e expansão ficam centralizados em
[`hardware_command_reference.md`](hardware_command_reference.md). Eles podem
ser usados pelo `tools/serial_console.py`, mas não aparecem como comandos da
demonstração visual.

## Próximas etapas

Estado atual:

- Etapa 01: concluída, com `ExperimentEngine`, eventos e efeitos reais.
- Etapa 02: parcial, com timeline simples derivada dos eventos.
- Etapa 04/05: funcionais para Wisdom, bridge serial e `FAULT` com CRC32.
- Etapa 06: parcial, com CRC32 real por tentativa; falta campanha A/B formal.

Próximos cortes, nesta ordem:

1. Etapa 04: portar/instalar ML-KEM-512 na placa, com KAT e benchmark de
   tempo, heap e flash nos perfis `BASELINE` e `OBC-1U-LIMITED`.
2. Etapa 06: expandir a radiação simulada manual para bit-flips em payload e,
   quando o KEM estiver pronto, ciphertext, mantendo checksum ativável ou
   desativável.
3. Etapa 03: implementar `EXPORT_JSON`, `SAVE_SESSION` e `RUN_BATTERY` para
   salvar eventos e métricas de hardware em JSON versionado.
4. Etapa 06: criar campanha A/B que reaplica os mesmos fault specs em `NONE`
   e `CRC32`.
5. Etapa 07: automatizar `DEMO`, pausa/parada e overlay calculado.
6. Etapa 08: validar projetor, roteiro e robustez final.

ML-KEM-512 deve entrar agora como experimento de bancada controlado. Ele só
vira comando de demonstração depois que o firmware passar vetor conhecido,
reportar métricas e não expor segredos completos no console ou no JSON.

## Estrutura

| Arquivo | Papel |
|---|---|
| `dashboard.py` | Aplicação Pygame e baseline simulado. |
| `firmware/` | Spike de firmware ESP32 para transporte serial. |
| `tools/` | Parser, bridge e console serial no computador. |
| `tests/` | Testes automatizados do protocolo serial Python. |
| `hardware_blackboard_wisdom.md` | Inventário e procedimento de bancada da placa RoboCore Wisdom. |
| `hardware_command_reference.md` | Referência única de comandos completos de hardware/bancada. |
| `projeto_final_pqc_esp32_cubesat.docx` | Proposta acadêmica formal. |
| `ROADMAP.md` | Plano consolidado, critérios e ordem recomendada. |
| `etapa_01_*.md` a `etapa_08_*.md` | Especificações de implementação por etapa. |
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
