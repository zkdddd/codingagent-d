@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Starting kagent in dev reload mode...
D:\python3.12.9\python.exe main.py --dev-reload
echo.
echo === kagent exited with code %errorlevel% ===
echo Check crash.log for details.
pause
