# Etapa 01 - Núcleo determinístico e efeitos de falha

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Substituir o sorteio de resultados por mutação real de bytes e usar o evento
resultante para acionar os efeitos visuais.

## Estado atual

Implementada no dashboard atual:

- `ExperimentEngine` sem dependência direta de Pygame;
- payload fixo `PQC-SAT|TEMP=24.5|STATUS=OK`;
- `FaultSpec` com `byte_index` e `bit_mask`;
- eventos com seed, trial, modo, guardião, bytes antes/depois, CRC antes/depois
  e resultado;
- `INJECT_FAULT` classifica `SILENT` por mutação real com guardião `NONE`;
- `BIT_FLIP [index mask]` aceita posição e máscara manuais;
- `CRC_CHECK` usa o mesmo engine com guardião `CRC32`;
- efeitos visuais e contadores são derivados do evento.

## Pré-condição

Definir uma mensagem curta e estável, por exemplo:

```python
payload = bytearray(b"PQC-SAT|TEMP=24.5|STATUS=OK")
```

## Entregas

1. Criar dentro de `dashboard.py` um núcleo sem dependência de Pygame que:
   - recebe `bytearray`, índice e máscara;
   - copia o valor original;
   - aplica `data[index] ^= mask`;
   - retorna evento estruturado.
2. Usar RNG própria do `ExperimentEngine`, nunca o RNG visual.
3. Definir campos mínimos:

```text
trial_id, target, byte_index, bit_mask, before_hex, after_hex,
guard, result, uptime, mode
```

4. Alterar comandos:
   - `INJECT_FAULT`: usa o próximo vetor determinístico;
   - `BIT_FLIP`: aceita opcionalmente posição e bit;
   - sem guardião, payload alterado e aceito resulta em `SILENT`.
5. Implementar efeitos:
   - tremor curto;
   - flash vermelho para `SILENT`;
   - flash laranja para `DETECTED_GUARD` ou `PROTOCOL_REJECT`;
   - olhos e label do satélite acompanham o evento;
   - timers baseados em `dt`.

## Regras

- A camada visual não decide o resultado.
- Não usar `time.sleep()`.
- Não usar cores inline se já houver constante equivalente.
- Não criar arquivos de asset.
- Não alegar ML-KEM real nesta etapa.

## Testes

- mesma seed gera a mesma sequência de índice/máscara;
- índice fora do buffer é rejeitado;
- máscara tem exatamente um bit no modo single-bit;
- bytes originais são preservados no evento;
- reset reinicia `trial_id` e RNG;
- efeito expira sem alterar métricas.

## Aceite

- [x] Não existe `random.random() < taxa` para classificar falhas.
- [x] Cada comando gera um evento inspecionável.
- [x] O efeito visual corresponde ao `result` do evento.
- [x] O dashboard continua funcionando em modo headless e fullscreen.
