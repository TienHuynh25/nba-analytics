"""Typed tools on the 2024-25 fixture (tasks 3.8-3.10, 3.12)."""

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import duckdb
import pytest

from app.snapshot import FileSnapshotStore
from app.tools.base import ToolArgError
from app.tools.stats import TOOLS, run_tool
from app.verifier import Evidence, check

S = "2024-25"
SGA, JOKIC, LUKA, CURRY = 1628983, 203999, 1629029, 201939
OKC, LAL, BOS, NYK = 1610612760, 1610612747, 1610612738, 1610612752


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def one(store: FileSnapshotStore, sql: str, *params: Any) -> Any:
    row = store.connection().execute(sql, list(params)).fetchone()
    assert row is not None
    return row[0]


class Exploding:
    """A store that fails if any query runs."""

    manifest: ClassVar[dict[str, Any]] = {}
    snapshot_id = "x"

    def connection(self) -> duckdb.DuckDBPyConnection:
        raise AssertionError("queried before validation")


def test_all_ten_tools_exist() -> None:
    assert len(TOOLS) == 10


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_leaders", {"metric": "not_a_metric", "season": S}),
        ("get_player_stats", {"player_ids": [SGA], "season": "2024", "metrics": ["points"]}),
        ("get_player_stats", {"player_ids": [SGA], "season": S, "metrics": []}),
        ("get_games", {"limit": 0}),
        ("compare", {"player_ids": [SGA], "metrics": ["points"], "unknown": 1}),
    ],
)
def test_invalid_args_rejected_before_any_query(tool: str, args: dict[str, Any]) -> None:
    with pytest.raises(ToolArgError):
        run_tool(tool, args, Exploding())


def test_player_stats_match_marts_and_source_line(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats",
        {"player_ids": [SGA], "season": S, "metrics": ["points_per_game"]},
        store,
    )
    want = one(
        store,
        "select pts / gp from marts.player_season where player_id = ? and "
        "season = ? and season_type = 'Regular Season'",
        SGA,
        S,
    )
    assert r.rows[0]["points_per_game"] == pytest.approx(want)
    assert round(want, 1) == 32.7  # SGA's 2024-25 scoring title
    assert r.source.startswith("points per game · 2024-25 regular season")
    assert "data through" in r.source


def test_traded_player_total_row_and_stint(store: FileSnapshotStore) -> None:
    total = run_tool(
        "get_player_stats",
        {"player_ids": [LUKA], "season": S, "metrics": ["games_played", "points"]},
        store,
    )
    lal = run_tool(
        "get_player_stats",
        {"player_ids": [LUKA], "season": S, "team_id": LAL, "metrics": ["games_played", "points"]},
        store,
    )
    assert (total.rows[0]["games_played"], total.rows[0]["points"]) == (50, 1408)
    assert (lal.rows[0]["games_played"], lal.rows[0]["points"]) == (28, 789)
    assert "with Los Angeles Lakers" in lal.source


def test_per_game_leaders_are_qualified(store: FileSnapshotStore) -> None:
    r = run_tool("get_leaders", {"metric": "points_per_game", "season": S, "limit": 10}, store)
    assert r.rows[0]["player_id"] == SGA
    for row in r.rows:
        assert row["gp"] >= math.ceil(0.7 * row["team_gp"]) or any(
            row["player_name"] in n for n in r.notes
        )
    assert "qualified" in r.source
    values = [row["points_per_game"] for row in r.rows]
    assert values == sorted(values, reverse=True)


def test_percentage_leaders_use_made_minimum(store: FileSnapshotStore) -> None:
    r = run_tool("get_leaders", {"metric": "three_point_pct", "season": S, "limit": 5}, store)
    assert all(row["threes_made"] >= 82 for row in r.rows)


def test_count_leaders_have_no_minimum(store: FileSnapshotStore) -> None:
    r = run_tool("get_leaders", {"metric": "blocks", "season": S}, store)
    best = one(
        store,
        "select max(blk) from marts.player_season where season = ? and "
        "season_type = 'Regular Season'",
        S,
    )
    assert r.rows[0]["blocks"] == best


def test_team_scoped_leader_reads_the_stint(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_leaders",
        {"metric": "points_per_game", "season": S, "team_id": LAL, "qualified": False},
        store,
    )
    assert r.rows[0]["team_name"] == "Los Angeles Lakers"


def test_standings_and_streak(store: FileSnapshotStore) -> None:
    west = run_tool("get_standings", {"season": S, "conference": "West"}, store)
    assert len(west.rows) == 15 and west.rows[0]["team_id"] == OKC
    streak = run_tool("get_games", {"team_ids": [OKC], "season": S, "streak": "win"}, store)
    # Independent check of the longest run of wins.
    wins = [
        r[0]
        for r in store.connection()
        .execute(
            "select winner_team_id = ? from marts.games where season = ? and season_type = "
            "'Regular Season' and ? in (home_team_id, away_team_id) order by game_date",
            [OKC, S, OKC],
        )
        .fetchall()
    ]
    best = cur = 0
    for w in wins:
        cur = cur + 1 if w else 0
        best = max(best, cur)
    assert streak.rows[0]["streak"] == best


def test_day_without_games_says_so(store: FileSnapshotStore) -> None:
    r = run_tool("get_games", {"date": "2024-08-01", "box_leaders": True}, store)
    assert r.rows == [] and r.notes == ["No games on 2024-08-01."]


def test_head_to_head_last_game(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_games",
        {
            "team_ids": [BOS, NYK],
            "last_n": 1,
            "season_types": ["Regular Season", "PlayIn", "Playoffs"],
        },
        store,
    )
    names = {r.rows[0]["home_team_name"], r.rows[0]["away_team_name"]}
    assert names == {"Boston Celtics", "New York Knicks"}


def test_not_tracked_names_first_season(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats", {"player_ids": [SGA], "season": "1970-71", "metrics": ["blocks"]}, store
    )
    assert [n.first_season for n in r.not_tracked] == ["1973-74"]
    assert "not tracked in 1970-71" in r.not_tracked[0].sentence()


def test_compare_keeps_requested_order(store: FileSnapshotStore) -> None:
    r = run_tool(
        "compare",
        {
            "player_ids": [JOKIC, SGA],
            "metrics": ["points_per_game"],
            "scope": "season",
            "season": S,
        },
        store,
    )
    assert [row["player_id"] for row in r.rows] == [JOKIC, SGA]


def test_result_values_feed_the_verifier(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats",
        {"player_ids": [SGA], "season": S, "metrics": ["points_per_game", "field_goal_pct"]},
        store,
    )
    row = r.rows[0]
    draft = (
        f"Shai Gilgeous-Alexander averaged {row['points_per_game']:.1f} points in "
        f"{row['gp']} games in 2024-25, shooting {100 * row['field_goal_pct']:.1f}%."
    )
    ev = Evidence(values=r.values(), args_text=r.args_text())
    assert check(draft, ev).ok, check(draft, ev).unmatched
    assert not check(draft.replace(f"{row['points_per_game']:.1f}", "35.0"), ev).ok


def test_stat_line_shorthand_and_source(store: FileSnapshotStore) -> None:
    r = run_tool(
        "get_player_stats", {"player_ids": [JOKIC], "season": S, "metrics": ["stat_line"]}, store
    )
    assert len(r.metrics) == 10 and r.source.startswith("stat line · 2024-25 regular season")
