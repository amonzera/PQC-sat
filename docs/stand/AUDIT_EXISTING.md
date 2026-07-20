# Auditoria da base anterior ao modo estande SBPC

Data da auditoria: 2026-07-20  
Branch de trabalho: `sbpc-stand-demo`  
Base preservada: commit `abd65a3d28cfa65fda4cd8465f76d582b376c116`

## Escopo e preservação

A versão do seminário permanece acessível pelas branches `main` e `game`,
ambas apontando para o commit-base acima. O arquivo local
`seminario-pqc-sat.zip` também foi preservado sem alteração; seu SHA-256 é
`0907ddc4a753b1c4f841a91fdd77ad222684c563eb549af7d35314f3caebaa8b`.

Na abertura do trabalho havia dois arquivos não versionados, que não foram
sobrescritos:

- `HANDOVER_ESTANDE_SBPC_PQC_SAT.md`;
- `seminario-pqc-sat.zip`.

O núcleo encontrado é composto por:

- `dashboard.py`: aplicação Pygame, modo simulado, cliente serial assíncrono,
  parser das respostas aplicado à UI e exportação de sessões;
- `tools/serial_bridge.py` e `tools/serial_protocol.py`: transporte e protocolo
  serial `V1`;
- `firmware/esp32_serial_spike/esp32_serial_spike.ino`: firmware da BlackBoard
  Wisdom, ML-KEM, AES-GCM, CRC32, perfis de CPU, botão e potenciômetro;
- `tools/aes_gcm_metrics_battery.py`: bateria que produziu a coleta oficial;
- `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`: campanha oficial
  pós-AES-GCM vigente;
- `tests/`: 96 testes existentes no início desta implementação.

## Reprodução da base

| Verificação | Resultado em 2026-07-20 | Evidência |
|---|---|---|
| Python disponível | PASS | Python 3.14.6; a documentação ainda citava 3.14.5 |
| Dependências instaladas | PASS | `python3 -m pip check`: nenhuma dependência quebrada |
| Compilação Python | PASS | `python3 -m py_compile dashboard.py` |
| Importação headless | PASS | importação com drivers SDL dummy |
| Testes existentes | PASS | 96 testes, 0 falhas |
| Compilação do firmware | PASS | PlatformIO: flash 70,3%, RAM estática 17,3% |
| Referência visual | PASS | `docs/stand/evidence/baseline_dashboard_1366x768.png` |
| Dashboard em hardware | NÃO REVALIDADO | nenhuma `/dev/ttyUSB0` ou `/dev/ttyACM0` presente |
| Handshake e comandos reais | NÃO REVALIDADO | placa ausente nesta auditoria |
| Botão e potenciômetro reais | NÃO REVALIDADO | placa ausente nesta auditoria |
| Coleta oficial anterior | PASS documental | JSON de 2026-07-02: 1.038 registros, 0 falhas |

`NÃO REVALIDADO` não significa falha do recurso. Significa apenas que a
evidência atual é código compilado e log oficial anterior, não uma nova
execução física em 2026-07-20.

## Verdade técnica observada

### AES-GCM

- O firmware define `AEAD_CIPHER = "AES-128-GCM"` e
  `AES128_KEY_BYTES = 16`.
- A chave derivada usa os 16 primeiros bytes de HMAC-SHA256 sobre um contexto
  que contém `AES-128-GCM`.
- A biblioteca é Mbed TLS (`mbedtls_gcm_*`) com chave de 128 bits.
- O nonce tem 12 bytes, é gerado pelo RNG por mensagem, e a tag tem 16 bytes.
- A recepção usa `mbedtls_gcm_auth_decrypt`; o plaintext só é aceito quando a
  autenticação e a comparação do material protegido passam.
- O log oficial contém 600/600 missões com `cipher=AES-128-GCM`, sem falhas
  AEAD e sem registros de outra cifra.

Decisão: todas as telas e documentos do modo estande devem dizer
`AES-128-GCM`, nunca AES-256-GCM.

### Função de `CLASSIC`

`MISSION CLASSIC` gera uma chave AES-128 aleatória por mensagem e copia essa
chave para os dois papéis lógicos executados na mesma placa. Não existe ECDH,
RSA, certificado nem acordo de chave clássico nesse caminho.

Decisão: a UI usará `Baseline AES-GCM` ou `baseline simétrico`. A comparação é
o custo de adicionar ML-KEM-512 ao baseline AES-GCM, e não uma comparação
completa entre criptografia assimétrica clássica e pós-quântica.

