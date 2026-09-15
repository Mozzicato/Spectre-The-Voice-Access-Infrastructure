"""ASR abstraction.

One interface, several engines. The rest of the system never imports a specific
speech model, so swapping Sahara for Whisper (or adding a fourth engine) changes
nothing downstream. That separation is the whole architectural claim of the project.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Protocol

import requests

from app import config


@dataclass
class ASRResult:
    audio_id: str
    model: str
    text: str
    latency_s: float
    language: str = ""
    error: str = ""
    meta: dict | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class ASREngine(Protocol):
    name: str

    def transcribe(self, wav_path: Path, language: str, audio_id: str) -> ASRResult: ...


# --------------------------------------------------------------------------------------
# audio helpers
# --------------------------------------------------------------------------------------

def to_wav16k_mono(src: Path, dst: Path) -> Path:
    """Normalize any input audio to 16 kHz mono PCM via ffmpeg.

    ffmpeg is used rather than librosa so the project does not depend on numba/llvmlite,
    which failed to install on this machine and buys us nothing here.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
        check=True,
    )
    return dst


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


class _RateLimiter:
    """Simple sliding-window limiter, shared across threads."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._hits and now - self._hits[0] > 60.0:
                    self._hits.popleft()
                if len(self._hits) < self.per_minute:
                    self._hits.append(now)
                    return
                sleep_for = 60.0 - (now - self._hits[0]) + 0.05
            time.sleep(max(sleep_for, 0.05))


# --------------------------------------------------------------------------------------
# 1. Intron Sahara v2.5  (API)
# --------------------------------------------------------------------------------------

class SaharaASR:
    """Intron Sahara v2.5 via the file upload endpoint.

    The /upload/sync endpoint frequently returns FILE_QUEUED rather than a finished
    transcript, so a status poll is mandatory, not an optimisation. Verified against the
    live API before this was written.
    """

    name = "sahara"

    def __init__(self, api_key: str | None = None, poll_timeout: float = 180.0):
        self.api_key = api_key or config.INTRON_API_KEY
        config.require(
            "INTRON_API_KEY", self.api_key,
            "Get it from https://voice.intron.io -> Developers tab, then put it in .env",
        )
        self.poll_timeout = poll_timeout
        self._upload_limiter = _RateLimiter(config.INTRON_UPLOAD_RPM)
        self._status_limiter = _RateLimiter(config.INTRON_STATUS_RPM)
        self._session = requests.Session()

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def transcribe(self, wav_path: Path, language: str, audio_id: str) -> ASRResult:
        lang = config.LANG_TO_INTRON.get(language, language or "en")
        started = time.monotonic()

        try:
            duration = audio_duration(wav_path)
            if duration > config.INTRON_MAX_AUDIO_SECONDS:
                return ASRResult(
                    audio_id, self.name, "", 0.0, lang,
                    error=f"audio {duration:.1f}s exceeds Sahara limit of "
                          f"{config.INTRON_MAX_AUDIO_SECONDS}s",
                )
        except Exception as exc:  # ffprobe missing or unreadable file
            duration = -1.0
            del exc

        payload, err = self._upload(wav_path, lang)
        if err:
            return ASRResult(audio_id, self.name, "", time.monotonic() - started, lang, error=err)

        status = payload.get("processing_status", "")
        text = payload.get("audio_transcript") or ""
        file_id = payload.get("file_id", "")

        if status != "FILE_TRANSCRIBED" and file_id:
            text, status, err = self._poll(file_id)
            if err:
                return ASRResult(
                    audio_id, self.name, "", time.monotonic() - started, lang, error=err
                )

        return ASRResult(
            audio_id=audio_id,
            model=self.name,
            text=(text or "").strip(),
            latency_s=round(time.monotonic() - started, 3),
            language=lang,
            meta={"file_id": file_id, "status": status, "audio_seconds": duration},
        )

    def _upload(self, wav_path: Path, lang: str, attempts: int = 4):
        for attempt in range(attempts):
            self._upload_limiter.acquire()
            try:
                with open(wav_path, "rb") as fh:
                    resp = self._session.post(
                        config.INTRON_UPLOAD_SYNC,
                        headers=self._headers,
                        files={"audio_file_blob": (wav_path.name, fh, "audio/wav")},
                        data={
                            "audio_file_name": wav_path.name,
                            "use_language_asr_input": lang,
                        },
                        timeout=300,
                    )
            except requests.RequestException as exc:
                if attempt == attempts - 1:
                    return None, f"network error: {exc}"
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 200:
                return resp.json().get("data", {}), None

            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 5))
                time.sleep(wait + 0.5)
                continue

            # 503 still hands back a file_id we can poll for.
            if resp.status_code == 503:
                try:
                    data = resp.json().get("data", {})
                    if data.get("file_id"):
                        return data, None
                except ValueError:
                    pass

            if 500 <= resp.status_code < 600 and attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue

            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"

        return None, "upload failed after retries"

    def _poll(self, file_id: str):
        deadline = time.monotonic() + self.poll_timeout
        delay = 1.5
        last_status = ""
        while time.monotonic() < deadline:
            time.sleep(delay)
            delay = min(delay * 1.4, 10.0)
            self._status_limiter.acquire()
            try:
                resp = self._session.get(
                    f"{config.INTRON_STATUS}/{file_id}", headers=self._headers, timeout=60
                )
            except requests.RequestException:
                continue

            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("Retry-After", 5)) + 0.5)
                continue
            if resp.status_code != 200:
                continue

            data = resp.json().get("data", {})
            last_status = data.get("processing_status", "")
            if last_status == "FILE_TRANSCRIBED":
                return data.get("audio_transcript") or "", last_status, None
            if last_status == "FILE_PROCESSING_FAILED":
                return "", last_status, "Sahara reported FILE_PROCESSING_FAILED"

        return "", last_status, f"poll timed out after {self.poll_timeout}s (last={last_status})"


# --------------------------------------------------------------------------------------
# 2. Whisper small  (local, CPU)
# --------------------------------------------------------------------------------------

class WhisperASR:
    """General-purpose multilingual baseline via faster-whisper.

    int8 on CPU. Whisper has no Nigerian Pidgin token, so Pidgin is sent as English;
    that is a genuine limitation of the baseline and is reported, not hidden.
    """

    name = "whisper_small"

    def __init__(self, size: str = "small", compute_type: str = "int8"):
        self.size = size
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.size, device="cpu", compute_type=self.compute_type, cpu_threads=4
            )
        return self._model

    def transcribe(self, wav_path: Path, language: str, audio_id: str) -> ASRResult:
        lang = config.LANG_TO_WHISPER.get(language, "en")
        started = time.monotonic()
        try:
            model = self._load()
            segments, info = model.transcribe(
                str(wav_path), language=lang, beam_size=5, vad_filter=False
            )
            text = "".join(seg.text for seg in segments).strip()
            return ASRResult(
                audio_id, self.name, text, round(time.monotonic() - started, 3), lang,
                meta={"requested_language": lang,
                      "detected_language": getattr(info, "language", "")},
            )
        except Exception as exc:
            return ASRResult(
                audio_id, self.name, "", round(time.monotonic() - started, 3), lang,
                error=f"{type(exc).__name__}: {exc}",
            )


# --------------------------------------------------------------------------------------
# 3. MMS-300M Yoruba-English  (local, CPU)
# --------------------------------------------------------------------------------------

class MMSYorubaEnglishASR:
    """LyngualLabs MMS-300M fine-tuned for Yoruba-English code-switching.

    A wav2vec2-style CTC model. It is Yoruba-English only, so it is scored ONLY on the
    Yoruba track. Running it on Hausa and calling that a fair comparison would be
    dishonest benchmarking.
    """

    name = "mms_yoruba_english"
    repo = "LyngualLabs/mms-300m-yoruba-english"
    supported_languages = {"yoruba"}

    def __init__(self, repo: str | None = None):
        self.repo = repo or self.repo
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoProcessor, AutoModelForCTC
            kwargs = {"token": config.HF_TOKEN} if config.HF_TOKEN else {}
            self._processor = AutoProcessor.from_pretrained(self.repo, **kwargs)
            self._model = AutoModelForCTC.from_pretrained(self.repo, **kwargs)
            self._model.eval()
            torch.set_num_threads(4)
        return self._model, self._processor

    def transcribe(self, wav_path: Path, language: str, audio_id: str) -> ASRResult:
        started = time.monotonic()
        try:
            import torch
            import soundfile as sf

            model, processor = self._load()
            audio, sr = sf.read(str(wav_path), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != 16000:
                raise ValueError(f"expected 16 kHz, got {sr}")

            inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
            with torch.no_grad():
                logits = model(**inputs).logits
            ids = torch.argmax(logits, dim=-1)
            text = processor.batch_decode(ids)[0].strip()

            return ASRResult(
                audio_id, self.name, text, round(time.monotonic() - started, 3), language,
            )
        except Exception as exc:
            return ASRResult(
                audio_id, self.name, "", round(time.monotonic() - started, 3), language,
                error=f"{type(exc).__name__}: {exc}",
            )


# --------------------------------------------------------------------------------------

class GroqWhisperASR:
    """Whisper large-v3 via Groq's hosted audio endpoint.

    The plan ruled large-v3 out as too heavy for an 8 GB laptop, which is true locally.
    Hosting it removes that constraint entirely, so the benchmark gets the strongest
    general-purpose baseline available without spending a byte of local RAM. That also
    lets us test the published claim that large-v3 does badly on AfriSwitch Yoruba
    instead of citing it.
    """

    name = "whisper_large_v3"
    url = "https://api.groq.com/openai/v1/audio/transcriptions"

    def __init__(self, model: str = "whisper-large-v3", api_key: str | None = None):
        import os
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        config.require(
            "GROQ_API_KEY", self.api_key,
            "Get a free key at https://console.groq.com/keys, then put it in .env",
        )
        self._session = requests.Session()
        self._limiter = _RateLimiter(20)

    def transcribe(self, wav_path: Path, language: str, audio_id: str) -> ASRResult:
        lang = config.LANG_TO_WHISPER.get(language, "en")
        started = time.monotonic()
        for attempt in range(4):
            self._limiter.acquire()
            try:
                with open(wav_path, "rb") as fh:
                    resp = self._session.post(
                        self.url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": (wav_path.name, fh, "audio/wav")},
                        data={"model": self.model, "language": lang,
                              "response_format": "json", "temperature": "0"},
                        timeout=300,
                    )
            except requests.RequestException as exc:
                if attempt == 3:
                    return ASRResult(audio_id, self.name, "",
                                     round(time.monotonic() - started, 3), lang,
                                     error=f"network error: {exc}")
                time.sleep(2 ** attempt)
                continue

            if resp.status_code == 200:
                return ASRResult(
                    audio_id, self.name, (resp.json().get("text") or "").strip(),
                    round(time.monotonic() - started, 3), lang,
                    meta={"hosted_model": self.model},
                )
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("retry-after", 5)) + 0.5)
                continue
            if 500 <= resp.status_code < 600 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return ASRResult(audio_id, self.name, "",
                             round(time.monotonic() - started, 3), lang,
                             error=f"HTTP {resp.status_code}: {resp.text[:200]}")

        return ASRResult(audio_id, self.name, "", round(time.monotonic() - started, 3),
                         lang, error="failed after retries")


ENGINES: dict[str, type] = {
    SaharaASR.name: SaharaASR,
    WhisperASR.name: WhisperASR,
    MMSYorubaEnglishASR.name: MMSYorubaEnglishASR,
    GroqWhisperASR.name: GroqWhisperASR,
}


def build(name: str) -> ASREngine:
    if name not in ENGINES:
        raise SystemExit(f"unknown engine {name!r}; choose from {sorted(ENGINES)}")
    return ENGINES[name]()


def transcribe_file(engine: ASREngine, src: Path, language: str, audio_id: str) -> ASRResult:
    """Transcribe any audio file, converting to 16 kHz mono first if needed."""
    if src.suffix.lower() == ".wav":
        return engine.transcribe(src, language, audio_id)
    with tempfile.TemporaryDirectory() as tmp:
        wav = to_wav16k_mono(src, Path(tmp) / f"{src.stem}.wav")
        return engine.transcribe(wav, language, audio_id)
