#!/usr/bin/env bash
# Regenerate every report from cached ASR outputs, then verify the measurement layer.
# Safe to re-run: it recomputes, it never re-transcribes.
set -u
cd "$(dirname "$0")/.."
M="data/manifests/demo.jsonl"

echo "### model coverage"
python - <<'PY'
import json
from pathlib import Path
man = {json.loads(l)["audio_id"] for l in open("data/manifests/demo.jsonl", encoding="utf-8")}
for p in sorted(Path("benchmark/results").glob("*.jsonl")):
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r["audio_id"] in man]
    ok = sum(1 for r in rows if not r.get("error") and r.get("text"))
    print(f"  {p.stem:24} {ok}/{len(man)}")
PY

echo
echo "### Level 2 - institutional understanding"
python -m benchmark.run_downstream --manifest "$M" --no-oracle --out reports/downstream

echo
echo "### per-scenario information preservation"
python scripts/failure_analysis.py

echo
echo "### self-test"
python scripts/selftest.py
echo "### DONE"
