"""Numeric verifier (task 3.11): no unverified number reaches the user.

Every number in a draft answer must match one of:

- a result value, under the registry rounding rule of its metric;
- a resolved argument (seasons, dates, "top 5"), by value or as a whole season or date token;
- for knowledge answers, a number written in a cited glossary chunk.

If any number fails, the answer is regenerated once. If it fails again, the user gets the
result table with a one-line summary, never the draft. Spelled-out numbers ("thirty-one") are
checked too, so a number cannot slip past by being written as words.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from metrics.rounding import Stated, extract, matches
from metrics.schema import Rounding

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_WORD_NUM = re.compile(
    r"\b("
    + "|".join(_TENS)
    + r")(?:[- ]("
    + "|".join(_UNITS)
    + r"))?\b|\b("
    + "|".join(_UNITS)
    + r")\b",
    re.IGNORECASE,
)
# Words that are numbers in form but not claims ("one of the best", "a three-pointer").
_NOT_CLAIMS = re.compile(
    r"\b(one of|no one|someone|anyone|everyone|one-on-one|three-point(?:er)?s?|"
    r"two-point(?:er)?s?|three-pointers?|triple-doubles?|double-doubles?)\b",
    re.IGNORECASE,
)


def words_to_digits(text: str) -> str:
    """Rewrite spelled-out numbers as digits, leaving idioms such as "one of" alone."""
    keep = [(m.start(), m.end()) for m in _NOT_CLAIMS.finditer(text)]

    def repl(m: re.Match[str]) -> str:
        if any(a <= m.start() < b for a, b in keep):
            return m.group(0)
        if m.group(3):
            return str(_UNITS[m.group(3).lower()])
        return str(_TENS[m.group(1).lower()] + (_UNITS[m.group(2).lower()] if m.group(2) else 0))

    return _WORD_NUM.sub(repl, text)


@dataclass(frozen=True)
class ResultValue:
    value: float
    rounding: Rounding


@dataclass(frozen=True)
class Evidence:
    values: Sequence[ResultValue] = ()
    args_text: Sequence[str] = ()  # resolved arguments as text: "2025-26", "top 5", "2026-04-12"
    chunks: Sequence[str] = ()  # cited glossary chunk texts (knowledge answers)


@dataclass(frozen=True)
class Check:
    ok: bool
    unmatched: list[str] = field(default_factory=list)
    numbers: int = 0


def _allowed_literal(s: Stated, literal: list[Stated]) -> bool:
    for a in literal:
        if s.token or a.token:
            if s.token and a.token and s.text == a.text:
                return True
            continue
        if s.value == a.value or abs(s.value) == abs(a.value):
            return True
    return False


# Quantity words with no digits attached are claims too ("a dozen", "hundreds of points").
_SCALE_WORDS = re.compile(
    r"(?<![\d.,])(?<![\d.,]\s)\b(dozens?|hundreds?|thousands?|millions?|billions?)\b",
    re.IGNORECASE,
)


def check(draft: str, ev: Evidence) -> Check:
    text = words_to_digits(draft)
    stated = extract(text)
    literal: list[Stated] = []
    for t in [*ev.args_text, *ev.chunks]:
        literal += extract(t)
    unmatched = []
    for s in stated:
        if not s.token and any(matches(s, v.value, v.rounding) for v in ev.values):
            continue
        if not s.exotic and _allowed_literal(s, literal):
            continue
        unmatched.append(s.text)
    unmatched += [m.group(0) for m in _SCALE_WORDS.finditer(text)]
    return Check(not unmatched, unmatched, len(stated))


@dataclass(frozen=True)
class Final:
    text: str
    status: Literal["verified", "regenerated", "fallback"]
    unverified_shown: int  # always 0: the verifier never shows an unmatched number
    first_check: Check


def finalize(
    generate: Callable[[list[str] | None], str],
    ev: Evidence,
    fallback: Callable[[], str],
) -> Final:
    """Generate, verify, regenerate once with feedback, else fall back to the result table.

    ``generate(feedback)`` returns a draft; on the retry, ``feedback`` lists the numbers that
    failed. ``fallback()`` returns the result table with a one-line summary, built from the
    results only, so it is verified by construction.
    """
    draft = generate(None)
    first = check(draft, ev)
    if first.ok:
        return Final(draft, "verified", 0, first)
    retry = generate(first.unmatched)
    if check(retry, ev).ok:
        return Final(retry, "regenerated", 0, first)
    return Final(fallback(), "fallback", 0, first)
