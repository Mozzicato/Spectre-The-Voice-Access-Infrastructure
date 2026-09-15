"""FastAPI backend for the voice-first UI.

The frontend never mentions Sahara, Whisper or MMS. It posts audio and receives a case
packet. Swapping the speech model is a query parameter, not a rewrite - which is the
architectural claim the whole project rests on.

    python -m uvicorn app.server:app --reload --port 8000
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app import config, llm, schemas
from app.asr import ENGINES, build, to_wav16k_mono
from app.compiler import CaseCompiler
from app.questions import apply_answer
from app.routing import build_packet

app = FastAPI(title="Voice Access Infrastructure", version="1.0")

_compiler: CaseCompiler | None = None
_engines: dict[str, object] = {}


def get_compiler() -> CaseCompiler:
    global _compiler
    if _compiler is None:
        _compiler = CaseCompiler()
    return _compiler


def get_engine(name: str):
    if name not in ENGINES:
        raise HTTPException(400, f"unknown model {name!r}; choose from {sorted(ENGINES)}")
    if name not in _engines:
        _engines[name] = build(name)
    return _engines[name]


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "asr_models": sorted(ENGINES),
        "compilers": {k: s.label for k, s in schemas.SCHEMAS.items()},
        "llm": llm.describe_setup(),
    }


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    model: str = Form("sahara"),
    language: str = Form("pidgin"),
) -> JSONResponse:
    engine = get_engine(model)
    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f"upload{suffix}"
        raw.write_bytes(await audio.read())
        try:
            wav = to_wav16k_mono(raw, Path(tmp) / "clip.wav")
        except Exception as exc:
            raise HTTPException(400, f"could not decode audio: {exc}")

        result = engine.transcribe(wav, language, "live")

    if result.error:
        raise HTTPException(502, f"ASR failed: {result.error}")
    return JSONResponse({
        "transcript": result.text,
        "model": result.model,
        "language": result.language,
        "latency_s": result.latency_s,
    })


@app.post("/api/compile")
async def compile_case(
    transcript: str = Form(...),
    domain: str | None = Form(None),
    evidence: str | None = Form(None),
) -> JSONResponse:
    if not transcript.strip():
        raise HTTPException(400, "empty transcript")
    supplied = [e.strip() for e in (evidence or "").split(",") if e.strip()]
    case = get_compiler().compile(transcript, domain or None)
    return JSONResponse(build_packet(case, supplied))


@app.post("/api/answer")
async def answer(
    transcript: str = Form(...),
    domain: str = Form(...),
    field: str = Form(...),
    answer: str = Form(...),
) -> JSONResponse:
    """Fold one spoken answer into the case and return the updated packet."""
    case = get_compiler().compile(transcript, domain)
    apply_answer(case, field, answer)
    return JSONResponse(build_packet(case))


@app.get("/")
def index() -> FileResponse:
    page = Path(__file__).resolve().parent / "static" / "index.html"
    if not page.exists():
        raise HTTPException(404, "UI not built")
    return FileResponse(page)


@app.get("/api/config")
def ui_config() -> dict:
    return {
        "models": sorted(ENGINES),
        "languages": sorted(config.LANG_TO_INTRON),
        "domains": [
            {"key": s.key, "label": s.label, "icon": s.icon}
            for s in schemas.SCHEMAS.values()
        ],
    }
