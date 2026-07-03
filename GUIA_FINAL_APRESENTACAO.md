# Guia final de estudo e apresentação — PQC-SAT

Este é o artefato central de preparação do seminário. Ele substitui o antigo
guia didático, o roteiro separado, o banco isolado de perguntas e respostas e
o documento separado de algoritmos. O objetivo é permitir que um aluno leia do
começo ao fim, compreenda o projeto com profundidade, ensaie a demonstração e
responda perguntas sem superestimar o que foi implementado.

Estado documental: 2026-07-02.

## 1. Como estudar este documento

Faça três passagens:

1. **Compreensão:** leia as seções 2 a 11 sem tentar decorar números.
2. **Defesa:** estude as seções 12 a 16 e explique cada conceito em voz alta.
3. **Ensaio:** execute as seções 17 a 20 com a placa e o projetor.

Se houver pouco tempo, leia nesta ordem:

1. seção 2, resumo de um minuto;
2. seção 8, os três cenários;
3. seção 11, resultados oficiais;
4. seção 17, roteiro de 20 minutos;
5. seção 18, perguntas difíceis;
6. seção 22, folha de consulta rápida.

## 2. O projeto em um minuto

O PQC-SAT é uma demonstração didática executada em uma RoboCore BlackBoard
Wisdom com ESP32. A placa representa um computador de bordo, ou OBC,
educacional inspirado em CubeSats. Ela não é um CubeSat real nem equipamento
certificado para voo.

A mesma mensagem é processada em três cenários:

| Cenário | Estabelecimento de chave | Proteção da mensagem | Guardião adicional |
|---|---|---|---|
| `CLASSIC` | ECDH P-256 efêmero | AES-128-GCM | nenhum |
| `PQC` | ML-KEM-512 | AES-128-GCM | nenhum |
| `PQC_CRC32` | ML-KEM-512 | AES-128-GCM | CRC32 no plaintext protegido |

O projeto responde a duas perguntas:

1. Qual é o custo de introduzir estabelecimento de chave pós-quântico em um
   hardware limitado?
2. Como tornar visível uma corrupção acidental de um bit no payload?

Os valores antigos de 23,2x em tempo e 12,1x em bytes são históricos
pré-ECDH e não servem como conclusão atual. A comparação de produção deve usar
o benchmark de sessão a 240 MHz, separando latência crítica, CPU agregada e
handshake amortizado. Nos testes de payload já validados, 200/200 falhas sem
CRC32 foram silenciosas e 200/200 falhas com CRC32 foram detectadas.

Resposta curta recomendada:

> O projeto mostra que ML-KEM-512 funciona em um ESP32, mas altera fortemente
> o orçamento de tempo e comunicação. AES-GCM continua cifrando e autenticando
> a mensagem; ML-KEM estabelece a chave. O CRC32 não é criptografia: ele é um
> recurso didático para transformar corrupção acidental de payload em erro
> observável.

## 3. Contexto do problema

### 3.1 CubeSat, OBC e COTS

Um CubeSat é um satélite pequeno construído em unidades padronizadas. O OBC é o
computador de bordo responsável por coordenar tarefas, processar telemetria e
executar partes do protocolo de comunicação.

`COTS` significa *commercial off-the-shelf*: componente comercial disponível
no mercado. Componentes COTS reduzem custo e tempo de desenvolvimento, mas não
devem ser automaticamente tratados como tolerantes à radiação ou certificados
para ambiente espacial.

No seminário:

- a Wisdom/ESP32 representa um OBC COTS educacional;
- o notebook executa o dashboard e a bridge serial;
- a comunicação real da bancada é USB serial;
- não existe enlace de rádio no experimento;
- os papéis de emissor e receptor são lógicos e executados na mesma placa.

### 3.2 Por que falhas transitórias importam

Uma falha transitória altera temporariamente um valor sem necessariamente
destruir o hardware. Um exemplo é o *bit-flip*:

```text
0 -> 1
1 -> 0
```

No projeto, a falha é injetada por software com XOR:

```text
byte_alterado = byte_original XOR mascara_de_um_bit
```

Isso não reproduz física de radiação. Ele reproduz, de forma segura e
determinística, o efeito lógico que interessa ao experimento: um bit mudou.

### 3.3 Por que falar de ameaça quântica

RSA e ECDH são mecanismos de chave pública baseados em problemas matemáticos
que um computador quântico grande e corrigido poderia atacar com o algoritmo
de Shor. Isso motiva a migração para criptografia pós-quântica.

Não diga que "toda criptografia clássica morre". AES, SHA-256 e HMAC continuam
relevantes. O problema principal está em mecanismos de chave pública
vulneráveis a Shor. Por isso sistemas híbridos usam um KEM pós-quântico para
estabelecer uma chave e mecanismos simétricos para proteger os dados.

### 3.4 Restrições de hardware

Em um sistema embarcado, segurança compete por:

- tempo de CPU;
- RAM;
- flash;
- bytes transmitidos;
- energia;
- latência tolerável da missão.

O projeto mede diretamente tempo, bytes e heap. Energia elétrica não foi
medida. Tempo de CPU é indicador de custo computacional, não watts ou joules.

## 4. Pergunta científica, hipóteses e recorte

### 4.1 Pergunta principal

> Qual é o custo observado de inserir ML-KEM-512 e CRC32 na entrega de uma
> mensagem curta em uma Wisdom/ESP32 operando a 240 MHz e em um perfil
> experimental limitado a 80 MHz?

### 4.2 Hipóteses

- **H1:** o custo de CPU dependerá da biblioteca; ML-KEM pode ser mais rápido
  que ECDH P-256 nesta plataforma e isso não invalida o experimento.
- **H2:** `PQC` terá pacote maior por incluir ciphertext ML-KEM.
- **H3:** limitar a CPU a 80 MHz aumentará o custo temporal, sem alterar os
  tamanhos do protocolo.
- **H4:** CRC32 acrescentará 4 bytes e detectará todo single-bit flip dentro da
  região de payload coberta.
- **H5:** o impacto mais visível será tempo e tráfego, não exaustão de heap.

### 4.3 O que o projeto demonstra

- integração funcional de ML-KEM-512 real no ESP32;
- entrega de mensagem com AES-128-GCM;
- custo relativo dos três cenários no hardware usado;
- efeito do perfil de 80 MHz;
- diferença entre corrupção silenciosa e erro detectado;
- confirmação operacional de divergência de chave em ensaio de bancada.

### 4.4 O que o projeto não demonstra

- certificação espacial;
- resistência física à radiação;
- consumo elétrico real;
- segurança universal de todo CubeSat;
- comparação de protocolos autenticados completos entre ECDH e ML-KEM;
- proteção contra *side-channel*;
- protocolo de missão completo com gestão permanente de identidades e chaves;
- prova matemática da segurança de ML-KEM.

## 5. Arquitetura do sistema

```text
┌──────────────────────── notebook ────────────────────────┐
│ dashboard.py                                             │
│  - onboarding e visualização                             │
│  - comandos da demo                                      │
│  - popups e RESULTADOS                                   │
│  - exportação JSON                                       │
│             │                                            │
│             └── bridge serial V1, não bloqueante ────────┼──┐
└──────────────────────────────────────────────────────────┘  │ USB serial
                                                               │
┌────────────────── BlackBoard Wisdom / ESP32 ────────────────┐│
│ firmware                                                     │◄┘
│  - sensores e payload                                        │
│  - ML-KEM-512 real                                           │
│  - AES-128-GCM                                                │
│  - CRC32 e injeção de falha                                  │
│  - métricas de tempo, bytes e heap                           │
└──────────────────────────────────────────────────────────────┘
```

### 5.1 Fonte de verdade operacional

