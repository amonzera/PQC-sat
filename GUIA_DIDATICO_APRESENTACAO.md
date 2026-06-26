# Guia didático da apresentação - PQC-SAT

Este arquivo explica, passo a passo, o que está funcionando no projeto e como
apresentar isso para uma pessoa que não conhece criptografia. Ele foi escrito
para apoiar o seminário: a ideia é que alguém consiga entender a historia,
operar a demonstração, interpretar os resultados e saber o que não deve ser
afirmado.

## 1. Ideia em uma frase

O PQC-SAT mostra que, em um sistema embarcado, mecanismos criptográficos mais
modernos e custosos podem exigir mais CPU, RAM, tempo e trafego; e que esse
custo aumenta quando, alem da criptografia pós-quântica, também exigimos
verificação de integridade por checksum.

## 2. A historia da apresentação

Imagine um pequeno computador embarcado em um satélite educacional. Esse
computador recebe mensagens e também executa criptografia. Em ambiente espacial,
radiação pode causar falhas transitórias, como inverter um bit em um byte.

No nosso seminário, a demonstração principal envia uma mensagem curta pelo
"satélite" em três cenários:

1. `CLASSIC`: mensagem cifrada/autenticada com AES-128-GCM e chave efêmera;
2. `PQC`: ML-KEM-512 estabelece a chave, AES-GCM cifra a mensagem;
3. `PQC_CRC32`: o mesmo fluxo PQC com CRC32 protegido no payload cifrado.

Depois disso, usamos bit-flips para mostrar por que integridade importa. Não
usamos radiação física. Em vez disso, simulamos o efeito de forma controlada:

1. escolhemos um dado;
2. invertemos um bit;
3. observamos se o erro passa despercebido ou se é detectado;
4. repetimos a mesma falha com e sem mecanismo de integridade;
5. conectamos isso com o custo real de uma sessão ML-KEM-512 na placa
   ESP32/Wisdom.

A mensagem principal é simples:

- criptografia clássica simetrica com AES-GCM é barata para o hardware;
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

### Modo Satélite Vivo

O dashboard agora tem um toggle discreto chamado `Payload vivo`, ligado por
padrão. Esse modo torna a apresentação mais fiel à ideia de um computador de
bordo:

1. o dashboard pede leituras reais à Wisdom;
2. a placa responde com sensores e entradas físicas;
3. o dashboard monta um payload curto com esses valores;
4. esse payload é convertido para hexadecimal;
5. o comando enviado vira `MISSION CLASSIC|PQC|PQC_CRC32 payload_hex`;
6. o firmware mede o custo criptográfico sobre esse payload real.

O payload fica parecido com:

```text
PQC-SAT|S=42|T=2450|H=5530|X=12|Y=-34|Z=1001|L=321|P=2048|B=0|OK
```

Como ler esse exemplo:

- `S`: número de sequência do envio;
- `T` e `H`: temperatura e umidade em escala inteira;
- `X`, `Y`, `Z`: aceleração nos três eixos;
- `L`: leitura de luz/proximidade;
- `P`: potenciômetro;
- `B`: botão;
- `OK`: marcador de status.

Se algum sensor não responder, a demo não trava. O campo aparece como `NA` e o
popup marca o payload como parcial. Isso é intencional: em sistemas embarcados,
um sensor pode falhar sem impedir que o computador de bordo continue operando
de forma degradada.

Esse modo é importante para a fala do seminário:

> Agora a placa não só responde a comandos. Ela mede o ambiente, monta a
> telemetria da missão e executa a criptografia sobre dados criados naquele
> instante.

### Onboarding do dashboard

Ao abrir o dashboard sem `--no-splash`, aparece uma introdução em cinco telas.
Ela deve ser usada como abertura do seminário:

1. **O problema**: conecta hardware limitado, necessidade de segurança,
   ameaça pós-quântica e falhas de bit.
2. **Ameaça quântica**: explica por que RSA/ECDH ficam em risco com
   computadores quânticos grandes e por que PQC entra no projeto.
3. **ML-KEM**: mostra que KEM não cifra a mensagem diretamente; ele estabelece
   um segredo compartilhado que depois deriva a chave de uma cifra autenticada
   como AES-GCM.
