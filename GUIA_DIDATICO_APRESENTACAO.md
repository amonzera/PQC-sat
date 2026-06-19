# Guia didático da apresentação - PQC-SAT

Este arquivo explica, passo a passo, o que está funcionando no projeto e como
apresentar isso para uma pessoa que não conhece criptografia. Ele foi escrito
para apoiar o seminário: a ideia é que alguém consiga entender a historia,
operar a demonstração, interpretar os resultados e saber o que não deve ser
afirmado.

## 1. Ideia em uma frase

O PQC-SAT mostra que, em um sistema embarcado, criptografia mais forte pode
custar mais CPU, RAM, tempo e trafego; e que esse custo aumenta quando, alem
da criptografia pós-quântica, também exigimos verificação de integridade por
checksum.

## 2. A historia da apresentação

Imagine um pequeno computador embarcado em um satélite educacional. Esse
computador recebe mensagens e também executa criptografia. Em ambiente espacial,
radiação pode causar falhas transitórias, como inverter um bit em um byte.

No nosso seminário, a demonstração principal envia uma mensagem curta pelo
"satélite" em três cenários:

1. `CLASSIC`: mensagem autenticada com HMAC-SHA256;
2. `PQC`: mensagem autenticada depois de acordo de segredo com ML-KEM-512;
3. `PQC_CRC32`: o mesmo fluxo PQC com CRC32 no payload.

Depois disso, usamos bit-flips para mostrar por que integridade importa. Não
usamos radiação física. Em vez disso, simulamos o efeito de forma controlada:

1. escolhemos um dado;
2. invertemos um bit;
3. observamos se o erro passa despercebido ou se é detectado;
4. repetimos a mesma falha com e sem mecanismo de integridade;
5. conectamos isso com o custo real de uma sessão ML-KEM-512 na placa
   ESP32/Wisdom.

A mensagem principal é simples:

- criptografia clássica simetrica é barata para o hardware;
- PQC aumenta o custo, mas prepara a comunicação para o mundo pós-quântico;
- PQC mais checksum aumenta a robustez de integridade e acrescenta custo;
- sem proteção de integridade, uma falha pode virar **falha silenciosa**;
- com CRC32 no payload, a mesma falha vira **erro detectado**;
- em ML-KEM, a decapsulacao não denuncia automaticamente todo ciphertext
  alterado; a detecção operacional vem da comparacao/confirmação da chave.

## 3. O que está funcionando agora

### Dashboard visual

Arquivo principal: `dashboard.py`.

O dashboard em Pygame está funcional e serve como tela principal da
apresentação. A apresentação não depende de slides externos: o onboarding
introduz os conceitos, o painel principal conduz a demonstração e o botão
`RESULTADOS` fecha com as métricas consolidadas. Ele mostra:

- animacao do satélite/robo;
- Terra e órbita;
- painel esquerdo com integridade, falhas e timeline;
- faixa superior com métricas essenciais;
- painel direito com botões da demonstração e terminal textual;
- modo simulado e modo hardware;
- exportacao JSON da sessão;
- painel de resultados da bateria longa real.

Por isso, os botões visuais foram reduzidos ao roteiro principal.
Hoje os botões centrais da apresentação sao `"ENVIAR MSG"`, `"CLÁSSICA"`, `"PQC"`, `"PQC+CRC"` e `"FALHA"`.

### Onboarding do dashboard

Ao abrir o dashboard sem `--no-splash`, aparece uma introdução em cinco telas.
Ela deve ser usada como abertura do seminário:

1. **O problema**: conecta hardware limitado, necessidade de segurança,
   ameaça pós-quântica e falhas de bit.
2. **Ameaça quântica**: explica por que RSA/ECDH ficam em risco com
   computadores quânticos grandes e por que PQC entra no projeto.
3. **ML-KEM**: mostra que KEM não cifra a mensagem diretamente; ele estabelece
   um segredo compartilhado que depois alimenta mecanismos como HMAC.
4. **Experimento**: apresenta os três cenários medidos (`CLASSIC`, `PQC` e
   `PQC_CRC32`) e quais métricas devem ser observadas.
5. **Como ler a demo**: apresenta os botões, a comparacao CLASSIC/PQC/PQC+CRC,
   o botão `RESULTADOS` e as métricas que devem ser observadas.

Essa introdução existe para que uma pessoa sem base de criptografia acompanhe
a narrativa sem depender de uma aula separada antes da demonstração.

### Botão RESULTADOS

O botão `RESULTADOS`, na faixa superior do dashboard, abre o resumo da bateria
real:

