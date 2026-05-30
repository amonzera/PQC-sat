# Desempenho e modos de falha de ML-KEM-512 em ESP32

Este repositório documenta um experimento de seminário sobre criptografia pós-quântica em sistema embarcado representativo de OBC de CubeSat.

O projeto compara ECDH P-256 com ML-KEM-512 em uma BlackBoard Wisdom baseada em ESP32, injeta um bit-flip no `ciphertext` pós-quântico e avalia uma confirmação simples de chave para detectar divergência entre estação em terra e nó embarcado.

## Tese

ML-KEM-512 é executável no ESP32 em perfil restrito, mas tem custo computacional e de comunicação significativamente maior que um mecanismo clássico; quando o ciphertext sofre bit-flip, o sistema pode apresentar falha explícita ou divergência de chave, e uma etapa simples de confirmação de chave detecta essa divergência com overhead pequeno.

## Hardware

Obrigatório:

- 1 RoboCore BlackBoard Wisdom baseada em ESP32;
- 1 notebook;
- cabo USB de dados.

Opcional:

- segunda BlackBoard Wisdom para replicação futura;
- OLED integrado para demonstração visual.

## Arquivos

| Arquivo | Função |
|---|---|
| `projeto_pqc_cubesat_revisado.md` | documento principal do projeto |
| `roadmap_execucao.md` | passo a passo detalhado de implementação |
| `protocolo_experimental.md` | campanhas e regras de execução |
| `dicionario_metricas.md` | campos de log, CSV, métricas e gráficos |
| `matriz_hipoteses.md` | critérios de decisão da hipótese |
| `linha_pesquisa_futura.md` | caminhos para evoluir o seminário para pesquisa |
| `readme.md` | manual do repositório |

## Estrutura recomendada

```text
.
├── firmware/
│   ├── platformio.ini
│   └── src/
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

Dependências esperadas no notebook:

- `pyserial`;
- `pandas`;
- `matplotlib`;
- `cryptography`;
- `liboqs-python` ou alternativa equivalente para ML-KEM-512.

## Campanhas

| Campanha | Iterações | Objetivo |
|---|---:|---|
| C0 funcional | 20 | testar Serial e JSON |
| C1 clássico baseline | 50 | medir ECDH P-256 |
| C2 PQC baseline | 50 | medir ML-KEM-512 |
| C3 PQC + bit-flip | 100 | observar falha explícita ou divergência |
| C4 PQC + bit-flip + confirmação | 100 | medir detecção e overhead |

## Fluxo resumido

1. Notebook configura a campanha.
2. ESP32 executa o fluxo clássico ou PQC.
3. Notebook e ESP32 comparam digests do segredo, nunca o segredo bruto.
4. Nos cenários C3/C4, ESP32 injeta 1 bit-flip no `ciphertext` ML-KEM.
5. Em C4, ESP32 executa confirmação de chave por HMAC-SHA256.
6. Logs brutos viram CSV.
7. CSV gera gráficos e decisão da hipótese.

Mesmo em C4, o ESP32 deve reportar apenas o digest do segredo, nunca o segredo bruto. Isso permite verificar se a confirmação detectou uma divergência real.

## O que medir

- tempo de geração/derivação ECDH;
- tempo de geração/decap ML-KEM;
- tempo de confirmação de chave;
- heap antes/depois;
- bytes trafegados;
- taxa de divergência de chave;
- taxa de falha explícita;
- overhead da confirmação.

## Execução recomendada

1. Ler `projeto_pqc_cubesat_revisado.md`.
2. Seguir `roadmap_execucao.md`.
3. Implementar o protocolo Serial.
4. Rodar C0.
5. Implementar ECDH P-256.
6. Rodar C1.
7. Implementar ML-KEM-512.
8. Rodar C2.
9. Implementar bit-flip.
10. Rodar C3.
11. Implementar confirmação de chave.
12. Rodar C4.
13. Gerar CSV e gráficos.
14. Avaliar `matriz_hipoteses.md`.

## Critérios de parada

Pare e corrija se:

- C1 ou C2 tiver `secret_match=false`;
- segredo bruto aparecer em log;
- JSON inválido ultrapassar 2%;
- C3/C4 não registrarem `fault_positions`;
- C4 não registrar `key_confirm_us`;
- houver reset recorrente.

## Limitações

Este experimento:

- não usa radiação real;
- não implementa enlace RF;
- não prova segurança formal;
- não representa um CubeSat completo;
- usa uma amostra adequada para seminário, não para generalização ampla.

## Entrega esperada

- firmware;
- script de controle;
- script de análise;
- logs brutos;
- CSV;
- gráficos;
- slides;
- documentação.
