@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --clean --onefile --windowed --name BreachProtocol --add-data "templates.npz;." app.py
if errorlevel 1 goto fail
echo.
echo dist\BreachProtocol.exe
exit /b 0
:fail
pause
exit /b 1
