# Firmware ESP32 - PQC-SAT Wisdom

Este diretorio contem o firmware do projeto para a RoboCore BlackBoard Wisdom.
Ele implementa o bridge serial `V1`, inventario da placa e comandos de bancada
para exercitar os perifericos integrados sem ainda executar criptografia,
injecao de falhas ou campanha de radiacao.

O objetivo desta etapa e dominar a comunicacao ESP32/notebook e preservar o
potencial da Wisdom para a demonstracao: sensores, atuadores, OLED, entradas
analogicas e expansoes ficam identificados no firmware desde o inicio.

## Sketch

Abra no Arduino IDE:

```text
firmware/esp32_serial_spike/esp32_serial_spike.ino
```

Configuracao inicial em Arduino IDE, caso nao use PlatformIO:

```text
Board: ESP32 Dev Module
Baud: 115200
Serial Monitor: Newline
```

Alternativamente, com PlatformIO:

```bash
python3 -m platformio run -e robocore_wisdom_esp32
```

A configuracao usa `board = esp32dev`, adequada para a Wisdom identificada como
ESP32 classico com conversor CP2102/CP2102N. Se a placa for trocada, revise
`platformio.ini`.

Para gravar, somente depois de confirmar que o backup da flash original existe:

```bash
python3 -m platformio run -e robocore_wisdom_esp32 -t upload
```

O firmware emite um evento de boot e aceita frames de uma linha:

```text
V1|request_id|COMMAND|arg1|arg2
```

As respostas usam:

```text
V1|request_id|RESULT|status|key=value
```

## Comandos

O dashboard da apresentacao usa apenas o subconjunto visual documentado no
`README.md`. A referencia completa de comandos de hardware, bancada, inventario
e expansao fica em:

```text
../hardware_command_reference.md
```

Use essa referencia para testes de firmware, debug de perifericos e manutencao
da comunicacao serial.

## Mapa da Wisdom usado

| Funcionalidade | Pinos / barramento |
|---|---|
| I2C comum | SCL D22, SDA D21 |
| OLED | I2C |
| APDS-9960 gesto/luz/proximidade | I2C |
| HTU21D temperatura/umidade | I2C |
| MMA8452QT acelerometro | I2C, INT1 D34, INT2 D35 |
| Bargraph | D17, D16, D4, D13 |
| LED RGB | R D19, G D23, B D18 |
| Botao | D27 |
| Receptor IR | D26 |
| Sensor de som | VP / A36 |
| Potenciometro deslizante | VN / A39 |
| Servo | D25 |
| Rele | D33 |
| BRIICK | I2C |

## Teste pelo computador

Depois de gravar o sketch:

```bash
python3 -m pip install -r requirements.txt
python3 tools/serial_console.py --list-ports
python3 tools/serial_console.py --commands
python3 tools/serial_console.py --port /dev/ttyUSB0
python3 tools/serial_console.py --port /dev/ttyUSB0 --interactive
```

Troque `/dev/ttyUSB0` pela porta exibida no seu sistema.

No modo interativo, digite `HELP` para ver a lista completa de comandos no
terminal. O comando tambem e enviado ao firmware, que retorna os grupos de
comandos aceitos pela placa.

Para usar a mesma placa pelo dashboard:

```bash
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
```

O dashboard tenta detectar a Wisdom automaticamente. A arte do satelite so e
liberada depois do handshake `HELLO`; sem a placa, a orbita fica travada.

Em Linux, se a porta existir mas abrir com `Permission denied`, confirme:

```bash
ls -l /dev/ttyUSB0
groups
```

Correção temporaria, ate desconectar a placa:

```bash
sudo chmod 666 /dev/ttyUSB0
```

Correção permanente comum:

```bash
sudo usermod -a -G dialout $USER
```

Depois da correção permanente, encerre a sessão do sistema e entre novamente
para o novo grupo valer no terminal.

Sequencia curta para validar a demonstracao apos upload:

```text
PING
STATUS
TELEMETRY
SENSOR_READ ACCEL
OLED STANDBY
LED TEST
RGB TEST
BARGRAPH 75
BARGRAPH 0
```

Para a sequencia completa de bancada, use `../hardware_command_reference.md`.

## Limites desta etapa

- O sketch usa Arduino/PlatformIO para destravar o transporte rapidamente.
- O backend criptografico aparece como `crypto=none`.
- A injecao de falhas aparece como `fault=none`.
- OLED tem suporte minimo de inicializacao, limpeza, padrao de teste e standby
  com o icone pixel-art do robo/satelite usado no dashboard; texto no display
  fica para uma biblioteca grafica ou driver proprio posterior.
- APDS-9960 e MMA8452 usam leituras diretas de registradores suficientes para
  bancada; calibracao fina fica para a etapa de sensores.
- A validacao completa depende de gravar em uma placa real; neste repositorio
  os testes automatizados cobrem o parser Python do protocolo.