- fonte dos dados: `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`;
- 83 registros;
- 0 falhas no aceite;
- 27 execuções `MISSION`;
- 2 benchmarks `PQC_BENCH`;
- comparacao `CLASSIC`, `PQC` e `PQC_CRC32`;
- resultados de segurança (`PQC_KAT`, `PQC_FAULT`, demo A/B e CRC32);
- conclusões e próximos passos.

Use esse botão no final da demo ao vivo para consolidar a fala:

> O que vimos manualmente agora também foi medido em uma bateria longa antes da
> apresentação. Estes sao os números reais que sustentam a conclusão.

### Hardware Wisdom/ESP32

O equipamento usado e a RoboCore BlackBoard Wisdom com ESP32.

No projeto, ela representa um OBC COTS educacional, ou seja, um computador de
bordo didático inspirado em sistemas de CubeSat. Ela não deve ser apresentada
como um CubeSat real.

Funcionalidades validadas na placa:

- protocolo serial `V1`;
- handshake `HELLO`;
- estado `STATUS`;
- OLED standby com ícone do projeto;
- controle técnico de sensores/LEDs pelo terminal;
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

- ML-KEM é um mecanismo para duas partes chegarem a um mesmo segredo;
- esse segredo depois poderia ser usado por outras partes de um protocolo;
- se um ciphertext for alterado, a decapsulacao pode produzir outro segredo;
- por isso, o projeto testa se as duas pontas chegaram ao mesmo segredo;
- com confirmação HMAC-SHA256, uma divergência vira rejeição de protocolo.

Resultados importantes:

- `PQC_KAT`: passou;
- `PQC_FAULT 0 0x01 NONE`: retornou `KEY_MISMATCH`;
- `PQC_FAULT 0 0x01 CONFIRM`: retornou `PROTOCOL_REJECT`.

### Entrega de mensagem da missao

O comando `MISSION` é o fluxo mais importante para a apresentação final.

Ele executa uma entrega de mensagem curta no firmware e retorna métricas:

- tempo total;
- bytes transmitidos;
- heap/RAM livre;
- perfil de CPU;
- resultado da entrega;
- custo de HMAC;
- custo de ML-KEM quando o cenário usa PQC;
- custo de CRC32 quando o cenário usa checksum.

Os três comandos sao:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Leitura para explicar em sala:

- `CLASSIC` mostra o custo de proteger uma mensagem com criptografia clássica
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

Só um bit mudou. Isso parece pequeno, mas em dados, mensagens ou ciphertexts
pode mudar completamente o resultado.

No projeto, os bit-flips aparecem de duas formas:

- no dashboard, sobre um payload didático;
- no firmware, sobre ciphertext ML-KEM ou payload hexadecimal.

### Checksum CRC32

CRC32 é um detector simples de alteração em dados. Ele não é criptografia. Ele
não esconde nada. Ele apenas ajuda a perceber que os bytes mudaram.

No seminário, CRC32 é usado para demonstrar a diferença entre:

- aceitar dado corrompido sem perceber;
- detectar que o dado foi alterado.

Essa diferença é o ponto visual mais forte da demo A/B.

### Exportacao JSON

O projeto exporta JSON para que os resultados não dependam apenas da animacao.

Arquivos principais de resultado:

- `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json`;
- `logs/20260618T234008Z_sim-42.json`.

O JSON guarda:

- comandos executados;
- tempos;
- resultado de falhas;
- eventos da demo;
- status do hardware;
- informações PQC;
- comparacao `CLASSIC`, `PQC` e `PQC_CRC32`;
- resumo de sucesso/falha.

Isso permite apresentar a demo e depois mostrar que os resultados foram
registrados de forma auditavel.

## 4. Resultado final consolidado

Fonte principal:

```text
logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json
```

Esse arquivo é o aceite consolidado com os comandos `MISSION` incluidos.

Resumo do aceite final:

| Medida | Resultado |
|---|---|
| Tempo total | 1.817,23 s |
| Registros | 83 |
| Falhas no aceite | 0 |
| Comandos no long-run | 27 MISSION runs |
| Benchmarks PQC | 2 |
| Demo headless | OK |
| Payload CRC32 | 8/8 `DETECTED_GUARD` |

Resultados da demo A/B:

| Cenário | Resultado |
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
| `BASELINE` | 240 MHz | 3298 | 3861 | 4985 |
| `OBC-1U-LIMITED` | 80 MHz | 10056 | 11780 | 15204 |

Leitura simples:

- com menos CPU, o algoritmo fica mais lento;
- mesmo assim, ML-KEM-512 continuou funcionando;
- a confirmação de chave foi capaz de rejeitar uma sessão divergente;
- CRC32 detectou todos os bit-flips de payload testados no aceite.

Comparacao MISSION (BASELINE, 240 MHz):

