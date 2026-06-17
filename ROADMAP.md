# Roadmap consolidado - PQC-SAT

Versão revisada em 2026-06-09.

## 1. Visão geral

O PQC-SAT deve demonstrar, em uma atividade de aproximadamente 20 minutos,
que segurança embarcada depende tanto do algoritmo criptográfico quanto da
integridade da implementação e do protocolo.

A interface visual já existe. O experimento mensurável ainda não existe.
Portanto, a prioridade não é adicionar mais animação: é construir uma cadeia
de evidências reproduzível por baixo do dashboard.

## 2. Baseline auditado

| Item | Estado |
|---|---|
| Dashboard Pygame | Funcional |
| Modo fullscreen | Funcional |
| Console | Funcional |
| Sorteio provisório de falhas | Funcional, apenas para UI |
| Seed isolada do experimento | Funcional |
| Mutação real de bytes | Ausente |
| ML-KEM real | Ausente |
| CRC/checksum real | Ausente |
| ESP32/serial | Ausente |
| CSV/timeline/demo | Ausente |

O dashboard não deve ser usado para gerar conclusões enquanto os resultados
forem sorteados.

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
    +-- visualização / timeline / CSV
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
| Comunicação | UART; frames de até 256 bytes com fragmentação |
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

### Trilha software demonstrável

1. [Etapa 01](etapa_01_efeitos_visuais_falha.md): núcleo determinístico e
   efeitos de falha.
2. [Etapa 02](etapa_02_grafico_temporal.md): timeline baseada em eventos.
3. [Etapa 03](etapa_03_exportacao_csv.md): CSV auditável.
4. [Etapa 06](etapa_06_guardiao_integridade.md): guardião real no simulador.
5. [Etapa 07](etapa_07_modo_apresentacao.md): campanha A/B automatizada.

Essa trilha gera uma entrega didática completa sem depender do hardware.

### Trilha hardware

1. [Etapa 04](etapa_04_firmware_esp32.md): spike de viabilidade na placa real.
2. [Etapa 05](etapa_05_bridge_serial.md): bridge para protocolo congelado.
3. [Etapa 06](etapa_06_guardiao_integridade.md): integração do guardião e
   medições reais.

### Fechamento

1. [Etapa 08](etapa_08_polimento_final.md): robustez, projetor, slides,
   roteiro e relatório.

## 7. Etapas e critérios

### Etapa 01 - núcleo e efeitos visuais

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

Entregas:

- timeline limitada por quantidade de eventos;
- cor por resultado, não por comando;
- legenda e contadores;
- layout testado em 1920x1080 e 1366x768.

Aceite:

- um evento gera exatamente um ponto;
- reset visual não apaga indevidamente dados da campanha;
- não há overflow do painel.

### Etapa 03 - CSV

Entregas:

- exportação atômica para `logs/`;
- schema versionado;
- seed, modo, alvo, posição e máscara;
- resumo derivado dos eventos;
- auto-save opcional.

Aceite:

- o CSV permite reproduzir cada mutação;
- exportar não altera a campanha;
- falha de escrita aparece na interface;
- `RESET_SESSION` não destrói resultados já registrados sem confirmação.

### Etapa 04 - firmware

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
relacionada, mas não equivale a ML-KEM-768 pronto para a placa e o framework
deste projeto. `pqm4` é direcionado a Cortex-M4.

O spike deve implementar nesta ordem:

1. `PING` e framing serial;
2. mutação de payload + CRC32;
3. backend criptográfico no host ou ESP32;
4. KAT;
5. somente então integração com a demo.

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

Requisitos:

- `pygame.init()` e display dentro de `main()`;
- import opcional de pyserial;
- leitura bloqueante com timeout em thread ou espera eficiente;
- fila thread-safe;
- estados `SIMULATED`, `CONNECTING`, `CONNECTED`, `LOST`;
- reconexão preservando o objeto bridge;
- fechamento idempotente;
- protocolo com versão e `request_id`.

Formato sugerido:

```text
PC>  V1|17|FAULT|payload|12|04
ESP> V1|17|RESULT|DETECTED_GUARD|elapsed_us=83
```

Aceite:

- nenhuma resposta é atribuída ao comando errado;
- desconectar o cabo não trava o Pygame;
- falha inicial continua elegível para reconexão;
- modo simulado não depende de pyserial.

### Etapa 06 - guardião

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

### Semana 1

- Gate 0;
- Etapa 01;
- testes do engine;
- Etapa 02.

### Semana 2

- Etapa 03;
- Etapa 06 no simulador;
- Etapa 07;
- primeira demo completa sem hardware.

### Semana 3

- inventário da placa;
- Etapa 04;
- decisão go/no-go para ML-KEM no ESP32;
- protocolo serial.

### Semana 4

- Etapa 05 e integração, se o spike passar;
- Etapa 08;
- slides, roteiro, relatório e ensaio.

## 9. Riscos e decisões

| Risco | Mitigação |
|---|---|
| ML-KEM não cabe ou não compila na placa | KEM no host + ESP32 como alvo de falha, claramente documentado. |
| Biblioteca implementa Kyber antigo, não FIPS 203 | Identificar variante e não chamá-la de ML-KEM. |
| Cinco amostras geram conclusão fraca | Usar campanha determinística maior na coleta e subconjunto visual na demo. |
| Serial perde ou reordena respostas | `request_id`, timeout e parser estrito. |
| Layout não cabe no projetor | Testar duas resoluções e reduzir conteúdo, não a fonte indiscriminadamente. |
| Resultado simulado é confundido com medição | Campo `mode` em UI e CSV. |
| Limite artificial é tratado como característica de todo CubeSat | Nomear o perfil e comparar com o baseline sem limitação. |

## 10. Entrega final

### Obrigatória

- dashboard funcional sem hardware;
- campanha reproduzível;
- comparação A/B baseada em bytes;
- CSV;
- demo automatizada;
- documentação das limitações;
- slides e roteiro.

### Condicional

- ESP32 conectado;
- ML-KEM/Kyber real;
- medições de tempo e memória no dispositivo.

O hardware é uma melhoria importante, mas não deve bloquear uma entrega
didática honesta e reproduzível.

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
