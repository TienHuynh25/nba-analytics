"""Exact numeric scorer (task 2.16).

Every gold number must appear in the answer, rounded by the metric's registry rule, and every
number in the answer must match a gold value or a resolved argument (seasons, dates, "top 5").
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from metrics.rounding import Stated, extract, matches
from metrics.schema import Rounding

INTEGER = Rounding(decimals=0)


@dataclass(frozen=True)
class NumericResult:
    passed: bool
    missing: list[float]  # gold values not stated
    unverified: list[str]  # stated numbers that match nothing


def _arg_numbers(args: Iterable[str]) -> list[Stated]:
    out: list[Stated] = []
    for a in args:
        out += extract(a)
    return out


def score(
    answer: str,
    gold: Iterable[tuple[float, Rounding]],
    args: Iterable[str] = (),
) -> NumericResult:
    gold = list(gold)
    stated = extract(answer)
    arg_stated = _arg_numbers(args)
    arg_nums = {s.value for s in arg_stated if not s.token}
    arg_tokens = {s.text for s in arg_stated if s.token}
    missing = [v for v, r in gold if not any(matches(s, v, r) for s in stated)]
    unverified = []
    for s in stated:
        if s.token:
            if s.text not in arg_tokens:
                unverified.append(s.text)
            continue
        if any(matches(s, v, r) for v, r in gold):
            continue
        if s.value in arg_nums or abs(s.value) in arg_nums:
            continue
        unverified.append(s.text)
    return NumericResult(not missing and not unverified, missing, unverified)
