@echo off
title TELCHAM
chcp 65001 >nul
color 0A

cd /d "%~dp0"

echo Starting TELCHAM ...

if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file with your API credentials.
    echo.
    echo Get your API credentials from: https://my.telegram.org/apps
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

if not exist "photo_duplicate_finder.py" (
    echo ERROR: photo_duplicate_finder.py not found!
    echo Please make sure the script is in this folder.
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python from https://python.org
    echo.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

echo.
python photo_duplicate_finder.py

pause