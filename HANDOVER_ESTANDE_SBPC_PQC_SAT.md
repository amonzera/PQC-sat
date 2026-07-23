# Handover de implementação — demonstração interativa PQC-SAT no estande do CBPF/SBPC 2026

> **Documento histórico superado em 2026-07-21.** Ele descreve o primeiro
> fluxo de 75–100 s e deve ser consultado apenas para rastrear decisões
> anteriores. O contrato vigente está em `docs/stand/EXPERIENCE_SPEC.md`: jogo
> `STAGED_V1` de 120–180 s, toque apenas seleciona, D27 confirma toda transição,
> sem avanço/reset automático e com comandos `GAME_*` separados. Em qualquer
> divergência, prevalecem `docs/ROADMAP.md`, a especificação vigente e os testes.
> Os comandos Bash, a simulação pública e `stand_demo.py` citados neste histórico
> foram removidos; a execução atual é exclusivamente `python3 dashboard.py` com
> a Wisdom conectada.

**Projeto:** PQC-SAT — criptografia pós-quântica e detecção de falhas em ESP32 usado como OBC educacional inspirado em CubeSat  
**Destino:** estande do CBPF na 78ª Reunião Anual da SBPC, UFF, Niterói  
**Evento:** 26 de julho a 1º de agosto de 2026  
**Estado documental usado neste handover:** 20 de julho de 2026  
**Público esperado:** heterogêneo, incluindo estudantes, famílias, pesquisadores e visitantes sem formação em criptografia  
**Natureza deste documento:** ordem de execução para um agente de IA com acesso ao repositório, ao ambiente de desenvolvimento e, idealmente, à BlackBoard Wisdom/ESP32

---

## 0. Instrução principal ao agente

Você deve **inspecionar o projeto existente, implementar a experiência descrita neste documento, testá-la de ponta a ponta e entregar evidências de que está pronta para o estande**.

Não trate este handover como uma descrição conceitual. Converta-o em código, documentação, testes, artefatos de execução e um relatório final de validação.

Regras de execução:

1. Não reescreva o núcleo criptográfico que já funciona, salvo se encontrar defeito comprovado ou se uma pequena alteração for indispensável para a demonstração.
2. Preserve o dashboard e os protocolos existentes sempre que possível. Prefira adicionar um `modo estande` isolado.
3. Toda métrica apresentada como resultado real deve vir da placa ou da campanha oficial validada. Não invente valores para preencher a interface.
4. Animações podem usar escala didática, mas devem ser explicitamente separadas do tempo medido.
5. Não confunda ML-KEM, AES-GCM e CRC32. Cada mecanismo deve ser apresentado com sua função correta.
6. Não afirme que a placa é um CubeSat, que houve radiação real ou que energia foi medida.
7. Se o código contradizer a documentação, o código executado e os logs reproduzíveis têm prioridade; registre a divergência.
8. Trabalhe em uma branch própria, faça commits pequenos por etapa e mantenha uma forma simples de retornar à versão do seminário.
9. Não introduza dependências de internet. A demonstração precisa funcionar totalmente offline.
10. Na impossibilidade de usar a placa durante alguma etapa, implemente e teste com mocks, mas faça a validação final obrigatoriamente no hardware antes de declarar conclusão.

---

# 1. Decisão de produto: a melhor demonstração

## 1.1 Nome da experiência

# **Missão Guardiões do Bit — salve o CubeSat em 90 segundos**

Frase de atração na tela:

> **Um único bit pode mudar uma missão espacial. Você consegue descobrir qual proteção percebe a falha?**

## 1.2 Conceito

A experiência será uma missão curta, conduzida por uma máquina de estados, na qual o visitante:

1. envia a mesma telemetria usando o baseline simétrico e a proteção pós-quântica;
2. observa quanto o uso de ML-KEM altera tempo e tamanho da comunicação;
3. reduz o perfil de CPU de 240 MHz para 80 MHz e observa o impacto;
4. gira o potenciômetro para escolher fisicamente um bit do payload;
5. pressiona o botão da placa para injetar a falha lógica;
6. vê o mesmo bit flip passar silenciosamente no ensaio sem guardião e ser detectado no ensaio com CRC32;
7. recebe uma conclusão de três linhas sobre ML-KEM, AES-GCM e CRC32.

A duração alvo é de **75 a 100 segundos**, sem exigir teclado, mouse ou conhecimento prévio.

## 1.3 Por que esta é a melhor opção

Esta solução combina os quatro critérios que realmente importam para um estande a poucos dias do evento:

- **impacto visual:** o visitante provoca uma mudança real de um bit e vê o byte antes/depois;
- **participação física:** utiliza botão e potenciômetro já disponíveis na Wisdom;
- **fidelidade ao trabalho científico:** mantém comparação 240/80 MHz, baseline/PQC, bytes, tempo e CRC32;
- **baixo risco de implementação:** reutiliza comandos, métricas, dashboard, serial bridge e testes já documentados.

A melhor experiência não é a que possui mais funcionalidades. É a que consegue repetir o ciclo centenas de vezes, ser entendida em menos de dois minutos e não obrigar o expositor a dar um seminário inteiro para cada visitante.

## 1.4 Alternativas rejeitadas

### CubeSat cenográfico complexo ou impresso em 3D

Pode melhorar a aparência do estande, mas não deve ser o centro do trabalho. O custo de fabricação, transporte e acabamento é alto para o tempo disponível, e ele acrescenta pouca evidência científica. Uma caixa transparente simples para proteger e destacar a placa é suficiente.

