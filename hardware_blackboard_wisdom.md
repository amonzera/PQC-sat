# BlackBoard Wisdom - conexao e programacao

Este arquivo registra o estado real testado em bancada para a RoboCore
BlackBoard Wisdom usada no projeto PQC-SAT.

## Fontes consultadas

- Produto oficial: <https://www.robocore.net/placa-robocore/blackboard-wisdom>
- Manual online: <https://www.robocore.net/tutoriais/blackboard-wisdom-introducao>
- Driver USB-Serial: <https://www.robocore.net/tutoriais/instalacao-driver-da-blackboard#blackboard-uno-v2>
- RoboCore IDE: <https://ide.robocore.net/ui/>

## Hardware identificado

Resultado local em `/dev/ttyUSB0`:

```text
USB: Silicon Labs CP2102N USB to UART Bridge Controller
Chip: ESP32-D0WD revision v1.1
CPU: Xtensa dual-core 32-bit LX6, ate 240 MHz
Crystal: 40 MHz
Flash: 4 MB
MAC: a8:42:e3:73:8f:a0
```

Estado validado em 2026-06-17 com o firmware do projeto:

```text
HELLO: node=PQC-SAT-WISDOM, fault=payload_crc32
STATUS BASELINE: cpu_mhz=240, heap=233556, flash=4194304
PROFILE OBC-1U-LIMITED: cpu_mhz=80
PROFILE BASELINE: cpu_mhz=240
FAULT NONE ... 0 0x01: result=SILENT
FAULT CRC32 ... 0 0x01: result=DETECTED_GUARD
```

A pagina oficial da RoboCore descreve a Wisdom como uma placa com processador
Xtensa dual-core 32-bit LX6 (ESP32) com 520 KB SRAM, alimentacao/programacao
via micro USB e interface USB-Serial SiliconLabs CP2102. Tambem lista sensores
integrados, OLED, LEDs, botao, potenciometro e conectores de expansao.

## Funcionalidades e pinagem oficial aproveitadas

A imagem oficial de disposicao de pinos da Wisdom foi usada para mapear o
firmware do projeto:

| Funcionalidade | Componente / pinos |
|---|---|
| Processador | ESP32 com Wi-Fi e Bluetooth |
| USB-Serial | SiliconLabs CP2102/CP2102N |
| I2C comum | SCL D22, SDA D21 |
| Display OLED | I2C |
| Sensor de gestos, luminosidade e proximidade | APDS-9960 em I2C |
| Sensor de temperatura e umidade | HTU21D em I2C |
| Acelerometro de 3 eixos | MMA8452QT em I2C, INT1 D34, INT2 D35 |
| Bargraph | D17, D16, D4, D13 |
| LED RGB | R D19, G D23, B D18 |
| Botao | D27 |
| Receptor IR | D26 |
| Sensor de som | VP / A36 |
| Potenciometro deslizante | VN / A39 |
| Servo | D25 |
| Rele | D33 |
| Conector BRIICK | I2C |

O firmware atual nao usa Wi-Fi/Bluetooth porque o experimento de comunicacao e
UART e o perfil OBC didatico pede radio desligado. Isso preserva a funcao para
etapas futuras sem misturar variaveis de comunicacao agora.

## Testes nao destrutivos executados

### Enumeracao USB

```bash
python3 tools/serial_console.py --list-ports
```

Resultado relevante:

```text
/dev/ttyUSB0    CP2102N USB to UART Bridge Controller - Silicon Labs
```

### Bootloader ESP32

```bash
python3 -m esptool --port /dev/ttyUSB0 chip-id
python3 -m esptool --port /dev/ttyUSB0 flash-id
```

Ambos funcionaram. Isso prova que o computador consegue falar com o bootloader
ROM do ESP32 e que a placa nao esta inacessivel.

### Serial do firmware original

Foram testados bauds comuns:

```text
115200
9600
57600
74880
921600
```

Tambem foram enviados probes simples como newline, `Ctrl+C`, `help` e `PING`.
Resultado: nenhum byte retornado. Portanto, o firmware atual da placa nao
expoe um protocolo serial textual utilizavel pelo bridge `V1`.

### Bridge do projeto

```bash
python3 tools/serial_console.py --port /dev/ttyUSB0 --timeout 2 \
  --command HELLO --command PING --command STATUS
```

Resultado:

```text
error: timeout waiting for request_id=1
```

