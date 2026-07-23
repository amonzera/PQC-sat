# Firmware ESP32 - PQC-SAT Wisdom

Este diretorio contem o firmware do projeto para a RoboCore BlackBoard Wisdom.
Ele implementa o bridge serial `V1`, inventário da placa e comandos de bancada
para exercitar os perifericos integrados. Ele também executa um experimento
pequeno de payload com bit-flip e CRC32. O legado ML-KEM-512 com
`mlkem-native` permanece disponível, mas o experimento comparativo novo usa o
mesmo wolfCrypt para ECDH P-256, ML-KEM-512, HKDF-SHA256, RNG e AES-128-GCM.
O jogo público usa o protocolo transacional `GAME_*` com capacidades
`STAGED_V1` e `FAIR_V1`; o comando monolítico
`INVESTIGATE` permanece para compatibilidade e bancada.

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

```text
python3 tools/firmware_deploy.py
```

A configuração usa `board = esp32dev`, adequada para a Wisdom identificada como
ESP32 clássico com conversor CP2102/CP2102N. Se a placa for trocada, revise
`platformio.ini`.

Para gravar, somente depois de confirmar que o backup da flash original existe
e autorizar explicitamente `--upload`:

```text
python3 tools/firmware_deploy.py --upload
```

Esse utilitário usa argumentos de processo Python, sem shell/Bash, reaproveita
a descoberta robusta do dashboard e valida
`game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` depois do reset.
Somente então salva um manifesto em `logs/firmware/` com hashes do binário e
das fontes, porta e handshakes.

O firmware emite um evento de boot e aceita frames de uma linha:

```text
V1|request_id|COMMAND|arg1|arg2
```

As respostas usam:

```text
V1|request_id|RESULT|status|key=value
```

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

No modo interativo, digite `HELP` para ver localmente a lista completa de
comandos. Use os comandos individuais para consultar a placa.

Para usar a mesma placa pelo dashboard:

```bash
python3 dashboard.py
python3 dashboard.py --port /dev/ttyUSB0
```

O programa sonda as portas por `HELLO` e só abre a interface após validar a
Wisdom. Sem placa, ou com firmware sem
`game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`, ele
permanece no standby de busca e mostra o motivo da rejeição; não entra na
narrativa. O handshake inclui `uptime_ms`, permitindo rejeitar um
`BUTTON_PING` enfileirado antes de a interface estar pronta. Um `HELLO` novo
também limpa qualquer sessão `GAME_*` anterior.

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
MISSION CLASSIC_CRC32
MISSION PQC
MISSION PQC_CRC32
KEX_INFO
KEX_BENCH 10
MISSION ECDH
MISSION MLKEM
SESSION_BENCH ECDH 1 54454D503D383443
SESSION_BENCH MLKEM 1 54454D503D383443
GAME_BEGIN TEST-STAGED BASELINE MLKEM CRC32 RX_MEMORY 54454D503D383443
GAME_PROTECT TEST-STAGED
GAME_TRANSMIT TEST-STAGED 0 0x01
GAME_VERIFY TEST-STAGED
GAME_RETRY TEST-STAGED
GAME_END TEST-STAGED ACCEPT
INVESTIGATE PQC NORMAL 54454D503D3834437C5354415455533D435249544943414C7C534146453D52455155455354 0 0x01 TEST-NORMAL
INVESTIGATE PQC CHANNEL_BITFLIP 54454D503D3834437C5354415455533D435249544943414C7C534146453D52455155455354 0 0x01 TEST-CHANNEL
INVESTIGATE PQC TAMPER 54454D503D3834437C5354415455533D435249544943414C7C534146453D52455155455354 0 0x01 TEST-TAMPER
INVESTIGATE PQC_CRC32 RX_MEMORY 54454D503D3834437C5354415455533D435249544943414C7C534146453D52455155455354 0 0x01 TEST-MEMORY
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
- O perfil `robocore_wisdom_esp32_fair` exige wolfSSL 5.9.2 em
  `firmware/lib/wolfssl`; a árvore local é ignorada pelo Git. Veja
  `WOLFSSL_LOCAL.md` para versão, commit e licença.
- `KEX_INFO` registra versão, backend, compilador, framework, perfil de build,
  HKDF, política de otimização, ausência de assembly/aceleração e tamanhos
  públicos. `KEX_BENCH n` executa pares ECDH/ML-KEM em ordem alternada.
- `SESSION_BENCH ECDH|MLKEM 1|100|500|1000 payload_hex` estabelece uma sessão
  e mede tempo, bytes, heap livre antes/depois, mínimo global, maior bloco e
  folga de stack ao processar várias mensagens AES-GCM.
