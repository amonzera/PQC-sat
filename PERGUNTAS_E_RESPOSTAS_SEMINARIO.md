# Perguntas e respostas prováveis do seminário - PQC-SAT

Este arquivo serve para treino antes da apresentação. Ele reúne perguntas que
podem surgir de alunos, professor ou banca, com respostas diretas e alinhadas
ao que o projeto realmente implementa.

Regra principal de defesa: **não superafirmar**. O projeto demonstra custo e
comportamento em uma BlackBoard Wisdom/ESP32 usada como OBC educacional
inspirado em CubeSat. Ele não mede radiação física, energia elétrica real nem
representa um CubeSat completo.

## 1. Resposta de 30 segundos sobre o projeto

**Pergunta:** Qual é a ideia central do projeto?

**Resposta curta:** O projeto mostra que migrar para criptografia
pós-quântica em hardware limitado tem custo real. Na Wisdom/ESP32, uma
mensagem clássica autenticada com HMAC-SHA256 levou em média 511 us e 73 bytes.
Quando usamos ML-KEM-512 no fluxo PQC, a entrega foi para 13.234 us e 841
bytes. Com PQC mais CRC32, ficou em 13.130 us e 845 bytes. A parte de bit-flip
mostra que, sem guardião, 600/600 corrupções passaram silenciosamente; com
CRC32, 600/600 foram detectadas.

**Resposta completa:** Estamos simulando a lógica de um computador de bordo
COTS inspirado em CubeSat. A placa recebe uma mensagem curta e a processa em
três cenários: `CLASSIC`, `PQC` e `PQC_CRC32`. O objetivo não é provar que essa
placa é um satélite, mas tornar visível a dificuldade de colocar criptografia
mais pesada em um ambiente com CPU, RAM, tráfego e energia limitados.

## 2. Perguntas sobre objetivo e escopo

### O que exatamente vocês querem provar?

Queremos demonstrar, de forma didática e mensurável, que PQC funciona em
hardware embarcado, mas custa mais tempo e tráfego que um baseline clássico
simétrico. Também queremos mostrar que mecanismos de integridade ajudam a
tornar falhas de bit visíveis, mas adicionam mais trabalho ao sistema.

### Vocês estão provando que PQC é inviável em CubeSats?

Não. A conclusão correta é mais cuidadosa: PQC é viável na nossa placa, mas
tem custo relevante. Em sistemas espaciais pequenos, esse custo precisa entrar
no projeto de CPU, memória, tráfego e energia.

### A Wisdom é um CubeSat real?

Não. Ela representa um OBC COTS educacional, ou seja, um computador de bordo
didático. Usamos a placa para reproduzir restrições típicas de sistemas
embarcados, não para afirmar que ela tem todos os requisitos ambientais,
elétricos e mecânicos de um CubeSat real.

### Por que usar um equipamento de bancada para falar de CubeSat?

Porque muitos CubeSats educacionais usam componentes COTS ou próximos disso.
A placa permite medir na prática CPU, heap, tempo, bytes e comunicação serial.
Isso torna o problema concreto para uma turma de Ciência da Computação.

### Qual é a mensagem principal para o público?

Segurança não é grátis. Ao sair de um fluxo clássico barato para um fluxo
pós-quântico, o custo de tempo e comunicação aumenta bastante. Quando somamos
verificação de integridade para lidar com corrupção de bits, o sistema ganha
visibilidade de falha, mas consome mais recursos.

### O projeto é sobre confidencialidade, autenticação ou integridade?

Principalmente sobre custo de comunicação segura e integridade operacional.
O fluxo `MISSION` autentica a mensagem com HMAC-SHA256. O ML-KEM-512 entra
para estabelecer um segredo compartilhado pós-quântico. O CRC32 entra como
guardião didático de corrupção de payload, não como criptografia.

## 3. Perguntas sobre criptografia básica

### O que é criptografia clássica no projeto?

No nosso baseline, "clássica" significa autenticar uma mensagem com
HMAC-SHA256 usando uma chave simétrica didática. Não estamos comparando contra
uma pilha clássica assimétrica completa, como ECDH + HMAC. Essa é uma limitação
assumida.

### O que é HMAC-SHA256?

HMAC-SHA256 é um código de autenticação de mensagem. Ele usa uma chave secreta
e uma função hash, SHA-256, para gerar uma tag. Quem tem a mesma chave consegue
verificar se a mensagem veio de quem deveria e se não foi alterada.

### HMAC criptografa a mensagem?

Não. HMAC autentica. Ele não esconde o conteúdo. Ele diz se a mensagem confere
com a chave esperada e se foi alterada.

### O que é criptografia pós-quântica?

