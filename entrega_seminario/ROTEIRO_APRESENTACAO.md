# Roteiro de apresentação - PQC-SAT

Tempo planejado: 18–20 minutos.

## Slide 1 — Abertura (1 min)

“O PQC-SAT é uma proposta didática para mostrar que um algoritmo
criptográfico forte não resolve sozinho falhas físicas, de comunicação ou de
integridade.”

Apresente o CubeSat como contexto e deixe claro que o trabalho possui um
protótipo visual funcional. Diferencie o que já está implementado da
metodologia experimental descrita.

## Slide 2 — Motivação (2 min)

- CubeSats usam componentes COTS por custo e disponibilidade.
- Falhas transitórias podem inverter bits em memória ou mensagens.
- ML-KEM protege contra ameaças quânticas, mas não contra toda corrupção.

Frase de transição: “A pergunta deixa de ser apenas se o algoritmo é seguro e
passa a incluir se a implementação percebe que algo foi alterado.”

## Slide 3 — Pergunta e hipótese (2 min)

Leia a pergunta principal e explique:

- sem proteção, um dado alterado pode ser aceito;
- com guardião, a alteração pode ser percebida;
- a comparação precisa usar exatamente as mesmas falhas.

## Slide 4 — Arquitetura (2 min)

Explique notebook, UART e ESP32. Destaque:

- o notebook controla e registra;
- o ESP32 representa o OBC;
- o modo simulado garante que a apresentação não dependa do hardware.

## Slide 5 — Protótipo atual (2 min)

Mostre o dashboard:

- visualização do CubeSat;
- telemetria;
- console;
- indicadores explícitos de simulação.

Não diga que ML-KEM ou CRC já estão executando. Use: “a interface está pronta;
o núcleo experimental aparece como arquitetura proposta”.

## Slide 6 — Metodologia A/B (3 min)

Explique a campanha:

1. gerar o payload;
2. aplicar o mesmo bit-flip;
3. cenário A sem CRC;
4. cenário B com CRC-32;
5. classificar e registrar.

Evite apresentar porcentagens antes da coleta.

## Slide 7 — Perfil OBC (2 min)

Explique que o ESP32 será testado:

- em baseline;
- sob o perfil `OBC-1U-LIMITED`.

Reforce que 80 MHz e 256 KiB são limites experimentais, não uma descrição de
todos os CubeSats.

## Slide 8 — Métricas (2 min)

Liste resultados, tempo, memória, firmware, robustez e CSV. Diga:

“O resultado esperado é redução de falhas silenciosas, mas a conclusão final
dependerá dos dados coletados.”

## Slide 9 — Limitações e validade (2 min)

Apresente claramente:

- bit-flips por software não reproduzem radiação real;
- o perfil OBC é didático;
- o protótipo atual ainda não produz resultados experimentais;
- consumo energético exige instrumentação.

Explique que separar proposta, protótipo e resultados fortalece a validade do
seminário.

## Slide 10 — Conclusão (1–2 min)

Feche com:

“A contribuição do projeto é tornar visível que a segurança depende do
algoritmo, da implementação, do protocolo e do hardware.”

Abra para perguntas.
