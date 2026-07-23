# Resultados KEX FAIR — coleta de 2026-07-23

## Situação da coleta

**Classificação: evidência exploratória parcial; não é candidata oficial.**

A bateria executou os 905 comandos planejados em 1.762,65 s
(29 min 22,65 s), mas terminou com 36 timeouts. O arquivo original foi
preservado em
[`logs/20260723T165305Z_kex_fair_metrics_dev-ttyusb0.json`](../logs/20260723T165305Z_kex_fair_metrics_dev-ttyusb0.json).

O resultado `official_candidate=false` deve ser mantido. Ainda assim, a coleta
contém:

- 370 missões `fresh` válidas, organizadas em 185 pares ECDH/ML-KEM;
- 480 sessões válidas, organizadas em 240 pares completos;
- todas as células de 1, 100, 500 e 1.000 mensagens nos dois perfis;
- manifesto, handshake e metadados FAIR válidos;
- nenhuma medição válida de `KEX_BENCH 100`, pois as seis chamadas excederam
  o timeout de 20 s.

Os números válidos são úteis para diagnosticar o sistema e orientar a próxima
coleta. Não devem substituir uma repetição oficial sem timeouts.

## Resumo executivo

Nas implementações e configurações específicas desta Wisdom, com ambos os
mecanismos no wolfCrypt portátil:

- ML-KEM-512 teve estabelecimento de segredo aproximadamente **45,0 vezes
  mais rápido** que ECDH P-256 a 240 MHz e **51,7 vezes mais rápido** no perfil
  experimental de 80 MHz;
- uma sessão nova ML-KEM transmitiu **1.632 B**, contra **194 B** da sessão
  ECDH: custo de comunicação **8,41 vezes maior**;
- ao amortizar o handshake em 1.000 mensagens, o total passou para
  **65.568 B** em ML-KEM e **64.130 B** em ECDH: diferença de apenas
  **2,24%**;
- o caminho comum de dados AES-128-GCM apresentou tempos muito próximos entre
  os cenários, reforçando que a principal diferença temporal observada está no
  estabelecimento;
- heap antes/depois, mínimo global, maior bloco e folga de stack ficaram
  estáveis, mas essa instrumentação **não mede o pico isolado de RAM de cada
  algoritmo**.

A afirmação científica permitida é:

> Nestas implementações e configurações específicas para ESP32, observamos
> estes custos de ECDH P-256 e ML-KEM-512.

Não se deve generalizar o resultado como superioridade universal de um
algoritmo.

## Proveniência e configuração

| Item | Valor |
|---|---|
| Experimento | `KEX_FAIR_V1` |
| Placa | RoboCore BlackBoard Wisdom, ESP32-D0WD |
| Perfis | `BASELINE` 240 MHz e `OBC-1U-LIMITED` 80 MHz |
| ECDH | P-256 |
| PQC | ML-KEM-512 |
| Componentes comuns | wolfCrypt RNG, HKDF-SHA256 e AES-128-GCM |
| Backend | `wolfCrypt-portable` 5.9.2 |
| Compilador | GCC 8.4.0 |
| Framework | arduino-esp32 2.0.17 |
| Otimização | `portable-software`, sem assembly do alvo e sem aceleração criptográfica |
| Firmware | `robocore_wisdom_esp32_fair` |
| SHA-256 do firmware | `9eba850f2ea493edbdb89d7103f85589456277426f50136a2e337f8dac32a18d` |
| Tamanho do binário | 1.012.080 B |
| Manifesto | `logs/firmware/20260723T155737Z_firmware_deploy_dev-ttyUSB0.json` |
| Payload | mensagem FAIR padronizada de 36 B |
| Ordem | ECDH/ML-KEM alternada dentro de cada par |
| Energia | não medida; tempo de CPU não é energia elétrica |

O manifesto e o desenho experimental não apresentaram erros.

## Integridade da bateria

### Execuções esperadas e válidas

| Família | Registros planejados | Medições válidas | Situação |
|---|---:|---:|---|
| `KEX_BENCH 100` | 6 | 0 | seis timeouts |
| `MISSION` fresh — 240 MHz | 200 | 194 | 97 pares válidos |
| `MISSION` fresh — 80 MHz | 200 | 176 | 88 pares válidos |
| `SESSION_BENCH` | 480 | 480 | 240 pares válidos; todas as células completas |
| Total de medições | 886 | 850 | 36 timeouts |
| Comandos auxiliares | 19 | 19 | preflight, perfil, saúde e cleanup |
| Total da bateria | 905 | 869 | `ok=false` |

As falhas foram balanceadas entre os algoritmos:

| Perfil | `KEX_BENCH` | ECDH fresh | ML-KEM fresh |
|---|---:|---:|---:|
| 240 MHz | 3 | 3 | 3 |
| 80 MHz | 3 | 12 | 12 |
| Total | 6 | 15 | 15 |