O dashboard não calcula ML-KEM. Ele envia comandos, recebe resultados e
visualiza os dados. O firmware é quem executa criptografia e medições.

Sem handshake válido da Wisdom, `ENVIAR MSG` deve ser recusado. O modo
`--simulated` existe para ensaio visual e não deve reproduzir métricas oficiais
como se viessem do hardware.

### 5.2 Payload vivo

Com `Payload vivo` ligado, o dashboard solicita leituras à placa, monta uma
mensagem ASCII compacta e envia seu hexadecimal no comando `MISSION`.

Exemplo:

```text
PQC-SAT|S=42|T=2450|H=5530|X=12|Y=-34|Z=1001|L=321|P=2048|B=0|OK
```

Campos:

- `S`: sequência;
- `T`, `H`: temperatura e umidade em escala inteira;
- `X`, `Y`, `Z`: aceleração;
- `L`: luz/proximidade;
- `P`: potenciômetro;
- `B`: botão;
- `OK`: marcador de estado.

Se um sensor falha, o payload pode usar `NA`. Isso evita travar a demonstração
por um periférico secundário.

### 5.3 Evento do botão físico

O firmware possui debounce e emite `BUTTON_PING` quando o botão da Wisdom é
pressionado. O dashboard desenha apenas um feixe curto do satélite até a Terra.
Esse easter egg funciona como um ping visual e não reativa polling automático
de telemetria.

Antes da apresentação, confirme que a revisão de firmware com `BUTTON_PING`
foi gravada e validada na placa. Compilar o código não equivale a gravá-lo.

## 6. Fundamentos de criptografia

### 6.1 Payload, plaintext, ciphertext, chave e tag

- **payload:** dados úteis da mensagem;
- **plaintext:** dados antes da cifragem;
- **ciphertext:** saída cifrada;
- **chave:** segredo que controla a operação criptográfica;
- **nonce:** valor único por uso de uma chave; não precisa ser secreto;
- **tag:** valor usado para verificar autenticidade e integridade.

### 6.2 Criptografia simétrica e assimétrica

Na criptografia simétrica, as pontas usam a mesma chave. AES é simétrico.

Na criptografia assimétrica, existe material público e privado. RSA, ECDH e
ML-KEM pertencem ao contexto de chave pública, embora tenham funções
diferentes. ECDH é acordo de chave; ML-KEM é encapsulamento de chave.

### 6.3 AES-128-GCM

AES-128 usa chave de 128 bits. GCM é um modo AEAD: *Authenticated Encryption
with Associated Data*. Ele oferece confidencialidade e autenticação.

No projeto:

```text
chave AES: 16 bytes
nonce:     12 bytes
tag GCM:   16 bytes
```

Fluxo conceitual:

```text
(ciphertext, tag) = GCM_Encrypt(chave, nonce, plaintext)
plaintext = GCM_Decrypt_And_Verify(chave, nonce, ciphertext, tag)
```

Se a tag não é válida, o plaintext não deve ser aceito. O nonce não deve se
repetir com a mesma chave. Na bateria oficial, 600 mensagens tiveram 600
nonces, ciphertexts e tags distintos.

### 6.4 KEM e ML-KEM-512

KEM significa *Key Encapsulation Mechanism*. Um KEM não cifra a mensagem da
aplicação. Ele estabelece um segredo compartilhado.

```text
(pk, sk) = KeyGen()
(ct, ss_emissor) = Encaps(pk)
ss_receptor = Decaps(sk, ct)
```

Se o fluxo é íntegro:

```text
ss_emissor == ss_receptor
```

Tamanhos de ML-KEM-512 usados no projeto:

| Objeto | Tamanho |
|---|---:|
| chave pública `pk` | 800 B |
| chave privada `sk` | 1.632 B |
| ciphertext KEM `ct` | 768 B |
| segredo compartilhado `ss` | 32 B |

`512` é o nome do conjunto de parâmetros mais leve da família ML-KEM; não
significa "segurança de 512 bits".

### 6.5 Intuição matemática de ML-KEM

ML-KEM é baseado em reticulados e Module Learning With Errors. Uma intuição
simplificada é:

```text
t = A·s + e  (mod q)
```

- `A` é estrutura pública;
- `s` é segredo pequeno;
- `e` é ruído pequeno;
- `q` é um módulo; em ML-KEM, `q = 3329`.

O ruído impede tratar o problema como álgebra linear comum. Não existe hoje um
algoritmo quântico conhecido equivalente a Shor que destrua essa estrutura.
Isso não é prova feita pelo projeto; é a base do padrão FIPS 203.

Detalhes suficientes para uma pergunta mais técnica:

- ML-KEM-512 mira a categoria de segurança 1 do NIST;
- os polinômios têm 256 coeficientes no anel
  `Z_q[X] / (X^256 + 1)`;
- ML-KEM-512 usa vetores de dimensão `k = 2`;
- `q = 3329` mantém os coeficientes em aritmética modular;
- a NTT acelera multiplicações polinomiais; ela é uma técnica de implementação,
  não a hipótese de segurança;
- `512` nomeia o conjunto de parâmetros, não o tamanho de `pk`, `sk`, `ct` ou
  uma alegação de 512 bits de segurança.

Uma resposta segura é: a segurança é baseada na dificuldade de Module-LWE e
problemas relacionados de reticulados com esses parâmetros, e o seminário não
tenta reproduzir a prova criptográfica do padrão.

### 6.6 KeyGen, Encaps e Decaps

**KeyGen:** gera sementes, expande a matriz pública, amostra segredo e ruído e
empacota `pk` e `sk`. É medido em `keygen_us`.

**Encaps:** usa `pk` e aleatoriedade nova para produzir `ct` e o segredo do
emissor. É medido em `encap_us`. O segredo não é colocado no pacote.

**Decaps:** usa `sk` e `ct`, recupera informação interna, reconstrói a
consistência do encapsulamento e produz o segredo do receptor. É medido em
`decap_us`. Na bateria, foi a etapa ML-KEM mais cara.

ML-KEM usa uma transformação no estilo Fujisaki–Okamoto e rejeição implícita.
Em vez de oferecer ao chamador um simples “ciphertext inválido”, a decapsulação
de uma entrada de tamanho válido produz um segredo alternativo quando a
verificação interna falha. Isso reduz oráculos de validade, mas significa que
o protocolo precisa confirmar ou usar a chave em uma operação autenticada.

### 6.7 Derivação de chave

Os segredos ECDH P-256 e ML-KEM têm 32 bytes no experimento. O firmware deriva
de cada um uma chave AES-128 de 16 bytes usando HMAC-SHA256 e o contexto
`PQC-SAT|MISSION|<cenário>|AES-128-GCM|v1`. O objetivo do contexto é separar
esse uso de outros possíveis usos do mesmo segredo. A implementação conserva
os primeiros 16 bytes do digest como chave AES-128.

Não diga que ML-KEM cifrou o payload. Diga:

> ML-KEM estabeleceu o segredo; a derivação produziu a chave AES; AES-GCM
> cifrou e autenticou a mensagem.

### 6.8 CRC32

CRC32 detecta corrupção acidental. Ele trata os bits como um polinômio binário
e calcula um resto de 32 bits. O firmware usa a forma refletida comum com o
polinômio `0xEDB88320`.

```text
crc_original = CRC32(payload_original)
crc_recebido = CRC32(payload_recebido)
corrompido = (crc_original != crc_recebido)
```

Um single-bit flip dentro da região coberta é detectado. CRC32 não usa chave;
um atacante pode alterar dados e recalcular o CRC. Portanto:

- CRC32 detecta erro acidental;
- AES-GCM autentica a entrega criptográfica;
- HMAC autentica com chave em ensaios específicos;
- um mecanismo não deve ser chamado pelo nome do outro.

