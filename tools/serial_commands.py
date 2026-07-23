"""Command catalog for the PQC-SAT ESP32 serial interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandInfo:
    usage: str
    description: str

    @property
    def name(self) -> str:
        return self.usage.split()[0]


FIRMWARE_COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo("HELLO", "identifica placa, protocolo e transporte"),
    CommandInfo("PING", "testa ida e volta UART e retorna uptime"),
    CommandInfo("STATUS", "mostra CPU, heap, flash, perfil e rádio"),
    CommandInfo("TELEMETRY", "lê uptime, heap, potenciômetro, som, botão e relé"),
    CommandInfo("FAULT NONE|CRC32 payload_hex index mask", "aplica bit-flip em payload e compara CRC32"),
    CommandInfo("PQC_INFO", "reporta backend ML-KEM-512, tamanhos e métricas"),
    CommandInfo("PQC_KAT", "executa vetor conhecido determinístico e retorna digest curto"),
    CommandInfo("PQC_KEYGEN", "gera par ML-KEM-512 e mede tempo/heap"),
    CommandInfo("PQC_ENCAP", "encapsula usando chave pública armazenada"),
    CommandInfo("PQC_DECAP", "decapsula ciphertext armazenado e compara segredo"),
    CommandInfo("PQC_FAULT index mask [CONFIRM|NONE]", "aplica bit-flip em ciphertext ML-KEM e testa confirmação"),
    CommandInfo("PQC_BENCH n", "executa n rodadas keygen/encap/decap, 1..100"),
    CommandInfo("KEX_INFO", "reporta o contrato FAIR_V1, backend comum e tamanhos públicos"),
    CommandInfo("KEX_BENCH n", "compara ECDH P-256 e ML-KEM-512 em pares alternados, 1..100"),
    CommandInfo(
        "SESSION_BENCH ECDH|MLKEM 1|100|500|1000 payload_hex",
        "mede uma sessão FAIR e o custo amortizado de várias mensagens AES-GCM",
    ),
    CommandInfo("STRESS PQC_LOOP n CONFIRM", "executa ML-KEM em loop extremo, 1..500, com confirmação explícita"),
    CommandInfo(
        "MISSION ECDH|ECDH_CRC32|MLKEM|MLKEM_CRC32|CLASSIC|CLASSIC_CRC32|PQC|PQC_CRC32 [payload_hex]",
        "mede a sessão FAIR_V1 ou preserva os cenários legados explicitamente rotulados",
    ),
    CommandInfo(
        "INVESTIGATE scenario incident payload_hex index mask incident_id",
        "executa incidente em camadas e reporta CRC de quadro, GCM e CRC da aplicação",
    ),
    CommandInfo(
        "GAME_BEGIN id profile ECDH|MLKEM|CLASSIC|PQC NONE|CRC32 incident payload_hex",
        "inicia sessão STAGED_V1; a superfície pública usa apenas ECDH ou MLKEM",
    ),
    CommandInfo("GAME_PROTECT id", "estabelece a chave e monta o envelope AES-GCM"),
    CommandInfo("GAME_TRANSMIT id byte_index bit_mask", "aplica o incidente oculto no vetor escolhido"),
    CommandInfo("GAME_VERIFY id", "verifica CRC de quadro, tag GCM e CRC da aplicação"),
    CommandInfo("GAME_RETRY id", "retransmite o mesmo payload com chave e nonce novos"),
    CommandInfo("GAME_END id ACCEPT|SAFE_MODE", "encerra a sessão e restaura o baseline"),
    CommandInfo("GAME_ABORT id", "aborta e apaga a sessão ativa"),
    CommandInfo("PERIPHERALS", "detecta OLED, APDS-9960, HTU21D e MMA8452 no I2C"),
    CommandInfo("I2C_SCAN", "varre o barramento I2C SDA21/SCL22"),
    CommandInfo("FEATURES [CORE|I2C|GPIO|ANALOG|EXPANSION]", "lista grupos de recursos conhecidos"),
    CommandInfo("BOARDMAP [I2C|GPIO|ANALOG|EXPANSION]", "mostra pinos, barramentos e endereços usados"),
    CommandInfo("SENSOR_READ TEMP_HUM|ACCEL|APDS", "lê HTU21D, MMA8452 ou APDS-9960"),
    CommandInfo("ANALOG [POT|SOUND]", "lê potenciômetro A39 e sensor de som A36"),
    CommandInfo("DIGITAL [BUTTON|IR]", "lê botão, receptor IR e interrupções do acelerômetro"),
    CommandInfo("RGB R G B", "define canais do LED RGB de 0 a 255"),
    CommandInfo("RGB OFF|TEST|COMMON_ANODE|COMMON_CATHODE", "desliga, testa cores ou ajusta polaridade do RGB"),
    CommandInfo("BARGRAPH 0..4", "acende LEDs de porcentagem por nível"),
    CommandInfo("BARGRAPH 0..100|PERCENT n|LEVEL n", "acende LEDs de porcentagem por percentual ou nível"),
    CommandInfo("BARGRAPH TEST|ACTIVE_HIGH|ACTIVE_LOW", "anima o bargraph ou troca a polaridade"),
    CommandInfo("LED ON|OFF|TOGGLE|TEST", "controla o indicador principal com LED interno mais RGB"),
    CommandInfo("LED WHITE|RED|GREEN|BLUE|CYAN|MAGENTA|YELLOW", "define a cor do indicador principal"),
    CommandInfo("RELAY ON|OFF|TOGGLE", "controla a saída de relé D33"),
    CommandInfo("SERVO 0..180|DETACH|OFF", "controla ou solta o PWM do servo em D25"),
    CommandInfo("OLED INIT|CLEAR|TEST|STANDBY", "controla o display e restaura o ícone standby"),
    CommandInfo("PROFILE BASELINE|OBC-1U-LIMITED", "alterna o perfil operacional do ESP32"),
    CommandInfo("RESET_STATS", "zera contadores internos do firmware"),
    CommandInfo("HELP", "lista comandos ou detalha um comando específico"),
)


# The production dashboard has no local command console. Keep the public name
# for import compatibility, but do not advertise controls that no longer exist.
DASHBOARD_COMMANDS: tuple[CommandInfo, ...] = ()


DEMO_FIRMWARE_COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo("PING", "confirma que a placa respondeu ao painel"),
    CommandInfo("STATUS", "mostra perfil, CPU, memória e rádio"),
    CommandInfo("MISSION CLASSIC", "envia mensagem cifrada com AES-128-GCM e chave efêmera"),
    CommandInfo("MISSION CLASSIC_CRC32", "usa chave AES efêmera local, AES-GCM e CRC32 protegido"),
    CommandInfo("MISSION PQC", "usa ML-KEM-512 para chave e AES-128-GCM para cifrar"),
    CommandInfo("MISSION PQC_CRC32", "usa ML-KEM-512, AES-GCM e CRC32 protegido no payload"),
    CommandInfo("MISSION ECDH", "usa ECDH P-256, HKDF-SHA256 e AES-128-GCM no wolfCrypt"),
    CommandInfo("MISSION ECDH_CRC32", "usa o fluxo ECDH FAIR_V1 com CRC32 protegido"),
    CommandInfo("MISSION MLKEM", "usa ML-KEM-512, HKDF-SHA256 e AES-128-GCM no wolfCrypt"),
    CommandInfo("MISSION MLKEM_CRC32", "usa o fluxo ML-KEM FAIR_V1 com CRC32 protegido"),
    CommandInfo("KEX_INFO", "confirma o contrato e a versão do backend FAIR_V1"),
    CommandInfo("KEX_BENCH 10", "executa pares alternados de ECDH e ML-KEM"),
    CommandInfo("TELEMETRY", "atualiza telemetria real da Wisdom"),
    CommandInfo("SENSOR_READ TEMP_HUM", "lê temperatura e umidade"),
    CommandInfo("SENSOR_READ ACCEL", "lê aceleração para demonstrar movimento"),
    CommandInfo("SENSOR_READ APDS", "lê luz/proximidade do APDS-9960"),
    CommandInfo("OLED STANDBY", "restaura o ícone robô-satélite no display"),
    CommandInfo("LED TEST", "executa teste visual do indicador principal"),
    CommandInfo("LED WHITE|RED|GREEN|BLUE|CYAN|MAGENTA|YELLOW|OFF", "muda a cor do indicador principal"),
    CommandInfo("RGB TEST", "executa teste vermelho/verde/azul do RGB"),
    CommandInfo("RGB R G B", "define uma cor RGB para efeito visual"),
    CommandInfo("RGB OFF", "desliga o LED RGB"),
    CommandInfo("BARGRAPH TEST", "anima os LEDs de porcentagem"),
    CommandInfo("BARGRAPH 0|25|50|75|100", "mostra progresso nos LEDs de porcentagem"),
)


FIRMWARE_COMMAND_NAMES = frozenset(command.name for command in FIRMWARE_COMMANDS)
DASHBOARD_COMMAND_NAMES = frozenset(command.name for command in DASHBOARD_COMMANDS)
DEMO_FIRMWARE_COMMAND_NAMES = frozenset(command.name for command in DEMO_FIRMWARE_COMMANDS)


def is_demo_firmware_command(command_line: str) -> bool:
    parts = command_line.strip().upper().split()
    if not parts:
        return False

    name = parts[0]
    if name in {"PING", "STATUS", "TELEMETRY"}:
        return len(parts) == 1
    if name == "MISSION":
        return len(parts) == 2 and parts[1] in {
            "CLASSIC",
            "CLASSIC_CRC32",
            "PQC",
            "PQC_CRC32",
            "ECDH",
            "ECDH_CRC32",
            "MLKEM",
            "MLKEM_CRC32",
        }
    if name == "KEX_INFO":
        return len(parts) == 1
    if name == "KEX_BENCH":
        return len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 100
    if name == "SENSOR_READ":
        return len(parts) == 2 and parts[1] in {"TEMP_HUM", "ACCEL", "APDS"}
    if name == "OLED":
        return len(parts) == 2 and parts[1] == "STANDBY"
    if name == "LED":
        return len(parts) == 2 and parts[1] in {
            "TEST",
            "WHITE",
            "RED",
            "GREEN",
            "BLUE",
            "CYAN",
            "MAGENTA",
            "YELLOW",
            "OFF",
        }
    if name == "RGB":
        if len(parts) == 2:
            return parts[1] in {"TEST", "OFF"}
        if len(parts) == 4:
            return all(_is_u8(part) for part in parts[1:])
        return False
    if name == "BARGRAPH":
        if len(parts) == 2:
            return parts[1] == "TEST" or parts[1] in {"0", "25", "50", "75", "100"}
        return False
    return False


def _is_u8(value: str) -> bool:
    try:
        parsed = int(value, 10)
    except ValueError:
        return False
    return 0 <= parsed <= 255


def _format_help_entry(info: CommandInfo, *, width: int = 38) -> list[str]:
    if len(info.usage) <= width:
        return [f"  {info.usage:<{width}} {info.description}"]
    return [f"  {info.usage}", f"      {info.description}"]


def command_help_lines(*, include_dashboard: bool = False, demo_only: bool = True) -> list[str]:
    """Return compact human-readable help lines for terminal or dashboard use."""

    lines: list[str] = []
    if include_dashboard and DASHBOARD_COMMANDS:
        lines.append("Comandos locais do dashboard:")
        for info in DASHBOARD_COMMANDS:
            lines.extend(_format_help_entry(info))
        lines.append("")

    if demo_only:
        lines.append("Comandos de demonstração ao vivo:")
        for info in DEMO_FIRMWARE_COMMANDS:
            lines.extend(_format_help_entry(info))
        lines.append("")
        lines.append("Comandos completos de bancada: hardware_command_reference.md")
    else:
        lines.append("Comandos completos do firmware ESP32:")
        for info in FIRMWARE_COMMANDS:
            lines.extend(_format_help_entry(info))
    return lines