| Cenário | `elapsed_us` (avg) | `bytes_total` | `heap` | `result` |
|---|---:|---:|---:|---|
| CLASSIC | 721 | 73 | 201.412 | DELIVERED |
| PQC | 13.536 | 841 | 201.412 | DELIVERED |
| PQC_CRC32 | 13.367 | 845 | 201.412 | DELIVERED |

Razoes observadas no BASELINE (240 MHz):

- PQC é 18,8x mais lento que CLASSIC em tempo;
- PQC transmite 11,5x mais bytes que CLASSIC;
- CRC32 adiciona ~10 us e +4 bytes sobre o fluxo PQC.

## 5. Fundamentos de criptografia para quem nunca viu

Esta seção foi escrita para quem nunca estudou criptografia. Ela explica, do
zero, cada conceito que aparece no projeto. Se você já conhece o assunto, pode
pular direto para a seção 6.

### 5.1 Criptografia simetrica vs. assimetrica

**O que é uma chave?**

Uma chave criptográfica e como uma senha que tranca e destranca dados. Sem a
chave correta, os dados ficam ilegíveis.

**Criptografia simetrica** -- a mesma chave dos dois lados.

Analogia: imagine uma caixa com um cadeado. O remetente e o destinatario tem
copias da mesma chave. O remetente tranca a caixa, envia, e o destinatario
abre com sua copia.

```text
  Remetente                      Destinatario
     |                               |
     |--- [caixa trancada] --------> |
     |    mesma chave K              |
     |    tranca com K               abre com K
```

Problema: como entregar a primeira copia da chave com segurança?

**Criptografia assimetrica** -- chave publica + chave privada.

Analogia: pense em uma caixa de correio. Qualquer pessoa pode colocar uma
carta pela abertura (chave publica), mas só o dono tem a chave para abrir a
caixa (chave privada).

```text
  Qualquer pessoa                Dono da caixa
     |                               |
     |--- carta pela abertura -----> |
     |    chave publica (aberta)     chave privada (secreta)
     |    qualquer um pode enviar    so o dono pode ler
```

**No nosso projeto:**

- HMAC-SHA256 usa uma chave **simetrica** (as duas pontas compartilham o
  mesmo segredo);
- ML-KEM gera pares **assimetricos** (chave publica + chave privada).

### 5.2 Por que a criptografia atual está ameaçada

Os algoritmos clássicos mais usados (RSA e ECDH) dependem de problemas
matematicos que sao muito difíceis para computadores normais:

- **RSA**: fatorar números enormes (ex.: encontrar os dois primos que, quando
  multiplicados, dao um número de 2048 bits);
- **ECDH**: o problema do logaritmo discreto em curvas elípticas.

Em 1994, Peter Shor publicou um **algoritmo quântico** que consegue fatorar
números exponencialmente mais rápido. Um computador quântico suficientemente
poderoso poderia quebrar RSA e ECDH em horas, em vez de bilhoes de anos.

Isso é chamado de **ameaça quântica**. Ela ainda não existe em escala
prática, mas o risco e real por causa da estratégia "harvest now, decrypt
later" -- um adversario pode capturar dados cifrados hoje e descriptografa-los
no futuro, quando tiver um computador quântico.

Por isso existe a **criptografia pós-quântica (PQC)**: algoritmos projetados
para resistir tanto a computadores clássicos quanto a quânticos.

### 5.3 O que é um KEM (Mecanismo de Encapsulamento de Chave)

Um KEM **não é cifra**. Ele não serve para esconder uma mensagem diretamente.
Ele serve para duas partes combinarem um segredo compartilhado de forma
segura.

Passo a passo:

```text
  Alice                              Bob
    |                                  |
    |--- keygen() --->  pk (publica)   |
    |                   sk (privada)   |
    |                                  |
    |       pk          encap(pk) ---> |
    |                   ct + ss_bob    |
    |                                  |
    |  <--- ct -------- ct             |
    |  decap(sk, ct)                   |
    |  ss_alice                        |
    |                                  |
    |  ss_alice == ss_bob  (segredo!)  |
```

Legenda:

- `pk` = chave publica (pode ser enviada abertamente);
- `sk` = chave privada (nunca sai da posse de Alice);
- `ct` = ciphertext (dado criptográfico que carrega o segredo encapsulado);
- `ss` = shared secret (segredo compartilhado que as duas pontas derivam).

Depois desse processo, Alice e Bob possuem o mesmo segredo (`ss`), que pode
ser usado para criptografia simetrica ou autenticação.

**No nosso projeto:** o ESP32 faz os dois papeis (Alice e Bob) no mesmo chip
para medir o custo computacional de cada etapa.

