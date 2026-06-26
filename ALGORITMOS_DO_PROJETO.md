# Algoritmos usados no PQC-SAT

Este arquivo explica, com mais profundidade, os algoritmos usados no projeto:
`CLASSIC`, `PQC`, `PQC_CRC32`, AES-128-GCM, HMAC-SHA256, ML-KEM-512, CRC32,
bit-flips, comparação em tempo constante, KAT e confirmação de chave.

A ideia é separar três coisas que às vezes se confundem:

1. **criptografia clássica simétrica**: no projeto, AES-128-GCM cifra e
   autentica uma mensagem usando uma chave de sessão;
2. **criptografia pós-quântica**: no projeto, ML-KEM-512 estabelece um segredo
   compartilhado resistente à ameaça quântica conhecida, e esse segredo vira
   chave AES;
3. **integridade contra corrupção acidental**: no projeto, CRC32 detecta
   alteração de payload causada por bit-flip controlado.

## 1. Visão geral do fluxo do projeto

O dashboard envia comandos `MISSION` para a Wisdom/ESP32. A placa executa o
fluxo real e devolve métricas.

```text
Dashboard                      Wisdom/ESP32
   |                                |
   |-- MISSION CLASSIC -----------> | AES-128-GCM
   |<-- elapsed, bytes, heap ------ |
   |                                |
   |-- MISSION PQC ---------------> | ML-KEM-512 + AES-128-GCM
   |<-- keygen, encap, decap ------ |
   |                                |
   |-- MISSION PQC_CRC32 ---------> | ML-KEM-512 + AES-GCM + CRC32
   |<-- crc, bytes +4, validações - |
```

O payload padrão da missão é:

```text
PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK
```

Esse payload tem 41 bytes nos resultados consolidados.

## 2. Os três cenários principais

### `MISSION CLASSIC`

Objetivo: medir um baseline barato de mensagem cifrada/autenticada.

O que acontece:

1. a placa recebe ou monta o payload;
2. gera uma chave AES-128 efêmera com RNG da placa;
3. gera um nonce aleatório de 12 bytes;
4. cifra o payload com AES-128-GCM e produz uma tag de 16 bytes;
5. decifra/verifica a tag como receptor;
6. se `aead_match=1`, retorna `DELIVERED`.

Pseudoalgoritmo:

```text
payload = "PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK"
key = RNG(16 bytes)
nonce = RNG(12 bytes)

ciphertext, tag = AES_128_GCM_Encrypt(key, nonce, payload)
plaintext = AES_128_GCM_Decrypt_And_Verify(key, nonce, ciphertext, tag)

aead_match = (plaintext == payload)
delivered = aead_match

bytes_total = len(payload) + len(nonce) + len(tag)
```

Na versão AES-GCM, para o payload padrão:

```text
payload: 41 bytes
nonce GCM: 12 bytes
tag GCM: 16 bytes
total esperado: 69 bytes
```

Esse cenário **não executa ML-KEM**. Ele não mede criptografia assimétrica
clássica como ECDH. Ele mede um baseline simétrico de cifragem autenticada.

### `MISSION PQC`

Objetivo: medir o custo de inserir ML-KEM-512 no fluxo de entrega de mensagem.

O que acontece:

1. a placa gera um par de chaves ML-KEM-512;
2. encapsula um segredo usando a chave pública;
3. decapsula o ciphertext usando a chave privada;
4. verifica se os dois segredos são iguais (`key_match`);
5. deriva uma chave AES-128 a partir do segredo ML-KEM;
6. cifra o payload com AES-128-GCM;
7. decifra/verifica a tag GCM;
8. se `key_match` e `aead_match` batem, retorna `DELIVERED`.

Pseudoalgoritmo:

