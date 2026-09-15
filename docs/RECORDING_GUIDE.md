# Recording Guide — Voice Access Infrastructure

**Written for: you (and anyone else recording), to produce the downstream evaluation set.**

This is the only part of the build I cannot do for you. Everything else is running in parallel.

---

## The one rule that matters

**Do not read these scripts word-for-word like a newsreader.**

Read the scenario, understand the situation, then **tell me what happened in your own words**, the way you'd tell a friend or complain to someone at a counter. Stumble. Restart a sentence. Say "ehn", "abi", "you know". Pause to think.

Why this matters: the entire thesis of this project is that **people tell stories, institutions need forms**. If you record robotic read-aloud English, we are benchmarking something that doesn't exist in the real world, and any judge who listens will hear it instantly.

The scripts below are **anchors, not scripts**. What you MUST keep are the items in the `MUST SAY` box of each scenario — those are the ground-truth facts my compiler gets scored against. Everything around them is yours.

---

## Setup (5 minutes, once)

| Setting | Value |
|---|---|
| Format | `.wav`, **16 kHz**, **mono**, 16-bit PCM |
| Device | Your phone, held normally (~20–30 cm) |
| Length | **20–60 seconds** each. Hard ceiling 120s — the Sahara API rejects anything longer |
| Speakers | 2 if you can find a second person. If not, 1 is acceptable — I'll report it honestly as a limitation |

If your recorder saves `.m4a` or `.mp3`, that's fine — record first, don't fight the tooling. Drop the files in `data/demo/audio/` and I'll convert everything to 16 kHz mono WAV with one ffmpeg pass.

### Noise conditions — please don't skip this

Record **most scenarios quiet**, but deliberately do **4–5 outdoors or with a fan/traffic/generator running**. The ones marked `noise: street` below.

This is not busywork. The challenge asks for metadata on device and noise conditions, and "does the accuracy gap widen under noise?" is a result worth having. A benchmark recorded entirely in a silent room is a benchmark nobody believes.

### Filenames

```
{scenario_id}_{speaker}.wav
```

Examples: `legal_01_s1.wav`, `legal_01_s2.wav`, `fin_03_s1.wav`

Speaker is `s1` or `s2`. That's the whole convention — I parse the rest from the scenario ID.

---

## Priority — read this before you start

You are short on time. Record in this order and stop whenever you run out of runway:

| Tier | Scenarios | Why | Time |
|---|---|---|---|
| **TIER 1** | `legal_01`, `fin_01`, `pub_01` | **The demo video.** Without these three there is no submission | ~8 min |
| **TIER 2** | The other 6 marked ⭐ | Makes the downstream benchmark statistically meaningful | ~20 min |
| **TIER 3** | Everything else | Strengthens per-domain numbers | ~30 min |

**Record all of TIER 1 first, for both speakers, before touching TIER 2.** If you have 10 minutes, Tier 1 alone still gives us a working submission.

---

## What the `MUST SAY` boxes are for

Each scenario has facts I've deliberately planted. They're chosen to be **exactly the things ASR gets wrong in ways that destroy a case file**:

- **Confusable amounts** — "forty-five thousand" vs "four thousand five hundred". A digit error here is the difference between a real claim and a fabricated one.
- **Negation** — "he *never* paid me". Whisper drops negations under code-switching. A dropped "never" inverts the entire case.
- **Reference numbers** — long digit strings are where every ASR model bleeds.
- **Names and places** — Nigerian proper nouns are the hardest thing on this list for a general-purpose model.
- **Dates** — "since the 3rd of August".

Say them clearly and naturally. **Don't over-enunciate them** — if you slow down artificially for the hard parts you sabotage the experiment, because that's the exact thing we're measuring.

---

## Code-switch density (`CMI`)

Each scenario is tagged **low / medium / heavy**. This lets me reproduce the CMI stratification from the plan on our own data:

- **low** — mostly English, a few Pidgin/Yoruba words dropped in
- **medium** — genuine back-and-forth between both languages
- **heavy** — dense switching, sometimes mid-sentence

