#!/usr/bin/env bash
# AIDA Desktop ilovasini ishga tushirish
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Virtual muhit yaratilmoqda…"
    python3 -m venv .venv
    ./.venv/bin/python -m pip install --upgrade pip
    ./.venv/bin/python -m pip install -r requirements.txt
fi

exec ./.venv/bin/python -m app.main