4. **Experimento**: apresenta os três cenários medidos (`CLASSIC`, `PQC` e
   `PQC_CRC32`) e quais métricas devem ser observadas.
5. **Como ler a demo**: apresenta os botões, a comparacao CLASSIC/PQC/PQC+CRC,
   o botão `RESULTADOS` e as métricas que devem ser observadas.

Essa introdução existe para que uma pessoa sem base de criptografia acompanhe
a narrativa sem depender de uma aula separada antes da demonstração.

### Botão RESULTADOS

O botão `RESULTADOS`, na faixa superior do dashboard, abre o resumo da bateria
real:

- fonte dos dados: `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`;
- 3.074 registros;
- 0 falhas no aceite;
- 1.800 execuções `MISSION`;
- 10 benchmarks `PQC_BENCH`;
- comparacao `CLASSIC`, `PQC` e `PQC_CRC32`;
- resultados de segurança (`PQC_KAT`, `MISSION`, `FAULT NONE` e `FAULT CRC32`);
- conclusões e próximos passos.
- fechamento opcional `STRESS PQC 500`, que repete ML-KEM 500 vezes para
  mostrar carga extrema controlada.

Use esse botão no final da demo ao vivo para consolidar a fala:

> O que vimos manualmente agora também foi medido em uma bateria longa antes da
> apresentação. Estes sao os números reais que sustentam a conclusão.

Se houver tempo, use o botão `STRESS PQC 500` dentro de `RESULTADOS`:

1. clique uma vez para armar;
2. explique que será uma carga agressiva, não um benchmark oficial;
3. clique novamente para confirmar;
4. observe o cronômetro e o aviso de espera longa;
5. leia o resumo final de rounds, tempo total, médias ML-KEM e heap mínimo.

Fala curta:

> Agora não estamos enviando uma mensagem; estamos repetindo o acordo
> pós-quântico 500 vezes. A ideia é mostrar o limite prático aparecendo no
> tempo de resposta do hardware.

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
- `PQC_FAULT` como comando técnico de bancada, fora da demo visual;
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
- na demonstração principal, esse segredo alimenta AES-GCM, que cifra e
  autentica o payload;
- a falha visual da apresentação não corrompe o ciphertext ML-KEM: ela corrompe
  payload para comparar `NONE` contra `CRC32`.

Resultados importantes:

- `PQC_KAT`: passou;
- `MISSION PQC`: ML-KEM + AES-GCM entregou mensagem;
- `MISSION PQC_CRC32`: ML-KEM + AES-GCM + CRC32 entregou mensagem com checksum
  protegido.

### Entrega de mensagem da missao

O comando `MISSION` é o fluxo mais importante para a apresentação final.

Ele executa uma entrega de mensagem curta no firmware e retorna métricas:

- tempo total;
- bytes transmitidos;
- heap/RAM livre;
- perfil de CPU;
- resultado da entrega;
- custo de AES-GCM;
- custo de KDF quando o cenário usa ML-KEM;
- custo de ML-KEM quando o cenário usa PQC;
- custo de CRC32 quando o cenário usa checksum.

Os três comandos sao:

```text
MISSION CLASSIC
MISSION PQC
MISSION PQC_CRC32
```

Na apresentação, o dashboard normalmente envia a versão com payload vivo:

```text
MISSION PQC_CRC32 5051432D5341547C533D...
```

Esse hexadecimal é apenas a forma serial dos bytes do payload. O popup traduz
a ideia visualmente mostrando `PAYLOAD REAL DA PLACA`, os sensores usados, o
tamanho do payload e depois as etapas de cifra e verificação.

#### Formato da animação de missão e falha

Cada etapa do popup usa um diagrama limpo de três blocos:

```
[ ENTRADA ]  →  [ OPERAÇÃO ]  →  [ SAÍDA ]
```

Os blocos mostram título curto, detalhe técnico e, abaixo do diagrama, duas
linhas de teoria. Facilitadores visuais discretos complementam a leitura:

- **ícones line-art** no bloco de operação: escudo (CRC32/verificação), cadeado
  fechado (cifra AES-GCM ou encapsulamento ML-KEM), cadeado aberto (decaps),
  chave (keygen/KDF), `#` (hash SHA-256), antena (sensor/RNG), satélite (downlink);
- **selos de resultado** no bloco de saída: `✓` verde quando a operação
  protege ou confirma algo, `✗` vermelho quando uma falha passa ou é detectada;
- **partículas de dados** fluindo pelas setas nos passos de payload e coleta;
- **raio cósmico** no passo de bit-flip: emissora pulsante, raio irregular e
  faísca no bit exato invertido.

Nas falhas, o popup mostra `PAYLOAD → BIT-FLIP → GUARDIÃO → VERIFICAÇÃO →
RESULTADO` com byte antes/depois, CRC antes/depois e a diferença entre
`SILENT` e `DETECTED_GUARD`.

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

Com a camada de satélite vivo, o botão `FALHA` usa o potenciômetro da Wisdom
como seletor didático:

1. o apresentador gira o potenciômetro;
2. o dashboard lê `ANALOG POT`;
3. o valor de 0 a 4095 é mapeado para uma posição de bit dentro do payload;
4. o bit é invertido;
5. a janela mostra `pot -> byte/mask -> payload alterado -> resultado`.

Isso não é radiação física. É uma forma controlada, visível e repetível de
mostrar o efeito de uma falha transitória em um computador embarcado.

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

- `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json`;
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
logs/20260625T005330Z_final_metrics_dev-ttyusb0.json
```

Esse arquivo é a coleta final consolidada com os comandos `MISSION`,
`PQC_BENCH` e `FAULT` incluidos.

Resumo do aceite final:

| Medida | Resultado |
|---|---|
| Tempo total | 1.681,24 s |
| Registros | 3.074 |
| Falhas no aceite | 0 |
| Comandos no long-run | 1.800 MISSION runs |
| Benchmarks PQC | 10 |
| Falhas sem CRC32 | 600/600 `SILENT` |
| Payload CRC32 | 600/600 `DETECTED_GUARD` |

Resultados de falha de payload:

| Cenário | Resultado |
|---|---|
| Sem CRC32 | 600/600 falhas silenciosas |
| Com CRC32 | 600/600 falhas detectadas |

Resultados PQC:

| Teste | Resultado |
|---|---|
| `PQC_KAT` | `kat=pass`, `ss_crc32=0xD9DA8D6C` |
| `MISSION PQC` | ML-KEM-512 estabelece segredo e AES-GCM cifra/autentica a mensagem |
| `MISSION PQC_CRC32` | CRC32 entra no plaintext protegido antes da cifragem |

Benchmark ML-KEM-512:

| Perfil | CPU | `keygen_avg_us` | `encap_avg_us` | `decap_avg_us` |
|---|---:|---:|---:|---:|
| `BASELINE` | 240 MHz | 3302 | 3866 | 4990 |
| `OBC-1U-LIMITED` | 80 MHz | 10066 | 11787 | 15217 |

Leitura simples:

- com menos CPU, o algoritmo fica mais lento;
- mesmo assim, ML-KEM-512 continuou funcionando;
- CRC32 detectou todos os bit-flips de payload testados no aceite.

Comparacao MISSION (BASELINE, 240 MHz):

| Cenário | `elapsed_us` (avg) | `bytes_total` | `heap` | `result` |
|---|---:|---:|---:|---|
| CLASSIC | 511 | 73 | 201.412 | DELIVERED |
| PQC | 13.234 | 841 | 201.412 | DELIVERED |
| PQC_CRC32 | 13.130 | 845 | 201.412 | DELIVERED |

Razoes observadas no BASELINE (240 MHz):

- PQC é 25,9x mais lento que CLASSIC em tempo;
- PQC transmite 11,5x mais bytes que CLASSIC;
- CRC32 adiciona ~10 us e +4 bytes sobre o fluxo PQC.

## 5. Fundamentos de criptografia para quem nunca viu

Esta seção foi escrita para quem nunca estudou criptografia. Ela explica, do
zero, cada conceito que aparece no projeto. Se você já conhece o assunto, pode
pular direto para a seção 6. Para estudar o funcionamento interno com mais
detalhe, incluindo pseudoalgoritmos, fórmulas, ML-KEM, HMAC, CRC32 e bit-flips,
use também `ALGORITMOS_DO_PROJETO.md`.

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

- AES-128-GCM usa uma chave **simetrica** para cifrar e autenticar a
  mensagem;
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
ser usado para derivar uma chave AES e cifrar mensagens.

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

**No nosso projeto:** HMAC-SHA256 não faz parte da demo visual de falha nem da
autenticação principal de `MISSION`. A autenticação da mensagem vem de
AES-128-GCM.

Ele ainda pode aparecer como mecanismo técnico legado para:

- derivar material de chave em alguns pontos internos;
- auditar, pelo terminal, comandos antigos de bancada que não entram no popup
  da apresentação.

No envio `MISSION`, a autenticação principal da mensagem agora vem do
AES-128-GCM, que cifra o payload e verifica a tag GCM no recebimento.

### 5.6 O que o CRC32 faz por dentro

CRC = Cyclic Redundancy Check (Verificação de Redundancia Ciclica).

O CRC32 trata os dados como um polinomio e divide por um polinomio fixo
(`0xEDB88320`). O resto dessa divisao e o valor CRC32 (4 bytes).

```text
  dados originais  --divisao polinomial-->  resto = CRC32 (4 bytes)

  Nos single-bit flips cobertos pela demo:
  bit muda --> o resto muda --> corrupcao detectada
