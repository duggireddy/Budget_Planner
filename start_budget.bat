@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment...
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

if not exist .env (
    echo Copying .env from .env.example...
    copy /Y .env.example .env >nul
)

if not exist data mkdir data

REM Stop old server on port 8765 if running
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do (
    echo Stopping old process on port 8765...
    taskkill /PID %%a /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)

start "" http://127.0.0.1:8765
echo Starting app (local SQLite database in data\budget.db)...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
