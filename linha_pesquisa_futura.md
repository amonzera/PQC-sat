# Linha de pesquisa futura

Este arquivo descreve como o seminário pode evoluir para uma linha de pesquisa mais original. A primeira entrega deve permanecer enxuta; os itens abaixo são expansões futuras.

## 1. Fault injection sistemática em KEMs pós-quânticos

Pergunta:

> Como diferentes regiões do fluxo ML-KEM reagem a falhas transitórias?

Implementações possíveis:

- bit-flip no `ciphertext`;
- bit-flip na chave pública;
- bit-flip na chave privada;
- bit-flip no seed/RNG;
- bit-flip em buffers intermediários;
- bit-flip no segredo derivado.

Contribuição potencial:

- mapear quais regiões geram falha explícita, divergência silenciosa ou travamento;
- criar uma taxonomia de modos de falha para KEMs em embarcados.

## 2. Comparação entre mecanismos de detecção

Pergunta:

> Qual mitigação tem melhor relação custo/detecção para falhas físicas aleatórias em fluxos PQC embarcados?

Comparações:

- CRC-32 do ciphertext;
- SHA-256 do ciphertext;
- HMAC de confirmação de chave;
- duplicação de decap;
- votação temporal;
- checks de consistência por transcript.

Contribuição potencial:

- mostrar que checksum detecta alteração de bytes, enquanto confirmação de chave detecta divergência operacional;
- propor uma matriz de escolha por custo, segurança e confiabilidade.

## 3. Energia e orçamento de missão

Pergunta:

> O custo temporal de PQC se traduz em impacto energético relevante para CubeSats?

Implementações possíveis:

- medir corrente do ESP32 durante ECDH e ML-KEM;
- estimar energia por handshake;
- comparar frequência de handshakes por órbita ou por sessão;
- avaliar impacto de confirmação de chave.

Contribuição potencial:

- transformar métricas de tempo em custo operacional;
- aproximar o estudo de engenharia de missão.

## 4. Perfis de restrição embarcada

Pergunta:

> Como clock, heap disponível e carga concorrente alteram a viabilidade de PQC?

Implementações possíveis:

- 80 MHz vs 160 MHz vs 240 MHz;
- reserva artificial de memória;
- tarefas FreeRTOS concorrentes;
- buffers de telemetria simulados;
- watchdog habilitado.

Contribuição potencial:

- construir curvas de desempenho sob restrição;
- identificar limiares de instabilidade.

## 5. Replicação em múltiplas plataformas

Pergunta:

> Os resultados observados no ESP32 se mantêm em outros microcontroladores ou placas?

Implementações possíveis:

- segunda BlackBoard Wisdom;
- STM32;
- RP2040;
- ESP32-S3;
- placas ARM Cortex-M usadas em OBCs acadêmicos.

Contribuição potencial:

- separar efeito da implementação do efeito da plataforma;
- aumentar validade externa.

## 6. Comparação entre variantes PQC

Pergunta:

> Qual variante de ML-KEM oferece melhor equilíbrio para sistemas embarcados espaciais?

Implementações possíveis:

- ML-KEM-512;
- ML-KEM-768;
- ML-KEM-1024;
- outras famílias PQC, se viáveis.

Métricas:

- tempo;
- memória;
- bytes trafegados;
- taxa de falha sob bit-flip;
- custo de confirmação.

Contribuição potencial:

- recomendação prática para seleção de nível de segurança em OBCs pequenos.

## 7. Protocolo mínimo de sessão para CubeSat

Pergunta:

> Como transformar o experimento em um protocolo mínimo de sessão seguro e tolerante a falhas?

Implementações possíveis:

- transcript formal;
- nonce;
- confirmação mútua de chave;
- autenticação de estação;
- reenvio em caso de divergência;
- contador anti-replay;
- logs de telemetria de segurança.

Contribuição potencial:

- sair de um experimento de primitiva e chegar a um protocolo aplicado;
- gerar base para TCC ou artigo.

## 8. Modelo de ameaça híbrido: adversário e ambiente

Pergunta:

> Como diferenciar falha física aleatória de ataque ativo em um canal de satélite?

Implementações possíveis:

- bit-flip aleatório;
- alteração controlada de ciphertext;
- replay de ciphertext antigo;
- troca de chave pública;
- comparação de checksum, HMAC e assinatura.

Contribuição potencial:

- conectar tolerância a falhas com segurança adversarial;
- mostrar limites de checksum e necessidade de autenticação.

## 9. Dataset aberto de falhas em PQC embarcado

Pergunta:

> É possível criar uma base reprodutível de logs de falhas em PQC embarcado?

Implementações possíveis:

- padronizar schema de logs;
- publicar CSVs;
- publicar scripts de análise;
- publicar firmware versionado;
- registrar seeds e posições de bit-flip.

Contribuição potencial:

- facilitar comparação entre trabalhos;
- aumentar reprodutibilidade.

## 10. Caminho recomendado depois do seminário

Ordem sugerida:

1. concluir seminário com ECDH vs ML-KEM, bit-flip e confirmação de chave;
2. aumentar amostra;
3. adicionar 4 bit-flips;
4. comparar CRC-32, SHA-256 e confirmação;
5. medir energia;
6. testar segunda plataforma;
7. formalizar protocolo mínimo;
8. escrever relatório técnico expandido;
9. avaliar submissão como workshop, iniciação científica ou TCC.
