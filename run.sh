#!/usr/bin/env bash
# One-click start for macOS / Linux.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv && source .venv/bin/activate
  pip install --upgrade pip && pip install -r requirements.txt
  python -m core.seed
else
  source .venv/bin/activate
fi
(sleep 6; python -m webbrowser http://localhost:8501 >/dev/null 2>&1) &
streamlit run app.py