É uma família de algoritmos projetados para continuar seguros mesmo contra
computadores quânticos grandes. Ela tenta substituir partes vulneráveis de
protocolos atuais, como RSA e ECDH, que seriam afetados por algoritmos
quânticos como Shor.

### Por que computadores quânticos ameaçam RSA e ECDH?

RSA depende da dificuldade de fatorar números grandes. ECDH depende de
logaritmo discreto em curvas elípticas. Um computador quântico grande, com
correção de erros suficiente, poderia usar o algoritmo de Shor para quebrar
esses problemas de forma muito mais eficiente que computadores clássicos.

### O que é ML-KEM?

ML-KEM é um mecanismo de encapsulamento de chave padronizado pelo NIST em
FIPS 203. Ele é baseado em problemas de reticulados. No projeto usamos
ML-KEM-512.

### O que significa KEM?

KEM significa Key Encapsulation Mechanism, ou mecanismo de encapsulamento de
chave. Ele não cifra uma mensagem diretamente. Ele cria um segredo
compartilhado entre duas pontas. Depois esse segredo pode alimentar HMAC,
cifras simétricas ou outros passos de protocolo.

### O ML-KEM cifra a mensagem do projeto?

Não diretamente. No nosso fluxo, o ML-KEM estabelece um segredo. Esse segredo
é usado para autenticar a mensagem com HMAC-SHA256. A mensagem em si não está
sendo cifrada como em AES-GCM, por exemplo.

### Por que não usar AES para cifrar a mensagem?

Porque o foco do seminário é medir o custo da troca/acordo de segredo
pós-quântico em hardware limitado e comparar com um baseline simples. AES ou
AES-GCM seriam uma evolução natural para uma pilha mais completa, mas
aumentariam o escopo da apresentação.

### Por que não usar assinatura pós-quântica?

Assinaturas pós-quânticas são importantes, mas o projeto escolheu ML-KEM
porque o problema didático é acordo de segredo e custo de comunicação. Uma
assinatura, como ML-DSA, mudaria o tipo de protocolo e as métricas.

### Por que ML-KEM-512 e não outro nível?

ML-KEM-512 é o menor conjunto de parâmetros da família ML-KEM e é mais
adequado para uma primeira demonstração em hardware limitado. Parâmetros
maiores tenderiam a consumir mais bytes, tempo e memória.

### O que são `keygen`, `encap` e `decap`?

`keygen` gera o par de chaves ML-KEM. `encap` encapsula um segredo usando a
chave pública. `decap` recupera o segredo usando a chave secreta. Essas três
etapas são as que aparecem no popup de métricas.

### O que é segredo compartilhado?

É um valor que duas pontas conseguem obter e que um observador externo não
deveria conhecer. No projeto, o segredo compartilhado do ML-KEM tem 32 bytes.

### O que é ciphertext?

É o dado gerado no encapsulamento ML-KEM. Ele é enviado para a outra ponta,
que usa a chave secreta para decapsular e chegar ao mesmo segredo.

### O que é checksum?

Checksum é um valor calculado a partir dos dados para detectar alterações. No
projeto usamos CRC32 no payload.

### CRC32 é criptografia?

Não. CRC32 não é seguro contra atacante malicioso. Ele é bom para detectar
erros acidentais, como bit-flips. Por isso ele é apresentado como guardião de
integridade contra corrupção de payload, não como mecanismo criptográfico.

### CRC32 aumenta segurança?

Depende do sentido de segurança. Ele não aumenta segurança contra um atacante
que consegue modificar mensagem e recomputar CRC. Mas aumenta robustez contra
corrupção acidental, porque transforma falha silenciosa em erro detectado.

### Por que usar CRC32 se HMAC já detecta alteração?

Porque eles respondem a perguntas diferentes no roteiro. HMAC é autenticação
criptográfica. CRC32 é um guardião simples e visual para mostrar corrupção de
payload por bit-flip. A demonstração A/B fica didática: sem CRC32 há falha
silenciosa; com CRC32 há detecção.

## 4. Perguntas sobre radiação e bit-flips

### Vocês usaram radiação real?

Não. O projeto simula manualmente o efeito de radiação por bit-flip. Isso
significa escolher um byte e inverter um bit de forma controlada.

### Por que simular bit-flip manualmente?

Porque é reproduzível, seguro e adequado para apresentação em sala. Radiação
real exigiria equipamento especializado, controle ambiental e protocolos de
segurança que fogem do escopo da disciplina.

### O que é um bit-flip?

É a inversão de um bit: 0 vira 1 ou 1 vira 0. Em memória ou transmissão, isso
pode alterar uma mensagem, chave, ciphertext ou dado de sensor.

