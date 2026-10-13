"""DEF-021: every tool query whose row order matters ends its ORDER BY in a unique key.

Ties (equal values) used to come back in whatever order DuckDB produced, so the same question
could list different players under ``LIMIT`` on two runs or two builds. A recording store
captures each query the tools run on the 2024-25 fixture.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.snapshot import FileSnapshotStore
from app.tools.stats import run_tool

S = "2024-25"
SGA, JOKIC = 1628983, 203999
OKC, BOS = 1610612760, 1610612738

# Keys that make an ORDER BY total for the tool's grain.
UNIQUE_KEYS = ("player_id", "team_id", "game_id", "franchise_id", "zone")
# One row per season for a single entity, so season alone is total.
SEASON_ONLY = re.compile(
    r"where season_type = \? and (player_id|team_id) = \?|from semantic\.league"
)

CALLS: list[tuple[str, dict[str, Any]]] = [
    (
        "get_player_stats",
        {"player_ids": [SGA], "season": S, "metrics": ["shot_attempts"], "breakdown": "zone"},
    ),
    ("get_leaders", {"metric": "points_per_game", "season": S, "limit": 5}),
    ("get_leaders", {"metric": "wins", "entity": "team", "season": S, "limit": 5}),
    ("get_leaders", {"metric": "points", "scope": "career", "limit": 5}),
    ("get_standings", {"season": S}),
    ("get_standings", {"season": S, "conference": "West"}),
    ("get_games", {"player_ids": [SGA], "season": S, "last_n": 3}),
    ("get_games", {"season": S, "sort": "player_points_desc", "limit": 3}),
    ("get_games", {"season": S, "sort": "margin_desc", "limit": 3}),
    ("get_games", {"team_ids": [OKC], "season": S, "limit": 3, "box_leaders": True}),
    ("get_games", {"team_ids": [OKC], "season": S, "streak": "win"}),
    ("get_record", {"record": "most_points_game", "limit": 3}),
    ("get_record", {"record": "career_triple_doubles", "limit": 3}),
    ("get_record", {"record": "best_regular_season_record", "limit": 3}),
    ("get_record", {"record": "most_championships", "limit": 3}),
    ("get_trend", {"metric": "points_per_game", "entity": "player", "player_ids": [JOKIC]}),
    ("get_awards", {"award": "NBA Most Valuable Player", "mode": "count_by_player"}),
    ("get_awards", {"award": "NBA Most Valuable Player"}),
    ("compare", {"team_ids": [OKC, BOS], "metrics": ["wins"], "season": S}),
]


class Recording:
    def __init__(self, store: FileSnapshotStore, seen: list[str]) -> None:
        self._store, self._seen = store, seen
        self.manifest, self.snapshot_id = store.manifest, store.snapshot_id

    def connection(self) -> "Recording":
        return self

    def execute(self, sql: str, params: list[Any] | None = None) -> duckdb.DuckDBPyConnection:
        self._seen.append(sql)
        return self._store.connection().execute(sql, params or [])

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def _outer_order_by(sql: str) -> str | None:
    """The ORDER BY of the outer query (not a window's), lower-cased, without LIMIT."""
    s = " ".join(sql.lower().split())
    s = re.sub(r"over \([^)]*\)", "over ()", s)
    if " order by " not in s:
        return None
    clause = s.rsplit(" order by ", 1)[1]
    return re.split(r" limit ", clause)[0]


IDS = [f"{t}-{i}" for i, (t, _) in enumerate(CALLS)]


@pytest.mark.parametrize(("tool", "args"), CALLS, ids=IDS)
def test_ordered_tool_queries_end_in_a_unique_key(
    store: FileSnapshotStore, tool: str, args: dict[str, Any]
) -> None:
    seen: list[str] = []
    run_tool(tool, args, Recording(store, seen))  # type: ignore[arg-type]
    ordered = [q for q in seen if _outer_order_by(q)]
    assert ordered, f"{tool} ran no ordered query"
    for q in ordered:
        clause = _outer_order_by(q) or ""
        if SEASON_ONLY.search(" ".join(q.lower().split())) and clause.strip() == "season":
            continue
        assert any(k in clause for k in UNIQUE_KEYS), f"no tie-break in: order by {clause}"


def test_tied_leaders_come_back_by_player_id(store: FileSnapshotStore) -> None:
    """Players tied on the metric are listed in player_id order, so a LIMIT cut is stable."""
    r = run_tool(
        "get_leaders",
        {"metric": "games_played", "season": S, "limit": 25, "qualified": False},
        store,
    )
    vals = [(row["games_played"], row["player_id"]) for row in r.rows]
    assert len({v for v, _ in vals}) < len(vals), "fixture should have tied games_played"
    assert vals == sorted(vals, key=lambda x: (-x[0], x[1]))
