# Etapa 05 - Bridge serial

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Conectar dashboard e firmware sem bloquear o loop e sem atribuir respostas ao
comando errado.

## Pré-requisitos

- protocolo da Etapa 04 congelado e testado;
- exemplos de request/response;
- pyserial opcional.

## Correções obrigatórias ao plano antigo

- `ListPortInfo` expõe `manufacturer`; não dependa de
  `manufacturer_str`.
- Se a conexão inicial falhar, preserve o objeto bridge para permitir
  reconexão.
- Não faça busy loop consultando apenas `in_waiting`.
- Não descarte `request_id`.
- Não mostre `CONNECTED` antes do handshake.

## Estados

```text
SIMULATED
CONNECTING
CONNECTED
LOST
CLOSING
```

## Protocolo sugerido

```text
V1|request_id|command|arg1|arg2
V1|request_id|RESULT|status|key=value
```

Requisitos:

- uma linha por frame;
- comandos recebidos pelo firmware continuam limitados a 256 caracteres;
- respostas lidas pelo host aceitam até 512 caracteres para `PQC_INFO` e
  helps de bancada;
- parser estrito;
- timeout por request;
- resposta de erro para comando desconhecido;
- versão incompatível rejeitada.

## Implementação

### Implementacao inicial

Foi criado um bridge sincrono para destravar o teste de bancada antes da
integracao com o loop Pygame:

```text
tools/serial_protocol.py
tools/serial_bridge.py
tools/serial_console.py
tools/serial_commands.py
dashboard.py
```

Uso:

```bash
python3 tools/serial_console.py --list-ports
python3 tools/serial_console.py --commands
python3 tools/serial_console.py --port /dev/ttyUSB0
python3 tools/serial_console.py --port /dev/ttyUSB0 --interactive
```

Esse bridge ja preserva `request_id`, valida frames `V1`, usa timeout por
request e nao depende de `manufacturer_str`.

### Integracao atual com o dashboard

O dashboard aceita:

```bash
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
python3 dashboard.py --simulated
```

Quando o modo serial esta ativo:

- argumentos sao processados antes de inicializar o display fullscreen;
- `DashboardSerialClient` roda em uma thread daemon;
- o loop Pygame apenas enfileira comandos e drena respostas;
- a thread tenta detectar/reconectar a Wisdom automaticamente;
- `SAT CONECTADO` so aparece depois do handshake `HELLO`;
- a arte do CubeSat fica oculta/travada enquanto a placa nao responde;
- somente comandos de demonstracao do firmware sao encaminhados para a ESP32
  pelo dashboard;
- comandos completos de bancada ficam em `hardware_command_reference.md`;
- comandos locais de experimento continuam no dashboard e usam o engine
  deterministico;
- `HELP` abre a lista de comandos da demonstracao no painel;
- `close()` sinaliza a thread e fecha a serial ao sair.

Pendencias conhecidas:

- ainda nao ha fake serial dedicado para testes automatizados do dashboard.

## Segurança e robustez

- limite o comprimento das linhas;
- valide números antes de converter;
- ignore campos extras apenas se a versão permitir;
- nunca execute texto serial como código;
- não exponha segredos completos no console/JSON.

## Testes

- serial simulada com `loop://` ou fake in-memory;
- resposta atrasada;
- resposta duplicada;
- resposta de request antigo;
- cabo desconectado;
- bytes inválidos em UTF-8;
- fechamento durante leitura;
- execução sem pyserial.

## Aceite

- [x] Pygame mantém FPS durante I/O serial em thread separada.
- [x] Cada resposta encontra o request correto no `SerialBridge`.
- [x] Falha inicial permite reconexão automática.
- [x] Modo simulado funciona sem abrir pyserial.
- [x] Cleanup sinaliza e encerra a thread serial.