### Rádio real entre dois dispositivos

Adicionaria interferência, pareamento, alimentação, latência e pontos de falha sem melhorar a resposta às perguntas experimentais atuais. O projeto mede o fluxo no firmware, não um enlace de rádio. Não introduzir isso nesta entrega.

### Visitante digitando mensagens

Digitação cria filas, erros, problemas de acessibilidade e conteúdo inadequado. Use payload fixo ou telemetria viva. A interação deve ocorrer pelo botão e potenciômetro.

### Jogo com pontuação, ranking ou “moedas de energia”

Gamificação abstrata pode ser atraente, mas corre o risco de transformar medições científicas em números arbitrários. O projeto já possui uma interação concreta melhor: mudar um bit e observar as camadas de proteção.

### “Tempestade solar” com efeitos teatrais como demonstração principal

Pode induzir o público a pensar que houve radiação real. A expressão permitida é **injeção controlada do efeito lógico de um single-bit flip**. Elementos visuais espaciais são aceitáveis, desde que esse limite fique explícito.

---

# 2. Verdade técnica que a interface deve preservar

## 2.1 Arquitetura conhecida pela documentação

O estado documental de 2 de julho descreve:

- BlackBoard Wisdom/ESP32 como OBC educacional de bancada;
- notebook executando `dashboard.py` e bridge serial;
- criptografia e medições executadas no firmware;
- comunicação física por USB serial;
- papéis de emissor e receptor executados logicamente na mesma placa;
- cenários `CLASSIC`, `PQC` e `PQC_CRC32`;
- comandos como `MISSION`, `FAULT`, `PQC_FAULT` e evento `BUTTON_PING`;
- potenciômetro capaz de selecionar posição de bit;
- modo `--simulated` já existente;
- logs oficiais em JSON.

Tudo isso deve ser confirmado diretamente no repositório.

## 2.2 Inconsistências obrigatórias a resolver antes de editar a UI

### AES-128-GCM versus AES-256-GCM

A descrição oral mais recente mencionou AES-256-GCM, mas o guia do projeto registra AES-128-GCM, chave de 16 bytes e contexto de derivação contendo `AES-128-GCM`.

O agente deve:

1. localizar a definição efetiva da chave no firmware;
2. verificar o tamanho usado pela biblioteca e pelo KDF;
3. inspecionar logs e campos exportados;
4. corrigir todas as telas e documentos para o valor real;
5. não alterar de 128 para 256 apenas para coincidir com a narrativa oral.

A implementação executável é a fonte de verdade.

### “Criptografia clássica” versus baseline simétrico

O cenário `CLASSIC`, segundo o guia, gera chave AES efêmera localmente e não implementa ECDH, RSA, certificado ou acordo de chave clássico completo.

Portanto, a interface deve usar:

> **Baseline AES-GCM**

ou:

> **Baseline simétrico**

Não usar “criptografia clássica completa” nem “ECDH” a menos que isso realmente exista no código e seja validado.

A comparação cientificamente correta é:

> custo de adicionar ML-KEM-512 a um baseline simétrico AES-GCM.

### CRC32 versus AES-GCM

AES-GCM é AEAD e autentica o ciphertext e os dados associados. Uma alteração no ciphertext durante a transmissão deve ser rejeitada pela verificação da tag.

CRC32:

- não autentica contra atacante;
- não identifica sozinho se a causa foi radiação, ruído ou ataque;
- é útil para detectar corrupção acidental na região coberta;
- no projeto, funciona como guardião didático de um payload em um ensaio de falha controlada.

A demonstração de `FAULT NONE` versus `FAULT CRC32` não pode ser narrada como “o GCM não detectaria uma alteração no canal”. Ela deve ser localizada visualmente como:

> **falha no payload/memória na etapa de teste de integridade, separada da transmissão AES-GCM.**

O agente deve inspecionar o código e determinar exatamente quando o CRC é calculado e quando o byte é mutado. A animação deve corresponder à implementação real.

## 2.3 Frases obrigatórias

- “ML-KEM estabelece o segredo compartilhado.”
- “AES-GCM cifra e autentica a mensagem.”
- “CRC32 detecta corrupção acidental na região coberta.”
- “A falha é injetada por software; não usamos radiação real.”
- “80 MHz é um perfil experimental, não uma especificação universal de CubeSat.”
- “A animação é didática; o valor numérico vem da medição real.”

## 2.4 Frases proibidas

- “ML-KEM criptografa a mensagem.”
- “CRC32 distingue invasor de radiação.”
- “CRC32 garante segurança.”
- “AES-GCM só verifica a criptografia, não o conteúdo.”
- “Esta placa é um CubeSat.”
- “Medimos consumo de energia.”
- “PQC é inviável.”
- “A comparação clássica usa ECDH”, sem código que prove isso.

---

# 3. Roteiro exato da experiência do visitante

## 3.1 Estado 0 — atração automática

Duração contínua enquanto ninguém interage.

Tela em alto contraste, com poucos elementos:

```text
UM ÚNICO BIT PODE MUDAR UMA MISSÃO ESPACIAL

Pressione o botão do satélite para começar

[animação lenta: satélite → pacote → Terra]
```

Requisitos:

- texto legível a pelo menos dois metros;
- sem parágrafos;
- botão físico da placa destacado por etiqueta ou iluminação;
- a animação não pode parecer uma medição real de rádio.

Ao receber `BUTTON_PING`, avançar para o estado seguinte. Se for necessário manter o comportamento original, adicione um listener no dashboard que use o evento como comando de avanço apenas no modo estande.

