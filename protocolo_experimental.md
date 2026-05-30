# Protocolo experimental

Este protocolo define as campanhas do seminário. O núcleo usa uma BlackBoard Wisdom e um notebook.

## 1. Campanhas

| Campanha | Nome | Iterações | Algoritmo | Falha | Confirmação | Objetivo |
|---|---|---:|---|---|---|---|
| C0 | `functional` | 20 | nenhum | não | não | testar Serial e JSON |
| C1 | `classic_baseline` | 50 | ECDH P-256 | não | não | medir mecanismo clássico |
| C2 | `pqc_baseline` | 50 | ML-KEM-512 | não | não | medir mecanismo PQC |
| C3 | `pqc_fault` | 100 | ML-KEM-512 | 1 bit no ciphertext | não | observar modos de falha |
| C4 | `pqc_fault_confirm` | 100 | ML-KEM-512 | 1 bit no ciphertext | sim | detectar divergência |

## 2. Ordem obrigatória

1. Rodar C0.
2. Validar JSON.
3. Rodar C1.
4. Validar `secret_match=true` no clássico.
5. Rodar C2.
6. Validar `secret_match=true` no PQC sem falha.
7. Rodar C3.
8. Validar `fault_positions` e classificação.
9. Rodar C4.
10. Validar `key_confirm_us` e `key_confirmed`.
11. Gerar CSV.
12. Gerar gráficos.
13. Decidir a hipótese.

## 3. Preparação antes de cada campanha

Confirmar:

- firmware correto;
- script Python correto;
- porta Serial correta;
- `run_id` único;
- perfil `obc_80mhz_basic`;
- log bruto habilitado;
- cenário correto;
- segredo bruto não será salvo.

## 4. Classes de resultado

| Classe | Definição |
|---|---|
| `normal_success` | segredo coincide e não houve falha |
| `explicit_failure` | algoritmo retorna erro ou estado de falha verificável |
| `key_divergence` | algoritmo conclui, mas digest do segredo diverge |
| `confirmation_failed` | confirmação de chave detecta divergência |
| `anomalous_behavior` | timeout, reset, JSON inválido ou heap inconsistente |
| `net_no_change` | fault injection executada, mas ciphertext final não mudou |

## 5. Regras contra viés

- Não apagar logs ruins.
- Não alterar schema depois de iniciar C1.
- Não trocar algoritmo clássico durante a coleta.
- Não trocar implementação ML-KEM durante a coleta.
- Não descartar resets sem classificar.
- Não salvar segredo bruto.
- Não usar segunda placa para substituir resultado ruim sem declarar.

## 6. Validade da campanha

Uma campanha é válida se:

- pelo menos 98% das linhas têm JSON parseável;
- todos os campos obrigatórios existem;
- `run_id` é único;
- algoritmo e cenário são constantes dentro da campanha;
- erros foram preservados;
- existe log bruto correspondente ao CSV.

## 7. Extensões opcionais

Extensões permitidas depois das campanhas C1-C4:

| Extensão | Iterações sugeridas | Objetivo |
|---|---:|---|
| 4 bit-flips | 100 | falha mais severa |
| 240 MHz | 50 por cenário | comparação de perfil |
| segunda placa | 50 por cenário | replicação curta |
| CRC-32 | 100 | comparar checksum com confirmação de chave |
| reserva de memória | 50 por cenário | simular carga de bordo |
