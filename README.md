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
python scripts/demo.py data/demo/audio/fin_01_s1.m4a --model sahara --language pidgin
python scripts/demo.py --text "I transfer forty five thousand naira but the person never receive am"
```

### Run the benchmark

```bash
# 1. build an evaluation manifest
python -m benchmark.load_dataset --source afriswitch --languages yoruba pidgin igbo hausa --per-language 25

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

| Model | Role | Runs on | Status |
|---|---|---|---|
| **Intron Sahara v2.5** | African code-switching specialist (required) | API | ✅ benchmarked |
| **Whisper large-v3** | strongest general-purpose multilingual baseline | API (Groq) | ✅ benchmarked |
| **Whisper small** | general-purpose baseline, size-controlled | CPU, int8 | ✅ benchmarked |
| **MMS-300M Yoruba-English** | African/code-switch specialist | CPU | ⚠️ implemented, not benchmarked |

Adding a fifth is one entry in `ENGINES` in [`app/asr.py`](app/asr.py).

The two Whisper models are a deliberate **size-controlled pair**: same architecture and
training recipe, different capacity. The gap between them separates *what capacity buys
you* from *what code-switch-specific training buys you* — which is the comparison Sahara
is actually in.

**MMS is implemented and selectable but produced no results**, so it appears in no table.
Its 1.2 GB download was cut off repeatedly on this network. It is Yoruba-English only and
would have been scored on the Yoruba track alone — running a Yoruba-only model on Hausa
and reporting that as a fair comparison would be dishonest benchmarking, and the harness
enforces that via `supported_languages`. We list it as unrun rather than drop it silently.

---

## Benchmark methodology

### Level 1 — speech recognition

WER and CER, broken down by language, code-mixing band (CMI) and noise condition, each
with a **bootstrap 95% confidence interval**. At this sample size a two-point WER gap
is usually noise, and an interval says so rather than letting it read as a finding.

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

## Results

All figures below are computed from cached model outputs in `benchmark/results/` and are
reproducible from them. Nothing here is estimated.

### Level 1 — speech recognition (25 AfriSwitch Yoruba clips, human references)

| Model | n | WER strict | WER loose | WER numeric (95% CI) | CER loose | Negation ↑ | Median latency |
|---|--:|--:|--:|--:|--:|--:|--:|
| `sahara` | 25 | 83.1 | **57.5** | **57.4 (49.1–66.6)** | **38.6** | **52.8** | 17.9s |
| `whisper_large_v3` | 25 | 89.1 | 87.8 | 87.8 (79.9–96.5) | 49.5 | 13.9 | 4.5s |
| `whisper_small` | 25 | 103.2 | 103.2 | 103.2 (96.8–114.7) | 89.0 | 0.0 | 188.0s |

`whisper_small` exceeding 100% WER is not an error: WER counts insertions, and it
hallucinates past the reference length. It preserved **zero** negations across the set.

**By code-mixing intensity — Sahara is flat where the baselines degrade:**

| Model | Low CMI | Medium | High |
|---|--:|--:|--:|
| `sahara` | 60.3 | 54.7 | **56.7** |
| `whisper_large_v3` | 91.9 | 93.0 | 79.7 |
| `whisper_small` | 101.2 | 113.4 | 97.8 |

Sahara moves ~5 points across bands; Whisper small swings 16. This is the clearest
evidence in the benchmark that code-switch-specific training is doing real work.

**Latency is a deployment finding.** Whisper small at 188s median on a 4-core CPU is ~6×
slower than real time — unusable interactively. The local "cheap" option is the expensive
one.

**Sahara wins decisively on in-the-wild code-switched Yoruba** — a 30-point WER gap whose
confidence intervals do not overlap. Absolute WER is high for both because AfriSwitch is
spontaneous, heavily code-mixed speech, not read prompts.

Sahara's **25-point strict/loose gap is entirely diacritics**. It writes `Ìwọ ni problem
mi`; the AfriSwitch human reference is un-diacritized `Iwo ni problem mi`. Under a
diacritic-sensitive scheme Sahara is penalised for being *more* orthographically correct.
Whisper's gap is 1.3 points, because it emits no diacritics at all.

A single-scheme WER table would have misrepresented both models.

### Level 2 — institutional understanding (18 self-recorded scenarios)

Same audio, same compiler, different speech model.

| Model | n | Field acc ↑ | Amounts ↑ | Ref-nums ↑ | Negation ↑ | Case type ↑ | Routing ↑ | Completeness ↑ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `whisper_large_v3` | 18 | **60.5** | **94.1** | 100.0 | 100.0 | **100.0** | **100.0** | 82.2 |
| `sahara` | 18 | 59.2 | 58.8 | 100.0 | 100.0 | **100.0** | **100.0** | **83.3** |
| `whisper_small` | 18 | 48.7 | 82.4 | 100.0 | 100.0 | 83.3 | 83.3 | 69.6 |

Three findings, none of them visible in a WER table:

**1. ASR quality does break the downstream task — but only past a threshold.** Sahara and
Whisper large-v3 both classify and route **100%** of cases correctly despite very
different transcripts. Whisper small drops to **83.3%** on both. The size-controlled pair
(large-v3 vs small, same architecture and recipe) isolates this: capacity, not
code-switch-specific training, is what carries the structural decision here.

**2. The two strong models fail in opposite directions.** Measured on the raw transcripts
([`FAILURE_ANALYSIS.md`](reports/downstream/FAILURE_ANALYSIS.md)):

| Model | Amounts preserved | Negations preserved |
|---|--:|--:|
| `sahara` | 10/17 (58.8%) | **36/38 (94.7%)** |
| `whisper_large_v3` | **16/17 (94.1%)** | 30/38 (78.9%) |
| `whisper_small` | 14/17 (82.4%) | 28/38 (73.7%) |

Sahara preserves code-switched *structure*; Whisper preserves *numbers*. Sahara
systematically loses a zero on large naira amounts (`240,000 → 24000`,
`320,000 → 32000`, `48,000 → 14000`).

**3. Semantic loss is recoverable; numeric loss is not.** Measuring negation in the raw
transcript and again in the compiled case fields:

| Model | In transcript | In compiled case | Change |
|---|--:|--:|--:|
| `sahara` | 94.7 | 92.1 | −2.6 |
| `whisper_large_v3` | 78.9 | **97.4** | **+18.4** |
| `whisper_small` | 73.7 | **94.7** | **+21.1** |

A model that drops negations while transcribing largely **regains them in the compiled
case**: the extractor reads surrounding context and reconstructs the negated claim.
Amounts show no such recovery — `240,000` heard as `24,000` has no contextual redundancy
to restore it, and the transcript still reads fluently.

This is the argument for the compiler layer rather than only picking a better speech
model, and the reason the confirmation gate targets amounts and reference numbers
specifically rather than everything.
That is a genuine robustness result, and it is only visible because we measured the same
property at both levels.

### What this changed in the product

Because amount preservation is unreliable **and the models fail on different scenarios**,
no choice of speech model fixes it. So the system does not treat an extracted amount or
reference number as settled: both are returned in `verification_required`, the packet is
held at `awaiting_confirmation`, and the value is read back to the speaker before the
case can be acted on. A dropped zero produces a fluent transcript that nothing downstream
can detect — confirmation is the only safe response.

See `HIGH_RISK_FIELDS` in [`app/routing.py`](app/routing.py).

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