```text
(pk, sk) = ML_KEM_KeyGen()
(ct, ss_enc) = ML_KEM_Encaps(pk)
ss_dec = ML_KEM_Decaps(sk, ct)

key_match = constant_time_equal(ss_enc, ss_dec)

aes_key_tx = KDF(ss_enc)
aes_key_rx = KDF(ss_dec)
nonce = RNG(12 bytes)
ciphertext_payload, tag = AES_128_GCM_Encrypt(aes_key_tx, nonce, payload)
plaintext = AES_128_GCM_Decrypt_And_Verify(aes_key_rx, nonce, ciphertext_payload, tag)
aead_match = (plaintext == payload)

delivered = key_match AND aead_match

bytes_total = len(payload) + len(ct) + len(nonce) + len(tag)
```

Na versão AES-GCM, para o payload padrão:

```text
payload: 41 bytes
ciphertext ML-KEM: 768 bytes
nonce GCM: 12 bytes
tag GCM: 16 bytes
total esperado: 837 bytes
```

Importante: a chave pública ML-KEM tem 800 bytes, mas **não entra** no
`bytes_total` de `MISSION`. O `bytes_total` da missão contabiliza ciphertext
do payload, ciphertext ML-KEM, nonce, tag GCM e checksum quando ativo.

### `MISSION PQC_CRC32`

Objetivo: medir o mesmo fluxo PQC com um guardião CRC32 adicional no payload.

O que acontece:

1. executa todo o fluxo de `MISSION PQC`;
2. calcula CRC32 do payload no lado de transmissão;
3. inclui os 4 bytes de CRC no plaintext protegido;
4. cifra `payload + CRC32` com AES-GCM;
5. após decifrar, recalcula CRC32 sobre o payload;
6. se `key_match`, `aead_match` e `crc_match` batem, retorna `DELIVERED`.

Pseudoalgoritmo:

```text
(pk, sk) = ML_KEM_KeyGen()
(ct, ss_enc) = ML_KEM_Encaps(pk)
ss_dec = ML_KEM_Decaps(sk, ct)

key_match = constant_time_equal(ss_enc, ss_dec)

crc_tx = CRC32(payload)
protected_plaintext = payload || crc_tx

aes_key_tx = KDF(ss_enc)
aes_key_rx = KDF(ss_dec)
nonce = RNG(12 bytes)
ciphertext_payload, tag = AES_128_GCM_Encrypt(aes_key_tx, nonce, protected_plaintext)
protected_rx = AES_128_GCM_Decrypt_And_Verify(aes_key_rx, nonce, ciphertext_payload, tag)

payload_rx, crc_field = split(protected_rx)
crc_rx = CRC32(payload_rx)
crc_match = (crc_tx == crc_rx)

delivered = key_match AND aead_match AND crc_match

bytes_total = len(payload) + len(ct) + len(nonce) + len(tag) + 4
```

Na versão AES-GCM, para o payload padrão:

```text
payload: 41 bytes
ciphertext ML-KEM: 768 bytes
CRC32: 4 bytes
nonce GCM: 12 bytes
tag GCM: 16 bytes
total esperado: 841 bytes
```

Os valores consolidados antigos de `511 us`, `13.234 us`, `13.130 us`,
`73 bytes`, `841 bytes` e `845 bytes` pertencem à bateria pré-AES-GCM. Eles
servem como histórico até a nova bateria oficial da versão cifrada.

O tempo total de `PQC_CRC32` pode aparecer ligeiramente menor que `PQC` em uma
coleta específica por variação natural de execução. A conclusão correta é:
CRC32 adiciona custo pequeno no subtempo `crc_us`, mas esse custo é quase
invisível perto do custo de ML-KEM.

## 3. HMAC-SHA256 em detalhe

### 3.1 O que HMAC resolve

HMAC significa Hash-based Message Authentication Code. Ele responde à pergunta:

> Quem recebeu a mensagem consegue verificar que ela foi produzida por alguém
> que conhece a chave secreta e que a mensagem não mudou?

HMAC não cifra. A mensagem continua visível. O HMAC gera uma **tag**.

