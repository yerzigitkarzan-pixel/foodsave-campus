@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Install Python 3.12, then run this file again.
    pause
    exit /b 1
  )
)
if not exist ".venv\foodsave-installed" (
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Check your Internet connection.
    pause
    exit /b 1
  )
  type nul > ".venv\foodsave-installed"
)
".venv\Scripts\python.exe" run.py
pause