Conclusao: para usar o bridge do projeto, a placa precisa executar firmware
que implemente o protocolo `V1|request_id|COMMAND|...`.

## Backup do firmware original

Backup completo criado antes de qualquer gravacao:

```bash
python3 -m esptool --port /dev/ttyUSB0 read-flash \
  0x0 0x400000 backups/wisdom_flash_original.bin
```

Resultado:

```text
Read 4194304 bytes from 0x00000000
```

Arquivo:

```text
backups/wisdom_flash_original.bin
tamanho: 4.0M
sha256: 3c7ab82a1977d82074703c0c7b938fb03f1f8a9e96959b51f33c74e91e8ab23e
```

Restauracao, se necessario:

```bash
python3 -m esptool --port /dev/ttyUSB0 write-flash \
  0x0 backups/wisdom_flash_original.bin
```

Nao execute restauracao sem necessidade; ela tambem grava a flash inteira.

## Caminhos possiveis

### 1. RoboCore IDE / MicroPython

A pagina oficial indica que a placa acompanha chave de acesso para tutoriais
exclusivos e que a Wisdom foi pensada para programacao em blocos e MicroPython.
As paginas especificas de "Software e Drivers" e "Introducao ao MicroPython"
exigiram login durante a consulta.

Esse caminho pode ser util para explorar os sensores integrados, mas nao foi
possivel conectar nosso bridge ao firmware atual por REPL ou comando serial.

### 2. Arduino IDE

A propria pagina de comentarios da RoboCore indica que o foco inicial da Wisdom
e RoboCore IDE, blocos e MicroPython, nao um tutorial tecnico completo de
Arduino IDE. Ainda assim, o hardware identificado e um ESP32 classico com
CP2102, entao Arduino/ESP32 e tecnicamente viavel.

### 3. PlatformIO

Configuracao local adicionada:

```text
platformio.ini
env: robocore_wisdom_esp32
board: esp32dev
framework: arduino
upload_port: /dev/ttyUSB0
```

Compilacao testada sem gravar:

```bash
python3 -m platformio run -e robocore_wisdom_esp32
```

Resultado:

```text
SUCCESS
RAM:   14.7% (48164 bytes de 327680)
Flash: 68.1% (893061 bytes de 1310720)
```

Para gravar o firmware do bridge, com autorizacao explicita:

```bash
python3 -m platformio run -e robocore_wisdom_esp32 -t upload
```

Depois da gravacao:

```bash
python3 tools/serial_console.py --port /dev/ttyUSB0 --timeout 3
python3 tools/serial_console.py --port /dev/ttyUSB0 --interactive
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
```

Sequencia curta de verificacao para a demonstracao:

```text
PING
STATUS
TELEMETRY
FAULT NONE 5051432D5341547C54454D503D32342E357C5354415455533D4F4B 0 0x01
FAULT CRC32 5051432D5341547C54454D503D32342E357C5354415455533D4F4B 0 0x01
OLED STANDBY
SENSOR_READ ACCEL
RGB TEST
RGB 0 255 0
RGB OFF
BARGRAPH TEST
BARGRAPH 75
BARGRAPH 0
LED TEST
LED WHITE
LED OFF
```

Os comandos completos de bancada, inventario, debug e expansao ficam em
`hardware_command_reference.md`.

O console interativo do terminal e o console visual do dashboard aceitam
`HELP` para listar os comandos de demonstracao. No dashboard, comandos do firmware
como `PING`, `STATUS`, `TELEMETRY`, `OLED STANDBY`, `RGB 0 255 0`,
`BARGRAPH 75` e `SENSOR_READ ACCEL` sao encaminhados para a ESP32. O dashboard
tenta detectar a placa automaticamente; se o firmware `PQC-SAT-WISDOM` nao
responder ao handshake `HELLO`, a arte do satelite fica travada e nao e
desenhada na orbita.

## Decisao recomendada

Para o projeto PQC-SAT, o caminho mais direto e cientificamente controlado e:

1. preservar o backup atual;
2. gravar o firmware serial do projeto;
3. validar bridge, inventario, I2C, entradas, sensores e atuadores;
4. manter `FAULT NONE|CRC32` como base de radiacao simulada de payload;
5. integrar ML-KEM-512/Kyber512 validado e medido antes de expor comandos PQC
   no dashboard.

O risco de brick permanente e baixo porque o bootloader ROM do ESP32 respondeu
de forma confiavel. O risco real e sobrescrever o ambiente original da
RoboCore; o backup completo mitiga esse risco.