Na versão atual do projeto, `MISSION` usa AES-GCM para autenticar/cifrar a
mensagem. O HMAC-SHA256 continua relevante no comando técnico
`PQC_FAULT ... CONFIRM`, onde ele confirma se duas pontas chegaram ao mesmo
segredo ML-KEM sem revelar esse segredo.

```text
mensagem + chave secreta -> HMAC-SHA256 -> tag de 32 bytes
```

Quem tem a mesma chave recalcula a tag:

```text
tag_recebida == HMAC-SHA256(chave, mensagem)?
```

Se a comparação bater, a mensagem é aceita.

### 3.2 Por que não usar SHA-256 puro?

Uma hash simples:

```text
SHA256(mensagem)
```

não usa chave. Qualquer pessoa consegue recalcular. Isso não autentica.

HMAC usa chave:

```text
HMAC_SHA256(chave, mensagem)
```

Sem a chave, um atacante não deveria conseguir produzir uma tag válida.

### 3.3 Fórmula do HMAC

A fórmula simplificada é:

```text
HMAC(K, M) = SHA256((K' XOR opad) || SHA256((K' XOR ipad) || M))
```

Onde:

- `K` é a chave original;
- `K'` é a chave ajustada para o tamanho do bloco do SHA-256;
- `M` é a mensagem;
- `ipad` é um preenchimento interno;
- `opad` é um preenchimento externo;
- `||` significa concatenação.

O uso de duas camadas, interna e externa, evita ataques que existiriam se
apenas fizéssemos `SHA256(chave || mensagem)`.

### 3.4 Como entra no projeto

Na versão atual, HMAC-SHA256 não é mais a autenticação principal de `MISSION`.
O fluxo de mensagem usa AES-GCM para cifrar e autenticar o payload.

HMAC-SHA256 permanece em dois papéis técnicos:

```text
KDF: ss_mlkem + contexto -> chave AES-128 da missão
PQC_FAULT CONFIRM: ss_mlkem + transcript -> tag de confirmação de chave
```

Assim, a apresentação pode separar corretamente os papéis:

- ML-KEM estabelece segredo;
- HMAC pode ajudar a derivar/confirmar chave;
- AES-GCM cifra e autentica a mensagem.

Isso é importante para a apresentação:

- em `CLASSIC`, a chave já existe de forma didática;
- em `PQC`, a chave nasce da sessão ML-KEM;
- nos dois casos, a mensagem é autenticada por HMAC-SHA256.

## 4. SHA-256 em detalhe suficiente para a apresentação

SHA-256 é uma função hash criptográfica.

Ela recebe uma entrada de qualquer tamanho:

```text
"PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK"
```

e produz uma saída fixa de 256 bits:

```text
32 bytes = 64 caracteres hexadecimais
```

Propriedades importantes:

- **determinística**: mesma entrada gera mesma saída;
- **efeito avalanche**: mudar 1 bit muda a saída inteira de forma imprevisível;
- **pré-imagem difícil**: dado um hash, é inviável descobrir a entrada original;
- **segunda pré-imagem difícil**: dado um texto, é inviável achar outro com o
  mesmo hash;
- **colisão difícil**: é inviável achar duas entradas diferentes com a mesma
  saída.

No projeto, não usamos SHA-256 sozinho. Usamos SHA-256 dentro do HMAC.

## 5. Comparação em tempo constante

### 5.1 O problema da comparação comum

Uma comparação ingênua pode parar no primeiro byte diferente:

```text
for i in bytes:
    if a[i] != b[i]:
        return false
return true
```

Isso vaza tempo. Se a primeira diferença está no byte 0, a função termina
rápido. Se a primeira diferença está no byte 31, demora mais.

Em segurança, tempo pode virar informação.

### 5.2 O que o projeto faz

O firmware acumula todas as diferenças:

```text
diff = 0
for i in bytes:
    diff = diff OR (a[i] XOR b[i])
return diff == 0
```

Assim, ele percorre todos os bytes antes de decidir. Isso é usado para comparar:

- tags HMAC;
- segredos compartilhados ML-KEM;
- confirmação de chave.

