# Projeto de seminário: desempenho e modos de falha de ML-KEM-512 em ESP32 representativo de OBC de CubeSat

## 1. Síntese

Este projeto avalia experimentalmente o custo e os modos de falha de um mecanismo pós-quântico de estabelecimento de chave em um sistema embarcado restrito. A plataforma usada é uma RoboCore BlackBoard Wisdom baseada em ESP32, configurada para representar de forma simplificada um computador de bordo de CubeSat de baixo custo. O notebook atua como estação em terra.

O projeto compara um mecanismo clássico de estabelecimento de chave, ECDH P-256, com ML-KEM-512. Depois, injeta uma falha lógica do tipo bit-flip no `ciphertext` de ML-KEM-512 para observar se o sistema apresenta falha explícita, divergência de chave ou outro comportamento anômalo. Por fim, adiciona uma etapa simples de confirmação de chave para detectar divergência entre o segredo da estação em terra e o segredo obtido pelo ESP32.

O objetivo é adequado para um seminário de 20 minutos: demonstrar o custo da migração para criptografia pós-quântica em hardware restrito e mostrar, em bancada, por que confiabilidade física e segurança criptográfica precisam ser analisadas juntas em sistemas espaciais.

## 2. Tese do projeto

ML-KEM-512 é executável no ESP32 em perfil restrito, mas tem custo computacional e de comunicação significativamente maior que um mecanismo clássico; quando o ciphertext sofre bit-flip, o sistema pode apresentar falha explícita ou divergência de chave, e uma etapa simples de confirmação de chave detecta essa divergência com overhead pequeno.

## 3. Pergunta de pesquisa

Em um ESP32 configurado como nó embarcado restrito, qual é o custo de usar ML-KEM-512 em comparação com ECDH P-256, e como uma falha simulada por bit-flip no `ciphertext` pós-quântico afeta o estado operacional do estabelecimento de chave?

Subperguntas:

1. ML-KEM-512 executa de forma estável no ESP32 em perfil restrito?
2. Qual é a diferença de tempo, memória e tamanho de mensagens entre ECDH P-256 e ML-KEM-512?
3. Um bit-flip no `ciphertext` de ML-KEM-512 gera falha explícita, divergência de chave ou outro comportamento?
4. Uma confirmação simples de chave detecta essa divergência com overhead aceitável?

## 4. Hipótese

### Hipótese principal

ML-KEM-512 é executável no ESP32 em perfil restrito, mas tem custo computacional e de comunicação significativamente maior que ECDH P-256; quando o `ciphertext` sofre bit-flip, o sistema pode apresentar falha explícita ou divergência de chave, e uma etapa simples de confirmação de chave detecta essa divergência com overhead pequeno.

### Critérios operacionais

Para tornar a hipótese mensurável no contexto de seminário:

- **Executável:** campanha ML-KEM-512 baseline completa sem reset recorrente e com segredos coincidentes.
- **Custo significativamente maior:** razão prática maior ou igual a 2x em pelo menos uma dimensão principal: tempo mediano no ESP32 ou bytes totais trafegados.
- **Modo de falha observável:** bit-flips efetivos no `ciphertext` produzem pelo menos uma classe mensurável diferente de sucesso normal, como falha explícita, divergência de chave ou anomalia.
- **Confirmação eficaz:** confirmação de chave detecta 100% dos casos com segredo divergente dentro da amostra.
- **Overhead pequeno:** tempo mediano da confirmação de chave inferior a 10% do tempo mediano de `decap` ML-KEM-512 no baseline.

Se algum critério não for atendido, o resultado deve ser reportado como refutação parcial ou resultado inconclusivo, não como falha do projeto.

## 5. Escopo principal

O núcleo do projeto usa:

- uma placa RoboCore BlackBoard Wisdom baseada em ESP32;
- um notebook como estação em terra;
- comunicação USB/Serial;
- ECDH P-256 como mecanismo clássico;
- ML-KEM-512 como mecanismo pós-quântico;
- bit-flip único no `ciphertext` de ML-KEM-512;
- confirmação de chave por HMAC-SHA256 ou SHA-256 chaveado equivalente;
- logs estruturados, CSV e gráficos.

A segunda BlackBoard Wisdom não é necessária para o seminário. Ela fica como contingência ou replicação futura.

