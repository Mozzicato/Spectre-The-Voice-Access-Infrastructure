# Voice Access Infrastructure

## Sahara CodeSwitch Africa Challenge — Build & Benchmark Execution Plan

### 0. The mission

We are building **one reusable voice infrastructure**, not three unrelated applications.

> **The missing translation layer between how people naturally tell their stories and how institutions need those stories structured.**

The system converts:

**Natural code-switched speech → transcript → structured meaning → institutional case → missing information → actionable output**

We will demonstrate the same infrastructure through three compilers:

1. **Legal Case Compiler**
2. **Financial Dispute Compiler**
3. **Citizen Complaint Compiler**

The challenge submission will be positioned primarily under **Legal & Public Services**, while the financial compiler demonstrates that the infrastructure generalises beyond one domain.

The challenge explicitly requires the voice input to perform a **downstream task**, not merely speech-to-text, and requires benchmarking at least **three speech models**, including Sahara plus two others.

---

# 1. What we are actually building

## The complete pipeline

```text
                    USER
                     │
                     │ natural speech
                     ▼
            ┌─────────────────┐
            │   ASR LAYER     │
            │                 │
            │ Sahara v2.5     │
            │ Model B         │
            │ Model C         │
            └────────┬────────┘
                     │
                     ▼
              HUMAN TRANSCRIPT
                     │
                     ▼
          ┌─────────────────────┐
          │  SEMANTIC ENGINE    │
          │                     │
          │ entities            │
          │ events              │
          │ dates               │
          │ amounts             │
          │ locations           │
          │ evidence            │
          │ relationships        │
          └──────────┬──────────┘
                     │
                     ▼
             STORY OBJECT
                     │
                     ▼
          ┌─────────────────────┐
          │ CASE CLASSIFIER     │
          └──────────┬──────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      LEGAL       FINANCIAL    PUBLIC SERVICE
      SCHEMA        SCHEMA        SCHEMA
        │            │            │
        └────────────┼────────────┘
                     ▼
            MISSING INFORMATION
                     │
                     ▼
             ADAPTIVE QUESTIONS
                     │
                     ▼
              COMPLETE CASE
                     │
                     ▼
              ACTION / ROUTING
```

This separation is extremely important.

**Sahara is not our product.**

Sahara is the speech-recognition component inside our infrastructure.

That allows us to benchmark Sahara against other speech models while keeping the downstream application identical.

---

# 2. What the challenge actually gives us

The official challenge identifies three relevant open datasets:

* **AfriSwitch**
* **AfriSwitchCare**
* **LyngualLabs Yoruba-English code-switching dataset**

The challenge explicitly tells participants to ground their work in open African datasets and benchmark speech models on code-switched audio.

For our project, **AfriSwitch is the primary benchmark dataset.**

AfriSwitch is particularly useful because it is explicitly designed for natural, in-the-wild African code-switched speech.

It contains:

* 54.41 hours
* 16,602 utterances
* 14 African languages
* each switching with English
* human transcriptions
* code-mixing index
* switch-point information

It is an **evaluation-only test set**, not a training set.

That last point matters.

### We do NOT need to download 6.84 GB and train a model.

We are evaluating speech models.

---

# 3. Which dataset do we use for what?

## Dataset A — AfriSwitch

### Purpose:

**Primary ASR benchmark**

We feed identical audio into:

```text
AfriSwitch audio
       │
       ├── Sahara
       ├── Model B
       └── Model C
```

Then compare their transcripts against the human reference transcript.

This gives us:

* WER
* CER
* performance by language
* performance by code-mixing intensity
* potentially performance by switch-point density

AfriSwitch contains Nigerian Pidgin, Yoruba, Igbo and Hausa among its languages, which makes it particularly relevant to our African institutional-access use case.

---

# 4. Dataset B — LyngualLabs Yoruba-English

This is useful because it gives us a **more focused Nigerian language benchmark**.

The challenge itself identifies the LyngualLabs Yoruba-English dataset as one of its code-switching resources.

We don't need to make this the main benchmark.

Instead:

```text
AfriSwitch
    ↓
main cross-language benchmark

LyngualLabs
    ↓
focused Yoruba-English robustness check
```

This is particularly useful if our demo contains Yoruba-English speech.

---

# 5. Dataset C — AfriSwitchCare

We are **not building a healthcare product**, so we should not make AfriSwitchCare central to our final benchmark.

It contains simulated doctor-patient conversations across nine African languages and 12 clinical conditions, totalling 12.11 hours.

