"""Text normalization for code-switched ASR scoring.

This module is the methodological centre of the benchmark, so it is deliberately
explicit rather than clever.

Yoruba orthography uses sub-dot characters (e-dot-below, o-dot-below, s-dot-below) and
three tone marks. Whether those are preserved or stripped before scoring can move WER by
tens of points, and it systematically favours whichever model happens to match the choice:
a model that emits bare ASCII looks terrible under a diacritic-sensitive scheme and fine
under a stripped one, regardless of whether it understood the speech.

Publishing a single WER number without stating the scheme is therefore not a result.
We report BOTH:

    strict  - diacritics preserved (rewards correct Yoruba orthography)
    loose   - diacritics and tone marks stripped (measures segmental accuracy only)

Neither is "the" right answer. Reporting both is what makes the comparison honest.
"""
from __future__ import annotations

import re
import unicodedata

# --- Yoruba sub-dot characters, mapped to their bare Latin base ---
# These are distinct letters in Yoruba, not accents, so NFD alone will not remove
# all of them consistently across the different ways models encode them.
_SUBDOT = {
    "ẹ": "e",  # e with dot below
    "Ẹ": "E",
    "ọ": "o",  # o with dot below
    "Ọ": "O",
    "ṣ": "s",  # s with dot below
    "Ṣ": "S",
    "̣": "",   # combining dot below
}

# Currency and filler noise that no ASR system agrees on.
_CURRENCY = {
    "₦": " naira ",  # naira sign
    "£": " pounds ",
    "$": " dollars ",
}

# \w does not match combining marks, so a naive [^\w\s] strips Yoruba tone marks
# AND splits the word in two. Combining marks U+0300-U+036F are explicitly kept.
_PUNCT = re.compile(r"[^\w\s̀-ͯ]", flags=re.UNICODE)
# 45,000 -> 45000 before punctuation stripping, else it becomes two numbers.
_DIGIT_GROUP = re.compile(r"(?<=\d),(?=\d\d\d(?!\d))")
# Whisper renders thousands with a space ("45 000"). Without this the parser reads
# that as [45, 0] and reports a FALSE amount failure against a correct transcript.
# Restricted to 1-3 digits + exactly 3 digits so "since 2021 240" is left alone.
_DIGIT_SPACE = re.compile(r"(?<!\d)(\d{1,3}) (\d{3})(?!\d)")
_WS = re.compile(r"\s+")

# Disfluencies. Removed in both schemes: every model transcribes them differently and
# they carry no institutional information.
_FILLERS = {
    "uh", "um", "erm", "eh", "ehn", "hmm", "mm", "mmm", "ah", "abi", "sha",
}


def _strip_combining(text: str) -> str:
    """Remove combining marks (tone marks) after NFD decomposition."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _base(text: str) -> str:
    """Shared front half of both schemes."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _DIGIT_GROUP.sub("", text)
    for _ in range(2):  # 1 234 567 needs two passes
        text = _DIGIT_SPACE.sub(lambda m: m.group(1) + m.group(2), text)
    for src, dst in _CURRENCY.items():
        text = text.replace(src, dst)
    text = text.lower()
    text = _PUNCT.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def _drop_fillers(text: str) -> str:
    return " ".join(w for w in text.split() if w not in _FILLERS)


def normalize_strict(text: str) -> str:
    """Diacritic-preserving. Correct Yoruba orthography is rewarded."""
    return _drop_fillers(_base(text))


def normalize_loose(text: str) -> str:
    """Diacritic-insensitive. Measures segmental accuracy only."""
    text = _base(text)
    text = "".join(_SUBDOT.get(ch, ch) for ch in text)
    text = _strip_combining(text)
    text = "".join(_SUBDOT.get(ch, ch) for ch in text)
    text = _WS.sub(" ", text).strip()
    return _drop_fillers(text)


def normalize_numeric(text: str) -> str:
    """Diacritic-insensitive AND number-canonical.

    Verified against the live Sahara API: it returns "45,000" and "0987654321" where a
    human transcriber writes "forty five thousand" and "zero nine eight seven...".
    Under plain WER that costs Sahara several word errors for being MORE useful, which
    would be an artefact of formatting conventions rather than a measure of recognition.

    This scheme maps both renderings to the same token, so the comparison measures
    whether the number was heard correctly, not how it was typeset.
    """
    text = normalize_loose(text)
    text = _DIGIT_RUN.sub(
        lambda m: " " + "".join(_SINGLE_DIGIT[w] for w in m.group(0).split()) + " ", text
    )

    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        values = spoken_numbers_to_values(" ".join(buf))
        if values:
            out.extend(str(v) for v in values)
        else:
            out.extend(buf)
        buf.clear()

    for token in text.split():
        if token in _NUM_WORDS or token in _SCALES or (token == "and" and buf):
            buf.append(token)
        else:
            flush()
            out.append(token)
    flush()

    return _WS.sub(" ", " ".join(out)).strip()


