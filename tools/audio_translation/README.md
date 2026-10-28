# Audio-assisted translation (100% offline)

Local pipeline: German text + Arabic audio → faster-whisper → Ollama polish → save into repo.

## Setup (once, needs network for downloads only)
```bat
pip install -r tools\audio_translation\requirements.txt
ollama pull qwen2.5:14b
winget install ffmpeg
ollama serve
```

## Run (offline)
```bat
tools\audio_translation\Run-Editor.bat
```
or:
```bat
streamlit run tools\audio_translation\app.py
```

Target files: listed from `docs-input/` + `docs/` (.txt/.md/.docx). New files default under `docs-input/new/`.
