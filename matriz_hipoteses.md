# Matriz de hipótese

Este arquivo define como avaliar a hipótese do seminário.

## Hipótese

ML-KEM-512 é executável no ESP32 em perfil restrito, mas tem custo computacional e de comunicação significativamente maior que um mecanismo clássico; quando o ciphertext sofre bit-flip, o sistema pode apresentar falha explícita ou divergência de chave, e uma etapa simples de confirmação de chave detecta essa divergência com overhead pequeno.

## Critérios

| Parte | Métrica | Critério para sustentar |
|---|---|---|
| Executabilidade PQC | C2 `secret_match` e resets | C2 completa sem divergência e sem reset recorrente |
| Custo computacional | `time_ratio_pqc_classic` | razão >= 2x ou aumento prático bem documentado |
| Custo de comunicação | `bytes_ratio_pqc_classic` | razão >= 2x ou aumento prático bem documentado |
| Falha sob bit-flip | `fault_class` em C3 | existe `explicit_failure`, `key_divergence` ou `anomalous_behavior` |
| Detecção | `confirmation_detection_rate` | 100% das divergências observadas em C4 detectadas |
| Overhead pequeno | `confirmation_overhead_ratio` | < 10% de `pqc_decap_us` baseline |

## Decisão

| Resultado | Interpretação |
|---|---|
| Todos os critérios atendidos | hipótese sustentada dentro do modelo experimental |
| ML-KEM não executa no baseline | hipótese refutada na executabilidade |
| custo não é maior em tempo nem comunicação | hipótese refutada na parte de custo |
| C3 não produz falha ou divergência observável | resultado inconclusivo para modo de falha; ainda relatar desempenho |
| confirmação falha em detectar divergência | hipótese refutada na mitigação |
| overhead >= 10% | mitigação funciona, mas não atende critério de overhead pequeno |
| logs incompletos | inconclusivo |

## Interpretação obrigatória

Mesmo que a hipótese seja sustentada:

- o bit-flip é uma simulação lógica de SEU, não radiação real;
- o ESP32 é representativo apenas como plataforma restrita de bancada;
- a confirmação de chave é uma mitigação mínima, não um protocolo completo;
- os resultados valem para a implementação testada;
- a amostra é adequada para seminário, não para generalização estatística ampla.
