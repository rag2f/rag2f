#!/usr/bin/env bash

set -euo pipefail

VENV_DIR=".venv"
MARKER_FILE="$VENV_DIR/.rag2f_bootstrapped"

python_bin=""
if command -v python3.12 >/dev/null 2>&1; then
  python_bin="python3.12"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="python3"
elif command -v python >/dev/null 2>&1; then
  python_bin="python"
else
  echo "ERROR: Python not found on PATH." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv in $VENV_DIR using $python_bin..."
  "$python_bin" -m venv "$VENV_DIR"
fi

venv_python="$VENV_DIR/bin/python"
if [[ ! -x "$venv_python" ]]; then
  echo "ERROR: venv python not found at $venv_python" >&2
  exit 1
fi

if [[ -f "$MARKER_FILE" ]]; then
  echo "venv already bootstrapped ($VENV_DIR)."
  exit 0
fi

echo "Upgrading pip..."
"$venv_python" -m pip install --upgrade pip

echo "Installing project (editable) + dev extras..."
"$venv_python" -m pip install uv
"$venv_python" -m uv pip install -e .
"$venv_python" -m uv pip install -e '.[dev]'

if [[ -x "$VENV_DIR/bin/pre-commit" ]]; then
  echo "Installing pre-commit hooks..."
  "$VENV_DIR/bin/pre-commit" install
fi

touch "$MARKER_FILE"

echo "Done. To activate: source $VENV_DIR/bin/activate"