Não houve erro semântico nas 480 sessões recebidas.

### Por que ocorreram os timeouts

Cada chamada usou timeout global de 20 s. Pelos tempos observados nas missões,
100 pares de KEX exigem aproximadamente:

- 59 s a 240 MHz;
- 178 s a 80 MHz.

Assim, `KEX_BENCH 100` não poderia responder dentro de 20 s. O padrão do log é
consistente com o firmware continuando o trabalho e formando uma fila serial:
depois dos benchmarks expirarem, as primeiras missões também expiraram até a
fila voltar a sincronizar. A bateria então se recuperou e concluiu todas as
sessões.

Uma repetição oficial deve usar timeout de benchmark de pelo menos 240 s;
300 s oferece margem operacional. O runner também deve abortar ou
ressincronizar imediatamente após qualquer timeout, em vez de continuar
enfileirando comandos.

### Interpretação dos contadores do resumo

Alguns nomes do resumo são enganosos quando existem timeouts:

- `fresh_mission_runs=400` conta registros planejados, não respostas válidas;
  o número válido é 370;
- `invalid_pairs=0` verifica a presença dos dois registros do par, mesmo quando
  ambos estão vazios por timeout; existem 185 pares fresh válidos;
- `profile_mismatches=102` não representa 102 execuções no perfil errado. O
  código soma mensagens de validação contendo `build_profile`, `profile` e
  `cpu_mhz` nos 36 registros vazios. Entre as medições recebidas e aceitas,
  nenhuma apresentou perfil ou frequência divergente.

## Sessão nova: estabelecimento e primeira mensagem

Tempos em milissegundos. `p95` é o percentil 95 da distribuição válida.

| Perfil | KEX | n válido | KEX médio | Mediana | p95 | Ponta a ponta | Bytes fresh | Bytes pré-distribuídos |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 240 MHz | ECDH P-256 | 97 | 574,578 | 574,629 | 574,727 | 582,174 | 194 | 129 |
| 240 MHz | ML-KEM-512 | 97 | 12,762 | 12,716 | 12,885 | 20,882 | 1.632 | 832 |
| 80 MHz | ECDH P-256 | 88 | 1.750,137 | 1.750,102 | 1.750,333 | 1.768,913 | 194 | 129 |
| 80 MHz | ML-KEM-512 | 88 | 33,856 | 33,892 | 33,949 | 53,241 | 1.632 | 832 |

### Comparação pareada do KEX

| Perfil | Pares | ML-KEM / ECDH | ECDH / ML-KEM | Diferença média ML-KEM − ECDH | IC95% da diferença |
|---|---:|---:|---:|---:|---:|
| 240 MHz | 97 | 0,022 | 45,02× | −561,816 ms | [−561,863; −561,770] ms |
| 80 MHz | 88 | 0,019 | 51,69× | −1.716,281 ms | [−1.716,333; −1.716,230] ms |

Os intervalos são aproximações normais sobre diferenças pareadas e descrevem
somente as amostras válidas desta execução parcial.

### Decomposição média do caminho fresh

| Perfil | KEX | Setup | Iniciador | Respondedor | KEX total | HKDF | AES-GCM cifrar | AES-GCM decifrar |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 240 MHz | ECDH | 96,339 ms | 287,061 ms | 191,178 ms | 574,578 ms | 0,788 ms | 1,243 ms | 0,289 ms |
| 240 MHz | ML-KEM | 4,563 ms | 4,155 ms | 4,045 ms | 12,762 ms | 1,047 ms | 1,330 ms | 0,319 ms |
| 80 MHz | ECDH | 292,337 ms | 874,841 ms | 582,959 ms | 1.750,137 ms | 2,226 ms | 1,692 ms | 0,719 ms |
| 80 MHz | ML-KEM | 10,932 ms | 11,160 ms | 11,764 ms | 33,856 ms | 2,495 ms | 1,781 ms | 0,752 ms |

## Sessões amortizadas

`Tempo/mensagem` divide toda a execução ponta a ponta, incluindo o
estabelecimento, pela quantidade de mensagens. Cada célula possui 30 pares
válidos.

### Perfil BASELINE — 240 MHz

| Mensagens | ECDH tempo/mensagem | ML-KEM tempo/mensagem | ML-KEM / ECDH | ECDH bytes totais | ML-KEM bytes totais | Sobrecusto ML-KEM |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 582,050 ms | 20,643 ms | 0,035 | 194 | 1.632 | 741,2% |
| 100 | 6,387 ms | 0,773 ms | 0,121 | 6.530 | 7.968 | 22,0% |
| 500 | 1,734 ms | 0,612 ms | 0,353 | 32.130 | 33.568 | 4,48% |
| 1.000 | 1,156 ms | 0,593 ms | 0,513 | 64.130 | 65.568 | 2,24% |