### 5.4 Por que reticulados resistem a computadores quânticos

ML-KEM e baseado no problema **Learning With Errors (LWE)** sobre
reticulados (lattices).

Intuicao: imagine uma grade (grid) em muitas dimensoes. Encontrar o vetor
mais curto nessa grade e extremamente difícil, mesmo para computadores
quânticos.

```text
  2D (facil de visualizar)        nD (impossivel de resolver por forca bruta)

    *   *   *   *   *              *  *  *  *  *  *  *  *  *  *  *
    *   *   *   *   *              *  *  *  *  *  *  *  *  *  *  *
    *   *   *   *   *              *  *  *  *  *  *  *  *  *  *  *
    *   *   *   *   *              (centenas de dimensoes...)
```

Nenhum algoritmo quântico conhecido oferece vantagem significativa para
problemas de reticulados (diferente do algoritmo de Shor para fatoração).

Por isso, o NIST escolheu ML-KEM como padrao para troca de chaves
pós-quântica.

### 5.5 O que o HMAC-SHA256 faz por dentro

**SHA-256** e uma função hash: recebe qualquer dado e produz uma
"impressao digital" fixa de 256 bits. Se você mudar 1 bit da entrada,
a saída muda completamente.

```text
  "Hello"   --SHA256-->  185f8db3...
  "Hello!"  --SHA256-->  334d016f...   (completamente diferente)
```

**HMAC** combina uma chave secreta com SHA-256. Somente quem possui a chave
correta consegue produzir a etiqueta (tag) correta.

Formula simplificada:

```text
  HMAC(key, msg) = SHA256(key XOR opad || SHA256(key XOR ipad || msg))
```

Analogia: e como assinar uma carta com um carimbo secreto. Qualquer pessoa
pode ler a carta, mas somente quem tem o carimbo consegue forjar a assinatura.

**No nosso projeto:** HMAC-SHA256 é usado para:

- autenticar a mensagem da missao;
- confirmar que as duas pontas derivaram o mesmo segredo ML-KEM.

### 5.6 O que o CRC32 faz por dentro

CRC = Cyclic Redundancy Check (Verificação de Redundancia Ciclica).

O CRC32 trata os dados como um polinomio e divide por um polinomio fixo
(`0xEDB88320`). O resto dessa divisao e o valor CRC32 (4 bytes).

```text
  dados originais  --divisao polinomial-->  resto = CRC32 (4 bytes)

  Se QUALQUER bit mudar --> o resto muda --> corrupcao detectada
```

**Importante: CRC32 NÃO e criptografia.**

- Ele **não esconde** dados;
- Ele **não autentica** (não usa chave secreta);
- Ele **só detecta alterações acidentais**.

Um atacante pode modificar os dados E recalcular o CRC32 para que bata.
Para segurança contra atacantes, use HMAC.

**No nosso projeto:** CRC32 demonstra detecção de integridade com custo
minimo (~10 microssegundos, +4 bytes).

### 5.7 NIST e FIPS 203

- **NIST** = National Institute of Standards and Technology (EUA);
- Em 2016, o NIST abriu uma competicao publica para encontrar algoritmos
  pós-quânticos;
- Em 2024, o NIST publicou **FIPS 203** -- o padrao oficial para ML-KEM
  (Module Lattice Key Encapsulation Mechanism);
- **ML-KEM-512** e a variante mais leve (nível de segurança 1, equivalente
  a AES-128).

Nosso projeto usa ML-KEM-512 porque ele tem as menores chaves e o menor
custo computacional -- ideal para hardware limitado.

Tamanhos de chave:

| Elemento | Tamanho |
|---|---:|
| Chave publica (`pk`) | 800 bytes |
| Chave privada (`sk`) | 1.632 bytes |
| Ciphertext (`ct`) | 768 bytes |
| Segredo compartilhado (`ss`) | 32 bytes |

### 5.8 O que acontece dentro do ESP32 quando enviamos MISSION PQC_CRC32

Quando o dashboard envia `MISSION PQC_CRC32`, o firmware executa estas
etapas em sequência:

1. **keygen**: gera par de chaves ML-KEM-512 (~3.679 us)
2. **encap**: encapsula um segredo usando a chave publica (~3.988 us)
3. **decap**: decapsula o ciphertext com a chave privada (~5.087 us)
4. **Compara**: verifica se `ss_alice == ss_bob` (`key_match`)
5. **HMAC tag**: calcula tag de autenticação sobre a mensagem usando o
   segredo derivado (~435 us)
6. **HMAC verify**: recalcula e compara a tag (~163 us)
7. **CRC32 TX**: calcula CRC32 do payload (~5 us)
8. **CRC32 RX**: recalcula CRC32 e compara (~5 us)
9. **Total**: ~13.367 us para completar a entrega da mensagem

