#!/usr/bin/env bash
# Resilient AfriSwitch pull. The HF CDN dropped connections repeatedly on this
# network, so each language is attempted separately and retried; already-cached
# clips are skipped, so every attempt makes forward progress.
set -u
cd "$(dirname "$0")/.."
N="${1:-25}"
for lang in yoruba pidgin igbo hausa; do
  for attempt in 1 2 3; do
    echo "### $lang (attempt $attempt)"
    if python -m benchmark.load_dataset --source afriswitch \
         --languages "$lang" --per-language "$N" \
         --out "data/manifests/_as_${lang}.jsonl"; then
      echo "### $lang OK"; break
    fi
    echo "### $lang failed, retrying"; sleep 5
  done
done
# merge whatever succeeded
python - <<'PY'
import json, pathlib
from app import config
out = config.DATA / "manifests" / "afriswitch.jsonl"
rows = []
for p in sorted((config.DATA / "manifests").glob("_as_*.jsonl")):
    rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
print(f"[merge] {len(rows)} rows -> {out}")
from collections import Counter
print("[merge] by language:", dict(Counter(r["language"] for r in rows)))
PY