It is primarily useful to us as:

> evidence that the same infrastructure could eventually work with domain-specific conversational speech.

But our challenge submission should stay focused.

### Therefore:

**Primary: AfriSwitch**

**Secondary: LyngualLabs Yoruba-English**

**AfriSwitchCare: optional / not required**

---

# 6. VERY IMPORTANT: We don't need to train Sahara

This is where I want us to save time.

The challenge gives us access to Sahara v2.5 APIs.

The requirement is to **use and benchmark** speech models, not build an ASR model from scratch.

The official challenge says teams should use the Sahara code-switching APIs and compare Sahara against at least two other speech models.

So our 8 GB laptop should NOT be spending hours doing:

```text
❌ model training
❌ fine-tuning Whisper
❌ downloading 100GB datasets
❌ GPU-heavy experiments
```

Instead:

```text
audio
  ↓
API / lightweight inference
  ↓
transcript
  ↓
evaluation
```

This is much more realistic on your machine.

---

# 7. Our three speech models

We need exactly three for the first implementation.

## Model 1 — Sahara v2.5

Required.

```text
Sahara API
```

This is our primary code-switching model.

---

## Model 2 — Whisper-family baseline

Use a lightweight inference setup such as:

```text
faster-whisper
```

Rather than downloading an enormous model immediately.

The purpose is to establish a strong, recognisable general-purpose baseline.

---

## Model 3 — African/code-switch-aware open model

We should select an open model with meaningful African-language/code-switch coverage rather than arbitrarily choosing another English ASR model.

A candidate family is a Yoruba/code-switch-trained model from LyngualLabs.

There are already public comparisons showing Sahara and open Yoruba/code-switching models being evaluated on AfriSwitch Yoruba data, which gives us a useful sanity check for our methodology.

### Final model table

| Model                     | Role                        |
| ------------------------- | --------------------------- |
| Sahara v2.5               | Required code-switch model  |
| faster-whisper            | General baseline            |
| African/code-switch model | Local/domain-aware baseline |

**Do not start benchmarking 10 models.**

Three good models with clean methodology > ten badly evaluated models.

---

# 8. First thing we code: the benchmark harness

Before the product UI.

This is important.

Create:

```text
voice-access/
│
├── benchmark/
│   ├── load_dataset.py
│   ├── run_sahara.py
│   ├── run_whisper.py
│   ├── run_model3.py
│   ├── evaluate.py
│   └── results/
│
├── app/
│   ├── asr.py
│   ├── compiler.py
│   ├── schemas.py
│   ├── questions.py
│   └── routing.py
│
├── data/
│   └── demo/
│
├── scripts/
│
├── requirements.txt
└── README.md
```

The benchmark should become reproducible.

---

# 9. Downloading the benchmark efficiently

Do NOT manually download the entire dataset through the browser.

Use Hugging Face's `datasets` library.

Install:

```bash
pip install datasets soundfile librosa jiwer pandas tqdm
```

Then:

```python
from datasets import load_dataset

ds = load_dataset(
    "intronhealth/AfriSwitch",
    "yoruba",
    split="test"
)

print(ds)
```

AfriSwitch exposes each language as a separate configuration and the dataset card explicitly documents this loading pattern.

---

# 10. Do NOT immediately download all 54 hours

This is one of our biggest efficiency decisions.

Your laptop has 8 GB RAM.

We don't need the whole dataset sitting in memory.

Start with:

```text
Yoruba
Pidgin
Igbo
Hausa
```

These are highly relevant to our Nigerian use case.

Then select a **representative evaluation subset**.

For example:

```text
100–200 clips per language
```

That gives us approximately:

```text
400–800 clips
```

for development.

Once everything works, we run the final benchmark on the agreed evaluation subset / full required benchmark according to the challenge guidance.

The dataset itself has enough metadata to stratify by code-mixing intensity, because every utterance contains CMI and switch-point information.

---

# 11. Why we stratify the benchmark

This is one of the things that can make our benchmark look much more serious.

Suppose:

```text
Model A WER = 20%
Model B WER = 22%
```

That doesn't tell us much.

But:

```text
                 Low mixing   Medium   Heavy mixing
Sahara              12%         19%        27%
Whisper             14%         28%        47%
Model C             13%         24%        39%
```

Now we can ask:

> **What happens as code-switching becomes harder?**

That's actually relevant to the challenge.

AfriSwitch already provides `cmi` and `num_switch_points`, so we don't need to invent those labels ourselves.

