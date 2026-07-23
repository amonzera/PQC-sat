# Guia final de estudo e apresentação — PQC-SAT

Este é o artefato central de preparação do seminário. Ele substitui o antigo
guia didático, o roteiro separado, o banco isolado de perguntas e respostas e
o documento separado de algoritmos. O objetivo é permitir que um aluno leia do
começo ao fim, compreenda o projeto com profundidade, ensaie a demonstração e
responda perguntas sem superestimar o que foi implementado.

Estado documental: 2026-07-23. O jogo público agora compara ECDH P-256 e
ML-KEM-512 sob `KEX_FAIR_V1`, usando o mesmo wolfCrypt, HKDF-SHA256 e
AES-128-GCM. O firmware desta revisão ainda precisa ser gravado e validado
fisicamente; não o apresente como concluído antes dos gates de
`docs/stand/FINAL_VALIDATION.md`.

> Aviso de transição científica: os números da bateria de 2026-07-02 medem o
> legado `CLASSIC` (chave AES local) versus `PQC` (ML-KEM). Eles permanecem
> úteis como histórico de engenharia, mas não são resultados ECDH versus
> ML-KEM. Até a bateria `tools/kex_metrics_battery.py` produzir um JSON
> `pqc-sat-kex-fair-metrics-v2` aceito, não use as razões 23,2x, 39,1x ou 12,1x
> como conclusão da nova pesquisa.

## 1. Como estudar este documento

Faça três passagens:

1. **Compreensão:** leia as seções 2 a 11 sem tentar decorar números.
2. **Defesa:** estude as seções 12 a 16 e explique cada conceito em voz alta.
3. **Ensaio:** execute as seções 17 a 20 com a placa e o projetor.

Se houver pouco tempo, leia nesta ordem:

1. seção 2, resumo de um minuto;
2. seção 2, o contrato ECDH/ML-KEM;
3. `docs/METRICAS_CONSOLIDADAS.md`, protocolo da nova coleta;
4. seção 17, roteiro de 20 minutos;
5. seção 17.5, roteiro externo do jogo por fases;
6. seção 18, perguntas difíceis;
7. seção 22, folha de consulta rápida.

## 2. O projeto em um minuto

O PQC-SAT é uma demonstração didática executada em uma RoboCore BlackBoard
Wisdom com ESP32. A placa representa um computador de bordo, ou OBC,
educacional inspirado em CubeSats. Ela não é um CubeSat real nem equipamento
certificado para voo.

A mesma mensagem é processada em dois caminhos de estabelecimento, cada um
com guardião `NONE` ou `CRC32`:

| Cenário | Estabelecimento de segredo | Componentes comuns |
|---|---|---|
| `ECDH` | ECDH P-256 efêmero | wolfCrypt RNG + HKDF-SHA256 + AES-128-GCM |
| `MLKEM` | ML-KEM-512 efêmero | wolfCrypt RNG + HKDF-SHA256 + AES-128-GCM |

O projeto responde a duas perguntas:

1. Quais custos de tempo, memória e comunicação são observados ao comparar
   ECDH P-256 e ML-KEM-512 sob a mesma implementação e configuração?
2. Como tornar visível uma corrupção acidental de um bit no payload?

Ainda não existe bateria oficial para o novo contrato. O experimento registra
setup do receptor, operação do iniciador, operação do receptor, HKDF,
AES-GCM, heap e bytes públicos. A ordem ECDH/ML-KEM alterna por ciclo para
reduzir deriva temporal. Os resultados só serão apresentados depois do flash,
smoke e coleta controlada na Wisdom.

Resposta curta recomendada:

> Comparamos ECDH P-256 e ML-KEM-512 no mesmo wolfCrypt e fazemos os dois
> segredos passarem pelo mesmo HKDF e AES-GCM. Assim medimos algoritmo mais
> implementação, compilador, hardware e configuração, sem fingir que o
> baseline AES local era ECDH. O CRC32 continua sendo um instrumento didático
> de corrupção acidental, não autenticação.

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

> Quais custos de tempo, memória e comunicação são observados ao estabelecer
> uma sessão efêmera com ECDH P-256 ou ML-KEM-512, usando o mesmo wolfCrypt,
> HKDF-SHA256 e AES-128-GCM, em uma Wisdom/ESP32 a 240 MHz e 80 MHz?

### 4.2 Hipóteses

- **H1:** `MLKEM` terá maior material público total que `ECDH`.
- **H2:** os tempos de setup, iniciador e receptor diferirão entre os KEX; a
  direção e a magnitude serão afirmadas somente após a coleta.
