@echo off
REM One-click: preview the public site locally (homepage).
REM Starts the local server in a minimized window, then opens the page.
cd /d "%~dp0"
start "SitePreview" /min cmd /c python scripts\serve.py --no-open
timeout /t 2 >nul
start "" "http://localhost:8000/index.html"
echo Preview running at http://localhost:8000/ (close the SitePreview window to stop it).
