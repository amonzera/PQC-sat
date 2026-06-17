# Etapa 03 - Exportação CSV

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Persistir evidência suficiente para auditar e reproduzir a campanha.

## Pré-requisito

Eventos estruturados da Etapa 01.

## Schema mínimo

```text
schema_version
session_id
timestamp
uptime_s
campaign_seed
trial_id
mode
target
byte_index
bit_mask
fault_width
guard
before_hex
after_hex
result
elapsed_us
```

Comandos que não representam tentativa podem ir para outro CSV ou usar
`record_type=command`. Não misture resumo e evento sem um campo que diferencie
os registros.

## Entregas

1. `EXPORT` e `SAVE_SESSION`.
2. Diretório `logs/`.
3. Nome com `session_id` e timestamp.
4. Escrita em arquivo temporário seguida de rename.
5. Feedback de sucesso ou erro na interface.
6. Auto-save opcional ao fechar.
7. Resumo calculado a partir dos eventos.

## Regras

- Use `csv.DictWriter` e `pathlib`.
- `RESET_SESSION` não deve apagar silenciosamente a evidência do cenário A.
- O comando `EXPORT` não pode alterar os dados exportados.
- A seed do experimento é dedicada; não chame `random.seed()` globalmente.
- Registre `SIMULATED` ou `HARDWARE`.

## Testes

- exportação com zero, um e muitos eventos;
- caracteres e quebras não quebram o CSV;
- falha de permissão retorna erro visível;
- duas exportações não corrompem o arquivo anterior;
- replay de `byte_index` e `bit_mask` reproduz `after_hex`.

## Aceite

- [ ] CSV abre em ferramentas comuns.
- [ ] Cada tentativa é reproduzível.
- [ ] O schema tem versão.
- [ ] Nenhum dado é perdido por reset acidental.