SCHEMES = {
    "strict": normalize_strict,
    "loose": normalize_loose,
    "numeric": normalize_numeric,
}


# --- number handling, used for entity-level scoring rather than WER ---

_NUM_WORDS = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}

# Digits as read out one by one, e.g. a transaction reference or a phone number.
# Bare "o" is excluded: Yoruba "o" would otherwise manufacture false digit runs.
_SINGLE_DIGIT = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
_DIGIT_RUN = re.compile(
    r"\b(?:" + "|".join(_SINGLE_DIGIT) + r")(?:\s+(?:" + "|".join(_SINGLE_DIGIT) + r")){3,}\b"
)


def spoken_digit_strings(text: str, min_len: int = 4) -> list[str]:
    """Extract read-out digit sequences such as transaction references.

    'zero nine eight seven six five four three two one' -> ['0987654321'].

    Long digit strings are where every ASR system bleeds most, and a wrong transaction
    reference makes a dispute unactionable no matter how good the rest of the transcript
    is. Scoring these separately is the point.
    """
    flat = _base(text.replace("-", " "))
    out: list[str] = []

    for match in _DIGIT_RUN.finditer(flat):
        out.append("".join(_SINGLE_DIGIT[w] for w in match.group(0).split()))

    for raw in re.findall(r"\d{%d,}" % min_len, flat):
        out.append(raw)

    # Models break long digit strings at arbitrary points: Sahara returns the verified
    # reference 0987654321 as "09876543 21". All ten digits are correct, so counting that
    # as a loss would score typography rather than recognition. Adjacent digit groups are
    # therefore also offered joined. Scoring is recall against an expected value, so an
    # extra candidate can never create a false match.
    for run in re.finditer(r"\d+(?:\s+\d+)+", flat):
        joined = re.sub(r"\s+", "", run.group(0))
        if len(joined) >= min_len:
            out.append(joined)

    return out


def spoken_numbers_to_values(text: str) -> list[int]:
    """Extract numeric values from text, whether written as digits or words.

    'forty-five thousand naira' and '45,000' both yield [45000], so an amount can be
    compared across models that spell numbers differently. This is what lets us ask
    whether a model preserved the AMOUNT, independently of how it rendered it.
    """
    text = _base(text.replace("-", " "))
    # A read-out reference number ("zero nine eight seven ...") must not be summed
    # into a nonsense amount. Strip those runs out and score them separately.
    text = _DIGIT_RUN.sub(" ", text)
    values: list[int] = []

    for raw in re.findall(r"\d[\d,]*", text):
        try:
            values.append(int(raw.replace(",", "")))
        except ValueError:
            pass

    current = 0
    running = 0
    seen = False
    for word in text.split():
        if word in _NUM_WORDS:
            current += _NUM_WORDS[word]
            seen = True
        elif word in _SCALES:
            scale = _SCALES[word]
            if scale == 100:
                current = max(current, 1) * 100
            else:
                running += max(current, 1) * scale
                current = 0
            seen = True
        elif word == "and" and seen:
            continue
        else:
            if seen:
                total = running + current
                if total:
                    values.append(total)
            current = running = 0
            seen = False

    if seen:
        total = running + current
        if total:
            values.append(total)

    return values


_NEGATIONS = {
    # English
    "not", "no", "never", "nothing", "nobody", "none", "without", "didnt", "dont",
    "doesnt", "hasnt", "havent", "wont", "cant", "couldnt", "wouldnt", "isnt",
    "arent", "wasnt", "werent",
    # Nigerian Pidgin
    "neva", "nofi", "noo",
    # Yoruba / Igbo / Hausa negation particles
    "ko", "kii", "ma", "ghi", "ba", "bai",
}


def negation_markers(text: str) -> int:
    """Count negation markers.

    A dropped 'never' inverts a case ('he never paid me' -> 'he paid me'), which is a
    far more damaging error than an equivalent number of wrong filler words. WER treats
    those identically; this does not.
    """
    words = normalize_loose(text).split()
    joined = " ".join(words)
    count = sum(1 for w in words if w in _NEGATIONS)
    count += len(re.findall(r"\bno\s+(?:gree|be|dey|come|fit)\b", joined))
    return count
