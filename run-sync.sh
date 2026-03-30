#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/Users/rolf/dockers/ngnix-slim/static/podfix"
CONFIG_FILE="$PROJECT_DIR/config.toml"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR/src"
exec "$VENV_PYTHON" -m podcast_proxy.cli sync --config "$CONFIG_FILE"
