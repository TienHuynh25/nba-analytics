"""Harness self-check without an LLM (T-2.15b, AC-4).

For every case unit in eval/cases.yaml, build the record a perfect system would produce from the
gold itself, score it through every stage, and expect a pass. Then mutate it (wrong number,
extra number, missing number, missing/extra row, rows out of order, wrong behaviour) and expect
the matching stage to fail. Text answers with no gold numbers (knowledge, Q79, M05.1) wait for
the LLM judge (task 2.20), so their answer stage is reported, not asserted as a pass.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from eval.harness.scorers import (
    STAGES,
    AnswerRecord,
    attach_gold,
    carry_over,
    gold_rows,
    sql_rows,
)
from eval.schema import Expect, Gold, Path_, load
from metrics.rounding import round_half_up
from metrics.schema import Rounding, registry

TEXT = {
    "decline": "I can't help with that.",
    "clarify": "Which player do you mean?",
    "not_tracked": "That stat was not tracked then.",
    "no_verdict": "Here are the stats side by side; I won't pick one.",
}


def units() -> Iterator[tuple[str, Gold]]:
    for c in load().cases:
        if c.turns is None:
            assert c.gold is not None
            yield c.id, c.gold
        else:
            for i, t in enumerate(c.turns, 1):
                yield f"{c.id}.{i}", t.gold


def display(value: float, r: Rounding, extra: int = 0) -> str:
    if r.display == "percent":
        return f"{round_half_up(value * 100, r.decimals + extra)}%"
    return str(round_half_up(value, r.decimals + extra))


def _items(gold: Gold, key: str) -> list[dict[str, Any]]:
    v = gold.value
    return list(v.get(key) or []) if isinstance(v, dict) else []


def _segment(item: dict[str, Any], shown: str) -> str:
    return f"{item.get('key', '')} {item['column']}: {shown}".strip()


def _args_text(gold: Gold) -> list[str]:
    if gold.tool_call is None:
        return []
    out = []
    for v in gold.tool_call.args.values():
        if isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool)):
            out.append(str(v))
    return out


def answer_text(gold: Gold, with_context: bool = False) -> str:
    reg = registry()
    if gold.expect != Expect.answer:
        return TEXT[gold.expect.value]
    if gold.path == Path_.knowledge:
        return " ".join(gold.value["facts"])
    parts = [
        _segment(n, display(n["value"], reg.metric(n["metric"]).rounding))
        for n in _items(gold, "answer")
    ]
    if with_context:
        parts += [
            _segment(n, display(n["value"], reg.metric(n["metric"]).rounding))
            for n in _items(gold, "allowed")
        ]
        parts.append(f"{len(gold_rows(gold.value) or [])} rows")
    return "; ".join(parts)


def perfect(gold: Gold, with_context: bool = False) -> AnswerRecord:
    rows = gold_rows(gold.value)
    rec = AnswerRecord(
        path=gold.path.value,
        entities={k: list(v) for k, v in gold.entities.items()},
        tool_call=(
            {"tool": gold.tool_call.tool, "args": dict(gold.tool_call.args)}
            if gold.tool_call
            else None
        ),
        sql=gold.sql,
        rows=(
            [list(r.values()) if isinstance(r, dict) else list(r) for r in rows]
            if rows is not None and gold.sql
            else None
        ),
        chunks=list(gold.chunks),
        text=answer_text(gold, with_context),
        behaviour=gold.expect.value,
        args_text=_args_text(gold),
    )
    return attach_gold(gold, rec)


def judged(gold: Gold) -> bool:
    """Text answers the deterministic scorers cannot pass yet (LLM judge, task 2.20)."""
    return gold.expect == Expect.answer and not _items(gold, "answer")


def stage_results(gold: Gold, rec: AnswerRecord) -> dict[str, tuple[bool, bool, str]]:
    return {
        n: (s.applicable, s.passed, s.detail) for n, fn in STAGES.items() for s in [fn(gold, rec)]
    }


def _shown(gold: Gold, rec: AnswerRecord) -> set[str]:
    reg = registry()
    out = {display(n["value"], reg.metric(n["metric"]).rounding) for n in _items(gold, "answer")}
    out |= {display(n["value"], reg.metric(n["metric"]).rounding) for n in _items(gold, "allowed")}
    return out | set(rec.args_text) | {str(len(gold_rows(gold.value) or []))}


def _bump(shown: str, taken: set[str]) -> str:
    pct = shown.endswith("%")
    d = Decimal(shown.rstrip("%"))
    exp = d.as_tuple().exponent
    assert isinstance(exp, int)
    step = Decimal(1).scaleb(exp)  # one unit in the last place
    cand = shown
    while cand in taken or cand == shown:
        d += step
        cand = f"{d}%" if pct else str(d)
    return cand


def mutations(gold: Gold) -> Iterator[tuple[str, str, AnswerRecord | None, bool]]:
    """(mutation, stage, record or None if not applicable, expected pass)."""
    reg = registry()
    base = perfect(gold)
    req = _items(gold, "answer")
    numeric = gold.expect == Expect.answer and bool(req)
    if numeric:
        first = req[0]
        r0 = reg.metric(first["metric"]).rounding
        right = display(first["value"], r0)
        wrong = _bump(right, _shown(gold, base))
        old = _segment(first, right)
        yield (
            "wrong number",
            "answer",
            dataclasses.replace(base, text=base.text.replace(old, _segment(first, wrong), 1)),
            False,
        )
        yield (
            "extra unrelated number",
            "answer",
            dataclasses.replace(base, text=base.text + "; also 98765.4"),
            False,
        )
        precise = display(first["value"], r0, extra=1)
        yield (
            "more precision than the rule",
            "answer",
            dataclasses.replace(base, text=base.text.replace(old, _segment(first, precise), 1)),
            False,
        )
        # Drop a required number whose shown value no other stated number repeats.
        segs = [(n, display(n["value"], reg.metric(n["metric"]).rounding)) for n in req]
        counts = Counter(s for _, s in segs)
        lone = [(n, s) for n, s in segs if counts[s] == 1]
        if lone:
            n, _ = lone[0]
            text = "; ".join(_segment(m, t) for m, t in segs if m is not n)
            yield "required number missing", "answer", dataclasses.replace(base, text=text), False
        yield "allowed context numbers added", "answer", perfect(gold, with_context=True), True
        if base.args_text:
            yield (
                "repeats a resolved argument",
                "answer",
                dataclasses.replace(base, text=f"{base.text} (asked: {base.args_text[0]})"),
                True,
            )
    elif gold.expect != Expect.answer:
        wrong_b = "answer" if gold.expect != Expect.decline else "clarify"
        yield (
            f"behaviour {wrong_b} instead of {gold.expect.value}",
            "answer",
            dataclasses.replace(base, behaviour=wrong_b),
            False,
        )
        if gold.expect == Expect.decline:
            yield (
                "answered instead of declining",
                "refusals",
                dataclasses.replace(base, behaviour="answer"),
                False,
            )
    if base.rows is not None and sql_rows(gold, base).applicable:
        rows = base.rows
        if rows:
            yield "missing row", "sql_rows", dataclasses.replace(base, rows=rows[:-1]), False
        yield "extra row", "sql_rows", dataclasses.replace(base, rows=rows + rows[:1]), False
        rev = list(reversed(rows))
        if rev != rows:
            ordered = bool(gold.value.get("ordered"))
            probe = sql_rows(gold, dataclasses.replace(base, rows=rev))
            # Reversal is invisible when the scored columns read the same backwards.
            same = (
                sql_rows(
                    Gold.model_validate(
                        {**gold.model_dump(), "value": {**gold.value, "ordered": False}}
                    ),
                    dataclasses.replace(base, rows=rev),
                ).passed
                and probe.passed
            )
            if ordered and not same:
                yield (
                    "rows reversed (ordered gold)",
                    "sql_rows",
                    dataclasses.replace(base, rows=rev),
                    False,
                )
            elif not ordered:
                yield (
                    "rows reversed (unordered gold)",
                    "sql_rows",
                    dataclasses.replace(base, rows=rev),
                    True,
                )
        if rows and len(rows[0]) > 1:
            yield (
                "columns permuted",
                "sql_rows",
                dataclasses.replace(base, rows=[list(reversed(r)) for r in rows]),
                True,
            )


def run_selfcheck() -> dict[str, Any]:
    perfect_by_kind: dict[str, Counter[str]] = {}
    failures: list[str] = []
    mut: dict[tuple[str, str, bool], Counter[str]] = {}
    for uid, gold in units():
        kind = str(gold.value["kind"])
        c = perfect_by_kind.setdefault(kind, Counter())
        c["units"] += 1
        res = stage_results(gold, perfect(gold))
        for stage, (app, ok, detail) in res.items():
            if not app:
                continue
            if stage == "answer" and judged(gold):
                c["answer: judge pending (2.20)"] += 1
                assert not ok and "judge" in detail, (uid, detail)
                continue
            c[f"{stage} applicable"] += 1
            c[f"{stage} passed"] += ok
            if not ok:
                failures.append(f"{uid} {stage}: {detail}")
        for name, stage, rec, want in mutations(gold):
            assert rec is not None
            got = STAGES[stage](gold, rec).passed
            k = mut.setdefault((name, stage, want), Counter())
            k["cases"] += 1
            k["as expected"] += got == want
            if got != want:
                failures.append(f"{uid} {name}: got {got}, want {want}")
    # Multi-turn: carry-over on the perfect records.
    co: Counter[str] = Counter()
    for case in load().cases:
        if case.turns:
            golds = [t.gold for t in case.turns]
            s = carry_over(golds, [perfect(g) for g in golds])
            if s.applicable:
                co["applicable"] += 1
                co["passed"] += s.passed
    return {"perfect": perfect_by_kind, "mutations": mut, "carry_over": co, "failures": failures}


def table(res: dict[str, Any]) -> str:
    lines = ["Perfect answers by gold kind:"]
    for kind, c in sorted(res["perfect"].items()):
        lines.append(f"  {kind}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    lines.append(f"  carry_over (multi-turn): {dict(res['carry_over'])}")
    lines += [
        "",
        "| Mutation | Stage | Expected | Cases | As expected |",
        "| --- | --- | --- | --- | --- |",
    ]
    for (name, stage, want), c in sorted(res["mutations"].items()):
        lines.append(
            f"| {name} | {stage} | {'pass' if want else 'fail'} | {c['cases']} "
            f"| {c['as expected']} |"
        )
    lines.append(f"\nUnexpected outcomes: {len(res['failures'])}")
    lines += res["failures"][:20]
    return "\n".join(lines)


def test_perfect_answers_pass_and_mutations_fail() -> None:
    res = run_selfcheck()
    assert not res["failures"], "\n".join(res["failures"][:20])
    kinds = res["perfect"]
    assert set(kinds) == {"answer", "knowledge", "decline", "not_tracked", "clarify", "no_verdict"}
    for kind, c in kinds.items():
        for key, n in c.items():
            if key.endswith(" applicable"):
                assert c[key.replace("applicable", "passed")] == n, (kind, key)
    assert res["carry_over"]["applicable"] == res["carry_over"]["passed"] > 0
    # Each mutation type ran on at least one case.
    names = {name for name, _, _ in res["mutations"]}
    assert {
        "wrong number",
        "extra unrelated number",
        "required number missing",
        "allowed context numbers added",
        "missing row",
        "extra row",
        "rows reversed (ordered gold)",
        "rows reversed (unordered gold)",
    } <= names
