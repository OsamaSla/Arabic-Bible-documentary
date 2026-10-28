"""Offline Arabic transcription with faster-whisper. No network calls."""
from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path

SUPPORTED_EXTS = {".mp3", ".mpeg", ".mpg", ".mpga", ".mpeg4", ".m4a", ".m4b", ".mp4", ".wma", ".wav", ".ogg", ".oga", ".opus", ".flac", ".webm"}


def _find_ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # bundled binary, still offline
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _to_wav(src: Path, ffmpeg: str) -> Path:
    """Convert to 16kHz mono wav for stable transcription."""
    if src.suffix.lower() == ".wav":
        return src
    fd, out_name = tempfile.mkstemp(prefix=f"{src.stem}_", suffix="_16k.wav")
    import os
    os.close(fd)
    out = Path(out_name)
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(out)],
            check=False, capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"ffmpeg executable failed to start ({ffmpeg}): {e}")
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        err = (proc.stderr or "")[-2000:]
        raise RuntimeError(f"ffmpeg convert failed for {src.name} (code {proc.returncode}). {err}")
    return out


def transcribe_audio(
    audio_path: str | Path,
    model_size: str = "medium",
    language: str = "ar",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict:
    """Transcribe Arabic audio locally. Returns {text, segments, language}."""
    from faster_whisper import WhisperModel

    src = Path(audio_path)
    if src.suffix.lower() not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported audio type: {src.suffix}. Use {sorted(SUPPORTED_EXTS)}.")
    if not src.exists():
        raise FileNotFoundError(f"Audio temp file not found: {src} (upload may have been cleaned up, retry upload).")
    if src.stat().st_size == 0:
        raise ValueError("Empty audio file (0 bytes). Re-upload the recording.")

    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found. Install it (winget install ffmpeg) or pip install imageio-ffmpeg.")
    wav = _to_wav(src, ffmpeg)

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    try:
        # First pass with VAD (cleaner for long recordings), fallback without VAD
        # because VAD can over-filter short/quiet clips into 0 segments.
        segments_iter, info = model.transcribe(str(wav), language=language, vad_filter=True)
        segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_iter]
        used_vad = True
        if not segments:
            segments_iter, info = model.transcribe(str(wav), language=language, vad_filter=False)
            segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_iter]
            used_vad = False
        segments = [s for s in segments if s["text"]]
        text = " ".join(s["text"] for s in segments).strip()
        lang = info.language
    finally:
        if wav != src:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass
    return {"text": text, "segments": segments, "language": lang, "vad_filter": used_vad}
