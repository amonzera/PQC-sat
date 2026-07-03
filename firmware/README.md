# Firmware ESP32 - PQC-SAT Wisdom

Este diretorio contem o firmware do projeto para a RoboCore BlackBoard Wisdom.
Ele implementa o bridge serial `V1`, inventário da placa e comandos de bancada
para exercitar os perifericos integrados. Ele também executa um experimento
pequeno de payload com bit-flip e CRC32, ML-KEM-512 real com `mlkem-native` e
o comando `MISSION` para comparar entrega de mensagem em `CLASSIC`, `PQC` e
`PQC_CRC32`. `CLASSIC` usa ECDH P-256 efêmero; todos os cenários usam
AES-128-GCM para proteger a mensagem.

O objetivo desta etapa e dominar a comunicação ESP32/notebook e preservar o
potencial da Wisdom para a demonstração: sensores, atuadores, OLED, entradas
analogicas e expansões ficam identificados no firmware desde o inicio.

## Sketch

Abra no Arduino IDE:

```text
firmware/esp32_serial_spike/esp32_serial_spike.ino
```

Configuração inicial em Arduino IDE, caso não use PlatformIO:

```text
Board: ESP32 Dev Module
Baud: 115200
Serial Monitor: Newline
```

Alternativamente, com PlatformIO:

```bash
python3 -m platformio run -e robocore_wisdom_esp32
```

A configuração usa `board = esp32dev`, adequada para a Wisdom identificada como
ESP32 clássico com conversor CP2102/CP2102N. Se a placa for trocada, revise
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

ECDH e ML-KEM usam `esp_random()` como fonte do adaptador `randombytes`. Isso é
adequado ao experimento, mas o projeto não certifica a entropia com o rádio
desligado nem implementa autenticação de identidade entre as pontas lógicas.

O build é Release: sketch e biblioteca vendorizada usam `-O2`. O Mbed TLS vem
pré-compilado pelo framework ESP32 em `-Os`, com aceleração de MPI, AES e SHA,
otimização NIST, P-256 e Curve25519 habilitados.

## Comandos

O dashboard da apresentação usa apenas o subconjunto visual documentado no
`README.md`. A referência completa de comandos de hardware, bancada, inventário
e expansão fica em:

```text
../docs/hardware_command_reference.md
```

Use essa referência para testes de firmware, debug de perifericos e manutenção
da comunicação serial.

## Mapa da Wisdom usado

| Funcionalidade | Pinos / barramento |
|---|---|
| I2C comum | SCL D22, SDA D21 |
| OLED | I2C |
| APDS-9960 gesto/luz/proximidade | I2C |
| HTU21D temperatura/umidade | I2C |
| MMA8452QT acelerômetro | I2C, INT1 D34, INT2 D35 |
| Bargraph | D17, D16, D4, D13 |
| LED RGB | R D19, G D23, B D18 |
| Botão | D27 |
| Receptor IR | D26 |
| Sensor de som | VP / A36 |
| Potenciômetro deslizante | VN / A39 |
| Servo | D25 |
| Relé | D33 |
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
terminal. O comando também e enviado ao firmware, que retorna os grupos de
comandos aceitos pela placa.

Para usar a mesma placa pelo dashboard:

```bash
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
```

O dashboard tenta detectar a Wisdom automaticamente. A arte do satélite só e
liberada depois do handshake `HELLO`; sem a placa, a órbita fica travada.

Em Linux, se a porta existir mas abrir com `Permission denied`, confirme:

```bash
ls -l /dev/ttyUSB0
groups
```

Correção temporária, até desconectar a placa:

```bash
sudo chmod 666 /dev/ttyUSB0
```

Correção permanente comum:

```bash
sudo usermod -a -G dialout $USER
```

Depois da correção permanente, encerre a sessão do sistema e entre novamente
para o novo grupo valer no terminal.

Sequência curta para validar a demonstração apos upload:

```text
PING
STATUS
TELEMETRY
FAULT NONE 5051432D5341547C54454D503D32342E357C5354415455533D4F4B 0 0x01
FAULT CRC32 5051432D5341547C54454D503D32342E357C5354415455533D4F4B 0 0x01
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
SENSOR_READ ACCEL
OLED STANDBY
LED TEST
RGB TEST
BARGRAPH 75
BARGRAPH 0
```

Para a sequência completa de bancada, use
`../docs/hardware_command_reference.md`.

## Limites desta etapa

- O sketch usa Arduino/PlatformIO para destravar o transporte rapidamente.
- O backend criptográfico aparece como `crypto=ML-KEM-512` e usa
  `mlkem-native` v1.1.0 vendorizado em `firmware/lib/mlkem_native`.
- A interface PQC real existe: `PQC_INFO` reporta alvo, backend, variante,
  commit, licença, tamanhos e métricas; `PQC_KAT`, `PQC_KEYGEN`,
  `PQC_ENCAP`, `PQC_DECAP`, `PQC_FAULT` e `PQC_BENCH` executam no firmware.
