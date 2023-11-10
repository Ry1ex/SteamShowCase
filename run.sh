#!/bin/bash

if ! command -v python &>/dev/null; then
    echo "Python is not installed. Installing Python..."
    sudo apt-get update
    sudo apt-get install python3
fi

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Generating executable with PyInstaller..."
pyinstaller --onefile --icon=favicon.ico --add-data "SteamShowCaseLogo.png:." --noconsole SteamShowCase.py

if [ -f "./dist/SteamShowCase" ]; then
    echo "Executable generated successfully: ./dist/SteamShowCase"
else
    echo "Error during executable generation."
fi
