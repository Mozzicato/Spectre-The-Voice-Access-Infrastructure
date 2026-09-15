# Demo Video Guide

**Written for: you, recording the submission video.**

Target length **3–4 minutes**. The judging weights are published, so this script is built
around them rather than around the product tour you'd normally give:

| Weight | Criterion | Where it lands in this script |
|--:|---|---|
| **30%** | Code-Switching Benchmark Quality | Scenes 4–6 — the largest block, deliberately |
| 25% | Product Quality & Fit | Scenes 2–3 |
| 20% | Real-World Impact | Scene 1 |
| 15% | Technical Execution | Scene 7 |
| 10% | Ethics / Safety / Inclusion | Scene 6 (fused with the benchmark finding) |

Benchmark quality is the single biggest slice. **Do not spend three minutes on the UI.**

---

## Before you hit record

```bash
cd "spectre-the_voice_infrastructure"
python -m uvicorn app.server:app --port 8000
```

Open `http://localhost:8000`. Check:

- [ ] Mic permission granted in the browser
- [ ] `data/demo/audio/` has your recordings (for the upload fallback)
- [ ] These tabs open and ready: the UI, `reports/downstream/DOWNSTREAM.md`,
      `reports/downstream/FAILURE_ANALYSIS.md`, `reports/afriswitch/RESULTS.md`
- [ ] A terminal with the project open
- [ ] Close Slack/email notifications

**Record in one take if you can.** Screen + voiceover. OBS, Loom or the Xbox Game Bar
(`Win+G`) all work.

---

## Scene 1 — The problem (0:00–0:30)

Open on the UI's landing state.

> "People don't speak in forms. They speak in stories — and in Nigeria, they
> code-switch while doing it.
>
> A tenant facing eviction doesn't arrive with a structured claim. He says:
> *'My landlord dey tell me make I comot for the house, I pay am two hundred and forty
> thousand naira for the year, e no give me any notice.'*
>
> Everything a legal aid officer needs is in that sentence. It's just not in a shape any
> institution accepts. Today you need a human intermediary to bridge that — and if you
> don't have one, you drop out of the process."

**Then state the thesis plainly:**

> "We built the translation layer. Speech in, structured institutional case out."

---

## Scene 2 — Live demo, financial (0:30–1:15)

**This is the one to get right.** Use `fin_01` — Pidgin-English, failed transfer.

Either tap the mic and speak it yourself, or upload `data/demo/audio/fin_01_s1.m4a`.

While it processes, say:

> "That's Nigerian Pidgin going to Intron Sahara v2.5."

When the case appears, **point at the screen and name what survived**:

> "Amount — forty-five thousand. Both banks. The transaction reference, ten digits. And
> the negation: *never received*. That one word is the difference between a dispute and a
> receipt.
>
> It's classified as a failed transfer and routed to the bank dispute workflow. Not a
> transcript — a case."

Then point at the amber block:

> "And look at this. The system will not treat that amount as settled. It asks."

**Don't explain why yet.** That's Scene 6, and the setup is worth more than the payoff
here.

---

## Scene 3 — Same infrastructure, different domain (1:15–1:45)

Go fast. Upload `pub_01_s1.m4a` (Yoruba-English streetlight).

> "Different language pair, different domain, same system."

When it resolves:

> "Yoruba-English this time. Street name, three weeks' duration, two prior reports to the
> local government, and the impact — robberies. Routed to the LGA works department.
>
> Same compiler engine. Only the schema changed. That's the infrastructure claim: adding
> a vertical means adding a schema, not building another app."

If time is tight, mention `legal_01` rather than running it.

---

## Scene 4 — The benchmark, Level 1 (1:45–2:25)

**Switch to the results.** This is the 30% block — slow down here.

Open `reports/afriswitch/RESULTS.md`.

> "We benchmarked three speech models: Sahara v2.5, Whisper large-v3 and Whisper small.
>
> On twenty-five AfriSwitch Yoruba clips with human reference transcripts, Sahara wins
> decisively — fifty-seven-point-five WER against eighty-seven-point-eight. The
> confidence intervals don't overlap."

Then the methodology point, which is what actually separates this benchmark:

