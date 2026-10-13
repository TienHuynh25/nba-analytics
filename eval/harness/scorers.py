"""One scorer per stage (task 2.15).

Each scorer takes a case's gold and what the system produced (an :class:`AnswerRecord`) and
returns a :class:`Score`. A scorer that does not apply to a case (e.g. Recall@6 on a stats case)
returns ``applicable=False``.
"""

from __future__ import annotations

import datetime as dt
import decimal
import itertools
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.tools.schemas import canonical
from eval.harness.numeric import INTEGER
from eval.harness.numeric import score as numeric_score
from eval.schema import Expect, Gold, Path_
from metrics.rounding import round_half_up
from metrics.schema import Rounding, registry

RECALL_K = 6


@dataclass
class AnswerRecord:
    """What the system did for one question (one turn)."""

    path: str | None = None
    entities: dict[str, list[int]] = field(default_factory=dict)
    tool_call: dict[str, Any] | None = None
    sql: str | None = None
    rows: list[list[Any]] | None = None
    chunks: list[str] = field(default_factory=list)  # retrieved, ranked
    text: str = ""
    behaviour: str = "answer"  # answer | decline | clarify | not_tracked | no_verdict
    args_text: list[str] = field(default_factory=list)  # resolved arguments, as text
    gold_numbers: list[tuple[float, Rounding]] = field(default_factory=list)  # required
    allowed_numbers: list[tuple[float, Rounding]] = field(default_factory=list)  # context
    literals: list[str] = field(default_factory=list)  # seasons/dates in the gold rows
    names: list[str] = field(default_factory=list)  # gold row names that contain digits
    unverified_numbers: int = 0  # numbers shown that the verifier could not match
    latency_ms: float | None = None


@dataclass(frozen=True)
class Score:
    applicable: bool
    passed: bool = False
    detail: str = ""


NA = Score(applicable=False)


def router(gold: Gold, rec: AnswerRecord) -> Score:
    ok = rec.path == gold.path.value
    return Score(True, ok, "" if ok else f"path {rec.path} != {gold.path.value}")


def entities(gold: Gold, rec: AnswerRecord) -> Score:
    if not gold.entities:
        return NA
    want = {k: sorted(v) for k, v in gold.entities.items()}
    got = {k: sorted(v) for k, v in rec.entities.items() if k in want}
    ok = got == want
    return Score(True, ok, "" if ok else f"entities {got} != {want}")


def tool_args(gold: Gold, rec: AnswerRecord) -> Score:
    """Tool and arguments equal gold, after filling schema defaults on both sides."""
    if gold.tool_call is None:
        return NA
    tool = gold.tool_call.tool
    want = {"tool": tool, "args": canonical(tool, gold.tool_call.args)}
    got = None
    if rec.tool_call is not None and rec.tool_call.get("tool") == tool:
        got = {"tool": tool, "args": canonical(tool, rec.tool_call.get("args", {}))}
    ok = got == want
    return Score(True, ok, "" if ok else f"tool call {rec.tool_call} != {want}")


TOKEN_LIKE = re.compile(r"\d{4}-\d{2}(-\d{2})?")  # a season (2025-26) or ISO date
LEGACY_DECIMALS = 3  # legacy list-of-rows gold carries no metric: floats compare at 3 decimals
STORED_DECIMALS = 6  # gold floats are stored at 6 decimals (eval/gold/README.md)
MAX_ASSIGNMENTS = 100_000  # column-mapping search bound for sql_rows


@dataclass(frozen=True)
class GoldNumbers:
    """What the numeric scorer needs from ``gold.value`` (eval/gold/README.md, T-2.15b)."""

    required: list[tuple[float, Rounding]] = field(default_factory=list)  # value.answer
    allowed: list[tuple[float, Rounding]] = field(default_factory=list)  # value.allowed, row count
    literals: list[str] = field(default_factory=list)  # season/date cells of the gold rows
    names: list[str] = field(default_factory=list)  # other string cells that contain a digit


def gold_rows(value: Any) -> list[Mapping[str, Any]] | list[Sequence[Any]] | None:
    """The gold result rows: ``rows`` (answer, no_verdict, not_tracked), ``candidates``
    (clarify), or a legacy list of rows. None when the gold has no rows (knowledge, decline)."""
    if isinstance(value, Mapping):
        rows = value.get("rows", value.get("candidates"))
        return list(rows) if isinstance(rows, list) else None
    if isinstance(value, list) and all(isinstance(r, list | tuple) for r in value):
        return list(value)
    return None