### Como o projeto detecta bit-flip?

Depende do cenário. No payload com CRC32, o CRC antes e depois não bate, então
o resultado vira `DETECTED_GUARD`. No fluxo ML-KEM com confirmação, se o
ciphertext for corrompido e os segredos divergirem, a confirmação HMAC-SHA256
transforma isso em `PROTOCOL_REJECT`.

### ML-KEM detecta automaticamente todo ciphertext corrompido?

Não é correto dizer isso. O que o projeto mostra é que a decapsulação pode
gerar um segredo diferente. O harness compara os segredos e identifica
`KEY_MISMATCH`. Quando adicionamos confirmação de chave com HMAC-SHA256, a
divergência vira `PROTOCOL_REJECT`.

### O que é `KEY_MISMATCH`?

É quando as duas pontas não chegaram ao mesmo segredo compartilhado. No
projeto, isso aparece quando corrompemos o ciphertext ML-KEM e comparamos os
segredos derivados.

### O que é `PROTOCOL_REJECT`?

É quando o protocolo rejeita a sessão porque a confirmação autenticada falhou.
No projeto, isso ocorre no `PQC_FAULT ... CONFIRM`, que usa HMAC-SHA256 para
confirmar se a chave derivada bate.

### O que é falha silenciosa?

É quando um dado foi alterado, mas o sistema aceita ou segue em frente sem
perceber. No projeto, sem CRC32 no payload, a coleta final registrou 600/600
falhas silenciosas.

### O que é erro detectado?

É quando o sistema percebe que algo foi alterado e marca a entrega como
inválida ou suspeita. Com CRC32, a coleta final registrou 600/600 falhas
detectadas.

### CRC32 detecta qualquer erro?

Não qualquer erro possível. Ele é muito bom para muitos erros acidentais e
detecta os single-bit flips usados no projeto, mas não deve ser apresentado
como proteção universal.

### Por que testar single-bit e não bursts de falha?

Single-bit é simples, reproduzível e suficiente para demonstrar o conceito.
Bursts, múltiplos bits e falhas fora da região coberta são próximos passos
para uma evolução científica.

## 5. Perguntas sobre hardware

### Que placa foi usada?

Uma RoboCore BlackBoard Wisdom com ESP32. Ela se comunica com o notebook por
USB/serial e roda o firmware do projeto.

### O que roda na placa e o que roda no computador?

A placa roda os comandos de firmware: `MISSION`, `PQC_KAT`, `PQC_BENCH`,
`PQC_FAULT`, sensores, LED, OLED e outros comandos de bancada. O computador
roda o dashboard em Pygame, envia comandos e exibe as métricas recebidas.

### O dashboard calcula ML-KEM localmente?

Não. Para a apresentação, as métricas de mensagem vêm da placa conectada. O
dashboard envia `MISSION CLASSIC`, `MISSION PQC` ou `MISSION PQC_CRC32` e
exibe a resposta do firmware.

### Por que o dashboard não mostra replay se a placa estiver desconectada?

Porque a apresentação precisa demonstrar hardware real. Se a placa não estiver
conectada, `ENVIAR MSG` retorna `SAT OFF` e não inventa métrica.

### O que acontece se a placa falhar na hora?

A demonstração de mensagem deve ser pausada até aparecer `SAT CONECTADO`. Os
resultados consolidados continuam documentados no JSON oficial, mas a regra da
apresentação é não usar replay para envio ao vivo.

### Que métricas de hardware aparecem na tela?

Na faixa superior aparecem CPU e RAM. CPU mostra frequência e porcentagem
ativa em uma janela móvel. RAM mostra consumo/total e memória livre. No popup
de mensagem aparecem tempo, bytes, heap, fases ML-KEM/HMAC/CRC e validações.

### Por que não aparece disco como métrica central?

Porque o experimento principal acontece na placa e no fluxo serial. Disco do
notebook não é gargalo relevante para a conclusão sobre PQC em hardware
embarcado. O dashboard foca CPU/RAM da simulação e métricas retornadas pela
placa.

### Como a energia foi medida?

Energia real não foi medida. O projeto usa tempo de CPU e perfil de frequência
como proxy operacional. Para watts ou joules, seria necessário medidor externo.

### Por que energia real ficou como limitação?

Porque medir energia corretamente exige instrumento físico e controle de
carga, tensão e corrente. Sem isso, seria incorreto afirmar consumo elétrico
real.

### O que é `OBC-1U-LIMITED`?

É um perfil didático limitado: CPU a 80 MHz e restrições operacionais para
simular um ambiente mais apertado. Ele não é uma especificação universal de
CubeSat.