### 6.9 SHA-256 e HMAC-SHA256

SHA-256 é uma função hash de 256 bits. É determinística, tem efeito avalanche
e foi projetada para dificultar pré-imagens e colisões.

HMAC combina uma hash e uma chave:

```text
HMAC(K,M) = SHA256((K' XOR opad) || SHA256((K' XOR ipad) || M))
```

HMAC não cifra. No projeto atual, AES-GCM autentica `MISSION`. HMAC-SHA256 é
usado no ensaio técnico `PQC_FAULT ... CONFIRM` para verificar se as pontas
derivaram o mesmo segredo.

Um SHA-256 simples de `chave || mensagem` não deve ser improvisado como MAC.
HMAC define corretamente a mistura da chave com `ipad` e `opad` e foi projetado
para autenticação. No projeto, HMAC também é usado como função de derivação da
chave AES com separação por contexto.

### 6.10 Comparação em tempo constante

Uma comparação comum pode parar no primeiro byte diferente e vazar informação
pelo tempo. Uma comparação em tempo constante percorre todos os bytes:

```text
diff = 0
para cada i:
    diff = diff OR (a[i] XOR b[i])
iguais = (diff == 0)
```

O firmware usa essa ideia para segredos e tags. Isso reduz vazamento trivial de
posição da primeira diferença; não significa que todo o sistema foi auditado
contra side-channel.

### 6.11 KAT

KAT significa *Known Answer Test*. Entradas conhecidas têm saídas esperadas.
Ele ajuda a verificar integração e compatibilidade da implementação. O
`PQC_KAT` da placa retornou `kat=pass`; isso não substitui auditoria formal da
biblioteca.

## 7. Ameaça quântica sem exageros

### 7.1 O que Shor ameaça

Shor ameaça fatoração e logaritmo discreto, base de RSA e ECDH. O risco de
*harvest now, decrypt later* é capturar dados hoje para tentar quebrá-los no
futuro.

### 7.2 O que continua sendo usado

AES e hashes não são substituídos por ML-KEM. Em uma arquitetura híbrida:

```text
ML-KEM -> estabelece chave
AES-GCM -> protege dados
SHA/HMAC -> derivação, confirmação ou autenticação específica
```

### 7.3 Frase segura para a apresentação

> A migração pós-quântica não elimina criptografia simétrica. Ela substitui ou
> complementa mecanismos de chave pública vulneráveis, enquanto AES-GCM
> continua protegendo o tráfego de dados.

## 8. Os três cenários exatos

### 8.1 `MISSION CLASSIC`

```text
payload
  -> duas pontas geram pares ECDH P-256 efêmeros
  -> emissor usa a chave pública do receptor e envia sua chave pública de 65 B
  -> as duas pontas calculam o mesmo segredo
  -> KDF deriva a chave AES; RNG gera o nonce
  -> AES-128-GCM cifra e gera tag
  -> receptor verifica tag e decifra
  -> DELIVERED se AEAD confere
```

Esse é o baseline clássico assimétrico equivalente ao estabelecimento ML-KEM.

Para o payload de 41 B da bateria oficial:

```text
41 B payload + 65 B chave pública ECDH + 12 B nonce + 16 B tag = 134 B
```

### 8.2 `MISSION PQC`

```text
KeyGen -> Encaps -> ss_emissor
                   |
                   +-> KDF -> chave AES emissor
ct ML-KEM -> Decaps -> ss_receptor -> KDF -> chave AES receptor
payload + nonce -> AES-GCM -> ciphertext + tag -> verifica -> DELIVERED
```

Para o payload oficial:

```text
41 B payload + 768 B ct ML-KEM + 12 B nonce + 16 B tag = 837 B
```

A chave pública de 800 B não entra em `bytes_total` de `MISSION`. A métrica
contabiliza o pacote de entrega modelado: payload/ciphertext da mensagem,
ciphertext ML-KEM, nonce, tag e CRC quando ativo.

### 8.3 `MISSION PQC_CRC32`

```text
crc_tx = CRC32(payload)
plaintext_protegido = payload || crc_tx
ML-KEM estabelece chave AES
AES-GCM cifra plaintext_protegido e gera tag
receptor verifica GCM, separa CRC e recalcula crc_rx
DELIVERED se key_match, aead_match e crc_match
```

```text
41 B payload + 768 B ct ML-KEM + 12 B nonce + 16 B tag + 4 B CRC = 841 B
```

O CRC está dentro do plaintext protegido por AES-GCM. Ele existe para a
narrativa de corrupção acidental e para medir seu pequeno custo adicional.

## 9. Modelo de falhas

### 9.1 Falha de payload da demonstração

```text
FAULT NONE  payload_hex index mask
FAULT CRC32 payload_hex index mask
```

Condições objetivas:

| Guardião | Payload mudou? | CRC divergiu? | Resultado |
|---|---:|---:|---|
| `NONE` | sim | não se aplica | `SILENT` |
| `CRC32` | sim | sim | `DETECTED_GUARD` |

O potenciômetro pode selecionar fisicamente a posição do bit. A mutação é
real sobre bytes; o resultado não é sorteado.

### 9.2 Falha de ciphertext ML-KEM de bancada

```text
PQC_FAULT index mask NONE
PQC_FAULT index mask CONFIRM
```

ML-KEM decapsula entradas de tamanho válido e produz um segredo. Um ciphertext
corrompido não deve ser descrito como "sempre gera erro explícito".

- `KEY_MISMATCH`: o harness observou `ss_enc != ss_dec`;
- `PROTOCOL_REJECT`: uma confirmação HMAC mostrou tags diferentes e o
  protocolo rejeitou a sessão.

`KEY_MISMATCH` é observação de teste. Detecção operacional exige confirmação
ou uso da chave em um protocolo autenticado.

## 10. Metodologia experimental

### 10.1 Perfis

| Perfil | CPU | Interpretação correta |
|---|---:|---|
| `BASELINE` | 240 MHz | capacidade integral usada como referência |
| `OBC-1U-LIMITED` | 80 MHz | política experimental de limitação |

`OBC-1U-LIMITED` não é especificação universal de CubeSat.

### 10.2 Variáveis observadas

- `elapsed_us`: tempo total;
- `keygen_us`, `encap_us`, `decap_us`: etapas ML-KEM;
- `rng_us`, `kdf_us`: aleatoriedade e derivação;
- `encrypt_us`, `decrypt_us`: AES-GCM;
- `crc_us`: custo de CRC;
- `bytes_total`: pacote modelado;
- `heap`, `min_heap`: memória livre e mínimo observado;
- `key_match`, `aead_match`, `tag_match`, `crc_match`: validações;
- `result`: classificação final.

### 10.3 Separação entre demo e evidência

A demonstração manual ensina. A bateria automatizada consolida resultados.
Nunca use cliques ao vivo como substituto para a coleta estatística oficial.

Fonte histórica pré-ECDH:

```text
logs/20260702T044907Z_final_metrics_dev-ttyusb0.json
```

Resumo:

```text
1.038 registros
0 falhas de comando
600 MISSION
6 PQC_BENCH
400 testes FAULT
```

## 11. Resultados históricos pré-ECDH e interpretação

Os números abaixo documentam a coleta de 2026-07-02. Eles não devem ser usados
como comparação final ECDH/ML-KEM; a nova bateria substituirá estas tabelas.

### 11.1 `MISSION` em 240 MHz