## 3.2 Estado 1 — missão e payload

Mostrar por 5–8 segundos:

```text
MISSÃO: enviar telemetria crítica à estação terrestre

TEMP=84 °C | MODO_SEGURO=ATIVAR | SEQ=042
```

Use payload fixo curto e compreensível ou telemetria viva resumida. Não exiba todos os sensores na tela principal.

O payload utilizado na medição precisa ser preservado em hexadecimal e registrado no log da sessão.

## 3.3 Estado 2 — corrida de proteção em 240 MHz

Executar de forma sequencial e controlada, com o mesmo payload:

1. `MISSION CLASSIC` ou comando equivalente;
2. `MISSION PQC` ou comando equivalente.

Visualizar lado a lado:

| Baseline AES-GCM | Pós-quântico |
|---|---|
| chave AES efêmera local | ML-KEM → KDF → AES-GCM |
| tempo real da execução | tempo real da execução |
| bytes modelados | bytes modelados |
| resultado | resultado |

A animação deve ser desacelerada para permitir percepção humana, mas cada cartão deve mostrar:

```text
Medido na placa: 611 µs
Animação ampliada para visualização
```

Não codifique `611 µs` como valor fixo. Esse número é apenas o resultado oficial anterior; a tela principal deve exibir a resposta da placa. A campanha oficial pode ser usada como referência em um painel secundário claramente rotulado.

Mensagem final deste estado:

> **A proteção pós-quântica funcionou, mas aumentou o custo de tempo e comunicação.**

## 3.4 Estado 3 — reduzir o computador de bordo para 80 MHz

Mostrar:

```text
Agora o computador de bordo terá apenas 1/3 do clock.
```

Alterar o perfil para 80 MHz usando o mecanismo já existente. Confirmar que a mudança ocorreu por resposta da placa; não mudar apenas o texto da interface.

Executar novamente o cenário PQC com o mesmo payload e apresentar:

- tempo PQC em 240 MHz;
- tempo PQC em 80 MHz;
- bytes, que devem permanecer iguais para o mesmo protocolo e payload;
- diferença percentual ou razão calculada dinamicamente.

Mensagem:

> **Reduzir o clock aumenta a latência, mas não muda o tamanho do pacote.**

Se a troca dinâmica de perfil não for segura ou exigir reboot, substitua esta etapa por comparação com a campanha oficial, sem fingir execução ao vivo. A interface deve rotular “resultado da campanha oficial”.

## 3.5 Estado 4 — visitante escolhe um bit

Mostrar uma representação de 8 a 16 bytes relevantes, não o payload inteiro.

Exemplo:

```text
MODO_SEGURO=1
01001101 01001111 01000100 01001111 ...
```

Instrução:

> **Gire o potenciômetro para escolher um bit.**

Enquanto o potenciômetro gira:

- destacar byte e bit selecionados;
- exibir índice do byte e máscara;
- manter linguagem leiga na área principal;
- deixar índices técnicos em uma faixa menor.

A seleção deve ser real e enviada ao comando de falha existente.

## 3.6 Estado 5 — falha sem guardião

Instrução:

> **Pressione o botão para virar este bit.**

Executar o ensaio `FAULT NONE` com o payload, índice e máscara escolhidos.

Visualizar:

```text
ANTES: 01001111
DEPOIS: 01001110
                  ↑
RESULTADO: ALTERAÇÃO SILENCIOSA NESTE ENSAIO
```

Exibir a legenda obrigatória:

> **Este teste representa uma corrupção controlada do payload. Ele não é o teste de alteração do ciphertext AES-GCM.**

## 3.7 Estado 6 — repetir exatamente a mesma falha com CRC32

Sem pedir nova seleção, repetir o mesmo índice e máscara com `FAULT CRC32`.

Mostrar:

```text
CRC salvo:        0x........
CRC recalculado:  0x........
RESULTADO: FALHA DETECTADA
```

Mensagem principal:

> **O CRC transformou a alteração acidental em um erro observável.**

Mensagem secundária:

> **Ele não impede um atacante de recalcular o checksum.**

A comparação deve usar o mesmo payload, byte e máscara. Não sorteie uma segunda falha.

## 3.8 Estado 7 — conclusão

Exibir somente três conclusões principais:

```text
1. ML-KEM estabeleceu uma chave pós-quântica no ESP32.
2. O custo maior apareceu principalmente em tempo e bytes.
3. CRC32 detectou o single-bit flip do ensaio, mas não substitui autenticação criptográfica.
```

Abaixo, três cartões:

- **ML-KEM:** estabelece a chave;
- **AES-GCM:** cifra e autentica;
- **CRC32:** detecta erro acidental.

Botões opcionais:

- `VER DETALHES TÉCNICOS`;
- `RECOMEÇAR`.

Reinício automático após 12–20 segundos sem interação.

## 3.9 Modo aprofundado opcional

Somente após o fluxo principal estar pronto.

Pode incluir:

- fases `KEYGEN`, `ENCAP`, `DECAP`;
- heap e min-heap;
- composição do pacote;
- resultados oficiais de 100 amostras;
- mutação de ciphertext AES-GCM e rejeição por tag, se implementada e validada;
- `PQC_FAULT ... CONFIRM` e diferença entre `KEY_MISMATCH` e `PROTOCOL_REJECT`.

Não colocar esses detalhes no fluxo de 90 segundos.

---

# 4. Arquitetura recomendada de software

## 4.1 Estratégia

