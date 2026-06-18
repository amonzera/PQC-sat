# Roadmap consolidado - PQC-SAT

Versão revisada em 2026-06-17.

## 1. Visão geral

O PQC-SAT deve demonstrar, em uma atividade de aproximadamente 20 minutos,
que segurança embarcada depende tanto do algoritmo criptográfico quanto da
integridade da implementação e do protocolo.

A interface visual já existe e o primeiro experimento mensurável também: o
dashboard muta um payload determinístico, registra eventos e compara os
cenários `NONE` e `CRC32`. O backend PQC real já está instalado na Wisdom com
ML-KEM-512 e medição inicial nos perfis `BASELINE` e `OBC-1U-LIMITED`. A
prioridade agora é usar essa base para bit-flips em payload/ciphertext,
checksum ativável/desativável, confirmação de chave e exportação auditável em
JSON.

## 2. Baseline auditado

| Item | Estado |
|---|---|
| Dashboard Pygame | Funcional |
| Modo fullscreen | Funcional |
| Console | Funcional |
| Sorteio provisório de falhas | Removido do caminho de classificação |
| Seed isolada do experimento | Funcional |
| Mutação real de bytes | Funcional no dashboard |
| ML-KEM real | Funcional na Wisdom com `mlkem-native` v1.1.0, commit `d2cae2b` |
| Interface serial PQC | `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP` e `PQC_BENCH` funcionais |
| Medição PQC na placa | `PQC_BENCH 5` medido em `BASELINE` e `OBC-1U-LIMITED`; `PQC_KAT` passou no perfil limitado |
| CRC/checksum real | CRC32 funcional no dashboard e no firmware |
| ESP32/serial | Funcional com `HELLO`, `STATUS`, sensores, OLED e `FAULT` |
| JSON/timeline/demo | Timeline, JSON e bateria A/B funcionais; demo visual automatizada ausente |

O dashboard já pode demonstrar `SILENT` versus `DETECTED_GUARD` em payload,
executar `RUN_BATTERY` A/B e exportar sessões em JSON. Ele ainda não deve ser
usado como coleta final enquanto não houver replay documentado e roteiro de
apresentação validado.

## 3. Gate 0 - protocolo experimental

Nenhuma fase de coleta deve começar antes destas decisões.

### 3.1 Objetos de teste

O projeto mistura três experimentos diferentes. Eles devem ser separados:

1. **Payload**: mensagem curta enviada entre duas pontas.
2. **Ciphertext ML-KEM**: saída de encapsulação entregue à decapsulação.
3. **Estado interno**: chave ou buffer em memória.

Para a apresentação curta, o experimento principal deve usar payload. A
corrupção de ciphertext ML-KEM pode ser uma extensão técnica. Corrupção de
estado interno exige instrumentação específica e fica fora do MVP.

### 3.2 Classificação dos resultados

| Resultado | Critério |
|---|---|
| `OK` | Os bytes recebidos são iguais aos originais. |
| `SILENT` | Os bytes mudaram e a aplicação aceitou o dado. |
| `DETECTED_GUARD` | O checksum/CRC divergiu do valor de referência. |
| `KEY_MISMATCH` | O harness observou segredos ML-KEM diferentes. |
| `PROTOCOL_REJECT` | Uma confirmação autenticada com a chave derivada falhou. |
| `INVALID_INPUT` | Tamanho ou formato foi rejeitado antes do algoritmo. |

ML-KEM não deve retornar um rótulo fictício `DETECTED_BY_DECAPS`. Para
ciphertexts com tamanho válido, a decapsulação produz um segredo. A detecção
operacional acontece no harness ou em um protocolo de confirmação.

### 3.3 Campanha de falhas

Cada evento deve conter:

```text
campaign_seed
trial_id
campaign_run_id
campaign_trial_id
target
byte_index
bit_mask
fault_width
guard
before_digest
after_digest
result
elapsed_us
mode
```

A mesma lista de falhas deve ser aplicada aos cenários A e B. A animação não
pode consumir a mesma fonte de aleatoriedade da campanha.

### 3.4 Comparação de guardiões

Para exatamente um bit-flip dentro da região protegida, XOR, CRC-16 e CRC-32
detectam a alteração. Percentuais como 15%, 5% e 1% não são justificáveis
nesse modelo.

Para comparar mecanismos, a campanha precisa incluir pelo menos um destes:

- dois ou mais bits alterados;
- bursts contíguos;
- bytes fora da região coberta;
- checksum também corrompido;
- truncamento ou reordenação.

O MVP pode comparar apenas `NONE` e `CRC32`, mantendo XOR/CRC-16 como extensão.

## 4. Arquitetura alvo

