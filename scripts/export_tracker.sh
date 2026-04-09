#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="${1:-exports/latest}"
MODE="${2:-}"

if [ ! -d ".venv" ]; then
  bash scripts/install_tracker.sh >/dev/null
fi

source .venv/bin/activate
if ! python -c "import idleon_reader" >/dev/null 2>&1; then
  PIP_DISABLE_PIP_VERSION_CHECK=1 python -m pip install -e . >/dev/null
fi

ARGS=( -m idleon_reader --csv "$OUTPUT_DIR" )
if [ "$MODE" = "--append" ]; then
  ARGS+=( --append )
fi

python "${ARGS[@]}"
