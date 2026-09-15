# Voice Access Infrastructure

**A voice-first translation layer between human narratives and institutional workflows.**

People don't communicate in forms. They tell stories. Institutions require structured
cases, complaints and disputes. Between the two sits a gap that excludes anyone who
speaks naturally — which, across Africa, means code-switching.

This system converts natural African code-switched speech into structured institutional
cases, preserving entities, events, evidence and — critically — **what is still missing**.

We demonstrate the same infrastructure across three verticals:

| Compiler | Turns speech into |
|---|---|
| ⚖️ **Legal Case Compiler** | tenancy, employment and consumer disputes |
| 🏦 **Financial Dispute Compiler** | failed transfers, unauthorised debits, ATM disputes |
| 🏛️ **Citizen Complaint Compiler** | streetlights, water, roads, electricity, sanitation |

One voice layer. One compiler engine. Three schemas.

---

## The research question

> **Does code-switch-aware speech recognition preserve more of the information required
> to turn African users' natural speech into actionable institutional cases?**

This is not a WER leaderboard. A speech error is not equally harmful in every position:

```
"₦45,000"          ->  "₦4,500"        a claim becomes wrong by a factor of ten
"He never paid me" ->  "He paid me"    the case inverts
"reference 0987654321" -> one digit off   the dispute cannot be located at all
```

Word Error Rate scores all three of those the same as a mangled filler word. For
institutional workflows, **information preservation matters more than pretty
transcripts** — so we measure both, at two levels.

---

## Architecture

```
                         USER
                          │ natural code-switched speech
                          ▼
              ┌───────────────────────┐
              │      ASR LAYER        │   swappable, benchmarked
              │  Sahara v2.5 (API)    │
              │  Whisper large-v3     │
              │  Whisper small (CPU)  │
              │  MMS-300M Yo-En (CPU) │
              └───────────┬───────────┘
                          ▼  transcript
              ┌───────────────────────┐
              │   SEMANTIC ENGINE     │   entities · events · dates
              │  schema-guided        │   amounts · locations · evidence
              │  structured extraction│   negation · relationships
              └───────────┬───────────┘
                          ▼  story object
              ┌───────────────────────┐
              │   CASE CLASSIFIER     │
              └───────────┬───────────┘
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
          LEGAL       FINANCIAL    PUBLIC SERVICE
          schema        schema         schema
            └─────────────┼─────────────┘
                          ▼
                 MISSING INFORMATION
                          ▼
                  ADAPTIVE QUESTIONS     ← voice form-filling, without the form
                          ▼
                    COMPLETE CASE
                          ▼
                  ROUTING / CASE PACKET
```

**Sahara is not the product.** It is the speech component inside the infrastructure.
That separation is what makes the benchmark honest: the downstream application is
identical no matter which speech model feeds it. The frontend never names a speech model.

---

## Quick start

```bash
pip install -r requirements.txt          # ffmpeg must also be on PATH
cp .env.example .env                     # then fill in your keys
```

Required in `.env`:

```bash
INTRON_API_KEY=...     # https://voice.intron.io -> Developers tab
HF_TOKEN=...           # https://huggingface.co/settings/tokens (AfriSwitch is gated)
GROQ_API_KEY=...       # or ANTHROPIC_/OPENAI_/GEMINI_/MISTRAL_ — any one works
```

### Run the demo

```bash
# web UI — record in the browser, watch the case build
python -m uvicorn app.server:app --port 8000

# or one file, in the terminal
python scripts/demo.py data/demo/audio/fin_01_s1.wav --model sahara --language pidgin
python scripts/demo.py --text "I transfer forty five thousand naira but the person never receive am"
```

### Run the benchmark

```bash
# 1. build an evaluation manifest
python -m benchmark.load_dataset --source afriswitch --languages yoruba pidgin igbo hausa --per-language 100

# 2. transcribe (resumable — safe to Ctrl-C and rerun)
python -m benchmark.run_asr --model sahara            --manifest data/manifests/afriswitch.jsonl
python -m benchmark.run_asr --model whisper_large_v3  --manifest data/manifests/afriswitch.jsonl
python -m benchmark.run_asr --model whisper_small     --manifest data/manifests/afriswitch.jsonl
python -m benchmark.run_asr --model mms_yoruba_english --manifest data/manifests/afriswitch.jsonl

# 3. score (Level 1) and compile cases (Level 2)
python -m benchmark.evaluate       --manifest data/manifests/afriswitch.jsonl
python -m benchmark.run_downstream --manifest data/manifests/demo.jsonl
```

Results land in `reports/` as `RESULTS.md`, `DOWNSTREAM.md` and CSVs.

---

## Models benchmarked

| Model | Role | Runs on |
|---|---|---|
| **Intron Sahara v2.5** | African code-switching specialist (required) | API |
| **Whisper large-v3** | strongest general-purpose multilingual baseline | API (Groq) |
| **Whisper small** | general-purpose baseline, fully local | CPU, int8 |
| **MMS-300M Yoruba-English** | African/code-switch specialist baseline | CPU |

Adding a fifth is one entry in `ENGINES` in [`app/asr.py`](app/asr.py).