```text
Dashboard Pygame
    |
    +-- ExperimentEngine
    |     +-- gera campanha determinística
    |     +-- muta bytes
    |     +-- classifica resultados
    |     +-- produz eventos
    |
    +-- visualização / timeline / JSON
    |
    +-- SerialBridge opcional
          |
          +-- protocolo versionado
          +-- firmware ESP32
                +-- backend criptográfico identificado
                +-- guardião real
                +-- telemetria e tempos
```

Por enquanto, as classes Python podem permanecer em `dashboard.py`. O
firmware terá diretório próprio.

## 5. Perfil OBC didático

O ESP32 não deve representar genericamente "um CubeSat". Ele representa um
OBC COTS educacional de uma missão 1U com orçamento operacional explícito.

O perfil inicial será:

| Recurso | Limite do experimento |
|---|---|
| CPU | Um core dedicado à aplicação; frequência inicial de 80 MHz |
| RAM | Sem PSRAM; pico medido e limite de 256 KiB para aplicação + criptografia |
| Flash da aplicação | Máximo de 1 MiB |
| Rádio integrado | Wi-Fi e Bluetooth desativados |
| Comunicação | UART; comandos curtos no firmware e respostas host de até 512 caracteres |
| Telemetria | 1 Hz no modo nominal; eventos críticos imediatos |
| Persistência local | Ring buffer de até 128 eventos; exportação completa no host |
| Criptografia | Uma operação por vez; sem alocação dinâmica no caminho crítico |
| Saúde do sistema | Watchdog, brownout e free heap reportados |
| Energia | Duty cycle registrado; consumo só pode ser afirmado se for medido |

Os números são um perfil experimental, não uma afirmação de que todo OBC de
CubeSat possui esses limites. O ESP32 oferece até 240 MHz e 520 KiB de SRAM;
OBCs comerciais atuais podem ter mais memória, armazenamento redundante e
ECC. O interesse do perfil é avaliar comportamento sob orçamento controlado.

O experimento deve executar também um baseline a 240 MHz. Isso permite separar
"efeito da limitação escolhida" de "limitação intrínseca do algoritmo".

## 6. Ordem recomendada

A numeração dos documentos representa áreas de entrega, não uma dependência
linear rígida.

### Trilha PQC na placa

1. [Etapa 04](etapa_04_firmware_esp32.md): manter `mlkem-native` v1.1.0
   vendorizado como backend ML-KEM-512 da Wisdom.
2. Manter `PQC_INFO`, `PQC_KAT`, `PQC_KEYGEN`, `PQC_ENCAP`, `PQC_DECAP` e
   `PQC_BENCH` como comandos de bancada, fora do `HELP` visual da demo.
3. Manter `PQC_INFO` como fonte de alvo, backend, fonte, commit, licença,
   perfil, tempo e memória.
4. Medição inicial de tempo, heap, heap mínimo e flash nos perfis `BASELINE` e
   `OBC-1U-LIMITED` concluída em 2026-06-17.
5. Integrar os resultados no dashboard/JSON sem exportar segredos completos.

### Trilha software demonstrável

1. [Etapa 06](etapa_06_guardiao_integridade.md): expandir o guardião para
   checksum ativável/desativável no fluxo de campanha e depois no ciphertext.
2. [Etapa 07](etapa_07_modo_apresentacao.md): transformar `RUN_BATTERY` em
   campanha visual automatizada.
3. [Etapa 08](etapa_08_polimento_final.md): robustez, projetor e roteiro.

Etapas 01, 02 e 03 já estão implementadas e seus markdowns foram removidos. A
trilha PQC agora possui backend real medido; a demo deve continuar separando
dado medido, simulação e pendência.

### Trilha hardware

1. Manter [Etapa 04](etapa_04_firmware_esp32.md) e
   [Etapa 05](etapa_05_bridge_serial.md) estáveis.
2. Usar `FAULT NONE|CRC32 payload_hex index mask` apenas como validação real
   do experimento de payload na Wisdom.
3. Medir `PROFILE BASELINE` e `PROFILE OBC-1U-LIMITED` antes de qualquer
   afirmação de limitação operacional.

### Fora do caminho crítico

- radiação física;
- corrupção de estado interno do KEM;
- ML-KEM-768 ou ML-KEM-1024;
- otimizações multicore além do necessário para a apresentação.

Esses itens continuam válidos como extensão. O núcleo agora é: Wisdom
conectada, ML-KEM-512 medido, bit-flips manuais, checksum ativável/desativável
e coleta JSON.

## 7. Etapas e critérios

### Etapa 01 - núcleo e efeitos visuais

Estado: **implementada**.

Entregas:

- `ExperimentEngine` com RNG própria;
- geração e aplicação de bit-flips em `bytearray`;
- eventos estruturados;
- efeitos visuais acionados pelo resultado real;
- nenhuma mudança de resultado feita pela camada de desenho.

