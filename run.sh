#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
	python3 -m venv venv
fi

venv/bin/python -m pip install -r requirements.txt
venv/bin/python main.py
