"""End-to-end demo: one audio file -> transcript -> structured case packet.

    python scripts/demo.py data/demo/audio/fin_01_s1.wav
    python scripts/demo.py fin_01_s1.wav --model whisper_large_v3 --domain financial
    python scripts/demo.py --text "My landlord dey tell me make I comot..."

This is the script to screen-record for the submission video: it shows speech going in
and an actionable institutional case coming out, with the missing-information and
routing steps visible.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, llm  # noqa: E402
from app.asr import build, transcribe_file  # noqa: E402
from app.compiler import CaseCompiler  # noqa: E402
from app.routing import build_packet, render_text, save_packet  # noqa: E402


def resolve_audio(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    for base in (config.DEMO_AUDIO, config.CACHE / "demo16k", Path.cwd()):
        candidate = base / value
        if candidate.exists():
            return candidate
    raise SystemExit(f"\n[demo] Audio not found: {value}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Voice Access Infrastructure demo.")
    ap.add_argument("audio", nargs="?", help="path to an audio file")
    ap.add_argument("--text", help="skip ASR and compile this transcript directly")
    ap.add_argument("--model", default="sahara",
                    help="sahara | whisper_small | whisper_large_v3 | mms_yoruba_english")
    ap.add_argument("--language", default="pidgin",
                    help="yoruba | pidgin | igbo | hausa | english")
    ap.add_argument("--domain", default=None,
                    help="legal | financial | public_service (default: auto-classify)")
    ap.add_argument("--evidence", nargs="*", default=None,
                    help="names of evidence files the user supplied")
    ap.add_argument("--save", action="store_true", help="write the packet to data/cases/")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead")
    args = ap.parse_args()

    if not args.audio and not args.text:
        ap.error("give an audio file or --text")

    print("=" * 62)
    print("  VOICE ACCESS INFRASTRUCTURE")
    print("=" * 62)
    print(f"  {llm.describe_setup()}")

    transcript = args.text
    asr_latency = 0.0

    if not transcript:
        audio = resolve_audio(args.audio)
        print(f"  ASR: {args.model}  ({args.language})")
        print(f"  audio: {audio.name}")
        print("-" * 62)
        print("  transcribing...", flush=True)

        engine = build(args.model)
        started = time.monotonic()
        result = transcribe_file(engine, audio, args.language, audio.stem)
        asr_latency = time.monotonic() - started

        if result.error:
            raise SystemExit(f"\n[demo] ASR failed: {result.error}\n")
        transcript = result.text
        print(f"  done in {asr_latency:.1f}s")

    print("-" * 62)
    print("  STEP 1 - WE HEARD")
    print("-" * 62)
    for line in _wrap(transcript, 58):
        print(f'  "{line}"')
    print()

    print("  STEP 2 - COMPILING CASE...", flush=True)
    compiler = CaseCompiler()
    case = compiler.compile(transcript, args.domain)
    packet = build_packet(case, args.evidence)
    print()

    if args.json:
        import json
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    else:
        print(render_text(packet))

    print(f"\n  timing: ASR {asr_latency:.1f}s + compile {case.latency_s:.1f}s "
          f"= {asr_latency + case.latency_s:.1f}s total")

    if args.save:
        path = save_packet(packet)
        print(f"  saved: {path}")


def _wrap(text: str, width: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out or [""]


if __name__ == "__main__":
    main()
