# Guia didatico da apresentacao - PQC-SAT

Este arquivo explica, passo a passo, o que esta funcionando no projeto e como
apresentar isso para uma pessoa que nao conhece criptografia. Ele foi escrito
para apoiar o seminario: a ideia e que alguem consiga entender a historia,
operar a demonstracao, interpretar os resultados e saber o que nao deve ser
afirmado.

## 1. Ideia em uma frase

O PQC-SAT mostra que, em um sistema embarcado, criptografia mais forte pode
custar mais CPU, RAM, tempo e trafego; e que esse custo aumenta quando, alem
da criptografia pos-quantica, tambem exigimos verificacao de integridade por
checksum.

## 2. A historia da apresentacao

Imagine um pequeno computador embarcado em um satelite educacional. Esse
computador recebe mensagens e tambem executa criptografia. Em ambiente espacial,
radiação pode causar falhas transitorias, como inverter um bit em um byte.

No nosso seminario, a demonstracao principal envia uma mensagem curta pelo
"satelite" em tres cenarios:

1. `CLASSIC`: mensagem autenticada com HMAC-SHA256;
2. `PQC`: mensagem autenticada depois de acordo de segredo com ML-KEM-512;
3. `PQC_CRC32`: o mesmo fluxo PQC com CRC32 no payload.

Depois disso, usamos bit-flips para mostrar por que integridade importa. Nao
usamos radiacao fisica. Em vez disso, simulamos o efeito de forma controlada:

1. escolhemos um dado;
2. invertemos um bit;
3. observamos se o erro passa despercebido ou se e detectado;
4. repetimos a mesma falha com e sem mecanismo de integridade;
5. conectamos isso com o custo real de uma sessao ML-KEM-512 na placa
   ESP32/Wisdom.

A mensagem principal e simples:

- criptografia classica simetrica e barata para o hardware;
- PQC aumenta o custo, mas prepara a comunicacao para o mundo pos-quantico;
- PQC mais checksum aumenta a robustez de integridade e acrescenta custo;
- sem protecao de integridade, uma falha pode virar **falha silenciosa**;
- com CRC32 no payload, a mesma falha vira **erro detectado**;
- em ML-KEM, a decapsulacao nao denuncia automaticamente todo ciphertext
  alterado; a deteccao operacional vem da comparacao/confirmacao da chave.

## 3. O que esta funcionando agora

### Dashboard visual

Arquivo principal: `dashboard.py`.

O dashboard em Pygame esta funcional e serve como tela principal da
apresentacao. Ele mostra:

- animacao do satelite/robo;
- Terra e orbita;
- painel esquerdo com integridade, falhas e timeline;
- faixa superior com metricas essenciais;
- painel direito com botoes da demonstracao e terminal textual;
- modo simulado e modo hardware;
- exportacao JSON da sessao.

O dashboard nao deve ficar poluindo a apresentacao com comandos de bancada.
Por isso, os botoes visuais foram reduzidos ao roteiro principal.
Hoje os botoes centrais da apresentacao sao `CLÁSSICA`, `PQC`, `PQC+CRC`,
`DEMO`, `FALHA`, `STATUS`, `EXPORT` e `OLED`.

### Hardware Wisdom/ESP32

O equipamento usado e a RoboCore BlackBoard Wisdom com ESP32.

No projeto, ela representa um OBC COTS educacional, ou seja, um computador de
bordo didatico inspirado em sistemas de CubeSat. Ela nao deve ser apresentada
como um CubeSat real.

Funcionalidades validadas na placa:

- protocolo serial `V1`;
- handshake `HELLO`;
- estado `STATUS`;
- OLED standby com icone do projeto;
- controle tecnico de sensores/LEDs pelo terminal;
- firmware com ML-KEM-512 real;
- `PQC_KAT`;
- `PQC_INFO`;
- `PQC_FAULT`;
- `PQC_BENCH`;
- `MISSION CLASSIC`;
- `MISSION PQC`;
- `MISSION PQC_CRC32`;
- `FAULT CRC32` para payload;
- perfis `BASELINE` e `OBC-1U-LIMITED`.

### Criptografia PQC real

O firmware executa ML-KEM-512 real usando `mlkem-native`.

O que isso significa em linguagem simples:

- ML-KEM e um mecanismo para duas partes chegarem a um mesmo segredo;
- esse segredo depois poderia ser usado por outras partes de um protocolo;
- se um ciphertext for alterado, a decapsulacao pode produzir outro segredo;
- por isso, o projeto testa se as duas pontas chegaram ao mesmo segredo;
- com confirmacao HMAC-SHA256, uma divergencia vira rejeicao de protocolo.

