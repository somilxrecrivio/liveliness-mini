#!/usr/bin/env bash
# ============================================================
# Enterprise Liveness Verification System - Setup
# Creates a virtual environment, installs dependencies and
# downloads all required models. Idempotent and safe to re-run.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[setup] python3.11 not found, falling back to python3"
  PYTHON_BIN="python3"
fi

echo "[setup] Using interpreter: $($PYTHON_BIN --version)"

if [ ! -d ".venv" ]; then
  echo "[setup] Creating virtual environment (.venv)"
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[setup] Upgrading pip"
python -m pip install --upgrade pip wheel

echo "[setup] Installing dependencies"
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[setup] Creating .env from .env.example"
  cp .env.example .env
fi

echo "[setup] Downloading models"
python -m backend.utils.model_manager

echo "[setup] Done. Activate with: source .venv/bin/activate"
