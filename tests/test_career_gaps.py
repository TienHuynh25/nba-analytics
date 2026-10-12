"""T-GAP, T-GAP2 (decision 0009 and its amendment): reviewed NBA.com career-stat gaps stay
listed, reconciled, flagged when new, and never shown as zero or as a complete career."""

import csv
import json
import os
import shutil
from collections import Counter
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.format import table
from app.snapshot import FileSnapshotStore
from app.tools.stats import run_tool
from ingest.backfill import ET, STAGES, Checkpoints, Unit, last_completed_season, reconcile, run
from ingest.career_gaps import (
    PINNED_NO_GAME_LOG,
    SEED,
    empty_successful,
    load_gaps,
    load_rows,
    reconcile_player_seasons,
    reverse_direction,
)
from ingest.raw_store import RawStore
from tests.test_backfill import LAST, _fake_store

KLEBER, SGA = 1628467, 1628983
RS, PO = "Regular Season", "Playoffs"
# Pinned as literals on purpose: the wording is a contract, not an implementation detail.
NO_TOTALS = "The source has no season totals for this player."

# --- the seed -----------------------------------------------------------------------------------


def _seed() -> list[dict[str, str]]:
    with SEED.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_seed_has_242_unique_rows_with_notes_and_review_date() -> None:
    rows = _seed()
    assert len(rows) == 242
    key = {(r["player_id"], r["endpoint"], r["season"], r["season_type"]) for r in rows}
    assert len(key) == 242
    assert Counter(r["class"] for r in rows) == {
        "played-in-gamelogs": 203,
        "no-games": 16,
        "commonplayerinfo": 1,
        "empty-response": 15,
        "early-era-partial": 6,
        "other": 1,
    }
    assert Counter(r["endpoint"] for r in rows) == {"playercareerstats": 241, "commonplayerinfo": 1}
    assert all(r["note"].strip() and r["reviewed"] == "2026-10-11" for r in rows)
    assert {r["player_id"] for r in rows if r["endpoint"] == "commonplayerinfo"} == {"200603"}
    # whole-player rows have no season; the 22 season rows carry both columns
    season_rows = [r for r in rows if r["season"]]
    assert len(season_rows) == 22 and all(r["season_type"] in (RS, PO) for r in season_rows)
    assert all(not r["season_type"] for r in rows if not r["season"])


def test_seed_covers_265_player_seasons_and_211_players() -> None:
    rows = _seed()
    whole = [r for r in rows if r["class"] == "played-in-gamelogs"]
    season_rows = [r for r in rows if r["season"]]
    assert sum(int(r["gamelog_games"]) for r in whole) == 1841
    # 240 regular-season + 3 playoff player-seasons for the original 203 players (T-1.6a)
    assert sum(int(r["gamelog_seasons"]) for r in whole) == 243
    assert 243 + len(season_rows) == 265
    assert len({r["player_id"] for r in whole} | {r["player_id"] for r in season_rows}) == 211
    assert all(
        int(r["gamelog_games"]) == 0 == int(r["gamelog_seasons"])
        for r in rows
        if r["class"] == "no-games"
    )


# --- backfill status ----------------------------------------------------------------------------


def _warm(tmp: Path) -> tuple[RawStore, Checkpoints]:
    ckpt = Checkpoints(tmp / "ck")
    run(_fake_store(tmp, [], None), ckpt, list(STAGES), LAST)
    return RawStore(tmp / "raw", None), ckpt


def _drop(ckpt: Checkpoints, key: str, pid: int) -> None:
    ckpt._path(Unit.make(key, None, player_id=pid)).unlink()


