"""Regression tests for T-SEC4: SEC-011, SEC-012 and two S4 availability gaps from T-QA4.

SEC-011: DuckDB spills to a private folder outside the sealed (0555) snapshot, so a query over
the memory limit spills instead of failing with an IO error; the shots folder stays unwritable.
SEC-012: ``USING SAMPLE`` / ``TABLESAMPLE`` are rejected (the guard used to write LIMIT in front
of the sample clause). S4: snapshot ids are at most 64 characters; SQL with a NUL or a lone
surrogate is a guard error, and a driver ``UnicodeEncodeError`` is a failed query, not a crash.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import app.snapshot as app_snapshot
from app import sql_fallback
from app.config import SourcesConfig
from app.snapshot import LiveSnapshotStore
from app.sql_guard import GuardError, check
from ingest import refresh, snapshots
from ingest.snapshots import MANIFEST, Snapshot, SnapshotIdError
from tests.test_sec3_hardening import _build, _patch_build, forbid_real_build
from tests.test_snapshots import cfg_for, fake_snapshot
from tests.test_sql_fallback import make

# --- SEC-011: spill outside the sealed snapshot ----------------------------------------------

# Sorting 20M integers needs ~160 MB; with a 64 MB limit it must spill to disk.
BIG_SORT = "select count(*) from (select i from range(20000000) t(i) order by i desc offset 1)"


def test_query_over_memory_limit_spills_outside_sealed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture_db_path: Path
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, source_db=fixture_db_path)
    snap = _build(cfg, 30)
    snapshots.publish(cfg, snap)
    monkeypatch.setattr(app_snapshot, "APP_MEMORY_LIMIT", "64MB")
    con = LiveSnapshotStore(cfg).connection()
    tmp = Path(con.execute("select current_setting('temp_directory')").fetchone()[0])  # type: ignore[index]
    root = cfg.resolve(cfg.paths.snapshots).resolve()
    assert not tmp.resolve().is_relative_to(root)
    assert stat.S_IMODE(os.stat(tmp.parent).st_mode) == 0o700  # private per-process folder
    cap = con.execute("select current_setting('max_temp_directory_size')").fetchone()
    assert cap == ("3.7 GiB",)  # APP_MAX_TEMP_SIZE "4GB" (DuckDB GB = 10^9 bytes)
    assert con.execute(BIG_SORT).fetchone() == (19999999,)
    # The shots folder stays unwritable through the locked connection.
    shots = snap.shots.resolve()
    before = sorted(p.name for p in shots.rglob("*"))
    with pytest.raises(duckdb.Error):
        con.execute(f"COPY (select 1) TO '{shots}/x.csv'")
    with pytest.raises(duckdb.Error):
        con.execute("SET temp_directory = ?", [str(shots)])
    assert sorted(p.name for p in shots.rglob("*")) == before


def test_spill_beyond_the_cap_is_a_duckdb_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture_db_path: Path
) -> None:
    """Past max_temp_directory_size the query fails cleanly instead of filling the disk."""
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, source_db=fixture_db_path)
    snap = _build(cfg, 30)
    snapshots.publish(cfg, snap)
    monkeypatch.setattr(app_snapshot, "APP_MEMORY_LIMIT", "64MB")
    monkeypatch.setattr(app_snapshot, "APP_MAX_TEMP_SIZE", "1MB")
    con = LiveSnapshotStore(cfg).connection()
    with pytest.raises(duckdb.OutOfMemoryException, match="offload"):
        con.execute(BIG_SORT).fetchone()
    with pytest.raises(duckdb.Error):
        con.execute("SET max_temp_directory_size = '1TB'")  # locked
    assert con.execute("select 1").fetchone() == (1,)  # the connection stays usable


def test_spill_paths_are_unique_per_instance() -> None:
    a = app_snapshot.spill_dir(Path("x/s1.duckdb"))
    b = app_snapshot.spill_dir(Path("y/s1.duckdb"))
    assert a != b and a.parent == b.parent and a.parent.is_dir()


# --- SEC-012: sample clauses -----------------------------------------------------------------

P = "SELECT player_id FROM semantic.players"


@pytest.mark.parametrize(
    "sql",
    [
        f"{P} USING SAMPLE 10%",
        f"{P} USING SAMPLE 5 ROWS",
        f"{P} USING SAMPLE reservoir(10 ROWS) REPEATABLE (1)",
        f"{P} TABLESAMPLE RESERVOIR(5 ROWS)",
        f"{P} p TABLESAMPLE (10%) LIMIT 5",
        f"SELECT * FROM ({P}) USING SAMPLE 5",
        f"WITH t AS ({P} USING SAMPLE 10%) SELECT * FROM t",
    ],
)
def test_sample_clauses_are_rejected(sql: str) -> None:
    with pytest.raises(GuardError, match="TABLESAMPLE is not allowed"):
        check(sql)


# --- S4: NUL and lone surrogates -------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1\x00",
        f"{P}\x00",
        f"{P} WHERE player_id = 1 \x00",
        "SELECT '\ud800' AS a",
        f"{P} WHERE player_name = '\udfff'",
    ],
)
def test_nul_and_surrogates_are_guard_errors(sql: str) -> None:
    with pytest.raises(GuardError, match=r"NUL|UTF-8"):
        check(sql)


def test_fallback_treats_unencodable_sql_as_a_failed_query(
    fixture_db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even with the guard bypassed, a driver UnicodeEncodeError goes to repair, not up."""
    monkeypatch.setattr(sql_fallback, "check", lambda sql: sql)
    fb, llm = make(fixture_db_path, ["SELECT '\ud800' AS a", "select count(*) from semantic.games"])
    r = fb.answer("how many games")
    assert r.ok and r.attempts == 2
    assert "surrogates not allowed" in llm.seen[1][-1].content


