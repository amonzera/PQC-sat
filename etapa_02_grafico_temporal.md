# Etapa 02 - Timeline de eventos

Referência principal: [ROADMAP.md](ROADMAP.md).

## Objetivo

Exibir a evolução da campanha sem criar uma segunda fonte de métricas.

## Pré-requisito

Etapa 01 concluída com eventos estruturados.

## Entregas

1. Manter uma coleção limitada dos últimos eventos visuais.
2. Derivar cor do campo `result`:
   - verde: `OK`;
   - vermelho: `SILENT` ou `KEY_MISMATCH`;
   - laranja: `DETECTED_GUARD` ou `PROTOCOL_REJECT`;
   - cinza: `INVALID_INPUT`.
3. Mostrar:
   - ordem dos eventos;
   - legenda;
   - totais por resultado;
   - modo `SIMULATED` ou `HARDWARE`.
4. Separar:
   - reset apenas visual;
   - nova sessão experimental;
   - limpeza definitiva dos dados.

## Layout

- O gráfico deve caber no painel a 1366x768.
- O último evento pode ter brilho, sem piscar rapidamente.
- Fonte mínima continua sendo uma decisão de projetor, não uma variável para
  compensar overflow.

## Testes

- um evento gera exatamente um ponto;
- evento duplicado não é contado duas vezes;
- limite remove apenas os pontos mais antigos;
- totais são derivados do log completo, não apenas da janela visível;
- resize/resolução suportada não causa coordenadas negativas.

## Aceite

- [ ] Timeline usa os eventos da Etapa 01.
- [ ] Não há contadores paralelos divergentes.
- [ ] Legenda permanece visível.
- [ ] Layout validado em 1920x1080 e 1366x768.