---

# 12. The ASR benchmark

For every audio file:

```text
audio.wav
    │
    ├── Sahara → prediction.txt
    │
    ├── Whisper → prediction.txt
    │
    └── Model C → prediction.txt
```

Reference:

```text
human_transcription.txt
```

Then calculate:

### WER

Word Error Rate.

Lower = better.

### CER

Character Error Rate.

Lower = better.

Then report:

```text
Overall WER
Overall CER

WER by language
CER by language

WER by CMI band
WER by switch-point band
```

The challenge explicitly expects consistent, reviewable model comparison, and Intron's published benchmark work uses WER/CER for ASR with results broken down by language.

---

# 13. But we are NOT stopping at WER

This is where our project becomes interesting.

Our actual question is:

> **Does better code-switched ASR produce a better institutional case?**

Because our product doesn't exist to produce pretty transcripts.

It exists to preserve **actionable information**.

---

# 14. Build the Case Compiler

After ASR:

```text
Transcript
    ↓
LLM / structured extraction
    ↓
Case JSON
```

For example:

```json
{
  "case_type": "tenancy_dispute",
  "parties": [],
  "events": [],
  "dates": [],
  "amounts": [],
  "location": null,
  "claims": [],
  "evidence": [],
  "missing_information": []
}
```

We use structured output rather than asking the model:

> "Summarise this."

That's too vague.

We tell it exactly what fields we require.

---

# 15. Our domain schemas

## Legal

```text
case_type
parties
location
events
dates
amounts
claims
actions_taken
evidence
missing_information
```

## Financial

```text
case_type
account_holder
transaction_type
amount
currency
date
transaction_reference
recipient
reported_status
problem
evidence
missing_information
```

## Public Service

```text
complaint_type
location
agency
problem
duration
previous_reports
previous_actions
impact
evidence
missing_information
```

The compiler engine stays the same.

Only the schema changes.

---

# 16. Adaptive questioning

This is a major product feature.

We don't ask:

> "Please fill out this 20-field form."

Instead:

```text
Story
 ↓
Extract what we know
 ↓
Find required fields that are missing
 ↓
Ask only necessary questions
 ↓
Update case
 ↓
Repeat
```

Example:

User says:

> "My landlord dey tell me make I comot..."

System already knows:

```text
case_type = tenancy dispute
party = landlord
issue = eviction
```

But perhaps doesn't know:

```text
location
date
rent status
```

So it asks:

> "What state is the property located in?"

Then:

> "When did your landlord first ask you to leave?"

That's **voice form-filling without the form.**

---

# 17. Evidence handling

We should support:

```text
Voice
Screenshots
Receipts
Documents
Photos
```

But don't overbuild document AI initially.

For the MVP:

```text
voice
+
optional evidence upload
```

The case compiler records:

```text
Evidence mentioned by user
Evidence uploaded
Evidence still missing
```

Example:

```text
✓ Rent receipt mentioned
✓ Rent receipt uploaded
⚠ Eviction notice not provided
```

This makes the system feel like actual case infrastructure rather than a chatbot.

---

# 18. Routing

The routing engine should initially be **rule-based**.

Do NOT ask an LLM to hallucinate government agencies.

Example:

```python
if case_type == "tenancy_dispute":
    route = "legal_aid_review"

elif case_type == "transfer_dispute":
    route = "bank_dispute_workflow"

elif case_type == "streetlight_failure":
    route = "public_infrastructure_complaint"
```

Later we can plug real agency endpoints into these routes.

For the challenge:

> **Generate an actionable case packet and recommended workflow.**

Don't pretend we are actually submitting to government systems if we aren't.

---

# 19. Our benchmark should have TWO levels

## Level 1 — Speech recognition

```text
Audio → Transcript
```

Metrics:

* WER
* CER
* language
* CMI
* switch points

---

## Level 2 — Institutional understanding

```text
Audio
 ↓
ASR
 ↓
Case Compiler
 ↓
Structured Case
```

Metrics:

### Field Accuracy

```text
correct required fields
────────────────────────
total required fields
```

### Case Completeness

How many required fields were correctly populated.

### Entity Accuracy

Names, dates, amounts, locations, references.

### Event Accuracy

Did the system correctly identify:

```text
who did what
when
to whom
```

### Routing Accuracy

Did the system classify the case correctly?

---

# 20. The really important experiment

Take the **same audio**.

Run:

```text
                 SAME AUDIO
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Sahara        Whisper        Model C
       │             │             │
       ▼             ▼             ▼
   Transcript    Transcript    Transcript
       │             │             │
       └─────────────┼─────────────┘
                     ▼
              SAME COMPILER
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Case A         Case B         Case C
```

Now we can answer:

> Which speech model preserves the information needed to construct an actionable institutional case?

That is far more interesting than simply saying:

> "Sahara has a 15% WER."

---

# 21. Our final benchmark table

Something like:

| Model   | WER ↓ | CER ↓ | Entity Acc ↑ | Field Acc ↑ | Routing Acc ↑ |
| ------- | ----: | ----: | -----------: | ----------: | ------------: |
| Sahara  |     — |     — |            — |           — |             — |
| Whisper |     — |     — |            — |           — |             — |
| Model C |     — |     — |            — |           — |             — |

And another:

| Model   | Yoruba | Pidgin | Igbo | Hausa |
| ------- | -----: | -----: | ---: | ----: |
| Sahara  |      — |      — |    — |     — |
| Whisper |      — |      — |    — |     — |
| Model C |      — |      — |    — |     — |

And:

| Model   | Low CMI | Medium CMI | High CMI |
| ------- | ------: | ---------: | -------: |
| Sahara  |       — |          — |        — |
| Whisper |       — |          — |        — |
| Model C |       — |          — |        — |

We fill the numbers after running the experiments.

**Never fabricate benchmark results.**

---

# 22. What data do we actually create ourselves?

This is important because the supplied datasets are primarily **ASR evaluation datasets**.

They aren't magically going to contain:

```text
landlord dispute → legal schema
bank transfer → financial schema
streetlight → government complaint
```

So we create a **small downstream evaluation set**.

For example:

### 30 legal scenarios

```text
10 tenancy
10 employment
10 consumer dispute
```

### 15 financial scenarios

```text
5 failed transfer
5 unauthorized transaction
5 payment dispute
```

### 15 public-service scenarios

```text
5 infrastructure
5 utility complaint
5 civic/service complaint
```

Total:

```text
60 scenarios
```

Each scenario has:

```text
audio
ground-truth transcript
ground-truth structured case
expected routing
```

This dataset is **ours**.

It is specifically for evaluating the downstream compiler.

---

# 23. How we create the audio

Do not try to build a 10-hour custom dataset.

We don't have time.

We need a small, high-quality **prototype evaluation set**.

For example:

```text
60 scenarios
×
2 speakers
≈
120 recordings
```

Use natural Nigerian code-switching.

Examples:

> "My landlord dey tell me make I comot..."

> "I transfer forty-five thousand yesterday..."

> "This streetlight don spoil for almost three weeks..."

The speakers should speak naturally rather than reading robotic English sentences.

We record:

```text
.wav
16 kHz
mono
```

Then store metadata:

```csv
id,domain,language_pair,scenario_type,device,noise
001,legal,Yoruba-English,tenancy,phone,quiet
002,finance,Pidgin-English,transfer,phone,street
003,public_service,Yoruba-English,streetlight,phone,quiet
```

The challenge asks, where possible and permitted, for code-switched audio samples used in testing with metadata such as language pair, domain, accent/country, device and noise conditions.

---

# 24. Don't use expensive APIs everywhere

Your 8 GB machine changes our engineering strategy.

## Local

Run locally:

* dataset loading
* audio preprocessing
* WER/CER
* evaluation
* JSON validation
* lightweight Whisper inference
* benchmark aggregation

## API/cloud

Use APIs for:

* Sahara
* whichever third speech model requires API access
* LLM semantic extraction if needed

## Browser/cloud deployment

Use:

* Vercel/another lightweight frontend host
* serverless backend where practical

Your laptop should be the **development/control machine**, not the production server.

---

# 25. Memory strategy for 8 GB RAM

### Rule 1

Never:

```python
dataset = list(dataset)
```

for huge datasets.

Stream or process in batches.

### Rule 2

Don't load hundreds of audio files simultaneously.

Process:

```text
1 audio
→ inference
→ save result
→ next audio
```

### Rule 3

Cache every model output.

If Sahara processes 500 clips once, save:

```text
results/sahara.jsonl
```

Then don't call Sahara again.

Same for every model.

### Rule 4

Never rerun expensive inference just to calculate another metric.

Separate:

```text
INFERENCE
```

from:

```text
EVALUATION
```

---

# 26. The benchmark pipeline should be resumable

This is critical.