Aceite:

- repetir a seed reproduz a mesma campanha;
- bytes antes/depois podem ser inspecionados;
- `RESET_SESSION` reinicia a campanha;
- testes headless cobrem classificação.

### Etapa 02 - timeline

Estado: **implementada**.

Entregas:

- timeline limitada por quantidade de eventos;
- cor por resultado, não por comando;
- legenda e contadores;
- layout testado em 1920x1080 e 1366x768.

Aceite:

- um evento gera exatamente um ponto;
- reset visual não apaga indevidamente dados da campanha;
- legenda permanece visível;
- layout validado por teste para 1920x1080 e 1366x768;
- não há overflow do painel.

### Etapa 03 - JSON

Estado: **implementada**.

Entregas:

- exportação atômica para `logs/`;
- schema versionado;
- seed, modo, alvo, posição, máscara, `campaign_run_id` e
  `campaign_trial_id`;
- resumo derivado dos eventos;
- amostras de hardware com CPU, heap, heap mínimo, flash, perfil e tempo;
- proxy de energia explicitamente rotulado enquanto não houver medidor real;
- auto-save opcional.

Aceite:

- o JSON permite reproduzir cada mutação;
- exportar não altera a campanha;
- falha de escrita aparece na interface;
- `RESET_SESSION` não destrói resultados já registrados sem confirmação.

### Etapa 04 - firmware

Estado: **implementada para transporte, periféricos, payload/CRC32,
ML-KEM-512 real e medição inicial nos perfis baseline/limitado**.

Primeiro deve ser registrado:

- modelo exato da placa;
- arquitetura da CPU;
- RAM e flash disponíveis;
- framework escolhido;
- biblioteca/commit criptográfico;
- licença;
- resultado de um KAT ou vetor conhecido.

Depois do inventário, aplique o perfil OBC didático. Toda medição deve
registrar:

```text
cpu_mhz
active_cores
free_heap_before
min_free_heap
app_flash_bytes
radio_enabled
elapsed_us
```

Uma referência do projeto usa Kyber512-90s, ESP-IDF e ESP32-S3. Outra
implementa ML-KEM-512 em ESP32 no SBSeg 2025. Isso demonstra viabilidade
relacionada, mas não equivale a uma biblioteca pronta para a Wisdom e o
framework deste projeto. `pqm4` é direcionado a Cortex-M4.

O spike foi implementado nesta ordem:

1. `PING` e framing serial;
2. mutação de payload + CRC32;
3. ML-KEM-512 na placa ou fallback identificado de Kyber512;
4. KAT/vetor conhecido;
5. benchmark de KEM nos dois perfis;
6. somente então integração com a demo.

Medição real registrada em 2026-06-17:

| Perfil | CPU | Comando | Resultado |
|---|---:|---|---|
| `BASELINE` | 240 MHz | `PQC_BENCH 5` | `keygen_avg_us=3369`, `encap_avg_us=3878`, `decap_avg_us=5013`, `elapsed_us=62068`, `heap=202444`, `min_heap=198456` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_INFO` | `pqc_status=ready`, `pk=800`, `sk=1632`, `ct=768`, `ss=32`, `elapsed_us=24697`, `heap=202444`, `min_heap=198456`, `flash=4194304` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_KAT` | `kat=pass`, `key_match=1`, `ss_crc32=0xD9DA8D6C`, `elapsed_us=39270` |
| `OBC-1U-LIMITED` | 80 MHz | `PQC_BENCH 5` | `keygen_avg_us=10101`, `encap_avg_us=11778`, `decap_avg_us=15214`, `elapsed_us=187371`, `heap=202444`, `min_heap=198456` |

Fallback aceitável:

- emulador claramente rotulado;
- ou KEM real executado no notebook, com ESP32 responsável pela mutação e
  telemetria.

Fallback inaceitável:

- chamar bytes aleatórios ou AES de "ML-KEM";
- usar funções de hash diferentes em encapsulação/decapsulação e esperar
  segredos iguais;
- alegar conformidade FIPS sem vetores e versão identificada.

### Etapa 05 - bridge serial

Estado: **implementada para a demo atual**.

Requisitos:

- `pygame.init()` e display dentro de `main()`;
- import opcional de pyserial;
- leitura bloqueante com timeout em thread ou espera eficiente;
- fila thread-safe;
- estados `SIMULATED`, `CONNECTING`, `CONNECTED`, `LOST`;
- reconexão preservando o objeto bridge;
- fechamento idempotente;
- protocolo com versão e `request_id`.

Formato implementado para experimento de payload:

