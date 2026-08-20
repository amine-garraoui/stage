@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
	echo Virtual environment not found. Run install.bat first.
	pause
	exit /b 1
)
.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
pause
