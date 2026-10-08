from datetime import date

import pytest

from app.timeparse import SnapshotClock, resolve

EVAL = SnapshotClock(as_of_date=date(2026, 4, 13), latest_season="2025-26")
OFFSEASON = SnapshotClock(as_of_date=date(2026, 9, 30), latest_season="2025-26")
OPENING_WEEK = SnapshotClock(as_of_date=date(2026, 10, 24), latest_season="2026-27")


@pytest.mark.parametrize(
    ("q", "season", "season_type"),
    [
        ("How many points per game is SGA averaging this season?", "2025-26", None),
        ("What were SGA's playoff stats last season?", "2024-25", "Playoffs"),
        ("What were Jokic's averages last season?", "2024-25", None),
        ("What was the final score of the last NBA Finals game?", "2024-25", "Playoffs"),
        ("Who won Rookie of the Year in 2024?", "2023-24", None),
        ("Who leads in rebounds in 2019-20?", "2019-20", None),
        ("What are the current NBA standings?", "2025-26", None),
    ],
)
def test_eval_snapshot_rules(q: str, season: str, season_type: str | None) -> None:
    r = resolve(q, EVAL)
    assert (r.season, r.season_type) == (season, season_type)


def test_last_night_and_today_use_snapshot_not_clock() -> None:
    assert resolve("box score leaders in last night's games", EVAL).date == date(2026, 4, 12)
    assert resolve("Should I bet on the Lakers tonight?", EVAL).date == date(2026, 4, 13)


def test_ranges() -> None:
    assert resolve("3PA rate since 2010", EVAL).seasons == ("2010-11", "2025-26")
    assert resolve("scoring now vs the 1990s", EVAL).seasons == ("1990-91", "1999-00")
    assert resolve("Thunder wins over the last 5 seasons", EVAL).seasons == ("2021-22", "2025-26")


def test_season_boundaries() -> None:
    # Off-season: "this season" is the one that just ended.
    assert resolve("who leads in scoring this season", OFFSEASON).season == "2025-26"
    # Once the new season has games, it is "this season".
    assert resolve("who leads in scoring this season", OPENING_WEEK).season == "2026-27"
    assert resolve("last season", OPENING_WEEK).season == "2025-26"


def test_no_time_phrase() -> None:
    r = resolve("Who has the most career assists in NBA history?", EVAL)
    assert r.season is None and r.date is None
