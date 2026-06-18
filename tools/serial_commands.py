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


DASHBOARD_COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo("INJECT_FAULT", "aplica bit-flip determinístico com o guardião ativo"),
    CommandInfo("BIT_FLIP [index mask]", "aplica bit-flip determinístico ou manual com o guardião ativo"),
    CommandInfo("CHECKSUM ON|OFF|TOGGLE|STATUS", "liga/desliga o guardião CRC32 do fluxo manual"),
    CommandInfo("GUARD NONE|CRC32", "define explicitamente o guardião ativo"),
    CommandInfo("PQC_STATUS", "consulta PQC_INFO na placa ou mostra pendência local"),
    CommandInfo("CRC_CHECK", "aplica bit-flip e verifica CRC32 real"),
    CommandInfo("EXPORT_JSON", "salva eventos e métricas em JSON"),
    CommandInfo("SAVE_SESSION", "alias de EXPORT_JSON"),
    CommandInfo("RUN_BATTERY n", "executa bateria A/B e exporta JSON"),
    CommandInfo("DEMO [n]", "executa campanha A/B visual cronometrada"),
    CommandInfo("DEMO_PAUSE|DEMO_RESUME", "pausa ou retoma a campanha visual"),
    CommandInfo("DEMO_STOP|DEMO_RESTART", "para ou reinicia a campanha visual"),
    CommandInfo("RESET_SESSION", "salva dados pendentes, zera sessão e reinicia a seed"),
    CommandInfo("HELP", "mostra ajuda avançada do terminal textual"),
)


DEMO_FIRMWARE_COMMANDS: tuple[CommandInfo, ...] = (
    CommandInfo("PING", "confirma que a placa respondeu ao painel"),
    CommandInfo("STATUS", "mostra perfil, CPU, memória e rádio"),
    CommandInfo("TELEMETRY", "atualiza telemetria real da Wisdom"),
    CommandInfo("SENSOR_READ TEMP_HUM", "lê temperatura e umidade"),
    CommandInfo("SENSOR_READ ACCEL", "lê aceleração para demonstrar movimento"),
    CommandInfo("SENSOR_READ APDS", "lê luz/proximidade do APDS-9960"),
    CommandInfo("OLED STANDBY", "restaura o ícone robô-satélite no display"),
    CommandInfo("LED TEST", "executa teste visual do indicador principal"),
    CommandInfo("LED WHITE|RED|GREEN|BLUE|OFF", "muda a cor do indicador principal"),
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
    if name == "SENSOR_READ":
        return len(parts) == 2 and parts[1] in {"TEMP_HUM", "ACCEL", "APDS"}
    if name == "OLED":
        return len(parts) == 2 and parts[1] == "STANDBY"
    if name == "LED":
        return len(parts) == 2 and parts[1] in {"TEST", "WHITE", "RED", "GREEN", "BLUE", "OFF"}
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


def command_help_lines(*, include_dashboard: bool = False, demo_only: bool = True) -> list[str]:
    """Return compact human-readable help lines for terminal or dashboard use."""

    lines: list[str] = []
    if include_dashboard:
        lines.append("Comandos locais do dashboard:")
        lines.extend(f"  {info.usage:<38} {info.description}" for info in DASHBOARD_COMMANDS)
        lines.append("")

    if demo_only:
        lines.append("Comandos de demonstração ao vivo:")
        lines.extend(f"  {info.usage:<38} {info.description}" for info in DEMO_FIRMWARE_COMMANDS)
        lines.append("")
        lines.append("Comandos completos de bancada: hardware_command_reference.md")
    else:
        lines.append("Comandos completos do firmware ESP32:")
        lines.extend(f"  {info.usage:<38} {info.description}" for info in FIRMWARE_COMMANDS)
    return lines
