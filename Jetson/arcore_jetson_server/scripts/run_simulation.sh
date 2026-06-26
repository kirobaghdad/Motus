#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi
export MOTUS_SIM=1
exec python3 run.py
