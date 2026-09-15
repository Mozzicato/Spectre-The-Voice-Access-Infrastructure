# Benchmark Report — Voice Access Infrastructure

**Sahara CodeSwitch Africa Challenge** · Legal & Public Services
Repository: https://github.com/Mozzicato/Spectre-The-Voice-Access-Infrastructure

**Research question:** *Does code-switch-aware speech recognition preserve more of the
information required to turn African users' natural speech into actionable institutional
cases?*

We benchmark at two levels: word accuracy (Level 1) and **institutional case accuracy**
(Level 2), because a speech error is not equally harmful in every position. `₦45,000 →
₦4,500` and `he never paid me → he paid me` cost one word each under WER, and destroy a
case file.

---

## 1. Models compared

| Model | Type | Runs on | Why included |
|---|---|---|---|
| **Intron Sahara v2.5** | African code-switching specialist | API | required; the model under test |
| **Whisper large-v3** | general-purpose multilingual | API (Groq) | strongest available general baseline |
| **Whisper small** | general-purpose multilingual | local CPU, int8 | size-controlled pair with large-v3 |

Whisper large-v3 and small share an architecture and training recipe and differ mainly in
capacity. That pairing separates *what capacity buys you* from *what code-switch-specific
training buys you* — which is the comparison Sahara is actually in.

**MMS-300M Yoruba-English** is implemented and selectable in `app/asr.py` but produced no
results: its 1.2 GB download was cut off repeatedly on our network. It appears in no
table. We report it as unrun rather than drop it silently.

---

## 2. Data

| Set | Source | Languages | Size | Reference |
|---|---|---|---|---|
| **Level 1** | `intronhealth/AfriSwitch` (gated) | Yoruba–English | 25 clips, ~4.6 min | human transcription |
| **Level 2** | own recordings | Yoruba / Igbo / Hausa / Pidgin × English | 18 clips, 7.8 min | designed case ground truth |

**Preprocessing.** All audio normalised to 16 kHz mono PCM via ffmpeg. AfriSwitch is
streamed one clip at a time and written to disk immediately (never materialised in RAM);
audio is fetched with `decode=False` and decoded by ffmpeg, avoiding a torchcodec
dependency and keeping peak memory per clip small. The evaluation set carries AfriSwitch's
`cmi` and `num_switch_points` metadata, so code-mixing stratification uses the dataset's
own labels rather than ones we invented.

**Level 2 recordings** were produced from `docs/RECORDING_GUIDE.md`, which plants specific
facts — confusable amounts, negations, a read-out ten-digit reference — chosen because
they are the errors that damage a *case*, not merely a transcript. Speakers improvised
around required facts rather than reading scripts. Metadata covers language pair, domain,
CMI band (low/medium/heavy) and noise condition (quiet/street).

**Limitation, stated plainly.** Level 1 covers Yoruba only. Igbo, Hausa and Pidgin
AfriSwitch pulls were repeatedly cut off by CDN connection drops. Level 2 covers all four
language pairs but has one speaker.

---

## 3. Metrics and why they are appropriate

**WER / CER** — standard, comparable to published ASR work. Reported under **three
declared normalization schemes**, because the choice changes the ranking:

| Scheme | Definition | Why it exists |
|---|---|---|
| `strict` | punctuation stripped, **diacritics preserved** | rewards correct Yoruba orthography |
| `loose` | also strips sub-dots (ẹ ọ ṣ) and tone marks | segmental accuracy only |
| `numeric` | `loose` + numbers canonicalised to digits | formatting is not recognition |

This is not pedantry. Sahara writes `Ìwọ ni problem mi`; the AfriSwitch human reference is
un-diacritized `Iwo ni problem mi`. **25 of Sahara's 83 strict WER points are orthography,
not recognition** — a diacritic-sensitive scheme penalises it for being *more* correct.
Whisper's strict/loose gap is 1.3 points because it emits no diacritics at all. Publishing
a single WER number without naming the scheme is not a result.

