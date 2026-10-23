#!/bin/sh
# First run: creates a virtual environment and installs everything, then starts the site.
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/playwright install chromium
fi
.venv/bin/python app.py