**MMS is Yoruba-English only, so it is scored only on the Yoruba track.** Running a
Yoruba-only model on Hausa and reporting the result as a fair comparison would be
dishonest benchmarking. The harness enforces this automatically via
`supported_languages`.

---

## Benchmark methodology

### Level 1 — speech recognition

WER and CER, broken down by language, code-mixing band (CMI) and noise condition, each
with a **bootstrap 95% confidence interval**. With 100–200 clips per language a
two-point WER gap is usually noise, and an interval says so.

**Three normalization schemes are reported, not one:**

| Scheme | Definition | Why it exists |
|---|---|---|
| `strict` | punctuation stripped, **diacritics preserved** | rewards correct Yoruba orthography |
| `loose` | also strips sub-dots (ẹ ọ ṣ) and tone marks | segmental accuracy only |
| `numeric` | `loose` + numbers canonicalised to digits | formatting is not recognition |

This matters more than it sounds. Yoruba tone marks and sub-dot characters can move WER
by tens of points, and the choice systematically favours whichever model happens to match
it. Reporting a single WER without naming the scheme is not a result.

The `numeric` scheme exists because of a measured effect: Sahara returns `45,000` and
`0987654321` where a human transcriber writes *"forty five thousand"* and *"zero nine
eight..."*. Under plain WER that costs Sahara **six word errors for a perfect
transcription**. We verified this against the live API. Canonicalising numbers measures
whether the number was *heard*, not how it was typeset.

### Level 2 — institutional understanding

The experiment that matters:

```
                     SAME AUDIO
                          │
      ┌───────────┬───────┴───────┬───────────┐
      ▼           ▼               ▼           ▼
   Sahara    Whisper L-v3    Whisper S      MMS
      └───────────┴───────┬───────┴───────────┘
                          ▼
                 THE SAME CASE COMPILER
                          ▼
         field accuracy · entity accuracy · negation
         integrity · case-type accuracy · routing accuracy
```

Plus a **`human_reference` row** that compiles the human transcript. That is the ceiling:
any gap between it and a model is the downstream cost of that model's ASR errors, cleanly
separated from the compiler's own limitations.

### Integrity guarantees

Benchmarks are easy to corrupt by accident, so the harness refuses to help:

- **Inference and evaluation are separate programs.** Transcription is cached to
  `benchmark/results/*.jsonl`; adding a metric never re-runs a model.
- **Resumable.** Crash at clip 287 of 400, rerun, continue at 288. Rows are flushed
  individually.
- **Degraded cases are excluded, not scored.** If the extraction LLM rate-limits, that
  case is dropped from the downstream results with a loud warning. During development
  this exact failure silently made one model look 36 points worse than it was. An
  infrastructure outage must never be reportable as a model result.
- **Provider failover.** Every configured LLM key is tried in order before anything falls
  back to rules.
- **No fabricated numbers.** Every figure in `reports/` is computed from cached model
  outputs and reproducible from them.

---

## Layout

```
app/
  asr.py         ASR abstraction + Sahara / Whisper / MMS engines
  normalize.py   normalization schemes, number + negation extraction
  llm.py         provider-agnostic structured JSON (+ failover)
  schemas.py     the three domain schemas   <- add a vertical here
  compiler.py    transcript -> structured case
  questions.py   adaptive question engine
  routing.py     rule-based routing + case packet
  server.py      FastAPI backend
  static/        voice-first UI
benchmark/
  load_dataset.py  AfriSwitch / demo -> manifest
  run_asr.py       resumable, throttled, concurrent runner
  evaluate.py      Level 1: WER/CER + CIs + stratification
  run_downstream.py Level 2: case-level accuracy
docs/
  RECORDING_GUIDE.md   how the evaluation audio was produced
  RESPONSIBLE_AI.md    consent, privacy, safety, limitations
```

Routing is **rule-based by design** ([`app/routing.py`](app/routing.py)). An LLM is never
asked which agency handles a complaint: a hallucinated agency in a case file is worse
than no routing at all.

---

## Safety posture

The system distinguishes **what the user reported** from **what the system concluded**,
and never crosses the line:

> ❌ "Your landlord has illegally evicted you."
> ✅ "You reported that your landlord asked you to leave before your stated rental period ended."

Every case packet carries a disclaimer, a confidence level, the extractor that produced
it and any warnings raised during compilation. It generates an actionable case packet and
a recommended workflow — **it does not submit anything to any real institution**, and it
says so.

See [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md).

---

## Known limitations

- **MMS is Yoruba-English only**; it is not a general African ASR baseline and is not
  scored as one.
- **Whisper has no Nigerian Pidgin token.** Pidgin is sent as English. That is a real
  limitation of the baseline and is reported rather than hidden.
- The downstream evaluation set is **small and self-recorded**, with a limited number of
  speakers. It demonstrates the measurement method; it is not a population-level claim.
- Rule-based extraction is a degraded fallback for when no LLM is reachable. It is
  labelled as such in every packet it produces.
- Routing targets are workflow names, not live government or bank endpoints.

---

*Built for the Sahara CodeSwitch Africa Challenge (Legal & Public Services).*
