# Responsible AI

Submission note on consent, privacy, safety, inclusion and limitations.

This system handles accounts of evictions, unpaid wages, stolen money and failing public
services — told by people who are usually already in a weak position relative to the
institution they are dealing with. The design decisions below follow from that.

---

## 1. What this system is, and is not

**It is** a translation layer that converts a spoken account into a structured case
record, identifies what information an institution would still need, and recommends a
workflow.

**It is not** a lawyer, an adjudicator, a bank, or a government portal. It makes no
determination of fault, liability or entitlement, and it does not file anything with any
real institution.

Every case packet ships with this, inline:

> This packet records what the speaker reported. It is not legal, financial or medical
> advice, and it contains no determination of fault or entitlement. It has not been
> submitted to any external institution.

---

## 2. Reported vs. concluded — enforced, not aspirational

The single largest safety risk in a system like this is quietly promoting a **claim**
into a **finding**.

| ❌ Never | ✅ Always |
|---|---|
| "Your landlord illegally evicted you." | "You reported that your landlord asked you to leave before your stated rental period ended." |
| "The bank stole your money." | "You reported a debit of ₦45,000 that the recipient says was not received." |
| "You are entitled to two months' salary." | "You reported that two months' salary remains unpaid." |

This is enforced in three places:

1. The extraction prompt in [`app/compiler.py`](../app/compiler.py) forbids legal or
   factual determinations explicitly.
2. The case packet stores extracted content under the key **`user_reported`** — the data
   structure itself refuses to describe the content as established fact.
3. Routing is **rule-based** ([`app/routing.py`](../app/routing.py)). An LLM is never
   asked which agency handles a complaint, because a hallucinated agency name in a case
   file is actively harmful.

---

## 3. Hallucination control

An institutional case built on invented details is worse than no case at all — it wastes
the time of an already-scarce reviewer and can damage the claimant's credibility.

- The extractor is instructed that a detail not present in the transcript **stays null**
  and is named in `missing_information`. Absence is recorded, never filled in.
- Missing-field detection is **recomputed independently** of what the model claims is
  missing. The model's own list is merged in only for fields the schema marks required.
- The transcript is treated as **imperfect by default**. The prompt states that the input
  comes from a speech model and that suspected mis-transcriptions must lower `confidence`
  rather than be silently repaired into a confident claim.
- Every packet carries `confidence`, the `extractor` that produced it, and any
  `warnings`.
- A cross-check flags any transcript containing negation that produced no claim — the
  signature of a dropped "never".

---

## 4. Negation as a safety property

"He never paid me" and "he paid me" are opposite cases. Under Word Error Rate they differ
by a single token; in an institutional record they are contradictory.

Negation integrity is therefore measured as a **first-class benchmark metric** at both
levels, not treated as an ordinary word error. Speech models that drop negations under
heavy code-switching are identified as such in the results.

---

## 5. Privacy and data handling

| Stage | Practice |
|---|---|
| Consent | Speakers are told the recording is for a prototype and its benchmark, may appear in a demo video and a public repository, and can decline |
| Processing | Audio is converted and transcribed; API calls go only to the configured speech/LLM provider |
| Retention | Benchmark audio is cached locally under `data/cache/` for reproducibility. Live UI audio is written to a temp directory and deleted when the request completes |
| Training | **No user submission is used to train anything.** No model in this project is fine-tuned on any user or demo data |
| Secrets | Keys live in `.env`, which is gitignored. `.env.example` documents the names only |
| Deletion | Local-first by design: deleting `data/` removes every recording and derived case |

The demo scenarios in [`RECORDING_GUIDE.md`](RECORDING_GUIDE.md) are **fictional**.
Speakers are instructed not to use real account numbers, real case details or real
third-party names.

**A caution we state plainly:** transcription and extraction are performed by third-party
APIs (Intron, and whichever LLM provider is configured). Anyone deploying this for real
casework must review those providers' data-retention terms and obtain informed consent
that names them. Nothing in this prototype should be read as a claim that a production
deployment would be compliant by default.

---

## 6. Inclusion and bias

The project exists because form-based systems exclude people who don't speak the
institution's dialect of the institution's language.

- **Code-switching is the target, not an error case.** Pidgin, Yoruba-English,
  Igbo-English and Hausa-English are first-class inputs.
- **Speakers are not corrected.** The extraction prompt forbids "sanitising" Pidgin or
  Yoruba into different claims.
- **Bias is measured, not assumed away.** Results are stratified by language and by
  code-mixing intensity, so a model that degrades as code-switching increases is visible
  rather than hidden inside an average.
- **Known coverage gap, stated:** Whisper has no Nigerian Pidgin language token, so
  Pidgin is submitted as English. MMS-300M covers Yoruba-English only and is scored only
  on Yoruba. Both are reported rather than papered over.
- Dual diacritic-sensitive and diacritic-insensitive scoring avoids penalising or
  rewarding a model purely for its orthographic convention.

---

## 7. Benchmark integrity

Overstating results is its own ethical failure, particularly in a competition.

- Inference and evaluation are separate programs; every number in `reports/` is
  recomputed from cached model outputs and reproducible from them.
- **No result is ever fabricated or estimated.** Unfilled tables stay unfilled.
- Confidence intervals are reported so small differences are not read as findings.
- Models are only scored on languages they are designed for.
- **Cases compiled by the rule-based fallback are excluded from downstream scoring.**
  During development, an LLM rate-limit silently degraded one batch and made a model
  appear ~36 points worse. An infrastructure failure must never be reportable as a model
  result, so the harness now drops those rows and says so loudly.

---

## 8. Human in the loop

The output is a case packet **for a human reviewer**, not an automated decision.

- A case is marked `ready_for_review`, never `approved` or `valid`.
- `completeness` below 75%, or any missing required field, flags the packet as
  `incomplete`.
- Outstanding questions are surfaced rather than guessed at.
- Evidence is tracked in three states — mentioned, supplied, outstanding — so a reviewer
  can see what is claimed versus what is actually attached.

---

## 9. Limitations we are not hiding

1. The downstream evaluation set is **small and self-recorded**, with few speakers. It
   demonstrates a measurement method; it does not support population-level claims.
2. Scenarios are fictional and were produced by the team, which introduces our own
   framing into the vocabulary.
3. Routing targets are workflow names, not live institutional endpoints.
4. Rule-based extraction is materially weaker than LLM extraction; packets it produces
   say so.
5. The system has not been tested with users in genuine distress, and no claim is made
   about its suitability for that setting without further research and safeguarding.
6. Speech and language models carry their own upstream biases, which this project
   measures but does not correct.

---

*Prototype built for the Sahara CodeSwitch Africa Challenge. Not a production legal,
financial or government system.*