| Métrica média | CLASSIC | PQC | PQC+CRC32 |
|---|---:|---:|---:|
| tempo total | 611 us | 14.152 us | 14.097 us |
| bytes totais | 69 B | 837 B | 841 B |
| keygen | 0 | 3.743 us | 3.678 us |
| encap | 0 | 3.953 us | 3.934 us |
| decap | 0 | 5.029 us | 5.019 us |
| AES encrypt | 365 us | 389 us | 416 us |
| AES decrypt | 125 us | 124 us | 125 us |
| CRC | 0 | 0 | 32 us |
| resultado | DELIVERED | DELIVERED | DELIVERED |

### 11.2 `MISSION` em 80 MHz

| Métrica média | CLASSIC | PQC | PQC+CRC32 |
|---|---:|---:|---:|
| tempo total | 1.028 us | 40.197 us | 40.077 us |
| bytes totais | 69 B | 837 B | 841 B |
| keygen | 0 | 10.524 us | 10.450 us |
| encap | 0 | 11.882 us | 11.833 us |
| decap | 0 | 15.259 us | 15.221 us |
| AES encrypt | 554 us | 600 us | 607 us |
| AES decrypt | 314 us | 313 us | 316 us |
| CRC | 0 | 0 | 53 us |
| resultado | DELIVERED | DELIVERED | DELIVERED |

### 11.3 Razões históricas pré-ECDH

| Comparação | 240 MHz | 80 MHz |
|---|---:|---:|
| PQC / CLASSIC em tempo | 23,2x | 39,1x |
| PQC+CRC / CLASSIC em tempo | 23,1x | 39,0x |
| PQC / CLASSIC em bytes | 12,1x | 12,1x |
| bytes extras do CRC32 | +4 B | +4 B |

Não interprete `PQC_CRC32` ligeiramente mais rápido que `PQC` em 240 MHz como
aceleração causada pelo CRC. A diferença é variação experimental. O subtempo
`crc_us` mostra custo positivo; ele é pequeno diante de ML-KEM.

### 11.4 Benchmark ML-KEM de 100 rounds

| Perfil | keygen | encap | decap |
|---|---:|---:|---:|
| 240 MHz | 3.302 us | 3.866 us | 4.990 us |
| 80 MHz | 10.067 us | 11.789 us | 15.217 us |

Decaps foi a etapa mais cara. Reduzir frequência aumentou aproximadamente três
vezes os tempos das operações, como esperado ao passar de 240 para 80 MHz.

### 11.5 Falhas e validação AEAD

- 200/200 `FAULT NONE` resultaram em `SILENT`;
- 200/200 `FAULT CRC32` resultaram em `DETECTED_GUARD`;
- 600/600 `MISSION` usaram `cipher=AES-128-GCM`;
- 600/600 tiveram `aead_match=1` e `decrypt_ok=1`;
- 600 nonces, ciphertexts e tags GCM foram únicos;
- `PQC_KAT` passou;
- `PQC_FAULT ... CONFIRM` produziu `PROTOCOL_REJECT`;
- `PQC_FAULT ... NONE` produziu `KEY_MISMATCH`.

### 11.6 Conclusões defensáveis

1. ML-KEM-512 funcionou no hardware usado.
2. O custo dominante foi tempo e tráfego.
3. O perfil limitado ampliou o custo temporal, mas não mudou bytes.
4. A heap permaneceu estável; não houve evidência de exaustão de RAM.
5. CRC32 teve custo pequeno e tornou o single-bit flip coberto observável.
6. Os resultados são válidos para esta placa, firmware, biblioteca, payload e
   metodologia; não são universais para todos os CubeSats.

### 11.7 Comparabilidade com baterias anteriores

A bateria oficial anterior pós-AES usava payload de 34 B e produzia
62/830/834 B. A coleta atual usa o payload padrão de 41 B do runner geral e
produz 69/837/841 B. Os 7 B adicionais vêm exclusivamente do payload; nonce,
tag, ciphertext ML-KEM e CRC mantiveram os mesmos tamanhos. Compare razões e
tempos somente depois de identificar qual payload e qual JSON foram usados.

Uma bateria ainda mais antiga usava composição de pacote sem AES-GCM. Números
como 511 us, 13.234 us, 73 B e 841 B são históricos pré-AES e não devem ser
misturados com a coleta atual.

## 12. Como ler o dashboard

### 12.1 Onboarding

As cinco telas cobrem:

1. cenário de segurança embarcada em órbita;
2. problema da migração para PQC;
3. overview da mensagem até a entrega;
4. cenários e hipóteses;
5. projeções, limites e roteiro da demonstração.

### 12.2 Centro

Terra procedural, continentes, satélite e órbita contextualizam a narrativa. O
feixe acionado pelo botão físico é apenas um ping visual.

### 12.3 Faixa superior

- título do projeto;
- `RESULTADOS`;
- retorno ao onboarding;
- relógio e estado `SAT CONECTADO`;
- CPU e RAM.

### 12.4 Painel esquerdo

- estado da sessão;
- ML-KEM ativo somente em `PQC` e `PQC+CRC`;
- guardião `NONE` ou `CRC32`.

### 12.5 Painel direito

Botões principais:

- `ENVIAR MSG`;
- `CLÁSSICA`;
- `PQC`;
- `PQC+CRC`;
- `FALHA`.

Comandos técnicos continuam disponíveis no terminal textual e em
`tools/serial_console.py`, mas não devem dominar a apresentação.

### 12.6 Popups de mensagem

Cada cenário abre um popup arrastável. A animação mostra entrada, operação,
saída, composição do pacote, explicação e linha do tempo. Use a barra para
pausar/revisar e `VER DADOS` para abrir métricas.

Ordem lógica de PQC:

```text
PAYLOAD -> CRC opcional -> KEYGEN -> ENCAP -> KDF -> AES-GCM
        -> DECAP -> VERIFICA -> RESULTADO
```

### 12.7 `RESULTADOS`

O resumo de apresentação mostra bateria, desempenho, detecção e conclusões. A
visão `DADOS TÉCNICOS` tem duas páginas. `MÉTRICAS` compara os três cenários
em 240 e 80 MHz, mostra gráficos de tempo, fases internas, composição do
pacote, benchmark, validade AES-GCM e falhas. `TEORIA E FONTES` explica o que
cada número mede, por que a redução de clock não escala tudo exatamente por
três, por que `PQC+CRC` pode ter média total menor mesmo com `crc_us` positivo,
o significado de heap/min-heap e a função de cada referência bibliográfica.
As barras comparam cenários apenas dentro do perfil indicado. A tela lê dados
consolidados do projeto; não inicia nova coleta.

`STRESS PQC 500` é fechamento opcional de carga, não fonte estatística.

## 13. O que cada métrica significa

| Campo | Explicação que deve ser dada |
|---|---|
| `elapsed_us` | latência total do fluxo modelado |
| `bytes_total` | bytes contabilizados na entrega modelada |
| `heap` | memória livre após a operação |
| `min_heap` | menor heap livre observado desde o boot |
| `key_match` | segredos do harness coincidiram |
| `aead_match` | AES-GCM verificou e recuperou o payload esperado |
| `tag_match` | tag de autenticação conferiu |
| `crc_match` | CRC salvo e recalculado coincidiram |
| `DELIVERED` | todas as condições exigidas pelo cenário passaram |
| `SILENT` | bytes mudaram sem guardião detectar |
| `DETECTED_GUARD` | guardião detectou a corrupção |
| `KEY_MISMATCH` | harness observou segredos diferentes |
| `PROTOCOL_REJECT` | confirmação operacional rejeitou a sessão |

## 14. Limites e comparação justa

### 14.1 O baseline é limitado

`CLASSIC` usa ECDH P-256 efêmero e `PQC` usa ML-KEM-512. Ambos derivam uma
chave AES-128 e executam o mesmo AES-GCM. Certificados, rede real e autenticação
de identidades permanecem fora do escopo; portanto, o protótipo não impede
ataque man-in-the-middle. O material aleatório vem de `esp_random()` com rádio
desligado, sem ensaio ou certificação independente de entropia.