Para o seminário, a explicação curta é:

> A comparação em tempo constante evita que o tempo de resposta revele em qual
> byte a tag ou o segredo começou a divergir.

## 6. CRC32 em detalhe

### 6.1 O que CRC32 resolve

CRC32 detecta erro acidental em dados.

Ele responde à pergunta:

> O dado que chegou parece idêntico ao dado para o qual o CRC foi calculado?

Ele não responde:

> Esse dado veio de alguém autorizado?

Por isso CRC32 **não é criptografia**.

### 6.2 Como CRC32 funciona intuitivamente

CRC significa Cyclic Redundancy Check.

A ideia matemática é tratar os bits da mensagem como um polinômio binário e
dividir por um polinômio fixo. O resto da divisão é o CRC.

```text
dados -> divisão polinomial -> resto de 32 bits
```

Se um bit muda, o polinômio muda. O resto quase sempre muda também.

### 6.3 O algoritmo bit a bit usado no projeto

O firmware usa a forma refletida comum do CRC32, com polinômio `0xEDB88320`.

Pseudoalgoritmo:

```text
crc = 0xFFFFFFFF

para cada byte em data:
    crc = crc XOR byte
    repetir 8 vezes:
        se bit menos significativo de crc é 1:
            crc = (crc >> 1) XOR 0xEDB88320
        senão:
            crc = crc >> 1

resultado = NOT crc
```

No firmware, a condição é feita com máscara para evitar ramificação direta:

```text
mask = -(crc & 1)
crc = (crc >> 1) XOR (0xEDB88320 & mask)
```

### 6.4 Por que CRC32 detecta o bit-flip da demo

Na demo, fazemos:

```text
before = payload[index]
payload[index] = payload[index] XOR bit_mask
after = payload[index]
```

Depois:

```text
crc_before = CRC32(payload_original)
crc_after = CRC32(payload_alterado)
```

Se `crc_before != crc_after`, o painel marca:

```text
DETECTED_GUARD
```

Com single-bit flip dentro do payload coberto, CRC32 detecta a alteração nos
testes do projeto.

### 6.5 Por que CRC32 não é segurança contra atacante

CRC32 não usa chave secreta. Um atacante que altera a mensagem pode simplesmente
recalcular:

```text
novo_crc = CRC32(mensagem_alterada)
```

e enviar mensagem + novo CRC.

Por isso:

- CRC32 é bom para erro acidental;
- HMAC é usado para autenticação;
- CRC32 não substitui HMAC.

## 7. ML-KEM-512 em detalhe

### 7.1 O que ML-KEM resolve

ML-KEM é um KEM: Key Encapsulation Mechanism.

Ele resolve o problema:

> Como duas partes chegam a um segredo compartilhado usando uma chave pública,
> sem enviar o segredo diretamente?

Depois que as duas partes têm o segredo, elas podem usá-lo em mecanismos
simétricos, como HMAC ou uma cifra autenticada.

### 7.2 O que ML-KEM não faz

ML-KEM não é uma cifra de mensagem.

Ele não faz:

```text
ciphertext = ML_KEM_Encrypt(mensagem)
mensagem = ML_KEM_Decrypt(ciphertext)
```

Ele faz:

```text
(pk, sk) = KeyGen()
(ct, ss_sender) = Encaps(pk)
ss_receiver = Decaps(sk, ct)
```

Se tudo deu certo:

```text
ss_sender == ss_receiver
```

Esse `ss` é o segredo compartilhado.

### 7.3 Por que ele é pós-quântico

ML-KEM é baseado em problemas de reticulados, especialmente uma família ligada
a Module Learning With Errors.

Explicação didática:

1. pense em uma grade de pontos em muitas dimensões;
2. o algoritmo mistura segredos pequenos, ruído e operações modulares;
3. quem tem a chave secreta consegue desfazer a estrutura suficiente para
   recuperar o segredo;