Resultados importantes:

- `PQC_KAT`: passou;
- `PQC_FAULT 0 0x01 NONE`: retornou `KEY_MISMATCH`;
- `PQC_FAULT 0 0x01 CONFIRM`: retornou `PROTOCOL_REJECT`.

### Entrega de mensagem da missao

O comando `MISSION` e o fluxo mais importante para a apresentacao final.

Ele executa uma entrega de mensagem curta no firmware e retorna metricas:

- tempo total;
- bytes transmitidos;
- heap/RAM livre;
- perfil de CPU;
- resultado da entrega;
- custo de HMAC;
- custo de ML-KEM quando o cenario usa PQC;
- custo de CRC32 quando o cenario usa checksum.

Os tres comandos sao:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Leitura para explicar em sala:

- `CLASSIC` mostra o custo de proteger uma mensagem com criptografia classica
  simetrica;
- `PQC` mostra o custo de estabelecer segredo com ML-KEM-512 antes de proteger
  a mensagem;
- `PQC_CRC32` mostra o custo adicional de colocar um guardiao de integridade
  no payload.

### Bit-flips manuais

Um bit-flip e a inversao de um bit.

Exemplo conceitual:

```text
Antes: 01010000
Depois: 01010001
```

So um bit mudou. Isso parece pequeno, mas em dados, mensagens ou ciphertexts
pode mudar completamente o resultado.

No projeto, os bit-flips aparecem de duas formas:

- no dashboard, sobre um payload didatico;
- no firmware, sobre ciphertext ML-KEM ou payload hexadecimal.

### Checksum CRC32

CRC32 e um detector simples de alteracao em dados. Ele nao e criptografia. Ele
nao esconde nada. Ele apenas ajuda a perceber que os bytes mudaram.

No seminario, CRC32 e usado para demonstrar a diferenca entre:

- aceitar dado corrompido sem perceber;
- detectar que o dado foi alterado.

Essa diferenca e o ponto visual mais forte da demo A/B.

### Exportacao JSON

O projeto exporta JSON para que os resultados nao dependam apenas da animacao.

Arquivos principais de resultado:

- `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json`;
- `logs/20260618T183829Z_sim-42.json`.

O JSON guarda:

- comandos executados;
- tempos;
- resultado de falhas;
- eventos da demo;
- status do hardware;
- informacoes PQC;
- comparacao `CLASSIC`, `PQC` e `PQC_CRC32`;
- resumo de sucesso/falha.

Isso permite apresentar a demo e depois mostrar que os resultados foram
registrados de forma auditavel.

## 4. Resultado final consolidado

Fonte principal:

```text
logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json
```

Esse arquivo e o aceite anterior ao comando `MISSION`. Para a apresentacao
consolidada, gere um JSON novo com os comandos documentados em
`METRICAS_CONSOLIDADAS.md` e use esse JSON como fonte principal da comparacao
`CLASSIC` versus `PQC` versus `PQC_CRC32`.

Resumo do aceite final:

| Medida | Resultado |
|---|---|
| Tempo total | 1.816,87 s |
| Registros | 77 |
| Falhas no aceite | 0 |
| Comandos no long-run | 60 |
| Benchmarks PQC | 2 |
| Demo headless | OK |
| Payload CRC32 | 13/13 `DETECTED_GUARD` |

Resultados da demo A/B:

| Cenario | Resultado |
|---|---|
| A, sem CRC32 | 5/5 falhas silenciosas |
| B, com CRC32 | 5/5 falhas detectadas |

Resultados PQC:

| Teste | Resultado |
|---|---|
| `PQC_KAT` | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| `PQC_FAULT CONFIRM` | `PROTOCOL_REJECT`, `confirmation=HMAC-SHA256` |
| `PQC_FAULT NONE` | `KEY_MISMATCH` |

Benchmark ML-KEM-512:

| Perfil | CPU | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|---:|
| `BASELINE` | 240 MHz | 3304 | 3867 | 4991 |
| `OBC-1U-LIMITED` | 80 MHz | 10064 | 11789 | 15214 |

Leitura simples:

- com menos CPU, o algoritmo fica mais lento;
- mesmo assim, ML-KEM-512 continuou funcionando;
- a confirmacao de chave foi capaz de rejeitar uma sessao divergente;
- CRC32 detectou todos os bit-flips de payload testados no aceite.