The `numeric` scheme exists for a measured reason: Sahara returns `45,000` and
`0987654321` where a human transcriber writes "forty five thousand". Under plain WER that
costs Sahara six word errors for a *perfect* transcription.

**Information-preservation metrics** — amount recall, reference-number recall, negation
integrity. These answer the question WER cannot: did the facts an institution acts on
survive?

**Case-level metrics** — field accuracy, case-type accuracy, routing accuracy,
completeness.

**Bootstrap 95% confidence intervals** (1000 resamples over utterances) on every headline
figure, so a small gap is not read as a finding.

---

## 4. Level 1 results — speech recognition

25 AfriSwitch Yoruba clips, human references:

| Model | WER strict | WER loose | WER numeric (95% CI) | CER loose | Negation ↑ | Median latency |
|---|--:|--:|--:|--:|--:|--:|
| **`sahara`** | 83.1 | **57.5** | **57.4 (49.1–66.6)** | **38.6** | **52.8%** | 17.9 s |
| `whisper_large_v3` | 89.1 | 87.8 | 87.8 (79.9–96.5) | 49.5 | 13.9% | 4.5 s |
| `whisper_small` | 103.2 | 103.2 | 103.2 (96.8–114.7) | 89.0 | 0.0% | 188.0 s |

**Sahara wins every accuracy metric, with non-overlapping confidence intervals** — a
30-point WER gap over the strongest general-purpose model. Absolute WER is high for all
three because AfriSwitch is spontaneous, heavily code-mixed in-the-wild speech, not read
prompts.

`whisper_small` exceeding 100% WER is not an error: WER counts insertions, and it
hallucinates past the reference length.

### By code-mixing intensity (WER loose) — the key table

| Model | Low CMI (n=9) | Medium (n=7) | High (n=9) | Spread |
|---|--:|--:|--:|--:|
| **`sahara`** | 60.3 | 54.7 | **56.7** | **5.6** |
| `whisper_large_v3` | 91.9 | 93.0 | 79.7 | 13.3 |
| `whisper_small` | 101.2 | 113.4 | 97.8 | 15.6 |

**Sahara is flat across code-mixing intensity; the baselines are not.** This is the
clearest evidence in the benchmark that code-switch-specific training is doing real work,
rather than Sahara simply being a better Yoruba model.

### Latency — a deployment finding

Whisper small at **188 s median on a 4-core CPU is ~6× slower than real time**, and
unusable interactively. The local "cheap" option is the expensive one. Sahara at 17.9 s
is a live API call (~2.3× real time). Whisper large-v3 via API is fastest at 4.5 s.

---

## 5. Level 2 results — institutional understanding

Same audio → every model → **the same case compiler** → scored against designed ground
truth. 18 recordings across four language pairs and three domains:

| Model | Field acc ↑ | Amounts ↑ | Ref-nums ↑ | Negation ↑ | Case type ↑ | Routing ↑ | Completeness ↑ |
|---|--:|--:|--:|--:|--:|--:|--:|
| `whisper_large_v3` | **60.5** | **94.1** | 100.0 | 100.0 | **100.0** | **100.0** | 82.2 |
| `sahara` | 59.2 | 58.8 | 100.0 | 100.0 | **100.0** | **100.0** | **83.3** |
| `whisper_small` | 48.7 | 82.4 | 100.0 | 100.0 | 83.3 | 83.3 | 69.6 |

**Finding 1 — ASR quality breaks the downstream task, but only past a threshold.**
Sahara and Whisper large-v3 both classify and route **100%** of cases correctly despite
very different transcripts. Whisper small falls to 83.3% on both. The size-controlled pair
isolates the cause as capacity.

**Finding 2 — the two strong models fail in opposite directions.** Measured on raw
transcripts:

| Model | Amounts preserved | Negations preserved |
|---|--:|--:|
| `sahara` | 10/17 (58.8%) | **36/38 (94.7%)** |
| `whisper_large_v3` | **16/17 (94.1%)** | 30/38 (78.9%) |
| `whisper_small` | 14/17 (82.4%) | 28/38 (73.7%) |

Sahara preserves code-switched *structure*; Whisper preserves *numbers*. Sahara
systematically drops a zero on large naira amounts: `240,000 → 24000`, `320,000 → 32000`,
`48,000 → 14000`, `20,000 → 2000`.

**Finding 3 — the compiler partially repairs dropped negations.** Negation integrity is
100% at case level for all three models while transcript-level preservation ranges
73.7–94.7%: the extraction step recovers the negative claim from context. Only visible
because the same property was measured at both levels.

---

## 6. Qualitative findings per model

**Intron Sahara v2.5** — *Strengths:* best WER/CER on code-switched Yoruba by a wide
margin; flat across code-mixing intensity; best negation preservation (94.7%); emits
correct Yoruba orthography with tone marks and sub-dots; handles Pidgin, Igbo and Hausa
code-switching in Level 2. *Weaknesses:* **unreliable on large naira amounts** (58.8%) —
systematically drops a zero; splits long reference numbers (`09876543 21`, all digits
correct); 17.9 s latency is the slowest of the two API options. *Note:* its orthographic
correctness is penalised by diacritic-sensitive scoring against un-diacritized references.

**Whisper large-v3** — *Strengths:* best number preservation (94.1%); fastest (4.5 s);
matches Sahara on case-type and routing accuracy. *Weaknesses:* 87.8% WER on code-switched
Yoruba; drops negations (13.9% preserved at Level 1, 78.9% at Level 2); emits no
diacritics; **rejects Igbo outright** (`unsupported language: ig`) and has no Nigerian
Pidgin token — both fall back to English.

**Whisper small** — *Strengths:* fully local, no API dependency or cost. *Weaknesses:*
breaks down on this task — 103.2% WER, 89.0% CER, **zero** negations preserved at Level 1;
degrades case-type and routing accuracy to 83.3%; 188 s median latency makes it unusable
interactively on commodity hardware.

---

## 7. Benchmark integrity

- **Inference and evaluation are separate programs.** Every figure is recomputed from
  cached outputs in `benchmark/results/*.jsonl` and reproducible from them.
- **Runs are resumable and rate-limited.** Crash at clip 287 of 400, rerun, continue at 288.
- **Degraded cases are excluded, not scored.** When our extraction LLM rate-limited
  mid-run it silently made one model look ~36 points worse. The harness now drops those
  rows loudly. An infrastructure outage must never be reportable as a model result.
- **Four scoring bugs were found and fixed**, each of which would have published a *wrong
  number* rather than crashed: `"45 000"` parsed as `[45, 0]` (Whisper was right, our
  scorer was wrong); a correctly-transcribed reference counted as lost; entity recall
  scored off a schema that could not hold multiple amounts; and a negation reference
  derived from an ASR output it was meant to judge. All are pinned in
  `scripts/selftest.py`, which passes.
- **Models are only scored on languages they support**, enforced in code.
- **No result is fabricated or estimated.** Unfilled tables stay unfilled.

---

## 8. Conclusion

**Partly — and the shape of the exception is the contribution.**

Sahara preserves substantially more code-switched linguistic structure: 30 points better
WER, flat performance as code-mixing intensifies, and the best negation retention. On the
information that decides whether a case is *correct* rather than merely *well-formed* —
naira amounts — it is materially worse than a general-purpose model.

Neither result is visible in a WER table. Both matter to someone trying to recover
₦240,000.

**This changed the product.** Because amount preservation is unreliable *and the models
fail on different scenarios*, no choice of speech model fixes it, and a dropped zero
produces a fluent transcript nothing downstream can detect. The system therefore holds
amounts and reference numbers at `awaiting_confirmation` and reads them back to the
speaker before acting. A measured failure became a safety rule.
