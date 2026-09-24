@echo off
REM One-click: start local server (auto-opens admin panel in your browser).
cd /d "%~dp0"
python scripts\serve.py
