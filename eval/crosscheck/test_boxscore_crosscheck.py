"""T-2.7 / R-039 scope floor: pinned eval snapshot box scores vs NBA.com BoxScoreTraditionalV3.

Compares the same 16 fields as tests/test_boxscore_match.py (which samples by hash and is left
unchanged), on a fixed list instead: every 2025-26 game of 2026-04-12 (the last regular-season
night, including the last 3 games), two other 2025-26 games that gold values depend on (the
83-point game, Q54; the 55-point margin, Q58), and 6 playoff games from earlier seasons.

Reads the pinned snapshot read-only; writes nothing under data/. Set XC_BOX_OUT=<file> to save the
NBA.com lines (used by the cross-check for Q55).
Run: uv run pytest eval/crosscheck/test_boxscore_crosscheck.py -m network -v
"""

import json
import os
from pathlib import Path

import duckdb
import pytest

from app.config import REPO_ROOT, sources
from ingest.client import NbaClient
from tests.test_boxscore_match import STATS, nba_box

pytestmark = pytest.mark.network

DB = REPO_ROOT / "data/snapshots/eval_2025_26_rs/eval_2025_26_rs.duckdb"
# 2026-04-12 (0022501186..0022501200), the 83-point game (Q54), the 55-point margin (Q58)
LAST_NIGHT = [*(f"00225011{n}" for n in range(86, 100)), "0022501200"]
GAMES_2025_26 = [*LAST_NIGHT, "0022500938", "0022500547"]
PLAYOFF_GAMES = ["0042400407", "0041500407", "0040900407", "0040500406", "0040000087", "0049700088"]


@pytest.mark.skipif(not DB.exists(), reason="pinned eval snapshot not built")
def test_box_scores_match_nba_com() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    client = NbaClient(sources().nba_api)
    mismatches: list[str] = []
    saved: dict[str, dict[str, dict[str, object]]] = {}
    lines = 0
    for gid in GAMES_2025_26 + PLAYOFF_GAMES:
        ours = {
            r[0]: dict(zip(STATS, r[1:], strict=True))
            for r in con.execute(
                f"select player_id, {', '.join(STATS)} from marts.player_game where game_id = ?",
                [gid],
            ).fetchall()
        }
        assert ours, f"{gid} not in the snapshot"
        theirs = nba_box(client, gid)
        saved[gid] = {str(k): v for k, v in theirs.items()}
        if set(ours) != set(theirs):
            mismatches.append(f"{gid}: players differ {set(ours) ^ set(theirs)}")
        for pid in set(ours) & set(theirs):
            lines += 1
            for k, v in theirs[pid].items():
                if ours[pid][k] != v:
                    mismatches.append(f"{gid} player {pid} {k}: ours {ours[pid][k]}, NBA.com {v}")
        print(f"{gid}: {len(theirs)} NBA.com lines, {len(ours)} snapshot lines")
    con.close()
    print(f"requests={client.calls} games={len(GAMES_2025_26) + len(PLAYOFF_GAMES)} lines={lines}")
    out = os.environ.get("XC_BOX_OUT")
    if out:
        Path(out).write_text(json.dumps(saved))
    assert not mismatches, "\n".join(mismatches[:40])
    assert lines >= 20 * 15
