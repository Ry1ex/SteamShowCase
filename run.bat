@echo off
rem To build the program yourself

rem Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Please install Python.
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -r requirements.txt

echo Generating executable with PyInstaller...
pyinstaller --onefile --icon=favicon.ico --distpath . --noconsole SteamShowCase.py

pause
