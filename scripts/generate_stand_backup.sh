#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PQC_SAT_PYTHON:-python3}"
OUTPUT_DIR="${PROJECT_DIR}/docs/stand/evidence/states"
OUTPUT_VIDEO="${PROJECT_DIR}/docs/stand/evidence/stand_backup_simulated.mp4"

cd "${PROJECT_DIR}"
SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-dummy}" \
SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}" \
  "${PYTHON_BIN}" tools/capture_stand_evidence.py --output-dir "${OUTPUT_DIR}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERRO: ffmpeg não encontrado; screenshots foram preservadas em ${OUTPUT_DIR}." >&2
  exit 2
fi

ffmpeg -hide_banner -loglevel error -y \
  -framerate 1/4 \
  -pattern_type glob \
  -i "${OUTPUT_DIR}/*_1366x768.png" \
  -vf "fps=5,format=yuv420p" \
  -c:v mpeg4 \
  -q:v 4 \
  -movflags +faststart \
  "${OUTPUT_VIDEO}"

echo "Vídeo de contingência SIMULADO: ${OUTPUT_VIDEO}"