def test_fallback_surrogate_sql_gives_up_cleanly(fixture_db_path: Path) -> None:
    fb, _ = make(fixture_db_path, ["SELECT '\ud800' AS a", "SELECT 1\x00"])
    r = fb.answer("anything")
    assert not r.ok and r.attempts == 2 and r.error and "NUL" in r.error


# --- S4: snapshot id length ------------------------------------------------------------------

OK_ID = "a" * 64
LONG_ID = "a" * 65


def _long_snapshot(cfg: SourcesConfig, sid: str, age_days: int = 0) -> Path:
    """A complete-looking snapshot folder whose name (and manifest id) is ``sid``."""
    d = cfg.resolve(cfg.paths.snapshots) / sid
    (d / "shots").mkdir(parents=True)
    con = duckdb.connect(str(d / f"{sid}.duckdb"))
    con.execute("create schema marts; create table marts.games as select 1 as game_id")
    con.close()
    manifest = {
        "snapshot_id": sid,
        "as_of_date": "2026-09-30",
        "built_at": (datetime.now(UTC) - timedelta(days=age_days)).isoformat(),
        "pinned": False,
        "checksums": snapshots._checksums(d, sid),
    }
    (d / MANIFEST).write_text(json.dumps(manifest))
    return d


def test_validate_id_length_cap() -> None:
    assert snapshots.validate_id(OK_ID) == OK_ID
    for sid in (LONG_ID, "a" * 200, "a" * 300):
        with pytest.raises(SnapshotIdError, match="invalid snapshot id"):
            snapshots.validate_id(sid)


def test_cli_length_cap(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    forbid_real_build(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        refresh.main(["--as-of", "2026-04-12", "--snapshot-id", LONG_ID])
    assert exc.value.code == 2
    assert "invalid snapshot id" in capsys.readouterr().err


def test_build_length_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch)
    snap = snapshots.build(cfg, snapshot_id=OK_ID, pinned=True)
    assert snap.dir.name == OK_ID and snapshots.load(snap.dir).snapshot_id == OK_ID
    with pytest.raises(SnapshotIdError):
        snapshots.build(cfg, snapshot_id=LONG_ID, pinned=True)
    assert not (cfg.resolve(cfg.paths.snapshots) / LONG_ID).exists()


def test_open_length_cap(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    d = _long_snapshot(cfg, LONG_ID)
    with pytest.raises(SnapshotIdError):
        snapshots.load(d)
    with pytest.raises(SnapshotIdError):
        Snapshot(LONG_ID, d, {})
    os.symlink(LONG_ID, cfg.resolve(cfg.snapshots.current_link))
    assert snapshots.current(cfg) is None


def test_prune_and_rollback_skip_long_ids(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    good = fake_snapshot(cfg, "nba_20260928", age_days=2)
    long_dir = _long_snapshot(cfg, LONG_ID, age_days=1)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    assert {s.snapshot_id for s in snapshots.published(cfg)} == {good.snapshot_id, cur.snapshot_id}
    keep_one = cfg.snapshots.model_copy(update={"keep": 1})
    assert snapshots.prune(cfg.model_copy(update={"snapshots": keep_one})) == [good.snapshot_id]
    assert long_dir.exists()  # never touched by prune
    good = fake_snapshot(cfg, "nba_20260927", age_days=3)
    cur.db.write_bytes(b"garbage")
    assert snapshots.open_current(cfg).snapshot_id == good.snapshot_id
    with pytest.raises(SnapshotIdError):
        snapshots._remove_tree(cfg, long_dir)
    assert long_dir.exists()
