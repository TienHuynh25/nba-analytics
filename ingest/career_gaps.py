"""Reviewed NBA.com player-endpoint gaps (decision 0009 and its amendment, tasks T-GAP, T-GAP2).

The seed ``transform/seeds/known_player_career_gaps.csv`` lists what NBA.com does not give us:
``playercareerstats`` for 219 whole players (``season`` blank), season rows for players whose
file is empty or partial, and ``commonplayerinfo`` for one id. Backfill status counts a listed
unit as documented; an unlisted failure stays pending.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import duckdb

from app.config import REPO_ROOT

SEED = REPO_ROOT / "transform" / "seeds" / "known_player_career_gaps.csv"
RECONCILED_TYPES = ("Regular Season", "Playoffs")
CAREERSTATS = "playercareerstats"

# Reverse direction (DEF-012): player_season rows with no game-log rows, all before 1996-97.
# Pinned so that a new one fails the full-build test. Source of truth stays player_season.
PINNED_NO_GAME_LOG: tuple[tuple[int, str, str], ...] = (
    (438, "1992-93", "Regular Season"),
    (438, "1995-96", "Regular Season"),
    (709, "1995-96", "Regular Season"),
    (715, "1995-96", "Regular Season"),
    (919, "1990-91", "Regular Season"),
    (919, "1991-92", "Playoffs"),
    (919, "1991-92", "Regular Season"),
    (919, "1992-93", "Regular Season"),
    (919, "1993-94", "Regular Season"),
    (919, "1994-95", "Regular Season"),
    (919, "1995-96", "Regular Season"),
    (1134, "1991-92", "Regular Season"),
    (1134, "1992-93", "Regular Season"),
    (1134, "1993-94", "Regular Season"),
    (76451, "1946-47", "Regular Season"),
    (76630, "1953-54", "Playoffs"),
    (76818, "1949-50", "Playoffs"),
    (76939, "1954-55", "Regular Season"),
    (77266, "1954-55", "Regular Season"),
    (77536, "1954-55", "Regular Season"),
    (77686, "1948-49", "Regular Season"),
    (77695, "1954-55", "Regular Season"),
)


@dataclass(frozen=True)
class GapRow:
    player_id: int
    endpoint: str
    cls: str
    season: str  # blank: the whole player
    season_type: str


def load_rows(path: Path = SEED) -> list[GapRow]:
    with path.open(newline="", encoding="utf-8") as f:
        return [
            GapRow(int(r["player_id"]), r["endpoint"], r["class"], r["season"], r["season_type"])
            for r in csv.DictReader(f)
        ]


def load_gaps(path: Path = SEED) -> set[tuple[str, int]]:
    """(endpoint, player_id) pairs listed in the seed."""
    return {(r.endpoint, r.player_id) for r in load_rows(path)}


def reconcile_player_seasons(
    con: duckdb.DuckDBPyConnection, rows: list[GapRow]
) -> dict[str, list[tuple[int, str, str]]]:
    """Compare player-seasons in ``player_season`` with those in ``player_game``.

    ``unexplained``: in the game logs, absent from ``player_season``, and not covered by a
    ``playercareerstats`` seed row (whole player, or that exact season). ``listed_gap``: the
    explained differences. ``listed_with_rows``: seed rows whose player-season now exists in
    ``player_season`` (a recovered id that must leave the seed).
    """
    con.execute("create or replace temp table _gap_whole(player_id integer)")
    con.execute(
        "create or replace temp table _gap_season(player_id integer, season varchar, "
        "season_type varchar)"
    )
    cs = [r for r in rows if r.endpoint == CAREERSTATS]
    con.executemany(
        "insert into _gap_whole values (?)", [(r.player_id,) for r in cs if not r.season]
    )
    con.executemany(
        "insert into _gap_season values (?, ?, ?)",
        [(r.player_id, r.season, r.season_type) for r in cs if r.season],
    )
    types = ",".join(f"'{t}'" for t in RECONCILED_TYPES)
    missing = (
        "select distinct player_id, season, season_type from marts.player_game "
        f"where season_type in ({types}) "
        "except select player_id, season, season_type from marts.player_season"
    )
    listed = (
        "(player_id in (select player_id from _gap_whole) or (player_id, season, season_type) "
        "in (select player_id, season, season_type from _gap_season))"
    )

    def q(sql: str) -> list[tuple[int, str, str]]:
        return [(int(a), str(b), str(c)) for a, b, c in con.execute(sql).fetchall()]

    return {
        "unexplained": q(f"select * from ({missing}) where not {listed} order by all"),
        "listed_gap": q(f"select * from ({missing}) where {listed} order by all"),
        "listed_with_rows": q(
            "select distinct player_id, season, season_type from marts.player_season "
            f"where {listed} order by all"
        ),
    }


def reverse_direction(con: duckdb.DuckDBPyConnection) -> list[tuple[int, str, str]]:
    """``player_season`` rows without any ``player_game`` row (DEF-012)."""
    rows = con.execute(
        "select player_id, season, season_type from marts.player_season "
        "except select player_id, season, season_type from marts.player_game order by all"
    ).fetchall()
    return [(int(a), str(b), str(c)) for a, b, c in rows]


def regular_season_games(con: duckdb.DuckDBPyConnection) -> dict[int, int]:
    rows = con.execute(
        "select player_id, count(*) from marts.player_game "
        "where season_type = 'Regular Season' group by 1"
    ).fetchall()
    return {int(p): int(n) for p, n in rows}


def empty_successful(
    raw_root: Path, games: Mapping[int, int], seeded: set[int]
) -> list[tuple[int, int]]:
    """Players whose latest ``playercareerstats`` file has no regular-season totals although they
    have regular-season game-log games and are not in the seed. Returns (player_id, games).

    A never-played player and a playoff-only player (no regular-season games) are not flagged.
    """
    latest: dict[int, tuple[str, int]] = {}  # player -> (fetched_at, regular-season total rows)
    for f in (raw_root / CAREERSTATS).glob("*/*/*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        pid, at = int(doc["params"]["PlayerID"]), str(doc["fetched_at"])
        n = 0
        for rs in doc["response"].get("resultSets", []):
            if rs["name"] == "SeasonTotalsRegularSeason":
                n = len(rs["rowSet"])
        if pid not in latest or at > latest[pid][0]:
            latest[pid] = (at, n)
    return sorted(
        (pid, games[pid])
        for pid, (_, n) in latest.items()
        if n == 0 and games.get(pid, 0) > 0 and pid not in seeded
    )
