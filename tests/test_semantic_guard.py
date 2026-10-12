"""Semantic guard: a number that verifies must not sit next to another metric's name.

Spec agreed with the developer (3.11 follow-up). ``ResultValue`` gains ``column`` and ``Check``
gains ``mislabeled``. Until that lands, every case here is a strict xfail, so the run fails
loudly (XPASS) the moment it works and the marker must be deleted.

Rule: a number matched to result values passes if no registry label or alias appears next to it,
or the one that does belongs to one of the matched columns. "Next to" = up to 5 words after the
number (stopping at the next number or clause punctuation), or a ``Label:`` form just before it.
"""

import pytest

from app.verifier import Evidence, ResultValue, check
from metrics.schema import Rounding

ONE, ZERO, PCT = Rounding(decimals=1), Rounding(decimals=0), Rounding(decimals=1, display="percent")


def ev(*cols: tuple[float, Rounding, str]) -> Evidence:
    return Evidence(
        values=[ResultValue(v, r, column=c) for v, r, c in cols],
        args_text=["2025-26", "top 5"],
    )


PPG = (32.7, ONE, "points_per_game")
APG = (6.4, ONE, "assists_per_game")
RPG = (8.1, ONE, "rebounds_per_game")
GP = (64, ZERO, "games_played")
FG = (0.4891, PCT, "field_goal_pct")
PTS = (2093, ZERO, "points")
MPG = (34.2, ONE, "minutes_per_game")


@pytest.mark.parametrize(
    ("draft", "cols"),
    [
        ("32.7 points and 6.4 assists", [PPG, APG]),
        ("32.7 points, 8.1 rebounds, and 6.4 assists", [PPG, RPG, APG]),
        ("32.7 points per game in 2025-26", [PPG]),
        ("32.7 ppg", [PPG]),
        ("He played 64 games", [GP]),
        ("a 64-game season", [GP]),
        ("shot 48.9% from the field", [FG]),
        ("48.9 percent field goal percentage", [FG]),
        ("He ranked in the top 5 in 2025-26 with 32.7 points per game", [PPG]),
        ("averaged 32.7 points against 64 teams", [PPG, GP]),
        (
            "He scored 32.7 points to lead the league",
            [PPG],
        ),  # "to" is turnovers' alias: not a label
        ("2,093 points over 64 games", [PTS, GP]),
        ("34.2 minutes per game and 32.7 points per game", [MPG, PPG]),
        # the same number under two columns: either label fits
        ("7.0 points", [(7.0, ONE, "points_per_game"), (7.0, ONE, "rebounds_per_game")]),
        ("7.0 rebounds", [(7.0, ONE, "points_per_game"), (7.0, ONE, "rebounds_per_game")]),
    ],
)
def test_correctly_labelled_numbers_pass(
    draft: str, cols: list[tuple[float, Rounding, str]]
) -> None:
    c = check(draft, ev(*cols))
    assert c.ok, (c.unmatched, c.mislabeled)


@pytest.mark.parametrize(
    ("draft", "cols", "phrase"),
    [
        ("He averages 32.7 assists per game", [PPG, APG], "32.7 assists"),
        ("He played 64 points", [GP, PTS], "64 points"),
        ("32.7 points per game and 6.4 points", [PPG, APG], "6.4 points"),
        ("Assists: 32.7", [PPG, APG], "32.7"),
        ("He has 8.1 steals", [RPG], "8.1 steals"),
        ("He averages 32.7 APG", [PPG, APG], "32.7 APG"),
        ("He averages 32.7 ast", [PPG, APG], "32.7 ast"),
        ("He shot 32.7 rebounds per game", [PPG, RPG], "32.7 rebounds"),
        ("34.2 points per game", [MPG, PPG], "34.2 points"),  # minutes value, points label
        ("48.9% of his 64 points", [FG, GP], "64 points"),
    ],
)
def test_wrong_metric_label_is_caught(
    draft: str, cols: list[tuple[float, Rounding, str]], phrase: str
) -> None:
    c = check(draft, ev(*cols))
    assert not c.ok and not c.unmatched  # every number is real; the words are wrong
    assert any(phrase in m for m in c.mislabeled), c.mislabeled


@pytest.mark.parametrize(
    ("draft", "cols"),
    [
        ("points, 32.7, per game", [PPG, APG]),  # label on both sides: ambiguous, so pass
        ("32.7 minutes per game", [PPG, MPG]),  # longest alias first: "minutes per game"
    ],
)
def test_edge_cases(draft: str, cols: list[tuple[float, Rounding, str]]) -> None:
    check(draft, ev(*cols))  # must not raise; verdicts documented in the spec
