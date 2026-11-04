@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
if not exist frontend\dist\index.html (
    echo Frontend build not found; installing frontend dependencies and building it...
    cd frontend
    call npm ci
    if errorlevel 1 exit /b %errorlevel%
    call npm run build
    if errorlevel 1 exit /b %errorlevel%
    cd ..
)
.venv\Scripts\python.exe run.py
pause
