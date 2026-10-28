"""Offline audio-assisted translation editor (Streamlit, local-only)."""
from __future__ import annotations
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st

from transcribe import transcribe_audio
from polish import polish_translation
from doc_io import list_articles, read_article, save_article

st.set_page_config(page_title="Audio Translation Editor (local)", layout="wide")

CSS = """
<style>
:root { --focus: #d4a017; }
html, .stApp, [data-testid="stSidebar"] { direction: ltr; text-align: left; }
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, [data-testid="stCaptionContainer"] { text-align: left; }
button:focus-visible, textarea:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid var(--focus) !important; outline-offset: 2px; }
.panel { min-height: 220px; min-width: 280px; }
.skeleton { min-height: 220px; background: repeating-linear-gradient(45deg,#f2f2f2,#f2f2f2 10px,#e8e8e8 10px,#e8e8e8 20px); border-radius: 8px; }
.stApp textarea { direction: ltr; text-align: left; font-size: 1.05rem; line-height: 1.8; }
.stApp textarea[aria-label="Raw Arabic"], .stApp textarea[aria-label="Cleaned Arabic (editable)"] { direction: rtl !important; text-align: right !important; line-height: 2; }
.stApp input { direction: ltr; text-align: left; }
/* Compact uploaders: single-line instead of huge dropzone */
[data-testid="stFileUploaderDropzone"] { min-height: 44px !important; padding: 4px 10px !important; }
[data-testid="stFileUploaderDropzone"] svg { width: 16px !important; height: 16px !important; }
[data-testid="stFileUploaderDropzone"] p, [data-testid="stFileUploaderDropzone"] span, [data-testid="stFileUploaderDropzone"] small { font-size: 0.75rem !important; margin: 0 !important; }
[data-testid="stFileUploader"] { margin-bottom: 4px; }
[data-testid="stFileUploader"] ul { margin: 2px 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.title("Audio Translation Editor — Fully Offline")

with st.sidebar:
    st.header("Local settings")
    whisper_model = st.selectbox("Whisper model", ["tiny", "base", "small", "medium", "large-v3"], index=3)
    ollama_model = st.text_input("Ollama model", value="qwen2.5:14b")
    ollama_url = st.text_input("Ollama URL", value="http://localhost:11434")
    st.caption("No data leaves your machine. Requires: faster-whisper + Ollama + ffmpeg.")

col_de, col_ar = st.columns(2)
with col_de:
    st.subheader("1) German source text")
    de_upload = st.file_uploader("German file (.txt/.md)", type=["txt", "md"], label_visibility="visible")
    de_text = ""
    if de_upload:
        raw_bytes = de_upload.getvalue()
        for enc in ("utf-8-sig", "utf-8", "windows-1256", "cp1252", "latin-1"):
            try:
                de_text = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, ValueError):
                continue
    german = st.text_area("German source", height=220,
                          value=de_text,
                          placeholder="Paste German text here…")
with col_ar:
    st.subheader("2) Arabic audio recording")
    # type=None = no browser-side filtering (Windows Sound Recorder MP3s report
    # as audio/mpeg and were rejected by the extension allowlist). Validation
    # happens in transcribe.py with a clear error message instead.
    audio = st.file_uploader("Audio file (MP3 / M4A / WAV / OGG / OPUS / FLAC / WebM / WMA / MP4 — e.g. Windows Sound Recorder)", type=None, label_visibility="visible",
                             help="Any file can be selected; unsupported containers show a clear error. Supported: mp3, mpeg, m4a, m4b, mp4, wma, wav, ogg, oga, opus, flac, webm.")
    if audio is not None:
        st.caption(f"Selected: {audio.name} ({audio.type or 'unknown type'}, {len(audio.getvalue())} bytes)")
    st.caption("Alternative (bypasses browser upload entirely): paste a local file path.")
    local_path = st.text_input("Local audio path (e.g. C:\\Recordings\\voice.mp3)", value="")
    if st.button("Transcribe from file path", disabled=not local_path.strip()):
        with st.spinner("Transcribing with faster-whisper…"):
            try:
                res = transcribe_audio(local_path.strip().strip('"'), model_size=whisper_model)
                st.session_state["raw"] = res["text"]
                st.session_state["raw_edit"] = res["text"]
                st.session_state["transcribe_info"] = res
                if not res["text"].strip():
                    st.warning("Transcription finished but no text (0 segments). Try a larger model or clearer audio.")
                else:
                    st.success(f"Transcribed: {len(res['segments'])} segments.")
            except Exception as e:
                st.error(f"Transcription failed: {e}")
    if st.button("Transcribe audio locally", disabled=audio is None, type="primary"):
        import os
        suffix = Path(audio.name).suffix.lower() if audio.name else ""
        if not suffix:
            suffix = ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio.getvalue())
            tmp_path = tmp.name
        with st.spinner("Transcribing with faster-whisper…"):
            try:
                res = transcribe_audio(tmp_path, model_size=whisper_model)
                st.session_state["raw"] = res["text"]
                st.session_state["raw_edit"] = res["text"]
                st.session_state["transcribe_info"] = res
                if not res["text"].strip():
                    st.warning("Transcription finished but no text (0 segments). Try a larger model or clearer audio.")
                else:
                    st.success(f"Transcribed: {len(res['segments'])} segments.")
            except Exception as e:
                st.error(f"Transcription failed: {e}")
                st.caption("Check: ffmpeg installed, model downloaded once (needs internet first time), format mp3/mpeg/m4a/m4b/mp4/wma/wav/ogg/opus/flac/webm.")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        st.caption("Audio temp file is deleted after transcription and is never stored.")

raw_default = st.session_state.get("raw", "")
if "raw_edit" not in st.session_state:
    st.session_state["raw_edit"] = raw_default
st.subheader("3) Raw transcript (editable)")
raw = st.text_area("Raw Arabic", height=180, key="raw_edit",
                   placeholder="Transcript will appear here…")
info = st.session_state.get("transcribe_info")
if info:
    st.caption(f"Language: {info.get('language')} — Segments: {len(info.get('segments', []))} — VAD: {info.get('vad_filter')}")

if st.button("Clean & align via Ollama", disabled=not (german.strip() and raw.strip())):
    with st.spinner(f"Processing with {ollama_model}…"):
        try:
            cleaned = polish_translation(german, raw, model=ollama_model, ollama_url=ollama_url)
            st.session_state["clean"] = cleaned
            st.session_state["clean_edit"] = cleaned
        except Exception as e:
            st.error(str(e))

st.subheader("4) Side-by-side preview")
state = st.radio("Preview state", ["default", "loading", "disabled"], horizontal=True)
clean_default = st.session_state.get("clean", "")
if "clean_edit" not in st.session_state:
    st.session_state["clean_edit"] = clean_default
disabled = state == "disabled"
if state == "loading":
    st.markdown('<div class="skeleton panel"></div>', unsafe_allow_html=True)
else:
    c1, c2 = st.columns(2)
    with c1:
        st.text_area("German preview", value=german, height=220, disabled=True)
    with c2:
        clean = st.text_area("Cleaned Arabic (editable)", height=220,
                             key="clean_edit", disabled=disabled)

st.subheader("5) Save to site repository")
articles = list_articles()
target = st.selectbox("Choose an existing file or enter a new path", ["<new file>"] + articles)
new_path = ""
if target == "<new file>":
    new_path = st.text_input("New path (e.g. docs-input/author/article.docx)", value="docs-input/new/article.docx")
mode = st.radio("Save mode", ["append", "overwrite"], horizontal=True)
final_text = st.session_state.get("clean_edit", clean_default)
if st.button("Save final text", disabled=not final_text.strip(), type="primary"):
    dest = new_path.strip() if target == "<new file>" else target
    if not dest:
        st.error("Select a save path.")
    else:
        try:
            saved = save_article(dest, final_text, mode=mode)
            st.success(f"Saved to: {saved}")
        except Exception as e:
            st.error(str(e))
