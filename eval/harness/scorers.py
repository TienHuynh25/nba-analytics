"""One scorer per stage (task 2.15).

Each scorer takes a case's gold and what the system produced (an :class:`AnswerRecord`) and
returns a :class:`Score`. A scorer that does not apply to a case (e.g. Recall@6 on a stats case)
returns ``applicable=False``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.tools.schemas import canonical
from eval.harness.numeric import score as numeric_score
from eval.schema import Expect, Gold, Path_
from metrics.schema import Rounding

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
    gold_numbers: list[tuple[float, Rounding]] = field(default_factory=list)
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


def _normalize_rows(rows: Sequence[Sequence[Any]]) -> list[tuple[Any, ...]]:
    def cell(v: Any) -> Any:
        return round(v, 3) if isinstance(v, float) else v

    return sorted((tuple(cell(c) for c in r) for r in rows), key=repr)


def sql_rows(gold: Gold, rec: AnswerRecord) -> Score:
    if gold.sql is None or rec.sql is None:
        return NA  # only scored for SQL-fallback answers to cases with gold SQL
    want = gold.value if isinstance(gold.value, list) else None
    if want is None or rec.rows is None:
        return Score(True, False, "no rows to compare")
    ok = _normalize_rows(rec.rows) == _normalize_rows(want)
    return Score(True, ok, "" if ok else "result rows differ from gold rows")


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
    r = numeric_score(rec.text, rec.gold_numbers, rec.args_text)
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