def test_status_counts_listed_gap_as_documented_and_unlisted_as_missing(tmp_path: Path) -> None:
    store, ckpt = _warm(tmp_path)
    _drop(ckpt, "playercareerstats", 101)
    _drop(ckpt, "commonplayerinfo", 102)
    _drop(ckpt, "playerawards", 101)  # same player, endpoint not listed
    gaps = {("playercareerstats", 101), ("commonplayerinfo", 102)}
    rows = {s: (d, k, t) for s, d, k, t in reconcile(store, ckpt, LAST, gaps)}
    assert rows["players"] == (9 - 3, 2, 9)  # 1 awards unit still pending
    assert rows["reference"] == (2, 0, 2)
    # without the seed row the same unit is missing again
    rows = {s: (d, k, t) for s, d, k, t in reconcile(store, ckpt, LAST, gaps - {next(iter(gaps))})}
    done, known, total = rows["players"]
    assert known == 1 and total - done - known == 2


def _real_cache_status() -> tuple[int, int, int]:
    from app.config import sources

    cfg = sources()
    if not (cfg.resolve(cfg.paths.raw) / "playercareerstats").exists():
        pytest.skip("no raw cache")
    last = last_completed_season(datetime.now(ET).date())
    store = RawStore(cfg.resolve(cfg.paths.raw), None)
    ck = Checkpoints(cfg.resolve(cfg.paths.checkpoints) / "backfill")
    players = {s: (d, k, t) for s, d, k, t in reconcile(store, ck, last, load_gaps())}["players"]
    if players[0] + players[1] != players[2]:
        pytest.skip(f"backfill incomplete: {players}")
    return players


def test_status_on_the_real_cache_is_fully_accounted() -> None:
    done, known, total = _real_cache_status()
    # the 22 season rows are not endpoint units: the total does not change
    assert (done, known, total) == (15509, 220, 15729)


# --- empty-but-successful career files ----------------------------------------------------------


def _careerstats(raw: Path, pid: int, rs_rows: int, at: str, po_rows: int = 0) -> None:
    sets = [
        {"name": "SeasonTotalsRegularSeason", "rowSet": [[0]] * rs_rows},
        {"name": "SeasonTotalsPostSeason", "rowSet": [[0]] * po_rows},
    ]
    d = raw / "playercareerstats" / "_all" / at[:10]
    d.mkdir(parents=True, exist_ok=True)
    doc = {"params": {"PlayerID": pid}, "fetched_at": at, "response": {"resultSets": sets}}
    (d / f"{pid}.{at}.json").write_text(json.dumps(doc))