```text
PC>  V1|17|FAULT|CRC32|payload_hex|12|0x04
ESP> V1|17|RESULT|OK|result=DETECTED_GUARD|elapsed_us=83
```

Aceite:

- nenhuma resposta é atribuída ao comando errado;
- desconectar o cabo não trava o Pygame;
- falha inicial continua elegível para reconexão;
- modo simulado não depende de pyserial.

### Etapa 06 - guardião

Estado: **parcialmente implementada**.

Implementação mínima:

1. compute o valor de referência antes da falha;
2. aplique a falha;
3. compute novamente;
4. compare;
5. registre cobertura e overhead.

O firmware antigo proposto chamava `checkIntegrity()` sem inicializar os
valores armazenados. Isso deve ser impedido por uma API explícita:

```text
guard.prepare(data)
mutate(data, fault)
guard.verify(data)
```

Aceite:

- teste conhecido para cada checksum;
- single-bit detectado em toda posição coberta;
- campanhas multi-bit documentadas;
- nenhuma taxa é hard-coded como resultado científico.

### Etapa 07 - modo apresentação

Estado: **não implementada**.

A demo automatizada é um segmento de cerca de 45-60 segundos dentro da aula
de 20 minutos.

Requisitos:

- usa a mesma campanha em A e B;
- número de tentativas configurável;
- não depende de sorte favorável;
- pausa, parada e reinício;
- overlay calcula a conclusão a partir dos dados;
- texto não afirma melhora se os resultados não sustentarem isso.

### Etapa 08 - fechamento

Entregas:

- splash opcional com `--no-splash`;
- help completo;
- resumo e auto-save;
- tratamento de exceções com cleanup, sem esconder traceback;
- teste prolongado;
- teste em projetor;
- até cinco slides;
- roteiro de 20 minutos;
- limitações no relatório.

Não use a expressão "nenhum crash possível". O critério correto é "nenhuma
falha conhecida nos cenários testados".

## 8. Cronograma sugerido

### Próximos cortes

1. Exportar resultados PQC no JSON de campanha sem segredos completos.
2. Ligar bit-flip manual ao fluxo PQC: payload primeiro, ciphertext depois do
   KEM estável.
3. Implementar checksum ativável/desativável no fluxo de campanha.
4. Promover `RUN_BATTERY` para `CampaignRunner` visual com replay documentado.
5. Implementar `DEMO`, `DEMO_PAUSE`, `DEMO_STOP` e overlay derivado dos dados.
6. Executar bateria PQC prolongada, validar projetor, resolução e roteiro.

## 9. Riscos e decisões

| Risco | Mitigação |
|---|---|
| Regressão de build/flash do ML-KEM na placa | Manter `mlkem-native` vendorizado, KAT host e build PlatformIO como validação obrigatória. |
| Biblioteca implementa Kyber antigo, não FIPS 203 | Identificar variante e não chamá-la de ML-KEM. |
| Cinco amostras geram conclusão fraca | Usar campanha determinística maior na coleta e subconjunto visual na demo. |
| Serial perde ou reordena respostas | `request_id`, timeout e parser estrito. |
| Layout não cabe no projetor | Testar duas resoluções e reduzir conteúdo, não a fonte indiscriminadamente. |
| Resultado simulado é confundido com medição | Campo `mode` em UI e JSON. |
| Limite artificial é tratado como característica de todo CubeSat | Nomear o perfil e comparar com o baseline sem limitação. |

## 10. Entrega final

### Obrigatória

- dashboard funcional sem hardware;
- campanha reproduzível;
- comparação A/B baseada em bytes;
- JSON;
- demo automatizada;
- documentação das limitações;
- slides e roteiro.

### Hardware já entregue para o MVP

- ESP32 conectado por bridge serial;
- ML-KEM-512 real;
- medição inicial de tempo e memória no dispositivo.

O hardware agora sustenta a demonstração. A entrega final ainda depende de
demo automatizada, coleta maior, roteiro e limites científicos explícitos.

## 11. Referências técnicas para decisões

- NIST FIPS 203:
  <https://csrc.nist.gov/pubs/fips/203/final>
- Implementação de Kyber512-90s em ESP32-S3:
  <https://arxiv.org/abs/2503.10207>
- ML-KEM-512 multicore em ESP32:
  <https://doi.org/10.5753/sbseg.2025.9783>
- pqm4, alvo ARM Cortex-M4:
  <https://github.com/mupq/pqm4>
- liboqs, biblioteca de prototipagem:
  <https://github.com/open-quantum-safe/liboqs>
- ESP32 Series Datasheet:
  <https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf>
- Exemplo de OBC comercial com Cortex-M7, FRAM ECC e armazenamento redundante:
  <https://www.endurosat.com/cubesat-store/cubesat-obc/onboard-computer-obc/>
