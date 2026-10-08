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
