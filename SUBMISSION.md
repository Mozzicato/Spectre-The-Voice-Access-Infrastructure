# Voice Access Infrastructure — Challenge Submission

**Sahara CodeSwitch Africa Challenge · Category: Legal & Public Services**

---

## 1. Problem & Solution

### The problem

People don't communicate in forms. They tell stories.

Institutions — courts, banks, local governments — require the opposite: structured cases
with named parties, exact amounts, dates, references and evidence. Between the two sits a
translation gap, and in Africa that gap has a language dimension. A tenant explaining an
eviction does it in Pidgin. A customer describing a failed transfer switches between
Yoruba and English mid-sentence. The form does not accept that, so either the person
gives up, or an intermediary re-tells their story for them.

Speech-to-text alone does not close this gap. A transcript of a story is still a story.

### The solution

**A voice-first translation layer between human narratives and institutional workflows.**

```
natural code-switched speech
   -> transcript
   -> structured meaning (entities, events, amounts, evidence, negation)
   -> institutional case
   -> what is still missing
   -> targeted follow-up questions
   -> actionable case packet + routing
```

The speech model is a *component*, not the product. The same infrastructure drives three
compilers — **Legal**, **Financial**, **Public Service** — sharing one engine and one
question loop. Adding a fourth vertical means adding a schema, not building an app.

### The downstream task

The challenge requires voice to achieve a downstream task rather than produce text. Ours
is **case compilation**: the system emits a structured, routable institutional case and a
list of the information still required to act on it. On our 18-scenario evaluation set it
classified and routed **100% of cases correctly** from raw code-switched speech.

---

## 2. Working prototype

```bash
pip install -r requirements.txt     # ffmpeg must be on PATH
cp .env.example .env                # add INTRON_API_KEY, HF_TOKEN, one LLM key

python -m uvicorn app.server:app --port 8000     # web UI, record in browser
python scripts/demo.py data/demo/audio/fin_01_s1.m4a --model sahara --language pidgin
```

### Demo sequence

Three real recordings, three compilers, one infrastructure:

| Demo | Audio | Compiler | Result |
|---|---|---|---|
| 1 | `fin_01` — Pidgin-English, failed transfer | Financial | `failed_transfer` → bank dispute / NIBSS reversal |
| 2 | `legal_01` — Pidgin-English, eviction | Legal | `tenancy_dispute` → legal aid review |
| 3 | `pub_01` — Yoruba-English, streetlight | Public Service | `streetlight_failure` → LGA works dept |

Verified end-to-end output for Demo 1, from real code-switched audio:

```
FINANCIAL DISPUTE COMPILER — FAILED TRANSFER          100% complete
  institution            : GTBank, Access Bank
  amount                 : 45000 NGN
  transaction_reference  : 0987654321
  recipient              : my brother
  reported_status        : not received          <- negation preserved
  evidence               : alert notification

  CONFIRM BEFORE ACTING
  [?] Please confirm the amount: 45000. Is that correct?
  [?] Please confirm the transaction reference: 0987654321. Is that correct?

  ROUTING  bank_dispute_workflow — Bank transfer dispute / NIBSS reversal

  timing: ASR 24.8s + compile 5.9s = 30.7s
```

---

## 3. Code & documentation

| | |
|---|---|
| [`README.md`](README.md) | architecture, methodology, results, reproduction |
| [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md) | consent, privacy, safety, inclusion, limitations |
| [`docs/RECORDING_GUIDE.md`](docs/RECORDING_GUIDE.md) | how the evaluation audio was produced |
| [`reports/`](reports/) | generated benchmark tables and per-scenario analysis |
| `python scripts/selftest.py` | self-test over the measurement layer — all checks pass |

Layout: `app/` (ASR abstraction, normalization, compiler, schemas, questions, routing,
API, UI) · `benchmark/` (manifest, resumable runner, Level 1 scorer, Level 2 scorer) ·
`scripts/` (demo, transcription, failure analysis, self-test).

---

## 4. Benchmark results

### Models compared

**Three speech models benchmarked**, satisfying the required Sahara + at least two others:

| Model | Role | Runs on | Status |
|---|---|---|---|
| **Intron Sahara v2.5** | African code-switching specialist (required) | API | ✅ benchmarked |
| **Whisper large-v3** | strongest general-purpose multilingual baseline | API | ✅ benchmarked |
| **Whisper small** | general-purpose baseline, size-controlled | local CPU | ✅ benchmarked |
| **MMS-300M Yoruba-English** | African/code-switch specialist, different architecture | local CPU | ⚠️ implemented, not benchmarked |

