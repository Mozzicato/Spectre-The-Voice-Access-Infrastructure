#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
M="data/manifests/demo.jsonl"
echo "### mms_yoruba_english (yoruba scenarios only, by design)"
python -m benchmark.run_asr --model mms_yoruba_english --manifest "$M" --retry-failed
echo "### whisper_small (local CPU)"
python -m benchmark.run_asr --model whisper_small --manifest "$M"
echo "### DONE"
