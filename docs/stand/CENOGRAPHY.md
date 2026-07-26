# Cenografia 1U — Missão Bit Flip

Esta montagem transforma a Wisdom em um objeto visível sem afirmar que ela é
hardware qualificado para voo. A etiqueta frontal deve dizer:

> **CubeSafe-01 — protótipo educacional de computador de bordo**

## Materiais

- quatro painéis laterais e duas tampas de acrílico fino, MDF ou impressão 3D;
- base aproximada de 10 × 10 cm e altura suficiente para placa, cabo e alívio
  de tração;
- quatro espaçadores não condutivos para a Wisdom;
- velcro/abraçadeira para o cabo USB;
- duas superfícies externas escuras com grade azul, representando painéis solares;
- etiqueta removível para D27; A39 pode receber uma etiqueta técnica discreta;
- parafusos sem ponta exposta e pés de borracha.

Não são necessários LEDs, botões ou seletores externos no MVP. D27 é o único
controle físico do visitante. A39, RGB e bargraph permanecem disponíveis para
diagnóstico técnico.

## Layout

- Frente: abertura para D27, com pelo menos 20 mm livres ao redor. A39 pode
  continuar acessível ao operador, fora da sinalização pública.
- Topo: janela transparente para RGB, bargraph e identificação da placa.
- Traseira: saída USB larga o bastante para não forçar o conector.
- Laterais: painéis solares cenográficos; nenhuma conexão elétrica.
- Base: placa fixada em espaçadores, sem contato direto com parafuso metálico.

Etiquetas:

```text
D27  CONFIRMAR / AVANÇAR CADA FASE
A39  DIAGNÓSTICO TÉCNICO
RGB  FASE DA OPERAÇÃO
```

A etiqueta não deve sugerir que D27 serve apenas em três momentos: no jogo
`STAGED_V1` ele confirma toda transição. O visitante não seleciona o vetor: o
controlador sorteia internamente se há incidente, sua causa e o bit afetado.
A39 não mede falha, radiação ou energia.

## Linguagem dos indicadores

| Cor/indicador | Significado |
|---|---|
| azul | preparação do payload |
| amarelo | cálculo de integridade |
| roxo | estabelecimento ML-KEM |
| ciano | AES-GCM |
| branco | quadro em transmissão |
| vermelho | pacote rejeitado |
| verde | pacote aceito |
| bargraph | progresso didático, nunca energia |

As fases rápidas podem aparecer como pulsos. O dashboard continua sendo a
fonte textual; nenhuma interpretação pode depender somente da cor.

## Montagem e segurança

1. Faça primeiro um molde em papelão e confirme botão, potenciômetro, reset e USB.
2. Prenda a placa somente pelos furos adequados e use espaçadores isolantes.
3. Garanta ventilação e acesso rápido ao reset.
4. Aplique alívio de tração antes de fechar a estrutura.
5. Evite iluminação UV funcional; qualquer túnel luminoso deve ser LED visível
   e rotulado “simulador visual de efeitos de radiação”.
6. Mantenha uma tampa removível para recuperação durante o evento.

## Aceite físico

- 100 pressões de D27 sem deslocar a estrutura;
- A39 acessível e legível para diagnóstico técnico, sem exigência pública;
- RGB/bargraph legíveis sob a iluminação do estande;
- cabo permanece firme após dez desconexões controladas;
- nenhuma parte aquece excessivamente ou expõe contato condutivo;
- operador consegue abrir, resetar e recolocar a tampa em menos de dois minutos;
- foto frontal, traseira e interna anexada à validação final.