The two Whisper models are deliberately chosen as a **size-controlled pair**: large-v3 and
small share an architecture and training recipe and differ mainly in capacity, so the gap
between them separates "what capacity buys you" from "what code-switch-specific training
buys you" — which is the comparison Sahara is actually in.

**MMS is implemented in `app/asr.py` and is selectable, but produced no results** and is
therefore absent from every table. Its 1.2 GB download was cut off repeatedly by the same
connection drops that limited our AfriSwitch pull. It is Yoruba-English only, so it would
have been scored on the Yoruba track alone — running a Yoruba-only model on Hausa and
calling that a fair comparison would be dishonest benchmarking, and the harness enforces
that automatically via `supported_languages`.

We report it as unrun rather than quietly dropping it from the model list.

### Evaluation data

- **AfriSwitch** (`intronhealth/AfriSwitch`) — gated, human-transcribed, with `cmi` and
  `num_switch_points`. Level 1 headline.
- **18 self-recorded scenarios** — Yoruba / Igbo / Hausa / Pidgin × English, across legal,
  financial and public-service domains, with designed CMI bands and noise conditions.
  Level 2. Produced from [`docs/RECORDING_GUIDE.md`](docs/RECORDING_GUIDE.md).

### Level 1 — speech recognition

Reported under **three normalization schemes**, because the choice changes the ranking:

| Scheme | Definition |
|---|---|
| `strict` | punctuation stripped, **diacritics preserved** |
| `loose` | also strips Yoruba sub-dots (ẹ ọ ṣ) and tone marks |
| `numeric` | `loose` + numbers canonicalised to digits |

On 25 AfriSwitch Yoruba clips with human reference transcriptions:

| Model | WER strict | WER loose | WER numeric (95% CI) | CER loose | Negation ↑ | Median latency |
|---|--:|--:|--:|--:|--:|--:|
| `sahara` | 83.1 | **57.5** | **57.4 (49.1–66.6)** | **38.6** | **52.8** | 17.9s |
| `whisper_large_v3` | 89.1 | 87.8 | 87.8 (79.9–96.5) | 49.5 | 13.9 | 4.5s |

**Sahara wins decisively on in-the-wild code-switched Yoruba** — a 30-point WER gap whose
95% confidence intervals do not overlap. Absolute WER is high for both because AfriSwitch
is spontaneous, heavily code-mixed speech rather than read prompts.