- **H3:** limitar a CPU a 80 MHz aumentará o custo temporal, sem alterar os
  tamanhos do protocolo.
- **H4:** CRC32 acrescentará 4 bytes e detectará todo single-bit flip dentro da
  região de payload coberta.
- **H5:** o impacto mais visível será tempo e tráfego, não exaustão de heap.

### 4.3 O que o projeto demonstra

- integração funcional de ML-KEM-512 real no ESP32;
- entrega de mensagem com AES-128-GCM;
- custo relativo de ECDH P-256 e ML-KEM-512 no hardware usado;
- efeito do perfil de 80 MHz;
- diferença entre corrupção silenciosa e erro detectado;
- confirmação operacional de divergência de chave em ensaio de bancada.

### 4.4 O que o projeto não demonstra

- certificação espacial;
- resistência física à radiação;
- consumo elétrico real;
- segurança universal de todo CubeSat;
- comparação completa entre ECDH e ML-KEM;
- proteção contra *side-channel*;
- protocolo de missão completo com gestão permanente de identidades e chaves;
- prova matemática da segurança de ML-KEM.

## 5. Arquitetura do sistema

```text
┌──────────────────────── notebook ────────────────────────┐
│ dashboard.py                                             │
│  - jogo público em 14 estados                            │
│  - cartão seleciona; controle contextual ou D27 confirmam│
│  - métricas GAME_* e log JSONL v2                        │
│  - sem simulação de produção                             │
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

Sem handshake válido da Wisdom, o programa mantém somente o standby de busca;
a abertura narrativa e o jogo não são liberados.
A execução pública não possui modo simulado; fixtures existem apenas nos
testes e nunca produzem métricas oficiais.

### 5.2 Payload da missão

O visitante escolhe um dos três payloads ASCII fixos e reproduzíveis. A Wisdom
recebe o hexadecimal correspondente em `GAME_BEGIN`; não há editor de texto ou
payload sintético criado pelo dashboard.

Os cartões atuais são telemetria crítica, comando de emergência e atualização
de configuração. Prioridade, prazo e consequência pertencem ao contexto
didático; não são dados de uma missão em voo.

### 5.3 Evento do botão físico

O firmware possui debounce e emite `BUTTON_PING` quando o botão da Wisdom é
pressionado. O standby não usa botão e sai automaticamente pelo handshake. Na
abertura narrativa, `INICIAR MISSÃO` ou D27 abrem diretamente as escolhas. No
jogo iniciado por `python3 dashboard.py`, cartão seleciona e o controle
contextual ou D27 confirmam. A resposta serial e a animação apenas liberam a
próxima confirmação.

Antes do jogo, confirme que a revisão anuncia `game=STAGED_V1`, inclui a
leitura `pot` no evento e foi gravada/validada na placa. Compilar o código não
equivale a gravá-lo. Confirme o D27 físico na abertura narrativa e durante a
partida; não use teclado ou fixture para fingir hardware.

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

O segredo ML-KEM tem 32 bytes. O firmware deriva dele uma chave AES-128 de 16
bytes usando HMAC-SHA256 e o contexto
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
  -> RNG gera chave AES efêmera e nonce
  -> AES-128-GCM cifra e gera tag
  -> receptor verifica tag e decifra
  -> DELIVERED se AEAD confere
```

Esse é um baseline simétrico barato. Não é ECDH, RSA nem uma pilha clássica
assimétrica completa.

Para o payload de 41 B da bateria oficial:

```text
41 B payload + 12 B nonce + 16 B tag = 69 B
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
- `setup_us`, `initiator_us`, `responder_us`: papéis comparáveis dos dois KEX;
- `keygen_us`, `encap_us`, `decap_us`: aliases didáticos e métricas do legado;
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

Fonte histórica AES-GCM do protocolo legado:

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

## 11. Resultados históricos do protocolo legado

As tabelas desta seção documentam `CLASSIC/PQC` antes de `KEX_FAIR_V1`. Elas
podem sustentar regressão e histórico de engenharia, mas não a comparação
ECDH/ML-KEM. Até a coleta FAIR, não há tabela numérica oficial para a pergunta
de pesquisa atual.

### 11.1 `MISSION` legado em 240 MHz

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

### 11.2 `MISSION` legado em 80 MHz

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

### 11.3 Razões históricas, proibidas como resultado FAIR

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

## 12. Como ler a interface única

### 12.1 Cabeçalho e progresso

Depois do handshake, a interface pública não repete marca, conexão ou atos. O
único cabeçalho identifica a tela ativa, por exemplo `ESCOLHA 2/4 • CPU` ou
`CHECKPOINT 3/4 • TRANSMITIR`.

A Terra em rotação e o satélite sorridente em órbita formam um mundo
procedural persistente; a torre sobre o planeta foi removida. Nas escolhas,
cada cartão quadrado tem um desenho próprio e um título em destaque, sem
subtítulo interno; a explicação aparece somente depois que o visitante
seleciona a opção. A faixa de loadout mostra missão, CPU, chave e CRC somente
depois de cada confirmação.

### 12.2 Cartões de escolha

Em `SELECT_MISSION`, `SELECT_PROFILE`, `SELECT_KEY_MODE`, `SELECT_GUARD`,
`DIAGNOSE` e `SELECT_RESPONSE`, toque no cartão apenas o destaca. A seleção
pode ser trocada até a confirmação. O cartão mantém somente arte e título; o
efeito científico da opção selecionada surge abaixo do conjunto e o botão
contextual aparece quando a escolha está pronta. Depois da confirmação não
existe “voltar”.

### 12.3 Checkpoints reais

`PREPARE`, `PROTECT`, `TRANSMIT`, `VERIFY` e `RETRY` mostram resposta real da
Wisdom e uma animação didática ampliada. Enquanto comando ou animação estiver
pendente, verde e D27 não avançam. Tempo, bytes e heap não vêm da animação.

Antes de a resposta serial passar pelo parser, não há encenação do trabalho:
a interface mostra uma espera estática. Só depois da validação ela reconstrói
didaticamente o que ocorreu. Em `PROTECT`, os subtimings reais distribuem as
etapas visuais quando estão presentes; em `VERIFY`, cada portal recebe o valor
real de `GameResult`.

Depois de completar a reprodução automática, a mensagem recebe contorno verde
e vira o controle da explicação. Segure-a e arraste para a entrada ou para uma
estação. Cada parada mostra o que entra, o que acontece, o que sai e a evidência
real. Voltar a mensagem só volta a explicação: não desfaz operação, não altera
resultado e não bloqueia novamente a confirmação.

Ordens lógicas dos caminhos FAIR:

```text
ECDH:  CHAVE PÚBLICA DO RECEPTOR -> CHAVE/PONTO DO INICIADOR
       -> SEGREDO NO RECEPTOR -> HKDF -> AES-GCM
MLKEM: CHAVE PÚBLICA DO RECEPTOR -> ENCAP/CÁPSULA
       -> DECAP/SEGREDO NO RECEPTOR -> HKDF -> AES-GCM
AMBOS: CRC opcional -> CRC DO QUADRO -> CANAL
       -> GCM -> CRC DA APLICAÇÃO -> RESULTADO