4. quem só vê os dados públicos encontra um problema matemático considerado
   difícil para computadores clássicos e também para computadores quânticos
   conhecidos.

O ponto de defesa no seminário:

> RSA e ECDH dependem de problemas que Shor ameaça. ML-KEM depende de
> reticulados, para os quais não há um algoritmo quântico conhecido com a mesma
> quebra estrutural.

### 7.4 Estrutura matemática simplificada

ML-KEM trabalha com polinômios e vetores de polinômios.

Elementos importantes:

- coeficientes inteiros módulo `q`;
- em ML-KEM, `q = 3329`;
- os polinômios têm grau limitado;
- em ML-KEM-512, o parâmetro principal usa vetores menores que variantes mais
  fortes, por isso é a opção mais leve.

Uma forma intuitiva de ver:

```text
t = A * s + e  (mod q)
```

Onde:

- `A` é uma matriz pública gerada a partir de uma semente;
- `s` é um segredo pequeno;
- `e` é um erro/ruído pequeno;
- `t` vira parte da chave pública.

Sem conhecer `s`, recuperar o segredo a partir de `A` e `t` é difícil porque o
ruído `e` impede resolver isso como álgebra linear simples.

### 7.5 KeyGen em alto nível

`KeyGen` gera chave pública e chave privada.

Fluxo conceitual:

```text
1. gerar sementes aleatórias
2. expandir uma matriz pública A
3. amostrar vetor secreto s
4. amostrar ruído e
5. calcular t = A*s + e
6. empacotar pk = (semente de A, t)
7. empacotar sk = informações privadas necessárias para decapsular
```

No projeto:

```text
crypto_kem_keypair(pqc_pk, pqc_sk)
```

Métricas:

```text
keygen_us
```

Tamanhos:

```text
pk = 800 bytes
sk = 1.632 bytes
```

### 7.6 Encaps em alto nível

`Encaps` usa a chave pública para gerar:

- um ciphertext `ct`;
- um segredo compartilhado `ss_enc`.

Fluxo conceitual:

```text
1. receber pk
2. gerar material aleatório interno
3. derivar uma mensagem/segredo intermediário
4. usar a estrutura pública para produzir ct
5. derivar ss_enc com função de derivação/hash
6. devolver (ct, ss_enc)
```

No projeto:

```text
crypto_kem_enc(pqc_ct, pqc_ss_enc, pqc_pk)
```

Métricas:

```text
encap_us
```

Tamanho:

```text
ct = 768 bytes
ss = 32 bytes
```

### 7.7 Decaps em alto nível

`Decaps` usa a chave privada e o ciphertext para recuperar o segredo.

Fluxo conceitual:

```text
1. receber sk e ct
2. usar sk para recuperar informação interna
3. reconstruir/verificar o encapsulamento
4. derivar ss_dec
5. devolver ss_dec
```

No projeto:

```text
crypto_kem_dec(pqc_ss_dec, pqc_ct, pqc_sk)
```

Métricas:

```text
decap_us
```

Nos resultados, `decap` foi a etapa mais cara do benchmark:

```text
BASELINE:        ~4.985 us
OBC-1U-LIMITED: ~15.204 us
```

### 7.8 Por que decap de ciphertext corrompido não é simplesmente "erro"

Um ponto importante para a defesa:

> ML-KEM não deve ser explicado como se todo ciphertext corrompido sempre
> retornasse um erro explícito de decapsulação.

No projeto, quando corrompemos o ciphertext:

```text
pqc_fault_ct[index] = pqc_ct[index] XOR bit_mask
ss_dec = Decaps(sk, pqc_fault_ct)
```

Depois comparamos:

```text
key_match = (ss_enc == ss_dec)
```

Se não bater:

```text
KEY_MISMATCH
```

Se também ativamos confirmação HMAC:

```text
tag_enc = HMAC(ss_enc, transcript)
tag_dec = HMAC(ss_dec, transcript)

se tag_enc != tag_dec:
    PROTOCOL_REJECT
```

Ou seja:

- `KEY_MISMATCH` é observação do harness;
- `PROTOCOL_REJECT` é rejeição operacional por confirmação de chave.

### 7.9 Transformação de Fujisaki-Okamoto em linguagem simples

Implementações modernas de KEMs como ML-KEM incorporam mecanismos para resistir
a ataques de ciphertext escolhido. Em linguagem simples, a decapsulação não
deve entregar informação útil para quem tenta manipular ciphertexts e observar
respostas.

Para a apresentação, não é necessário explicar a prova formal. Basta dizer:

> A biblioteca implementa ML-KEM padronizado. O nosso projeto não prova a
> segurança matemática do ML-KEM; ele mede integração, custo e comportamento
> operacional no ESP32.

## 8. Confirmação de chave com HMAC

### 8.1 Por que ela existe no projeto

Se `Encaps` e `Decaps` chegam a segredos diferentes, a sessão não deve ser
usada.

Só comparar CRC de ciphertext seria trivial: detectaria transmissão alterada,
mas não testaria se as duas pontas realmente chegaram ao mesmo segredo.

A confirmação de chave faz uma pergunta melhor:

> As duas pontas conseguem provar que derivaram o mesmo segredo, sem revelar o
> segredo?

### 8.2 Como funciona no projeto

O firmware usa um transcript fixo:

```text
PQC-SAT|ML-KEM-512|KEY_CONFIRM|v1
```

Cada ponta calcula:

```text
tag = HMAC_SHA256(shared_secret, transcript)
```

Se as tags batem, a chave foi confirmada.

```text
tag_enc = HMAC_SHA256(ss_enc, transcript)
tag_dec = HMAC_SHA256(ss_dec, transcript)

key_confirmed = constant_time_equal(tag_enc, tag_dec)
```

No comando:

```text
PQC_FAULT 0 0x01 CONFIRM
```

o projeto corrompe o ciphertext e ativa essa confirmação. O resultado esperado
consolidado foi:

```text
PROTOCOL_REJECT
key_match=0
confirmation=HMAC-SHA256
```

## 9. Bit-flip em detalhe

### 9.1 O que é bit-flip

Um bit-flip é uma inversão de bit:

```text
0 -> 1
1 -> 0
```

No código, isso é feito com XOR:

```text
after = before XOR bit_mask
```

Exemplo:

```text
before:   01010000
mask:     00000001
after:    01010001
```

### 9.2 Bit-flip de payload

No fluxo de payload:

```text
FAULT NONE payload_hex index mask
FAULT CRC32 payload_hex index mask
```

Sem guardião:

```text
payload muda
nenhum CRC é exigido
resultado = SILENT
```

Com CRC32:

```text
crc_before = CRC32(payload_original)
payload[index] ^= mask
crc_after = CRC32(payload_alterado)

se crc_before != crc_after:
    result = DETECTED_GUARD
```

### 9.3 Bit-flip de ciphertext ML-KEM

No fluxo PQC:

```text
PQC_FAULT index mask NONE
PQC_FAULT index mask CONFIRM
```

O alvo não é o payload. O alvo é o ciphertext ML-KEM:

```text
ct_fault[index] = ct[index] XOR mask
```

Depois:

```text
ss_dec = Decaps(sk, ct_fault)
key_match = (ss_enc == ss_dec)
```

Sem confirmação:

```text
se key_match == false:
    result = KEY_MISMATCH
```

Com confirmação:

```text
se HMAC(ss_enc, transcript) != HMAC(ss_dec, transcript):
    result = PROTOCOL_REJECT
```

## 10. KAT: Known Answer Test

### 10.1 O que é

KAT significa Known Answer Test.

É um teste em que a aleatoriedade é controlada para que o resultado seja
previsível.

No ML-KEM real, normalmente há aleatoriedade. Para testar, usamos "moedas"
determinísticas:

```text
keygen_coins = sequência fixa
encap_coins  = sequência fixa
```

Assim:

```text
KeyGenDeterministico(keygen_coins)
EncapsDeterministico(encap_coins)
```

