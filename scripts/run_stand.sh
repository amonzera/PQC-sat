#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PQC_SAT_PYTHON:-python3}"
RESTART_ON_CRASH=0
ARGS=()

show_help() {
  cat <<'EOF'
Uso: ./scripts/run_stand.sh [opções do dashboard] [--restart-on-crash]

Exemplos:
  ./scripts/run_stand.sh --port /dev/ttyUSB0 --restart-on-crash
  ./scripts/run_stand.sh --simulated
  ./scripts/run_stand.sh --port /dev/ttyUSB0 --windowed

O inicializador valida dependências e a Wisdom antes de abrir a apresentação
integrada. As demais opções são encaminhadas para `dashboard.py --presentation`.
EOF
}

for arg in "$@"; do
  if [[ "${arg}" == "--help" || "${arg}" == "-h" ]]; then
    show_help
    exit 0
  elif [[ "${arg}" == "--restart-on-crash" ]]; then
    RESTART_ON_CRASH=1
  else
    ARGS+=("${arg}")
  fi
done

cd "${PROJECT_DIR}" || exit 2

if ! "${PYTHON_BIN}" -c "import pygame" >/dev/null 2>&1; then
  echo "ERRO: pygame-ce indisponível. Instale requirements.txt antes do evento." >&2
  exit 2
fi

SIMULATED=0
DIAGNOSTIC_PORT=()
for ((index = 0; index < ${#ARGS[@]}; index++)); do
  arg="${ARGS[index]}"
  if [[ "${arg}" == "--simulated" ]]; then
    SIMULATED=1
  elif [[ "${arg}" == "--port" && $((index + 1)) -lt ${#ARGS[@]} ]]; then
    DIAGNOSTIC_PORT=(--port "${ARGS[index + 1]}")
  elif [[ "${arg}" == --port=* ]]; then
    DIAGNOSTIC_PORT=(--port "${arg#--port=}")
  fi
done

if [[ ${SIMULATED} -eq 0 ]]; then
  if ! "${PYTHON_BIN}" -c "import serial" >/dev/null 2>&1; then
    echo "ERRO: pyserial indisponível. Instale requirements-hardware.txt." >&2
    exit 2
  fi
  if ! "${PYTHON_BIN}" tools/stand_diagnostics.py --check-only "${DIAGNOSTIC_PORT[@]}"; then
    echo "ERRO: Wisdom não localizada. Use --port ou escolha conscientemente --simulated." >&2
    exit 2
  fi
fi

mkdir -p logs/stand

run_interface() {
  if command -v systemd-inhibit >/dev/null 2>&1 && systemd-inhibit --list >/dev/null 2>&1; then
    systemd-inhibit \
      --what=idle:sleep \
      --who="PQC-SAT SBPC" \
      --why="demonstração contínua no estande" \
      --mode=block \
      "${PYTHON_BIN}" dashboard.py --presentation --no-splash "${ARGS[@]}"
  else
    echo "AVISO: bloqueio de suspensão indisponível; desative a suspensão manualmente." >&2
    "${PYTHON_BIN}" dashboard.py --presentation --no-splash "${ARGS[@]}"
  fi
}

while true; do
  run_interface
  STATUS=$?
  if [[ ${STATUS} -eq 0 || ${RESTART_ON_CRASH} -eq 0 ]]; then
    exit "${STATUS}"
  fi
  echo "Interface encerrou com status ${STATUS}; reiniciando em 2 s." >&2
  sleep 2
done
