"""Build the one-season fixture database for unit tests (task 1.27).

Usage: ``uv run python -m ingest.fixture [--season 2024-25]``

Lands only the raw files for one season: its game logs, season stats, standings and shots; the
per-player files (career stats, awards, info) for players who appeared in it; and the reference
endpoints. It then runs the same dbt project and commits the result as a Parquet export in
``tests/fixtures/nba_fixture/`` (small enough for git; a DuckDB file carries ~13 MB of fixed block
overhead). :func:`ensure_fixture_db` rebuilds ``tests/fixtures/nba_fixture.duckdb`` from it, in
under a second, for the tests. In the fixture, shots are a table rather than a view over Parquet
(that view stores an absolute path). The staging schema is kept: the domain checks read it, and
``tests/test_domain_checks.py`` plants errors in a copy of the fixture to prove each check fires.
Season tables keep only seasons whose games are present, so careers in the fixture hold that one
season; the career-vs-source check is skipped (dbt var ``fixture``).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

import duckdb

from app.config import REPO_ROOT, sources
from ingest.land import land
from ingest.raw_store import ALL
from ingest.snapshots import run_dbt
from metrics import generate_views

FIXTURES = REPO_ROOT / "tests" / "fixtures"
FIXTURE_DB = FIXTURES / "nba_fixture.duckdb"
FIXTURE_EXPORT = FIXTURES / "nba_fixture"
PER_PLAYER = {"playercareerstats", "playerawards", "commonplayerinfo"}
REFERENCE = {"commonallplayers", "franchisehistory", "teamyearbyyearstats"}


def season_players(raw: Path, season: str) -> set[int]:
    ids: set[int] = set()
    for f in (raw / "leaguegamelog_p" / season).glob("*/*.json"):
        body = json.loads(f.read_text())["response"]
        rs = body["resultSets"][0]
        i = rs["headers"].index("PLAYER_ID")
        ids.update(int(r[i]) for r in rs["rowSet"])
    return ids


def build(season: str) -> Path:
    cfg = sources()
    raw = cfg.resolve(cfg.paths.raw)
    players = season_players(raw, season)
    if not players:
        raise SystemExit(f"no player game logs for {season} in {raw}")

    def keep(key: str, path: Path, doc: dict[str, Any]) -> bool:
        if key in REFERENCE:
            return True
        if key in PER_PLAYER:
            return int(doc["params"]["PlayerID"]) in players
        return bool(doc["season"] == season and doc["season"] != ALL)

    work = REPO_ROOT / "data" / "build" / "fixture"
    work.mkdir(parents=True, exist_ok=True)
    landing = work / "landing.duckdb"
    generate_views.write()
    land(raw, landing, work / "landing_work", keep=keep)
    tmp_db = work / "nba_fixture.duckdb"
    tmp_db.unlink(missing_ok=True)
    shots = work / "shots"
    shutil.rmtree(shots, ignore_errors=True)
    run_dbt(tmp_db, shots, landing, None, {"fixture": True})
    con = duckdb.connect(str(tmp_db))
    try:
        con.execute("create table marts.shots_table as select * from marts.shots")
        con.execute("drop view marts.shots")
        con.execute("alter table marts.shots_table rename to shots")
        shutil.rmtree(FIXTURE_EXPORT, ignore_errors=True)
        con.execute(f"export database '{FIXTURE_EXPORT}' (format parquet, compression zstd)")
    finally:
        con.close()
    FIXTURE_DB.unlink(missing_ok=True)
    return ensure_fixture_db()


def ensure_fixture_db() -> Path:
    """Build ``nba_fixture.duckdb`` from the committed export if it is missing or older."""
    marker = FIXTURE_EXPORT / "schema.sql"
    if FIXTURE_DB.exists() and FIXTURE_DB.stat().st_mtime >= marker.stat().st_mtime:
        return FIXTURE_DB
    tmp = FIXTURE_DB.with_suffix(f".{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.execute(f"import database '{FIXTURE_EXPORT}'")
    finally:
        con.close()
    tmp.replace(FIXTURE_DB)
    return FIXTURE_DB


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2024-25")
    args = ap.parse_args()
    t = time.monotonic()
    build(args.season)
    size = sum(p.stat().st_size for p in FIXTURE_EXPORT.rglob("*"))
    print(f"{FIXTURE_EXPORT} ({size / 1e6:.1f} MB) in {time.monotonic() - t:.0f} s")


if __name__ == "__main__":
    main()