devem gerar sempre os mesmos digests/CRCs esperados.

### 10.2 O que o projeto valida

O comando:

```text
PQC_KAT
```

validou:

```text
kat=pass
ss_crc32=0xD9DA8D6C
```

Isso não prova a segurança matemática de ML-KEM. Prova que a integração da
biblioteca no firmware está produzindo o resultado esperado para o vetor
determinístico do projeto.

## 11. PQC_BENCH

`PQC_BENCH n` executa várias rodadas de:

```text
KeyGen
Encaps
Decaps
Compare shared secrets
```

e calcula médias:

```text
keygen_avg_us
encap_avg_us
decap_avg_us
```

Resultados consolidados de `PQC_BENCH 100`:

| Perfil | keygen | encap | decap |
|---|---:|---:|---:|
| BASELINE 240 MHz | 3.298 us | 3.861 us | 4.985 us |
| OBC-1U-LIMITED 80 MHz | 10.056 us | 11.780 us | 15.204 us |

Leitura:

- reduzir CPU de 240 MHz para 80 MHz aumentou os tempos em torno de 3x;
- decap foi a etapa mais cara;
- isso ajuda a explicar por que `MISSION PQC` cresce muito em relação ao
  baseline clássico.

## 12. Como as métricas nascem

### 12.1 Tempo

O firmware usa `micros()` para medir intervalos:

```text
started = micros()
op_started = micros()
operação()
tempo_operacao = micros() - op_started
tempo_total = micros() - started
```

Campos:

- `keygen_us`;
- `encap_us`;
- `decap_us`;
- `tag_us`;
- `verify_us`;
- `crc_us`;
- `elapsed_us`.

### 12.2 Bytes

No firmware:

```text
bytes_total = bytes_ciphertext + bytes_mlkem + bytes_nonce + bytes_gcm_tag
```

Para `CLASSIC`:

```text
bytes_payload = 41
bytes_ciphertext = 41
bytes_nonce = 12
bytes_gcm_tag = 16
bytes_checksum = 0
bytes_total = 69
```

Para `PQC`:

```text
bytes_payload = 41
bytes_ciphertext = 41
bytes_mlkem = 768
bytes_nonce = 12
bytes_gcm_tag = 16
bytes_checksum = 0
bytes_total = 837
```

Para `PQC_CRC32`:

```text
bytes_payload = 41
bytes_ciphertext = 45     # payload + CRC32 cifrados
bytes_mlkem = 768
bytes_nonce = 12
bytes_gcm_tag = 16
bytes_checksum = 4
bytes_total = 841
```

### 12.3 Heap/RAM

O firmware reporta:

```text
heap = ESP.getFreeHeap()
min_heap = ESP.getMinFreeHeap()
```

Nos resultados consolidados, a heap ficou estável. Isso significa que, nesta
versão, o custo mais importante para explicar é:

- tempo;
- bytes;
- latência;
- possível energia associada ao tempo de CPU.

Não é correto dizer que a RAM foi o gargalo principal.

## 13. Como cada algoritmo aparece no popup

| Campo no popup | Algoritmo relacionado | Como explicar |
|---|---|---|
| `TEMPO` | todos | tempo total da entrega |
| `BYTES` | protocolo | payload + material criptográfico + checksum |
| `KEYGEN` | ML-KEM | geração de `pk` e `sk` |
| `ENCAP` | ML-KEM | criação de `ct` e `ss_enc` |
| `DECAP` | ML-KEM | recuperação de `ss_dec` |
| `RNG` | ESP32 RNG | geração de chave efêmera e nonce |
| `KDF` | HMAC-SHA256 como derivador | derivação da chave AES a partir do segredo ML-KEM |
| `ENC` | AES-128-GCM | cifragem e geração da tag GCM |
| `DEC` | AES-128-GCM | decifragem e verificação da tag GCM |
| `CRC` | CRC32 | cálculo/verificação de checksum |
| `key` | ML-KEM | `ss_enc == ss_dec` |
| `aead` | AES-128-GCM | tag GCM válida e plaintext recuperado |
| `crc` | CRC32 | checksum transmitido bate com checksum recalculado |