### Por que comparar 240 MHz e 80 MHz?

Para mostrar que reduzir CPU afeta diretamente o custo temporal de ML-KEM.
No benchmark, keygen/encap/decap ficaram cerca de 3 vezes mais lentos no perfil
de 80 MHz.

### A RAM foi problema?

Nos testes consolidados, não. A heap livre ficou estável: 201.412 bytes nos
cenários de missão e mínimo de 197.624 bytes. A evidência mais forte desta
versão é tempo e tráfego, não exaustão de RAM.

## 6. Perguntas sobre resultados e métricas

### Quais foram os resultados principais?

No perfil baseline de 240 MHz:

- `CLASSIC`: 511 us, 73 bytes;
- `PQC`: 13.234 us, 841 bytes;
- `PQC_CRC32`: 13.130 us, 845 bytes.

Isso dá aproximadamente 25,9x mais tempo e 11,5x mais bytes para PQC em
comparação com `CLASSIC`.

### Quantas vezes os testes rodaram?

A bateria final teve 3.074 registros, 0 falhas, 1.800 execuções `MISSION`,
1.200 testes `FAULT` e 10 execuções `PQC_BENCH` com 100 rounds cada. Nos
resultados `MISSION`, foram 300 amostras por cenário em cada perfil.

### Por que `PQC_CRC32` aparece um pouco mais rápido que `PQC` no tempo total?

Porque os tempos totais têm variação natural de execução. O CRC32 aparece no
subtempo específico como ~10 us e adiciona +4 bytes. A diferença pequena entre
13.234 us e 13.130 us no total não deve ser vendida como "CRC deixa mais
rápido"; é ruído/variação experimental.

### Então qual é a conclusão correta sobre CRC32?

CRC32 adicionou custo pequeno no payload: cerca de 10 us a 240 MHz e 4 bytes.
O valor didático dele está em transformar falha silenciosa em falha detectada,
não em alterar significativamente o custo total do ML-KEM.

### Por que PQC aumentou tanto os bytes?

Porque o fluxo PQC inclui material do ML-KEM. Na consolidação de mensagem, o
pacote contabiliza payload, ciphertext ML-KEM de 768 bytes e tag HMAC de 32
bytes. Por isso `PQC` chega a 841 bytes contra 73 bytes do clássico.

### A chave pública ML-KEM entra nesses 841 bytes?

Não nessa métrica consolidada de mensagem. A chave pública ML-KEM tem 800
bytes, mas o `bytes_total` da entrega consolidada contabiliza payload,
ciphertext, tag e checksum. Isso deve ser dito se alguém perguntar.

### O que significa `heap=201.412`?

É a memória heap livre reportada pela placa no cenário. Em todos os cenários
principais ela ficou igual, então não houve evidência de pressão de memória
nessa bateria.

### Por que medir `min_heap`?

Porque a heap livre instantânea pode parecer boa, mas o mínimo observado indica
se houve algum pico de uso maior durante a execução.

### O que significa `key_match=1`?

Significa que, no fluxo ML-KEM, as duas pontas chegaram ao mesmo segredo.
No cenário clássico ele fica verdadeiro por convenção do fluxo, já que não há
ML-KEM real ali.

### O que significa `tag_match=1`?

Significa que a tag HMAC calculada na verificação bateu com a tag esperada.

### O que significa `crc_match=1`?

Significa que o CRC32 recebido bateu com o CRC32 calculado no payload. Esse
campo é relevante no cenário `PQC_CRC32`.

### O que é `elapsed_us`?

É o tempo total medido em microssegundos para completar o fluxo de entrega da
mensagem no firmware.

### Por que usar microssegundos?

Porque as operações são rápidas o bastante para milissegundos esconderem parte
da diferença. Microssegundos deixam os custos das fases visíveis.

### As métricas são científicas?

São métricas reais da placa e dos comandos implementados, mas dentro de um
experimento didático. Elas permitem comparar os três cenários neste hardware e
neste firmware. Não devem ser generalizadas para todos os CubeSats.

### O que significa 0 falhas na bateria?

Significa que a bateria automatizada executou os comandos esperados sem falha
de aceite. Não significa que o sistema seja infalível em ambiente espacial.

### Por que rodar benchmark `PQC_BENCH 100`?

Para reduzir variação ao medir keygen, encap e decap repetidas vezes. Isso
ajuda a mostrar o custo médio das etapas ML-KEM separadas da demo visual.

### Qual etapa ML-KEM foi mais cara?

Nos números consolidados, decap foi a etapa mais cara: cerca de 4.990 us a
240 MHz e 15.217 us a 80 MHz no `PQC_BENCH 100`.

### Por que decap é importante?