```text
  Fluxo no firmware (PQC_CRC32):

  keygen -----> encap -----> decap -----> compara ss
  (3.679 us)    (3.988 us)   (5.087 us)
                                           |
                                           v
                                     HMAC tag (435 us)
                                           |
                                           v
                                     HMAC verify (163 us)
                                           |
                                           v
                                     CRC32 TX (5 us)
                                           |
                                           v
                                     CRC32 RX (5 us)
                                           |
                                           v
                                     DELIVERED (~13.367 us total)
```

### 5.9 Tabela comparativa: criptografia clássica vs PQC

| Aspecto | Clássica (HMAC-SHA256) | PQC (ML-KEM-512 + HMAC) |
|---|---|---|
| O que faz | Autentica mensagem | Estabelece segredo + autentica |
| Tipo de chave | Simetrica fixa | Assimetrica gerada por sessão |
| Tamanho de chave | 32 bytes | pk=800, sk=1.632 bytes |
| Bytes transmitidos | 73 | 841 |
| Tempo (240 MHz) | ~721 us | ~13.536 us |
| Tempo (80 MHz) | ~1.283 us | ~38.646 us |
| Resiste a quântico | Sim (chave simetrica) | Sim (reticulados) |
| Custo de adicionar CRC32 | N/A | +10 us, +4 bytes |

## 6. Como explicar os termos para uma pessoa leiga

### O que é um payload?

Payload e a mensagem/dado que está sendo enviado. No nosso caso, é uma mensagem
curta usada para mostrar o efeito de uma alteração de bit.

### O que é uma falha silenciosa?

E quando o dado mudou, mas o sistema aceitou como se estivesse tudo certo.

No seminário:

```text
SILENT = o erro passou despercebido
```

### O que é um erro detectado?

E quando o sistema percebe que algo mudou e não trata o dado como normal.

No seminário:

```text
DETECTED_GUARD = o CRC32 percebeu a alteracao
```

### O que é ML-KEM?

ML-KEM é um mecanismo de encapsulamento de chave padronizado pelo NIST. Ele é
parte da criptografia pós-quântica.

Explicacao curta para a fala:

> ML-KEM não é uma cifra para esconder diretamente uma mensagem. Ele serve para
> duas partes chegarem a um segredo compartilhado que depois pode proteger uma
> comunicação.

### O que significa pós-quântica?

Criptografia pós-quântica e a familia de algoritmos projetada para resistir a
ataques futuros com computadores quânticos grandes o suficiente para quebrar
alguns esquemas clássicos.

Para o seminário, não precisamos provar resistência quântica. O ponto e mostrar
que um algoritmo moderno também precisa ser integrado com cuidado em hardware
limitado e sujeito a falhas.

### O que é um ciphertext?

E um dado criptográfico produzido por uma etapa do protocolo. No ML-KEM, o
ciphertext e entregue para a outra ponta decapsular e chegar ao segredo.

### O que é `KEY_MISMATCH`?

Significa que o harness de teste observou que os segredos das duas pontas não
bateram.

Fala sugerida:

> Aqui não estamos dizendo que a decapsulacao gritou "erro". Estamos dizendo
> que, ao comparar os resultados no experimento, vimos que as duas pontas
> chegaram a segredos diferentes.

### O que é `PROTOCOL_REJECT`?

Significa que uma confirmação autenticada da chave falhou.

Fala sugerida:

> Quando adicionamos uma confirmação baseada na chave derivada, a divergência
> deixa de ser só uma observação do laboratorio e vira uma rejeição operacional
> da sessão.

### O que é HMAC-SHA256?

é um mecanismo para calcular uma etiqueta de autenticação usando uma chave.
Aqui, ele serve para confirmar se as duas pontas realmente chegaram ao mesmo
segredo.

## 7. O que aparece na tela

### Centro da tela

Mostra a animacao do satélite e a Terra. Quando a Wisdom está conectada, a
órbita fica ativa. A ideia visual e lembrar o contexto de sistemas embarcados
inspirados em CubeSat.

### Faixa superior

Mostra apenas métricas essenciais de hardware da maquina/satélite:

- CPU (MHz e % de carga ativo em tempo real);
- RAM (consumo atual de heap / total disponivel, e memória livre de detalhe).

Essa faixa não polui a tela com resultados e foca puramente nos recursos físicos do sistema.

### Painel esquerdo

Mostra a parte experimental:

- status da sessão;
- algoritmo/estado PQC;
- guardiao ativo;
- quantidade de injecoes de falha;
- falhas silenciosas;
- erros detectados;
- barra de integridade;
- timeline dos eventos.