Metricas novas que devem ser consolidadas apos gravar o firmware atualizado:

| Cenario | O que mostrar |
|---|---|
| `MISSION CLASSIC` | `elapsed_us`, `bytes_total`, `heap`, `tag_match`, `result` |
| `MISSION PQC` | `elapsed_us`, `bytes_total`, `heap`, `key_match`, `tag_match`, `result` |
| `MISSION PQC_CRC32` | `elapsed_us`, `bytes_total`, `heap`, `key_match`, `tag_match`, `crc_match`, `result` |

## 5. Como explicar os termos para uma pessoa leiga

### O que e um payload?

Payload e a mensagem/dado que esta sendo enviado. No nosso caso, e uma mensagem
curta usada para mostrar o efeito de uma alteracao de bit.

### O que e uma falha silenciosa?

E quando o dado mudou, mas o sistema aceitou como se estivesse tudo certo.

No seminario:

```text
SILENT = o erro passou despercebido
```

### O que e um erro detectado?

E quando o sistema percebe que algo mudou e nao trata o dado como normal.

No seminario:

```text
DETECTED_GUARD = o CRC32 percebeu a alteracao
```

### O que e ML-KEM?

ML-KEM e um mecanismo de encapsulamento de chave padronizado pelo NIST. Ele e
parte da criptografia pos-quantica.

Explicacao curta para a fala:

> ML-KEM nao e uma cifra para esconder diretamente uma mensagem. Ele serve para
> duas partes chegarem a um segredo compartilhado que depois pode proteger uma
> comunicacao.

### O que significa pos-quantica?

Criptografia pos-quantica e a familia de algoritmos projetada para resistir a
ataques futuros com computadores quanticos grandes o suficiente para quebrar
alguns esquemas classicos.

Para o seminario, nao precisamos provar resistencia quantica. O ponto e mostrar
que um algoritmo moderno tambem precisa ser integrado com cuidado em hardware
limitado e sujeito a falhas.

### O que e um ciphertext?

E um dado criptografico produzido por uma etapa do protocolo. No ML-KEM, o
ciphertext e entregue para a outra ponta decapsular e chegar ao segredo.

### O que e `KEY_MISMATCH`?

Significa que o harness de teste observou que os segredos das duas pontas nao
bateram.

Fala sugerida:

> Aqui nao estamos dizendo que a decapsulacao gritou "erro". Estamos dizendo
> que, ao comparar os resultados no experimento, vimos que as duas pontas
> chegaram a segredos diferentes.

### O que e `PROTOCOL_REJECT`?

Significa que uma confirmacao autenticada da chave falhou.

Fala sugerida:

> Quando adicionamos uma confirmacao baseada na chave derivada, a divergencia
> deixa de ser so uma observacao do laboratorio e vira uma rejeicao operacional
> da sessao.

### O que e HMAC-SHA256?

E um mecanismo para calcular uma etiqueta de autenticacao usando uma chave.
Aqui, ele serve para confirmar se as duas pontas realmente chegaram ao mesmo
segredo.

## 6. O que aparece na tela

### Centro da tela

Mostra a animacao do satelite e a Terra. Quando a Wisdom esta conectada, a
orbita fica ativa. A ideia visual e lembrar o contexto de sistemas embarcados
inspirados em CubeSat.

### Faixa superior

Mostra apenas metricas essenciais para a apresentacao:

- CPU;
- RAM;
- CLÁSSICA;
- PQC;
- PQC+CRC.

Essas metricas foram reduzidas para nao poluir a tela.

### Painel esquerdo

Mostra a parte experimental:

- status da sessao;
- algoritmo/estado PQC;
- guardiao ativo;
- quantidade de injecoes de falha;
- falhas silenciosas;
- erros detectados;
- barra de integridade;
- timeline dos eventos.

### Painel direito

Tem botoes somente para o roteiro visual:

- `DEMO`;
- `CLÁSSICA`;
- `PQC`;
- `PQC+CRC`;
- `STATUS`;
- `FALHA`;
- `PAUSA`;
- `EXPORT`;
- `OLED`.

O terminal textual continua existindo abaixo dos botoes. Ele aceita comandos
avancados, mas esses comandos nao devem virar parte principal da apresentacao.

## 7. Sequencia recomendada para apresentar

### Antes de abrir o dashboard

Verifique:

```bash
python3 -m compileall -q dashboard.py tools tests
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
```

Se for compilar firmware:

```bash
python3 -m platformio run -e robocore_wisdom_esp32
```