Preferência:

> adicionar um modo `--stand` ou `--kiosk` ao dashboard atual, reutilizando sua bridge serial, parser de respostas, componentes visuais e consolidação de métricas.

Alternativa aceitável:

> criar `stand_demo.py` como shell visual que importa/adapta os módulos existentes sem duplicar o protocolo.

Evitar:

- copiar e colar todo `dashboard.py`;
- criar um segundo parser serial incompatível;
- executar criptografia no notebook;
- usar Streamlit ou servidor web novo apenas para a demonstração, salvo se o projeto já usar essa arquitetura.

## 4.2 Máquina de estados

Implementar estados explícitos, por exemplo:

```python
class DemoState(Enum):
    ATTRACT = auto()
    INTRO = auto()
    RUN_240 = auto()
    RUN_80 = auto()
    SELECT_BIT = auto()
    FAULT_NONE = auto()
    FAULT_CRC = auto()
    SUMMARY = auto()
    ERROR = auto()
```

Requisitos:

- transições centralizadas;
- cada estado sabe quais eventos aceita;
- cliques repetidos e button bounce não podem disparar comandos duplicados;
- comandos seriais devem ter timeout;
- a UI não pode bloquear enquanto espera a placa;
- após erro, oferecer `TENTAR NOVAMENTE` e `VOLTAR AO INÍCIO`;
- o reset deve limpar apenas a sessão visual, não apagar logs.

## 4.3 Separação entre dados medidos e animação

Criar estruturas distintas:

```python
@dataclass
class HardwareMeasurement:
    command: str
    profile_mhz: int
    elapsed_us: int
    bytes_total: int
    result: str
    raw_response: dict

@dataclass
class AnimationModel:
    duration_ms: int
    label: str
    scale_factor: float
```

Nunca use a duração visual como medição.

## 4.4 Configuração

Criar arquivo como `config/stand_demo.yaml` ou equivalente:

```yaml
payload: "PQC-SAT|SEQ=042|TEMP=84|SAFE=1"
auto_reset_seconds: 15
serial_timeout_seconds: 8
kiosk_fullscreen: true
animation:
  min_duration_ms: 1000
  max_duration_ms: 5500
profiles:
  baseline_mhz: 240
  limited_mhz: 80
```

A configuração deve permitir ensaio em tela menor e alteração do payload sem editar código.

## 4.5 Logging da sessão

Cada ciclo deve gerar registro JSONL ou JSON com:

- timestamp;
- revisão Git;
- versão de firmware, se disponível;
- porta serial;
- handshake;
- payload;
- comandos enviados;
- respostas cruas;
- bit selecionado;
- resultados de `FAULT NONE` e `FAULT CRC32`;
- erros e timeouts;
- modo `hardware` ou `simulated`.

Não armazenar dados pessoais; o visitante não digita nada.

## 4.6 Modo simulado e fallback

O modo simulado deve servir para:

- desenvolver sem placa;
- ensaiar layout;
- manter uma demonstração de contingência.

Regras:

- exibir permanentemente `MODO VISUAL SIMULADO`;
- não apresentar os valores como leitura atual da placa;
- carregar métricas de fixture ou campanha oficial com origem identificada;
- nunca entrar automaticamente em modo simulado sem avisar o expositor;
- permitir alternância somente por argumento de linha de comando ou tela protegida.

---

# 5. Etapa 0 — auditoria obrigatória do que já existe

Antes de implementar qualquer funcionalidade, produzir `docs/stand/AUDIT_EXISTING.md`.

## 5.1 Preservação e inventário