Porque é a etapa que o receptor executa para recuperar o segredo. Em um
satélite que recebe comandos ou dados protegidos por KEM, esse custo pode
impactar latência e orçamento de CPU.

## 7. Perguntas sobre comparação justa

### A comparação `CLASSIC` vs `PQC` é totalmente justa?

Não como comparação criptográfica completa. `CLASSIC` é um baseline simétrico
barato; `PQC` inclui acordo de segredo com ML-KEM. A comparação é didática:
ela mostra quanto custa adicionar PQC ao fluxo, não substitui uma análise
formal entre pilhas completas.

### O que seria uma comparação clássica mais justa?

Comparar `PQC` contra uma pilha clássica assimétrica, como ECDH P-256 + HMAC,
usando o mesmo padrão de mensagem, número de rodadas e métricas.

### Por que não implementaram ECDH P-256 agora?

Porque a apresentação precisava focar no objetivo principal: mostrar ML-KEM
real funcionando na placa e comparar custo com um baseline simples. ECDH é
próximo passo natural.

### PQC é sempre mais lento que criptografia clássica?

Não dá para afirmar universalmente. Depende dos algoritmos, plataforma,
implementação e perfil de segurança. O que podemos afirmar é que, neste
experimento, o fluxo `PQC` foi muito mais caro que o baseline `CLASSIC`.

### PQC sempre usa mais bytes?

Em geral, muitos algoritmos PQC têm chaves, ciphertexts ou assinaturas maiores
que alternativas clássicas equivalentes, mas o número exato depende do
algoritmo. No nosso caso, `PQC` foi 841 bytes contra 73 bytes.

### CRC32 é uma comparação justa com HMAC?

Não são mecanismos da mesma categoria. HMAC é autenticação criptográfica.
CRC32 é detecção de erro acidental. No seminário, eles aparecem juntos porque
o objetivo é didático: segurança de protocolo e consistência sob falhas.

## 8. Perguntas sobre implementação

### Qual biblioteca ML-KEM foi usada?

O firmware usa `mlkem-native` v1.1.0, com parâmetro ML-KEM-512 em build C-only.

### Por que usar biblioteca pronta em vez de implementar ML-KEM do zero?

Porque criptografia deve usar implementações revisadas e testadas sempre que
possível. Implementar ML-KEM do zero aumentaria risco de bug e desviaria o
foco do seminário.

### Como vocês validaram que ML-KEM está funcionando?

Com `PQC_KAT`, que executa um vetor determinístico e retorna `kat=pass`; com
`PQC_BENCH`, que roda várias rodadas; e com `MISSION PQC`, que exige
`key_match=1` e `tag_match=1`.

### O que é KAT?

KAT significa Known Answer Test, ou teste de resposta conhecida. Ele verifica
se uma implementação gera o resultado esperado para um caso determinístico.

### Vocês exportam chaves ou segredos no JSON?

Não. O projeto exporta métricas, tamanhos, tempos, estados e CRCs/digests
curtos. Segredos completos não são exportados.

### Por que não exportar segredos completos?

Porque não é necessário para análise e seria uma má prática de segurança. O
objetivo é medir custo e validar comportamento, não registrar material secreto.

### O firmware usa chaves didáticas?

O baseline clássico usa uma chave simétrica didática para autenticação. Isso é
aceitável para o experimento, mas não deve ser apresentado como política de
chaves de um sistema real.

### A implementação é resistente a side-channel?

Não foi avaliada contra side-channel. Essa é uma limitação. O projeto mede
funcionalidade, tempo, bytes e comportamento sob bit-flip controlado.

### O dashboard e a placa usam qual protocolo?

Usam protocolo serial por linha, no formato `V1|request_id|COMMAND|arg...` e
respostas `V1|request_id|RESULT|status|key=value`.

### Por que o dashboard tem terminal e botões?

Os botões são só para a demonstração visual principal. O terminal permite
comandos avançados, como `HELP`, `PQC_KAT`, `PQC_FAULT` e comandos de bancada,
sem poluir a interface da apresentação.

### Por que remover comandos visuais extras?

Para manter a apresentação focada. Sensores, RGB, relay, servo e comandos de
debug existem, mas não ajudam a provar a tese principal sobre PQC, checksum e
hardware limitado.

### Por que os popups são arrastáveis?

Para abrir um resultado `CLASSIC`, um `PQC` e um `PQC+CRC` ao mesmo tempo e
comparar visualmente tempo, bytes, heap e fases internas lado a lado.

## 9. Perguntas sobre a demonstração ao vivo

### Qual é a sequência ideal da demo?