```

### 12.4 Encerramento

`DEBRIEF` revela a causa, compara a hipótese do visitante, separa entrega,
detecção, custo e diagnóstico e oferece um contrafactual qualitativo. Não há
nota ou ranking. A mensagem pode ser arrastada pela revisão completa de
preparar, proteger, transmitir, verificar e eventual retransmissão. Os
os resultados históricos e o estado da coleta FAIR continuam neste guia e em
`docs/METRICAS_CONSOLIDADAS.md`; a partida pública não atualiza estatísticas.

### 12.5 Superfície técnica separada

Comandos de inventário, sensores, `MISSION`, `FAULT`, `INVESTIGATE`, benchmark
e stress permanecem em `tools/serial_console.py` e scripts de bancada. Eles não
possuem console visual, botões ou segundo dashboard.

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

`CLASSIC` usa AES-GCM com chave efêmera local. Ele não inclui ECDH, certificado
ou troca assimétrica. Portanto, a comparação mede o custo de adicionar ML-KEM
ao baseline simétrico, não uma disputa completa ECDH versus ML-KEM.

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
| “PQC é inviável.” | “PQC foi funcional, com custo maior.” |
| “CLASSIC é ECDH.” | “CLASSIC é baseline simétrico AES-GCM.” |
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
> A coleta anterior mostrou que ML-KEM cabe na placa e que o custo depende
> fortemente do perfil, mas o baseline era uma chave AES local, não ECDH. Por
> isso, os números antigos ficam como histórico. A conclusão quantitativa nova
> só será formulada depois da bateria pareada ECDH/ML-KEM no wolfCrypt.

## 17. Roteiro de apresentação de 20 minutos

### 17.1 Antes de começar

1. Feche programas que possam usar `/dev/ttyUSB0`.
2. Conecte a Wisdom.
3. Confirme firmware e permissões.
4. Abra o dashboard:

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

5. Aguarde o standby desaparecer e a abertura narrativa surgir.
6. Confirme D27 e A39 antes da entrada do público.
7. Não inicie bateria longa durante a apresentação.

### 17.2 Distribuição de tempo

| Tempo | Conteúdo |
|---|---|
| 0–2 min | provocação e problema |
| 2–5 min | ameaça quântica e arquitetura híbrida |
| 5–7 min | três cenários e hipóteses |
| 7–13 min | demo ECDH, ML-KEM e CRC opcional |
| 13–15 min | falha silenciosa versus detectada |
| 15–18 min | metodologia FAIR e resultados, somente se a coleta estiver aceita |
| 18–20 min | limites, próximos passos e perguntas |

### 17.3 Abertura

Pergunte:

> Se um computador de bordo pequeno precisar migrar para criptografia
> pós-quântica, o que cresce mais: tempo, bytes ou RAM?

Explique que a resposta será observada na placa, não apenas estimada.

### 17.4 Condução da interface única

Faça uma partida de 2–3 minutos com o roteiro abaixo. Depois da partida,
explique os campos medidos e o desenho pareado. Enquanto a coleta FAIR estiver
pendente, não anuncie razão de velocidade ou bytes entre ECDH e ML-KEM. Não
trate uma partida pública como nova amostra estatística.

Feche com:

> PQC não foi inviável: funcionou. Mas segurança altera o orçamento do sistema.
> Em hardware limitado, tempo e tráfego precisam ser decisões de arquitetura,
> não detalhes adicionados no final.

### 17.5 Roteiro externo do jogo por fases (2–3 minutos)

Este roteiro pertence ao apresentador. A tela mantém textos públicos curtos e
não deve receber notas F12. Abra com:

```bash
python3 dashboard.py --port /dev/ttyUSB0 --restart-on-crash
```

Em hardware, toque no cartão somente destaca uma opção; espere a tela liberar
e use a faixa verde ou peça um novo D27 em cada linha. Não antecipe o incidente.

| Fase | Frase do apresentador | Pergunta ao visitante | Conceito teórico | Animação esperada | Resposta segura | Afirmação proibida |
|---|---|---|---|---|---|---|
| `ATTRACT` | “Vamos acompanhar uma mensagem real processada pela Wisdom.” | “Pronto para assumir a missão?” | busca automática; abertura por `INICIAR MISSÃO` ou D27 | Terra, CubeSat e chamada mínima; segue direto às escolhas | “Ainda não há resultado; o `HELLO` só confirmou a capacidade.” | “A placa está pronta” sem `game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` |
| `SELECT_MISSION` | “Escolha qual consequência você quer proteger.” | “Qual mensagem tolera menos erro?” | payload, prioridade e prazo | desenhos de telemetria, comando e configuração; o selecionado pulsa | “O prazo é contexto didático, não deadline de voo certificado.” | “A missão representa um satélite real em operação.” |
| `SELECT_PROFILE` | “Agora escolha o ritmo de CPU do experimento.” | “80 MHz deve aumentar qual custo?” | perfil controlado e tempo de CPU | chips ilustrados mostram ritmos distintos, sem ícone de energia | “80 MHz é um perfil experimental; não medimos energia.” | “Todo CubeSat opera a 80 MHz” ou “economizamos energia.” |
| `SELECT_KEY_MODE` | “Escolha como o segredo será estabelecido.” | “ECDH e ML-KEM fazem qual parte da sessão?” | acordo clássico, KEM pós-quântico, KDF e cifra simétrica | pontos ECDH e chave/cápsula ML-KEM percorrem caminhos visuais distintos | “Os dois estabelecem segredo; HKDF deriva e AES-GCM protege a mensagem.” | “ML-KEM criptografa o payload” ou “ECDH usa chave AES pré-compartilhada.” |
| `SELECT_GUARD` | “Decida se o plaintext leva um CRC da aplicação.” | “Um CRC válido prova autenticidade?” | checksum e região coberta | blocos do payload recebem ou não o bloco verde de +4 B | “CRC detecta corrupção acidental; não autentica.” | “CRC impede ataque” ou “CRC substitui GCM.” |
| `PREPARE` | “A Wisdom está serializando exatamente a mensagem escolhida.” | “Onde o CRC entra quando ligado?” | representação em bytes e referência anterior à falha | bytes só surgem durante serialização; CRC muda de previsto para calculando e anexado; depois arraste a mensagem | “A animação está ampliada; os números de recursos ficam reservados ao debrief.” | “Esses segundos são o tempo real da placa.” |
| `PROTECT` | “Agora o segredo é obtido e o AES-GCM protege o pacote.” | “Qual parte muda entre ECDH e ML-KEM?” | setup, iniciador, receptor, HKDF, nonce e tag | pontos ECDH ou chave/cápsula ML-KEM; depois arraste por cada subtiming | “As duas opções usam o mesmo HKDF e AES-GCM; muda o estabelecimento.” | “PQC substitui o AES” ou “a tag é um CRC.” |
| `TRANSMIT` | “Gire A39: ele escolhe o bit; a causa continua escondida.” | “Qual byte e máscara foram selecionados?” | vetor single-bit reproduzível e camada do incidente | a mensagem atravessa as estações; o bit aparece somente no ponto A39 e a revisão não revela a causa | “A falha é injetada por software e ainda não revela sua causa.” | “Observamos radiação real” ou “o potenciômetro mede radiação.” |
| `VERIFY` | “Leia as três camadas na ordem: quadro, GCM e aplicação.” | “Qual foi a primeira evidência que falhou?” | integridade de transporte, autenticação e integridade pós-GCM | indicadores reais são revelados em ordem e podem ser revistos arrastando a mensagem | “O padrão sugere uma camada; não prova a causa física.” | “CRC distingue ataque de radiação.” |
| `DIAGNOSE` | “Forme sua hipótese sem ver a resposta.” | “Canal, adulteração ou memória: qual combina com o padrão?” | inferência por evidências | hipótese apenas recebe destaque | “Você pode mudar a seleção até confirmar no verde ou D27.” | “A tela já identificou definitivamente a origem.” |
| `SELECT_RESPONSE` | “Escolha o que o sistema deveria fazer com este pacote.” | “Aceitar, retransmitir ou pedir modo seguro?” | decisão operacional condicionada à verificação | `ACCEPT` fica bloqueado em rejeição criptográfica | “Pacote criptograficamente rejeitado não pode ser aceito aqui.” | “Modo seguro é uma política universal” ou “retry garante disponibilidade.” |
| `RETRY` | “Vamos retransmitir a mesma mensagem sem repetir material criptográfico.” | “O que precisa mudar e o que precisa permanecer?” | mesmo payload, chave/nonce novos, sem falha injetada | arraste por payload igual, chave nova, nonce novo, proteção e entrega | “O harness confirma fingerprints novos e `DELIVERED`.” | “Reutilizamos o nonce” ou “corrigimos o pacote antigo.” |
| `DEBRIEF` | “Agora podemos revelar a cadeia completa.” | “Seu diagnóstico e sua ação protegeram a missão?” | causalidade, contrafactual e limites | arraste a mensagem pela revisão completa; só aqui o incidente é revelado | “Tempo, bytes e heap são desta partida; não há nota ou ranking.” | “Um acerto prova causalidade física” ou “a demo vira resultado oficial.” |
| `ERROR` | “A partida foi interrompida e nenhum resultado anterior será usado.” | “Podemos repetir depois de um handshake novo?” | falha segura, limpeza de sessão e recuperação | erro estático; sem números reaproveitados | “Reconecte, aguarde `HELLO` novo e confirme pelo controle contextual ou D27.” | “O último resultado ainda vale” ou “clique para pular o erro.” |

No debrief, conduza os quatro blocos nesta ordem: entrega da missão;
detecção/segurança; tempo, bytes e heap; diagnóstico. Leia o contrafactual como
qualitativo — por exemplo, “com CRC ligado esta corrupção pós-GCM seria
detectada” — e não como uma nova medição.

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

**Por que usar ECDH?**  Ele fornece um baseline clássico assimétrico de acordo
de chave. Compará-lo com ML-KEM no mesmo wolfCrypt reduz o viés de biblioteca
que existia quando o baseline era apenas uma chave AES local.

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

**Qual é o número mais importante?**  Ainda não existe um número FAIR oficial.
O resultado principal, quando coletado, será a diferença pareada ML-KEM menos
ECDH em tempo total, tempo online e bytes, sempre com o intervalo de confiança
e a configuração declarada.

**Por que PQC+CRC às vezes parece mais rápido que PQC?**  Variação natural. O
subtempo de CRC é positivo; não há aceleração causada pelo checksum.

**Por que os bytes crescem tanto?**  Principalmente pelo ciphertext ML-KEM de
768 B.

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

**A comparação ECDH/ML-KEM é justa?**  Ela reduz um viés importante porque os
dois KEX, o RNG, o HKDF e o AES-GCM usam o mesmo wolfCrypt, as mesmas flags e a
mesma placa. Ainda assim, todo benchmark mede algoritmo + implementação +
compilador + hardware + configuração; a conclusão deve citar esse contexto.

**CRC dentro de AES-GCM é redundante?**  Como defesa criptográfica, sim. Como
instrumento de diagnóstico e narrativa de corrupção acidental, ele mede uma
propriedade diferente.

**Uma única placa invalida o protocolo?**  Não para medir custo local e fluxo
lógico, mas limita conclusões sobre rede, sincronização e interoperabilidade.

**Como sabem que AES-GCM realmente cifrou?**  O firmware registrou
`cipher=AES-128-GCM`, sucesso AEAD e CRCs distintos de nonce, ciphertext e tag
em 600 mensagens com plaintext fixo.

**Como sabem que ML-KEM é real?**  O caminho FAIR chama as primitivas
ML-KEM-512 do wolfCrypt e valida igualdade de segredo antes de usar AES-GCM.
O KAT e os tempos já observados na placa pertencem ao backend legado; o caminho
FAIR só poderá ser afirmado como validado depois do flash, smoke e bateria v2.

**Biblioteca vendorizada é garantia de segurança?**  Não. Garante
reprodutibilidade da revisão usada; auditoria e atualização continuam sendo
necessárias.

### 18.7 Implementação e termos da tela

**Qual biblioteca ML-KEM foi usada?**  Na comparação FAIR atual, ECDH P-256 e
ML-KEM-512 usam o mesmo wolfCrypt 5.9.2 em configuração portátil. A árvore
local oficial está sob GPLv3 e não é versionada neste Git; uma distribuição
comercial equivalente pode substituí-la sob licença própria. `mlkem-native` v1.1.0,
revisão `d2cae2b`, permanece vendorizado somente para o protocolo legado e
seus resultados históricos.

**Por que não implementar ML-KEM do zero?**  Uma implementação própria
aumentaria muito o risco criptográfico e desviaria o experimento para outro
problema. A biblioteca vendorizada fixa a revisão e permite KAT e build
reproduzíveis, embora não elimine a necessidade de auditoria.

**O firmware gera um par por mensagem?**  `MISSION MLKEM` e `MISSION ECDH`
medem uma sessão nova para uma mensagem. `SESSION_BENCH` estabelece uma sessão
e processa 1, 100, 500 ou 1000 mensagens para medir o custo amortizado. No jogo,
`GAME_PROTECT` estabelece a sessão da partida e `GAME_RETRY` cria material novo.
Um protocolo real ainda precisaria definir ciclo de vida, rotação e proteção
das chaves.

**O baseline CLASSIC distribui a chave?**  Não. A chave efêmera é gerada e
copiada entre os dois papéis lógicos dentro da placa. Por isso ele é referência
simétrica de baixo custo, não protocolo clássico completo.

**Qual protocolo liga dashboard e placa?**  Linhas seriais versionadas, como
`V1|request_id|COMMAND|...`, seguidas de respostas correlacionadas com campos
`key=value`. O `request_id`, parser e timeout evitam confundir respostas.

**O JSON contém segredos?**  Não contém chave privada nem segredo
compartilhado completo. Ele guarda tamanhos, tempos, estados e CRCs curtos
úteis para auditoria, sem material suficiente para reconstruir a sessão.

**A implementação foi auditada contra side-channel?**  Não. Há limpeza de
buffers e comparações em tempo constante em pontos relevantes, mas isso não é
uma avaliação completa de tempo, cache, potência ou emissão eletromagnética.

**O que o handshake `STAGED_V1` significa?**  O programa validou identidade,
protocolo e capacidade do jogo e pode encaminhar comandos reais.

**E se o standby de busca não desaparecer?**  Não há sessão serial validada. O
programa permanece procurando a Wisdom, em vez de inventar métricas.

**O que significam `GUARD: NONE` e `GUARD: CRC32`?**  Indicam qual guardião
foi selecionado para a partida.

**Por que tocar no cartão não avança?** Para separar escolha de confirmação:
o cartão muda `pending_choice`; o controle contextual ou D27 confirmam a fase.
Em `PROTECT`, o controle da tela ainda solicita uma leitura A39 real antes de
avançar.

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
tag; nos cenários PQC, também o ciphertext ML-KEM; em `PQC_CRC32`, mais 4 B
dentro do plaintext cifrado. Não entram chave pública, cabeçalho serial USB,
protocolo de rádio, FEC ou framing de missão.

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

**Qual seria o próximo experimento mais forte?**  Duas placas representando
pontas físicas distintas, vários payloads, ordem aleatorizada, pico de memória
instrumentado por operação, medição elétrica, falhas em rajada, anti-replay e
repetição em múltiplas unidades.

**Qual é a conclusão se a heap ficar estável?**  Apenas que as leituras
observadas não mostraram perda persistente ou novo mínimo global. Como o mínimo
é histórico desde o boot, isso não prova igualdade de pico entre algoritmos.

### 18.10 Respostas de emergência em uma frase

- “ML-KEM estabelece; AES-GCM cifra e autentica.”
- “CRC32 detecta erro acidental, não autentica atacante.”
- “CLASSIC é baseline simétrico, não ECDH.”
- “80 MHz é perfil experimental, não especificação de CubeSat.”
- “Medimos tempo e heap; não medimos energia elétrica.”
- “O bit-flip é lógico e determinístico, não radiação física.”
- “Os números são reais desta placa, mas não universais.”
- “A chave pública não está em `bytes_total`; o ciphertext ML-KEM está.”
- “Zero falhas de comando não significa prova de segurança.”
- “Sem hardware validado, a interface não deve fabricar a missão.”

## 19. Plano de contingência

### 19.1 Placa não aparece

1. confira cabo e `/dev/ttyUSB0`;
2. feche console serial concorrente;
3. confirme permissão do dispositivo;
4. rode `python3 tools/stand_diagnostics.py --check-only`;
5. reinicie `python3 dashboard.py`; sem Wisdom a demonstração ao vivo fica
   indisponível.

### 19.2 `AGUARDANDO SAT`

O handshake não foi aceito. Leia a mensagem de sondagem, corrija porta,
permissão ou firmware e declare que a demo ao vivo está indisponível.

### 19.3 Comando demora

Não clique repetidamente. Aguarde a resposta serial. `STRESS` pode demorar e é
opcional.

### 19.4 Ping físico não aparece

No jogo por fases, D27 é um gate obrigatório: aborte a partida, confirme
`HELLO game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1`,
`DIGITAL BUTTON` e o evento com `pot`. Se não recuperar,
interrompa a demonstração; não há fallback simulado e teclado não substitui o
D27.

## 20. Checklist de ensaio e operação

### 20.1 Validação de software

```text
python3 -m py_compile dashboard.py
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -c "import dashboard"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -m unittest discover
git diff --check
```

### 20.2 Compilação de firmware

```text
python3 tools/firmware_deploy.py
```

Compilar não grava a placa. Upload é uma operação separada:

```text
python3 tools/firmware_deploy.py --upload
```

### 20.3 Preflight da apresentação

- projetor em 1920×1080 ou 1366×768;
- fonte legível à distância;
- Wisdom reconhecida;
- firmware correto gravado e
  `HELLO game=STAGED_V1 kex=FAIR_V1 session_bench=FAIR_SESSION_V1` confirmado;
- `KEX_INFO` confirma wolfCrypt, HKDF-SHA256, AES-128-GCM e perfil portable;
- perfil `BASELINE` para a demo principal;
- três cartões de missão legíveis;
- quatro combinações ECDH/MLKEM × NONE/CRC32 testadas;
- D27 físico e leitura A39 no `BUTTON_PING` testados;
- standby liberado automaticamente somente por
  `HELLO STAGED_V1/FAIR_V1/FAIR_SESSION_V1`;
- abertura narrativa preservada e confirmada por `INICIAR MISSÃO` e D27;
- uma partida pelo verde com `ANALOG POT` validado em `PROTECT`;
- uma partida `GAME_BEGIN` … `GAME_END` com retry testada;
- uma tela de cada checkpoint deixada parada sem avançar sozinha;
- JSON oficial disponível localmente;
- sem terminal concorrendo pela serial;
- procedimento de interrupção sem hardware ensaiado.

### 20.4 Ensaio oral

O aluno deve conseguir responder sem consultar:

1. diferença entre ML-KEM e AES-GCM;
2. diferença entre CRC32 e autenticação;
3. por que `CLASSIC/PQC` são apenas nomes do protocolo legado;
4. diferença entre `wire_total_fresh` e `wire_total_preprovisioned`;
5. por que a ordem ECDH/ML-KEM alterna em cada par;
6. o que 80 MHz representa;
7. por que energia não foi medida;
8. diferença entre `KEY_MISMATCH` e `PROTOCOL_REJECT`;
9. por que ainda não há números FAIR oficiais;
10. três limitações científicas.

## 21. Nova bateria de resultados

Não execute bateria longa durante o seminário. Para uma nova coleta oficial
com AES-GCM e os dois perfis:

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
summary.mission_runs=600
summary.pqc_bench_runs=6
summary.fault_runs=400
logs/<timestamp>_aes_gcm_metrics_dev-ttyusb0.json
```