## 6. Fora do escopo

Não fazem parte da primeira entrega:

- radiação física real;
- enlace RF real;
- implementação completa de protocolo espacial;
- duas placas no núcleo experimental;
- múltiplos algoritmos PQC;
- ML-KEM-768/1024;
- falhas em chave privada, RNG, stack, heap ou firmware;
- medição direta de energia;
- comparação CRC-32 vs SHA-256;
- prova de segurança criptográfica formal.

## 7. Por que ECDH P-256

ECDH P-256 é escolhido como mecanismo clássico de referência porque é amplamente usado, tem suporte comum em bibliotecas embarcadas como mbedTLS e permite uma comparação simples com ML-KEM-512 no mesmo fluxo lógico: estação em terra e nó embarcado estabelecem um segredo compartilhado.

X25519 seria uma alternativa válida, mas pode depender mais do stack disponível no ambiente ESP32 escolhido. Para manter o projeto enxuto, deve-se congelar um mecanismo clássico e evitar comparar vários algoritmos no seminário.

## 8. Modelo de sistema

Arquitetura:

```text
ESP32 / BlackBoard Wisdom (OBC demonstrativo) <---- USB/Serial ----> Notebook (estação em terra)
```

Papel do ESP32:

- gerar material público;
- receber resposta da estação;
- derivar ou desencapsular segredo;
- medir tempo e heap;
- executar fault injection no cenário PQC;
- executar confirmação de chave no cenário mitigado.

Papel do notebook:

- controlar campanhas;
- executar parte da estação em terra;
- calcular segredo correspondente;
- gerar tag de confirmação;
- salvar logs brutos;
- gerar CSV, tabelas e gráficos.

## 9. Perfil embarcado

Perfil principal:

1. clock do ESP32 em 80 MHz;
2. Wi-Fi desativado;
3. Bluetooth desativado;
4. heap livre registrado antes e depois das operações;
5. sem reserva artificial de memória na primeira versão.

A reserva artificial de memória pode ser uma extensão futura. No seminário, ela aumenta risco de instabilidade antes de responder à pergunta principal.

## 10. Fluxos criptográficos

### 10.1 Fluxo clássico: ECDH P-256

1. ESP32 gera par de chaves ECDH P-256.
2. ESP32 envia chave pública ao notebook.
3. Notebook gera seu par de chaves ECDH P-256.
4. Notebook calcula segredo compartilhado.
5. Notebook envia sua chave pública ao ESP32.
6. ESP32 calcula segredo compartilhado.
7. Notebook e ESP32 comparam apenas digests do segredo, sem registrar o segredo bruto.

Métricas principais:

- `classic_keygen_us`;
- `classic_derive_us`;
- `classic_public_key_bytes`;
- `classic_peer_public_key_bytes`;
- heap antes/depois;
- `secret_match`.

### 10.2 Fluxo pós-quântico: ML-KEM-512

1. ESP32 gera par de chaves ML-KEM-512.
2. ESP32 envia chave pública ao notebook.
3. Notebook encapsula e obtém segredo compartilhado.
4. Notebook envia `ciphertext` ao ESP32.
5. ESP32 desencapsula e obtém segredo compartilhado.
6. Notebook e ESP32 comparam apenas digests do segredo.

Métricas principais:

- `pqc_keygen_us`;
- `pqc_decap_us`;
- `pqc_public_key_bytes`;
- `pqc_ciphertext_bytes`;
- heap antes/depois;
- `secret_match`.

### 10.3 Fault injection no ML-KEM-512

No cenário de falha:

1. Notebook envia `ciphertext` válido.
2. ESP32 injeta 1 bit-flip no buffer do `ciphertext` antes do `decap`.
3. ESP32 executa `decap`.
4. Sistema classifica o resultado.

Classes esperadas:

- `normal_success`;
- `explicit_failure`;
- `key_divergence`;
- `anomalous_behavior`;
- `net_no_change`.

### 10.4 Confirmação de chave

A confirmação de chave detecta se estação e ESP32 chegaram ao mesmo segredo.

Fluxo:

1. Notebook e ESP32 compartilham um `nonce` da iteração.
2. Notebook calcula `tag_host = HMAC_SHA256(K_host, nonce || transcript)`.
3. ESP32 calcula `tag_device = HMAC_SHA256(K_device, nonce || transcript)`.
4. ESP32 compara as tags.
5. Se as tags diferem, registra `key_confirmed=false` e aborta o uso da chave.

O transcript deve incluir, no mínimo:

- identificador do algoritmo;
- `run_id`;
- `iteration`;
- chave pública ou digest da chave pública;
- ciphertext ou digest do ciphertext.

O objetivo não é implementar um protocolo completo, mas demonstrar uma confirmação mínima de que as duas partes chegaram ao mesmo segredo.

Para validar o experimento, o ESP32 ainda deve reportar um digest do segredo obtido, nunca o segredo bruto. O notebook compara esse digest com o digest do segredo da estação para identificar divergência real e verificar se a confirmação detectou corretamente o problema.

## 11. Campanhas do seminário

| Campanha | Iterações | Objetivo |
|---|---:|---|
| C0 funcional | 20 | testar Serial, JSON e controle |
| C1 clássico baseline | 50 | medir ECDH P-256 |
| C2 PQC baseline | 50 | medir ML-KEM-512 |
| C3 PQC + bit-flip | 100 | observar modos de falha |
| C4 PQC + bit-flip + confirmação | 100 | medir detecção e overhead |

Esses números são adequados para uma primeira demonstração. Se houver tempo, pode-se aumentar C1/C2 para 100 e C3/C4 para 300, mas isso não deve bloquear o seminário.

## 12. Métricas

### Desempenho

- tempo mediano de geração de chave clássica;
- tempo mediano de derivação ECDH;
- tempo mediano de geração de chave ML-KEM;
- tempo mediano de desencapsulamento ML-KEM;
- tempo mediano de confirmação de chave;
- min, max, média, mediana e desvio padrão.

### Comunicação

- bytes da chave pública clássica;
- bytes da resposta pública clássica;
- bytes da chave pública ML-KEM;
- bytes do ciphertext ML-KEM;
- razão `pqc_total_bytes / classic_total_bytes`.

### Memória

- heap livre antes;
- heap livre depois;
- variação de heap.

### Falhas

- taxa de falha explícita;
- taxa de divergência de chave;
- taxa de anomalia;
- taxa de confirmação negativa;
- taxa de detecção de divergência.

## 13. Análise esperada

Gráficos mínimos:

1. barras de tempo clássico vs PQC;
2. barras de tamanho de mensagens clássico vs PQC;
3. barras de classes de falha em C3;
4. barras de confirmação detectada em C4;
5. tabela-resumo da hipótese.

Tabelas mínimas:

1. estatística de tempo por campanha;
2. bytes trafegados por algoritmo;
3. contagem por `fault_class`;
4. overhead da confirmação;
5. decisão da hipótese.

## 14. O que o experimento consegue demonstrar

O experimento consegue demonstrar:

- se ML-KEM-512 roda no ESP32 no perfil definido;
- o custo observado de ML-KEM-512 em comparação com ECDH P-256;
- o aumento de tamanho de mensagens ao usar PQC;
- os modos de falha observados quando um `ciphertext` ML-KEM sofre bit-flip;
- se confirmação de chave detecta divergência dentro da amostra;
- o overhead dessa confirmação.

## 15. O que o experimento não demonstra

O experimento não demonstra:

- comportamento sob radiação real;
- confiabilidade de um CubeSat completo;
- segurança formal de protocolo;
- resistência contra adversário ativo;
- comportamento de todas as variantes de ML-KEM;
- comportamento em outros microcontroladores;
- tolerância a falhas em todo o firmware.

## 16. Critério de qualidade para o seminário

O seminário deve apresentar:

- motivação;
- arquitetura;
- hipótese;
- metodologia;
- demo ou logs reais;
- gráficos;
- limitações;
- próximos passos.

O projeto é cientificamente aceitável para seminário mesmo que a hipótese seja parcialmente refutada, desde que os dados sejam preservados e a conclusão respeite os limites experimentais.

## 17. Entregáveis

- firmware do ESP32;
- script Python da estação em terra;
- logs brutos;
- CSV consolidado;
- gráficos;
- relatório ou resumo técnico;
- slides de 20 minutos;
- documentação metodológica do repositório.