Se a porta estiver bloqueada no Linux:

```bash
sudo chmod 666 /dev/ttyUSB0
```

### Abrir a demonstracao

Com a placa conectada:

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

Sem placa, apenas para ensaio visual:

```bash
python3 dashboard.py --simulated
```

Para pular splash em teste:

```bash
python3 dashboard.py --simulated --no-splash
```

### Passo 1: confirmar estado

No dashboard, clique:

```text
STATUS
```

O que esperar:

- `STATUS` atualiza CPU, heap/RAM e estado da placa;

Explique:

> Antes de enviar mensagens, confirmamos que a placa esta viva, qual perfil de
> CPU esta ativo e quanta memoria ainda esta livre.

### Passo 2: enviar mensagens nos tres cenarios

Clique, nesta ordem:

```text
CLÁSSICA
PQC
PQC+CRC
```

Ou digite:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

O que acontece:

1. `CLASSIC` autentica a mensagem com HMAC-SHA256;
2. `PQC` executa ML-KEM-512, deriva segredo e autentica a mensagem;
3. `PQC_CRC32` repete o fluxo PQC e adiciona CRC32 no payload;
4. o topo do dashboard atualiza tempo e bytes;
5. o overlay mostra mensagem entregue;
6. LEDs/bargraph reforcam visualmente o aumento de custo.

Como explicar:

> A mensagem enviada e pequena. Mesmo assim, quando trocamos o baseline
> classico por PQC, o custo cresce. Quando adicionamos checksum ao fluxo PQC,
> ganhamos mais integridade observavel e tambem somamos mais trabalho ao
> hardware.

### Passo 3: rodar demo automatica de falhas

Clique:

```text
DEMO
```

Ou digite:

```text
DEMO 5
```

O que acontece:

1. o dashboard gera uma lista deterministica de falhas;
2. aplica essas falhas no cenario A, sem CRC32;
3. registra falhas silenciosas;
4. aplica as mesmas falhas no cenario B, com CRC32;
5. registra erros detectados;
6. mostra resumo visual;
7. exporta JSON.

Como explicar:

> A comparacao e justa porque usamos a mesma lista de falhas nos dois cenarios.
> A unica diferenca e a presenca ou ausencia do guardiao CRC32.

### Passo 4: demonstrar falha manualmente

Para mostrar sem automatizar:

```text
CHECKSUM OFF
INJECT_FAULT
CHECKSUM ON
INJECT_FAULT
CRC_CHECK
```

O que esperar:

- com `CHECKSUM OFF`, a falha tende a aparecer como `SILENT`;
- com `CHECKSUM ON`, a falha tende a aparecer como `DETECTED_GUARD`;
- `CRC_CHECK` forca uma tentativa com CRC32.

### Passo 5: exportar

Clique:

```text
EXPORT
```

Ou digite:

```text
EXPORT_JSON
```

O arquivo vai para `logs/`.

Explique:

> A animacao ajuda a entender, mas o JSON e a evidencia. Ele registra eventos,
> resultados e metricas para auditoria.

## 8. Comandos que funcionam, mas nao devem ser foco visual

Esses comandos existem e sao uteis, mas devem ficar no terminal/HELP ou no
`tools/serial_console.py`:

| Comando | Por que nao fica nos botoes |
|---|---|
| `PING` | Bom para diagnostico, mas pouco didatico na tela principal |
| `TELEMETRY` | Pode poluir a serial e a apresentacao se enviado o tempo todo |
| `RUN_BATTERY` | E coleta local, nao narrativa principal |
| `PQC_KAT` | Importante para bancada, mas tecnico demais para o fluxo visual |
| `PQC_BENCH` | Gera dados, mas nao e a demo principal |
| `PQC_FAULT` | Essencial para explicar resultado, mas melhor mostrar como tabela |
| `LED`, `RGB`, `BARGRAPH` | Efeito visual de hardware; no dashboard eles sao acionados indiretamente por `MISSION` |
| sensores | Extras da placa, fora do argumento principal |

Isso evita que a apresentacao vire uma lista de comandos e mantém o foco:

```text
mensagem -> custo -> PQC real -> checksum -> falha/deteccao -> limites
```

## 9. Como explicar os resultados finais

### Resultado 1: CLASSIC, PQC e PQC+CRC têm custos diferentes

Use a frase:

> A mesma mensagem de missao pode ser entregue com criptografia classica,
> com PQC, ou com PQC mais checksum. O que muda e o custo observado no
> hardware: tempo, bytes e memoria.

