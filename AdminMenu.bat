@echo off
cd /d "%~dp0"
:menu
cls
echo ===================================
echo       ADMIN PANEL MANAGER
echo ===================================
echo [1] Start Server & Open Panel
echo [2] Stop Server & out
echo ===================================
set /p choice="Choose an option (1-2): "

if "%choice%"=="1" (
    echo Starting server...
    start /b "" cmd /c python scripts\serve.py
    timeout /t 2 >nul
    goto menu
)
if "%choice%"=="2" (
    echo Stopping server...
    taskkill /f /im python.exe >nul 2>&1
    echo Server stopped.
    timeout /t 2 >nul
    exit
)

goto menu