- A interface PQC real existe: `PQC_INFO` reporta alvo, backend, variante,
  commit, licença, tamanhos e métricas; `PQC_KAT`, `PQC_KEYGEN`,
  `PQC_ENCAP`, `PQC_DECAP`, `PQC_FAULT` e `PQC_BENCH` executam no firmware.
- O comando `MISSION CLASSIC|CLASSIC_CRC32|PQC|PQC_CRC32 [payload_hex]` entrega uma mensagem
  curta e retorna tempos, bytes, heap, resultado, confirmação, checksum e
  subtempos de ML-KEM quando aplicável.
- `MISSION ECDH|ECDH_CRC32|MLKEM|MLKEM_CRC32 [payload_hex]` usa o contrato
  `KEX_FAIR_V1` e separa `setup_us`, `initiator_us`, `responder_us`,
  `setup_bytes`, `response_bytes`, `data_bytes`, `wire_total_fresh` e
  `wire_total_preprovisioned`.
- `GAME_BEGIN`, `GAME_PROTECT`, `GAME_TRANSMIT`, `GAME_VERIFY`, `GAME_RETRY`,
  `GAME_END` e `GAME_ABORT` dividem a partida em etapas reais, mantêm uma única
  sessão, rejeitam ordem/ID incorreto e restauram o baseline ao encerrar.
- Enquanto a sessão está ativa, somente sua continuação `GAME_*`, um novo
  `GAME_BEGIN`, o reset transacional `HELLO` e a consulta somente-leitura
  `ANALOG POT` são aceitos. A exceção captura A39 entre `GAME_PROTECT` e
  `GAME_TRANSMIT` sem limpar a sessão; outros comandos de bancada concorrentes
  retornam `BAD_GAME_STATE` e limpam o contexto para não reutilizar perfil nem
  buffers ML-KEM globais.
- `GAME_VERIFY` apaga chaves e segredos; `GAME_RETRY` usa o mesmo payload e
  cria chave/nonce novos sem injetar falha. Respostas expõem somente métricas e
  fingerprints curtas.
- `INVESTIGATE scenario incident payload_hex index mask incident_id` executa
  mutação single-bit em canal ou memória e retorna as três verificações do
  diagnóstico em uma resposta legada. O frame de entrada suporta o payload
  hexadecimal máximo de 96 B.
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

O MVP original do firmware está concluído. A extensão `STAGED_V1/FAIR_V1`
atual com `SESSION_BENCH` compila em build limpo com 59.020 B de RAM,
1.005.497 B de flash e binário de 1.012.080 B, SHA-256
`9eba850f2ea493edbdb89d7103f85589456277426f50136a2e337f8dac32a18d`.
Esta revisão corrige o campo `experiment` duplicado em `GAME_PROTECT` depois de
ECDH/ML-KEM passarem no segundo smoke FAIR. O binário foi gravado pelo
manifesto `20260723T155737Z` e o diagnóstico `20260723T160223Z` passou os 27
registros curtos; baterias e aceite físico longo continuam pendentes. Novas
mudanças devem
preservar `MISSION`, `INVESTIGATE`, todos os `GAME_*`, `PQC_KAT`, `PQC_FAULT`,
`PQC_BENCH 100`, `FAULT CRC32` e `BUTTON_PING` como regressão, sem expor chave
privada, segredo compartilhado completo ou material suficiente para reconstruir
a sessão.

Sequência minima de bancada:

```text
PQC_INFO
PQC_KAT
PQC_KEYGEN
PQC_ENCAP
PQC_DECAP
PQC_FAULT 0 0x01 CONFIRM
PQC_BENCH n
MISSION CLASSIC
MISSION CLASSIC_CRC32
MISSION PQC
MISSION PQC_CRC32
GAME_BEGIN TEST-STAGED BASELINE PQC CRC32 RX_MEMORY 54454D503D383443
GAME_PROTECT TEST-STAGED
GAME_TRANSMIT TEST-STAGED 0 0x01
GAME_VERIFY TEST-STAGED
GAME_RETRY TEST-STAGED
GAME_END TEST-STAGED ACCEPT
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

Validação funcional histórica de `MISSION`:

```text
MISSION CLASSIC      result=DELIVERED crypto=AES-128-GCM cipher=AES-128-GCM checksum=NONE aead_match=1 elapsed_us=<medido>
MISSION PQC          result=DELIVERED crypto=ML-KEM-512 cipher=AES-128-GCM checksum=NONE key_match=1 aead_match=1 elapsed_us=<medido>
MISSION PQC_CRC32    result=DELIVERED crypto=ML-KEM-512 cipher=AES-128-GCM checksum=CRC32 key_match=1 aead_match=1 crc_match=1 elapsed_us=<medido>
```

O smoke físico `STAGED_V1` ainda precisa produzir respostas reais para a
sequência `GAME_BEGIN` … `GAME_END`; não reutilize as linhas acima como prova
desse protocolo.

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
