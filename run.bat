@echo off
cd /d "%~dp0"
if not exist .venv (
  py -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
  .venv\Scripts\playwright install chromium
)
.venv\Scripts\python app.py
