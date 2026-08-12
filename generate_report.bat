@echo off
cd /d "%~dp0"
python scripts\generate_monthly_report.py --month 2026-06
pause