Base:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Use o JSON novo para preencher a tabela final de `elapsed_us`, `bytes_total`
e `heap`.

### Resultado 2: CRC32 detectou o payload alterado

Use a frase:

> Quando protegemos o payload com CRC32, a mesma alteracao de bit deixou de
> passar silenciosamente e virou um erro detectado.

Base:

```text
13/13 DETECTED_GUARD no aceite final
```

### Resultado 3: ML-KEM funcionou na Wisdom

Use a frase:

> A placa nao esta apenas simulando PQC. Ela executa ML-KEM-512 real pelo
> backend mlkem-native.

Base:

```text
PQC_KAT = kat=pass
pk=800, sk=1632, ct=768, ss=32
```

### Resultado 4: bit-flip em ciphertext causa divergencia

Use a frase:

> Ao corromper um ciphertext ML-KEM, as pontas podem chegar a segredos
> diferentes. Isso aparece como KEY_MISMATCH no harness.

Base:

```text
PQC_FAULT NONE -> KEY_MISMATCH
```

### Resultado 5: confirmacao transforma divergencia em rejeicao

Use a frase:

> Com uma confirmacao HMAC-SHA256, a divergencia da chave passa a ser rejeitada
> pelo protocolo.

Base:

```text
PQC_FAULT CONFIRM -> PROTOCOL_REJECT
```

### Resultado 6: limitar CPU aumenta custo, mas nao quebra a demo

Use a tabela:

| Perfil | Keygen | Encap | Decap |
|---|---:|---:|---:|
| 240 MHz | 3304 us | 3867 us | 4991 us |
| 80 MHz | 10064 us | 11789 us | 15214 us |

Use a frase:

> O perfil limitado deixa o algoritmo mais lento, mas a operacao continua
> funcional. Isso ajuda a discutir custo computacional em hardware embarcado.

## 10. O que nao afirmar

Nao diga:

- "provamos que isso funciona em um CubeSat real";
- "medimos consumo em watts";
- "CRC32 resolve seguranca";
- "ML-KEM detecta sozinho qualquer ciphertext corrompido";
- "ML-KEM cifra diretamente a mensagem";
- "HMAC-SHA256 e equivalente a ECDH";
- "o experimento prova resistencia a radiacao real";
- "o ESP32 representa todos os OBCs de CubeSat";
- "checksum de ciphertext e a contribuicao principal".

Diga:

- "a Wisdom representa um OBC COTS educacional";
- "simulamos bit-flips manualmente";
- "CLASSIC e um baseline simetrico de mensagem autenticada";
- "PQC usa ML-KEM para estabelecer segredo antes de autenticar a mensagem";
- "CRC32 mostra deteccao de integridade no payload";
- "ML-KEM-512 foi executado na placa";
- "a confirmacao de chave e o ponto de deteccao operacional";
- "energia real exigiria medidor externo";
- "o objetivo e didatico e reproduzivel".

## 11. Bateria longa de hardware

Regra atual do projeto:

> Baterias longas nao devem ser iniciadas pelo agente. O operador roda no
> terminal e depois chama o agente para analisar o JSON.

