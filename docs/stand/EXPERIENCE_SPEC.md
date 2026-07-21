# Especificação — Missão Guardiões do Bit

Estado: release candidate de software; aceite físico pendente.
Público: visitantes da 78ª Reunião Anual da SBPC.
Objetivo: experiência guiada, sem teclado ou mouse, com conclusão em até 100 s.

## Promessa ao visitante

> Um único bit pode mudar uma missão espacial. Você consegue descobrir qual
> proteção percebe a falha?

O visitante compara o custo de adicionar ML-KEM-512 a um baseline AES-GCM,
observa o impacto do perfil experimental de 80 MHz, escolhe fisicamente um bit
e repete a mesma falha com e sem CRC32.

## Arquitetura

`dashboard.py --presentation` (ou o alias `--stand`) executa a experiência no
mesmo loop, cenário e `DashboardPanel` do dashboard original. `stand_demo.py`
mantém somente o modelo controlado da missão, os parsers tipados, a fixture e
o logger; a superfície de produção é renderizada pelo próprio `dashboard.py`.
O modo reutiliza `DashboardSerialClient`, que por sua vez reutiliza
`tools/serial_bridge.py` e `tools/serial_protocol.py`. Não existe segundo
parser serial nem implementação criptográfica no notebook.

```text
botão/potenciômetro ─┐
                     v
Wisdom <─ USB ─> DashboardSerialClient ─> StandController
                     |                       |
                     |                       └─ JSONL datado
                     v
         DashboardPanel + cenário Terra/satélite
                     |
                     └─ apresentação guiada nativa
```

O núcleo criptográfico permanece no firmware. O controlador só avança quando
uma resposta tipada comprova cenário, perfil, clock, cifra, payload, resultado
e métricas esperadas.

## Estados e transições

| Estado | Entrada | Ação | Saída |
|---|---|---|---|
| `ATTRACT` | handshake confirmado | animação de atração | botão físico |
| `INTRO` | botão em `ATTRACT` | mostra o payload fixo por 7,5 s | temporizador |
| `RUN_240` | fim da introdução | confirma 240 MHz; executa CLASSIC e PQC sequencialmente | duas respostas válidas + 12 s de leitura |
| `RUN_80` | comparação 240 concluída | confirma 80 MHz; executa PQC com o mesmo payload | resposta válida + 12 s de leitura |
| `SELECT_BIT` | comparação 80 concluída | restaura 240 MHz; lê A39 sem bloquear; destaca byte/bit | botão físico |
| `FAULT_NONE` | seleção congelada | executa XOR single-bit em `FAULT NONE` | `SILENT` comprovado + 8 s |
| `FAULT_CRC` | fim do primeiro ensaio | repete payload, índice e máscara em `FAULT CRC32` | `DETECTED_GUARD` comprovado + 8 s |
| `SUMMARY` | par de falhas validado | três conclusões e papéis das tecnologias | botão ou 18 s |
| `ERROR` | timeout, desconexão ou resposta inválida | interrompe o fluxo sem completar dados | recuperação explícita |

As transições são centralizadas e qualquer transição não prevista é rejeitada.
O firmware já aplica debounce de 40 ms; o controlador adiciona uma janela de
350 ms e aceita o botão apenas em estados permitidos.

O tempo visual fixo, sem contar a escolha do visitante, é aproximadamente
69 s até o reset. A seleção fica limitada a 30 s de inatividade, mantendo o
ciclo inteiro próximo de 75–100 s. Tempos seriais possuem timeout de 8 s.

## Payload e comandos

Payload configurado e medido na campanha oficial:

```text
PQC-SAT|MSG=HELLO_UFF|TEMP=24.5|STATUS=OK
```

São 41 bytes, enviados em hexadecimal nos três comandos de missão:

```text
PROFILE BASELINE
MISSION CLASSIC <mesmo_payload_hex>
MISSION PQC <mesmo_payload_hex>
PROFILE OBC-1U-LIMITED
MISSION PQC <mesmo_payload_hex>
PROFILE BASELINE
ANALOG POT
FAULT NONE <mesmo_payload_hex> <index> <mask>
FAULT CRC32 <mesmo_payload_hex> <mesmo_index> <mesma_mask>
```

A UI só mostra uma medição ao vivo depois que o firmware confirma `profile`,
`cpu_mhz`, `cipher=AES-128-GCM`, `result=DELIVERED`, `elapsed_us`,
`bytes_total`, `bytes_payload` e `aead_match`.

## Dados medidos versus animação

`HardwareMeasurement` contém os valores recebidos. `AnimationModel` contém
somente duração e escala visual. A duração animada é limitada entre 1,2 s e
4,8 s e nunca é reutilizada como medição.

No modo hardware, o selo diz `MEDIDO AGORA NA BLACKBOARD WISDOM`. No modo
simulado, a tela inteira mantém o rótulo `MODO VISUAL SIMULADO` e as missões
vêm exclusivamente de `fixtures/stand/official_20260702.json`, vinculada por
SHA-256 ao log oficial. O modelo de falha offline calcula o XOR e os CRCs
deterministicamente e é rotulado como modelo, não medição atual.

Não existe fallback automático. A simulação só é ativada por `--simulated`.

## Registro da sessão

Cada execução cria `logs/stand/AAAAMMDD/*_stand_<modo>_*.jsonl` com:

- data/hora UTC, revisão Git e modo;
- handshake, estado da conexão e porta reportada pelo cliente;
- payload e comandos enviados;
- respostas cruas aceitas;
- transições e eventos rejeitados;
- bit selecionado;
- medições das missões e dos dois ensaios de falha;
- erros, timeouts, duração e encerramento de cada ciclo.

Não há entrada de texto do visitante nem coleta de dados pessoais.

## Layout e acessibilidade

- canvas lógico de 1366×768 escalado com proporção preservada;
- cobertura automatizada e capturas em 1366×768 e escala 1920×1080;
- tipografia grande, alto contraste e texto junto a todas as cores;
- nenhuma etapa depende de áudio;
- no máximo tempo, bytes e resultado aparecem simultaneamente nos cartões;
- hexadecimal técnico fica fora da narrativa principal;
- `Esc` alterna entre tela cheia e janela; `Ctrl+Q` encerra;
- `F12` abre o diagnóstico administrativo;
- no fallback, setas alteram o potenciômetro simulado e Espaço representa o
  botão somente para ensaio do operador.

## Tratamento de falhas

Sem handshake, o botão não inicia. Se houver timeout, resposta fora de ordem,
perfil incorreto, AES diferente de 128-GCM, payload divergente, desconexão ou
resultado experimental incompatível, o estado muda para `ERROR`. A tela
informa que nenhum dado será inventado e oferece reinício do ciclo.

O cliente serial continua tentando reconectar em segundo plano. Depois do
handshake, o operador reinicia a experiência. O reset limpa apenas a sessão
visual e preserva o JSONL.
