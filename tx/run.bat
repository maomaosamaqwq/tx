@echo off
chcp 65001 >nul
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.6+ and add to PATH.
    pause
    exit /b 1
)
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo PySide6 not found, installing...
    pip install PySide6
    if errorlevel 1 (
        echo Failed to install PySide6.
        pause
        exit /b 1
    )
)
python tx.py
pause