```

**Importante: CRC32 NÃO e criptografia.**

- Ele **não esconde** dados;
- Ele **não autentica** (não usa chave secreta);
- Ele **só detecta alterações acidentais**.

Um atacante pode modificar os dados E recalcular o CRC32 para que bata.
Para segurança contra atacantes, use autenticação criptográfica, como
AES-GCM no fluxo `MISSION` ou HMAC em outros protocolos.

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

1. **keygen**: gera par de chaves ML-KEM-512 (~3.586 us)
2. **encap**: encapsula um segredo usando a chave publica (~3.911 us)
3. **decap**: decapsula o ciphertext com a chave privada (~5.012 us)
4. **Compara**: verifica se `ss_alice == ss_bob` (`key_match`)
5. **KDF**: deriva uma chave AES-128 a partir do segredo ML-KEM
6. **RNG**: gera nonce GCM aleatório de 12 bytes
7. **AES-GCM encrypt**: cifra `payload + CRC32` e gera tag GCM de 16 bytes
8. **AES-GCM decrypt/verify**: só libera o plaintext se a tag for válida
9. **CRC32 RX**: recalcula CRC32 e compara com o valor protegido
10. **Total**: deve ser medido novamente na bateria pós-AES-GCM

```text
  Fluxo no firmware (PQC_CRC32):

  keygen -----> encap -----> decap -----> compara ss
  (3.586 us)    (3.911 us)   (5.012 us)
                                           |
                                           v
                                     KDF -> AES key
                                           |
                                           v
                                     AES-GCM encrypt
                                           |
                                           v
                                     AES-GCM verify
                                           |
                                           v
                                     CRC32 RX (5 us)
                                           |
                                           v
                                     DELIVERED (tempo pós-AES a medir)
