@echo off
REM ============================================================
REM  RSI Sagemcom KPI Platform — Startup Script
REM  Run this script to launch the platform.
REM ============================================================
echo.
echo  RSI Sagemcom KPI Platform
echo  ========================
echo.

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

REM Check dependencies
python -c "import streamlit" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Dependencies not installed.
    echo Run: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Create .env if missing
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo NOTE: .env created from example. Review and set SECRET_KEY.
)

REM Launch
echo Starting application on http://localhost:8501 ...
echo Press Ctrl+C to stop.
echo.
streamlit run main.py

pause
