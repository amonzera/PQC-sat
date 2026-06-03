# PQC-SAT Mission Control Dashboard 🛰️🔒

Este repositório contém a demonstração didática e o painel de controle de missão do **PQC-SAT**, um projeto desenvolvido para a disciplina de **Cibersegurança** do curso de Ciência da Computação na **Universidade Federal Fluminense (UFF)**.

O objetivo do projeto é analisar a viabilidade e a resiliência de algoritmos de **Criptografia Pós-Quântica (PQC)**, especificamente o **ML-KEM-768** (antigo Kyber, padronizado pelo NIST em 2024), quando executados em computadores de bordo baseados em hardware COTS (como o **ESP32** em CubeSats) sujeitos a falhas transitórias (como *bit-flips* causados por radiação cósmica).

---

## 📌 Contexto e Objetivos

O projeto propõe um mini-experimento didático para ilustrar:
1. **Falhas Transitórias em Ambiente Espacial**: Como a radiação do espaço pode alterar bytes na memória de trabalho ou nas mensagens de comunicação de um CubeSat em órbita baixa.
2. **Impacto na Criptografia**: O efeito dessas corrupções em chaves e sessões criptográficas estabelecidas por algoritmos pós-quânticos.
3. **Mecanismos de Integridade**: A comparação prática entre a transmissão de mensagens sem proteção (gerando altas taxas de **Falhas Silenciosas** / *Silent Failures*) e a transmissão com um guardião leve de integridade (como CRC-16, CRC-32 ou XOR checksum, transformando falhas silenciosas em **Erros Detectados**).

O painel visual simula a estação de controle terrestre (Mission Control) monitorando o satélite **PQC-SAT-01** e aplicando campanhas de injeção de falhas.

---

## 🎮 Funcionalidades do Dashboard (`dashboard.py`)

O painel de controle foi construído usando a biblioteca **Pygame** e apresenta:
* **Visualização Espacial Animada**: Um CubeSat orbitando a Terra em 2D, com partículas de poeira cósmica, estrelas cadentes, nebulosa dinâmica de fundo e um simpático robô em pixel art animado dentro do satélite.
* **Painel de Telemetria**: Informações em tempo real sobre:
  * Status da sessão criptográfica.
  * Algoritmo PQC ativo (`ML-KEM-768`).
  * Coordenadas orbitais do satélite (X, Y) e ângulo de órbita.
  * Métricas de integridade e falhas (injetadas, detectadas e silenciosas).
  * Uptime do sistema e velocidade orbital.
* **Console de Comandos Interativo**: Um terminal integrado que aceita comandos em tempo real para controle da missão e injeção de falhas.

---

## 🚀 Como Executar

### Pré-requisitos
Certifique-se de ter o Python 3 instalado em sua máquina. Para instalar a única dependência necessária (Pygame), execute:

```bash
pip install pygame
```

### Executando a Aplicação
Com o terminal no diretório raiz do projeto, execute o script do painel:

```bash
python3 dashboard.py
```

*Para fechar a janela em modo de tela cheia, use a combinação de teclas `Ctrl + Q` ou clique no botão fechar se executado em modo janela.*

---

## ⌨️ Comandos do Console do Dashboard

Na parte inferior direita do painel, você pode clicar na caixa de entrada do console e testar os seguintes comandos interactivos (pressione `Enter` para enviar):

| Comando | Ação | Status Retornado |
|:---|:---|:---|
| `INJECT_FAULT` | Injeta uma falha transitória na sessão criptográfica ativa. | `FAULT INJECTED` (com chance de gerar `SILENT FAILURE!` ou `ERROR DETECTED`) |
| `BIT_FLIP` | Simula a inversão de bits em um frame de dados. | `BIT-FLIP SIMULATED` / `CORRUPTION SILENCIOSA` |
| `PQC_STATUS` | Solicita o estado da negociação de chave pós-quântica. | `PQC NOMINAL` |
| `RESET_SESSION` | Reinicia a sessão de criptografia e limpa o estado de falhas. | `SESSION RESET` |
| `PING` | Mede o tempo de resposta da comunicação com o CubeSat. | `PONG — 12ms` |
| `CRC_CHECK` | Realiza uma varredura de integridade na memória. | `CRC OK` |
| `TELEMETRY` | Inicia o streaming contínuo de dados. | `STREAMING` |
| `HELP` | Exibe uma ajuda rápida dos comandos no terminal. | `CMD LIST SHOWN` |

---

## 📁 Estrutura do Repositório

* `dashboard.py`: Código-fonte principal em Python (Pygame) contendo toda a renderização 2D e lógica do console e da órbita.
* `projeto_final_pqc_esp32_cubesat.docx`: Documento formal da proposta do projeto científico (v4.1 Final) detalhando a metodologia, as etapas do mini-experimento de cibersegurança e o cronograma de atividades.
* `README.md`: Este arquivo explicativo.

---

## 📚 Referências Bibliográficas (Destaques)

* **SILVA, A. et al.** *Efficient Implementation of CRYSTALS-KYBER Key Encapsulation Mechanism on ESP32.* arXiv:2503.10207, 2025.
* **MENEZES, L. et al.** *Multicore Implementation of ML-KEM on Embedded Devices.* In: SBSeg, 2024.
* **NIST.** *FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism Standard.* NIST, agosto 2024.
* **RAVI, P. et al.** *Side-channel and Fault-injection attacks over Lattice-based Post-quantum Schemes.* ACM TECS, 2023.