def gold_numbers(gold: Gold) -> GoldNumbers:
    """Required numbers from ``value.answer``; allowed ones from ``value.allowed`` plus the
    gold row count (the verifier also accepts it); seasons, dates and digit-bearing names from
    the gold rows. Raises KeyError on a metric that is not in the registry."""
    v = gold.value
    if not isinstance(v, Mapping):
        return GoldNumbers()
    reg = registry()

    def items(key: str) -> list[tuple[float, Rounding]]:
        return [(float(n["value"]), reg.metric(n["metric"]).rounding) for n in v.get(key) or []]

    required, allowed = items("answer"), items("allowed")
    rows = gold_rows(v) or []
    if rows:
        allowed.append((float(len(rows)), INTEGER))
    literals: list[str] = []
    names: list[str] = []
    for r in rows:
        for c in r.values() if isinstance(r, Mapping) else r:
            if not isinstance(c, str):
                continue
            if TOKEN_LIKE.fullmatch(c):
                literals.append(c)
            elif re.search(r"\d", c):
                names.append(c)
    for n in v.get("answer") or []:  # keys name the rows ("Tim Duncan, 1997-98")
        literals += [t for t in re.findall(r"\d{4}-\d{2}(?:-\d{2})?", str(n.get("key", "")))]
    return GoldNumbers(required, allowed, sorted(set(literals)), sorted(set(names)))


def attach_gold(gold: Gold, rec: AnswerRecord) -> AnswerRecord:
    """Copy the gold numbers onto the record (the harness does this before scoring)."""
    g = gold_numbers(gold)
    rec.gold_numbers, rec.allowed_numbers = g.required, g.allowed
    rec.literals, rec.names = g.literals, g.names
    return rec


def _cell(v: Any, rounding: Rounding | None, legacy: bool) -> Any:
    """A cell in comparable form: numbers under the column's registry rounding (in storage
    scale, so a fraction for a percent metric), dates as ISO text."""
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int | float):
        if rounding is not None:
            dec = rounding.decimals + (2 if rounding.display == "percent" else 0)
        else:
            dec = LEGACY_DECIMALS if legacy else STORED_DECIMALS
        return round_half_up(float(v), dec)
    if isinstance(v, dt.datetime | dt.date):
        return v.isoformat()
    return v


def _scored_columns(
    value: Any, rows: Sequence[Any]
) -> tuple[list[Any], dict[Any, Rounding | None], bool, bool]:
    """(gold columns to match, their rounding, ordered, legacy)."""
    reg = registry()
    if not isinstance(value, Mapping):  # legacy list of rows: every column, unordered
        width = max((len(r) for r in rows), default=0)
        return list(range(width)), dict.fromkeys(range(width)), False, True
    cols: dict[Any, Rounding | None] = {}
    for n in value.get("answer") or []:  # the required numbers' columns
        cols.setdefault(n["column"], reg.metric(n["metric"]).rounding)
    if not cols:  # no required numbers (names, clarify, not tracked): every column
        by_name = {m.name: m.rounding for m in reg.metrics}  # exact names only, not aliases
        for c in rows[0] if rows else []:
            cols[c] = by_name.get(c)
    return list(cols), cols, bool(value.get("ordered")), False


def _same(a: list[Any], b: list[Any], ordered: bool) -> bool:
    """Equal sequences (ordered) or equal multisets (unordered)."""
    if ordered:
        return a == b
    return Counter(map(repr, a)) == Counter(map(repr, b))