Please respect the tag. It's what produces the "what happens as code-switching gets harder?" table, which is the most interesting result in the entire benchmark.

---

# ⚖️ LEGAL

### `legal_01` — Tenancy / eviction · Pidgin-English · **heavy** · quiet · **TIER 1** 🎬

> My landlord dey tell me make I comot for the house, and I never even do anything. I don dey live for that place since 2021. I pay am **two hundred and forty thousand naira** for the year, February. E no give me any notice, e just come knock for my door say make I pack comot before month end. I still get **eight months** wey remain for my rent.

```
MUST SAY
• landlord asked me to leave / comot
• ₦240,000 rent, paid in February
• he gave me NO notice  ← negation, say it clearly
• 8 months remaining on the rent
• I have the rent receipt
```

---

### `legal_02` — Tenancy / deposit · Yoruba-English · **medium** · quiet · ⭐ TIER 2

> Ẹ jọ̀ọ́, I moved out of the apartment for Akoko Road, Yaba, last month. My caution deposit na **one hundred and fifty thousand naira**. Ọ̀gá mi, the landlord, ó ní he will return it, but títí di ìsinsìnyí **he has not paid me anything**. Mo ti call am like six times.

```
MUST SAY
• Akoko Road, Yaba  ← place name
• caution deposit ₦150,000
• he has NOT paid / has not returned it  ← negation
• moved out last month
• called about 6 times
```

---

### `legal_03` — Employment / unpaid wages · Pidgin-English · **heavy** · street 🔊 · ⭐ TIER 2

> I dey work for one company for Ikeja since January. Dem suppose dey pay me **eighty-five thousand** every month. Dem pay me for January and February, but from March till now, **dem never pay me one naira**. I don talk to my supervisor, Mr. Adeyemi, plenty times. E just dey tell me make I dey wait.

```
MUST SAY
• Ikeja  ← place
• ₦85,000 monthly
• paid Jan and Feb, NOT paid from March  ← negation + dates
• supervisor: Mr. Adeyemi  ← name
```

---

### `legal_04` — Employment / wrongful dismissal · Igbo-English · **medium** · quiet

> Biko, they sacked me from my job last week without any warning. I worked there for **three years**, since 2023. Ha ekwughị ihe ọbụla — they didn't give me any query, no warning letter, nothing. They just told me on Friday not to come back on Monday. They still owe me **two months** salary.

```
MUST SAY
• sacked last week, no warning  ← negation
• worked 3 years, since 2023
• no query letter issued  ← negation
• owed 2 months salary
```

---

### `legal_05` — Consumer / defective goods · Pidgin-English · **medium** · quiet

> I buy one generator for Alaba market on the **twelfth of August**. The thing cost me **three hundred and twenty thousand naira**. Before one week finish, e don spoil. I carry am go back, the seller say na my fault. E no gree collect am back, and **e no give me any receipt** when I buy am.

```
MUST SAY
• Alaba market  ← place
• 12th of August  ← date
• ₦320,000
• broke within one week
• NO receipt was given  ← negation + evidence gap
```

---

### `legal_06` — Consumer / service dispute · Yoruba-English · **low** · quiet

> I paid a contractor to fix the roof of my house in Ibadan. We agreed on **one hundred and eighty thousand naira**, and I paid him **half** of it upfront in July. Ó ti pẹ́ — it's been two months and he has not come back to finish the work. He's not picking my calls.

```
MUST SAY
• Ibadan  ← place
• agreed ₦180,000, paid half (₦90,000) upfront
• paid in July
• work NOT finished, 2 months  ← negation
```

---

# 🏦 FINANCIAL

### `fin_01` — Failed transfer · Pidgin-English · **heavy** · quiet · **TIER 1** 🎬

> Yesterday I transfer **forty-five thousand naira** from my GTBank account go my brother account for Access Bank. The money comot for my account, alert enter my phone, but **the person never receive am**. Na since yesterday morning. The transaction reference na **zero nine eight seven six five four three two one**. I don call the bank, dem never do anything.

