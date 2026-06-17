# Etapa 01 - Núcleo determinístico e efeitos de falha

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Substituir o sorteio de resultados por mutação real de bytes e usar o evento
resultante para acionar os efeitos visuais.

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
2. Usar `DashboardPanel.fault_rng`, nunca o RNG visual.
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

- [ ] Não existe `random.random() < taxa` para classificar falhas.
- [ ] Cada comando gera um evento inspecionável.
- [ ] O efeito visual corresponde ao `result` do evento.
- [ ] O dashboard continua funcionando em modo headless e fullscreen.
