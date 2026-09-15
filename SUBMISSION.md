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

Four speech models, exceeding the required Sahara + two others:

| Model | Role | Runs on |
|---|---|---|
| **Intron Sahara v2.5** | African code-switching specialist (required) | API |
| **Whisper large-v3** | strongest general-purpose multilingual baseline | API |
| **Whisper small** | general-purpose baseline, size-controlled | local CPU |
| **MMS-300M Yoruba-English** | African/code-switch specialist, different architecture | local CPU |

MMS is Yoruba-English only and is therefore **scored only on the Yoruba track**. Running
a Yoruba-only model on Hausa and calling the result a fair comparison would be dishonest.

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

On AfriSwitch Yoruba:

| Model | WER strict | WER loose | Negation ↑ | Median latency |
|---|--:|--:|--:|--:|
| `sahara` | 57.6 | **34.6** | **88.9** | 19.2s |
| `whisper_large_v3` | 65.1 | 65.1 | 22.2 | 3.1s |

**Sahara's 23-point strict/loose gap is entirely diacritics.** It writes `Ìwọ ni problem
mi`; the AfriSwitch human reference is un-diacritized `Iwo ni problem mi`. Under a
diacritic-sensitive scheme Sahara is penalised for being *more* orthographically correct.
Whisper scores identically under both because it emits no diacritics at all.

A single-scheme WER table would have named the wrong winner. This is the central
methodological claim of our benchmark.

### Level 2 — institutional understanding

The experiment that matters: **same audio → every ASR model → the same case compiler.**

See [`reports/downstream/DOWNSTREAM.md`](reports/downstream/DOWNSTREAM.md) and
[`reports/downstream/FAILURE_ANALYSIS.md`](reports/downstream/FAILURE_ANALYSIS.md) for the
generated tables and per-scenario breakdown.

**Headline finding: the models fail in opposite directions.**

Sahara preserves code-switched *structure* — it keeps negations Whisper drops and writes
correct Yoruba orthography. Whisper preserves *numbers* — Sahara systematically loses a
zero on large naira amounts (`240,000 → 24000`, `320,000 → 32000`, `48,000 → 14000`).

Both classify and route **100%** of cases correctly. The architecture is robust to ASR
noise for the structural decision and fragile for the numeric one.

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