def test_empty_successful_flags_only_unseeded_players_with_regular_season_games(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "raw"
    games = {KLEBER: 531, 200: 40, 300: 10}
    _careerstats(raw, KLEBER, 0, "2026-09-30T23:50:54+00:00")  # empty, has games: flagged
    _careerstats(raw, 200, 0, "2026-09-30T23:50:54+00:00")  # empty, has games, seeded
    _careerstats(raw, 201, 0, "2026-09-30T23:50:54+00:00")  # empty, never played (not in games)
    _careerstats(
        raw, 1630492, 0, "2026-09-30T23:50:54+00:00", po_rows=1
    )  # playoff-only, 0 RS games
    _careerstats(raw, 300, 0, "2026-09-30T23:50:54+00:00")  # empty then recovered
    _careerstats(raw, 300, 4, "2026-10-11T03:34:37+00:00")
    _careerstats(raw, 400, 5, "2026-09-30T23:50:54+00:00")  # has totals
    assert empty_successful(raw, games, {200}) == [(KLEBER, 531)]
    assert empty_successful(raw, games, {200, KLEBER}) == []


def _dev_db() -> Path:
    from app.config import REPO_ROOT

    p = REPO_ROOT / "data" / "build" / "dev.duckdb"
    if not p.exists():
        pytest.skip("no dev build")
    return p


def test_empty_successful_on_the_real_cache_flags_nothing_until_kleber_is_unlisted() -> None:
    from app.config import sources
    from ingest.career_gaps import regular_season_games

    cfg = sources()
    raw = cfg.resolve(cfg.paths.raw)
    if not (raw / "playercareerstats").exists():
        pytest.skip("no raw cache")
    con = duckdb.connect(str(_dev_db()), read_only=True)
    try:
        games = regular_season_games(con)
    finally:
        con.close()
    seeded = {r.player_id for r in load_rows() if r.endpoint == "playercareerstats"}
    assert empty_successful(raw, games, seeded) == []
    flagged = empty_successful(raw, games, seeded - {KLEBER})
    assert (
        flagged == [(KLEBER, games[KLEBER])] and games[KLEBER] == 483
    )  # regular season only (531 with playoffs)


# --- reconciliation -----------------------------------------------------------------------------


@pytest.fixture()
def db(fixture_db_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect(":memory:")
    con.execute(f"attach '{fixture_db_path}' as f (read_only)")
    con.execute("create schema marts")
    for t in ("player_game", "player_season"):
        con.execute(f"create table marts.{t} as select * from f.marts.{t}")
    yield con
    con.close()


def test_fixture_reconciles_with_the_seed(db: duckdb.DuckDBPyConnection) -> None:
    got = reconcile_player_seasons(db, load_rows())
    assert got["unexplained"] == [] and got["listed_with_rows"] == []
    assert (KLEBER, "2024-25", RS) in got["listed_gap"]
    assert set(reverse_direction(db)) <= set(PINNED_NO_GAME_LOG)


def test_deleting_one_season_row_makes_it_unexplained(db: duckdb.DuckDBPyConnection) -> None:
    rows = load_rows()
    gone = next(
        r for r in rows if r.player_id == KLEBER and r.season == "2024-25" and r.season_type == RS
    )
    got = reconcile_player_seasons(db, [r for r in rows if r != gone])
    assert got["unexplained"] == [(KLEBER, "2024-25", RS)]


def test_unlisted_missing_player_seasons_fail(db: duckdb.DuckDBPyConnection) -> None:
    pid = int(
        db.execute(
            "select player_id from marts.player_season where season_type = 'Regular Season' "
            "order by gp desc limit 1"
        ).fetchone()[0]  # type: ignore[index]
    )
    db.execute("delete from marts.player_season where player_id = ?", [pid])
    got = reconcile_player_seasons(db, load_rows())
    assert pid in {p for p, _, _ in got["unexplained"]}


def test_listed_id_or_season_with_a_player_season_row_fails(db: duckdb.DuckDBPyConnection) -> None:
    from ingest.career_gaps import GapRow

    whole = GapRow(SGA, "playercareerstats", "played-in-gamelogs", "", "")
    got = reconcile_player_seasons(db, [*load_rows(), whole])
    assert {p for p, _, _ in got["listed_with_rows"]} == {SGA}
    one = GapRow(SGA, "playercareerstats", "other", "2024-25", RS)
    got = reconcile_player_seasons(db, [*load_rows(), one])
    assert got["listed_with_rows"] == [(SGA, "2024-25", RS)]


def test_a_new_reverse_direction_row_fails(db: duckdb.DuckDBPyConnection) -> None:
    db.execute(
        "insert into marts.player_season (player_id, season, season_type) "
        "values (999999, '2024-25', 'Regular Season')"
    )
    assert set(reverse_direction(db)) - set(PINNED_NO_GAME_LOG) == {(999999, "2024-25", RS)}


def test_full_build_reconciles_with_the_seed() -> None:
    if "NBA_RECON_DB" not in os.environ:
        pytest.skip("set NBA_RECON_DB to a full build to reconcile it")
    con = duckdb.connect(os.environ["NBA_RECON_DB"], read_only=True)
    rows = load_rows()
    got = reconcile_player_seasons(con, rows)
    assert got["unexplained"] == [] and got["listed_with_rows"] == []
    assert len(got["listed_gap"]) == 265
    # deleting any one of the 22 new rows makes it fail
    for gone in (r for r in rows if r.season):
        left = reconcile_player_seasons(con, [r for r in rows if r != gone])
        assert left["unexplained"] == [(gone.player_id, gone.season, gone.season_type)]
    # the reverse direction is exactly the pinned list; a 23rd would fail
    assert reverse_direction(con) == sorted(PINNED_NO_GAME_LOG)
    assert len(PINNED_NO_GAME_LOG) == 22


# --- tool layer ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def _ps(pid: int, season: str = "2024-25", st: str = RS) -> dict[str, Any]:
    return {
        "player_ids": [pid],
        "season": season,
        "season_type": st,
        "metrics": ["points", "games_played"],
    }


def test_kleber_has_no_player_season_rows_in_the_fixture(store: FileSnapshotStore) -> None:
    q = "select count(*) from marts.player_season where player_id = ?"
    assert store.connection().execute(q, [KLEBER]).fetchone() == (0,)


def test_kleber_gets_the_no_totals_sentence_in_all_three_tools(store: FileSnapshotStore) -> None:
    for st in (RS, PO):
        r = run_tool("get_player_stats", _ps(KLEBER, st=st), store)
        assert r.rows == [] and r.notes == [NO_TOTALS]
    c = run_tool(
        "get_career", {"player_ids": [KLEBER], "season_type": RS, "metrics": ["points"]}, store
    )
    assert c.rows == [] and c.notes == [NO_TOTALS]
    cmp = run_tool(
        "compare",
        {
            "player_ids": [KLEBER, SGA],
            "scope": "season",
            "season": "2024-25",
            "season_type": RS,
            "metrics": ["points"],
        },
        store,
    )
    assert [r["player_id"] for r in cmp.rows] == [SGA]
    assert cmp.notes == ["The source has no season totals for this player. Player id: 1628467."]
    for r in (c, cmp):
        assert not any("games for this player" in n for n in r.notes)


def test_unlisted_player_keeps_the_old_wording(store: FileSnapshotStore) -> None:
    r = run_tool("get_player_stats", _ps(SGA, season="1960-61"), store)
    assert r.notes == ["No 1960-61 regular season games for this player."]
    c = run_tool("get_career", {"player_ids": [1], "season_type": RS, "metrics": ["points"]}, store)
    assert c.notes == ["No regular season games for this player."]


def test_kleber_fallback_table_says_no_rows_and_the_new_sentence(
    store: FileSnapshotStore,
) -> None:
    from app.stats_path import StatsPath
    from tests.test_stats_path import Script, call

    llm = Script(
        [
            call("get_player_stats", player_ids=[KLEBER], season="2024-25", metrics=["points"]),
            "He scored 99 points.",
            "He scored 98 points.",
        ]
    )
    a, _ = StatsPath(store, llm).answer("How many points did Maxi Kleber score in 2024-25?")
    assert a.status == "fallback"
    assert "No rows." in a.text and NO_TOTALS in a.text
    assert "No rows." in table([], [])  # app/format.py unchanged


@pytest.fixture()
def planted(fixture_db_path: Path, tmp_path: Path) -> Iterator[FileSnapshotStore]:
    """A fixture copy where SGA is an early-era-partial player (1951-52 PO, 1956-57 RS)."""
    db = tmp_path / "nba_fixture.duckdb"
    shutil.copy2(fixture_db_path, db)
    con = duckdb.connect(str(db))
    ins = (
        "insert into seeds.known_player_career_gaps values "
        "(?, 'playercareerstats', ?, ?, ?, 21, 1, 'planted', '2026-10-11')"
    )
    con.execute(ins, [SGA, "early-era-partial", "1956-57", RS])
    con.execute(ins, [SGA, "early-era-partial", "1951-52", PO])
    con.close()
    yield FileSnapshotStore(db)


MISSING = (
    "The source is missing season totals for this player for: 1951-52 playoffs, "
    "1956-57 regular season. The totals here exclude those seasons."
)


def test_partial_player_gets_a_missing_seasons_note_on_every_tool(
    planted: FileSnapshotStore,
) -> None:
    r = run_tool("get_player_stats", _ps(SGA), planted)
    assert r.rows and r.notes == [MISSING]
    gone = run_tool("get_player_stats", _ps(SGA, "1956-57"), planted)
    assert gone.rows == [] and gone.notes == [NO_TOTALS, MISSING]
    c = run_tool(
        "get_career", {"player_ids": [SGA], "season_type": RS, "metrics": ["points"]}, planted
    )
    assert c.rows and c.notes == [MISSING]
    cmp = run_tool(
        "compare",
        {
            "player_ids": [SGA, 79635],
            "scope": "season",
            "season": "2024-25",
            "season_type": RS,
            "metrics": ["points"],
        },
        planted,
    )
    assert MISSING in cmp.notes
    assert "The source has no season totals for this player. Player id: 79635." in cmp.notes


def test_other_class_player_with_no_rows_gets_the_sentence_and_the_missing_note(
    planted: FileSnapshotStore,
) -> None:
    c = run_tool(
        "get_career", {"player_ids": [79635], "season_type": RS, "metrics": ["points"]}, planted
    )
    note = "The source is missing season totals for this player for: 1954-55 regular season."
    assert c.rows == []
    assert c.notes[0] == NO_TOTALS and c.notes[1].startswith(note)


def test_snapshot_without_the_seed_table_has_no_gaps(fixture_db_path: Path, tmp_path: Path) -> None:
    db = tmp_path / "nba_fixture.duckdb"
    shutil.copy2(fixture_db_path, db)
    con = duckdb.connect(str(db))
    con.execute("drop table seeds.known_player_career_gaps")
    con.close()
    r = run_tool("get_player_stats", _ps(KLEBER), FileSnapshotStore(db))
    assert r.notes == ["No 2024-25 regular season games for this player."]


# --- no machine-specific paths in committed test and transform files ----------------------------


# Built from parts so that this file does not contain the needle it searches for.
DESKTOP = "/" + "Desktop" + "/"


def files_naming_a_desktop_path(root: Path, files: list[str]) -> list[str]:
    skip = {".parquet", ".duckdb", ".pyc"}
    return [
        f
        for f in files
        if f and Path(f).suffix not in skip and DESKTOP in (root / f).read_text(errors="ignore")
    ]


def test_no_tracked_file_names_a_desktop_path() -> None:
    import subprocess

    from app.config import REPO_ROOT

    files = subprocess.run(
        ["git", "ls-files", "-z", "tests", "transform"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    assert files_naming_a_desktop_path(REPO_ROOT, files) == []


def test_the_desktop_guard_fails_on_a_file_that_names_such_a_path(tmp_path: Path) -> None:
    (tmp_path / "clean.sql").write_text("COPY t FROM 'a.parquet';\n")
    (tmp_path / "dirty.sql").write_text(f"COPY t FROM '/Users/x{DESKTOP}r/a.parquet';\n")
    (tmp_path / "dirty.parquet").write_text(DESKTOP)  # binary suffixes are not scanned
    listed = ["clean.sql", "dirty.sql", "dirty.parquet", ""]
    assert files_naming_a_desktop_path(tmp_path, listed) == ["dirty.sql"]


def test_relativize_load_sql_keeps_only_file_names(tmp_path: Path) -> None:
    from ingest.fixture import relativize_load_sql

    (tmp_path / "load.sql").write_text(
        f"COPY marts.a FROM '/Users/x{DESKTOP}r/tests/fixtures/nba_fixture/marts_a.parquet' "
        "(FORMAT 'parquet');\n"
    )
    relativize_load_sql(tmp_path)
    assert (tmp_path / "load.sql").read_text() == (
        "COPY marts.a FROM 'marts_a.parquet' (FORMAT 'parquet');\n"
    )
