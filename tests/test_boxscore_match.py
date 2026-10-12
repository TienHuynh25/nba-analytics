"""Gate 1 check (task 1.21): 20 sampled box scores match NBA.com exactly.

Our player_game rows come from LeagueGameLog. This compares them, player by player, with an
independent NBA.com endpoint, the per-game BoxScoreTraditionalV3. The 20 games are a
deterministic sample (by hash of game_id) of regular-season and playoff games from 1996-97 on,
the seasons whose game logs are complete (ingest/ENDPOINTS.md, G1).

Runs against NBA_CHECK_DB, else the published ``current`` snapshot, else the dev build.
Network test: ``uv run pytest tests/test_boxscore_match.py -m network``.
"""

import os
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.config import REPO_ROOT, sources
from ingest import snapshots
from ingest.client import NbaClient

pytestmark = pytest.mark.network

STATS = {
    "pts": "points",
    "reb": "reboundsTotal",
    "ast": "assists",
    "stl": "steals",
    "blk": "blocks",
    "tov": "turnovers",
    "fgm": "fieldGoalsMade",
    "fga": "fieldGoalsAttempted",
    "fg3m": "threePointersMade",
    "fg3a": "threePointersAttempted",
    "ftm": "freeThrowsMade",
    "fta": "freeThrowsAttempted",
    "oreb": "reboundsOffensive",
    "dreb": "reboundsDefensive",
    "pf": "foulsPersonal",
    "plus_minus": "plusMinusPoints",
}


def check_db() -> Path | None:
    if os.environ.get("NBA_CHECK_DB"):
        return Path(os.environ["NBA_CHECK_DB"])
    cur = snapshots.current(sources())
    if cur is not None:
        return cur.db
    dev = REPO_ROOT / "data" / "build" / "dev.duckdb"
    return dev if dev.exists() else None


def sample_games(con: duckdb.DuckDBPyConnection, n: int = 20) -> list[str]:
    rows = con.execute(
        """select game_id from marts.games
           where season_start >= 1996 and season_type in ('Regular Season', 'Playoffs')
           order by hash(game_id) limit ?""",
        [n],
    ).fetchall()
    return [r[0] for r in rows]


def nba_box(client: NbaClient, game_id: str) -> dict[int, dict[str, Any]]:
    body = client.fetch(
        "boxscoretraditionalv3",
        {
            "GameID": game_id,
            "StartPeriod": 0,
            "EndPeriod": 0,
            "StartRange": 0,
            "EndRange": 0,
            "RangeType": 0,
        },
    )
    box = body["boxScoreTraditional"]
    out: dict[int, dict[str, Any]] = {}
    for side in ("homeTeam", "awayTeam"):
        for p in box[side]["players"]:
            s = p["statistics"]
            if not s.get("minutes") or s["minutes"] in ("", "0:00", "PT00M00.00S"):
                continue  # did not play: absent from LeagueGameLog
            out[int(p["personId"])] = {k: s[v] for k, v in STATS.items()}
    return out


@pytest.mark.skipif(check_db() is None, reason="no snapshot or dev build to check")
def test_twenty_box_scores_match_nba_com() -> None:
    db = check_db()
    assert db is not None
    con = duckdb.connect(str(db), read_only=True)
    games = sample_games(con)
    assert len(games) == 20
    client = NbaClient(sources().nba_api)
    mismatches: list[str] = []
    compared = 0
    for gid in games:
        ours = {
            r[0]: dict(zip(STATS, r[1:], strict=True))
            for r in con.execute(
                f"select player_id, {', '.join(STATS)} from marts.player_game where game_id = ?",
                [gid],
            ).fetchall()
        }
        theirs = nba_box(client, gid)
        if set(ours) != set(theirs):
            mismatches.append(f"{gid}: players differ {set(ours) ^ set(theirs)}")
            continue
        compared += len(theirs)
        for pid, stats in theirs.items():
            for k, v in stats.items():
                if ours[pid][k] != v:
                    mismatches.append(f"{gid} player {pid} {k}: ours {ours[pid][k]}, NBA.com {v}")
    con.close()
    assert not mismatches, "\n".join(mismatches[:20])
    assert compared >= 20 * 15, f"only {compared} player lines compared"