### Perfil OBC-1U-LIMITED — 80 MHz

| Mensagens | ECDH tempo/mensagem | ML-KEM tempo/mensagem | ML-KEM / ECDH | ECDH bytes totais | ML-KEM bytes totais | Sobrecusto ML-KEM |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.768,795 ms | 53,040 ms | 0,030 | 194 | 1.632 | 741,2% |
| 100 | 19,220 ms | 2,066 ms | 0,107 | 6.530 | 7.968 | 22,0% |
| 500 | 5,083 ms | 1,650 ms | 0,325 | 32.130 | 33.568 | 4,48% |
| 1.000 | 3,315 ms | 1,599 ms | 0,482 | 64.130 | 65.568 | 2,24% |

O handshake ML-KEM adiciona 1.438 B em relação ao ECDH. Como cada mensagem
protegida ocupa os mesmos 64 B nos dois cenários, esse custo fixo perde peso
conforme a sessão cresce.

## Controle do caminho comum AES-GCM

Os tempos de processamento do lote de dados são próximos entre os dois
cenários:

| Perfil | Mensagens | Dados com ECDH | Dados com ML-KEM | Diferença ML-KEM |
|---|---:|---:|---:|---:|
| 240 MHz | 100 | 60,619 ms | 60,680 ms | +0,10% |
| 240 MHz | 500 | 289,209 ms | 289,501 ms | +0,10% |
| 240 MHz | 1.000 | 577,949 ms | 576,679 ms | −0,22% |
| 80 MHz | 100 | 162,643 ms | 163,072 ms | +0,26% |
| 80 MHz | 500 | 782,121 ms | 781,534 ms | −0,08% |
| 80 MHz | 1.000 | 1.556,131 ms | 1.556,216 ms | +0,006% |

Isso é compatível com o desenho: depois do KEX e HKDF, ambos percorrem o mesmo
AES-128-GCM. A coleta não mede rede real.

## Efeito do perfil de 80 MHz

Comparado ao perfil de 240 MHz:

| Operação | Fator de tempo em 80 MHz |
|---|---:|
| KEX ECDH | 3,046× |
| KEX ML-KEM | 2,653× |
| Dados AES-GCM, 1.000 mensagens, sessão ECDH | 2,693× |
| Dados AES-GCM, 1.000 mensagens, sessão ML-KEM | 2,699× |

`OBC-1U-LIMITED` é um perfil experimental deste projeto, não uma especificação
universal de CubeSat.

## Memória observada

As 480 sessões válidas apresentaram:

| Métrica | ECDH | ML-KEM |
|---|---:|---:|
| Heap livre antes | 198.868 B | 198.868 B |
| Heap livre depois | 198.868 B | 198.868 B |
| Delta de heap retido | 0 B | 0 B |
| Heap mínimo global desde o boot | 190.524 B | 190.524 B |
| Maior bloco livre depois | 110.580 B | 110.580 B |
| Folga mínima de stack | 17.112 palavras | 17.112 palavras |

Esses números mostram ausência de perda retida de heap entre as amostras e
estabilidade do processo. Eles **não demonstram igualdade de pico de RAM**:
`min_heap_global` é compartilhado desde o boot, e as leituras antes/depois não
capturam necessariamente o pico transitório interno do algoritmo.

## Conclusões que a coleta sustenta

1. O caminho de sessão e AES-GCM funcionou em todas as 480 execuções
   amortizadas recebidas.
2. Nesta implementação portátil do wolfCrypt para ESP32, ML-KEM-512 teve
   estabelecimento consideravelmente mais rápido que ECDH P-256.
3. ML-KEM exige muito mais bytes no handshake, mas o custo relativo cai de
   741,2% para 2,24% quando amortizado em 1.000 mensagens de 36 B.
4. O perfil de 80 MHz amplia o custo temporal, com fator próximo de 3× para
   ECDH e AES-GCM e aproximadamente 2,65× para ML-KEM.
5. Não foi observada perda retida de heap; o pico isolado por algoritmo
   continua sem medição direta.

## Limitações e decisão

- A coleta completa falhou no gate de qualidade por causa dos 36 timeouts.
- Nenhum dos seis agregados `KEX_BENCH 100` foi recebido.
- A amostra fresh é parcial: 97 pares a 240 MHz e 88 a 80 MHz.
- Os timeouts ocorreram antes das amostras preservadas, portanto esta seleção
  temporal não deve ser tratada como uma campanha oficial aleatória completa.
- Os números medem algoritmo, implementação, compilador, hardware e
  configuração em conjunto.
- Não há medição elétrica, rede real, side channels ou pico isolado de RAM.

**Decisão:** preservar este arquivo como `PILOT_PARTIAL_TIMEOUT`; corrigir o
timeout/ressincronização do runner e repetir a bateria antes de promover
resultados para o dashboard, artigo, pôster ou resultado oficial do estande.