Suppose you process 400 files and your laptop crashes at #287.

We should be able to run:

```bash
python benchmark/run_sahara.py
```

and it detects:

```text
286 results already exist
```

then continues from:

```text
287
```

Not start from zero.

---

# 27. Product architecture

For the actual application:

```text
Frontend
   │
   ▼
API
   │
   ├── ASR service
   │      └── Sahara
   │
   ├── Compiler
   │      ├── extraction
   │      ├── classification
   │      └── validation
   │
   ├── Question engine
   │
   └── Routing engine
```

The frontend doesn't need to know anything about Sahara.

That means later:

```text
Sahara
   ↓
Whisper
   ↓
another African ASR
```

can be swapped without rebuilding the product.

---

# 28. MVP UI

Do NOT build a massive dashboard.

Screen 1:

```text
VOICE ACCESS

Tell us what happened.

[ ⚖ Legal ]
[ 🏦 Financial ]
[ 🏛 Public Service ]
```

Then:

```text
        🎙

   Tap to speak

"Tell us what happened
in your own words."
```

Then:

### Step 1 — Understanding

```text
We heard:

"My landlord dey tell me..."
```

### Step 2 — Case

```text
TENANCY DISPUTE

People involved
✓ Tenant
✓ Landlord

Issue
✓ Eviction request

Evidence
✓ Rent receipt

Missing
⚠ Property location
```

### Step 3 — Complete

```text
CASE READY

[ Review Case ]
[ Download Case ]
```

That's enough.

---

# 29. Demo sequence

The final video should show **three cases very quickly**.

### Demo 1

🎙 User speaks Nigerian Pidgin/English

↓

**Legal Case Compiler**

↓

Structured tenancy case.

---

### Demo 2

🎙 User speaks Pidgin/English

↓

**Financial Dispute Compiler**

↓

Structured transfer dispute.

---

### Demo 3

🎙 User speaks Yoruba/English

↓

**Citizen Complaint Compiler**

↓

Structured public-service complaint.

Then zoom out:

```text
              VOICE ACCESS INFRASTRUCTURE

                         ↓

       ┌─────────────────┼─────────────────┐
       ↓                 ↓                 ↓

    LEGAL            FINANCIAL        PUBLIC SERVICE

       Same voice understanding + case compiler
```

That is the moment we communicate the platform.

---

# 30. What NOT to build

We are aggressively cutting scope.

### ❌ No custom ASR training

### ❌ No fine-tuning Whisper

### ❌ No mobile app

### ❌ No WhatsApp bot initially

### ❌ No USSD initially

### ❌ No real government API integration

### ❌ No payment integration

### ❌ No vector database unless a real feature requires it

### ❌ No giant knowledge base

### ❌ No generic legal chatbot

### ❌ No "AI lawyer"

### ❌ No autonomous legal advice

### ❌ No 20-domain support

The product is:

> **Speech → structured institutional case.**

---

# 31. Legal safety

The system should explicitly distinguish:

```text
USER REPORTED
```

from:

```text
SYSTEM CONCLUDED
```

For example:

Bad:

> "Your landlord has illegally evicted you."

Good:

> "You reported that your landlord asked you to leave before your stated rental period ended."

This prevents the system from pretending to make legal determinations.

---

# 32. Privacy

Because we're dealing with potentially sensitive legal and financial information:

```text
Consent
   ↓
Audio processing
   ↓
Minimal retention
   ↓
No training on user submissions
   ↓
User-controlled deletion
```

For the demo, we can make clear that prototype recordings are processed for the demonstration/benchmark and aren't presented as a production legal record.

The challenge explicitly judges consent, privacy, inclusion, bias and user dignity.

---

# 33. The actual development order

This is the part I want us to follow.

## PHASE 1 — Benchmark foundation

**First.**

```text
1. Create repository
2. Install dependencies
3. Load AfriSwitch
4. Inspect dataset
5. Select initial evaluation subset
6. Implement Sahara inference
7. Implement Model B
8. Implement Model C
9. Save transcripts
10. Calculate WER/CER
```

### Deliverable:

```text
benchmark/results.csv
```

with actual numbers.

---

# PHASE 2 — Downstream benchmark

```text
1. Create 60 scenarios
2. Record audio
3. Create ground-truth transcripts
4. Create ground-truth JSON cases
5. Run all three ASR systems
6. Feed transcripts into same compiler
7. Compare structured outputs
8. Calculate field/entity/routing accuracy
```

### Deliverable:

```text
downstream_benchmark.csv
```

---

# PHASE 3 — Build the infrastructure

```text
1. ASR abstraction
2. semantic extraction
3. case classifier
4. schema engine
5. missing-field detector
6. question engine
7. routing engine
```

### Deliverable:

```text
working backend
```

---

# PHASE 4 — Three compilers

Implement:

```text
LegalSchema
FinancialSchema
PublicServiceSchema
```

No duplicated pipeline code.

---

# PHASE 5 — UI

Build the simple voice-first interface.

---

# PHASE 6 — Integration

Test:

```text
speech
 ↓
Sahara
 ↓
compiler
 ↓
questions
 ↓
case
```

End-to-end.

---

# PHASE 7 — Benchmark + polish

Run final benchmark.

Generate:

```text
WER table
CER table
language table
CMI table
field accuracy
entity accuracy
routing accuracy
latency
```

---

# PHASE 8 — Submission

Prepare:

### 1. Problem & Solution

One-page concise explanation.

### 2. Working prototype

Demo video.

### 3. Code & docs

GitHub repository + README.

### 4. Benchmark report

Reproducible methodology + results.

### 5. Responsible AI

Privacy + consent + limitations + safety.

These are exactly the categories listed by the challenge.

---

# 34. What our GitHub README should eventually communicate

The opening should basically say:

> **Voice Access Infrastructure is a voice-first translation layer between human narratives and institutional workflows.**
>
> People don't naturally communicate in forms. They tell stories. Institutions, however, require structured cases, complaints and disputes.
>
> Our system converts natural African code-switched speech into structured institutional cases while preserving entities, events, evidence and missing information.
>
> We demonstrate the infrastructure across legal disputes, financial disputes and public-service complaints.

Then:

```text
Architecture
Benchmark
Models
Results
Demo
Safety
Reproducibility
```

---

# 35. The research question

This should be the spine of the benchmark report:

> **Does code-switch-aware speech recognition preserve more of the information required to transform African users' natural speech into actionable institutional cases?**

That connects:

**Sahara → code-switching → ASR → our infrastructure → downstream impact.**

It isn't an arbitrary benchmark.

---

# 36. What success looks like

We don't need Sahara to win every metric.

In fact, if another model wins something, **that's useful evidence**.

Our job is to demonstrate:

### Product

The infrastructure works.

### Technical

The benchmark is fair and reproducible.

### Research

We measure the downstream consequence of ASR quality.

### Impact

People can communicate naturally rather than learning bureaucratic forms.

### Scalability

The same infrastructure supports:

```text
Legal
Financial
Public Service
```

without rebuilding the voice layer.

---

# 37. The final mental model

Do NOT think:

> "I'm building three AI applications."

Think:

> **I'm building a compiler for human stories.**

The input language is:

```text
Speech
Pidgin
Yoruba-English
Igbo-English
Hausa-English
etc.
```

The intermediate representation is:

```text
entities
events
timeline
evidence
claims
relationships
```

The output language is:

```text
LEGAL_CASE
FINANCIAL_DISPUTE
CITIZEN_COMPLAINT
```

And that is why the architecture is defensible.

---

# 38. Our immediate next move

**Do not start the frontend.**

Do not start the three compilers.

Do not start recording 60 scenarios.

First, we establish the benchmark.

### Step 1

Create the repo.

### Step 2

Install the lightweight Python environment.

### Step 3

Load **100 Yoruba + 100 Pidgin + 100 Igbo + 100 Hausa** AfriSwitch samples.

### Step 4

Inspect exactly what Hugging Face gives us.

### Step 5

Run **Sahara on those samples**.

### Step 6

Run the first baseline.

### Step 7

Calculate WER/CER.

### Step 8

Inspect actual failure cases.

**Only after that do we lock the downstream benchmark design.**

This order minimizes wasted work because we'll know, with real audio, what Sahara and the baselines actually produce before we build the rest of the system around assumptions.


Yes. And after checking the **current challenge wording and the available models**, I would change our earlier recommendation slightly.

There are **two things to optimize simultaneously**:

1. The benchmark has to look scientifically credible.
2. It has to be practical on your **8 GB machine** and within today's deadline.

The official competition rules require **Sahara + at least two other speech models**. The submission page currently phrases the benchmark section even more aggressively as comparing Sahara against at least three other models, so I would actually design our code so adding a **4th model is trivial**, but I would not make that a blocker for the MVP. ([Intron Voice AI][1])

## My recommendation

