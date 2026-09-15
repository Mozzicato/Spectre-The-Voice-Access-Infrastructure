"""Run one ASR engine over a manifest. Resumable, throttled, crash-safe.

    python -m benchmark.run_asr --model sahara --manifest data/manifests/afriswitch.jsonl

If it dies at clip 287 of 400, rerunning picks up at 288. Results are appended to
results/{model}.jsonl and flushed per row, so a crash costs at most one clip.

INFERENCE and EVALUATION are deliberately separate programs. Expensive transcription is
never re-run to compute an extra metric.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app import config
from app.asr import ASRResult, build


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(
            f"\n[run_asr] Manifest not found: {path}\n"
            "  Build one first:  python -m benchmark.load_dataset --source demo\n"
        )
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def already_done(results_path: Path) -> set[str]:
    """IDs already transcribed WITHOUT error. Failures are retried on the next run."""
    if not results_path.exists():
        return set()
    done = set()
    with open(results_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn final line from a hard crash
            if not row.get("error") and row.get("text"):
                done.add(row["audio_id"])
    return done


def run(model: str, manifest: Path, workers: int, limit: int | None,
        languages: list[str] | None, retry_failed: bool) -> Path:
    rows = read_manifest(manifest)

    if languages:
        wanted = {l.lower() for l in languages}
        rows = [r for r in rows if r.get("language", "").lower() in wanted]

    engine = build(model)

    # A language-specialised model is only scored where it is designed to work.
    supported = getattr(engine, "supported_languages", None)
    if supported:
        before = len(rows)
        rows = [r for r in rows if r.get("language", "").lower() in supported]
        if before != len(rows):
            print(f"[{model}] restricted to {sorted(supported)}: "
                  f"{len(rows)}/{before} clips (the rest would be an unfair comparison)")

    results_path = config.RESULTS / f"{model}.jsonl"
    done = set() if retry_failed and not results_path.exists() else already_done(results_path)
    todo = [r for r in rows if r["audio_id"] not in done]

    if limit:
        todo = todo[:limit]

    print(f"[{model}] manifest={len(rows)}  done={len(done)}  todo={len(todo)}  workers={workers}")
    if not todo:
        print(f"[{model}] nothing to do.")
        return results_path

    lock = threading.Lock()
    counter = {"n": 0, "err": 0}
    started = time.monotonic()

    def work(row: dict) -> ASRResult:
        return engine.transcribe(
            Path(row["audio_path"]), row.get("language", "en"), row["audio_id"]
        )

    with open(results_path, "a", encoding="utf-8") as sink:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, r): r for r in todo}
            for fut in as_completed(futures):
                row = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    result = ASRResult(
                        row["audio_id"], model, "", 0.0,
                        row.get("language", ""), error=f"{type(exc).__name__}: {exc}",
                    )

                with lock:
                    sink.write(result.to_json() + "\n")
                    sink.flush()  # crash-safety beats throughput here
                    counter["n"] += 1
                    if result.error:
                        counter["err"] += 1
                    n = counter["n"]

                if result.error:
                    print(f"  ! {result.audio_id}: {result.error[:110]}", file=sys.stderr)
                if n % 10 == 0 or n == len(todo):
                    rate = n / max(time.monotonic() - started, 1e-6)
                    eta = (len(todo) - n) / max(rate, 1e-6)
                    print(f"  [{model}] {n}/{len(todo)}  "
                          f"{rate*60:.1f}/min  eta {eta/60:.1f} min  errors={counter['err']}")

    elapsed = time.monotonic() - started
    print(f"[{model}] done: {counter['n']} clips in {elapsed/60:.1f} min "
          f"({counter['err']} errors) -> {results_path}")
    return results_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an ASR engine over a manifest.")
    ap.add_argument("--model", required=True,
                    help="sahara | whisper_small | mms_yoruba_english")
    ap.add_argument("--manifest", type=Path,
                    default=config.DATA / "manifests" / "afriswitch.jsonl")
    ap.add_argument("--workers", type=int, default=None,
                    help="default: 6 for the API, 1 for local CPU models")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--languages", nargs="*", default=None)
    ap.add_argument("--retry-failed", action="store_true",
                    help="retry rows that previously errored")
    args = ap.parse_args()

    # Local models are CPU- and RAM-bound: parallelism makes them slower and risks the
    # 8 GB ceiling. The API is latency-bound, so concurrency is a large win there.
    if args.workers is None:
        args.workers = 6 if args.model == "sahara" else 1

    run(args.model, args.manifest, args.workers, args.limit,
        args.languages, args.retry_failed)


if __name__ == "__main__":
    main()
