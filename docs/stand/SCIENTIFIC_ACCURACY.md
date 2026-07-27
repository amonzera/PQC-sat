# Precisão científica do modo estande

Este documento fixa a narrativa permitida para a experiência pública.

## O que cada mecanismo faz

| Mecanismo | Função neste projeto | Não afirmar |
|---|---|---|
| ECDH P-256 | estabelece um segredo compartilhado clássico; a KDF produz a chave AES | que o cenário legado `CLASSIC` executa ECDH |
| ML-KEM-512 | estabelece um segredo compartilhado; a KDF produz a chave AES | que ML-KEM cifra o payload |
| AES-128-GCM | cifra o plaintext e autentica ciphertext/dados associados com tag | que GCM não detecta alteração do ciphertext |
| CRC32 | detecta corrupção acidental no payload coberto pelo harness | que autentica, identifica atacante ou substitui GCM |

## Comparação correta

O jogo público compara:

> ECDH P-256 versus ML-KEM-512 para estabelecer o segredo, seguidos pelo mesmo
> RNG, HKDF-SHA256 e AES-128-GCM do wolfCrypt, na mesma placa e configuração.

`MISSION CLASSIC` permanece como baseline simétrico AES-GCM histórico. Ele gera
uma chave AES local e não implementa ECDH, RSA, certificado ou uma pilha
clássica assimétrica completa. Portanto suas razões antigas não respondem à
pergunta ECDH versus ML-KEM.

O guardião `NONE|CRC32` é variável independente do KEX. CRC32 não transforma o
baseline em PQC nem oferece autenticação.

## Evidência de AES-128-GCM

- `AES128_KEY_BYTES = 16` no firmware;
- chave configurada no wolfCrypt com 128 bits no caminho FAIR;
- nonce aleatório de 12 bytes e tag de 16 bytes;
- `wc_AesGcmDecrypt` verifica antes de aceitar o plaintext FAIR;
- contexto de KDF contém `AES-128-GCM`;
- `KEX_INFO`, `MISSION` e `SESSION_BENCH` exigem `cipher=AES-128-GCM`.

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
| `RX_MEMORY` | plaintext depois da verificação AES-GCM | GCM coincide; CRC da aplicação diverge se presente |
| `NORMAL` | nenhuma mutação | todas as verificações aplicáveis coincidem |

No caso de CRC do quadro inválido, o harness continua a verificação GCM apenas
para instrumentação; o plaintext nunca é aceito. Sem CRC da aplicação,
`RX_MEMORY` é classificado `SILENT_CORRUPTION`. Com `ECDH_CRC32` ou
`MLKEM_CRC32`, a referência fica dentro do plaintext autenticado e o resultado
é `APP_REJECT`.

Esses padrões localizam uma camada provável. Não atribuem causalidade física
ou intenção: radiação, ataque e defeito de software continuam indistinguíveis
sem evidência externa adicional.

No jogo público, o sorteio sempre aplica um evento: 50% `TAMPER` e 50%
`RX_MEMORY`, rotulados didaticamente como “tentativa de invasão simulada” e
“radiação simulada”. `NORMAL`, `CHANNEL_BITFLIP` e o CRC do quadro permanecem
apenas na instrumentação técnica. A tela expõe um único CRC opcional da
mensagem:

- `TAMPER`: AES-GCM falha; o CRC não é verificado;
- `RX_MEMORY/CRC32`: AES-GCM coincide e o CRC da mensagem falha;
- `RX_MEMORY/NONE`: AES-GCM coincide, não há CRC e a corrupção é silenciosa;
- `NORMAL` técnico: todas as verificações aplicáveis coincidem.

O alerta durante a animação indica que o harness aplicou uma injeção simulada;
ele não representa um detector embarcado. O diagnóstico é uma hipótese sobre
o cenário sorteado, nunca prova física de radiação ou intenção hostil.

Nos dois caminhos, o dashboard só aceita uma resposta quando o firmware
confirma `key_match=1` e as verificações GCM previstas estão presentes. Uma chave
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
animação ampliada não mede duração; números da partida aparecem somente no
debrief e resultados científicos vêm da bateria controlada.

No FAIR, `wire_total_fresh` inclui setup, resposta, nonce, tag e ciphertext.
`SESSION_BENCH` separa handshake, dados e custo amortizado para 1, 100, 500 e
1000 mensagens. ECDH usa 65 + 65 bytes públicos; ML-KEM usa 800 + 768.

Memória significa heap livre antes/depois, mínimo global desde o boot, maior
bloco livre e folga de stack da task. O mínimo global não é pico isolado por
algoritmo; nenhuma conclusão de energia ou pico exclusivo deve ser derivada.

## Frases que devem aparecer ou ser ditas

- “A comparação clássica atual usa ECDH P-256.”
- “ML-KEM estabelece o segredo compartilhado.”
- “AES-GCM cifra e autentica a mensagem.”
- “CRC32 detecta corrupção acidental na região coberta.”
- “A falha é injetada por software; não usamos radiação real.”
- “80 MHz é um perfil experimental, não uma especificação universal de CubeSat.”
- “A animação é didática; os resultados oficiais vêm da bateria na placa.”

## Frases proibidas

- “ML-KEM criptografa a mensagem.”
- “CRC32 distingue invasor de radiação.”
- “CRC32 garante segurança.”
- “AES-GCM só verifica a criptografia, não o conteúdo.”
- “Esta placa é um CubeSat.”
- “Medimos consumo de energia.”
- “PQC é inviável.”
- “O cenário legado CLASSIC é ECDH.”
- “O mínimo global de heap é o pico isolado de cada algoritmo.”

## Fonte dos números

A campanha
`logs/20260702T044907Z_final_metrics_dev-ttyusb0.json`, SHA-256
`bcf16f1f49f6433ca7bdfde000023af1cb3b72546a3af16d570fe212edd6ce8d`.
Ela possui 1.038 registros, zero falhas, 600 missões, seis benchmarks PQC e
400 ensaios de falha. Ela é evidência histórica de AES local versus ML-KEM,
não a fonte de uma conclusão ECDH versus ML-KEM.

Ainda não há campanha FAIR oficial. A nova fonte só será um JSON
`pqc-sat-kex-fair-metrics-v2` com manifesto válido,
`official_candidate=true`, 400 amostras fresh, 480 amostras de sessão, seis
benches e zero pares/células/perfis inválidos. Leituras `GAME_*` ao vivo
descrevem somente a partida atual; sessões de visitantes e fixture não
substituem a campanha.

## Referências normativas e contextuais

- NIST FIPS 203 — ML-KEM: <https://csrc.nist.gov/pubs/fips/203/final>
- NIST SP 800-38D — GCM/GMAC: <https://csrc.nist.gov/pubs/sp/800/38/d/final>
- NASA — efeitos de radiação e single-event upset:
  <https://ntrs.nasa.gov/citations/19890014178>

Essas referências fundamentam conceitos. Elas não transformam a injeção por
software em ensaio físico de radiação.
