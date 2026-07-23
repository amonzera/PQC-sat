# Precisão científica do modo estande

Este documento fixa a narrativa permitida para a experiência pública.

## O que cada mecanismo faz

| Mecanismo | Função neste projeto | Não afirmar |
|---|---|---|
| ML-KEM-512 | estabelece um segredo compartilhado; a KDF produz a chave AES | que ML-KEM cifra o payload |
| AES-128-GCM | cifra o plaintext e autentica ciphertext/dados associados com tag | que GCM não detecta alteração do ciphertext |
| CRC32 | detecta corrupção acidental no payload coberto pelo harness | que autentica, identifica atacante ou substitui GCM |

## Baseline correto

`MISSION CLASSIC` e `GAME_BEGIN ... CLASSIC ...` são um baseline simétrico
AES-128-GCM. O firmware gera uma chave AES aleatória por mensagem e executa
emissor e receptor logicamente na mesma Wisdom. Esse caminho não implementa
ECDH, RSA, certificado ou uma pilha clássica assimétrica completa.

`CLASSIC_CRC32` usa exatamente esse estabelecimento local de chave e adiciona
o CRC da aplicação. Portanto modo de chave e guardião são variáveis
independentes; CRC32 não transforma o baseline em PQC.

A comparação mostrada é:

> custo de adicionar ML-KEM-512 a um baseline simétrico AES-GCM.

## Evidência de AES-128-GCM

- `AES128_KEY_BYTES = 16` no firmware;
- chave configurada no Mbed TLS com 128 bits;
- nonce aleatório de 12 bytes e tag de 16 bytes;
- `mbedtls_gcm_auth_decrypt` verifica antes de aceitar o plaintext;
- contexto de KDF contém `AES-128-GCM`;
- 600/600 missões da coleta oficial registram `cipher=AES-128-GCM`.

Não há base executável para dizer AES-256-GCM.

## Modelo legado da falha CRC32

| Elemento | Definição executável |
|---|---|
| Objeto corrompido | payload em claro fornecido ao comando `FAULT` |
| Instante | dentro de um harness separado de `MISSION`, depois do CRC de referência |
| Região coberta | todos os bytes do payload recebido pelo harness |
| Vetor reproduzível | `payload_hex`, `byte_index` e máscara single-bit |
| `SILENT` | byte mudou e nenhum guardião foi aplicado |
| `DETECTED_GUARD` | byte mudou e `crc_after != crc_before` com CRC32 |

A sequência real é:

```text
crc_before = CRC32(payload_original)
payload[index] ^= single_bit_mask
crc_after = CRC32(payload_mutado)
```

O ensaio não altera o ciphertext de uma transmissão AES-GCM. Por isso a tela
diz explicitamente que representa corrupção controlada de payload/memória em
uma etapa de teste de integridade separada.

Esse modelo continua válido para o comando técnico `FAULT`. A interface visual
legada foi removida; o jogo público usa o modelo integrado abaixo.

## Modelo integrado de investigação

O protocolo `GAME_BEGIN` … `GAME_VERIFY` protege a mensagem, monta um quadro
experimental, injeta uma mutação single-bit na camada solicitada e devolve
três observações separadas em estágios. O comando monolítico `INVESTIGATE`
permanece como implementação compatível do mesmo modelo para bancada.

| Incidente | Objeto/instante | Condição objetiva |
|---|---|---|
| `CHANNEL_BITFLIP` | ciphertext depois do CRC de transmissão | CRC do quadro e GCM divergem; pacote rejeitado |
| `TAMPER` | ciphertext, seguido de recálculo do CRC sem chave | CRC do quadro coincide, tag GCM falha |
| `RX_MEMORY` | plaintext depois de `mbedtls_gcm_auth_decrypt` | GCM coincide; CRC da aplicação diverge se presente |
| `NORMAL` | nenhuma mutação | todas as verificações aplicáveis coincidem |

No caso de CRC do quadro inválido, o harness continua a verificação GCM apenas
para instrumentação; o plaintext nunca é aceito. Sem CRC da aplicação,
`RX_MEMORY` é classificado `SILENT_CORRUPTION`. Com `CLASSIC_CRC32` ou
`PQC_CRC32`, a referência fica dentro do plaintext autenticado e o resultado
é `APP_REJECT`.

