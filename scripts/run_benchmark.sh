#!/usr/bin/env bash
# Full Level-1 benchmark. Resumable: safe to re-run after any interruption.
#
#   bash scripts/run_benchmark.sh 100
#
set -u
cd "$(dirname "$0")/.."
N="${1:-100}"
M="data/manifests/afriswitch.jsonl"

echo "### [1/6] building manifest (${N}/language)"
python -m benchmark.load_dataset --source afriswitch \
  --languages yoruba pidgin igbo hausa --per-language "$N" --out "$M" || exit 1

echo "### [2/6] sahara (API)"
python -m benchmark.run_asr --model sahara --manifest "$M"

echo "### [3/6] whisper_large_v3 (API)"
python -m benchmark.run_asr --model whisper_large_v3 --manifest "$M"

echo "### [4/6] mms_yoruba_english (yoruba only, by design)"
python -m benchmark.run_asr --model mms_yoruba_english --manifest "$M"

echo "### [5/6] whisper_small (local CPU, slowest)"
python -m benchmark.run_asr --model whisper_small --manifest "$M"

echo "### [6/6] scoring"
python -m benchmark.evaluate --manifest "$M"
echo "### DONE"