### Localização do bit flip e do CRC32

`FAULT NONE|CRC32 payload_hex index mask` é um harness de integridade separado
de `MISSION`. Ele:

1. recebe o payload em claro;
2. calcula `crc_before` sobre o payload original;
3. executa `payload[index] ^= mask`;
4. calcula `crc_after` sobre o payload mutado;
5. classifica a alteração como `SILENT` sem guardião ou `DETECTED_GUARD` com
   CRC32 quando os CRCs diferem.

A falha não é injetada no ciphertext de uma transmissão AES-GCM. A UI deve
localizá-la como corrupção controlada do payload/memória dentro do harness.
O CRC é um detector de erro acidental nessa região e não autentica contra um
atacante.

### Seleção do bit

O firmware lê o potenciômetro A39 com `ANALOG POT`. O dashboard limita a
leitura a 0..4095, mapeia linearmente para `payload_len * 8` posições e deriva:

- `byte_index = bit_position // 8`;
- `bit_mask = 1 << (bit_position % 8)`.

O mesmo par índice/máscara pode ser enviado a `FAULT NONE` e `FAULT CRC32`.
Essa repetição ainda precisa ser automatizada pela máquina de estados do modo
estande.

### Perfis de CPU

`PROFILE BASELINE` chama `setCpuFrequencyMhz(boot_cpu_mhz)` e
`PROFILE OBC-1U-LIMITED` chama `setCpuFrequencyMhz(80)`. A resposta inclui o
perfil ativo e `cpu_mhz`, portanto a UI pode exigir confirmação real antes de
rotular a medição. A troca ocorre em execução e não requer build separado.

`OBC-1U-LIMITED` é somente um perfil experimental; não representa uma
especificação universal de CubeSat.

### Botão, serial e simulação

- O botão no GPIO 27 possui debounce de 40 ms no firmware e emite o evento
  assíncrono `BUTTON_PING` apenas na borda de pressionamento.
- `DashboardSerialClient` já faz handshake obrigatório, fila de comandos fora
  do loop Pygame, timeout e tentativa de reconexão.
- O handshake valida `node=PQC-SAT-WISDOM` e `board=BlackBoard-Wisdom`.
- O dashboard original possui `--simulated`, mas seus números sintéticos
  internos não são apropriados como resultado real do estande. O novo modo
  deve carregar somente fixture oficial identificada e manter um rótulo
  permanente de simulação.

### Fonte oficial de métricas

A fonte vigente é
`logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`, SHA-256
`bcf16f1f49f6433ca7bdfde000023af1cb3b72546a3af16d570fe212edd6ce8d`.
Ela registra 600 missões, 400 ensaios de falha, seis benchmarks PQC e zero
falhas. As médias consolidadas são referências de campanha; execuções ao vivo
devem mostrar a resposta recebida na sessão atual.

## Gate de saída da auditoria

| Afirmação | Documentação | Código observado | Teste executado | Decisão da UI |
|---|---|---|---|---|
| AES-128 ou AES-256 | documentos vigentes dizem AES-128; narrativa externa citou AES-256 | chave de 16 B e Mbed TLS a 128 bits | firmware compilou; log tem 600/600 AES-128-GCM | mostrar `AES-128-GCM` |
| função de CLASSIC | guia descreve baseline simétrico | RNG gera chave AES local por mensagem; não há ECDH | 100 amostras oficiais por perfil entregues | mostrar `Baseline AES-GCM` |
| localização do bit flip | guia separa `FAULT` de `MISSION` | CRC antes do XOR em payload claro, harness separado | 200 `SILENT` e 200 `DETECTED_GUARD` no log | desenhar falha em payload/memória, não no canal GCM |
| perfil 80 MHz | perfil experimental documentado | troca dinâmica e resposta `cpu_mhz` | 300 missões oficiais a 80 MHz | aceitar ao vivo somente após confirmação; fixture sempre rotulada |

O gate documental está satisfeito. A implementação visual pode começar. A
validação física final permanece aberta até a Wisdom estar conectada.

## Adendo de validação em hardware

Depois do congelamento desta auditoria, a Wisdom apareceu em `/dev/ttyUSB0` e
foi submetida a um diagnóstico completo e a um ciclo curto do novo modo. Os
resultados estão em `docs/stand/evidence/hardware_smoke.json` e
`docs/stand/FINAL_VALIDATION.md`. O aceite longo e o botão físico continuam
tratados separadamente; este adendo não reescreve o estado observado no início
da auditoria.
