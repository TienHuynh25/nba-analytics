"""Task 2.15 done-when: each scorer passes on a hand-made pass example and fails on a fail one."""

from eval.harness.scorers import (
    AnswerRecord,
    answer,
    attach_gold,
    carry_over,
    entities,
    gold_numbers,
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


# T-2.15b: sql_rows on the mapping gold shape, and allowed numbers in the answer stage.

PCT = Rounding(decimals=1, display="percent")
SQL = "select 1"


def answer_gold(
    rows: list[dict[str, object]], answer_items: list[dict[str, object]], **kw: object
) -> Gold:
    value: dict[str, object] = {"kind": "answer", "ordered": False, "answer": answer_items}
    value.update(kw)
    value["rows"] = rows
    return g(sql=SQL, value=value)


LEADERS = [
    {"player_id": 1, "player_name": "A", "points_per_game": 32.71, "games_played": 70},
    {"player_id": 2, "player_name": "B", "points_per_game": 30.04, "games_played": 66},
    {"player_id": 3, "player_name": "C", "points_per_game": 30.04, "games_played": 75},
]
LEADER_ITEMS = [
    {
        "metric": "points_per_game",
        "value": r["points_per_game"],
        "column": "points_per_game",
        "key": r["player_name"],
    }
    for r in LEADERS
]


def rec(rows: list[list[object]]) -> AnswerRecord:
    return AnswerRecord(sql=SQL, rows=rows)


def test_sql_rows_mapping_unordered_within_registry_rounding() -> None:
    gold = answer_gold(LEADERS, LEADER_ITEMS)
    # Different column names/order, extra columns, other row order, raw (unrounded) floats.
    ok = rec([["C", 30.0449, 3], ["A", 32.7111, 1], ["B", 30.0351, 2]])
    assert sql_rows(gold, ok).passed
    bad = rec([["C", 30.0, 3], ["A", 32.7, 1], ["B", 30.1, 2]])  # 30.1 != 30.0
    assert not sql_rows(gold, bad).passed


def test_sql_rows_ordered_only_when_gold_says_so() -> None:
    shuffled = rec([[2, 30.04], [1, 32.71], [3, 30.04]])
    assert sql_rows(answer_gold(LEADERS, LEADER_ITEMS), shuffled).passed
    ordered = answer_gold(LEADERS, LEADER_ITEMS, ordered=True)
    s = sql_rows(ordered, shuffled)
    assert not s.passed and "order" in s.detail
    assert sql_rows(ordered, rec([[1, 32.71], [2, 30.04], [3, 30.04]])).passed


def test_sql_rows_tie_at_the_cut_needs_every_tied_row() -> None:
    gold = answer_gold(LEADERS, LEADER_ITEMS, ordered=True, ties="RANK() <= 2 keeps ties")
    cut = rec([[1, 32.71], [2, 30.04]])  # LIMIT 2 drops C, tied with B
    s = sql_rows(gold, cut)
    assert not s.passed and "2 result rows != 3 gold rows" in s.detail
    extra = rec([[1, 32.71], [2, 30.04], [3, 30.04], [4, 29.9]])
    assert not sql_rows(gold, extra).passed


def test_sql_rows_missing_column_or_row_fails() -> None:
    gold = answer_gold(LEADERS, LEADER_ITEMS)
    s = sql_rows(gold, rec([["A", 70], ["B", 66], ["C", 75]]))
    assert not s.passed and "points_per_game" in s.detail
    assert not sql_rows(gold, rec([[1, 32.71], [2, 30.04]])).passed
    # Column values right as a set, but paired with the wrong rows (two scored columns).
    two = answer_gold(
        LEADERS,
        [
            *LEADER_ITEMS,
            {"metric": "games_played", "value": 70, "column": "games_played", "key": "A"},
        ],
    )
    assert sql_rows(two, rec([[32.71, 70], [30.04, 66], [30.04, 75]])).passed
    assert not sql_rows(two, rec([[32.71, 66], [30.04, 70], [30.04, 75]])).passed


def test_sql_rows_percent_compares_fractions_under_display_rounding() -> None:
    rows = [{"player_name": "A", "field_goal_pct": 0.476123}]
    items = [{"metric": "field_goal_pct", "value": 0.476123, "column": "field_goal_pct"}]
    gold = answer_gold(rows, items)
    assert sql_rows(gold, rec([["A", 0.4759]])).passed  # 47.6% either way
    assert not sql_rows(gold, rec([["A", 0.4766]])).passed  # 47.7%
    assert not sql_rows(gold, rec([["A", 47.6]])).passed  # rows carry fractions, not percents


def test_sql_rows_no_verdict_not_tracked_and_clarify_kinds() -> None:
    nv = g(
        sql=SQL,
        expect="no_verdict",
        value={
            "kind": "no_verdict",
            "ordered": False,
            "answer": LEADER_ITEMS[:1],
            "rows": LEADERS[:1],
        },
    )
    assert sql_rows(nv, rec([["A", 32.7]])).passed
    assert not sql_rows(nv, rec([["A", 32.8]])).passed
    nt_rows = [
        {
            "player_id": 76003,
            "season": "1970-71",
            "steals": None,
            "stat": "steals",
            "first_season_tracked": "1973-74",
        }
    ]
    nt = g(
        sql=SQL,
        expect="not_tracked",
        value={
            "kind": "not_tracked",
            "column": "steals",
            "stat": "steals",
            "first_season_tracked": "1973-74",
            "rows": nt_rows,
        },
    )
    assert sql_rows(nt, rec([[76003, "1970-71", None, "steals", "1973-74"]])).passed
    assert not sql_rows(nt, rec([[76003, "1970-71", 0, "steals", "1973-74"]])).passed  # 0, not NULL
    cands = [
        {"player_id": 1, "player_name": "Jalen Williams"},
        {"player_id": 2, "player_name": "Jaylin Williams"},
    ]
    cl = g(sql=SQL, expect="clarify", value={"kind": "clarify", "candidates": cands})
    assert sql_rows(cl, rec([["Jaylin Williams", 2], ["Jalen Williams", 1]])).passed
    assert not sql_rows(cl, rec([["Jalen Williams", 1]])).passed


def test_sql_rows_not_applicable_without_gold_sql_or_fallback() -> None:
    kn = Gold.model_validate(
        {
            "path": "knowledge",
            "chunks": ["net_rating"],
            "value": {"kind": "knowledge", "chunks": ["net_rating"], "facts": []},
        }
    )
    assert not sql_rows(kn, rec([[1]])).applicable
    dec = Gold.model_validate(
        {"path": "refuse", "expect": "decline", "value": {"kind": "decline", "reason": "betting"}}
    )
    assert not sql_rows(dec, rec([[1]])).applicable
    assert not sql_rows(answer_gold(LEADERS, LEADER_ITEMS), AnswerRecord()).applicable
    no_rows = g(sql=SQL, value={"kind": "answer", "answer": []})
    assert not sql_rows(no_rows, rec([[1]])).passed


def test_gold_numbers_reads_required_allowed_and_row_literals() -> None:
    gold = answer_gold(
        [{"team_name": "Philadelphia 76ers", "season": "2025-26", "wins": 24, "win_pct": 0.292683}],
        [{"metric": "wins", "value": 24, "column": "wins", "key": "Philadelphia 76ers"}],
        allowed=[
            {
                "metric": "win_pct",
                "value": 0.292683,
                "column": "win_pct",
                "key": "Philadelphia 76ers",
            }
        ],
    )
    gn = gold_numbers(gold)
    assert gn.required == [(24.0, Rounding(decimals=0))]
    assert gn.allowed == [(0.292683, Rounding(decimals=3)), (1.0, Rounding(decimals=0))]
    assert gn.literals == ["2025-26"] and gn.names == ["Philadelphia 76ers"]
    r = attach_gold(
        gold, AnswerRecord(behaviour="answer", text="The 76ers won 24 (.293) in 2025-26.")
    )
    assert answer(gold, r).passed
    r.text = "The 76ers won 24 (.293) in 2025-26, 3 more than last year."
    s = answer(gold, r)
    assert not s.passed and "unverified ['3']" in s.detail
    r.text = "The 76ers had a .293 record in 2025-26."
    s = answer(gold, r)
    assert not s.passed and "missing [24.0]" in s.detail


def test_allowed_items_are_schema_checked() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        g(value={"kind": "answer", "answer": [], "allowed": [{"metric": "wins"}]})
    with pytest.raises(ValidationError):
        g(value={"kind": "answer", "answer": [], "allowed": []})
