# ruff: noqa: E501  (long SQL oracle strings read better on one line)
"""Tool branches the first oracle file did not reach: zones, streaks, finals, box leaders,
game-level sorts, compare scopes and ordering, and era handling in leaders (test plan L3).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.snapshot import FileSnapshotStore
from app.tools.base import ToolError
from app.tools.stats import run_tool

S = "2024-25"
SGA, JOKIC = 1628983, 203999
OKC, BOS = 1610612760, 1610612738


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def q(store: FileSnapshotStore, sql: str, *params: Any) -> list[tuple[Any, ...]]:
    return store.connection().execute(sql, list(params)).fetchall()


# --- shot zones (the fixture has playoff shots only) -----------------------------------------


def test_zone_breakdown_matches_shot_rows_and_shares_sum_to_100(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats",
        {
            "player_ids": [SGA],
            "season": S,
            "season_type": "Playoffs",
            "metrics": ["shot_attempts", "shot_fg_pct"],
            "breakdown": "zone",
        },
        store,
    )
    want = {
        z: (n, made / n)
        for z, n, made in q(
            store,
            "select zone, count(*), sum(made::int) from marts.shots "
            "where player_id=? and season=? and season_type='Playoffs' group by zone",
            SGA,
            S,
        )
    }
    assert {x["zone"] for x in r.rows} == set(want)
    for x in r.rows:
        assert x["shot_attempts"] == want[x["zone"]][0]
        assert x["shot_fg_pct"] == pytest.approx(want[x["zone"]][1])
    assert sum(x["share_pct"] for x in r.rows) == pytest.approx(100, abs=0.5)
    attempts = [x["shot_attempts"] for x in r.rows]
    assert attempts == sorted(attempts, reverse=True)


def test_zone_breakdown_without_shots_says_so(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats",
        {"player_ids": [SGA], "season": S, "metrics": ["shot_attempts"], "breakdown": "zone"},
        store,
    )  # regular season: the fixture has none
    assert r.rows == [] and r.notes


def test_zone_breakdown_rejects_non_shot_metrics(store: FileSnapshotStore) -> None:
    with pytest.raises(Exception, match="zone"):
        run_tool(
            "get_player_stats",
            {"player_ids": [SGA], "season": S, "metrics": ["points"], "breakdown": "zone"},
            store,
        )


# --- games: streaks, finals, box leaders, sorts ----------------------------------------------


def longest_streak(store: FileSnapshotStore, team: int, win: bool) -> int:
    rows = q(
        store,
        "select winner_team_id = ? from marts.games where season=? and season_type='Regular Season' "
        "and (home_team_id=? or away_team_id=?) order by game_date, game_id",
        team,
        S,
        team,
        team,
    )
    best = cur = 0
    for (won,) in rows:
        cur = cur + 1 if bool(won) == win else 0
        best = max(best, cur)
    return best


@pytest.mark.parametrize("kind", ["win", "loss"])
def test_longest_streaks_match_a_python_recount(store: FileSnapshotStore, kind: str) -> None:
    r = run_tool("get_games", {"team_ids": [OKC], "season": S, "streak": kind}, store)
    assert r.rows[0]["streak"] == longest_streak(store, OKC, kind == "win")
    assert r.rows[0]["from"] <= r.rows[0]["to"]


def test_finals_are_one_series_between_two_teams(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_games",
        {"season": S, "season_types": ["Playoffs"], "finals_only": True, "limit": 20},
        store,
    )
    assert 4 <= len(r.rows) <= 7
    assert all(x["game_id"].startswith("00424") for x in r.rows)
    teams = {x["home_team_name"] for x in r.rows} | {x["away_team_name"] for x in r.rows}
    assert len(teams) == 2


def test_box_leaders_equal_the_max_in_the_box_score(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"season": S, "box_leaders": True, "limit": 5}, store)
    for x in r.rows:
        best = q(
            store,
            "select max(pts), max(reb), max(ast) from marts.player_game where game_id=?",
            x["game_id"],
        )[0]
        assert (x["pts_leader_value"], x["reb_leader_value"], x["ast_leader_value"]) == best


def test_player_points_sort_gives_the_season_high(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"season": S, "sort": "player_points_desc", "limit": 3}, store)
    top = q(
        store,
        "select pts from marts.player_game where season=? and season_type='Regular Season' order by pts desc limit 3",
        S,
    )
    assert [x["pts"] for x in r.rows] == [p for (p,) in top]


def test_single_date_returns_every_game_that_day(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"date": "2025-01-15"}, store)
    n = q(
        store,
        "select count(*) from marts.games where game_date = date '2025-01-15' and season_type='Regular Season'",
    )[0][0]
    assert len(r.rows) == n > 0


# --- leaders: filters, teams, eras -----------------------------------------------------------


def test_team_leaders_sorted_and_match_team_season(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_leaders", {"entity": "team", "metric": "wins", "season": S, "limit": 5}, store
    )
    want = q(
        store,
        "select wins from marts.team_season where season=? and season_type='Regular Season' order by wins desc limit 5",
        S,
    )
    assert [x["wins"] for x in r.rows] == [w for (w,) in want]


def test_triple_double_leader_matches_box_score_count(store: FileSnapshotStore) -> None:
    r = run_tool("get_leaders", {"metric": "triple_doubles", "season": S, "limit": 1}, store)
    n = q(
        store,
        "select count(*) from marts.player_game where player_id=? and season=? "
        "and season_type='Regular Season' and pts>=10 and reb>=10 and ast>=10",
        r.rows[0]["player_id"],
        S,
    )[0][0]
    assert r.rows[0]["triple_doubles"] == n


@pytest.mark.parametrize("metric", ["steals", "steals_per_game", "blocks"])
def test_leaders_in_an_untracked_era_say_not_tracked(store: FileSnapshotStore, metric: str) -> None:
    try:
        r = run_tool("get_leaders", {"metric": metric, "season": "1970-71"}, store)
    except ToolError as exc:
        pytest.fail(f"raised {exc}")
    assert r.not_tracked and r.not_tracked[0].first_season == "1973-74"


def test_per_game_leaders_before_the_first_rule_era_fail_with_a_clear_error(
    store: FileSnapshotStore,
) -> None:
    """Known gap (qualification rules start at 2013-14): the error is explicit, never a wrong
    unqualified leader. Reported to the developer as a spec gap, not a defect."""
    with pytest.raises(ToolError, match="qualification rule"):
        run_tool("get_leaders", {"metric": "points_per_game", "season": "2005-06"}, store)


def test_unqualified_flag_bypasses_the_rule_in_any_era(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_leaders", {"metric": "points_per_game", "season": S, "qualified": False}, store
    )
    assert r.rows  # no ToolError path when the caller opts out


# --- compare ---------------------------------------------------------------------------------


def test_compare_teams_keeps_requested_order(store: FileSnapshotStore) -> None:
    r = run_tool("compare", {"team_ids": [OKC, BOS], "metrics": ["wins"], "season": S}, store)
    assert [x["team_id"] for x in r.rows] == [OKC, BOS]


def test_compare_first_n_seasons_gives_n_rows_per_player(store: FileSnapshotStore) -> None:
    r = run_tool(
        "compare",
        {
            "player_ids": [SGA, JOKIC],
            "metrics": ["points_per_game"],
            "scope": "first_n_seasons",
            "n_seasons": 1,
        },
        store,
    )
    assert sorted(x["player_id"] for x in r.rows) == sorted([SGA, JOKIC])
    assert {x["season_number"] for x in r.rows} == {1}


def test_compare_career_equals_get_career(store: FileSnapshotStore) -> None:
    c = run_tool(
        "compare",
        {"player_ids": [SGA, JOKIC], "metrics": ["points"], "scope": "career"},
        store,
    )
    for row in c.rows:
        k = run_tool("get_career", {"player_ids": [row["player_id"]], "metrics": ["points"]}, store)
        assert row["points"] == k.rows[0]["points"]