```
MUST SAY
• ₦45,000  ← say it naturally; "forty-five thousand", NOT "four five"
• GTBank → Access Bank
• debited but recipient did NOT receive  ← negation, the core of the case
• reference: 0987654321  ← read digit by digit, naturally
• yesterday morning
```

> **Why this one is the star of the show:** if a model hears "four thousand five hundred" instead of "forty-five thousand", or drops the "never", the resulting case file is *wrong in a way that matters to a bank*. This single recording is the clearest demonstration of the entire thesis. Record it well.

---

### `fin_02` — Unauthorized debit · Yoruba-English · **medium** · quiet · ⭐ TIER 2

> Owó mi ti lọ — money left my account and **I did not authorize it**. It happened on the **third of September**. They took **seventy-two thousand, five hundred naira**. Mi ò mọ ibi tí ó lọ, I don't know where it went. I got the alert at about 2am while I was sleeping. My bank is Zenith Bank.

```
MUST SAY
• NOT authorized  ← negation
• 3rd of September  ← date
• ₦72,500  ← awkward amount on purpose
• Zenith Bank
• alert came ~2am
```

---

### `fin_03` — Failed ATM withdrawal · Pidgin-English · **heavy** · street 🔊 · ⭐ TIER 2

> I go ATM for Ojuelegba on Saturday, I wan withdraw **twenty thousand**. The machine debit me but **money no comot**. Na three times e do that kind thing — total **sixty thousand** wey dem debit me. I fill the dispute form for the branch on Monday but **dem never reverse am**. Na First Bank.

```
MUST SAY
• Ojuelegba  ← place
• ₦20,000 attempted × 3 = ₦60,000 debited
• debited but NOT dispensed  ← negation
• dispute form filed Monday
• NOT reversed  ← negation
• First Bank
```

---

### `fin_04` — Fraudulent transaction · Igbo-English · **medium** · quiet

> Somebody used my card without my permission. Ego m efuola — I lost **one hundred and ten thousand naira**. It was on the **twenty-eighth of August**, three different transactions. **I was not the one** who did it, I was at work. I reported it to UBA the same day but they have not resolved anything.

```
MUST SAY
• card used without permission
• ₦110,000 total, 3 transactions
• 28th of August  ← date
• I was NOT the one  ← negation
• UBA
• reported same day, NOT resolved  ← negation
```

---

### `fin_05` — Payment dispute / merchant · Pidgin-English · **medium** · quiet

> I order something online, I pay **thirty-five thousand naira** on the **fifth of September**. The seller say e don ship am but **I never receive anything**. Na two weeks now. When I message am for WhatsApp, e block me. I still get the payment receipt and the chat.

```
MUST SAY
• ₦35,000
• 5th of September  ← date
• NOT received  ← negation
• two weeks elapsed
• has payment receipt + chat  ← evidence PRESENT
```

---

### `fin_06` — Loan / overcharge · Hausa-English · **low** · quiet

> I took a loan from one of these mobile apps. The amount was **fifty thousand naira**, and they said I would pay back **sixty-two thousand**. But when it was time, they deducted **eighty-nine thousand** from my account. Kudi na ya yi yawa — it's too much. **They did not explain** the extra charges.

```
MUST SAY
• borrowed ₦50,000, agreed repayment ₦62,000
• actually deducted ₦89,000  ← three amounts, deliberately confusable
• NOT explained  ← negation
```

---

# 🏛️ PUBLIC SERVICE

### `pub_01` — Streetlight failure · Yoruba-English · **heavy** · quiet · **TIER 1** 🎬

> This streetlight don spoil for almost **three weeks** now for our street, Adeniyi Jones, Ikeja. Kò sí ìmọ́lẹ̀ rárá — there's no light at all, and the place don dark well well. Mo ti report é sí local government **two times** but **won ò ṣe nkankan**, they have not done anything. Àwọn ọmọ jáǹdùkú ti bẹ̀rẹ̀ sí í — armed robbers don start to dey operate for there. Last week dem rob two people.

