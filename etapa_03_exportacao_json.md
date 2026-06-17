# Etapa 03 - Exportação JSON e bateria de testes

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Persistir evidência suficiente para auditar a demonstração e alimentar
planilhas. O formato principal passa a ser JSON versionado, porque precisamos
guardar eventos, métricas de hardware e metadados de bateria sem achatar tudo
em uma tabela única.

## Estado atual

Ainda não implementada. O dashboard já possui eventos estruturados suficientes
para exportação inicial:

```text
schema_version
session_id
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
crc_before
crc_after
result
elapsed_us
uptime_s
```

## Schema mínimo

```json
{
  "schema_version": "pqc-sat-run-v1",
  "session_id": "SIM-42",
  "created_at": "2026-06-17T00:00:00Z",
  "board": {
    "connected": true,
    "node": "PQC-SAT-WISDOM",
    "chip": "ESP32-D0WD",
    "profile": "BASELINE"
  },
  "config": {
    "campaign_seed": 42,
    "pqc_backend": "ML-KEM-512",
    "checksum": "CRC32",
    "radiation_mode": "manual_bitflip"
  },
  "summary": {
    "events": 0,
    "silent": 0,
    "detected_guard": 0,
    "key_mismatch": 0,
    "protocol_reject": 0
  },
  "events": [],
  "hardware_samples": []
}
```

`hardware_samples` deve registrar leituras periódicas do dashboard e da placa:

```text
timestamp
uptime_s
mode
profile
cpu_mhz
heap
min_heap
flash
elapsed_us
radio
checksum
energy_proxy
```

`energy_proxy` deve ser explicitamente rotulado como proxy enquanto não houver
medidor elétrico real. A estimativa inicial pode usar tempo de operação,
frequência de CPU e modo de rádio; não deve ser apresentada como consumo em
mA, mW ou J sem instrumento.

## Comandos

- `EXPORT_JSON`: salva a sessão atual.
- `SAVE_SESSION`: alias para `EXPORT_JSON`.
- `RUN_BATTERY n`: executa uma bateria curta com `n` tentativas por cenário.

## Entregas

1. Diretório `logs/`.
2. Escrita atômica: arquivo temporário e rename.
3. JSON indentado e legível para revisão.
4. Resumo derivado dos eventos, não editado manualmente.
5. Exportação de zero, um e muitos eventos.
6. Registro de métricas de hardware quando a Wisdom estiver conectada.
7. Conversão posterior para planilha fora do dashboard, se necessário.

## Regras

- Use `json`, `pathlib` e escrita atômica.
- `RESET_SESSION` não deve apagar silenciosamente uma sessão ainda não
  exportada.
- `EXPORT_JSON` não pode alterar os dados exportados.
- Não exporte segredos completos de ML-KEM no JSON; use hash/digest curto,
  tamanho, resultado e tempo.
- Use `SIMULATED` ou `HARDWARE` em cada evento.

## Testes

- exportação com zero, um e muitos eventos;
- duas exportações consecutivas não sobrescrevem o arquivo anterior;
- falha de permissão retorna erro visível;
- replay de `byte_index` e `bit_mask` reproduz `after_hex`;
- `hardware_samples` aparece vazio sem placa e preenchido com placa conectada;
- segredos de KEM não aparecem em claro no JSON.

## Aceite

- [ ] JSON abre e é legível em ferramentas comuns.
- [ ] Cada tentativa é reproduzível.
- [ ] O schema tem versão.
- [ ] Nenhum dado é perdido por reset acidental.
- [ ] Métricas de hardware e eventos ficam no mesmo arquivo de bateria.
