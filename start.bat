@echo off
echo ==============================================
echo   SmartHome OS - Unified Control Center
echo ==============================================

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Python is not installed or not in PATH.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo Checking and installing dependencies...
pip install -r requirements.txt

if not exist .env (
    if exist .env.example (
        echo Creating .env configuration from template...
        copy .env.example .env
    )
)

echo Starting SmartHome OS server...
python main.py %*

pause
