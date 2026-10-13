"""Exact numeric scorer (task 2.16).

Every required gold number must appear in the answer, rounded by the metric's registry rule, and
every number in the answer must match one of:

- a required gold number, or an allowed (context) gold number, under its registry rounding;
- a resolved argument (seasons, dates, "top 5"), by value, or as a whole season/date token;
- a season or date token that appears in the gold result rows (``literals``), by text.

Anything else is unverified. Names in the gold rows that contain digits ("Philadelphia 76ers",
"Left Corner 3") are blanked out before numbers are read, so a name is not taken for a claim;
only the exact name text is blanked, never a bare number.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from metrics.rounding import Stated, extract, matches, normalize
from metrics.schema import Rounding

INTEGER = Rounding(decimals=0)


@dataclass(frozen=True)
class NumericResult:
    passed: bool
    missing: list[float]  # required gold values not stated
    unverified: list[str]  # stated numbers that match nothing


def _arg_numbers(args: Iterable[str]) -> list[Stated]:
    out: list[Stated] = []
    for a in args:
        out += extract(a)
    return out


def mask_names(text: str, names: Iterable[str]) -> str:
    """Blank out each name (exact text, whole words) and each digit-bearing word of a name
    that also has letters ("76ers"); a bare number inside a name ("3") is not blanked alone."""
    text = normalize(text)
    phrases: set[str] = set()
    for n in names:
        n = normalize(n).strip()
        if not n or not re.search(r"\d", n):
            continue
        phrases.add(n)
        phrases |= {w for w in n.split() if re.search(r"\d", w) and re.search(r"[^\W\d_]", w)}
    for p in sorted(phrases, key=len, reverse=True):
        pat = re.compile(r"(?<![\w.])" + re.escape(p) + r"(?![\w])")
        text = pat.sub(lambda m: " " * len(m.group(0)), text)
    return text


def score(
    answer: str,
    gold: Iterable[tuple[float, Rounding]],
    args: Iterable[str] = (),
    allowed: Iterable[tuple[float, Rounding]] = (),
    literals: Iterable[str] = (),
    names: Iterable[str] = (),
) -> NumericResult:
    gold = list(gold)
    allowed = list(allowed)
    stated = extract(mask_names(answer, names))
    arg_stated = _arg_numbers(args)
    arg_nums = {s.value for s in arg_stated if not s.token}
    tokens = {s.text for s in arg_stated if s.token}
    tokens |= {s.text for s in _arg_numbers(literals) if s.token}
    missing = [v for v, r in gold if not any(matches(s, v, r) for s in stated)]
    unverified = []
    for s in stated:
        if s.token:
            if s.text not in tokens:
                unverified.append(s.text)
            continue
        if any(matches(s, v, r) for v, r in gold) or any(matches(s, v, r) for v, r in allowed):
            continue
        if not s.exotic and (s.value in arg_nums or abs(s.value) in arg_nums):
            continue
        unverified.append(s.text)
    return NumericResult(not missing and not unverified, missing, unverified)
