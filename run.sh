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
streamlit run app.py