### 🥇 Model 1 — Intron Sahara v2.5

**Mandatory.**

This is our primary model.

```text
Sahara v2.5 API
```

Why:

* It's the model the challenge is built around.
* It is specifically designed for African code-switching.
* We can use the API rather than consuming your laptop's RAM/CPU.
* It gives us the model we're actually trying to evaluate against alternatives.

**Keep Sahara exactly as the challenge intends: API, not local model.**

---

# 🥈 Model 2 — Whisper Small

I recommend:

**`openai/whisper-small`**

or the Hugging Face implementation.

Why?

Because this gives us a **general-purpose global baseline**.

It's only about **244M parameters**, so it is dramatically more realistic on your 8 GB machine than trying to run something like Whisper large-v3 locally.

The question we're asking becomes:

> How does a general-purpose multilingual speech model perform when confronted with African code-switching?

That's a legitimate baseline.

### Role

```text
Sahara
   vs
General-purpose multilingual ASR
```

This is important because we're not comparing Sahara against two models that were specifically built for the exact same problem.

---

# 🥉 Model 3 — Meta MMS-300M, Yoruba-English fine-tune

This is the one I **really like** for our benchmark.

Use:

**`LyngualLabs/mms-300m-yoruba-english`**

It's a Meta MMS-300M model fine-tuned specifically for **Yoruba-English code-switching**. ([Hugging Face][2])

That gives us:

```text
Sahara
     │
     │ African code-switching
     │
     ├───────────────┐
     │               │
     ▼               ▼
Whisper Small     MMS-300M
general           Yoruba-English
baseline          specialized baseline
```

This is a **much more interesting comparison**.

We're testing:

> General multilingual model vs African-language specialized model vs Sahara's African code-switching infrastructure.

---

# So the three are:

| Model                       | Why we're using it                           | Where it runs |
| --------------------------- | -------------------------------------------- | ------------- |
| **Sahara v2.5**             | Required + African code-switching specialist | API           |
| **Whisper Small**           | General multilingual baseline                | Your PC       |
| **MMS-300M Yoruba-English** | African/code-switching specialist baseline   | Your PC       |

### I would lock these three.

---

# Why NOT faster-whisper large-v3?

You might ask:

> "Why don't we use faster-whisper large-v3? Everybody knows Whisper."

Because **large-v3 is overkill for our situation**.

We have:

* 8 GB RAM
* deadline today
* actual product to build
* benchmark to run
* report to write
* demo to record

We don't need to spend our remaining time fighting a giant model.

And there's actually evidence from a public AfriSwitch benchmark that `faster-whisper large-v3` performed **very poorly on the Yoruba AfriSwitch subset** compared with Sahara and African/code-switching models. ([Hugging Face][3])

So it isn't automatically a better benchmark simply because it's a larger model.

---

# Why NOT use LyngualLabs Whisper-small as Model 3?

There is actually a very interesting model:

**`LyngualLabs/yecs-asr-whisper-plain`**

It is Whisper-small fine-tuned specifically on Yoruba-English code-switching. ([Hugging Face][4])

And there is also a language-tag version that can simultaneously identify Yoruba vs English words. ([Hugging Face][5])

It's a **very good model**.

But here's the problem:

```text
Whisper Small
       ↓
Whisper Small fine-tuned on YECS
```

They're both fundamentally Whisper-small.

For our headline benchmark, I prefer:

```text
Sahara
   vs
Whisper
   vs
MMS
```

because the architectures/training philosophies are more meaningfully different.

---

# There is one important limitation

The MMS model we just selected is specifically:

> **Yoruba-English**

So we shouldn't pretend that this third model is a universal benchmark for:

```text
Yoruba
Igbo
Hausa
Pidgin
...
```

It isn't.

That's actually fine.

### We can structure our benchmark intelligently.

Use the **Yoruba-English subset** of AfriSwitch for the three-model head-to-head benchmark:

```text
AfriSwitch Yoruba-English
          │
          ├──────── Sahara
          │
          ├──────── Whisper Small
          │
          └──────── MMS-300M Yoruba-English
```

Now all three models have a fair playing field.

Then we can use Sahara separately on additional Nigerian code-switching examples where the other model isn't designed for the language.

**Don't compare a Yoruba-only model on Hausa and then call that a fair benchmark.**

---

# Actually, I'd make the benchmark even stronger

We can run **two benchmark tracks**.

## Track A — Fair 3-model comparison

Yoruba-English.

