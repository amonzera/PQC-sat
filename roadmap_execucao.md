# Roadmap de execução detalhado

Este roadmap orienta a implementação do projeto por um estudante de Ciência da Computação. A prioridade é chegar a uma demonstração experimental funcional para seminário, sem transformar o projeto em uma plataforma de pesquisa grande demais.

## 1. Estrutura recomendada

```text
.
├── firmware/
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp
│       ├── protocol.cpp
│       ├── protocol.h
│       ├── metrics.cpp
│       ├── metrics.h
│       ├── classic_ecdh.cpp
│       ├── classic_ecdh.h
│       ├── pqc_mlkem.cpp
│       ├── pqc_mlkem.h
│       ├── fault_injection.cpp
│       ├── fault_injection.h
│       ├── key_confirmation.cpp
│       └── key_confirmation.h
├── host/
│   ├── station.py
│   ├── analyze.py
│   └── requirements.txt
├── data/
│   ├── raw/
│   ├── processed/
│   └── figures/
├── projeto_pqc_cubesat_revisado.md
├── roadmap_execucao.md
├── protocolo_experimental.md
├── dicionario_metricas.md
├── matriz_hipoteses.md
├── linha_pesquisa_futura.md
└── readme.md
```

## 2. Fase 0: preparar ambiente

Objetivo: garantir que placa e notebook funcionam antes de implementar criptografia.

Passos:

1. Instalar PlatformIO ou ambiente ESP32 equivalente.
2. Criar projeto em `firmware/`.
3. Fazer upload de um firmware mínimo na BlackBoard Wisdom.
4. Confirmar que a porta Serial aparece no notebook.
5. Criar ambiente Python em `host/`.
6. Criar `data/raw`, `data/processed` e `data/figures`.

Dependências prováveis no notebook:

- `pyserial` para comunicação Serial;
- `pandas` para CSV e tabelas;
- `matplotlib` para gráficos;
- `cryptography` para ECDH P-256 e HMAC;
- `liboqs-python` ou binding equivalente para ML-KEM-512 no host.

Critério de conclusão:

- upload funciona;
- Serial imprime mensagem de boot;
- Python consegue abrir a porta Serial.

## 3. Fase 1: protocolo mínimo Serial

Objetivo: controlar a placa pelo notebook e salvar logs.

No firmware:

1. inicializar Serial;
2. definir `board_id = "A"`;
3. ler linhas terminadas por `\n`;
4. responder a `HELLO`;
5. receber `CONFIG:<json>`;
6. emitir `STATUS:<json>`.

No notebook:

1. criar `host/station.py`;
2. aceitar argumentos `--port`, `--campaign`, `--iterations`;
3. enviar `HELLO`;
4. enviar `CONFIG`;
5. ler `STATUS`;
6. salvar log bruto em `data/raw/`.

Critério de conclusão:

- 20 iterações funcionais com JSON válido.

## 4. Fase 2: schema fixo de dados

Objetivo: evitar mudar formato durante a coleta.

Implementar campos comuns em todos os cenários:

- `run_id`;
- `iteration`;
- `board_id`;
- `profile`;
- `campaign`;
- `algorithm`;
- `fault_enabled`;
- `fault_positions`;
- `key_confirmation_enabled`;
- `free_heap_before`;
- `free_heap_after`;
- `status`;
- `fault_class`;
- `reset_counter`.

No Python, adicionar:

- `timestamp_host`;
- `host_script_version`;
- campos de validação de segredo;
- exportação CSV.

Critério de conclusão:

- campos ausentes são preenchidos com `null`, `0`, `false` ou lista vazia;
- `analyze.py` consegue transformar log bruto em CSV.

## 5. Fase 3: perfil embarcado restrito

Objetivo: representar um nó embarcado simples sem criar instabilidade artificial.

No boot:

1. configurar CPU para 80 MHz;
2. desativar Wi-Fi;
3. desativar Bluetooth;
4. registrar heap livre.

Não reservar memória artificial nesta primeira versão.

Critério de conclusão:

- JSON contém `profile="obc_80mhz_basic"`;
- 20 iterações funcionais continuam estáveis.

## 6. Fase 4: implementar ECDH P-256

Objetivo: estabelecer baseline clássico.

No firmware:

1. usar mbedTLS ou biblioteca equivalente disponível no ESP32;
2. gerar par de chaves ECDH P-256;
3. medir `classic_keygen_us`;
4. serializar chave pública em formato definido;
5. enviar `CLASSIC_PK:<hex>`;
6. receber `CLASSIC_PEER_PK:<hex>`;
7. derivar segredo compartilhado;
8. medir `classic_derive_us`;
9. calcular digest do segredo;
10. enviar digest no `STATUS`.

No notebook:

1. receber `CLASSIC_PK`;
2. gerar par ECDH P-256;
3. derivar segredo;
4. enviar `CLASSIC_PEER_PK`;
5. calcular digest do segredo;
6. comparar digest do host com digest do ESP32;
7. preencher `secret_match`.

Critério de conclusão:

- 10 iterações manuais com `secret_match=true`;
- depois, 50 iterações da campanha C1 sem falha.

## 7. Fase 5: implementar ML-KEM-512

Objetivo: estabelecer baseline pós-quântico.

No firmware:

1. integrar implementação de ML-KEM-512;
2. evitar buffers grandes na stack;
3. gerar par de chaves ML-KEM-512;
4. medir `pqc_keygen_us`;
5. enviar `PQC_PK:<hex>`;
6. receber `PQC_CT:<hex>`;
7. executar `decap`;
8. medir `pqc_decap_us`;
9. calcular digest do segredo;
10. enviar digest no `STATUS`.