### 14.2 CRC32 e AES-GCM não são concorrentes

AES-GCM autentica o ciphertext contra alterações sem a chave. CRC32 detecta
erro acidental no payload e torna o bit-flip visual. CRC32 é redundante como
segurança criptográfica, mas útil como guardião didático e diagnóstico de
corrupção.

### 14.3 Energia

Frequência e tempo sugerem carga computacional, mas energia exige instrumento
externo e integração de potência no tempo. Não use LEDs, bargraph ou
`MHz × us` como joules.

### 14.4 Radiação

O projeto injeta falha lógica. Não mede taxa de eventos, dose, LET, upset
físico, latch-up ou efeitos cumulativos.

### 14.5 Uma placa, dois papéis

Emissor e receptor são papéis lógicos executados na Wisdom. Isso facilita
medição e demonstração, mas não mede latência de rede real nem interoperabilidade
entre dispositivos independentes.

## 15. Frases corretas e frases proibidas

| Evite | Prefira |
|---|---|
| “ML-KEM cifra a mensagem.” | “ML-KEM estabelece a chave; AES-GCM cifra.” |
| “CRC32 garante segurança.” | “CRC32 detecta corrupção acidental coberta.” |
| “A placa é um CubeSat.” | “A placa representa um OBC educacional.” |
| “Medimos energia.” | “Medimos tempo; energia é trabalho futuro.” |
| “ML-KEM detectou a falha.” | “O harness observou divergência ou o protocolo confirmou e rejeitou.” |
| “PQC é inviável.” | “PQC foi funcional; CPU, tráfego e memória devem ser comparados separadamente.” |
| “CLASSIC é só AES.” | “CLASSIC usa ECDH P-256; AES-GCM protege a mensagem.” |
| “80 MHz simula qualquer CubeSat.” | “80 MHz é um perfil experimental.” |
| “0 falhas prova segurança.” | “0 falhas de execução indica estabilidade da campanha.” |

## 16. Explicação completa em linguagem oral

> Sistemas embarcados de missão têm orçamento limitado. Ao mesmo tempo,
> mecanismos clássicos de chave pública como RSA e ECDH enfrentam uma ameaça
> futura de computadores quânticos. Nosso projeto pergunta quanto custa
> introduzir um mecanismo pós-quântico nesse contexto.
>
> Usamos uma BlackBoard Wisdom com ESP32 como OBC educacional. A placa processa
> a mesma mensagem em três cenários. No primeiro, AES-128-GCM usa uma chave
> efêmera e serve de baseline. No segundo, ML-KEM-512 estabelece o segredo que
> vira chave AES. No terceiro, adicionamos CRC32 dentro do plaintext protegido
> para visualizar corrupção acidental.
>
> ML-KEM não cifra o payload. Ele executa geração de chaves, encapsulamento e
> decapsulamento. AES-GCM cifra e autentica. O CRC32 não protege contra
> atacante; ele detecta o bit-flip controlado da demo.
>
> A bateria oficial mostrou 611 microssegundos e 69 bytes em CLASSIC contra
> 14.152 microssegundos e 837 bytes em PQC a 240 MHz. Em 80 MHz, PQC chegou a
> 40.197 microssegundos. As falhas sem CRC passaram silenciosamente e todas as
> falhas com CRC foram detectadas. A conclusão é que PQC cabe na placa, mas
> muda principalmente o orçamento de tempo e comunicação.

## 17. Roteiro de apresentação de 20 minutos

### 17.1 Antes de começar

1. Feche programas que possam usar `/dev/ttyUSB0`.
2. Conecte a Wisdom.
3. Confirme firmware e permissões.
4. Abra o dashboard:

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

5. Aguarde `SAT CONECTADO`.
6. Mantenha `Payload vivo` ligado.
7. Não inicie bateria longa durante a apresentação.

### 17.2 Distribuição de tempo

| Tempo | Conteúdo |
|---|---|
| 0–2 min | provocação e problema |
| 2–5 min | ameaça quântica e arquitetura híbrida |
| 5–7 min | três cenários e hipóteses |
| 7–13 min | demo CLASSIC, PQC e PQC+CRC |
| 13–15 min | falha silenciosa versus detectada |
| 15–18 min | resultados oficiais |
| 18–20 min | limites, próximos passos e perguntas |

### 17.3 Abertura

Pergunte:

> Se um computador de bordo pequeno precisar migrar para criptografia
> pós-quântica, o que cresce mais: tempo, bytes ou RAM?

Explique que a resposta será observada na placa, não apenas estimada.

### 17.4 Use o onboarding

Passe pelas cinco telas sem ler palavra por palavra. Em cada tela, dê uma
mensagem:

1. hardware limitado e bit-flip;
2. ameaça a mecanismos de chave pública;
3. ML-KEM estabelece e AES-GCM protege;
4. os três cenários mudam uma camada por vez;
5. hipóteses, limites e sequência da demo.

### 17.5 Demonstração das mensagens

1. Selecione `CLÁSSICA` e clique `ENVIAR MSG`.
   - diga: “baseline AES-GCM, sem ML-KEM”;
   - pause no RNG e AES-GCM;
   - mostre tempo e 69 B como referência oficial, não como valor obrigatório do
     envio ao vivo.
2. Selecione `PQC` e clique `ENVIAR MSG`.
   - pause em KEYGEN, ENCAP e DECAP;
   - mostre o ciphertext ML-KEM de 768 B;
   - destaque que AES-GCM ainda cifra.
3. Selecione `PQC+CRC` e clique `ENVIAR MSG`.
   - destaque CRC antes da cifragem;
   - mostre +4 B;
   - explique que não é autenticação contra atacante.

Se desejar comparar popups, mantenha-os abertos e arraste-os. Em resolução
menor, compare sequencialmente para preservar legibilidade.

### 17.6 Demonstração de falha

1. Selecione `PQC`, gire o potenciômetro e clique `FALHA`.
2. Mostre `SILENT`.
3. Pergunte: “Os bytes mudaram; quem percebeu?”
4. Selecione `PQC+CRC`, gire o potenciômetro e clique `FALHA`.
5. Mostre `DETECTED_GUARD`.

Frase correta:

> Mantivemos o tipo de falha e mudamos a presença do guardião. Sem referência,
> a corrupção foi silenciosa. Com CRC salvo antes da falha, a divergência ficou
> visível.

### 17.7 Ping físico opcional

Pressione o botão da Wisdom uma vez. O feixe visual representa um ping do
satélite para a Terra. Não associe esse efeito a rádio real ou medição de
latência de rede.

### 17.8 Resultados

Abra `RESULTADOS` e conduza três conclusões:

1. **segurança:** ML-KEM-512 real e AES-GCM validado;
2. **custo:** compare os novos valores ECDH/ML-KEM da bateria oficial;
3. **integridade:** 200/200 silenciosas sem CRC e 200/200 detectadas com CRC.

Depois diga os limites antes que a banca os cobre.

### 17.9 Fechamento

> PQC não foi inviável: funcionou. Mas segurança altera o orçamento do sistema.
> Em hardware limitado, tempo e tráfego precisam ser decisões de arquitetura,
> não detalhes adicionados no final.

## 18. Perguntas prováveis e respostas

### 18.1 Objetivo e escopo

**O que vocês provaram?**  Integração funcional e custo relativo nesta
Wisdom/ESP32. Não provamos uma propriedade universal de CubeSats.

**PQC foi inviável?**  Não. Foi funcional e mais caro em tempo e bytes.

**A Wisdom é um CubeSat?**  Não. É um OBC educacional de bancada.