- O comando `MISSION CLASSIC|PQC|PQC_CRC32 [payload_hex]` entrega uma mensagem
  curta e retorna tempos, bytes, heap, resultado, confirmação, checksum e
  subtempos de ML-KEM quando aplicável.
- `SESSION_BENCH ECDH_P256|X25519|MLKEM512 1|100|500|1000` mede uma sessão
  estabelecida uma vez e reutilizada por N mensagens AES-GCM, sempre a
  240 MHz. É comando técnico, sem botão no dashboard.
- A injecao de falhas existe em dois caminhos: payload serial com
  `FAULT NONE|CRC32 ...` e ciphertext ML-KEM com
  `PQC_FAULT index mask [CONFIRM|NONE]`.
- OLED tem suporte minimo de inicializacao, limpeza, padrao de teste e standby
  com o ícone pixel-art do robo/satélite usado no dashboard; texto no display
  fica para uma biblioteca gráfica ou driver próprio posterior.
- APDS-9960 e MMA8452 usam leituras diretas de registradores suficientes para
  bancada; calibracao fina fica para a etapa de sensores.
- O nucleo `FAULT` foi validado em placa real para `NONE` e `CRC32`;
  `PQC_FAULT` foi validado em placa real para `CONFIRM` e `NONE`; os testes
  automatizados cobrem o parser Python e o engine deterministico do dashboard.

## Manutenção

O MVP do firmware está concluído. Novas mudanças devem preservar
`MISSION CLASSIC`, `MISSION PQC`, `MISSION PQC_CRC32`, `PQC_KAT`,
`PQC_FAULT`, `PQC_BENCH 100`, `FAULT CRC32` e `BUTTON_PING` como testes de
regressão, sem expor chave privada, segredo compartilhado completo ou material
suficiente para reconstruir a sessão.

Sequência minima de bancada:

```text
PQC_INFO
PQC_KAT
PQC_KEYGEN
PQC_ENCAP
PQC_DECAP
PQC_FAULT 0 0x01 CONFIRM
PQC_BENCH n
SESSION_BENCH ECDH_P256 1
SESSION_BENCH ECDH_P256 100
SESSION_BENCH X25519 500
SESSION_BENCH MLKEM512 1000
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Validação real em placa após upload:

```text
PQC_INFO                      pqc_backend=mlkem-native pqc_status=ready pk=800 sk=1632 ct=768 ss=32
PQC_KAT                       kat=pass ss_crc32=0xD9DA8D6C elapsed_us=14117
PQC_FAULT 0 0x01 CONFIRM      result=PROTOCOL_REJECT confirmation=HMAC-SHA256 key_match=0 confirm_us=960
PQC_FAULT 0 0x01 NONE         result=KEY_MISMATCH confirmation=NONE key_match=0
PQC_BENCH 100 BASELINE        ok=100 keygen_avg_us=3301 encap_avg_us=3864 decap_avg_us=4988
PQC_BENCH 100 OBC-1U-LIMITED  ok=100 keygen_avg_us=10045 encap_avg_us=11769 decap_avg_us=15194
FAULT CRC32 ... 0 0x01        result=DETECTED_GUARD crc_before=0xDFFEC3A1 crc_after=0x7989C815
```

Validação funcional do novo fluxo de apresentação:

```text
MISSION CLASSIC      result=DELIVERED crypto=ECDH-P256 cipher=AES-128-GCM bytes_ecdh=65 aead_match=1 elapsed_us=<medido>
MISSION PQC          result=DELIVERED crypto=ML-KEM-512 cipher=AES-128-GCM checksum=NONE key_match=1 aead_match=1 elapsed_us=<medido>
MISSION PQC_CRC32    result=DELIVERED crypto=ML-KEM-512 cipher=AES-128-GCM checksum=CRC32 key_match=1 aead_match=1 crc_match=1 elapsed_us=<medido>
```

Medição comparativa registrada em 2026-06-17:

```text
BASELINE 240 MHz
PQC_BENCH 5   keygen_avg_us=3369 encap_avg_us=3878 decap_avg_us=5013 elapsed_us=62068 heap=202444 min_heap=198456

OBC-1U-LIMITED 80 MHz
PQC_INFO       pqc_status=ready pk=800 sk=1632 ct=768 ss=32 elapsed_us=24697 heap=202444 min_heap=198456 flash=4194304
PQC_KAT        kat=pass key_match=1 ss_crc32=0xD9DA8D6C elapsed_us=39270
PQC_BENCH 5   keygen_avg_us=10101 encap_avg_us=11778 decap_avg_us=15214 elapsed_us=187371 heap=202444 min_heap=198456
```

Nenhum comando imprime chaves privadas, segredos completos ou material
criptográfico suficiente para reconstruir a sessão; são usados tamanhos,
status, tempos, CRCs curtos e tags resumidos de confirmação.