Esses padrões localizam uma camada provável. Não atribuem causalidade física
ou intenção: radiação, ataque e defeito de software continuam indistinguíveis
sem evidência externa adicional.

No caminho PQC, o dashboard só aceita uma resposta quando o firmware confirma
`key_match=1` e as verificações GCM previstas estão presentes. Uma chave
divergente, campo ausente, ordem/ID incorreto ou vetor que não represente um
único bit é erro de protocolo, não evidência experimental válida.

## Retransmissão e decisão operacional

`GAME_RETRY` não desfaz o pacote anterior nem reaproveita chave/nonce. Ele usa
o mesmo payload e proteção confirmados, cria chave e nonce novos e não injeta
falha. O resultado esperado é `DELIVERED`. Isso demonstra uma resposta
operacional possível; não prova disponibilidade de um enlace real.

Um pacote rejeitado por CRC do quadro, tag GCM ou CRC da aplicação não pode ser
marcado como aceito pela interface. `SAFE_MODE` é uma decisão didática, não um
comando de voo certificado. `ACCEPT` em `SILENT_CORRUPTION` ilustra justamente
que ausência de alarme não garante correção.

## Perfis e métricas

`BASELINE` restaura o clock de boot, observado como 240 MHz na campanha.
`OBC-1U-LIMITED` solicita 80 MHz durante a execução e mantém os rádios
desligados. A UI só usa o rótulo depois que a resposta confirma `cpu_mhz`.

O perfil de 80 MHz é experimental. Ele não é uma especificação universal de
CubeSat. A BlackBoard Wisdom é um OBC educacional de bancada inspirado no
contexto de CubeSats; não é um CubeSat e não possui qualificação para voo.

`elapsed_us` e os tempos de estágio são tempos de processamento e podem ser
discutidos como proxy de custo computacional. Não houve instrumento elétrico
externo, portanto watts, joules e consumo de energia não foram medidos. A
animação ampliada não mede duração: o número recebido da Wisdom é a evidência.

`bytes_total` é um modelo do pacote do experimento. Em PQC, inclui ciphertext
ML-KEM, nonce, tag GCM, ciphertext do payload e CRC quando aplicável; não inclui
a chave pública ML-KEM provisionada fora dessa troca.

## Frases que devem aparecer ou ser ditas

- “ML-KEM estabelece o segredo compartilhado.”
- “AES-GCM cifra e autentica a mensagem.”
- “CRC32 detecta corrupção acidental na região coberta.”
- “A falha é injetada por software; não usamos radiação real.”
- “80 MHz é um perfil experimental, não uma especificação universal de CubeSat.”
- “A animação é didática; o valor numérico vem da medição real.”

## Frases proibidas

- “ML-KEM criptografa a mensagem.”
- “CRC32 distingue invasor de radiação.”
- “CRC32 garante segurança.”
- “AES-GCM só verifica a criptografia, não o conteúdo.”
- “Esta placa é um CubeSat.”
- “Medimos consumo de energia.”
- “PQC é inviável.”
- “A comparação clássica usa ECDH.”

## Fonte dos números

A campanha oficial vigente é
`logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`, SHA-256
`bcf16f1f49f6433ca7bdfde000023af1cb3b72546a3af16d570fe212edd6ce8d`.
Ela possui 1.038 registros, zero falhas, 600 missões, seis benchmarks PQC e
400 ensaios de falha. Essa campanha continua sendo a fonte dos resultados
consolidados. Leituras `GAME_*` ao vivo descrevem somente a partida atual;
sessões de visitantes não substituem a campanha. A fixture permanece
identificada como referência histórica/modelo offline.

## Referências normativas e contextuais

- NIST FIPS 203 — ML-KEM: <https://csrc.nist.gov/pubs/fips/203/final>
- NIST SP 800-38D — GCM/GMAC: <https://csrc.nist.gov/pubs/sp/800/38/d/final>
- NASA — efeitos de radiação e single-event upset:
  <https://ntrs.nasa.gov/citations/19890014178>

Essas referências fundamentam conceitos. Elas não transformam a injeção por
software em ensaio físico de radiação.