1. Mostrar `SAT CONECTADO`.
2. Enviar `CLÁSSICA` -> `ENVIAR MSG`.
3. Enviar `PQC` -> `ENVIAR MSG`.
4. Enviar `PQC+CRC` -> `ENVIAR MSG`.
5. Arrastar os três popups lado a lado e comparar.
6. Clicar `PQC` -> `FALHA` para mostrar falha silenciosa.
7. Clicar `PQC+CRC` -> `FALHA` para mostrar detecção.
8. Abrir `RESULTADOS` para fechar com os dados consolidados.

### O que explicar quando abrir os três popups?

Explique que `CLASSIC` só tem HMAC, por isso keygen/encap/decap ficam zerados.
Em `PQC`, aparecem keygen, encap e decap. Em `PQC+CRC`, aparece também custo
de CRC e +4 bytes.

### O que falar se perguntarem por que o satélite some quando a placa não está conectada?

É uma decisão de honestidade visual. A demo final só deve mostrar a arte do
satélite funcional quando o hardware real respondeu ao handshake.

### O que fazer se a tela mostrar `SAT OFF`?

Explicar que o dashboard recusou inventar métricas. Em seguida, verificar a
porta serial, cabo, permissão e reiniciar a conexão.

### Qual comando abre o dashboard com hardware?

```bash
python3 dashboard.py --port /dev/ttyUSB0
```

### Qual comando abre só para ensaio visual?

```bash
python3 dashboard.py --simulated
```

Mas esse modo não deve ser usado para gerar métricas de mensagem na
apresentação final.

### Por que não rodar bateria longa durante a apresentação?

Porque ela demora e polui a dinâmica. As coletas longas já foram feitas antes,
e os resultados consolidados ficam no botão `RESULTADOS` e nos arquivos JSON.

### Onde estão os resultados oficiais?

No arquivo:

```text
logs/20260625T005330Z_final_metrics_dev-ttyusb0.json
```

E resumidos em `METRICAS_CONSOLIDADAS.md`.

## 10. Perguntas difíceis e respostas seguras

### Isso é realmente pós-quântico se a mensagem não é cifrada?

Sim no componente de acordo de segredo: o projeto executa ML-KEM-512 real. Mas
é importante dizer que a demonstração não implementa uma pilha completa de
canal seguro com cifra autenticada. Ela mede o custo de inserir ML-KEM no
fluxo de mensagem.

### Vocês estão misturando autenticação, checksum e KEM?

Sim, de forma controlada e didática. O roteiro separa os papéis: ML-KEM
estabelece segredo, HMAC autentica mensagem e CRC32 detecta corrupção
acidental do payload. Eles não são equivalentes.

### CRC32 não é inseguro?

Contra atacante, sim, CRC32 é inadequado. Contra erro acidental de bit, ele é
útil. No seminário, ele não é apresentado como proteção criptográfica.

### Então por que chamar PQC+CRC de mais seguro?

Melhor dizer "mais robusto contra corrupção acidental de payload", não "mais
seguro contra atacante". A segurança criptográfica continua vindo do protocolo
criptográfico; o CRC32 ajuda na consistência operacional.

### Por que `CLASSIC` usa HMAC e `PQC` também usa HMAC?

Porque queremos que a mensagem seja autenticada nos dois casos. A diferença é
que, em `PQC`, o segredo usado para autenticação vem de uma sessão ML-KEM; no
baseline clássico, vem de uma chave simétrica didática.

### Se HMAC detecta alteração, para que CRC?

Na prática, HMAC poderia detectar alteração maliciosa ou acidental na mensagem
autenticada. O CRC entra como recurso didático para isolar e visualizar falhas
de payload por bit-flip. Ele também representa mecanismos leves de integridade
usados em camadas de transporte/armazenamento.

### O projeto mede consumo de energia?

Não mede energia elétrica real. Mede tempo e perfil de CPU como proxies. A
resposta correta é: energia real fica como trabalho futuro com instrumento
externo.

### O projeto prova resistência à radiação?

Não. Ele simula efeitos de bit-flip. Resistência à radiação exigiria teste em
ambiente e equipamento específicos.

### O projeto prova segurança formal de ML-KEM?

Não. A segurança formal vem da especificação e análise do algoritmo. O projeto
prova integração funcional e mede custo em uma placa específica.

### O que garante que os números não são inventados?

As métricas vêm de comandos reais da placa e foram exportadas em JSON. A
bateria final registrou 3.074 entradas, 0 falhas, 1.800 `MISSION runs`, 1.200
testes `FAULT` e 10 `PQC_BENCH` de 100 rodadas.

### Por que confiar nos resultados se só há uma placa?