No notebook:

1. receber `PQC_PK`;
2. encapsular;
3. medir `pqc_encap_host_us`;
4. enviar `PQC_CT`;
5. calcular digest do segredo;
6. comparar com digest da placa.

Critério de conclusão:

- 10 iterações manuais com `secret_match=true`;
- depois, 50 iterações da campanha C2 sem falha.

## 8. Fase 6: métricas de comunicação

Objetivo: medir o custo de bytes, não só tempo.

Registrar:

- `classic_public_key_bytes`;
- `classic_peer_public_key_bytes`;
- `classic_total_bytes`;
- `pqc_public_key_bytes`;
- `pqc_ciphertext_bytes`;
- `pqc_total_bytes`.

Critério de conclusão:

- CSV permite calcular `pqc_total_bytes / classic_total_bytes`.

## 9. Fase 7: fault injection no ciphertext ML-KEM

Objetivo: observar modos de falha quando o material PQC recebido é corrompido.

Implementar:

```c
void inject_one_bit(uint8_t* buf, size_t len, FaultInfo* info) {
    uint32_t byte_index = esp_random() % len;
    uint8_t bit_index = esp_random() % 8;
    buf[byte_index] ^= (1u << bit_index);
    info->byte_index = byte_index;
    info->bit_index = bit_index;
}
```

No cenário C3:

1. receber `PQC_CT`;
2. registrar digest do ciphertext antes da falha;
3. aplicar 1 bit-flip;
4. registrar `fault_positions`;
5. registrar se o ciphertext mudou;
6. executar `decap`;
7. comparar digest do segredo com o host;
8. classificar resultado.

Classes:

- `normal_success`;
- `explicit_failure`;
- `key_divergence`;
- `anomalous_behavior`;
- `net_no_change`.

Critério de conclusão:

- 100 iterações C3;
- todas com `fault_class` preenchido.

## 10. Fase 8: confirmação de chave

Objetivo: detectar se host e ESP32 chegaram à mesma chave depois da falha.

No notebook:

1. gerar `nonce` por iteração;
2. montar `transcript`;
3. calcular `tag_host = HMAC_SHA256(K_host, nonce || transcript)`;
4. enviar `CONFIRM_TAG:<hex>` ou incluir tag na resposta do cenário.

No ESP32:

1. após `decap`, montar o mesmo `transcript`;
2. calcular `tag_device`;
3. medir `key_confirm_us`;
4. comparar tags;
5. se tags diferem, registrar `key_confirmed=false`;
6. classificar como `confirmation_failed`;
7. abortar uso da chave.

Para análise, o ESP32 ainda deve enviar `shared_secret_digest_device` em C4. O notebook compara com `shared_secret_digest_host` para confirmar se houve divergência real e separar detecção correta de erro de implementação da confirmação.

Critério de conclusão:

- 20 iterações de teste com confirmação correta sem fault;
- 100 iterações C4 com bit-flip e confirmação.

## 11. Fase 9: campanhas finais

Executar nesta ordem:

| Campanha | Iterações | Comando lógico |
|---|---:|---|
| C0 funcional | 20 | `functional` |
| C1 clássico baseline | 50 | `classic_baseline` |
| C2 PQC baseline | 50 | `pqc_baseline` |
| C3 PQC + bit-flip | 100 | `pqc_fault` |
| C4 PQC + bit-flip + confirmação | 100 | `pqc_fault_confirm` |

Não iniciar C3 se C2 não estiver estável.

Não iniciar C4 se C3 não registrar corretamente `fault_positions` e `secret_match`.

## 12. Fase 10: análise

Implementar `host/analyze.py` para:

1. ler logs de `data/raw`;
2. extrair JSON;
3. validar campos obrigatórios;
4. gerar CSV em `data/processed`;
5. calcular estatísticas;
6. gerar gráficos em `data/figures`.

Métricas obrigatórias:

- mediana de `classic_keygen_us`;
- mediana de `classic_derive_us`;
- mediana de `pqc_keygen_us`;
- mediana de `pqc_decap_us`;
- razão de tempo PQC/clássico;
- razão de bytes PQC/clássico;
- taxa de `key_divergence`;
- taxa de `explicit_failure`;
- taxa de confirmação negativa;
- overhead `median(key_confirm_us) / median(pqc_decap_us_C2)`.

## 13. Fase 11: material do seminário

Slides sugeridos:

1. problema e motivação;
2. CubeSat, restrição e PQC;
3. arquitetura experimental;
4. ECDH P-256 vs ML-KEM-512;
5. modelo de bit-flip;
6. confirmação de chave;
7. resultados de desempenho;
8. resultados de falha;
9. limitações;
10. linha de pesquisa futura.

## 14. Critérios de parada

Parar e corrigir se:

- C1 tiver `secret_match=false`;
- C2 tiver `secret_match=false` sem fault injection;
- mais de 2% dos JSON forem inválidos;
- segredo bruto aparecer em log;
- `fault_positions` estiver ausente em C3/C4;
- `key_confirm_us` estiver ausente em C4;
- houver reset recorrente.

## 15. Entrega mínima

Entrega mínima aceitável:

- C1 com 50 iterações;
- C2 com 50 iterações;
- C3 com 100 iterações;
- C4 com 100 iterações;
- CSV consolidado;
- pelo menos 4 gráficos;
- decisão da hipótese;
- limitações explícitas.

## 16. Extensões opcionais

Somente depois da entrega mínima:

- aumentar iterações;
- testar 4 bit-flips;
- rodar 240 MHz para comparação;
- usar segunda placa;
- comparar CRC-32 e confirmação de chave;
- medir energia aproximada.
