@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Create a venv first: python -m venv .venv
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt -r requirements-build.txt

if not exist "static\vendor\chart.umd.min.js" (
  echo Downloading Chart.js for offline use...
  powershell -NoProfile -Command ^
    "New-Item -ItemType Directory -Force -Path 'static\vendor' | Out-Null; ^
     Invoke-WebRequest -Uri 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js' -OutFile 'static\vendor\chart.umd.min.js'"
)

python -m pytest tests/ -q
if errorlevel 1 (
  echo Tests failed — fix before building the .exe
  exit /b 1
)

pyinstaller BudgetPlanner.spec --noconfirm
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   dist\BudgetPlanner\BudgetPlanner.exe
echo.
echo Copy the whole dist\BudgetPlanner folder to your PC or USB.
echo Your database will be created in data\budget.db next to the .exe.
pause
