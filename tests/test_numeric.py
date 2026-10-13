import pytest

from eval.harness.numeric import score
from metrics.rounding import extract, matches
from metrics.schema import Rounding

ONE = Rounding(decimals=1)
PCT = Rounding(decimals=1, display="percent")
INT = Rounding(decimals=0)


def test_plan_example_one_decimal_metric() -> None:
    # Task 2.16 done-when: "27.3" matches 27.33 for a one-decimal metric, and "27.4" does not.
    assert score("He averages 27.3 points.", [(27.33, ONE)]).passed
    r = score("He averages 27.4 points.", [(27.33, ONE)])
    assert not r.passed and r.missing == [27.33] and r.unverified == ["27.4"]


@pytest.mark.parametrize(
    ("text", "value", "rule", "ok"),
    [
        ("47.6%", 0.4762, PCT, True),
        (".476", 0.4762, PCT, True),
        ("48%", 0.4762, PCT, False),
        ("47.62%", 0.4762, PCT, False),  # more precision than the rule
        ("1,408", 1408, INT, True),
        ("1408", 1408.0, INT, True),
        ("27.35", 27.35, ONE, False),
        ("27.4", 27.35, ONE, True),  # half up
        ("-3", -3, INT, True),
    ],
)
def test_matches(text: str, value: float, rule: Rounding, ok: bool) -> None:
    (s,) = extract(text)
    assert matches(s, value, rule) is ok


def test_numbers_repeating_arguments_are_allowed() -> None:
    r = score(
        "The top 5 rebounders in 2025-26: 12.1, 11.8",
        [(12.1, ONE), (11.8, ONE)],
        args=["top 5", "2025-26"],
    )
    assert r.passed, r


def test_unverified_number_fails() -> None:
    r = score("He scored 31.1 per game over 68 games, a 52% clip.", [(31.1, ONE), (68, INT)])
    assert not r.passed and r.unverified == ["52%"]


def test_extract_ignores_words_with_digits_and_keeps_seasons_whole() -> None:
    got = [s.text for s in extract("SGA hit 3PT shots in 2025-26, 31.1 a game, on 2026-04-12")]
    assert got == ["2025-26", "31.1", "2026-04-12"]


def test_wrong_season_is_unverified() -> None:
    r = score("In 2024-25 he averaged 31.1.", [(31.1, ONE)], args=["2025-26"])
    assert not r.passed and r.unverified == ["2024-25"]


def test_stat_names_with_digits_are_not_numbers() -> None:
    got = [s.text for s in extract("His 3-point percentage is 47.8% with 16 40-point games.")]
    assert got == ["47.8%", "16"]


# T-2.15b: allowed (context) numbers, literals from the gold rows, names with digits.


def test_required_number_missing_fails() -> None:
    r = score("The Thunder went 64 and lost games.", [(64, INT), (18, INT)])
    assert not r.passed and r.missing == [18] and r.unverified == []


def test_allowed_context_number_passes_but_is_not_required() -> None:
    # Q72 shape: usage rate required, the centers' average is context.
    req, ctx = [(0.289, PCT)], [(0.177096, PCT)]
    assert score("Jokic's usage rate is 28.9%, centers average 17.7%.", req, allowed=ctx).passed
    assert score("Jokic's usage rate is 28.9%.", req, allowed=ctx).passed  # context optional
    r = score("Centers average 17.7%.", req, allowed=ctx)
    assert not r.passed and r.missing == [0.289]  # allowed never stands in for required


def test_allowed_number_still_needs_its_rounding() -> None:
    r = score("28.9%, centers 17.8%", [(0.289, PCT)], allowed=[(0.177096, PCT)])
    assert not r.passed and r.unverified == ["17.8%"]
    r = score("28.9%, centers 17.71%", [(0.289, PCT)], allowed=[(0.177096, PCT)])
    assert not r.passed and r.unverified == ["17.71%"]  # more precision than the rule


def test_unrelated_number_is_unverified_even_with_allowed_and_literals() -> None:
    r = score(
        "28.9% in 2025-26, about 41 more than most.",
        [(0.289, PCT)],
        args=["2025-26"],
        allowed=[(0.177096, PCT), (52, INT)],
        literals=["2024-25"],
        names=["Left Corner 3"],
    )
    assert not r.passed and r.unverified == ["41"]


@pytest.mark.parametrize(
    ("text", "value", "rule", "ok"),
    [
        ("27.4", 27.35, ONE, True),  # half up, not banker's
        ("27.2", 27.25, ONE, False),  # 27.25 -> 27.3 under half up
        ("27.3", 27.25, ONE, True),
        ("0.5", 0.45, ONE, True),
        ("47.7%", 0.47650, PCT, True),  # percent rounds after x100
        ("47.6%", 0.47650, PCT, False),
        ("2", 1.5, INT, True),
        ("3", 2.5, INT, True),
        (".781", 0.780488, Rounding(decimals=3), False),
        (".780", 0.780488, Rounding(decimals=3), True),
    ],
)
def test_rounding_edges_half_up(text: str, value: float, rule: Rounding, ok: bool) -> None:
    assert score(text, [(value, rule)]).passed is ok


def test_season_and_date_literals_from_gold_rows() -> None:
    # Q62 shape: seasons in the result rows may be named; others may not.
    r = score("1994-95: 101.4; 2025-26: 115.2", [(101.4, ONE), (115.2, ONE)], literals=["1994-95"])
    assert not r.passed and r.unverified == ["2025-26"]
    r = score(
        "1994-95: 101.4; 2025-26: 115.2",
        [(101.4, ONE), (115.2, ONE)],
        literals=["1994-95", "2025-26"],
    )
    assert r.passed, r


def test_number_repeating_a_resolved_argument_passes() -> None:
    r = score("Top 10 scorers since 2015-16: 31.1", [(31.1, ONE)], args=["10", "2015-16"])
    assert r.passed, r
    r = score("Top 12 scorers: 31.1", [(31.1, ONE)], args=["10"])
    assert not r.passed and r.unverified == ["12"]


def test_names_with_digits_are_masked_but_bare_numbers_are_not() -> None:
    names = ["Philadelphia 76ers", "Left Corner 3"]
    assert score("The 76ers won 24 games.", [(24, INT)], names=names).passed
    assert not score("The 76ers won 24 games.", [(24, INT)]).passed  # unmasked: 76 counts
    assert score("Left Corner 3: 20 attempts", [(20, INT)], names=names).passed
    r = score("Left Corner: 3 attempts and 20 more", [(20, INT)], names=names)
    assert not r.passed and r.unverified == ["3"]
