#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
CONFIG_FILE="${CONFIG_FILE:-$PROJECT_DIR/config.server.toml}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src"
exec "$VENV_PYTHON" -m podcast_proxy.cli sync --config "$CONFIG_FILE"
