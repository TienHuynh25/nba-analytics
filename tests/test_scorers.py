"""Task 2.15 done-when: each scorer passes on a hand-made pass example and fails on a fail one."""

from eval.harness.scorers import (
    AnswerRecord,
    answer,
    carry_over,
    entities,
    recall_at_6,
    refusal,
    router,
    sql_rows,
    tool_args,
)
from eval.schema import Gold
from metrics.schema import Rounding

ONE = Rounding(decimals=1)


def g(**kw: object) -> Gold:
    return Gold.model_validate({"path": "stats", **kw})


def test_router() -> None:
    assert router(g(), AnswerRecord(path="stats")).passed
    assert not router(g(), AnswerRecord(path="knowledge")).passed


def test_entities() -> None:
    gold = g(entities={"players": [1628983]})
    assert entities(gold, AnswerRecord(entities={"players": [1628983]})).passed
    assert not entities(gold, AnswerRecord(entities={"players": [203999]})).passed
    assert not entities(g(), AnswerRecord()).applicable


def test_tool_args() -> None:
    gold = g(tool_call={"tool": "get_leaders", "args": {"metric": "points_per_game"}})
    ok = AnswerRecord(tool_call={"tool": "get_leaders", "args": {"metric": "points_per_game"}})
    bad = AnswerRecord(tool_call={"tool": "get_leaders", "args": {"metric": "points"}})
    assert tool_args(gold, ok).passed and not tool_args(gold, bad).passed


def test_sql_rows_order_insensitive_within_rounding() -> None:
    gold = g(sql="select 1", value=[["a", 1.23456], ["b", 2.0]])
    ok = AnswerRecord(sql="select 1", rows=[["b", 2.0], ["a", 1.2346]])
    bad = AnswerRecord(sql="select 1", rows=[["a", 1.3], ["b", 2.0]])
    assert sql_rows(gold, ok).passed and not sql_rows(gold, bad).passed


def test_recall_at_6() -> None:
    gold = Gold.model_validate({"path": "knowledge", "chunks": ["true_shooting_pct"]})
    hit = AnswerRecord(chunks=["a", "b", "true_shooting_pct"])
    miss = AnswerRecord(chunks=["a", "b", "c", "d", "e", "f", "true_shooting_pct"])
    assert recall_at_6(gold, hit).passed and not recall_at_6(gold, miss).passed


def test_refusal_and_false_decline() -> None:
    decline = Gold.model_validate({"path": "refuse", "expect": "decline"})
    assert refusal(decline, AnswerRecord(behaviour="decline")).passed
    assert not refusal(decline, AnswerRecord(behaviour="answer")).passed
    assert not refusal(g(), AnswerRecord(behaviour="decline")).passed  # false decline


def test_answer_numbers_and_behaviour() -> None:
    rec = AnswerRecord(behaviour="answer", text="31.1 points per game", gold_numbers=[(31.08, ONE)])
    assert answer(g(), rec).passed
    rec.text = "31.4 points per game"
    assert not answer(g(), rec).passed
    nt = Gold.model_validate({"path": "stats", "expect": "not_tracked"})
    assert answer(nt, AnswerRecord(behaviour="not_tracked")).passed
    assert not answer(nt, AnswerRecord(behaviour="answer")).passed
    unverified = AnswerRecord(
        behaviour="answer", text="31.1", gold_numbers=[(31.1, ONE)], unverified_numbers=1
    )
    assert not answer(g(), unverified).passed


def test_carry_over() -> None:
    golds = [g(entities={"players": [1]}), g(entities={"players": [1]})]
    assert carry_over(golds, [AnswerRecord(), AnswerRecord(entities={"players": [1]})]).passed
    assert not carry_over(golds, [AnswerRecord(), AnswerRecord(entities={"players": [2]})]).passed
