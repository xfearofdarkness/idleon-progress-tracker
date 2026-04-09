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

PIP_DISABLE_PIP_VERSION_CHECK=1 python -m pip install --upgrade pip setuptools wheel >/dev/null
PIP_DISABLE_PIP_VERSION_CHECK=1 python -m pip install -e . >/dev/null

echo "== IdleOn Tracker installed =="
echo "Virtual environment: $ROOT_DIR/.venv"
echo

if ! command -v leveldbutil >/dev/null 2>&1 && [ ! -x "$ROOT_DIR/tools/leveldbutil" ]; then
  echo "leveldbutil not found on PATH."
  echo "On macOS the recommended command is: brew install leveldb"
  echo
fi

echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  python -m idleon_reader --info"
echo "  python -m idleon_reader"
echo "  python -m idleon_reader --csv exports/latest"
echo "  bash scripts/export_tracker.sh"
