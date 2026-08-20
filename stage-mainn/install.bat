@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
	python -m venv .venv
	if errorlevel 1 (
		echo Failed to create the virtual environment.
		pause
		exit /b 1
	)
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
	echo Failed to install dependencies.
	pause
	exit /b 1
)
echo Installation complete.
pause