```

### 5.9 Tabela comparativa: criptografia clássica vs PQC

| Aspecto | Clássica (AES-128-GCM) | PQC (ML-KEM-512 + AES-128-GCM) |
|---|---|---|
| O que faz | Cifra e autentica a mensagem | Estabelece segredo + cifra e autentica |
| Tipo de chave | Simetrica efêmera | Assimetrica gerada por sessão |
| Tamanho de chave | 16 bytes (AES-128) | pk=800, sk=1.632 bytes |
| Bytes transmitidos* | 73 | 841 |
| Tempo (240 MHz)* | ~511 us | ~13.234 us |
| Tempo (80 MHz)* | ~1.139 us | ~38.837 us |
| Resiste a quântico | Parcial: AES-128 cai a ~64 bits sob Grover | Sim (reticulados) |
| Custo de adicionar CRC32 | N/A | +10 us, +4 bytes |

\* Bytes e tempos vêm da bateria histórica pré-AES-GCM; servem de referência
até a nova bateria oficial da versão cifrada.

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
batem. Esse rótulo é de bancada técnica, não da demo visual principal.

Fala sugerida:

> Aqui não estamos dizendo que a decapsulacao gritou "erro". Estamos dizendo
> que, ao comparar os resultados no experimento, vimos que as duas pontas
> chegaram a segredos diferentes.

### O que é `PROTOCOL_REJECT`?

Significa que uma confirmação autenticada da chave falhou em um ensaio técnico
de protocolo. Esse rótulo não aparece no popup de falha da apresentação.

Fala sugerida:

> Esse resultado é útil para bancada de protocolo, mas não é o fluxo que vamos
> mostrar no seminário. Na tela, a comparação principal é SILENT versus
> DETECTED_GUARD.

### O que é HMAC-SHA256?

é um mecanismo para calcular uma etiqueta de autenticação usando uma chave.
Aqui, ele serve para confirmar se as duas pontas realmente chegaram ao mesmo
segredo em ensaios técnicos fora da demo visual.

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

1. `CLASSIC` cifra/autentica a mensagem com AES-128-GCM e chave efêmera;
2. `PQC` executa ML-KEM-512, deriva chave AES e cifra a mensagem;
3. `PQC_CRC32` repete o fluxo PQC e protege CRC32 junto do payload;
4. o console e o overlay de mensagem entregue mostram tempo e bytes;
5. cada cenário abre um popup próprio; arraste os cartões pelo topo e mantenha `CLASSIC`, `PQC` e `PQC+CRC` lado a lado até clicar no `X`, permitindo comparar tempo, bytes, heap, keygen, encap, KDF, AES-GCM, decap e verificação na ordem real da mensagem;
6. com dois ou mais popups abertos lado a lado, compare em cada cartão payload, ML-KEM, nonce, tag GCM e CRC32;
7. LEDs/bargraph reforçam visualmente o aumento de custo.

Como explicar:

> A mensagem enviada é pequena. Mesmo assim, quando trocamos o baseline
> clássico por PQC, o custo cresce. Quando adicionamos checksum ao fluxo PQC,
> ganhamos mais integridade observavel e também somamos mais trabalho ao
> hardware.

### Momento de descoberta: previsão da turma

Antes de clicar em `ENVIAR MSG`, pergunte:

> O que vocês acham que vai crescer mais quando sairmos de AES-GCM puro para
> ML-KEM-512 + AES-GCM: CPU, bytes transmitidos ou RAM?

Depois dos três envios, compare os popups lado a lado:

> A RAM ficou estável, então o gargalo visível não foi memória. O impacto forte
> apareceu em tempo e tráfego. Na bateria histórica pré-AES, a mesma mensagem
> passou de 73 bytes para 841 bytes e de menos de 1 ms para cerca de 13 ms.

Falas curtas para cada cartão:

- `CLASSIC`: "Este é o baseline barato: payload pequeno cifrado com AES-GCM."
- `PQC`: "Aqui entra o ciphertext ML-KEM; é por isso que os bytes saltam."
- `PQC+CRC`: "CRC32 soma só 4 bytes, mas dá uma forma visual de detectar corrupção acidental."

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

Pergunte antes de revelar:

> Se um bit mudar no payload e ninguém conferir, o sistema tem como saber?

Depois da segunda falha:

> Esse é o papel didático do CRC32 aqui. Ele não substitui AES-GCM nem HMAC
> contra atacante, mas transforma corrupção acidental em evento observável.

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
| `STRESS` | Fica protegido dentro de `RESULTADOS`; é fechamento de impacto, não botão lateral |
| `PQC_FAULT` | Comando técnico opcional no terminal se a serial estiver estável; não deve virar botão |
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
`logs/20260625T005330Z_final_metrics_dev-ttyusb0.json` para mostrar a
tabela final de `elapsed_us`, `bytes_total` e `heap`.

### Resultado 2: CRC32 detectou o payload alterado

Use a frase:

> Quando protegemos o payload com CRC32, a mesma alteração de bit deixou de
> passar silenciosamente e virou um erro detectado.

Base:

```text
600/600 DETECTED_GUARD na coleta final
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

