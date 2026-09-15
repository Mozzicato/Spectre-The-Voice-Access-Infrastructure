# Downstream Benchmark - Institutional Understanding

Same audio, every ASR model, the **same** case compiler. Differences below are
caused by speech recognition, not by the compiler.

`human_reference` compiles the human transcript and is the ceiling: the gap
between it and a model is the downstream cost of that model's ASR errors.

| Model | n | Field acc ↑ | Amounts ↑ | Ref-nums ↑ | Negation ↑ | Case type ↑ | Routing ↑ | Completeness ↑ |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `whisper_large_v3` | 18 | 60.5 | 94.1 | 100.0 | 100.0 | 100.0 | 100.0 | 82.2 |
| `sahara` | 18 | 59.2 | 58.8 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 |
| `whisper_small` | 18 | 48.7 | 82.4 | 100.0 | 100.0 | 83.3 | 83.3 | 69.6 |

All figures are percentages, higher is better.

A model can post a respectable WER and still score badly here: dropping one
negation or one digit of an amount leaves the transcript mostly intact while
making the resulting case file wrong in a way an institution would act on.
