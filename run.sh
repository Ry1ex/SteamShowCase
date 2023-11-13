#!/bin/bash
#To build the program yourself
if ! command -v python &>/dev/null; then
    echo "Python is not installed. Installing Python..."
    sudo apt-get update
    sudo apt-get install python3
fi

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Generating executable with PyInstaller..."
pyinstaller --onefile --icon=favicon.ico --distpath . --noconsole SteamShowCase.py
