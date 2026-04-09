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
pip install -e .

if ! command -v leveldbutil >/dev/null 2>&1; then
  echo "leveldbutil not found. On macOS run: brew install leveldb"
fi

python -m idleon_reader --info
python -m idleon_reader --csv exports/latest