O runner alterna automaticamente entre `BASELINE` e `OBC-1U-LIMITED` e
retorna a placa para `BASELINE` no cleanup.

Antes da coleta longa, valide o plano sem abrir a serial:

```bash
python3 tools/aes_gcm_metrics_battery.py \
  --dry-run --cycles 100 --bench-repeats 3 --bench-rounds 100
```

As baterias abaixo são históricas e servem somente para regressão do protocolo
`CLASSIC`/`PQC`. Para a pesquisa atual, valide primeiro o plano pareado:

```bash
python3 tools/kex_metrics_battery.py \
  --dry-run
```

Depois do flash e do smoke FAIR_V1, o operador coleta com:

```bash
python3 tools/kex_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --deployment-manifest logs/firmware/<manifesto_deploy>.json \
  --timeout 20 \
  --fresh-cycles 100 \
  --session-repeats 30 \
  --message-counts 1 100 500 1000 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

O resultado esperado é um arquivo
`logs/<timestamp>_kex_fair_metrics_dev-ttyusb0.json` com
`official_candidate=true`, `failed=0`, 400 `fresh_mission_runs`, 480
`session_bench_runs`, 6 `kex_bench_runs`, zero pares/células inválidos e zero
divergências de perfil. `tools/final_metrics_battery.py` continua disponível como
bateria geral legada:

```bash
python3 tools/final_metrics_battery.py \
  --port /dev/ttyUSB0 \
  --timeout 12 \
  --cycles 100 \
  --pause 0.25 \
  --bench-repeats 3 \
  --bench-rounds 100