### Resultado 4: bit-flip em payload sem guardião é silencioso

Use a frase:

> Quando um bit do payload muda e não existe checksum ativo, o sistema não tem
> uma referência simples para comparar. A corrupção passa como falha silenciosa.

Base:

```text
FAULT NONE -> SILENT
```

### Resultado 5: CRC32 transforma a mesma falha em detecção

Use a frase:

> Com CRC32, salvamos um resumo do payload antes da falha e recalculamos depois.
> Quando os valores divergem, o dashboard mostra DETECTED_GUARD.

Base:

```text
FAULT CRC32 -> DETECTED_GUARD
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
- "CLASSIC e um baseline simetrico com AES-GCM";
- "PQC usa ML-KEM para estabelecer a chave antes de cifrar/autenticar com AES-GCM";
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
| `ALGORITMOS_DO_PROJETO.md` | Explicação detalhada dos algoritmos usados no firmware e na demo |
| `METRICAS_CONSOLIDADAS.md` | Como medir e apresentar CLASSIC, PQC e PQC+CRC |
| `PERGUNTAS_E_RESPOSTAS_SEMINARIO.md` | Banco de perguntas prováveis e respostas para treino |
| `ROADMAP.md` | Histórico técnico consolidado |
| `hardware_command_reference.md` | Comandos completos de bancada |
| `logs/20260625T005330Z_final_metrics_dev-ttyusb0.json` | Evidencia principal da coleta final |

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

> No envio CLASSIC, a placa usa AES-128-GCM com chave efêmera. No envio PQC,
> ela executa ML-KEM-512 para chegar a um segredo e então usa AES-GCM para
> cifrar/autenticar a mensagem. No envio PQC+CRC, ela adiciona CRC32 ao
> payload protegido. O console do dashboard mostra o
> tempo e os bytes de custo individual de cada mensagem enviada, enquanto a
> faixa superior mostra CPU e RAM para comparar o impacto de recursos.

### Conectar com PQC

> A parte pós-quântica não é apenas decorativa: a placa executa ML-KEM-512 real.
> Na demo visual, porém, a falha fica no payload para comparar exatamente o que
> muda quando ativamos CRC32: sem guardião, SILENT; com CRC32,
> DETECTED_GUARD.

### Interpretar resultados

> Na coleta histórica pré-AES-GCM tivemos 3.074 registros, 0 falhas, 1.800
> MISSION runs e 10 benchmarks PQC. CLASSIC entregava em 511 us com 73 bytes;
> PQC custava 13.234 us com 841 bytes; PQC+CRC custava 13.130 us com 845
> bytes. A versão atual cifra o payload com AES-GCM e precisa de nova bateria
> para números oficiais, mas a conclusão de custo do ML-KEM continua sendo o
> centro do experimento.
> No payload, CRC32 detecta a alteração (600/600 DETECTED_GUARD); no ML-KEM, a
> confirmação de chave rejeita a sessão divergente.

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
  CLASSIC: AES-128-GCM -> baseline classico simetrico cifrado.
  PQC: ML-KEM-512 + AES-GCM -> chave pos-quantica + mensagem cifrada.
  PQC+CRC: ML-KEM + AES-GCM + CRC32 -> integridade didatica adicional.
  A/B bit-flip: sem CRC32 -> silencioso; com CRC32 -> detectado.
  A bateria historica pre-AES mostrou PQC 25,9x mais lento que CLASSIC.

PQC:
  ML-KEM-512 real na placa.
  MISSION PQC usa ML-KEM para estabelecer chave.
  AES-GCM cifra/autentica o payload.
  A falha visual corrompe payload e compara NONE vs CRC32.

Resultado:
  3.074 registros, 0 falhas no aceite.
  600/600 DETECTED_GUARD em payload CRC32.
  PQC_KAT passou.
  Benchmarks em 240 MHz e 80 MHz medidos.
  Numeros antigos: CLASSIC=511 us / PQC=13.234 us / PQC_CRC32=13.130 us.
  Numeros atuais com AES-GCM precisam de nova bateria oficial.

Limites:
  Nao e radiacao fisica.
  Nao mede energia real.
  Wisdom e OBC educacional, nao CubeSat real.
```