**Por que usar COTS?**  Para tornar o problema reproduzível e mensurável com
hardware acessível, mantendo explícita a ausência de qualificação espacial.

**Há rádio?**  Não. A bancada usa USB serial. O feixe do ping é visual.

### 18.2 Criptografia

**ML-KEM cifra a mensagem?**  Não. Ele estabelece o segredo; AES-GCM cifra.

**Por que não usar apenas AES?**  AES pressupõe que as pontas já compartilham
uma chave. ML-KEM trata o estabelecimento dessa chave sob ameaça quântica.

**Por que usar ECDH?**  Ele fornece o baseline clássico de estabelecimento de
chave: ECDH P-256 e ML-KEM-512 alimentam o mesmo KDF/AES-GCM na mesma placa.

**Por que ML-KEM-512?**  É o conjunto mais leve da família e adequado à
primeira integração embarcada. `512` não é tamanho da chave nem segurança em
bits.

**Por que não ML-DSA?**  ML-DSA é assinatura. O problema escolhido é
estabelecimento de segredo, não assinatura de software ou identidade.

**O que torna ML-KEM pós-quântico?**  Sua segurança se baseia em problemas de
reticulados para os quais não há quebra quântica conhecida equivalente a Shor.

**A chave pública entra nos 837 B?**  Não. O modelo de `MISSION` contabiliza o
ciphertext ML-KEM de 768 B, não a chave pública de 800 B.

**O segredo viaja?**  Não. Viaja o ciphertext KEM; cada papel deriva o segredo.

**AES-GCM já detecta alteração; por que CRC?**  AES-GCM oferece autenticação
criptográfica. CRC32 foi mantido como guardião didático de corrupção acidental
e para medir o acréscimo de 4 B.

**HMAC ainda é usado?**  Sim, em confirmação de chave de bancada. Não é a
autenticação principal de `MISSION`.

### 18.3 Falhas

**Vocês usaram radiação real?**  Não. Injetamos XOR de um bit.

**CRC32 detecta qualquer erro?**  Ele detecta todo single-bit flip dentro da
região coberta. A afirmação não deve ser generalizada para qualquer padrão de
erro ou atacante.

**ML-KEM rejeita todo ciphertext corrompido?**  Não como um erro simples
observável. A decapsulação produz um segredo; o harness compara segredos e a
confirmação pode rejeitar a sessão.

**Qual a diferença entre KEY_MISMATCH e PROTOCOL_REJECT?**  O primeiro é
observação do harness. O segundo é decisão operacional baseada em confirmação.

**Por que não testar bursts?**  Foi um recorte controlado de single-bit. Bursts
são extensão futura necessária para comparar códigos de detecção.

### 18.4 Resultados

**Qual é o número mais importante?**  Use a razão ECDH/ML-KEM da nova bateria;
os valores 23,2x e 12,1x são históricos porque o baseline antigo não tinha ECDH.

**Por que PQC+CRC às vezes parece mais rápido que PQC?**  Variação natural. O
subtempo de CRC é positivo; não há aceleração causada pelo checksum.

**Por que os bytes crescem tanto?**  Em `MISSION`, principalmente pelo
ciphertext ML-KEM de 768 B. No handshake completo de sessão entram também a
chave pública de 800 B, totalizando 1.568 B.

**A RAM foi o gargalo?**  Não na coleta. A heap permaneceu estável; tempo e
tráfego dominaram.

**O que significa zero falhas?**  Zero comandos falharam na campanha. Isso não
é prova de segurança nem ausência de vulnerabilidades.

**Por que 100 amostras por cenário?**  Para observar distribuição e reduzir o
peso de uma execução isolada. Uma análise mais forte ainda poderia aumentar
amostras e controlar temperatura e ordem.

**Por que usar média?**  A média resume custo; mediana, mínimo, máximo, desvio e
p95 devem ser consultados no JSON para analisar dispersão.

### 18.5 Hardware e metodologia

**O que roda na placa?**  Sensores, ML-KEM, KDF, AES-GCM, CRC, mutação e
medição.

**O que roda no notebook?**  Dashboard, bridge, visualização e consolidação.

**O dashboard calcula PQC?**  Não.

**Por que 80 MHz?**  Para criar um perfil controlado de CPU reduzida e observar
sensibilidade temporal.

**Isso representa todo OBC 1U?**  Não.

**A energia foi medida?**  Não. É necessário instrumento externo.

**Os resultados são reproduzíveis?**  O runner, perfis, comandos, payload e
JSON são registrados. Hardware, temperatura e revisão de firmware ainda devem
ser documentados em cada repetição.

### 18.6 Perguntas de banca mais críticas

**A comparação CLASSIC/PQC é justa?**  No benchmark de sessão, ambos rodam na
mesma placa, em Release e 240 MHz, alimentam o mesmo KDF/AES-GCM e reutilizam a
sessão pelo mesmo N. O handshake completo contabiliza 130 B em P-256, 64 B em
X25519 e 1.568 B em ML-KEM-512; certificados, rede e autenticação de identidade
não são medidos.

**CRC dentro de AES-GCM é redundante?**  Como defesa criptográfica, sim. Como
instrumento de diagnóstico e narrativa de corrupção acidental, ele mede uma
propriedade diferente.

**Uma única placa invalida o protocolo?**  Não para medir custo local e fluxo
lógico, mas limita conclusões sobre rede, sincronização e interoperabilidade.

**Como sabem que AES-GCM realmente cifrou?**  O firmware registrou
`cipher=AES-128-GCM`, sucesso AEAD e CRCs distintos de nonce, ciphertext e tag
em 600 mensagens com plaintext fixo.

**Como sabem que ML-KEM é real?**  O backend vendorizado executa os tamanhos e
operações de ML-KEM-512, passou KAT e produziu tempos reais no hardware.

**Biblioteca vendorizada é garantia de segurança?**  Não. Garante
reprodutibilidade da revisão usada; auditoria e atualização continuam sendo
necessárias.

### 18.7 Implementação e termos da tela

**Qual biblioteca ML-KEM foi usada?**  `mlkem-native` v1.1.0, revisão
`d2cae2b`, vendorizada em `firmware/lib/mlkem_native` e configurada para
ML-KEM-512.

**Por que não implementar ML-KEM do zero?**  Uma implementação própria
aumentaria muito o risco criptográfico e desviaria o experimento para outro
problema. A biblioteca vendorizada fixa a revisão e permite KAT e build
reproduzíveis, embora não elimine a necessidade de auditoria.

**O firmware gera um par ML-KEM por mensagem?**  `MISSION PQC` inclui KeyGen
em cada demonstração isolada. `SESSION_BENCH` faz o modelo de produção:
KeyGen/Encaps/Decaps/KDF uma vez e depois 1, 100, 500 ou 1000 mensagens com a
mesma sessão AES-GCM e nonces únicos.

**O baseline CLASSIC distribui a chave?**  Ele não copia uma chave pronta.
P-256 e X25519 geram pares reais, serializam e validam as chaves públicas,
calculam o segredo em cada ponta e aplicam a KDF. Como os dois papéis rodam na
mesma placa, latência de rede e autenticação de identidade ficam fora do escopo.

**Qual protocolo liga dashboard e placa?**  Linhas seriais versionadas, como
`V1|request_id|COMMAND|...`, seguidas de respostas correlacionadas com campos
`key=value`. O `request_id`, parser e timeout evitam confundir respostas.

**O JSON contém segredos?**  Não contém chave privada nem segredo
compartilhado completo. Ele guarda tamanhos, tempos, estados e CRCs curtos
úteis para auditoria, sem material suficiente para reconstruir a sessão.

**A implementação foi auditada contra side-channel?**  Não. Há limpeza de
buffers e comparações em tempo constante em pontos relevantes, mas isso não é
uma avaliação completa de tempo, cache, potência ou emissão eletromagnética.

