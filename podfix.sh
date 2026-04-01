#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

ensure_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  echo "python3 is required but was not found on PATH" >&2
  exit 1
}

ensure_venv() {
  if [[ -x "$VENV_PYTHON" ]]; then
    return
  fi

  local bootstrap_python
  bootstrap_python="$(ensure_python)"
  "$bootstrap_python" -m venv "$VENV_DIR"
}

ensure_install() {
  if "$VENV_PYTHON" - <<'PY' >/dev/null 2>&1
import feedparser
import PIL
import requests
import podcast_proxy
PY
  then
    return
  fi

  "$VENV_PYTHON" -m pip install -e "$PROJECT_DIR"
}

main() {
  ensure_venv
  ensure_install

  cd "$PROJECT_DIR"
  export PYTHONPATH="$PROJECT_DIR/src"
  exec "$VENV_PYTHON" -m podcast_proxy.cli "$@"
}

main "$@"
