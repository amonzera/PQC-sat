# Validação final do modo estande SBPC

Data: 2026-07-20
Estado geral: **release candidate; aceite longo e ensaio com público pendentes**.

## Evidências produzidas

- auditoria da base: `docs/stand/AUDIT_EXISTING.md`;
- captura da interface anterior:
  `docs/stand/evidence/baseline_dashboard_1366x768.png`;
- nove capturas do modo estande: `docs/stand/evidence/states/`;
- vídeo offline de contingência, claramente simulado:
  `docs/stand/evidence/stand_backup_simulated.mp4`;
- soak acelerado: `docs/stand/evidence/simulated_soak.json`;
- smoke real autocontido: `docs/stand/evidence/hardware_smoke.json`;
- log JSONL do ciclo real: `docs/stand/evidence/hardware_smoke_cycle.jsonl`;
- ciclo real com tempos de produção:
  `docs/stand/evidence/hardware_production_timing.json` e
  `docs/stand/evidence/hardware_production_timing_cycle.jsonl`;
- matriz completa do handover: `docs/stand/REQUIREMENTS_TRACEABILITY.md`;
- resultado reproduzível da validação de software:
  `docs/stand/evidence/software_validation.json`;
- logs JSONL detalhados: `logs/stand/`;
- modelo para avaliação de cinco visitantes:
  `docs/stand/evidence/AUDIENCE_TEST_TEMPLATE.csv`.

## Validação automatizada de software

Na base anterior havia 96 testes. O modo estande adicionou cobertura para:

- configuração e proveniência da fixture;
- parsers tipados de perfil, missão e falha;
- resposta serial incompleta ou fora de ordem;
- timeout e desconexão;
- máquina de estados e reset automático;
- debounce e rejeição de ações em estado incorreto;
- cálculo das razões com divisão por zero;
- mapeamento A39 → byte/máscara;
- XOR de um único bit;
- mesmo payload em CLASSIC/PQC/240/80;
- mesma falha em NONE/CRC32;
- log JSONL;
- rótulo permanente de simulação;
- renderização de todos os estados e escala 1366×768/1920×1080.

Resultado mais recente: 122 testes Python, import headless, `py_compile`,
`git diff --check` e build PlatformIO passam. O firmware compilado ocupa
70,3% da flash e 17,3% da RAM estática.

## Soak offline

`python3 tools/stand_soak.py --cycles 50` concluiu:

- 50/50 ciclos;
- 100 ações lógicas de botão;
- 100 mudanças de potenciômetro;
- 150 missões e 100 comandos de falha;
- zero eventos rejeitados;
- crescimento de RSS observado: zero bytes.

Esse teste prova invariantes e estabilidade lógica com tempo acelerado. Ele
não prova USB, entradas físicas, heap da placa ou duração contínua real.

## Smoke em hardware real

O diagnóstico completo em `/dev/ttyUSB0` passou com `HELLO`, `STATUS`,
`ANALOG POT`, `PROFILE BASELINE`, `MISSION CLASSIC`, `MISSION PQC`, o mesmo
`FAULT` em `NONE`/`CRC32` e restauração a 240 MHz.

O runner ponta a ponta percorreu todos os estados até `SUMMARY` usando o
controlador e renderer reais. Além do smoke acelerado, uma segunda execução
manteve exatamente os tempos de `config/stand_demo.json` e chegou à conclusão
em 51,55 s. Os dois JSONL passaram pelo validador de invariantes com limiares
de ciclo curto. A entrada oficial `dashboard.py --stand` também fez handshake
e encerrou com `session_end` limpo.

Resultados dessa execução curta:

| Etapa | Evidência real |
|---|---|
| Handshake | `PQC-SAT-WISDOM`, `BlackBoard-Wisdom`, protocolo V1 |
| CLASSIC 240 MHz | `DELIVERED`, AES-128-GCM, 838 µs, 69 B |
| PQC 240 MHz | `DELIVERED`, ML-KEM-512 + AES-128-GCM, 14.453 µs, 837 B |
| PQC 80 MHz | `DELIVERED`, 40.061 µs, 837 B |
| Potenciômetro | A39=2884 → byte 28, máscara `0x40` |
| FAULT NONE | `0x34 ^ 0x40 = 0x74`, `SILENT` |
| FAULT CRC32 | mesmo byte/máscara/antes/depois, `DETECTED_GUARD` |
| Restauração | `PROFILE BASELINE`, 240 MHz |

As duas transições do ciclo curto foram acionadas pelo driver administrativo.
Duas janelas separadas, de 30 s e 45 s, não observaram `BUTTON_PING`; não há
evidência de que o botão tenha sido pressionado durante essas janelas. O botão
físico permanece pendente de repetição assistida, embora o firmware com
debounce e emissão do evento esteja compilado.

## Pendências que impedem o aceite completo

- observar `BUTTON_PING` físico e usá-lo para iniciar/avançar a interface;
- executar 30 ciclos físicos sem crash;
- registrar 100 pressões, 100 mudanças do potenciômetro e dez recuperações USB;
- completar 2 h de atração e 1 h de ciclos periódicos;
- executar a interface visível em tela cheia no monitor real do estande;
- capturar o vídeo exigido do fluxo completo em hardware, com o botão físico;
- validar montagem, proteção dos cabos e etiquetas;
- preencher a avaliação de cinco pessoas e obter os critérios 4/5;
- revisar o runbook com outro operador;
- criar a tag de release somente depois desses gates.

O comando operacional e o validador estão em `docs/stand/RUNBOOK.md`. O agente
não iniciou automaticamente a campanha longa, conforme a regra do projeto.

| Item | Estado | Evidência | Limitação restante |
|---|---|---|---|
| Hardware real | PASS | `docs/stand/evidence/hardware_production_timing.json` | botão físico ainda não observado |
| Baseline/PQC | PASS | ciclo real de 51,55 s: CLASSIC/PQC com mesmo payload | apenas um ciclo com timing de produção |
| 240/80 MHz | PASS | ciclo real confirmou 240 e 80 MHz, ambos com 837 B em PQC | resistência longa pendente |
| Bit flip | PASS | ciclo real: byte 28, `0x34 → 0x74`, máscara `0x40` | acionamento do botão foi administrativo |
| CRC32 | PASS | mesma falha: `SILENT` e `DETECTED_GUARD` | campanha longa do estande pendente |
| Precisão científica | PASS | `SCIENTIFIC_ACCURACY.md`, auditoria e parsers tipados | revisão oral contínua no evento |
| 30 ciclos | FAIL | soak offline 50/50 não substitui hardware | executar gate físico do runbook |
| Offline | PASS | fixture local, execução sem rede e smoke do inicializador | testar no notebook definitivo |
| Fallback | PASS | screenshots, fixture e vídeo MP4 de 36 s | testar reprodução no monitor definitivo |
