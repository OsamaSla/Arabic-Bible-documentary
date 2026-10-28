@echo off
cd /d "%~dp0..\.."
streamlit run tools\audio_translation\app.py
pause