### Painel direito

Tem botões somente para o roteiro visual didático manual:

- `"ENVIAR MSG"`;
- `"CLÁSSICA"`;
- `"PQC"`;
- `"PQC+CRC"`;
- `"FALHA"`.

O terminal textual continua existindo abaixo dos botões. Ele aceita comandos
avançados, mas esses comandos não devem virar parte principal da apresentação.

## 8. Sequência recomendada para apresentar

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

### Abrir a demonstração

Com a placa conectada:

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

Sem placa, apenas para ensaio visual:

```bash
python3 dashboard.py --simulated
```

Esse modo não deve ser usado para a demonstração principal. Ele serve para
layout e treinamento de fala; métricas de mensagem só devem aparecer quando a
Wisdom estiver conectada e responder aos comandos `MISSION`.

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

> Antes de enviar mensagens, confirmamos que a placa está viva, qual perfil de
> CPU está ativo e quanta memória ainda está livre.

### Passo 2: enviar mensagens nos três cenários

Clique, nesta ordem:

```text
CLÁSSICA
ENVIAR MSG
PQC
ENVIAR MSG
PQC+CRC
ENVIAR MSG
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
4. o console e o overlay de mensagem entregue mostram tempo e bytes;
5. cada cenário abre um popup próprio; arraste os cartões pelo topo e mantenha `CLASSIC`, `PQC` e `PQC+CRC` lado a lado até clicar no `X`, permitindo comparar tempo, bytes, heap, keygen, encap, decap, HMAC e CRC;
6. LEDs/bargraph reforcam visualmente o aumento de custo.

Como explicar:

> A mensagem enviada é pequena. Mesmo assim, quando trocamos o baseline
> clássico por PQC, o custo cresce. Quando adicionamos checksum ao fluxo PQC,
> ganhamos mais integridade observavel e também somamos mais trabalho ao
> hardware.

### Passo 3: demonstrar falha transitória (Bit-Flip) manualmente

Para demonstrar a diferença prática entre corrupção silenciosa e erro detectado sem automatização no dashboard:

1. **Caso A (Corrupção Silenciosa):**
   - Clique no preset `"PQC"` para usar o fluxo sem CRC32 no payload.
   - Clique em `"FALHA"` para injetar uma falha de bit no payload.
   - Observe na timeline a esquerda que o status registrado será `SILENT`, simulando o satélite recebendo dados invalidos sem saber.

2. **Caso B (Erro Detectado):**
   - Clique no preset `"PQC+CRC"` para usar o fluxo com CRC32 no payload.
   - Clique em `"FALHA"` para injetar uma falha de bit.
   - Observe na timeline a esquerda que o status registrado será `DETECTED_GUARD`, mostrando que o satélite interceptou a corrupção e descartou o pacote corrompido.

Como explicar:

> A comparacao é justa porque a falha atinge o mesmo ponto no pacote. A única diferença e a presenca ou ausencia do guardiao de integridade. Sem ele, a alteração de bits gera corrupção silenciosa; com ele, garantimos que dados invalidos não afetem a operação do CubeSat.

> [!NOTE]
> Os logs oficiais e dados numericos consolidados de longo prazo do projeto foram gerados anteriormente usando ferramentas automatizadas via terminal (como o script `tools/stage8_acceptance.py`). O dashboard visual é reservado unicamente para demonstração e manipulacao didática ao vivo de forma interativa e manual.

## 9. Comandos que funcionam, mas não devem ser foco visual

Esses comandos existem e sao úteis, mas devem ficar no terminal/HELP ou no
`tools/serial_console.py`:

| Comando | Por que não fica nos botões |
|---|---|
| `PING` | Bom para diagnóstico, mas pouco didático na tela principal |
| `TELEMETRY` | Pode poluir a serial e a apresentação se enviado o tempo todo |
| `RUN_BATTERY` | E coleta local, não narrativa principal |
| `PQC_KAT` | Importante para bancada, mas técnico demais para o fluxo visual |
| `PQC_BENCH` | Gera dados, mas não é a demo principal |
| `PQC_FAULT` | Essencial para explicar resultado, mas melhor mostrar como tabela |
| `LED`, `RGB`, `BARGRAPH` | Efeito visual de hardware; no dashboard eles sao acionados indiretamente por `MISSION` |
| sensores | Extras da placa, fora do argumento principal |

Isso evita que a apresentação vire uma lista de comandos e mantém o foco:

```text
mensagem -> custo -> PQC real -> checksum -> falha/deteccao -> limites
```

## 10. Como explicar os resultados finais

### Resultado 1: CLASSIC, PQC e PQC+CRC têm custos diferentes

Use a frase:

> A mesma mensagem de missao pode ser entregue com criptografia clássica,
> com PQC, ou com PQC mais checksum. O que muda e o custo observado no
> hardware: tempo, bytes e memória.

Base:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Use o botão `RESULTADOS` e o arquivo
`logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json` para mostrar a
tabela final de `elapsed_us`, `bytes_total` e `heap`.

### Resultado 2: CRC32 detectou o payload alterado

Use a frase:

> Quando protegemos o payload com CRC32, a mesma alteração de bit deixou de
> passar silenciosamente e virou um erro detectado.

Base:

```text
8/8 DETECTED_GUARD no aceite final
```

### Resultado 3: ML-KEM funcionou na Wisdom

Use a frase:

> A placa não está apenas simulando PQC. Ela executa ML-KEM-512 real pelo
> backend mlkem-native.

Base:

```text
PQC_KAT = kat=pass
pk=800, sk=1632, ct=768, ss=32
```

### Resultado 4: bit-flip em ciphertext causa divergência

Use a frase:

> Ao corromper um ciphertext ML-KEM, as pontas podem chegar a segredos
> diferentes. Isso aparece como KEY_MISMATCH no harness.

Base:

```text
PQC_FAULT NONE -> KEY_MISMATCH
```

### Resultado 5: confirmação transforma divergência em rejeição

Use a frase:

> Com uma confirmação HMAC-SHA256, a divergência da chave passa a ser rejeitada
> pelo protocolo.

Base:

```text
PQC_FAULT CONFIRM -> PROTOCOL_REJECT
```

### Resultado 6: limitar CPU aumenta custo, mas não quebra a demo

Use a tabela:

| Perfil | Keygen | Encap | Decap |
|---|---:|---:|---:|
| 240 MHz | 3298 us | 3861 us | 4985 us |
| 80 MHz | 10056 us | 11780 us | 15204 us |

Use a frase:

> O perfil limitado deixa o algoritmo mais lento, mas a operação continua
> funcional. Isso ajuda a discutir custo computacional em hardware embarcado.

## 11. O que não afirmar

Não diga:

- "provamos que isso funciona em um CubeSat real";
- "medimos consumo em watts";
- "CRC32 resolve segurança";
- "ML-KEM detecta sozinho qualquer ciphertext corrompido";
- "ML-KEM cifra diretamente a mensagem";
- "HMAC-SHA256 e equivalente a ECDH";
- "o experimento prova resistência a radiação real";
- "o ESP32 representa todos os OBCs de CubeSat";
- "checksum de ciphertext e a contribuicao principal".

Diga:

- "a Wisdom representa um OBC COTS educacional";
- "simulamos bit-flips manualmente";
- "CLASSIC e um baseline simetrico de mensagem autenticada";
- "PQC usa ML-KEM para estabelecer segredo antes de autenticar a mensagem";
- "CRC32 mostra detecção de integridade no payload";
- "ML-KEM-512 foi executado na placa";
- "a confirmação de chave é o ponto de detecção operacional";
- "energia real exigiria medidor externo";
- "o objetivo é didático e reproduzível".

## 12. Bateria longa de hardware

Regra atual do projeto:

> Baterias longas não devem ser iniciadas pelo agente. O operador roda no
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

Se os números mudarem, chame o agente e peça:

```text
analise o JSON novo da bateria longa e atualize as conclusoes da apresentacao
```

## 13. Arquivos importantes

| Arquivo | Uso |
|---|---|
| `dashboard.py` | Interface visual da apresentação |
| `firmware/esp32_serial_spike/esp32_serial_spike.ino` | Firmware da Wisdom |
| `tools/serial_console.py` | Console serial manual |
| `tools/stage8_acceptance.py` | Runner de aceite longo/manual |
| `APRESENTACAO_ROTEIRO.md` | Roteiro resumido de 20 minutos |
| `GUIA_DIDATICO_APRESENTACAO.md` | Este guia completo |
| `METRICAS_CONSOLIDADAS.md` | Como medir e apresentar CLASSIC, PQC e PQC+CRC |
| `ROADMAP.md` | Histórico técnico consolidado |
| `hardware_command_reference.md` | Comandos completos de bancada |
| `logs/20260618T234008Z_stage8_acceptance_dev-ttyusb0.json` | Evidencia principal do aceite |

## 14. Sugestao de fala completa

### Abertura

> Nosso projeto mostra um desafio atual: o mundo está migrando para
> criptografia pós-quântica, mas hardware embarcado tem CPU, RAM e energia
> limitadas. Em um contexto inspirado em CubeSat, queremos ver quanto custa
> sair de uma mensagem clássica autenticada para PQC e depois para PQC com
> checksum.

### Apresentar o experimento

> Usamos uma BlackBoard Wisdom com ESP32 como OBC educacional e um dashboard no
> notebook. Primeiro enviamos uma mensagem em três cenários: CLASSIC, PQC e
> PQC+CRC. Depois usamos bit-flips para mostrar a diferença entre falha
> silenciosa e erro detectado.

### Explicar a demo

> No envio CLASSIC, a placa usa HMAC-SHA256. No envio PQC, ela executa
> ML-KEM-512 para chegar a um segredo e autenticar a mensagem. No envio
> PQC+CRC, ela adiciona CRC32 ao payload. O console do dashboard mostra o
> tempo e os bytes de custo individual de cada mensagem enviada, enquanto a
> faixa superior mostra CPU e RAM para comparar o impacto de recursos.

### Conectar com PQC

> A parte pós-quântica não é apenas decorativa: a placa executa ML-KEM-512 real.
> Quando corrompemos um ciphertext ML-KEM, a decapsulacao pode gerar outro
> segredo. O harness observa KEY_MISMATCH. Com confirmação HMAC-SHA256, essa
> divergência vira PROTOCOL_REJECT.

### Interpretar resultados

> No aceite final tivemos 83 registros, 0 falhas, 27 MISSION runs, dois
> benchmarks PQC e demo A/B bem-sucedida. CLASSIC entrega em 721 us com 73
> bytes; PQC custa 13.536 us com 841 bytes; PQC+CRC custa 13.367 us com 845
> bytes. PQC é 18,8x mais lento, mas prepara o sistema para o mundo
> pós-quântico. No payload, CRC32 detecta a alteração (8/8 DETECTED_GUARD);
> no ML-KEM, a confirmação de chave rejeita a sessão divergente.

### Fechar com limites

> O experimento é didático. Não estamos medindo radiação real, nem consumo em
> watts. A Wisdom não é um CubeSat real. O que demonstramos e a relação entre
> falha de bit, integridade, criptografia pós-quântica em hardware embarcado e
> confirmação de protocolo.

## 15. Checklist para ensaio

Antes da apresentação:

1. conectar a Wisdom;
2. conferir `/dev/ttyUSB0`;
3. abrir `python3 dashboard.py --port /dev/ttyUSB0`;
4. clicar em `CLÁSSICA` (botão azul) e depois `ENVIAR MSG` para mostrar o tempo clássico;
5. clicar em `PQC` (botão roxo) e depois `ENVIAR MSG` para mostrar o tempo PQC;
6. clicar em `PQC+CRC` (botão verde) e depois `ENVIAR MSG` para mostrar o tempo PQC+Checksum;
7. clicar em `PQC` e depois em `FALHA` para demonstrar erro silencioso (`SILENT`);
8. clicar em `PQC+CRC` e depois em `FALHA` para demonstrar erro detectado (`DETECTED_GUARD`);
9. citar o JSON de aceite de bateria de testes de longa duração;
10. fechar com limites.

Se algo falhar:

- se a placa não abrir, conferir permissão da porta;
- se o dashboard estiver em modo simulado, conferir cabo e `HELLO`;
- se o projetor cortar texto, reduzir resolução ou ajustar espelhamento;
- se um comando de bancada for necessario, usar terminal textual ou
  `tools/serial_console.py`, não criar novo botão na demo.

## 16. Resumo de uma página

```text
Problema:
  Falhas transitorias podem alterar bits em sistemas embarcados.

Experimento:
  Wisdom/ESP32 + dashboard Python.

Demo:
  CLASSIC: HMAC-SHA256 -> baseline classico (721 us, 73 bytes).
  PQC: ML-KEM-512 + HMAC -> custo pos-quantico (13.536 us, 841 bytes).
  PQC+CRC: ML-KEM + HMAC + CRC32 -> integridade adicional (13.367 us, 845 bytes).
  A/B bit-flip: sem CRC32 -> silencioso; com CRC32 -> detectado.
  PQC e 18,8x mais lento e 11,5x mais pesado que CLASSIC.

PQC:
  ML-KEM-512 real na placa.
  Ciphertext corrompido -> KEY_MISMATCH.
  Confirmacao HMAC-SHA256 -> PROTOCOL_REJECT.

Resultado:
  83 registros, 0 falhas no aceite.
  8/8 DETECTED_GUARD em payload CRC32.
  PQC_KAT passou.
  Benchmarks em 240 MHz e 80 MHz medidos.
  CLASSIC=721 us / PQC=13.536 us / PQC_CRC32=13.367 us.

Limites:
  Nao e radiacao fisica.
  Nao mede energia real.
  Wisdom e OBC educacional, nao CubeSat real.
```
