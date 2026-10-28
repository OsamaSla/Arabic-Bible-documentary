"""Local Ollama polishing client. Uses stdlib only (offline, localhost)."""
from __future__ import annotations
import json
import urllib.request
try:
    from .prompts import SYSTEM_PROMPT
except ImportError:
    from prompts import SYSTEM_PROMPT


def polish_translation(
    german_text: str,
    arabic_raw: str,
    model: str = "qwen2.5:14b",
    ollama_url: str = "http://localhost:11434",
    timeout: int = 300,
) -> str:
    """Send German source + raw Arabic to local Ollama, return cleaned Arabic only."""
    if not german_text.strip() or not arabic_raw.strip():
        raise ValueError("German source and Arabic transcription must both be non-empty.")
    user_msg = (
        "النص الألماني المصدر:\n---\n" + german_text.strip()
        + "\n---\n\nالتفريغ العربي الخام:\n---\n" + arabic_raw.strip()
        + "\n---\n\nأخرج فقط النص العربي النهائي النظيف."
    )
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
    except ConnectionRefusedError:
        raise RuntimeError("Cannot reach Ollama at localhost:11434. Run `ollama serve` first.")
    except OSError as e:
        raise RuntimeError(f"Ollama request failed (is `ollama serve` running? model `{model}` pulled?): {e}")
    msg = (data.get("message") or {}).get("content", "").strip()
    if not msg:
        raise RuntimeError(f"Empty Ollama response: {str(data)[:300]}")
    return msg