> "But here's what we'd have got wrong with a single WER number.
>
> Sahara writes correct Yoruba — `Ìwọ ni problem mi`, with the tone marks. The AfriSwitch
> human reference is un-diacritized: `Iwo ni problem mi`. So under diacritic-sensitive
> scoring, Sahara is *penalised for being more correct* — twenty-five points of its WER is
> orthography, not recognition.
>
> That's why we report three normalization schemes and name the one every number came
> from."

---

## Scene 5 — The benchmark, Level 2 (2:25–3:00)

Open `reports/downstream/DOWNSTREAM.md`.

> "But WER measures transcripts. We don't ship transcripts — we ship cases. So we ran the
> same audio through every model into the *same* compiler."

Point at the case-type and routing columns:

> "Sahara and Whisper large-v3 both classify and route a hundred percent of cases
> correctly. Whisper small drops to eighty-three.
>
> Large-v3 and small are the same architecture — so that gap is capacity, isolated from
> code-switch training. ASR quality does break the downstream task, but only past a
> threshold."

Open `FAILURE_ANALYSIS.md`:

> "And the two strong models fail in opposite directions. Sahara keeps ninety-five percent
> of negations but only fifty-nine percent of naira amounts. Whisper is the reverse —
> ninety-four percent of amounts, seventy-nine percent of negations.
>
> Sahara drops a zero: two hundred and forty thousand becomes twenty-four thousand."

---

## Scene 6 — Measurement became a safety feature (3:00–3:30)

**The strongest 30 seconds in the video.** Go back to the amber block from Scene 2.

> "So come back to that confirmation prompt.
>
> No speech model is safe on amounts, and the two models fail on *different* scenarios —
> so picking a better model doesn't fix it. And a dropped zero produces a transcript that
> still reads perfectly fluently. Nothing downstream can detect it.
>
> So the system stops pretending. Amounts and reference numbers are held at
> `awaiting_confirmation` and read back to the speaker before anything acts on them.
>
> We measured a failure and turned it into a safety rule."

Add the ethics line here rather than as a separate scene:

> "Everything is filed under `user_reported`. The system never says *you were illegally
> evicted* — it says *you reported that your landlord asked you to leave*. Routing is
> rule-based, so no agency name is ever hallucinated. And it submits nothing to any real
> institution — it says so on every packet."

---

## Scene 7 — Technical execution (3:30–3:50)

Terminal:

```bash
python scripts/selftest.py
```

> "The measurement layer tests itself. Every check here is a scoring bug we actually hit —
> including one where Whisper was right and *our scorer* was wrong, and one where an LLM
> rate-limit silently made a model look thirty-six points worse. We found four of those.
> Each would have published a wrong number rather than crashed.
>
> Inference and evaluation are separate programs. Runs are resumable. Every figure is
> recomputed from cached outputs."

---

## Close (3:50–4:00)

> "One voice layer. Three compilers. The speech model is swappable — the benchmark is how
> we chose it, and what we refuse to trust it with.
>
> Voice Access Infrastructure."

---

## Fallbacks if something breaks live

| If | Do this |
|---|---|
| Mic fails | Use the file picker — recordings are in `data/demo/audio/` |
| Sahara is slow | Say "that's a live API call" — the honest latency is a result, not a flaw |
| Sahara errors | Switch the model dropdown to `whisper_large_v3`, and *say* you're switching — it demonstrates the swappable layer |
| Everything fails | `python scripts/demo.py data/demo/audio/fin_01_s1.m4a --model sahara --language pidgin` |

---

## Things not to do

- **Don't read the tables aloud row by row.** Name the one number that matters per table.
- **Don't apologise for WER being high.** AfriSwitch is spontaneous heavy code-mixing;
  57% is the honest difficulty of the task, and saying so confidently reads as rigour.
- **Don't claim four models.** Three are benchmarked. MMS is implemented but never
  produced results, and the docs say so.
- **Don't oversell routing.** It produces a workflow recommendation, not a filed case.
- **Don't skip Scene 6.** It's the strongest thing you built.

---

## The one sentence to land

If a judge remembers a single line, make it this:

> **"We measured a failure in the speech model and turned it into a safety rule in the
> product."**
