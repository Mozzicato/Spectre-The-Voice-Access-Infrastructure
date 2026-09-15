"""Build an evaluation manifest.

Everything downstream reads a manifest (JSONL), never a dataset object. That keeps the
benchmark runnable from AfriSwitch, from our own recordings, or from any future corpus
without touching the runners.

Manifest row:
    {audio_id, audio_path, language, reference, cmi, num_switch_points, source, domain}

Memory: audio is streamed one clip at a time and written to disk immediately. The
dataset is never materialised as a list, which is what keeps this inside 8 GB.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import config


def _write_manifest(rows: list[dict], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[manifest] {len(rows)} rows -> {out}")
    return out


def _first_present(row: dict, *names, default=None):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def build_afriswitch(languages: list[str], per_language: int, out: Path) -> Path:
    """Stream AfriSwitch, decode audio to 16 kHz mono WAV, emit a manifest."""
    import soundfile as sf
    from datasets import load_dataset, get_dataset_config_names

    token = config.HF_TOKEN
    if not token:
        raise SystemExit(
            "\n[load_dataset] HF_TOKEN is not set.\n"
            "  AfriSwitch is a manually gated dataset: approval alone is not enough,\n"
            "  the download still has to be authenticated.\n"
            "  1. Create a read token at https://huggingface.co/settings/tokens\n"
            "  2. Add it to .env as  HF_TOKEN=hf_...\n"
        )

    try:
        available = get_dataset_config_names(config.AFRISWITCH_REPO, token=token)
    except Exception as exc:
        raise SystemExit(
            f"\n[load_dataset] Could not list AfriSwitch configs: {exc}\n"
            "  If this is a 401/403, the access request at\n"
            f"  https://huggingface.co/datasets/{config.AFRISWITCH_REPO}\n"
            "  has not been approved for this token's account yet.\n"
        )
    print(f"[afriswitch] available configs: {available}")

    audio_dir = config.CACHE / "afriswitch"
    audio_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for lang in languages:
        cfg = next(
            (c for c in available if c.lower() == lang.lower()
             or lang.lower() in c.lower()),
            None,
        )
        if cfg is None:
            print(f"[afriswitch] no config matches {lang!r}, skipping", file=sys.stderr)
            continue

        print(f"[afriswitch] streaming {cfg} (target {per_language} clips)")
        ds = load_dataset(
            config.AFRISWITCH_REPO, cfg, split="test", streaming=True, token=token
        )

        taken = 0
        for i, item in enumerate(ds):
            if taken >= per_language:
                break
            reference = _first_present(
                item, "transcript", "transcription", "text", "sentence", default=""
            )
            audio = item.get("audio")
            if not reference or not audio:
                continue

            audio_id = f"afriswitch_{cfg}_{i:05d}"
            dest = audio_dir / f"{audio_id}.wav"
            if not dest.exists():
                try:
                    sf.write(dest, audio["array"], audio["sampling_rate"], subtype="PCM_16")
                except Exception as exc:
                    print(f"  ! {audio_id}: {exc}", file=sys.stderr)
                    continue

            rows.append({
                "audio_id": audio_id,
                "audio_path": str(dest),
                "language": lang.lower(),
                "reference": str(reference).strip(),
                "cmi": _first_present(item, "cmi", "code_mixing_index", "CMI"),
                "num_switch_points": _first_present(
                    item, "num_switch_points", "switch_points", "n_switches"
                ),
                "source": "afriswitch",
                "domain": "general",
            })
            taken += 1
            if taken % 25 == 0:
                print(f"  {cfg}: {taken}/{per_language}")

        print(f"[afriswitch] {cfg}: {taken} clips")

    return _write_manifest(rows, out)


def build_demo(audio_dir: Path, out: Path) -> Path:
    """Manifest for our own recordings, parsed from the filename convention.

        {domain}_{nn}_{speaker}.wav   e.g. legal_01_s1.wav

    References are filled in later by scripts/transcribe_demo.py; rows are emitted with
    an empty reference so the ASR runners can work while transcription is still pending.
    """
    from app.asr import to_wav16k_mono

    spec_path = config.DEMO_META / "scenarios.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}

    converted_dir = config.CACHE / "demo16k"
    converted_dir.mkdir(parents=True, exist_ok=True)

    exts = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".mp4"}
    files = sorted(p for p in audio_dir.iterdir() if p.suffix.lower() in exts)
    if not files:
        raise SystemExit(f"\n[load_dataset] No audio found in {audio_dir}\n")

    rows = []
    for path in files:
        stem = path.stem
        parts = stem.split("_")
        scenario_id = "_".join(parts[:2]) if len(parts) >= 2 else stem
        speaker = parts[2] if len(parts) >= 3 else "s1"
        meta = spec.get(scenario_id, {})

        dest = converted_dir / f"{stem}.wav"
        if not dest.exists():
            to_wav16k_mono(path, dest)

        rows.append({
            "audio_id": stem,
            "audio_path": str(dest),
            "language": meta.get("language", "pidgin"),
            "reference": meta.get("reference", ""),
            "cmi": meta.get("cmi_band"),
            "num_switch_points": None,
            "source": "demo",
            "domain": meta.get("domain", scenario_id.split("_")[0]),
            "scenario_id": scenario_id,
            "speaker": speaker,
            "noise": meta.get("noise", "quiet"),
        })

    return _write_manifest(rows, out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an ASR evaluation manifest.")
    ap.add_argument("--source", choices=["afriswitch", "demo"], default="afriswitch")
    ap.add_argument("--languages", nargs="+", default=config.PRIMARY_LANGS)
    ap.add_argument("--per-language", type=int, default=100)
    ap.add_argument("--audio-dir", type=Path, default=config.DEMO_AUDIO)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    out = args.out or (config.DATA / "manifests" / f"{args.source}.jsonl")
    if args.source == "afriswitch":
        build_afriswitch(args.languages, args.per_language, out)
    else:
        build_demo(args.audio_dir, out)


if __name__ == "__main__":
    main()