Se precisar repetir a bateria longa:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 tools/stage8_acceptance.py --port /dev/ttyUSB0 --timeout 12 --duration 1800 --interval 30
```

Resultado esperado:

```text
stage8_acceptance_json=logs/<timestamp>_stage8_acceptance_dev-ttyusb0.json
summary={"dashboard_demo_ok": true, "failed": 0, "mission_runs": <n>, "ok": true, "pqc_bench_runs": 2, ...}
```

Se os numeros mudarem, chame o agente e peça:

```text
analise o JSON novo da bateria longa e atualize as conclusoes da apresentacao
```

## 12. Arquivos importantes

| Arquivo | Uso |
|---|---|
| `dashboard.py` | Interface visual da apresentacao |
| `firmware/esp32_serial_spike/esp32_serial_spike.ino` | Firmware da Wisdom |
| `tools/serial_console.py` | Console serial manual |
| `tools/stage8_acceptance.py` | Runner de aceite longo/manual |
| `APRESENTACAO_ROTEIRO.md` | Roteiro resumido de 20 minutos |
| `GUIA_DIDATICO_APRESENTACAO.md` | Este guia completo |
| `METRICAS_CONSOLIDADAS.md` | Como medir e apresentar CLASSIC, PQC e PQC+CRC |
| `ROADMAP.md` | Historico tecnico consolidado |
| `hardware_command_reference.md` | Comandos completos de bancada |
| `logs/20260618T183829Z_stage8_acceptance_dev-ttyusb0.json` | Evidencia principal do aceite |

## 13. Sugestao de fala completa

### Abertura

> Nosso projeto mostra um desafio atual: o mundo esta migrando para
> criptografia pos-quantica, mas hardware embarcado tem CPU, RAM e energia
> limitadas. Em um contexto inspirado em CubeSat, queremos ver quanto custa
> sair de uma mensagem classica autenticada para PQC e depois para PQC com
> checksum.

### Apresentar o experimento

> Usamos uma BlackBoard Wisdom com ESP32 como OBC educacional e um dashboard no
> notebook. Primeiro enviamos uma mensagem em tres cenarios: CLASSIC, PQC e
> PQC+CRC. Depois usamos bit-flips para mostrar a diferenca entre falha
> silenciosa e erro detectado.

### Explicar a demo

> No envio CLASSIC, a placa usa HMAC-SHA256. No envio PQC, ela executa
> ML-KEM-512 para chegar a um segredo e autenticar a mensagem. No envio
> PQC+CRC, ela adiciona CRC32 ao payload. A faixa superior mostra tempo, bytes,
> CPU e RAM para comparar o impacto.

### Conectar com PQC

> A parte pos-quantica nao e apenas decorativa: a placa executa ML-KEM-512 real.
> Quando corrompemos um ciphertext ML-KEM, a decapsulacao pode gerar outro
> segredo. O harness observa KEY_MISMATCH. Com confirmacao HMAC-SHA256, essa
> divergencia vira PROTOCOL_REJECT.

### Interpretar resultados

> No aceite anterior tivemos 77 registros, 0 falhas, 60 comandos no long-run,
> dois benchmarks PQC e demo A/B bem-sucedida. Para a apresentacao final,
> usamos o JSON novo de MISSION para preencher a comparacao CLASSIC, PQC e
> PQC+CRC. No payload, CRC32 detecta a alteracao; no ML-KEM, a confirmacao de
> chave rejeita a sessao divergente.

### Fechar com limites

> O experimento e didatico. Nao estamos medindo radiacao real, nem consumo em
> watts. A Wisdom nao e um CubeSat real. O que demonstramos e a relacao entre
> falha de bit, integridade, criptografia pos-quantica em hardware embarcado e
> confirmacao de protocolo.

## 14. Checklist para ensaio

Antes da apresentacao:

1. conectar a Wisdom;
2. conferir `/dev/ttyUSB0`;
3. abrir `python3 dashboard.py --port /dev/ttyUSB0`;
4. clicar `STATUS`;
5. clicar `CLÁSSICA`;
6. clicar `PQC`;
7. clicar `PQC+CRC`;
8. rodar `DEMO 5`;
9. explicar A/B;
10. mostrar `EXPORT_JSON`;
11. citar o JSON de aceite e o JSON novo de métricas;
12. fechar com limites.

Se algo falhar:

- se a placa nao abrir, conferir permissao da porta;
- se o dashboard estiver em modo simulado, conferir cabo e `HELLO`;
- se o projetor cortar texto, reduzir resolucao ou ajustar espelhamento;
- se um comando de bancada for necessario, usar terminal textual ou
  `tools/serial_console.py`, nao criar novo botao na demo.

## 15. Resumo de uma pagina

```text
Problema:
  Falhas transitorias podem alterar bits em sistemas embarcados.

Experimento:
  Wisdom/ESP32 + dashboard Python.

Demo:
  CLASSIC: HMAC-SHA256 -> baseline classico.
  PQC: ML-KEM-512 + HMAC -> custo pos-quantico.
  PQC+CRC: ML-KEM-512 + HMAC + CRC32 -> integridade adicional.
  A/B bit-flip: sem CRC32 -> silencioso; com CRC32 -> detectado.

PQC:
  ML-KEM-512 real na placa.
  Ciphertext corrompido -> KEY_MISMATCH.
  Confirmacao HMAC-SHA256 -> PROTOCOL_REJECT.

Resultado:
  77 registros, 0 falhas no aceite.
  13/13 DETECTED_GUARD em payload CRC32.
  PQC_KAT passou.
  Benchmarks em 240 MHz e 80 MHz medidos.
  MISSION gera JSON novo para comparar tempo, bytes e heap.

Limites:
  Nao e radiacao fisica.
  Nao mede energia real.
  Wisdom e OBC educacional, nao CubeSat real.
```
