"""Number matching under the registry's rounding rules.

Shared by the eval numeric scorer (task 2.16) and the answer verifier (task 3.11), so both treat
"27.3" and "47.6%" the same way. A stated number matches a value when it equals the value
rounded to the metric's decimals, in the metric's display scale (percentages x100).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from metrics.schema import Rounding

# Seasons (2025-26) and ISO dates (2026-04-12) are single tokens, matched by text against the
# resolved arguments, so a wrong season in an answer is still caught.
TOKEN = re.compile(r"(?<![\w.-])(\d{4}-\d{2}-\d{2}|\d{4}-\d{2})(?![\w-])")
# Stat names that contain a digit are not claims: "3-point percentage", "40-point games",
# "3PT", "3P%", "3PM", "corner 3s".
STAT_NAME = re.compile(
    r"(?<![\w.-])(?:\d+-point(?:er)?s?\b|[23]P(?:T|M|A|%)?(?![\w])|[23]s\b)", re.IGNORECASE
)
# Numbers as people write them: 1,408  27.3  .476  47.6%  -3  +12. A number glued to letters
# is still a claim ("33.5ppg", "12reb", "99th"): only a following digit stops a match. A scale
# suffix multiplies it ("1.2k", "33.5 million"), so it can't pass as the unscaled value.
NUMBER = re.compile(
    r"(?<![\w.])([+-]?)(\d{1,3}(?:,\d{3})+|\d+)?(\.\d+)?(%?)"
    r"(?:\s?(k|K|M|bn|thousand|million|billion)\b)?(?!\d)"
)
SCALE = {
    "k": 10**3,
    "K": 10**3,
    "thousand": 10**3,
    "M": 10**6,
    "million": 10**6,
    "bn": 10**9,
    "billion": 10**9,
}


@dataclass(frozen=True)
class Stated:
    text: str
    value: Decimal
    decimals: int
    percent: bool
    token: bool = False  # a season or date: matched by text, never by value
    exotic: bool = False  # a Unicode digit or fraction (½, ², ٣): never matches anything


def extract(text: str) -> list[Stated]:
    """Every number, season and date written in ``text``, in order.

    Text is NFKC-normalized first, so full-width digits read as ASCII. Superscripts
    and fractions normalize into digits that no longer match ("99²" -> "992", "99½" ->
    "991" and "2"). Any numeric character left over (other scripts' digits) is flagged as exotic.
    """
    text = unicodedata.normalize("NFKC", text)
    out = []
    for m in TOKEN.finditer(text):
        out.append(Stated(m.group(1), Decimal(0), 0, False, token=True))
    rest = TOKEN.sub(lambda m: " " * len(m.group(0)), text)
    rest = STAT_NAME.sub(lambda m: " " * len(m.group(0)), rest)
    for m in NUMBER.finditer(rest):
        sign, whole, frac, pct, scale = m.groups()
        if not whole and not frac:
            continue
        s = (whole or "0").replace(",", "") + (frac or "")
        v = Decimal(s) * SCALE.get(scale or "", 1)
        if sign == "-":
            v = -v
        decimals = (len(frac) - 1 if frac else 0) if not scale else 0
        out.append(Stated(m.group(0).strip(), v, decimals, pct == "%"))
    for ch in rest:
        if not ("0" <= ch <= "9") and ch.isnumeric():
            out.append(Stated(ch, Decimal(0), 0, False, exotic=True))
    return sorted(out, key=lambda st: text.find(st.text))


def round_half_up(x: float, decimals: int) -> Decimal:
    q = Decimal(1).scaleb(-decimals)
    return Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP)


def matches(stated: Stated, value: float, rounding: Rounding) -> bool:
    """Does the stated number equal ``value`` under ``rounding``?

    The stated number may carry fewer decimals than the rule (e.g. "48%" for 47.6% is NOT a
    match, but "1,408" for a count is). It may not carry more precision than the value
    supports. Percent metrics also accept the fraction form (".476" for 47.6%).
    """
    if stated.token or stated.exotic:
        return False
    candidates: list[tuple[float, int]] = []
    if rounding.display == "percent":
        candidates.append((value * 100, rounding.decimals))
        candidates.append((value, rounding.decimals + 2))  # .476 form
    else:
        candidates.append((value, rounding.decimals))
    for v, dec in candidates:
        if stated.decimals > dec:
            continue
        if round_half_up(v, dec) == stated.value.quantize(Decimal(1).scaleb(-dec)):
            # Same digits at the rule's precision, and no extra digits in the statement.
            return True
    return False


def matches_any(stated: Stated, values: Iterable[tuple[float, Rounding]]) -> bool:
    return any(matches(stated, v, r) for v, r in values)
