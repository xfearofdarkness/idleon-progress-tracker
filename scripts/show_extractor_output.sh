#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
PIP_DISABLE_PIP_VERSION_CHECK=1 pip install -e . >/dev/null

OUTPUT_LOG="${1:-}"

echo "== IdleOn Extractor: Save Detection =="
python -m idleon_reader --info

echo
echo "== IdleOn Extractor: Live CLI Output =="
if [ -n "$OUTPUT_LOG" ]; then
  python -m idleon_reader | tee "$OUTPUT_LOG"
else
  python -m idleon_reader
fi
