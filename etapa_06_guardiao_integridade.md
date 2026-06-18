# Etapa 06 - Guardião de integridade

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Comparar proteção ausente e proteção leve usando bytes e verificações reais.

## Estado atual

Parcialmente implementada:

- `CRC_CHECK` calcula CRC32 antes e depois da mutação;
- `INJECT_FAULT` representa o cenário `NONE`;
- `RUN_BATTERY n` reaplica a mesma lista de fault specs em `NONE` e `CRC32`
  e exporta a sessão em JSON;
- o firmware ESP32 aceita `FAULT NONE|CRC32 payload_hex index mask` e retorna
  `SILENT` ou `DETECTED_GUARD` com CRC antes/depois;
- testes cobrem single-bit em payload curto no engine Python.

Ainda falta para concluir a etapa:

- registrar overhead separado de `prepare`/`verify`;
- cobrir campanhas multi-bit, bursts, checksum corrompido e região fora da
  cobertura;
- integrar a bateria A/B ao modo apresentação;
- documentar limitações no relatório final.

## Escopo mínimo

O MVP compara:

- cenário A: `NONE`;
- cenário B: `CRC32`.

CRC-16 e XOR são extensões para uma campanha que inclua falhas múltiplas.

## Por que as taxas antigas foram removidas

No modelo de exatamente um bit-flip dentro dos dados cobertos:

- XOR muda;
- CRC-16 muda;
- CRC-32 muda.

Logo, taxas fixas de 15%, 5% ou 1% não descrevem esse experimento. Para
observar diferenças entre guardiões, use falhas de dois bits, bursts,
cobertura parcial ou corrupção do próprio checksum.

## Interface

```text
prepare(data) -> reference
verify(data, reference) -> bool
```

O valor de referência precisa existir antes da injeção.

## Cenário A

1. gerar payload;
2. aplicar fault spec;
3. entregar ao receptor sem guardião;
4. se os bytes mudaram e foram aceitos: `SILENT`.

## Cenário B

1. gerar o mesmo payload;
2. calcular CRC32;
3. aplicar a mesma fault spec;
4. recalcular;
5. divergência: `DETECTED_GUARD`.

## Extensão ML-KEM

CRC sobre ciphertext detecta corrupção de transporte, mas não substitui
confirmação de chave. Registre separadamente:

- `DETECTED_GUARD` para CRC;
- `KEY_MISMATCH` para comparação no harness;
- `PROTOCOL_REJECT` para confirmação autenticada.

## Métricas

- total por cenário;
- resultados por classe;
- cobertura em bytes;
- tempo de `prepare` e `verify`;
- tamanho do metadado;
- modo simulado/hardware.

## Testes

- vetores conhecidos de CRC;
- todos os single-bit flips em payload curto;
- dois bits na mesma posição de bytes diferentes para demonstrar fraqueza do
  XOR;
- checksum corrompido;
- byte fora da cobertura;
- payload vazio.

## UI

- indicador de guardião;
- tipo e cobertura;
- comparação A/B;
- nenhuma conclusão hard-coded.

## Aceite

- [x] Resultados vêm de comparação real.
- [x] Mesma campanha é usada em A e B via `RUN_BATTERY`.
- [x] Os dois cenários são exportados no mesmo JSON.
- [ ] Overhead agregado é medido, não inventado.
- [ ] Limitações do mecanismo aparecem no relatório.
