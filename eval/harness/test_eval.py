"""One test per case: run it through the answerer and record every stage's score (task 2.15).

Cases always pass as tests; the regression rule in conftest decides the run's exit status.
"""

from __future__ import annotations

from typing import Any

import pytest

from eval.harness.answerer import ANSWERERS, Answerer
from eval.harness.report import CaseResult
from eval.harness.scorers import STAGES, AnswerRecord, carry_over
from eval.schema import Case, Gold, load
from metrics.schema import registry


def gold_numbers(gold: Gold) -> list[tuple[float, Any]]:
    """Numbers in gold.value given as {"metric": name, "value": x} (anywhere inside it)."""
    reg = registry()
    out: list[tuple[float, Any]] = []

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if "metric" in v and isinstance(v.get("value"), int | float):
                out.append((float(v["value"]), reg.metric(v["metric"]).rounding))
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(gold.value)
    return out


def selected(split: str) -> list[Case]:
    cs = load().cases
    if split == "all":
        return cs
    return [c for c in cs if c.split == split or (split == "dev" and c.split is None)]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        cs = selected(metafunc.config.getoption("--split"))
        metafunc.parametrize("case", cs, ids=[c.id for c in cs])


@pytest.fixture(scope="session")
def answerer(request: pytest.FixtureRequest) -> Answerer:
    a: Answerer = ANSWERERS[request.config.getoption("--answerer")]()
    return a


def _score(gold: Gold, rec: AnswerRecord) -> dict[str, dict[str, Any]]:
    rec.gold_numbers = gold_numbers(gold)
    return {
        name: {"applicable": s.applicable, "passed": s.passed, "detail": s.detail}
        for name, fn in STAGES.items()
        for s in [fn(gold, rec)]
    }


def test_case(case: Case, answerer: Answerer, results: list[CaseResult]) -> None:
    answerer.new_conversation()
    if case.turns is None:
        assert case.gold is not None and case.question is not None
        rec = answerer.answer(case.question, gold_path=case.gold.path.value)
        stages = _score(case.gold, rec)
        unverified = rec.unverified_numbers
    else:
        golds = [t.gold for t in case.turns]
        recs = [answerer.answer(t.question, gold_path=t.gold.path.value) for t in case.turns]
        per_turn = [_score(g, r) for g, r in zip(golds, recs, strict=True)]
        # A conversation passes a stage only if every applicable turn passes it.
        stages = {}
        for name in STAGES:
            app = [t[name] for t in per_turn if t[name]["applicable"]]
            stages[name] = {
                "applicable": bool(app),
                "passed": bool(app) and all(t["passed"] for t in app),
                "detail": "; ".join(t["detail"] for t in app if t["detail"])[:500],
            }
        co = carry_over(golds, recs)
        stages["carry_over"] = {
            "applicable": co.applicable,
            "passed": co.passed,
            "detail": co.detail,
        }
        unverified = sum(r.unverified_numbers for r in recs)
    results.append(
        CaseResult(case.id, case.seed_id, case.split, case.critical, case.tags, stages, unverified)
    )
