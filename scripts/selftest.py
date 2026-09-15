"""Self-test for the measurement layer.

    python scripts/selftest.py

Every case here is a bug that was actually hit while building the benchmark, and each one
would have produced a WRONG published number rather than a crash. That is what makes them
worth pinning: a scoring bug does not announce itself, it just quietly reports the wrong
winner.

No pytest dependency - runs anywhere the project runs. Exit code 1 on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402,F401  (configures UTF-8 stdout)
from app.normalize import (  # noqa: E402
    negation_markers,
    normalize_loose,
    normalize_numeric,
    normalize_strict,
    spoken_digit_strings,
    spoken_numbers_to_values,
)

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if not ok:
        print(f"          got  {got!r}\n          want {want!r}")
        FAILURES.append(label)


def check_true(label: str, got: bool) -> None:
    check(label, bool(got), True)


def main() -> int:
    print("\n-- amounts ------------------------------------------------------")
    # The core distinction the whole project turns on.
    check("forty-five thousand != four thousand five hundred",
          (spoken_numbers_to_values("forty-five thousand"),
           spoken_numbers_to_values("four thousand five hundred")),
          ([45000], [4500]))
    # Regression: comma groups were split into two numbers by punctuation stripping.
    check("comma thousands", spoken_numbers_to_values("240,000 naira"), [240000])
    check("comma millions", spoken_numbers_to_values("1,234,567"), [1234567])
    # Regression: Whisper writes "45 000"; this parsed as [45, 0] and reported a FALSE
    # amount failure against a transcript that was actually correct.
    check("space thousands", spoken_numbers_to_values("i transfer 45 000 naira"), [45000])
    # ...but a year followed by a count must NOT be glued together.
    check("year + count left alone",
          spoken_numbers_to_values("since 2021 240 families"), [2021, 240])

    print("\n-- reference numbers --------------------------------------------")
    check("spelled out digits",
          spoken_digit_strings("reference na zero nine eight seven six five four three two one"),
          ["0987654321"])
    # Regression: Sahara returns the reference as "09876543 21". All ten digits are
    # correct, so counting it as a loss scores typography, not recognition.
    check_true("split digit run rejoined",
               "0987654321" in spoken_digit_strings("reference na 09876543 21"))
    # A read-out reference must never be summed into a nonsense amount.
    check("digit run not summed as an amount",
          spoken_numbers_to_values("reference na zero nine eight seven six five four three two one"),
          [])

    print("\n-- diacritics ---------------------------------------------------")
    # Regression: a naive [^\w\s] stripped tone marks AND split the word in two.
    check("tone marks preserved under strict", normalize_strict("ṣùgbọ́n"), "ṣùgbọ́n")
    check("tone marks stripped under loose", normalize_loose("ṣùgbọ́n"), "sugbon")
    check("sub-dots stripped under loose", normalize_loose("Ẹ jọ̀ọ́ ṣe"), "e joo se")

    print("\n-- number-canonical scheme --------------------------------------")
    # Verified against the live Sahara API: it returns digits where a human transcriber
    # spells numbers out. Under plain WER that costs it errors for being MORE useful.
    human = ("I transferred forty five thousand naira but the person never received it. "
             "The reference is zero nine eight seven six five four three two one.")
    model = ("I transferred 45,000 naira but the person never received it "
             "The reference is 0987654321")
    check_true("spelled and digit forms differ under loose",
               normalize_loose(human) != normalize_loose(model))
    check("spelled and digit forms match under numeric",
          normalize_numeric(human), normalize_numeric(model))

    print("\n-- negation -----------------------------------------------------")
    check_true("negation detected", negation_markers("he never paid me") > 0)
    check("no false negation", negation_markers("he paid me"), 0)
    check_true("pidgin negation detected", negation_markers("e no gree collect am") > 0)
    check_true("dropped negation is visible to the scorer",
               negation_markers("the person never receive am")
               > negation_markers("the person receive am"))

    print("\n-- schemas ------------------------------------------------------")
    from app import schemas
    for key, schema in schemas.SCHEMAS.items():
        check_true(f"{key}: has required fields", len(schema.required_fields) > 0)
        check_true(f"{key}: every case type routes",
                   all(ct in schema.routes for ct in schema.case_types))
        props = schema.json_schema()["properties"]
        check_true(f"{key}: json schema covers every field",
                   all(f.name in props for f in schema.fields if f.name != "case_type"))

    print("\n-- routing safety -----------------------------------------------")
    from app.compiler import CompiledCase
    from app.routing import build_packet
    case = CompiledCase(domain="financial", case_type="failed_transfer",
                        fields={"amount": 45000, "transaction_reference": "0987654321"},
                        transcript="t", extractor="test")
    packet = build_packet(case)
    # Measured: amount preservation is 58.8% / 94.1% across models, failing on different
    # scenarios. No model is safe, so extracted amounts must never be treated as settled.
    check_true("amount flagged for confirmation",
               any(c["field"] == "amount" for c in packet["verification_required"]))
    check_true("reference flagged for confirmation",
               any(c["field"] == "transaction_reference"
                   for c in packet["verification_required"]))
    check_true("unconfirmed case is not ready_for_review",
               packet["status"] != "ready_for_review")
    check_true("packet carries a disclaimer", bool(packet["disclaimer"]))
    check_true("content filed under user_reported, not as fact",
               "user_reported" in packet)

    print("\n" + "=" * 66)
    if FAILURES:
        print(f"  {len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(f"    - {f}")
        return 1
    print("  all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