Para uma demonstração didática, uma placa é suficiente para observar o efeito.
Para generalização científica, seria necessário repetir em mais placas,
compiladores, perfis e cargas.

### O que vocês fariam diferente em uma versão de pesquisa?

Adicionaríamos ECDH P-256 como baseline clássico assimétrico, AES-GCM para
confidencialidade, medição de energia real, mais payloads, bursts de bit-flip,
mais placas e análise estatística mais ampla.

### A heap constante invalida a tese de hardware limitado?

Não. Hardware limitado não é só RAM. Tempo de CPU, tráfego, energia e latência
também importam. Nesta versão, a evidência mais forte ficou em tempo e bytes.

### O que acontece se o payload for maior?

O custo fixo do ML-KEM continuaria existindo, mas HMAC, CRC e eventual cifra
simétrica cresceriam com o tamanho da mensagem. Payloads maiores são trabalho
futuro.

### Por que o total de `PQC_CRC32` não cresceu muito?

Porque CRC32 é barato comparado ao ML-KEM. O custo adicional aparece como +4
bytes e ~10 us, mas fica pequeno perto dos ~13 ms do fluxo PQC.

### Isso escala para comunicação real de satélite?

O conceito escala, mas o protótipo não é uma pilha de comunicação espacial
completa. Para missão real seria necessário protocolo, tolerância a falhas,
sincronização, gestão de chaves, medição de energia, certificação e validação
ambiental.

## 11. Perguntas sobre números específicos

### Qual foi o custo de `CLASSIC`?

511 us em média, 73 bytes, heap livre 201.412 bytes, resultado `DELIVERED`.

### Qual foi o custo de `PQC`?

13.234 us em média, 841 bytes, heap livre 201.412 bytes, resultado
`DELIVERED`.

### Qual foi o custo de `PQC_CRC32`?

13.130 us em média, 845 bytes, heap livre 201.412 bytes, resultado
`DELIVERED`.

### Qual foi o overhead de bytes do CRC32?

+4 bytes sobre o cenário PQC.

### Qual foi o overhead temporal do CRC32?

No subtempo específico, cerca de 10 us a 240 MHz e 30 us a 80 MHz.

### Quanto PQC foi mais lento que CLASSIC?

25,9x mais lento no perfil baseline de 240 MHz e 34,1x mais lento no perfil
limitado de 80 MHz.

### Quanto PQC foi maior em bytes?

11,5x maior que o baseline clássico: 841 bytes contra 73 bytes.

### Qual foi o resultado do `PQC_KAT`?

`kat=pass`, com `ss_crc32=0xD9DA8D6C`.

### Qual foi o resultado do `PQC_FAULT 0 0x01 CONFIRM`?

`PROTOCOL_REJECT`, com `key_match=0` e confirmação `HMAC-SHA256`.

### Qual foi o resultado do `PQC_FAULT 0 0x01 NONE`?

`KEY_MISMATCH`, com `key_match=0`.

### Qual etapa foi mais cara no benchmark ML-KEM?

Decapsulação. No `BASELINE`, `decap_avg_us` ficou em 4.985 us. No
`OBC-1U-LIMITED`, ficou em 15.204 us.

## 12. Perguntas sobre termos da tela

### O que significa `SAT CONECTADO`?

Que o dashboard recebeu handshake da placa e pode enviar comandos reais.

### O que significa `SAT OFF`?

Que o comando de mensagem foi recusado porque não há placa conectada ou
confirmada.

### O que significa `GUARD: NONE`?

Que o fluxo de bit-flip manual está sem guardião CRC32.

### O que significa `GUARD: CRC32`?

Que o fluxo de bit-flip manual usa CRC32 para detectar alteração de payload.

### O que significa `SILENT`?

Que a corrupção aconteceu e não foi detectada pelo guardião ativo.

### O que significa `DETECTED_GUARD`?

Que o guardião, como CRC32, detectou a alteração.

### O que significa `DELIVERED`?

Que o fluxo de mensagem foi aceito pelo firmware.

### O que significa `REJECTED`?

Que alguma validação falhou e a entrega não deve ser aceita.

### O que significa `CPU 240 MHz 1%`?

Que o painel está mostrando a frequência ativa e uma estimativa de atividade
observada na janela móvel da simulação/dashboard.

### O que significa `RAM 123 KB / 320 KB`?

É a visualização didática de uso de RAM disponível no painel, baseada nas
métricas coletadas e no estado do sistema.

## 13. Perguntas sobre próximos passos

### Qual é o próximo passo mais importante?

Medir energia real com instrumento externo. Tempo de CPU indica custo, mas não
substitui watts ou joules.

### O que vocês adicionariam para ficar mais completo?

