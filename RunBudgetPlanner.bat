@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run: python -m venv .venv
  echo      .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
call .venv\Scripts\python.exe launcher.py