**Sahara's 25-point strict/loose gap is entirely diacritics.** It writes `Ìwọ ni problem
mi`; the AfriSwitch human reference is un-diacritized `Iwo ni problem mi`. Under a
diacritic-sensitive scheme Sahara is penalised for being *more* orthographically correct.
Whisper's gap is 1.3 points, because it emits no diacritics at all.

A single-scheme WER table would have named the wrong winner. This is the central
methodological claim of our benchmark.

### Level 2 — institutional understanding

The experiment that matters: **same audio → every ASR model → the same case compiler.**

See [`reports/downstream/DOWNSTREAM.md`](reports/downstream/DOWNSTREAM.md) and
[`reports/downstream/FAILURE_ANALYSIS.md`](reports/downstream/FAILURE_ANALYSIS.md) for the
generated tables and per-scenario breakdown.

18 recordings, three models, one compiler:

| Model | n | Field acc ↑ | Amounts ↑ | Ref-nums ↑ | Negation ↑ | Case type ↑ | Routing ↑ | Completeness ↑ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `whisper_large_v3` | 18 | **60.5** | **94.1** | 100.0 | 100.0 | **100.0** | **100.0** | 82.2 |
| `sahara` | 18 | 59.2 | 58.8 | 100.0 | 100.0 | **100.0** | **100.0** | **83.3** |
| `whisper_small` | 18 | 48.7 | 82.4 | 100.0 | 100.0 | 83.3 | 83.3 | 69.6 |

**Finding 1 — ASR quality breaks the downstream task, but only past a threshold.**
Sahara and Whisper large-v3 both classify and route **100%** of cases correctly despite
producing very different transcripts. Whisper small falls to **83.3%** on both. The
size-controlled pair isolates the cause: large-v3 and small share an architecture and
recipe, so the gap is capacity, not code-switch-specific training.

**Finding 2 — the two strong models fail in opposite directions.** Measured on raw
transcripts:

| Model | Amounts preserved | Negations preserved |
|---|--:|--:|
| `sahara` | 10/17 (58.8%) | **36/38 (94.7%)** |
| `whisper_large_v3` | **16/17 (94.1%)** | 30/38 (78.9%) |
| `whisper_small` | 14/17 (82.4%) | 28/38 (73.7%) |

Sahara preserves code-switched *structure*; Whisper preserves *numbers*. Sahara
systematically loses a zero on large naira amounts (`240,000 → 24000`,
`320,000 → 32000`, `48,000 → 14000`).

**Finding 3 — the compiler partially repairs dropped negations.** Negation integrity is
100% at the case level for all three models, while transcript-level preservation ranges
from 73.7% to 94.7%: the extraction step recovers the negative claim from surrounding
context. That robustness is only visible because the same property was measured at both
levels.

### Why this is not just a WER leaderboard

A speech error is not equally harmful in every position:

```
"₦45,000"          -> "₦4,500"       a claim wrong by a factor of ten
"He never paid me" -> "He paid me"   the case inverts
"reference 0987654321" one digit off the dispute cannot be located
```

WER scores all three the same as a mangled filler word. We therefore measure **amount
preservation, reference-number preservation and negation integrity** as first-class
metrics alongside WER, and a `human_reference` row compiles the human transcript as a
ceiling so ASR cost is separated from compiler limitations.

### Benchmark integrity

- Inference and evaluation are separate programs; every number is recomputed from cached
  outputs in `benchmark/results/` and reproducible from them.
- Runs are resumable and rate-limited; crash at clip 287 of 400 and it resumes at 288.
- **Cases compiled by the rule-based fallback are excluded from scoring.** During
  development an LLM rate-limit silently degraded a batch and made one model look ~36
  points worse. An infrastructure outage must never be reportable as a model result.
- Four scoring bugs were found and fixed that would each have published a *wrong number*
  rather than crashed — `"45 000"` parsed as `[45, 0]`, a correctly-transcribed reference
  counted as lost, entity recall scored off a schema that could not hold multiple amounts,
  and a negation reference derived from an ASR output it was meant to judge. These are
  pinned in `scripts/selftest.py`.
- **No result is fabricated or estimated.**

---

## 5. Responsible AI

Full note: [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md).

**Reported vs. concluded.** The system never promotes a claim into a finding. Extracted
content is stored under `user_reported`; the prompt forbids legal or factual
determinations; routing is rule-based so no agency name is ever hallucinated.

> ❌ "Your landlord illegally evicted you."
> ✅ "You reported that your landlord asked you to leave before your stated rental period ended."

**Measurement drove a safety feature.** Because amount preservation is unreliable *and
the models fail on different scenarios*, no choice of speech model fixes it. The system
therefore refuses to treat an extracted amount or reference number as settled: both are
returned in `verification_required`, the packet is held at `awaiting_confirmation`, and
the value is read back to the speaker before the case can be acted on. A dropped zero
produces a fluent transcript that nothing downstream can detect — confirmation is the
only safe response.

**Consent & privacy.** Speakers were told the recordings are for a prototype and its
benchmark and may appear publicly. Scenarios are fictional, with no real account numbers
or third-party names. Live UI audio is written to a temp directory and deleted when the
request completes. No user submission trains anything. Keys live in a gitignored `.env`.

**Inclusion.** Code-switching is the target, not an error case. The prompt forbids
"sanitising" Pidgin or Yoruba into different claims. Results are stratified by language
and code-mixing intensity so a model that degrades as switching increases is visible
rather than averaged away.

**Coverage gaps we state rather than hide.** Whisper has **no Igbo language token** — the
API rejects `ig` outright — and no Nigerian Pidgin token; both fall back to English. MMS
is Yoruba-English only. These are reported, not papered over.

**Limitations.** The downstream set is small and self-recorded with few speakers; it
demonstrates a measurement method, not a population-level claim. Routing targets are
workflow names, not live institutional endpoints. The system has not been tested with
users in genuine distress. It submits nothing to any real institution, and says so on
every packet.

---

## What we would do next

1. More speakers and dialects — the current set demonstrates the method, not coverage.
2. Confirm amounts by voice readback in the UI loop, closing the gap the benchmark found.
3. Evidence upload with document understanding, using the existing three-state tracker.
4. Real routing endpoints, once an institutional partner exists to receive them.

---

*Prototype. Not a production legal, financial or government system.*
