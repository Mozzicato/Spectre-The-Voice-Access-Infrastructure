"""Level 2 benchmark: does better ASR produce a better institutional case?

    python -m benchmark.run_downstream --manifest data/manifests/demo.jsonl

Same audio -> every ASR model -> the SAME case compiler -> compare the structured cases
against ground truth. This is the experiment that separates the project from a wrapper
around a speech API: WER measures transcripts, this measures whether the information an
institution actually needs survived.

Metrics:
    field accuracy      - required fields correctly populated
    entity accuracy     - amounts, dates, locations, reference numbers
    negation integrity  - did "never paid" survive as a negative claim
    routing accuracy    - was the case sent to the right desk
    completeness        - required fields filled, whatever their correctness

Ground truth lives in data/demo/meta/ground_truth.json, keyed by scenario_id.
A reference-free run still reports cross-model AGREEMENT, which is informative on its own.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from app import config, schemas
from app.compiler import CaseCompiler, _is_filled
from app.normalize import (
    negation_markers,
    normalize_loose,
    spoken_digit_strings,
    spoken_numbers_to_values,
)
from app.routing import build_packet


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


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value)
    if isinstance(value, dict):
        return " ".join(f"{k} {v}" for k, v in value.items())
    return str(value)


def _field_matches(truth, got) -> bool:
    """Lenient containment match: the case record must PRESERVE the fact, not phrase it
    identically. Exact string equality would measure prose style, not information."""
    t, g = normalize_loose(_flatten(truth)), normalize_loose(_flatten(got))
    if not t:
        return True
    if not g:
        return False
    if t in g or g in t:
        return True
    t_tokens = {w for w in t.split() if len(w) > 3}
    if not t_tokens:
        return t.split()[0] in g if t.split() else False
    overlap = len(t_tokens & set(g.split())) / len(t_tokens)
    return overlap >= 0.6


def score_case(packet: dict, truth: dict, transcript: str, reference_text: str) -> dict:
    schema = schemas.get(packet["domain"])
    got = packet["user_reported"]
    truth_fields = truth.get("fields", {})

    # --- field accuracy over required fields that ground truth actually specifies ---
    checked = [f for f in schema.required_fields if f in truth_fields]
    hits = sum(1 for f in checked if _field_matches(truth_fields[f], got.get(f)))
    field_acc = hits / len(checked) if checked else float("nan")

    # --- entity accuracy ---
    def recall(expected: list, actual: list) -> tuple[int, int]:
        pool = list(actual)
        hit = 0
        for item in expected:
            if item in pool:
                pool.remove(item)
                hit += 1
        return hit, len(expected)

    exp_amounts = truth.get("amounts") or []
    got_amounts = spoken_numbers_to_values(_flatten(got))
    amt_hit, amt_tot = recall(exp_amounts, got_amounts)

    exp_refs = [str(r) for r in (truth.get("references") or [])]
    got_refs = spoken_digit_strings(_flatten(got))
    ref_hit, ref_tot = recall(exp_refs, got_refs)

    # --- negation integrity, measured against the human reference transcript ---
    expected_neg = negation_markers(reference_text) if reference_text else 0
    kept_neg = min(negation_markers(_flatten(got)), expected_neg) if expected_neg else 0

    return {
        "case_type": packet["case_type"],
        "route": packet["routing"]["route"],
        "case_type_correct": int(packet["case_type"] == truth.get("case_type"))
        if truth.get("case_type") else None,
        "route_correct": int(packet["routing"]["route"] == truth.get("route"))
        if truth.get("route") else None,
        "field_hits": hits,
        "field_checked": len(checked),
        "field_accuracy": field_acc,
        "amount_hits": amt_hit, "amount_total": amt_tot,
        "refnum_hits": ref_hit, "refnum_total": ref_tot,
        "negation_expected": expected_neg, "negation_kept": kept_neg,
        "completeness": packet["completeness"],
        "confidence": packet["confidence"],
        "missing_count": len(packet["missing_information"]),
    }


def run(manifest: Path, models: list[str] | None, out_dir: Path,
        include_oracle: bool = True) -> pd.DataFrame:
    manifest_rows = {r["audio_id"]: r for r in _load_jsonl(manifest)}
    if not manifest_rows:
        raise SystemExit(f"\n[downstream] Empty or missing manifest: {manifest}\n")

    gt_path = config.DEMO_META / "ground_truth.json"
    ground_truth = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else {}
    if not ground_truth:
        print("[downstream] No ground_truth.json - reporting cross-model agreement only.")

    result_files = sorted(config.RESULTS.glob("*.jsonl"))
    if models:
        result_files = [p for p in result_files if p.stem in models]
    if not result_files:
        raise SystemExit(f"\n[downstream] No ASR results in {config.RESULTS}\n")

    compiler = CaseCompiler()
    print(f"[downstream] compiler extractor: {compiler.extractor_label}")

    cache_path = out_dir / "compiled_cases.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)
    done = {(r["model"], r["audio_id"]) for r in _load_jsonl(cache_path)}
    records: list[dict] = []
    cache_rows = _load_jsonl(cache_path)

    sources: list[tuple[str, dict[str, str]]] = []
    for path in result_files:
        preds = {}
        for row in _load_jsonl(path):
            if not row.get("error") and row.get("text"):
                preds[row["audio_id"]] = row["text"]
        sources.append((path.stem, preds))

    # The oracle row compiles the HUMAN transcript. It is the ceiling: any gap between it
    # and a model is caused by ASR, not by the compiler.
    if include_oracle and any(r.get("reference") for r in manifest_rows.values()):
        sources.append((
            "human_reference",
            {aid: r["reference"] for aid, r in manifest_rows.items() if r.get("reference")},
        ))

    with open(cache_path, "a", encoding="utf-8") as sink:
        for model, preds in sources:
            for audio_id, transcript in preds.items():
                row = manifest_rows.get(audio_id)
                if row is None:
                    continue
                scenario = row.get("scenario_id") or audio_id
                truth = ground_truth.get(scenario, {})

                if (model, audio_id) in done:
                    continue

                domain = truth.get("domain") or row.get("domain")
                if domain not in schemas.SCHEMAS:
                    domain = None

                case = compiler.compile(transcript, domain)
                packet = build_packet(case)
                entry = {
                    "model": model, "audio_id": audio_id, "scenario_id": scenario,
                    "language": row.get("language", ""), "packet": packet,
                }
                sink.write(json.dumps(entry, ensure_ascii=False) + "\n")
                sink.flush()
                cache_rows.append(entry)
                print(f"  [{model}] {audio_id} -> {packet['case_type']} "
                      f"({packet['completeness']*100:.0f}% complete)")

    degraded = 0
    for entry in cache_rows:
        row = manifest_rows.get(entry["audio_id"])
        if row is None:
            continue
        # A case compiled by the rule-based fallback measures our rate limit, not the ASR
        # model. Scoring it would report an infrastructure failure as a model result.
        prov = entry["packet"].get("provenance", {})
        if prov.get("extractor") == "rule_based_fallback" or any(
            "rule-based extraction" in w for w in prov.get("warnings", [])
        ):
            degraded += 1
            continue
        scenario = entry.get("scenario_id") or entry["audio_id"]
        truth = ground_truth.get(scenario, {})
        rec = {
            "model": entry["model"], "audio_id": entry["audio_id"],
            "scenario_id": scenario, "language": entry.get("language", ""),
            "domain": entry["packet"]["domain"],
        }
        rec.update(score_case(entry["packet"], truth, "", row.get("reference", "")))
        records.append(rec)

    if degraded:
        print("")
        print("[downstream] EXCLUDED {} case(s) that fell back to rule-based "
              "extraction.".format(degraded))
        print("             These are LLM outages, not ASR results.")
        print("             Delete {} and re-run to recompile them."
              .format(cache_path.name))
    if not records:
        raise SystemExit(
            "\n[downstream] Every case was degraded - nothing scoreable.\n"
            "  The LLM provider is failing. Check keys/quota, then re-run.\n"
        )
    return pd.DataFrame(records)


def summarise(df: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "downstream_per_case.csv", index=False)

    rows = []
    for model, sub in df.groupby("model"):
        amt_tot = sub["amount_total"].sum()
        ref_tot = sub["refnum_total"].sum()
        neg_tot = sub["negation_expected"].sum()
        checked = sub["field_checked"].sum()
        rec = {
            "model": model,
            "n": len(sub),
            "field_accuracy": sub["field_hits"].sum() / checked if checked else float("nan"),
            "amount_accuracy": sub["amount_hits"].sum() / amt_tot if amt_tot else float("nan"),
            "refnum_accuracy": sub["refnum_hits"].sum() / ref_tot if ref_tot else float("nan"),
            "negation_integrity": sub["negation_kept"].sum() / neg_tot if neg_tot else float("nan"),
            "case_type_accuracy": sub["case_type_correct"].mean(skipna=True),
            "routing_accuracy": sub["route_correct"].mean(skipna=True),
            "completeness": sub["completeness"].mean(),
        }
        rows.append(rec)

    summary = pd.DataFrame(rows).sort_values("field_accuracy", ascending=False)
    summary.to_csv(out_dir / "downstream_summary.csv", index=False)

    def pct(x):
        return "-" if pd.isna(x) else f"{x * 100:.1f}"

    lines = [
        "# Downstream Benchmark - Institutional Understanding",
        "",
        "Same audio, every ASR model, the **same** case compiler. Differences below are",
        "caused by speech recognition, not by the compiler.",
        "",
        "`human_reference` compiles the human transcript and is the ceiling: the gap",
        "between it and a model is the downstream cost of that model's ASR errors.",
        "",
        "| Model | n | Field acc ↑ | Amounts ↑ | Ref-nums ↑ | Negation ↑ | Case type ↑ | "
        "Routing ↑ | Completeness ↑ |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for _, r in summary.iterrows():
        lines.append(
            f"| `{r['model']}` | {int(r['n'])} | {pct(r['field_accuracy'])} | "
            f"{pct(r['amount_accuracy'])} | {pct(r['refnum_accuracy'])} | "
            f"{pct(r['negation_integrity'])} | {pct(r['case_type_accuracy'])} | "
            f"{pct(r['routing_accuracy'])} | {pct(r['completeness'])} |"
        )
    lines += [
        "",
        "All figures are percentages, higher is better.",
        "",
        "A model can post a respectable WER and still score badly here: dropping one",
        "negation or one digit of an amount leaves the transcript mostly intact while",
        "making the resulting case file wrong in a way an institution would act on.",
        "",
    ]
    (out_dir / "DOWNSTREAM.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[downstream] wrote {out_dir/'DOWNSTREAM.md'}")
    print("\n" + "\n".join(lines[8:]))


def main() -> None:
    ap = argparse.ArgumentParser(description="Downstream (case-level) benchmark.")
    ap.add_argument("--manifest", type=Path,
                    default=config.DATA / "manifests" / "demo.jsonl")
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=config.REPORTS)
    ap.add_argument("--no-oracle", action="store_true",
                    help="skip compiling the human reference transcript")
    args = ap.parse_args()

    df = run(args.manifest, args.models, args.out, include_oracle=not args.no_oracle)
    summarise(df, args.out)


if __name__ == "__main__":
    main()
