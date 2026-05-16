@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt pytest
python -m pytest tests/ -v --tb=short
pause
