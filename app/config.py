"""Central configuration. Everything reads paths and keys from here."""
from __future__ import annotations

import os
import sys

# Windows consoles default to cp1252, which cannot encode Yoruba orthography and
# crashes any script that prints a transcript. Force UTF-8 at every entry point.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- paths ---
DATA = ROOT / "data"
DEMO_AUDIO = DATA / "demo" / "audio"
DEMO_META = DATA / "demo" / "meta"
CACHE = DATA / "cache"
RESULTS = ROOT / "benchmark" / "results"
REPORTS = ROOT / "reports"

for _p in (DATA, DEMO_AUDIO, DEMO_META, CACHE, RESULTS, REPORTS):
    _p.mkdir(parents=True, exist_ok=True)

# --- Intron / Sahara ---
INTRON_API_KEY = os.getenv("INTRON_API_KEY", "").strip()
INTRON_BASE = "https://infer.voice.intron.io"
INTRON_UPLOAD_SYNC = f"{INTRON_BASE}/file/v1/upload/sync"
INTRON_STATUS = f"{INTRON_BASE}/file/v1/status"

# Documented limits (docs.voice.intron.io). The runner throttles to stay under these.
INTRON_UPLOAD_RPM = 30
INTRON_STATUS_RPM = 100
INTRON_MAX_AUDIO_SECONDS = 120

# --- Hugging Face ---
# Accept every common spelling so a correctly-provisioned token is never missed
# just because it was named differently in .env.
HF_TOKEN = next(
    (v.strip() for v in (
        os.getenv("HF_TOKEN"), os.getenv("HF_API_KEY"),
        os.getenv("HUGGING_FACE_HUB_TOKEN"), os.getenv("HUGGINGFACE_TOKEN"),
    ) if v and v.strip()),
    "",
)

# --- datasets ---
AFRISWITCH_REPO = "intronhealth/AfriSwitch"

# AfriSwitch config name -> Intron STT language code.
LANG_TO_INTRON = {
    "yoruba": "yo",
    "igbo": "ig",
    "hausa": "ha",
    "pidgin": "pcm",
    "nigerian_pidgin": "pcm",
    "english": "en",
}

# Whisper needs an ISO-639-1 hint. Whisper has no Pidgin; it is treated as English,
# which is itself a finding worth reporting rather than hiding.
LANG_TO_WHISPER = {
    "yoruba": "yo",
    "igbo": "ig",
    "hausa": "ha",
    "pidgin": "en",
    "nigerian_pidgin": "en",
    "english": "en",
}

PRIMARY_LANGS = ["yoruba", "pidgin", "igbo", "hausa"]


def require(name: str, value: str, how: str) -> str:
    if not value:
        raise SystemExit(f"\n[config] Missing {name}.\n        {how}\n")
    return value
