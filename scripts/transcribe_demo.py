"""Draft reference transcripts for our own recordings, then let a human fix them.

    python scripts/transcribe_demo.py --draft      # ASR pass -> editable file
    python scripts/transcribe_demo.py --apply      # corrected file -> manifest

The ground-truth transcript must be HUMAN. Using a model's output as its own reference
would score every model against Sahara rather than against the truth, and Sahara would
trivially "win". So the draft exists only to save typing: you correct it, and the
corrected text becomes the reference.

Workflow:
  1. drop recordings in data/demo/audio/
  2. --draft   writes data/demo/meta/transcripts.md with one editable block per clip
  3. edit that file, fixing every line to exactly what was said
  4. --apply   folds the corrected text into data/manifests/demo.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.asr import build, transcribe_file  # noqa: E402
from benchmark.load_dataset import build_demo  # noqa: E402

TRANSCRIPTS = config.DEMO_META / "transcripts.md"
BLOCK = re.compile(r"^##\s+(\S+)\s*$", re.MULTILINE)

HEADER = """\
# Reference transcripts

Fix every line below so it is EXACTLY what the speaker said, including Pidgin, Yoruba,
Igbo and Hausa words, and including the diacritics (ẹ ọ ṣ and tone marks) where you can.

These become the ground truth the models are scored against, so an error here becomes an
error in the benchmark. Do not tidy the speaker's grammar and do not translate.

Write numbers the way they were SPOKEN ("forty five thousand", not "45,000"). The scorer
canonicalises numbers itself, so spoken form is safe and keeps the reference honest.

When you are done:  python scripts/transcribe_demo.py --apply

---
"""


def draft(model: str, overwrite: bool) -> None:
    files = sorted(
        p for p in config.DEMO_AUDIO.iterdir()
        if p.suffix.lower() in {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}
    ) if config.DEMO_AUDIO.exists() else []

    if not files:
        raise SystemExit(
            f"\n[transcribe] No audio in {config.DEMO_AUDIO}\n"
            "  Record the scenarios in docs/RECORDING_GUIDE.md first.\n"
        )

    existing = _parse(TRANSCRIPTS) if TRANSCRIPTS.exists() and not overwrite else {}
    spec_path = config.DEMO_META / "scenarios.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}

    engine = build(model)
    blocks = [HEADER]
    print(f"[transcribe] drafting {len(files)} clip(s) with {model}")

    for path in files:
        stem = path.stem
        scenario = "_".join(stem.split("_")[:2])
        meta = spec.get(scenario, {})
        language = meta.get("language", "pidgin")

        if stem in existing and existing[stem].strip():
            text = existing[stem]
            print(f"  = {stem} (keeping existing)")
        else:
            result = transcribe_file(engine, path, language, stem)
            text = result.text or ""
            flag = f" [{result.error[:60]}]" if result.error else ""
            print(f"  + {stem} ({language}){flag}")

        blocks.append(
            f"## {stem}\n"
            f"<!-- {meta.get('language_pair', '?')} · "
            f"{meta.get('scenario_type', '?')} · CMI {meta.get('cmi_band', '?')} · "
            f"noise {meta.get('noise', '?')} -->\n\n{text}\n"
        )

    TRANSCRIPTS.parent.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS.write_text("\n".join(blocks), encoding="utf-8")
    print(f"\n[transcribe] wrote {TRANSCRIPTS}")
    print("  Now CORRECT every block by hand, then run --apply.")


def _parse(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    matches = list(BLOCK.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        out[m.group(1)] = body.strip()
    return out


def apply() -> None:
    corrected = _parse(TRANSCRIPTS)
    if not corrected:
        raise SystemExit(
            f"\n[transcribe] No transcripts found in {TRANSCRIPTS}\n"
            "  Run --draft first.\n"
        )

    manifest = config.DATA / "manifests" / "demo.jsonl"
    build_demo(config.DEMO_AUDIO, manifest)

    rows = [json.loads(line) for line in
            manifest.read_text(encoding="utf-8").splitlines() if line.strip()]

    filled = blank = 0
    for row in rows:
        text = corrected.get(row["audio_id"], "").strip()
        if text:
            row["reference"] = text
            filled += 1
        else:
            blank += 1

    with open(manifest, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n[transcribe] {filled} reference(s) applied to {manifest}")
    if blank:
        print(f"[transcribe] {blank} clip(s) still have NO reference and will be "
              f"skipped by the scorer.")
    print("\nNext:")
    print("  python -m benchmark.run_asr --model sahara --manifest data/manifests/demo.jsonl")
    print("  python -m benchmark.evaluate --manifest data/manifests/demo.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser(description="Draft and apply reference transcripts.")
    ap.add_argument("--draft", action="store_true", help="ASR pass -> editable file")
    ap.add_argument("--apply", action="store_true", help="corrected file -> manifest")
    ap.add_argument("--model", default="sahara", help="model used for the draft only")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-draft clips that already have text")
    args = ap.parse_args()

    if args.apply:
        apply()
    elif args.draft:
        draft(args.model, args.overwrite)
    else:
        ap.error("pass --draft or --apply")


if __name__ == "__main__":
    main()
