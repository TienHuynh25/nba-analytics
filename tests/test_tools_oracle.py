"""Typed tools checked against independent oracles (test plan layer L3).

Each expected value is computed from the marts (box scores, team_season, awards), not through
the semantic views and tool SQL, so a bug shared by the registry expression and the tool is
still visible. The fixture is the 2024-25 season only.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from app.format import display
from app.snapshot import FileSnapshotStore
from app.tools.base import ToolArgError
from app.tools.stats import TOOLS, run_tool
from app.verifier import Evidence, check
from metrics.schema import Grain, registry

S = "2024-25"
SGA, JOKIC = 1628983, 203999
OKC = 1610612760
RS = "Regular Season"


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def q(store: FileSnapshotStore, sql: str, *params: Any) -> list[tuple[Any, ...]]:
    return store.connection().execute(sql, list(params)).fetchall()


# --- career / player stats vs box scores ---------------------------------------------------


def test_career_points_equal_sum_of_box_scores(store: FileSnapshotStore) -> None:
    r = run_tool("get_career", {"player_ids": [SGA], "metrics": ["points", "games_played"]}, store)
    pts, gp = q(
        store,
        "select sum(pts), count(*) from marts.player_game where player_id=? and season_type=?",
        SGA,
        RS,
    )[0]
    assert r.rows[0]["points"] == pts
    assert r.rows[0]["games_played"] == gp


def test_career_season_type_playoffs_is_separate(store: FileSnapshotStore) -> None:
    rs = run_tool("get_career", {"player_ids": [SGA], "metrics": ["points"]}, store)
    po = run_tool(
        "get_career",
        {"player_ids": [SGA], "metrics": ["points"], "season_type": "Playoffs"},
        store,
    )
    assert rs.rows[0]["points"] != po.rows[0]["points"]
    assert "playoffs" in po.source.lower()


def test_player_with_no_playoff_games_says_so_not_zero(store: FileSnapshotStore) -> None:
    [pid] = [
        r[0]
        for r in q(
            store,
            "select player_id from marts.player_season where season_type=? and gp>=50 and "
            "player_id not in (select player_id from marts.player_season "
            "where season_type='Playoffs') limit 1",
            RS,
        )
    ]
    r = run_tool(
        "get_career", {"player_ids": [pid], "metrics": ["points"], "season_type": "Playoffs"}, store
    )
    assert r.rows == [] and r.notes


# --- standings / team stats ----------------------------------------------------------------


@pytest.mark.parametrize("conf", ["East", "West"])
def test_standings_are_complete_ordered_and_consistent(store: FileSnapshotStore, conf: str) -> None:
    r = run_tool("get_standings", {"season": S, "conference": conf}, store)
    assert len(r.rows) == 15
    assert [x["conference_rank"] for x in r.rows] == sorted(x["conference_rank"] for x in r.rows)
    wins = [x["wins"] for x in r.rows]
    assert wins == sorted(wins, reverse=True) or r.rows[0]["wins"] >= r.rows[-1]["wins"]
    for x in r.rows:
        assert x["wins"] + x["losses"] == 82
        assert x["win_pct"] == pytest.approx(x["wins"] / 82)


def test_league_wins_equal_losses(store: FileSnapshotStore) -> None:
    rows = run_tool("get_standings", {"season": S, "limit": 30}, store).rows
    assert len(rows) == 30
    assert sum(x["wins"] for x in rows) == sum(x["losses"] for x in rows) == 1230


def test_team_stats_match_games_table(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_team_stats", {"team_ids": [OKC], "season": S, "metrics": ["wins", "losses"]}, store
    )
    w = q(
        store,
        "select count(*) from marts.games where season=? and season_type=? and winner_team_id=?",
        S,
        RS,
        OKC,
    )[0][0]
    assert r.rows[0]["wins"] == w == 68


# --- games ---------------------------------------------------------------------------------


def test_games_sorted_by_margin_match_games_table(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"season": S, "sort": "margin_desc", "limit": 5}, store)
    want = q(
        store,
        "select game_id, margin from marts.games where season=? and season_type=? "
        "order by margin desc, game_id limit 5",
        S,
        RS,
    )
    assert [x["margin"] for x in r.rows] == [m for _, m in want]
    assert all(x["margin"] == abs(x["home_pts"] - x["away_pts"]) for x in r.rows)


def test_overtime_only_returns_only_overtime_games(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"season": S, "overtime_only": True, "limit": 100}, store)
    n = q(
        store,
        "select count(*) from marts.games where season=? and season_type=? and periods>4",
        S,
        RS,
    )[0][0]
    assert r.rows and all(x["periods"] > 4 for x in r.rows)
    assert len(r.rows) == min(n, 100)


def test_team_last_n_games_are_the_latest(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"team_ids": [OKC], "season": S, "last_n": 3}, store)
    want = q(
        store,
        "select game_date from marts.games where season=? and season_type=? and "
        "(home_team_id=? or away_team_id=?) order by game_date desc limit 3",
        S,
        RS,
        OKC,
        OKC,
    )
    assert [x["game_date"] for x in r.rows] == [d for (d,) in want]


# --- awards, records, trend ----------------------------------------------------------------


def test_mvp_matches_awards_mart(store: FileSnapshotStore) -> None:
    r = run_tool("get_awards", {"award": "NBA Most Valuable Player", "season": S}, store)
    want = q(
        store,
        "select player_id from marts.awards where season=? and award = 'NBA Most Valuable Player'",
        S,
    )
    if want:
        assert {x["player_id"] for x in r.rows} == {p for (p,) in want}


def test_single_game_records_are_not_below_any_box_score_in_fixture(
    store: FileSnapshotStore,
) -> None:
    """A curated all-time record can never be lower than a real game in the data."""
    r = run_tool("get_record", {"record": "most_points_game"}, store)
    best = q(store, "select max(pts) from marts.player_game")[0][0]
    assert r.rows[0]["value"] >= best


def test_league_trend_equals_avg_team_points(store: FileSnapshotStore) -> None:
    r = run_tool("get_trend", {"entity": "league", "metric": "league_points_per_game"}, store)
    got = {x["season"]: x["league_points_per_game"] for x in r.rows if x["season"] == S}
    want = q(
        store,
        "select sum(pts)*1.0/sum(gp) from marts.team_season where season=? and season_type=?",
        S,
        RS,
    )[0][0]
    assert got[S] == pytest.approx(want, abs=0.05)


# --- invariants swept over the whole registry ----------------------------------------------


def _metrics(grain: Grain) -> list[str]:
    return [m.name for m in registry().metrics if grain in m.grains]


@pytest.mark.parametrize("metric", _metrics(Grain.player_season))
def test_player_leaders_sorted_nonnull_and_bounded(store: FileSnapshotStore, metric: str) -> None:
    r = run_tool("get_leaders", {"metric": metric, "season": S, "limit": 7}, store)
    vals = [x[metric] for x in r.rows]
    assert len(vals) <= 7
    assert all(v is not None for v in vals)
    assert vals == sorted(vals, reverse=registry().metric(metric).higher_is_better)
    assert "data through" in r.source


@pytest.mark.parametrize("metric", _metrics(Grain.player_season))
def test_leader_values_pass_the_verifier_when_restated(
    store: FileSnapshotStore, metric: str
) -> None:
    r = run_tool("get_leaders", {"metric": metric, "season": S, "limit": 3}, store)
    ev = Evidence(values=r.values(), args_text=[S, "top 3"])
    for x in r.rows:
        if x[metric] is not None:
            assert check(display(x[metric], metric, r.metrics), ev).ok


@pytest.mark.parametrize("metric", _metrics(Grain.team_season))
def test_team_metrics_are_available_for_a_team(store: FileSnapshotStore, metric: str) -> None:
    r = run_tool("get_team_stats", {"team_ids": [OKC], "season": S, "metrics": [metric]}, store)
    assert len(r.rows) == 1 and r.rows[0][metric] is not None


def test_career_grain_gaps_are_clean_arg_errors_not_crashes(store: FileSnapshotStore) -> None:
    for m in _metrics(Grain.player_season):
        if Grain.player_career in registry().metric(m).grains:
            continue
        with pytest.raises(ToolArgError):
            run_tool("get_career", {"player_ids": [SGA], "metrics": [m]}, store)


def test_every_tool_rejects_unknown_arguments_without_querying() -> None:
    class Boom:
        manifest: ClassVar[dict[str, Any]] = {}
        snapshot_id = "x"

        def connection(self) -> Any:
            raise AssertionError("queried")

    for name in TOOLS:
        with pytest.raises(ToolArgError):
            run_tool(name, {"definitely_not_an_arg": 1}, Boom())
