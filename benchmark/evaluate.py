"""Score ASR results. Pure evaluation: no inference happens here.

    python -m benchmark.evaluate --manifest data/manifests/afriswitch.jsonl

Produces, per model:
  * WER / CER under three normalization schemes, with bootstrap confidence intervals
  * breakdowns by language, code-mixing band and noise condition
  * information-preservation metrics: amounts, reference numbers, negations

The last group is the point of the project. WER treats every word error alike; a dropped
"never" or a mangled amount destroys a case file while a wrong filler word does not.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import jiwer
import pandas as pd

from app import config
from app.normalize import (
    SCHEMES,
    negation_markers,
    spoken_digit_strings,
    spoken_numbers_to_values,
)

BOOTSTRAP_N = 1000
SEED = 20260915


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def _dedupe(rows: list[dict]) -> dict[str, dict]:
    """Last write wins, so a re-run after a fix supersedes the earlier attempt."""
    out: dict[str, dict] = {}
    for row in rows:
        out[row["audio_id"]] = row
    return out


def _cmi_band(value) -> str:
    """AfriSwitch ships a code-mixing index; bucket it so results stay readable.

    CMI is reported on either a 0-1 or 0-100 scale depending on the release, so the
    scale is detected rather than assumed.
    """
    if value in (None, ""):
        return "unknown"
    try:
        cmi = float(value)
    except (TypeError, ValueError):
        return str(value)
    if cmi > 1.0:
        cmi /= 100.0
    if cmi < 0.15:
        return "low"
    if cmi < 0.35:
        return "medium"
    return "high"


def _counts(ref: str, hyp: str) -> tuple[int, int, int, int]:
    """Word-level (errors, ref_len) and char-level (errors, ref_len)."""
    if not ref.strip():
        return 0, 0, 0, 0
    w = jiwer.process_words([ref], [hyp if hyp.strip() else " "])
    c = jiwer.process_characters([ref], [hyp if hyp.strip() else " "])
    w_err = w.substitutions + w.deletions + w.insertions
    c_err = c.substitutions + c.deletions + c.insertions
    return w_err, w.substitutions + w.deletions + w.hits, c_err, \
        c.substitutions + c.deletions + c.hits


def _bootstrap_ci(pairs: list[tuple[int, int]], n: int = BOOTSTRAP_N) -> tuple[float, float]:
    """Percentile bootstrap over utterances for a corpus-level ratio metric.

    With 100-200 clips a two-point WER gap is usually noise. Reporting an interval is
    what separates a benchmark from a vibe.
    """
    if not pairs:
        return (float("nan"), float("nan"))
    rng = random.Random(SEED)
    k = len(pairs)
    samples = []
    for _ in range(n):
        err = den = 0
        for _ in range(k):
            e, d = pairs[rng.randrange(k)]
            err += e
            den += d
        if den:
            samples.append(err / den)
    if not samples:
        return (float("nan"), float("nan"))
    samples.sort()
    return (samples[int(0.025 * len(samples))], samples[int(0.975 * len(samples))])


def _ratio(pairs: list[tuple[int, int]]) -> float:
    err = sum(e for e, _ in pairs)
    den = sum(d for _, d in pairs)
    return err / den if den else float("nan")


def _set_recall(ref_items, hyp_items) -> tuple[int, int]:
    """How many reference items survived into the hypothesis (hits, total)."""
    ref_list = list(ref_items)
    if not ref_list:
        return 0, 0
    pool = list(hyp_items)
    hits = 0
    for item in ref_list:
        if item in pool:
            pool.remove(item)
            hits += 1
    return hits, len(ref_list)


def evaluate(manifest: Path, models: list[str] | None) -> pd.DataFrame:
    manifest_rows = {r["audio_id"]: r for r in _load_jsonl(manifest)}
    if not manifest_rows:
        raise SystemExit(f"\n[evaluate] Empty or missing manifest: {manifest}\n")

    result_files = sorted(config.RESULTS.glob("*.jsonl"))
    if models:
        result_files = [p for p in result_files if p.stem in models]
    if not result_files:
        raise SystemExit(
            f"\n[evaluate] No results in {config.RESULTS}\n"
            "  Run:  python -m benchmark.run_asr --model sahara --manifest <manifest>\n"
        )

    records: list[dict] = []

    for path in result_files:
        model = path.stem
        preds = _dedupe(_load_jsonl(path))
        scored = skipped_no_ref = errored = 0

        for audio_id, pred in preds.items():
            row = manifest_rows.get(audio_id)
            if row is None:
                continue
            if pred.get("error"):
                errored += 1
                continue
            reference = (row.get("reference") or "").strip()
            if not reference:
                skipped_no_ref += 1
                continue

            hypothesis = (pred.get("text") or "").strip()
            rec: dict = {
                "model": model,
                "audio_id": audio_id,
                "language": (row.get("language") or "").lower(),
                "cmi_band": _cmi_band(row.get("cmi")),
                "noise": row.get("noise", "unknown"),
                "domain": row.get("domain", "general"),
                "latency_s": pred.get("latency_s"),
                "audio_seconds": (pred.get("meta") or {}).get("audio_seconds"),
            }

            for scheme, fn in SCHEMES.items():
                ref_n, hyp_n = fn(reference), fn(hypothesis)
                w_err, w_len, c_err, c_len = _counts(ref_n, hyp_n)
                rec[f"werr_{scheme}"] = w_err
                rec[f"wlen_{scheme}"] = w_len
                rec[f"cerr_{scheme}"] = c_err
                rec[f"clen_{scheme}"] = c_len

            # --- information preservation ---
            amt_hit, amt_tot = _set_recall(
                spoken_numbers_to_values(reference), spoken_numbers_to_values(hypothesis)
            )
            ref_hit, ref_tot = _set_recall(
                spoken_digit_strings(reference), spoken_digit_strings(hypothesis)
            )
            ref_neg, hyp_neg = negation_markers(reference), negation_markers(hypothesis)

            rec.update({
                "amount_hits": amt_hit, "amount_total": amt_tot,
                "refnum_hits": ref_hit, "refnum_total": ref_tot,
                "negation_ref": ref_neg,
                "negation_kept": min(hyp_neg, ref_neg),
            })
            records.append(rec)
            scored += 1

        print(f"[evaluate] {model}: scored={scored}  errored={errored}  "
              f"no_reference={skipped_no_ref}")

    if not records:
        raise SystemExit(
            "\n[evaluate] Nothing scoreable.\n"
            "  Every joined row was missing a reference transcript.\n"
            "  For demo audio, fill references via scripts/transcribe_demo.py first.\n"
        )

    return pd.DataFrame(records)


def _agg(df: pd.DataFrame, group: list[str] | None) -> pd.DataFrame:
    keys = ["model"] + (group or [])
    out = []
    for key, sub in df.groupby(keys, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        rec = dict(zip(keys, key))
        rec["n"] = len(sub)

        for scheme in SCHEMES:
            wpairs = list(zip(sub[f"werr_{scheme}"], sub[f"wlen_{scheme}"]))
            cpairs = list(zip(sub[f"cerr_{scheme}"], sub[f"clen_{scheme}"]))
            rec[f"WER_{scheme}"] = _ratio(wpairs)
            rec[f"CER_{scheme}"] = _ratio(cpairs)
            if group is None:
                lo, hi = _bootstrap_ci(wpairs)
                rec[f"WER_{scheme}_lo"] = lo
                rec[f"WER_{scheme}_hi"] = hi

        amt_tot = sub["amount_total"].sum()
        ref_tot = sub["refnum_total"].sum()
        neg_tot = sub["negation_ref"].sum()
        rec["amount_recall"] = sub["amount_hits"].sum() / amt_tot if amt_tot else float("nan")
        rec["refnum_recall"] = sub["refnum_hits"].sum() / ref_tot if ref_tot else float("nan")
        rec["negation_recall"] = sub["negation_kept"].sum() / neg_tot if neg_tot else float("nan")

        lat = sub["latency_s"].dropna()
        rec["latency_median_s"] = float(lat.median()) if len(lat) else float("nan")
        secs = sub["audio_seconds"].dropna()
        if len(secs) and len(lat):
            total_audio = float(secs.sum())
            rec["rtf"] = float(lat.sum()) / total_audio if total_audio else float("nan")
        else:
            rec["rtf"] = float("nan")
        out.append(rec)

    return pd.DataFrame(out).sort_values(keys).reset_index(drop=True)


def _pct(x) -> str:
    return "-" if pd.isna(x) else f"{x * 100:.1f}"


def write_report(df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "per_utterance.csv", index=False)

    overall = _agg(df, None)
    overall.to_csv(out_dir / "overall.csv", index=False)

    lines: list[str] = [
        "# ASR Benchmark Results",
        "",
        "Generated by `benchmark/evaluate.py`. Every number is computed from cached",
        "model outputs in `benchmark/results/*.jsonl` and is reproducible from them.",
        "",
        "## Normalization schemes",
        "",
        "| Scheme | What it does | Why |",
        "|---|---|---|",
        "| `strict` | lowercase, punctuation stripped, **diacritics preserved** | "
        "rewards correct Yoruba orthography |",
        "| `loose` | additionally strips sub-dots and tone marks | "
        "segmental accuracy only |",
        "| `numeric` | `loose` + numbers canonicalised to digits | "
        "stops formatting differences counting as recognition errors |",
        "",
        "All three are reported because the choice materially changes the ranking.",
        "",
        "## Overall",
        "",
        "| Model | n | WER strict | WER loose | WER numeric (95% CI) | CER loose | "
        "Amounts ↑ | Ref-nums ↑ | Negation ↑ | Median latency | RTF |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]

    for _, r in overall.iterrows():
        ci = ""
        if not pd.isna(r.get("WER_numeric_lo", float("nan"))):
            ci = f" ({_pct(r['WER_numeric_lo'])}–{_pct(r['WER_numeric_hi'])})"
        lat = "-" if pd.isna(r["latency_median_s"]) else f"{r['latency_median_s']:.2f}s"
        rtf = "-" if pd.isna(r["rtf"]) else f"{r['rtf']:.2f}×"
        lines.append(
            f"| `{r['model']}` | {int(r['n'])} | {_pct(r['WER_strict'])} | "
            f"{_pct(r['WER_loose'])} | {_pct(r['WER_numeric'])}{ci} | "
            f"{_pct(r['CER_loose'])} | {_pct(r['amount_recall'])} | "
            f"{_pct(r['refnum_recall'])} | {_pct(r['negation_recall'])} | {lat} | {rtf} |"
        )

    lines += [
        "",
        "WER/CER are percentages, lower is better. Amounts, reference numbers and",
        "negation are recall percentages, **higher is better** — they measure whether the",
        "information an institution actually needs survived transcription.",
        "",
    ]

    for label, group in (("language", ["language"]),
                         ("code-mixing band", ["cmi_band"]),
                         ("noise condition", ["noise"])):
        sub = _agg(df, group)
        if len(sub) <= 1 and sub[group[0]].isin(["unknown"]).all():
            continue
        col = group[0]
        lines += [
            f"## By {label}",
            "",
            f"| Model | {label.title()} | n | WER loose | WER numeric | CER loose | "
            "Amounts ↑ | Negation ↑ |",
            "|---|---|--:|--:|--:|--:|--:|--:|",
        ]
        for _, r in sub.iterrows():
            lines.append(
                f"| `{r['model']}` | {r[col]} | {int(r['n'])} | {_pct(r['WER_loose'])} | "
                f"{_pct(r['WER_numeric'])} | {_pct(r['CER_loose'])} | "
                f"{_pct(r['amount_recall'])} | {_pct(r['negation_recall'])} |"
            )
        lines.append("")
        sub.to_csv(out_dir / f"by_{col}.csv", index=False)

    (out_dir / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[evaluate] wrote {out_dir/'RESULTS.md'} and CSVs")
    print("\n" + "\n".join(lines[:22]))


def main() -> None:
    ap = argparse.ArgumentParser(description="Score cached ASR results.")
    ap.add_argument("--manifest", type=Path,
                    default=config.DATA / "manifests" / "afriswitch.jsonl")
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=config.REPORTS)
    args = ap.parse_args()

    df = evaluate(args.manifest, args.models)
    write_report(df, args.out)


if __name__ == "__main__":
    main()
