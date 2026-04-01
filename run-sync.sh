#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
CONFIG_FILE="${CONFIG_FILE:-$PROJECT_DIR/config.server.toml}"

cd "$PROJECT_DIR"
exec "$PROJECT_DIR/podfix.sh" sync --config "$CONFIG_FILE"