```
MUST SAY
• Adeniyi Jones, Ikeja  ← place
• broken ~3 weeks  ← duration
• reported to local government 2 times  ← previous reports
• nothing done  ← negation
• impact: robberies, 2 people robbed last week
```

---

### `pub_02` — Water supply · Pidgin-English · **medium** · street 🔊 · ⭐ TIER 2

> Water never run for our area since **the beginning of August**. Na Water Corporation suppose dey supply us. We don write letter, we don go their office for **three different times**, dem no do anything. Now everybody dey buy water for **five hundred naira** per jerrican. E dey affect the whole street, like **forty houses**.

```
MUST SAY
• no water since beginning of August  ← negation + date
• Water Corporation  ← agency
• 3 visits to their office  ← previous action
• ₦500 per jerrican
• ~40 houses affected  ← impact
```

---

### `pub_03` — Road / drainage · Pidgin-English · **heavy** · street 🔊 · ⭐ TIER 2

> The road wey dey lead to our area for Ajegunle don bad since last year rainy season. The drainage block, so anytime rain fall, water go enter people house. Last month e damage plenty property. We don report to the local government **since March**, **dem never come even look am**. Na about **two hundred** families dey affected.

```
MUST SAY
• Ajegunle  ← place
• bad since last rainy season, reported since March  ← dates
• blocked drainage → flooding into homes
• NOT inspected / nobody came  ← negation
• ~200 families  ← impact
```

---

### `pub_04` — Electricity / billing · Igbo-English · **medium** · quiet

> They brought a bill of **forty-eight thousand naira** for last month, but we only had light for about **six days** in that whole month. Ọ bụghị eziokwu — it's not correct. This is estimated billing, **we don't have a prepaid meter**. We applied for a meter since **January** and they have not given us one.

```
MUST SAY
• bill ₦48,000
• only ~6 days of supply
• NO prepaid meter  ← negation
• applied since January, NOT given  ← negation + date
```

---

### `pub_05` — Waste / sanitation · Yoruba-English · **medium** · street 🔊

> Àwọn tí ń kó pàǹtí — the waste collectors have not come to our street for **over a month**. Ìdọ̀tí ti kún — the refuse don pile up everywhere, and e don dey smell. We dey pay **two thousand naira** every month for that service. Mo ti pe wọ́n — I called them **four times**, nobody answered.

```
MUST SAY
• waste NOT collected for over a month  ← negation + duration
• paying ₦2,000/month for the service
• called 4 times, no answer  ← previous action + negation
```

---

### `pub_06` — Health facility / service · Hausa-English · **low** · quiet

> I went to the primary health centre in our area **three times** this month and there was **no doctor on duty**. The last time was on the **ninth of September**. They told me to come back the next day, and when I came back, still nobody. Ba likita — no doctor. People are coming from far places to use this centre.

```
MUST SAY
• primary health centre
• visited 3 times this month
• NO doctor on duty  ← negation
• 9th of September  ← date
```

---

## After you record

Drop every file into:

```
data/demo/audio/
```

Then **just tell me they're there.** Don't bother making the metadata CSV — I generate it from the filenames plus this document, and I'll transcribe and build the ground-truth case JSONs myself.

---

## If you're running out of time

Record **`legal_01`, `fin_01`, `pub_01`** with one speaker. Three files, about 8 minutes.

That is enough for a complete demo video and a working end-to-end submission. Everything above Tier 1 makes the benchmark stronger, not possible.

---

## A note on consent

If you record a second speaker, tell them plainly: this audio is for a hackathon prototype and its benchmark, it isn't a real legal or financial record, and it may appear in a demo video and a public repository. If they'd rather it not be published, record them anyway for the benchmark and keep them out of the video — I'll handle that split.

The scenarios above are **fictional**. Please don't use real account numbers, real case details, or a real person's name.