def sql_rows(gold: Gold, rec: AnswerRecord) -> Score:
    """Spec: result rows match gold rows (order-insensitive unless ``ordered``, within the
    registry rounding). Ties at a LIMIT cut are in the gold rows, so a cut that drops a tied row
    fails on the row count. The SQL fallback's columns have its own names and order, so each
    scored gold column (the required numbers' columns, or every column when there are none)
    must map to a distinct result column with the same values row for row."""
    if gold.sql is None or rec.sql is None:
        return NA  # only scored for SQL-fallback answers to cases with gold SQL
    rows = gold_rows(gold.value)
    if rows is None or rec.rows is None:
        return Score(True, False, "no rows to compare")
    if len(rec.rows) != len(rows):
        return Score(True, False, f"{len(rec.rows)} result rows != {len(rows)} gold rows")
    if not rows:
        return Score(True, True)
    cols, rounding, ordered, legacy = _scored_columns(gold.value, rows)
    width = {len(r) for r in rec.rows}
    if len(width) != 1:
        return Score(True, False, "result rows have different widths")
    (w,) = width

    def gold_col(c: Any) -> list[Any]:
        return [_cell(r[c], rounding[c], legacy) for r in rows]

    def got_col(j: int, c: Any) -> list[Any]:
        return [_cell(r[j], rounding[c], legacy) for r in rec.rows or []]

    want = {c: gold_col(c) for c in cols}
    options: list[list[int]] = []
    for c in cols:
        js = [j for j in range(w) if _same(got_col(j, c), want[c], ordered)]
        if not js:
            if ordered and any(_same(got_col(j, c), want[c], False) for j in range(w)):
                return Score(True, False, f"column {c!r} is in a different row order (ordered)")
            return Score(True, False, f"no result column matches gold column {c!r}")
        options.append(js)
    want_rows = [tuple(t) for t in zip(*(want[c] for c in cols), strict=True)]
    for n, combo in enumerate(itertools.product(*options)):
        if n >= MAX_ASSIGNMENTS:
            return Score(True, False, "too many column mappings to check")
        if len(set(combo)) != len(combo):
            continue
        picked = [got_col(j, c) for j, c in zip(combo, cols, strict=True)]
        got_rows = [tuple(t) for t in zip(*picked, strict=True)]
        if _same(want_rows, got_rows, ordered):
            return Score(True, True)
    detail = "result rows differ from gold rows" + (" (order matters)" if ordered else "")
    return Score(True, False, detail)


def recall_at_6(gold: Gold, rec: AnswerRecord) -> Score:
    if gold.path not in (Path_.knowledge, Path_.mixed) or not gold.chunks:
        return NA
    top = rec.chunks[:RECALL_K]
    ok = any(c in top for c in gold.chunks)
    return Score(True, ok, "" if ok else f"no gold chunk in top {RECALL_K}: {top}")


def refusal(gold: Gold, rec: AnswerRecord) -> Score:
    should = gold.expect == Expect.decline
    did = rec.behaviour == "decline"
    if should:
        return Score(True, did, "" if did else "should have declined")
    return Score(True, not did, "" if not did else "false decline")


def answer(gold: Gold, rec: AnswerRecord) -> Score:
    """End-to-end correctness: right behaviour, and for answers, exact numbers."""
    if rec.unverified_numbers:
        return Score(True, False, f"{rec.unverified_numbers} unverified number(s) shown")
    if gold.expect != Expect.answer:
        ok = rec.behaviour == gold.expect.value
        return Score(True, ok, "" if ok else f"behaviour {rec.behaviour} != {gold.expect.value}")
    if rec.behaviour != "answer":
        return Score(True, False, f"behaviour {rec.behaviour} != answer")
    if not rec.gold_numbers:
        # Text-only answers are scored by the calibrated LLM judge (2.20); none yet.
        return Score(True, False, "no gold numbers and no judge yet")
    r = numeric_score(
        rec.text, rec.gold_numbers, rec.args_text, rec.allowed_numbers, rec.literals, rec.names
    )
    detail = "" if r.passed else f"missing {r.missing}, unverified {r.unverified}"
    return Score(True, r.passed, detail)


def latency(gold: Gold, rec: AnswerRecord) -> Score:
    if rec.latency_ms is None:
        return NA
    return Score(True, True, f"{rec.latency_ms:.0f} ms")


STAGES: dict[str, Callable[[Gold, AnswerRecord], Score]] = {
    "router": router,
    "entities": entities,
    "tool_args": tool_args,
    "sql_rows": sql_rows,
    "recall_at_6": recall_at_6,
    "refusals": refusal,
    "answer": answer,
    "latency": latency,
}


def carry_over(turn_golds: Sequence[Gold], recs: Sequence[AnswerRecord]) -> Score:
    """Multi-turn: turns 2+ resolve the same entities as gold."""
    later = [(g, r) for g, r in zip(turn_golds[1:], recs[1:], strict=True) if g.entities]
    if not later:
        return NA
    ok = all(entities(g, r).passed for g, r in later)
    return Score(True, ok, "" if ok else "a later turn lost the carried entities")