```text
              SAME AUDIO
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    Sahara     Whisper     MMS-YE
       │          │          │
       ▼          ▼          ▼
     WER        WER        WER
     CER        CER        CER
```

This is our **scientific benchmark**.

---

## Track B — Sahara's broader African capability

Then separately:

```text
Sahara
  │
  ├── Yoruba-English
  ├── Pidgin-English
  ├── Igbo-English
  └── Hausa-English
```

This demonstrates the actual product environment we're targeting.

We don't need to force the other models into languages they weren't designed for.

---

# And here's where our downstream experiment becomes 🔥

Remember our product isn't:

> "Which model transcribes words best?"

Our product is:

> **Which model preserves the information needed to compile an actionable case?**

So for the Yoruba-English benchmark:

```text
                    SAME AUDIO
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
        Sahara       Whisper        MMS
           │            │            │
           ▼            ▼            ▼
      transcript    transcript   transcript
           │            │            │
           └────────────┼────────────┘
                        ▼
               SAME CASE COMPILER
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
           Legal     Financial   Public
```

Then we measure:

### ASR

* WER
* CER

### Information preservation

* names
* dates
* amounts
* locations
* events
* negation
* evidence

### Case quality

* field accuracy
* completeness
* classification accuracy
* routing accuracy

That's where **Voice Access Infrastructure** becomes more than a fancy UI sitting on top of Sahara.

---

# One more thing: don't benchmark only WER

This is probably the most important advice I can give you.

Suppose the results are:

```text
Sahara       WER 18%
Whisper      WER 21%
MMS          WER 19%
```

Cool.

But then:

```text
                 Case Field Accuracy

Sahara              91%
Whisper             73%
MMS                 84%
```

**That is our story.**

Because:

> A speech error isn't equally harmful.

Getting a filler word wrong is different from turning:

> "₦45,000"

into:

> "₦4,500."

Or:

> "He **never** paid me"

into:

> "He paid me."

For institutional workflows, **information preservation matters more than pretty transcripts.**

---

# What about a 4th model?

I'd architect the benchmark code to support it:

```python
MODELS = {
    "sahara": run_sahara,
    "whisper_small": run_whisper,
    "mms_yoruba_english": run_mms,
    # "yecs_whisper": run_yecs_whisper,
}
```

If we have enough time, add:

### **LyngualLabs YECS Whisper-small**

because it's a very strong **code-switch-specialized** baseline. Its model card reports 16.69% WER on its held-out YECS test under its stated normalization. ([Hugging Face][4])

Then we'd have:

```text
1. Sahara
2. Whisper Small
3. MMS-300M Yoruba-English
4. YECS Whisper-small
```

That would be an **excellent benchmark**.

But:

### Don't let model #4 delay the product.

Three properly evaluated models satisfy the rule quoted in the competition requirements. ([Intron Voice AI][1])

---

# My final decision

If you tell me:

> **"Mozzicato, stop giving me options. Pick the models we're actually going to use."**

I'm picking:

### **1. Sahara v2.5**

Required — API.

### **2. OpenAI Whisper Small**

General multilingual baseline — local.

### **3. LyngualLabs MMS-300M Yoruba-English**

African/code-switching specialist — local.

And our primary controlled benchmark is:

> **Yoruba-English AfriSwitch → same audio → all three models → same evaluation → same case compiler.**

Then, **if we have spare time**, add LyngualLabs YECS Whisper-small as Model 4.

That gives us a benchmark that is **fair, technically defensible, relevant to the challenge, and actually runnable on your 8 GB machine.**

[1]: https://www.intron.io/compete/?utm_source=chatgpt.com "Compete » Intron Voice AI"
[2]: https://huggingface.co/LyngualLabs/mms-300m-yoruba-english?library=transformers&utm_source=chatgpt.com "LyngualLabs/mms-300m-yoruba-english · Hugging Face"
[3]: https://huggingface.co/datasets/Kimyayd/vocal-money-codeswitch-asr-benchmark?utm_source=chatgpt.com "Kimyayd/vocal-money-codeswitch-asr-benchmark · Datasets at Hugging Face"
[4]: https://huggingface.co/LyngualLabs/yecs-asr-whisper-plain?utm_source=chatgpt.com "LyngualLabs/yecs-asr-whisper-plain · Hugging Face"
[5]: https://huggingface.co/LyngualLabs/yecs-asr-whisper-lid?utm_source=chatgpt.com "LyngualLabs/yecs-asr-whisper-lid · Hugging Face"
