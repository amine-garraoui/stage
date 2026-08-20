@echo off
REM ============================================================
REM  Install all dependencies (requires internet access)
REM ============================================================
echo Installing RSI KPI Platform dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Installation failed. Check your internet connection and proxy settings.
    pause
    exit /b 1
)
echo.
echo All dependencies installed successfully.
echo Run start.bat to launch the platform.
pause