**O que significa `SAT CONECTADO`?**  O dashboard recebeu handshake válido da
Wisdom e pode encaminhar comandos reais.

**O que significa `AGUARDANDO SAT` ou `SAT OFF`?**  Não há sessão serial
validada. A interface deve recusar a missão em vez de inventar métricas.

**O que significam `GUARD: NONE` e `GUARD: CRC32`?**  Indicam qual guardião
será usado no ensaio manual de bit-flip do payload.

**Por que os popups são arrastáveis?**  Para permitir comparação lado a lado
em tela grande. Em resolução menor, a comparação sequencial é mais legível.

**O que a faixa de RAM mostra?**  Consumo observado de heap em relação ao total
disponível. `heap` é o livre após a operação; `min_heap` é o menor livre desde
o boot, não uma medição isolada de pico de cada chamada.

### 18.8 Números, amostragem e interpretação

**Quantas vezes cada cenário rodou?**  Na bateria oficial, 100 vezes por
cenário em cada perfil: 3 cenários × 100 × 2 perfis = 600 `MISSION`.

**Quantos testes de falha ocorreram?**  Foram 200 `FAULT NONE` e 200
`FAULT CRC32`, totalizando 400 nos dois perfis.

**Por que medir em microssegundos?**  Milissegundos esconderiam parte da
diferença entre fases curtas. O timer do firmware permite decompor RNG, KDF,
AES-GCM, CRC e operações ML-KEM.

**O tempo inclui USB ou rede?**  `elapsed_us` de `MISSION` mede o fluxo no
firmware, não latência USB, renderização do dashboard, rádio ou propagação.

**O que exatamente entra em `bytes_total`?**  Ciphertext da mensagem, nonce e
tag; em `CLASSIC`, a chave pública ECDH do emissor (65 B); em PQC, o ciphertext
ML-KEM (768 B); em `PQC_CRC32`, mais 4 B no plaintext cifrado. Não entram a
chave pública do receptor, cabeçalho USB, rádio, FEC ou framing de missão.

**O que significam `key_match=1`, `aead_match=1` e `crc_match=1`?**
Respectivamente: os segredos comparados coincidiram; AES-GCM autenticou e
recuperou os bytes esperados; o CRC armazenado coincidiu com o recalculado.

**Por que `tag_match` e `aead_match` parecem iguais?**  `tag_match` foi mantido
como alias de compatibilidade. Na versão atual, `aead_match` deixa mais claro
que a verificação inclui autenticação e recuperação correta do plaintext.

**PQC é sempre mais lento ou maior?**  Não se generaliza. Algoritmo,
plataforma, otimização, payload e protocolo mudam o resultado. A afirmação
válida é sobre esta integração e esta metodologia.

**Por que confiar nos números?**  Eles vêm de respostas da placa registradas
com comando, perfil e payload em JSON; o runner verifica campos obrigatórios,
contagens e falhas. Isso dá rastreabilidade, não validade universal.

### 18.9 Escala, segurança de sistema e próximos passos

**FIPS 203 certifica esta placa?**  Não. FIPS 203 especifica ML-KEM. Usar uma
implementação compatível com o algoritmo não certifica produto, firmware,
gerador aleatório ou sistema completo.

**O que significa categoria 1?**  É a categoria NIST mais leve da família,
referenciada à classe de esforço para atacar AES-128. Não significa igualdade
direta de algoritmos nem “128 bits medidos” pelo projeto.

**Computadores quânticos já quebram RSA hoje?**  Não há computador quântico
tolerante a falhas em escala para isso. A migração é preventiva por causa do
tempo de adoção e do risco de capturar dados hoje para decifrar no futuro.

**Por que AES-128 ainda aparece em um projeto pós-quântico?**  A principal
ameaça de Shor recai sobre chave pública. Cifras simétricas continuam úteis;
ataques quânticos genéricos alteram margens e escolha de parâmetros, mas não
transformam AES em um problema de fatoração ou logaritmo discreto.

**O protocolo tem identidade, certificado e anti-replay?**  Não. O protótipo
mede estabelecimento de chave e entrega local. Autenticação de identidade,
contadores de replay, provisionamento e rotação são próximos passos para um
protocolo de missão.

**O que acontece com payload maior?**  O custo fixo do encapsulamento ML-KEM
permanece; ciphertext AES-GCM e custo de processamento crescem com o payload.
É necessário repetir a bateria para diferentes tamanhos antes de extrapolar.

**Isso escala para um enlace espacial?**  O padrão híbrido é aplicável, mas o
protótipo não mede rádio, perda de quadros, MTU, fragmentação, FEC, atraso ou
energia. Esses fatores podem tornar os 768 B do ciphertext KEM ainda mais
relevantes.

**Qual seria o próximo experimento mais forte?**  Duas placas, autenticação das
chaves públicas, vários payloads, ordem aleatorizada, medição elétrica, falhas
em rajada, anti-replay e repetição em múltiplas unidades.

**Qual é a conclusão se a heap ficou estável?**  RAM não foi o gargalo
observado. Isso fortalece a conclusão específica de que tempo e comunicação
dominaram; não elimina outras restrições de sistemas embarcados.

### 18.10 Respostas de emergência em uma frase

- “ML-KEM estabelece; AES-GCM cifra e autentica.”
- “CRC32 detecta erro acidental, não autentica atacante.”
- “CLASSIC usa ECDH P-256; PQC usa ML-KEM-512; ambos alimentam AES-GCM.”
- “80 MHz é perfil experimental, não especificação de CubeSat.”
- “Medimos tempo e heap; não medimos energia elétrica.”
- “O bit-flip é lógico e determinístico, não radiação física.”
- “Os números são reais desta placa, mas não universais.”
- “Entra a chave pública ECDH do emissor ou o ciphertext ML-KEM; não entra a chave pública do receptor.”
- “Zero falhas de comando não significa prova de segurança.”
- “Sem hardware validado, a interface não deve fabricar a missão.”

## 19. Plano de contingência

### 19.1 Placa não aparece

1. confira cabo e `/dev/ttyUSB0`;
2. feche console serial concorrente;
3. confirme permissão do dispositivo;
4. reinicie o dashboard;
5. não finja métricas reais em `--simulated`.

### 19.2 `AGUARDANDO SAT`

O handshake não foi aceito. Mostre onboarding e resultados consolidados, mas
declare que a demo ao vivo está indisponível.

### 19.3 Sensor retorna `NA`

Explique operação degradada. Use payload fixo se necessário.

### 19.4 Popup cobre conteúdo

Arraste pelo topo, pause a animação ou feche cenários anteriores. Em 1366×768,
prefira comparação sequencial.

### 19.5 Comando demora

Não clique repetidamente. Aguarde a resposta serial. `STRESS` pode demorar e é
opcional.

### 19.6 Ping físico não aparece

O evento requer firmware atualizado. Não interrompa a narrativa; o ping é
easter egg, não evidência científica.

## 20. Checklist de ensaio e operação

### 20.1 Validação de software

```bash
python3 -m py_compile dashboard.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import dashboard"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
git diff --check
```

### 20.2 Compilação de firmware

```bash
pio run
```