```

O resumo legado esperado é `ok=true`, `failed=0`, `mission_runs=600`,
`pqc_bench_runs=6` e `fault_runs=400`. Tanto esse runner quanto o dedicado a
AES-GCM executam `BASELINE` a 240 MHz e `OBC-1U-LIMITED` a 80 MHz; não é
necessário iniciar uma bateria separada por frequência.

Depois da coleta, atualize primeiro `docs/METRICAS_CONSOLIDADAS.md` e depois os
números deste guia. A interface pública não embute nem altera a bateria oficial.

## 22. Folha de consulta rápida

### Projeto

```text
Placa: BlackBoard Wisdom / ESP32
Contrato: KEX_FAIR_V1
Clássica: ECDH P-256
PQC: ML-KEM-512
Backend comum: wolfCrypt portátil
KDF comum: HKDF-SHA256
Cifra: AES-128-GCM
Guardião: CRC32
Perfis: 240 MHz e 80 MHz experimental
Transporte da bancada: USB serial, sem rádio
```

### Cenários

```text
ECDH       = ECDH P-256 -> HKDF -> AES-GCM
MLKEM      = ML-KEM-512 -> HKDF -> AES-GCM
CRC32      = opção ortogonal dentro do plaintext protegido
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
pub ECDH: 65 B + 65 B
```

### Resultados

```text
ECDH versus ML-KEM: coleta FAIR_V1 ainda pendente
Não reutilizar razões CLASSIC/PQC como resultado novo
Falhas CRC32 históricas continuam evidência separada do KEX
```

### Limites

```text
não é CubeSat real
não há radiação real
não há rádio
energia não foi medida
CLASSIC/PQC são nomes do protocolo legado
80 MHz não é especificação universal
```

### Fechamento

> ECDH e ML-KEM estabelecem segredos; o mesmo HKDF e AES-GCM completam a
> sessão. A comparação mede algoritmo e implementação no contexto declarado.
> CRC32 torna a corrupção acidental visível, mas não autentica. Os números
> finais só entram aqui depois da coleta FAIR_V1 na Wisdom.

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