ECDH P-256 + HMAC como baseline clássico assimétrico, AES-GCM para
confidencialidade, payloads maiores, múltiplas placas, bursts de bit-flip,
medição elétrica e testes de side-channel.

### Como transformar isso em artigo ou relatório mais forte?

Definir metodologia estatística mais rigorosa, aumentar amostras, separar
fontes de variação, comparar bibliotecas, medir energia e repetir em outras
plataformas embarcadas.

### O que fica fora do escopo atual?

Radiação física, certificação espacial, medição de energia real, canal seguro
completo, proteção contra side-channel, gestão real de chaves e testes com
múltiplos dispositivos.

## 14. Respostas curtas para usar sob pressão

**"Isso é um CubeSat real?"**  
Não. É um protótipo educacional inspirado no problema de OBC limitado em
CubeSats.

**"CRC32 é seguro?"**  
Não contra atacante. Ele é usado aqui para detectar corrupção acidental de
payload por bit-flip.

**"ML-KEM cifra a mensagem?"**  
Não. ML-KEM estabelece segredo; depois esse segredo pode alimentar HMAC ou
cifra simétrica.

**"PQC foi inviável?"**  
Não. Foi funcional, mas custou muito mais tempo e bytes.

**"Qual número mais importante?"**  
PQC foi 25,9x mais lento e 11,5x maior em bytes que `CLASSIC` a 240 MHz.

**"A energia foi medida?"**  
Não. Usamos tempo de CPU como proxy; energia real exige medidor externo.

**"Por que o CRC quase não muda o total?"**  
Porque CRC32 é barato perto do ML-KEM. Ele soma +4 bytes e ~10 us, mas o custo
dominante é keygen/encap/decap.

**"Por que não comparar com ECDH?"**  
Porque o escopo do seminário era ML-KEM real na placa. ECDH é próximo passo
para uma comparação clássica assimétrica mais justa.

**"O que vocês provaram?"**  
Provamos integração funcional e custo relativo no hardware usado; não uma
garantia universal para todos os CubeSats.

**"O que a demo ao vivo mostra?"**  
Mostra a mesma mensagem em três cenários, os custos de cada um e a diferença
entre falha silenciosa e falha detectada.

## 15. Perguntas que você pode fazer para a turma

Estas perguntas ajudam a tornar o seminário interativo. Use-as antes de
revelar o resultado no dashboard.

| Momento | Pergunta | Resposta que você quer conduzir |
|---|---|---|
| Antes do primeiro envio | O que vai crescer mais quando sairmos de `CLASSIC` para `PQC`: CPU, bytes ou RAM? | Tempo e bytes cresceram muito; heap ficou estável na coleta. |
| Depois de `PQC` | Por que uma mensagem pequena virou um pacote muito maior? | O pacote passou a carregar ciphertext ML-KEM de 768 bytes mais tag HMAC. |
| Antes de `PQC+CRC` | CRC32 é criptografia ou detecção de erro? | Detecção de erro acidental; não autenticação contra atacante. |
| Ao mostrar o comparador | Qual pedaço domina os bytes em `PQC`: payload, HMAC, ML-KEM ou CRC? | ML-KEM domina por causa do ciphertext. |
| Antes de `FALHA` | Se um bit mudar e ninguém conferir, o sistema percebe? | Não necessariamente; pode virar falha silenciosa. |
| Depois de `PQC+CRC -> FALHA` | O que mudou entre falha silenciosa e falha detectada? | O guardião CRC32 tornou a corrupção observável. |
| Antes de `RESULTADOS` | O que vocês esperam que tenha ficado estável na bateria longa? | A RAM/heap ficou estável; tempo e bytes foram o impacto forte. |
| Fechamento | PQC foi inviável ou apenas caro? | Foi viável na Wisdom, mas caro em tempo e tráfego. |

Perguntas extras se houver tempo:

1. Se uma mensagem clássica leva menos de 1 ms e a versão PQC leva cerca de
   13 ms, em que tipo de missão isso importa?
2. Que baseline seria mais justo que HMAC puro para comparar com ML-KEM?
3. O que deveria acontecer quando `key_match=0`: aceitar, tentar de novo ou
   rejeitar a sessão?
4. Vale mais a pena gastar bytes com PQC agora ou correr o risco de dados
   capturados hoje serem quebrados no futuro?

## 16. Fechamento recomendado

> A conclusão não é que PQC é impossível em hardware limitado. A conclusão é
> que PQC funciona, mas muda o orçamento do sistema. Em um ambiente inspirado
> em CubeSat, onde CPU, RAM, tráfego e energia precisam ser justificados, essa
> diferença deixa de ser detalhe de implementação e vira decisão de projeto.