Executar e registrar:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git log -5 --oneline
find . -maxdepth 3 -type f | sort
```

Criar branch:

```bash
git switch -c feat/sbpc-stand-demo
```

Se houver alterações não commitadas, não sobrescrever. Fazer backup ou commit de preservação conforme política do repositório.

## 5.2 Localização dos componentes

Usar busca equivalente a:

```bash
rg -n "MISSION|FAULT|PQC_FAULT|BUTTON_PING|SAT CONECTADO|simulated" .
rg -n "AES-128|AES-256|GCM|ML-KEM|CRC32|EDB88320" .
rg -n "240|80|cpu|frequency|setCpuFrequencyMhz" .
rg -n "ttyUSB|serial|handshake|timeout" .
```

Identificar:

- entrypoint do dashboard;
- framework visual;
- bridge serial;
- parser dos comandos;
- firmware principal;
- bibliotecas criptográficas;
- comando ou mecanismo de alteração de frequência;
- tratamento do botão e potenciômetro;
- runner de bateria;
- logs oficiais;
- testes existentes;
- arquivos de dependências e instruções de build/flash.

## 5.3 Reproduzir a versão atual sem alterações

Critérios mínimos:

1. ambiente instala do zero;
2. firmware compila;
3. dashboard abre;
4. placa realiza handshake;
5. `MISSION CLASSIC`, `MISSION PQC` e `MISSION PQC_CRC32` retornam sucesso;
6. `FAULT NONE` retorna o estado documentado;
7. `FAULT CRC32` detecta a mesma classe de falha;
8. botão emite evento;
9. potenciômetro produz leitura utilizável;
10. resultados são exportados.

Gravar um vídeo curto ou sequência de screenshots da versão original. Isso é a referência de regressão.

## 5.4 Auditar a verdade técnica

Responder no documento de auditoria:

- Qual tamanho de chave AES é efetivamente usado?
- Qual biblioteca implementa GCM?
- Como nonce e tag são gerados e verificados?
- `CLASSIC` possui ou não mecanismo assimétrico?
- Onde o CRC é calculado?
- Em qual ponto o payload é mutado no comando `FAULT`?
- A falha ocorre antes da cifragem, depois da decifragem ou em harness separado?
- Como o bit é escolhido pelo potenciômetro?
- É possível repetir exatamente a mesma falha nos modos `NONE` e `CRC32`?
- A mudança 240/80 MHz ocorre durante execução, reboot ou build separado?
- O botão pode ser usado para avançar a demonstração sem modificar firmware?
- O modo simulado está claramente identificado?
- Qual JSON é a campanha oficial atual?

## 5.5 Gate de saída da auditoria

Não iniciar mudanças visuais até existir uma tabela:

| Afirmação | Documentação | Código observado | Teste executado | Decisão da UI |
|---|---|---|---|---|
| AES-128 ou AES-256 | ... | ... | ... | ... |
| função de CLASSIC | ... | ... | ... | ... |
| localização do bit flip | ... | ... | ... | ... |
| perfil 80 MHz | ... | ... | ... | ... |

---

# 6. Plano de implementação em etapas

## Etapa 1 — criar o esqueleto do modo estande

Entregas:

- argumento `--stand`/`--kiosk`;
- tela cheia e modo janela para desenvolvimento;
- máquina de estados;
- fluxo com dados mockados;
- reset automático;
- tecla administrativa `Esc` para sair de tela cheia;
- indicador discreto de hardware conectado.

Critérios de aceite:

- fluxo inteiro pode ser percorrido sem placa;
- nenhuma tela exige scroll;
- textos principais são legíveis em 1366×768 e 1920×1080;
- ação do visitante é sempre evidente;
- após inatividade, retorna à tela inicial.

## Etapa 2 — integrar hardware e comandos existentes

Entregas:

- handshake obrigatório;
- fila de comandos não bloqueante;
- `BUTTON_PING` avançando estados permitidos;
- leitura do potenciômetro;
- execução de `MISSION` real;
- parser tipado de respostas;
- tratamento de timeout e desconexão.

Critérios de aceite:

- a UI nunca apresenta métrica de hardware antes de receber a resposta;
- comando duplicado não ocorre com dois cliques rápidos;
- desconectar e reconectar USB não exige reiniciar todo o sistema, se tecnicamente viável;
- caso não seja viável, a tela informa instrução simples de recuperação.

## Etapa 3 — comparação baseline/PQC

Entregas:

- mesma mensagem nos dois cenários;
- cartões de tempo, bytes e resultado;
- decomposição opcional de ML-KEM;
- animação proporcional limitada;
- rótulos tecnicamente corretos.

Cálculos dinâmicos:

```text
ratio_time = pqc.elapsed_us / baseline.elapsed_us
ratio_bytes = pqc.bytes_total / baseline.bytes_total
```

Tratar divisão por zero e respostas incompletas.

Critérios de aceite:

- números da UI iguais aos retornados pela placa;
- razão recalculada corretamente;
- payload e perfil idênticos entre as duas execuções;
- não chamar baseline de ECDH.

## Etapa 4 — comparação 240/80 MHz

Entregas:

- troca real de perfil ou painel de campanha oficial;
- indicação inequívoca de `AO VIVO` ou `CAMPANHA OFICIAL`;
- gráfico simples de duas barras;
- bytes comparados.

Critérios de aceite:

- perfil confirmado pelo firmware;
- não derivar consumo de energia;
- não afirmar relação universal para todo CubeSat;
- restauração segura para 240 MHz ao terminar ou reiniciar.

## Etapa 5 — interação do bit flip

Entregas:

- potenciômetro mapeado para índice/máscara;
- visual binário antes/depois;
- mesmo bit usado nos dois ensaios;
- `FAULT NONE` seguido de `FAULT CRC32`;
- CRC original e recalculado, se disponíveis;
- localização conceitual da falha coerente com o código.

Critérios de aceite:

- XOR real confirmado;
- single-bit flip, não byte aleatório;
- mudança mostrada na UI corresponde ao byte efetivamente enviado;
- 20 repetições consecutivas apresentam resultados coerentes;
- o texto não sugere que CRC identifica um atacante.

## Etapa 6 — tornar AES-GCM visível sem distorção

P0 mínimo:

- mostrar AES-GCM na cadeia normal de proteção;
- explicar que ele cifra e autentica;
- explicar que o ensaio CRC ocorre em uma camada diferente.

P1, somente se seguro e rápido:

- adicionar comando de teste que altere um bit do ciphertext ou tag após a cifragem;
- verificar que a decifragem autenticada rejeita a mensagem;
- exibir `TAG INVÁLIDA — MENSAGEM REJEITADA`;
- cobrir com testes automatizados.

Não implemente um “ataque” teatral que contorne a API correta do GCM ou aceite plaintext antes da verificação da tag.

## Etapa 7 — acabamento visual e acessibilidade

Entregas:

- tipografia grande;
- contraste adequado;
- ícones acompanhados por texto;
- não depender apenas de cor verde/vermelha;
- animações sem flashes intensos;
- fluxo utilizável sem áudio;
- área principal com no máximo três números simultâneos;
- tela de detalhes separada.

Evitar:

- terminal rolando na tela principal;
- hexadecimal excessivo;
- gráficos pequenos;
- janelas arrastáveis no fluxo de estande;
- textos longos;
- efeitos que ocultem o hardware real.

## Etapa 8 — robustez e operação offline

Entregas:

- script único de inicialização, por exemplo `./scripts/run_stand.sh`;
- verificação de porta serial;
- checagem de dependências;
- logs em diretório datado;
- bloqueio de suspensão de tela durante a execução;
- opção de reiniciar somente a interface;
- modo de diagnóstico protegido;
- pacote de fixtures offline;
- vídeo de backup da experiência completa.

O vídeo de backup não substitui a demonstração, mas evita estande vazio em caso de falha irrecuperável de hardware.

## Etapa 9 — documentação operacional

Criar:

```text
docs/stand/AUDIT_EXISTING.md
docs/stand/EXPERIENCE_SPEC.md
docs/stand/RUNBOOK.md
docs/stand/SCIENTIFIC_ACCURACY.md
docs/stand/FINAL_VALIDATION.md
```

O `RUNBOOK.md` deve permitir que outra pessoa monte e opere o estande sem conhecer o código.

---

# 7. Estrutura física recomendada

## 7.1 Elementos mínimos

- notebook com fonte;
- monitor externo, se disponibilizado;
- BlackBoard Wisdom/ESP32;
- cabo USB principal e reserva;
- extensão/filtro de linha;
- caixa transparente ou suporte que deixe placa, botão e potenciômetro visíveis;
- etiqueta grande no botão: `INICIAR / VIRAR BIT`;
- etiqueta no potenciômetro: `ESCOLHA O BIT`;
- proteção para impedir que o visitante puxe o cabo;
- fita, abraçadeiras e velcro;
- mouse e teclado guardados para operação técnica;
- QR code opcional para repositório, relatório ou pôster, sem ser necessário para executar a demo.

## 7.2 Não depender de

- internet;
- som ambiente;
- projetor específico;
- celular do visitante;
- login;
- Bluetooth;
- rede do evento.

## 7.3 Cartaz de apoio

Título:

> **Criptografia pós-quântica cabe em um computador de satélite?**

Subtítulo:

> ML-KEM + AES-GCM + detecção de bit flips em um ESP32 usado como OBC educacional.

Rodapé obrigatório:

> Falhas e ambiente espacial são simulados logicamente. A placa não possui qualificação para voo.

---

# 8. Roteiro oral do expositor

## 8.1 Abordagem de 15 segundos

> Um satélite envia um comando crítico, mas um único bit pode mudar no caminho ou na memória. Aqui você consegue comparar o custo da criptografia pós-quântica e escolher fisicamente qual bit será alterado. Quer tentar salvar a missão?

## 8.2 Durante a comparação

> Este primeiro cenário é nosso baseline AES-GCM. Agora adicionamos ML-KEM, que não cifra a mensagem: ele estabelece a chave que o AES usa. Veja que funcionou, mas custou mais tempo e mais bytes.

## 8.3 Durante 80 MHz

> Quando reduzimos o clock experimentalmente de 240 para 80 MHz, o pacote não cresce, mas o processamento demora mais.

## 8.4 Durante o bit flip

> Gire o controle e escolha um bit. Primeiro vamos alterar o payload sem um guardião adicional. Agora repetimos exatamente a mesma alteração com CRC32.

## 8.5 Fechamento

> O resultado não é que CRC substitui criptografia. ML-KEM estabelece a chave, AES-GCM cifra e autentica, e CRC32 ajuda a tornar uma corrupção acidental observável. Em sistemas espaciais, segurança também consome orçamento de tempo, memória e comunicação.

---

# 9. Plano de testes

## 9.1 Testes automatizados

Criar ou ampliar testes para:

- parser de cada resposta serial;
- máquina de estados;
- rejeição de eventos fora de ordem;
- timeout;
- cálculo das razões;
- mapeamento potenciômetro → índice/máscara;
- XOR de um único bit;
- preservação da mesma falha entre `NONE` e `CRC32`;
- serial mockado;
- carga de fixtures oficiais;
- reset automático;
- rotulagem de modo simulado.

## 9.2 Matriz de integração

| Caso | Perfil | Cenário | Hardware | Resultado esperado |
|---|---:|---|---|---|
| missão baseline | 240 | CLASSIC | conectado | DELIVERED |
| missão PQC | 240 | PQC | conectado | DELIVERED |
| missão PQC | 80 | PQC | conectado | DELIVERED |
| falha sem CRC | 240 | FAULT NONE | conectado | SILENT, conforme harness atual |
| mesma falha com CRC | 240 | FAULT CRC32 | conectado | DETECTED_GUARD |
| desconexão antes da missão | qualquer | qualquer | desconectado | nenhum dado inventado |
| timeout | qualquer | qualquer | mock | tela de recuperação |
| modo simulado | 240 | todos | desconectado | rótulo permanente |

Repetir também em 80 MHz se o comando de falha depender do perfil.

## 9.3 Teste de resistência do estande

Executar no mínimo:

- 30 ciclos completos consecutivos;
- 100 ações de botão;
- 100 alterações de potenciômetro;
- 10 desconexões/reconexões USB controladas;
- 2 horas de execução contínua no modo atração;
- 1 hora de ciclos periódicos sem reiniciar o aplicativo.

Registrar:

- crashes;
- memória do notebook;
- heap da placa;
- latência de resposta serial;
- falhas de renderização;
- comandos perdidos;
- necessidade de reinício.

## 9.4 Teste de compreensão com pessoas

Convidar pelo menos cinco pessoas que não participaram do projeto.

Após a experiência, perguntar sem induzir:

1. O que o ML-KEM fez?
2. O que o AES-GCM fez?
3. O que o CRC32 fez?
4. Houve radiação real?
5. Qual foi o principal custo observado?

Critério de aceite:

- pelo menos 4/5 conseguem explicar que ML-KEM estabelece chave;
- pelo menos 4/5 não dizem que CRC protege contra invasor;
- pelo menos 4/5 entendem que o bit flip foi simulado;
- duração mediana inferior a 100 segundos.

Se falhar, simplificar o texto; não adicionar mais explicações.

---

# 10. Critérios de completude e Definition of Done

A entrega só está completa quando todos os itens P0 estiverem satisfeitos.

## P0 — obrigatório para o evento

- [ ] versão original preservada;
- [ ] auditoria técnica concluída;
- [ ] AES-128/256 resolvido pelo código;
- [ ] baseline nomeado corretamente;
- [ ] localização da falha CRC descrita corretamente;
- [ ] modo estande em tela cheia;
- [ ] fluxo de até 100 segundos;
- [ ] botão físico inicia e avança a experiência;
- [ ] potenciômetro seleciona bit;
- [ ] `MISSION CLASSIC` e `MISSION PQC` usam mesmo payload;
- [ ] comparação 240/80 funciona ao vivo ou está claramente identificada como campanha oficial;
- [ ] mesma falha é repetida em `NONE` e `CRC32`;
- [ ] métricas vêm de hardware ou fixture identificada;
- [ ] modo simulado explicitamente rotulado;
- [ ] reset automático;
- [ ] funcionamento offline;
- [ ] 30 ciclos sem crash;
- [ ] runbook pronto;
- [ ] vídeo de backup pronto;
- [ ] ensaio geral concluído.

## P1 — desejável

- [ ] teste visual de alteração de ciphertext com rejeição AES-GCM;
- [ ] modo aprofundado técnico;
- [ ] recuperação automática de USB;
- [ ] cartaz/QR code;
- [ ] caixa transparente acabada.

## P2 — não bloquear a entrega

- [ ] sons;
- [ ] iluminação externa;
- [ ] animação 3D;
- [ ] segundo ESP32;
- [ ] rádio real;
- [ ] ranking de visitantes;
- [ ] medição de energia com sensor externo.

---

# 11. Cronograma comprimido até o início da SBPC

A 78ª Reunião Anual começa em **26 de julho de 2026**. Ajuste as datas ao horário real de acesso ao estande, mas preserve a ordem.

## 20 de julho — auditoria e congelamento da base

- localizar repositório e hardware;
- reproduzir a demonstração original;
- resolver inconsistências técnicas;
- criar branch;
- definir wireframe;
- registrar vídeo baseline.

Saída: `AUDIT_EXISTING.md` aprovado.

## 21 de julho — esqueleto do modo estande

- máquina de estados;
- tela de atração;
- fluxo completo com mocks;
- tela final e reset;
- modo janela/tela cheia.

Saída: experiência navegável sem placa.

## 22 de julho — integração serial e comparação criptográfica

- handshake;
- botão;
- comandos `MISSION`;
- cartões de tempo/bytes;
- logging;
- comparação 240/80.

Saída: primeira execução real ponta a ponta.

## 23 de julho — bit flip e integridade

- potenciômetro;
- visual antes/depois;
- `FAULT NONE`;
- repetição com `FAULT CRC32`;
- revisão rigorosa das legendas.

Saída: núcleo interativo completo.

## 24 de julho — robustez, acessibilidade e fallback

- testes automatizados;
- recuperação de erros;
- fixtures;
- vídeo de backup;
- scripts de inicialização;
- revisão em resoluções diferentes.

Saída: release candidate.

## 25 de julho — congelamento e ensaio geral

- 30 ciclos completos;
- teste com público leigo;
- montagem física;
- revisão do runbook;
- backup em mídia local;
- tag de release.

Não adicionar funcionalidades depois do ensaio, salvo correção crítica.

## 26 de julho — operação

- chegar com antecedência;
- validar energia e tela;
- executar checklist de abertura;
- manter vídeo e modo simulado acessíveis, mas não ativos por padrão;
- registrar incidentes para correções entre os dias do evento.

---

# 12. Runbook mínimo a ser produzido

## Checklist de abertura

1. conectar fonte e monitor;
2. conectar Wisdom por USB;
3. impedir suspensão do notebook;
4. confirmar porta serial;
5. executar script de diagnóstico;
6. confirmar handshake;
7. realizar uma missão baseline;
8. realizar uma missão PQC;
9. testar botão;
10. testar potenciômetro;
11. testar `FAULT NONE` e `FAULT CRC32`;
12. iniciar modo estande;
13. conferir rótulo de hardware real;
14. limpar a mesa e proteger cabos.

## Recuperação rápida

### Dashboard travou

- encerrar somente a aplicação;
- salvar/copiar log atual;
- reiniciar com `run_stand.sh`;
- executar teste rápido.

### Placa desconectou

- voltar à tela de diagnóstico;
- reconectar cabo;
- identificar porta;
- refazer handshake;
- nunca continuar exibindo dados como se fossem atuais.

### Firmware não responde

- reset físico;
- serial console de diagnóstico;
- usar placa/cabo reserva se disponível;
- migrar temporariamente para modo visual simulado, informando claramente.

### Tela externa falhou

- usar display do notebook;
- iniciar perfil de resolução reduzida;
- não usar janelas arrastáveis.

## Checklist de encerramento

- encerrar aplicativo;
- copiar logs do dia;
- registrar incidentes;
- desligar placa corretamente;
- guardar cabos e hardware;
- carregar notebook;
- testar novamente antes do dia seguinte.

---

# 13. Entregáveis finais exigidos do agente

## Código

- modo estande funcional;
- testes;
- fixtures;
- scripts de execução e diagnóstico;
- alterações de firmware estritamente necessárias;
- configuração de demonstração.

## Documentação

- auditoria do estado anterior;
- especificação da experiência;
- runbook;
- precisão científica;
- relatório final de validação;
- changelog.

## Evidências

- vídeo do fluxo completo em hardware;
- screenshot de cada estado;
- log de um ciclo completo;
- resultado dos testes automatizados;
- resultado dos 30 ciclos;
- tabela das cinco avaliações com público leigo;
- hash do commit e tag de release.

## Relatório final obrigatório

O arquivo `docs/stand/FINAL_VALIDATION.md` deve terminar com esta tabela:

| Item | Estado | Evidência | Limitação restante |
|---|---|---|---|
| Hardware real | PASS/FAIL | link/caminho | ... |
| Baseline/PQC | PASS/FAIL | log | ... |
| 240/80 MHz | PASS/FAIL | log | ... |
| Bit flip | PASS/FAIL | log/vídeo | ... |
| CRC32 | PASS/FAIL | log | ... |
| Precisão científica | PASS/FAIL | revisão | ... |
| 30 ciclos | PASS/FAIL | relatório | ... |
| Offline | PASS/FAIL | teste | ... |
| Fallback | PASS/FAIL | vídeo/fixture | ... |

Não declarar `PASS` sem evidência.

---

# 14. Riscos prioritários

| Risco | Probabilidade | Impacto | Mitigação |
|---|---:|---:|---|
| documentação diverge do firmware | alta | alta | auditoria antes da UI |
| chamar baseline simétrico de criptografia clássica completa | alta | alta | renomear e explicar limite |
| narrativa errada de CRC versus GCM | alta | alta | localizar a falha e separar camadas |
| USB/serial instável no estande | média | alta | cabo reserva, timeout, reconexão, fallback |
| UI complexa demais | alta | média | máquina de estados e fluxo fixo |
| visitante não percebe microssegundos | alta | média | animação didática rotulada + números reais |
| fila longa | média | média | duração menor que 100 s e auto-reset |
| ausência de internet | alta | baixa se preparado | funcionamento totalmente offline |
| alteração tardia quebra a versão estável | média | alta | branch, tag e congelamento em 25/07 |
| botão sofre bounce ou múltiplos eventos | média | média | debounce e bloqueio por estado |
| 80 MHz exige reboot demorado | desconhecida | média | usar campanha oficial claramente rotulada |

---

# 15. Escopo que não deve ser absorvido agora

Não transformar esta entrega em:

- protocolo espacial completo;
- sistema de telecomunicações por rádio;
- pesquisa de tolerância física à radiação;
- implementação de FEC;
- estudo de consumo energético sem instrumento;
- comparação completa ECDH versus ML-KEM;
- redesign integral do firmware;
- auditoria formal de side-channel;
- produto multiusuário na web.

Esses são trabalhos futuros. O objetivo atual é uma **experiência pública robusta, curta e cientificamente honesta**, baseada no experimento já executado.

---

# 16. Fontes e insumos documentais

## Material interno a localizar

- `GUIA_FINAL_APRESENTACAO.md`, estado documental de 2 de julho de 2026;
- `dashboard.py`;
- firmware da BlackBoard Wisdom/ESP32;
- `tools/serial_console.py` ou equivalente;
- runner das campanhas;
- `logs/20260702T044907Z_final_metrics_dev-ttyusb0.json` ou coleta oficial mais recente validada.

## Fontes técnicas oficiais

- NIST FIPS 203 — Module-Lattice-Based Key-Encapsulation Mechanism Standard:  
  https://csrc.nist.gov/pubs/fips/203/final
- NIST SP 800-38D — Galois/Counter Mode for authenticated encryption:  
  https://csrc.nist.gov/pubs/sp/800/38/d/final
- NASA — Effects of space radiation on electronic microcircuits / Single Event Upset:  
  https://ntrs.nasa.gov/citations/19890014178

## Contexto oficial do evento

- 78ª Reunião Anual da SBPC:  
  https://ra.sbpcnet.org.br/78RA/
- Apresentação e objetivo de difusão científica para a população:  
  https://ra.sbpcnet.org.br/78RA/sobre-a-reuniao/apresentacao/

---

# 17. Resumo executivo para o agente

Não construa uma nova exposição do zero. Converta o dashboard existente em uma missão guiada de 90 segundos.

A sequência é:

```text
BOTÃO → PAYLOAD → BASELINE/PQC EM 240 MHz → PQC EM 80 MHz
      → POTENCIÔMETRO ESCOLHE BIT → FALHA SEM CRC
      → MESMA FALHA COM CRC → CONCLUSÃO → RESET
```

A promessa ao visitante é:

> “Você vai escolher um bit, alterá-lo de verdade no experimento e descobrir qual camada percebe a falha.”

A conclusão científica é:

> ML-KEM-512 funcionou no ESP32 e aumentou principalmente o custo de tempo e tráfego; AES-GCM continuou responsável por cifrar e autenticar a mensagem; CRC32 tornou o single-bit flip controlado observável na região de payload testada.

A entrega está pronta apenas quando outra pessoa consegue ligar o equipamento, executar 30 ciclos sem falha, explicar corretamente as três tecnologias e recuperar o sistema seguindo o runbook.
