@echo off
cd /d "%~dp0"
where pythonw >nul 2>&1 && start "" pythonw app.py && exit /b
python app.py
if errorlevel 1 pause