## 14. Diferenças essenciais para defender no seminário

### HMAC vs CRC32

| HMAC-SHA256 | CRC32 |
|---|---|
| usa chave secreta | não usa chave |
| autentica mensagem | detecta erro acidental |
| resiste a atacante sem chave | atacante pode recalcular |
| gera tag de 32 bytes | gera checksum de 4 bytes |
| usado para KDF/confirmacao técnica | usado em `PQC_CRC32` e na demo de falha |

### ML-KEM vs AES-GCM

| ML-KEM-512 | AES-128-GCM |
|---|---|
| estabelece segredo compartilhado | cifra e autentica payload |
| usa chave pública e chave privada | usa chave simétrica derivada |
| gera ciphertext KEM de 768 bytes | gera nonce de 12 bytes e tag de 16 bytes |
| é PQC | é clássico simétrico e continua relevante |
| custa milissegundos no ESP32 | tende a custar muito menos que ML-KEM |

### PQC vs "cifrar mensagem"

O projeto não deve ser explicado assim:

```text
ML-KEM cifra a mensagem.
```

Explique assim:

```text
ML-KEM estabelece um segredo; esse segredo vira chave AES para cifrar/autenticar a mensagem.
```

## 15. Roteiro de fala técnica de 2 minutos

> No modo clássico, a placa usa AES-128-GCM com chave efêmera e nonce aleatório
> para cifrar/autenticar o payload. No modo PQC, antes da cifra, a placa executa
> ML-KEM-512: gera chave, encapsula um segredo e decapsula o ciphertext. Esse
> segredo vira a chave AES da mensagem. Na versão AES-GCM, o pacote inclui
> payload cifrado, ciphertext ML-KEM, nonce e tag GCM; os números oficiais
> precisam de nova bateria. No modo PQC+CRC, adicionamos CRC32 ao plaintext
> protegido. CRC32 não é criptografia; ele detecta corrupção acidental e ajuda
> a mostrar visualmente a diferença entre falha silenciosa e erro detectado.

## 16. Frases que devem ser evitadas

Evite:

- "CRC32 deixa a mensagem segura";
- "ML-KEM cifra o payload";
- "a Wisdom é um CubeSat real";
- "o projeto mediu energia em watts";
- "PQC é inviável";
- "ML-KEM sempre detecta automaticamente ciphertext corrompido";
- "HMAC é a mesma coisa que ECDH";
- "o baseline clássico é uma pilha clássica completa".

Use:

- "CRC32 detecta corrupção acidental de payload";
- "ML-KEM estabelece segredo compartilhado";
- "a Wisdom representa um OBC educacional inspirado em CubeSat";
- "medimos tempo de CPU como proxy operacional, não energia elétrica real";
- "PQC funcionou, mas aumentou muito tempo e bytes";
- "a confirmação HMAC transforma divergência de segredo em rejeição de protocolo";
- "HMAC autentica mensagem";
- "CLASSIC é um baseline simétrico barato".

## 17. Resumo final

O projeto usa quatro blocos principais:

```text
HMAC-SHA256  -> autenticação clássica da mensagem
ML-KEM-512   -> estabelecimento de segredo pós-quântico
CRC32        -> detecção de corrupção acidental de payload
Bit-flip     -> simulação manual de falha transitória
```

A contribuição didática é mostrar que esses blocos têm papéis e custos
diferentes. Em hardware limitado, essa diferença vira decisão de arquitetura:

- `CLASSIC` é barato;
- `PQC` protege contra a ameaça quântica no acordo de segredo, mas custa muito
  mais tempo e bytes;
- `PQC_CRC32` mostra integridade adicional de payload com custo pequeno;
- falhas de bit precisam ser detectadas de forma explícita para não virarem
  falhas silenciosas.
