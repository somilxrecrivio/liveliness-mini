#!/usr/bin/env bash
# Start the Streamlit frontend.
set -euo pipefail
cd "$(dirname "$0")"

# shellcheck disable=SC1091
[ -d ".venv" ] && source .venv/bin/activate

exec streamlit run frontend/streamlit_app.py