Compilar não grava a placa. Upload é uma operação separada:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
```

### 20.3 Preflight da apresentação

- projetor em 1920×1080 ou 1366×768;
- fonte legível à distância;
- Wisdom reconhecida;
- firmware correto gravado;
- `SAT CONECTADO`;
- perfil `BASELINE` para a demo principal;
- payload vivo testado;
- três cenários testados uma vez;
- `FALHA` com e sem CRC testada;
- botão físico/ping testado, se for usado;
- JSON oficial disponível localmente;
- sem terminal concorrendo pela serial;
- modo de contingência ensaiado.

### 20.4 Ensaio oral

O aluno deve conseguir responder sem consultar:

1. diferença entre ML-KEM e AES-GCM;
2. diferença entre CRC32 e autenticação;
3. como ECDH P-256 e ML-KEM estabelecem a chave;
4. por que entram 65 B ECDH ou 768 B ML-KEM em `bytes_total`;
5. por que PQC+CRC pode variar no tempo;
6. o que 80 MHz representa;
7. por que energia não foi medida;
8. diferença entre `KEY_MISMATCH` e `PROTOCOL_REJECT`;
9. três números principais da bateria;
10. três limitações científicas.

## 21. Nova bateria de resultados

Não execute bateria longa durante o seminário. Para a comparação justa de
sessão ECDH/ML-KEM, depois de regravar o firmware, use:

```bash
python3 tools/session_benchmark.py \
  --port /dev/ttyUSB0 \
  --timeout 20 \
  --repeats 10 \
  --pause 0.25
```

Esperado: `summary.ok=true`, `summary.session_runs=120`,
`summary.invalid_session_runs=0` e
`logs/<timestamp>_session_benchmark_dev-ttyusb0.json`. O runner só aceita
240 MHz/BASELINE, rotaciona a ordem dos algoritmos e imprime a tabela:

```text
Modo | Setup us | AES-GCM medio us | N | Amortizado us/msg | Handshake B | Heap watermark B | Flash B
```

Sem abrir a serial, confira com
`python3 tools/session_benchmark.py --dry-run --repeats 10`.

Para regressão completa de AES-GCM, falhas e os dois perfis, use a bateria
abaixo. Ela não deve ser usada como única fonte para latência de sessão:

```bash
python3 tools/aes_gcm_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --timeout 12 \
  --cycles 100 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

Esperado:

```text
summary.aes_gcm.checks.official_candidate=true
summary.aes_gcm.checks.aead_failures=0
summary.aes_gcm.checks.non_aes_gcm_records=0
summary.aes_gcm.checks.ecdh_invalid_records=0
summary.aes_gcm.checks.pqc_invalid_records=0
summary.aes_gcm.checks.balanced_scenarios=true
summary.mission_runs=600
summary.pqc_bench_runs=6
summary.fault_runs=400
logs/<timestamp>_aes_gcm_metrics_dev-ttyusb0.json
```

O runner alterna automaticamente entre `BASELINE` e `OBC-1U-LIMITED` e
retorna a placa para `BASELINE` no cleanup.

Depois da coleta, consolide o JSON validado para a tela `RESULTADOS`:

```bash
python3 tools/consolidate_metrics.py --file logs/<timestamp>_aes_gcm_metrics_dev-ttyusb0.json
```

Antes da coleta longa, valide o plano sem abrir a serial:

```bash
python3 tools/aes_gcm_metrics_battery.py \
  --dry-run --cycles 100 --bench-repeats 3 --bench-rounds 100
```

`tools/final_metrics_battery.py` continua disponível como bateria geral, mas
não verifica todos os campos específicos que qualificam a coleta ECDH/ML-KEM
como fonte oficial. Para repetir essa bateria de regressão com os dois perfis,
use:

```bash
python3 tools/final_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --timeout 12 \
  --cycles 100 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

O resumo esperado é `ok=true`, `failed=0`, `mission_runs=600`,
`pqc_bench_runs=6` e `fault_runs=400`. Tanto esse runner quanto o dedicado a
AES-GCM executam `BASELINE` a 240 MHz e `OBC-1U-LIMITED` a 80 MHz; não é
necessário iniciar uma bateria separada por frequência.

Depois da coleta, atualize primeiro `docs/METRICAS_CONSOLIDADAS.md`, depois os
números deste guia e, por fim, as constantes de `RESULTADOS` no dashboard.

## 22. Folha de consulta rápida

### Projeto

```text
Placa: BlackBoard Wisdom / ESP32
PQC: ML-KEM-512
Cifra: AES-128-GCM
Guardião: CRC32
Perfis: 240 MHz e 80 MHz experimental
Transporte da bancada: USB serial, sem rádio
```

### Cenários

```text
CLASSIC    = ECDH P-256 efêmero -> chave AES -> AES-GCM
PQC        = ML-KEM -> chave AES -> AES-GCM
PQC+CRC32  = ML-KEM -> AES-GCM(payload || CRC32)
```

### Tamanhos

```text
pk ML-KEM: 800 B
sk ML-KEM: 1632 B
ct ML-KEM: 768 B
ss ML-KEM: 32 B
nonce GCM: 12 B
tag GCM: 16 B
CRC32: 4 B
chave pública ECDH P-256: 65 B
MISSION ECDH: nova bateria pendente
```

### Resultados

```text
Resultados de 2026-07-02: históricos pré-ECDH
Comparação ECDH/ML-KEM: preencher após a nova bateria oficial
Falhas: 200/200 SILENT sem CRC; 200/200 detectadas com CRC
```

### Limites

```text
não é CubeSat real
não há radiação real
não há rádio
energia não foi medida
ECDH e ML-KEM são executados na mesma Wisdom e alimentam o mesmo AES-GCM
80 MHz não é especificação universal
```

### Fechamento

> ECDH P-256 e ML-KEM-512 estabelecem a chave na Wisdom; AES-GCM protege a
> mensagem; CRC32 torna a corrupção acidental visível. O resultado é uma
> demonstração reproduzível de que segurança pós-quântica em hardware limitado
> é possível, porém precisa entrar no orçamento do sistema.

## 23. Glossário

| Termo | Definição curta |
|---|---|
| AEAD | cifragem autenticada |
| AES-GCM | cifra simétrica com tag de autenticação |
| COTS | componente comercial de prateleira |
| CRC32 | código de detecção de erro de 32 bits |
| ciphertext | dado cifrado ou encapsulamento transmitido |
| decap | recuperação do segredo KEM com chave privada |
| encap | criação de ciphertext KEM e segredo com chave pública |
| ECDH | acordo de chave clássico em curva elíptica |
| FIPS 203 | padrão NIST de ML-KEM |
| HMAC | autenticação de mensagem baseada em hash e chave |
| KAT | teste com resposta conhecida |
| KDF | função de derivação de chave |
| KEM | mecanismo de encapsulamento de chave |
| ML-KEM | KEM pós-quântico baseado em reticulados |
| nonce | valor único por uso de uma chave |
| OBC | computador de bordo |
| payload | dados úteis da mensagem |
| plaintext | dados antes da cifragem |
| PQC | criptografia pós-quântica |
| tag | valor de autenticação |

## 24. Fontes técnicas e arquivos de apoio

Use este guia para estudar e apresentar. Use os arquivos abaixo apenas para
aprofundamento operacional ou auditoria:

| Fonte | Papel |
|---|---|
| `docs/METRICAS_CONSOLIDADAS.md` | metodologia, estatísticas e comandos de coleta |
| `docs/hardware_command_reference.md` | comandos completos de bancada |
| `docs/hardware_blackboard_wisdom.md` | inventário e bring-up da placa |
| `docs/ROADMAP.md` | histórico de decisões e critérios |
| `docs/projeto_final_pqc_esp32_cubesat.docx` | objetivo acadêmico formal |
| log AES-GCM oficial | evidência bruta principal |

Referências conceituais centrais:

- NIST FIPS 203 — ML-KEM;
- NIST FIPS 197 — AES;
- NIST SP 800-38D — GCM;
- documentação e licença da revisão vendorizada de `mlkem-native`;
- literatura de CRC para redes e sistemas embarcados;
- literatura de efeitos de radiação em eletrônica espacial.
