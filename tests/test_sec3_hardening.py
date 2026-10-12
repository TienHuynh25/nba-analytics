"""Regression tests for SEC-003, SEC-004, SEC-006 and SEC-009 (T-SEC3, G1 security review).

SEC-003: a published snapshot is sealed (files 0444, folders 0555), so the app's locked
connection cannot COPY or EXPORT into its shots folder. SEC-004: the health check opens the
snapshot the way the app does, so rollback accepts a healthy snapshot the app holds open.
SEC-006: landing validates contracts and only accepts plain column names. SEC-009: snapshot ids
are ``[a-z0-9_]+``, match their folder, and nothing outside the snapshots root is deleted.
Everything runs in tmp dirs.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.config import SourcesConfig
from app.snapshot import LiveSnapshotStore
from ingest import land, refresh, snapshots
from ingest.contracts import SCHEMA_DIR, ContractError, validate
from ingest.snapshots import MANIFEST, MARKER, MARTS, Snapshot, SnapshotIdError
from metrics import generate_views
from tests.test_snapshots import cfg_for, fake_snapshot

# --- helpers -------------------------------------------------------------------------------


def _mode(p: Path) -> int:
    return stat.S_IMODE(os.lstat(p).st_mode)


def _write_shot(shots: Path, value: int = 1) -> None:
    d = shots / "season=2025-26"
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"copy (select {value} as a) to '{d / 'data_0.parquet'}' (format parquet)")
    con.close()


def _small_marts(db: Path) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute("create schema marts")
    for t in MARTS:
        if t != "games":
            con.execute(f"create table marts.{t} as select 1 as x")
    con.execute("create table marts.games as select 1 as game_id, date '2026-04-12' as game_date")
    con.close()


def _patch_build(monkeypatch: pytest.MonkeyPatch, source_db: Path | None = None) -> None:
    """build() without land or dbt: marts from ``source_db`` (the fixture) or a tiny stand-in."""

    def fake_dbt(db: Path, shots: Path, landing: Path, as_of: date | None) -> None:
        if source_db is not None:
            db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_db, db)
        else:
            _small_marts(db)
        _write_shot(shots)

    monkeypatch.setattr(generate_views, "write", lambda: None)
    monkeypatch.setattr(snapshots, "land", lambda *a, **k: None)
    monkeypatch.setattr(snapshots, "run_dbt", fake_dbt)


def forbid_real_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any build step fail fast, for tests that drive the CLI with a bad id.

    If ``validate_id`` ever regressed, ``refresh.main`` would otherwise start a real as-of build
    over ``data/``. SystemExit (not an Exception) so ``main`` neither catches nor logs it; its
    code is a message, never 2, so the exit-code assertions still fail on a regression.
    """

    def no_build(*a: Any, **k: Any) -> None:
        raise SystemExit("a bad snapshot id got past validation and reached a build step")

    for mod, name in (
        (refresh, "as_of_build"),
        (refresh, "nightly"),
        (snapshots, "build"),
        (snapshots, "land"),
        (snapshots, "run_dbt"),
        (generate_views, "write"),
    ):
        monkeypatch.setattr(mod, name, no_build)
    monkeypatch.setattr(refresh, "_log_run", lambda record: None)


def _build(cfg: SourcesConfig, day: int, **kw: Any) -> Snapshot:
    return snapshots.build(cfg, today=date(2026, 9, day), **kw)


def _assert_sealed(snap_dir: Path) -> None:
    assert _mode(snap_dir) == 0o555
    for p in snap_dir.rglob("*"):
        assert _mode(p) == (0o555 if p.is_dir() else 0o444), p


# --- SEC-003: sealed snapshots -------------------------------------------------------------


def test_build_seals_published_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch)
    snap = _build(cfg, 30)
    assert not (snap.dir / MARKER).exists()
    _assert_sealed(snap.dir)
    snapshots.health_check(snap)  # sealing comes after the manifest: checksums still match


def test_locked_connection_cannot_write_into_sealed_shots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture_db_path: Path
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, source_db=fixture_db_path)
    snap = _build(cfg, 30)
    snapshots.publish(cfg, snap)
    con = LiveSnapshotStore(cfg).connection()
    shots = snap.shots.resolve()
    before = sorted(p.name for p in shots.rglob("*"))
    with pytest.raises(duckdb.Error):
        con.execute(f"COPY (select 1) TO '{shots}/x.csv'")
    with pytest.raises(duckdb.Error):
        con.execute(f"COPY (select 1) TO '{shots}/season=2025-26/data_0.parquet' (format parquet)")
    with pytest.raises(duckdb.Error):
        con.execute(f"EXPORT DATABASE '{shots}/exp'")
    with pytest.raises(duckdb.Error):
        con.execute(f"EXPORT DATABASE '{shots}'")
    assert sorted(p.name for p in shots.rglob("*")) == before
    # Reads through the allowed folder still work.
    assert con.execute(f"select a from read_parquet('{shots}/*/*.parquet')").fetchall() == [(1,)]
    assert con.execute("select count(*) from marts.games").fetchone()[0] > 0  # type: ignore[index]


def test_prune_removes_sealed_snapshots_and_keeps_shared_shot_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch)
    snaps = []
    for day in range(1, 10):
        snaps.append(_build(cfg, day))
        snapshots.publish(cfg, snaps[-1])
    root = cfg.resolve(cfg.paths.snapshots)
    kept = {d.name for d in root.iterdir() if d.is_dir() and not d.is_symlink()}
    assert kept == {s.snapshot_id for s in snaps[-7:]}
    newest = snaps[-1]
    shot = newest.shots / "season=2025-26" / "data_0.parquet"
    assert shot.stat().st_nlink == 7  # unchanged season hard-linked across the kept snapshots
    for s in snaps[-7:]:
        _assert_sealed(s.dir)  # deletion touched folders it removed only
    assert snapshots.open_current(cfg).snapshot_id == newest.snapshot_id


def test_rollback_to_sealed_previous(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch)
    prev = _build(cfg, 29)
    cur = _build(cfg, 30)
    snapshots.publish(cfg, cur)
    os.chmod(cur.db, 0o644)  # someone with write access to data/ corrupts it
    cur.db.write_bytes(b"garbage")
    assert LiveSnapshotStore(cfg).snapshot_id == prev.snapshot_id
    _assert_sealed(prev.dir)


def test_partially_sealed_building_leftover_is_rebuilt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A kill between sealing the contents and removing the marker leaves 0555 subfolders."""
    cfg = cfg_for(tmp_path)
    left = fake_snapshot(cfg, "nba_20260930")
    (left.dir / MARKER).write_text("x")
    snapshots.seal(left.dir, include_root=False)
    _patch_build(monkeypatch)
    snap = _build(cfg, 30)
    _assert_sealed(snap.dir)
    snapshots.health_check(snap)


def test_failed_build_after_seal_point_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch)

    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("killed while sealing")

    monkeypatch.setattr(snapshots, "seal", boom)
    with pytest.raises(RuntimeError):
        _build(cfg, 30)
    assert not (cfg.resolve(cfg.paths.snapshots) / "nba_20260930").exists()


def test_remove_tree_refuses_current(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snap = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, snap)
    with pytest.raises(snapshots.BuildError, match="current points at it"):
        snapshots._remove_tree(cfg, snap.dir)
    assert snap.dir.exists()


def test_digest_cache_misses_after_mode_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chmod changes ctime, so a sealed file is re-hashed once; never a stale cache hit."""
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    hashed: list[Path] = []
    real = snapshots.sha256

    def spy(path: Path) -> str:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(snapshots, "sha256", spy)
    first = snapshots.sha256_cached(p)
    snapshots.sha256_cached(p)
    assert len(hashed) == 1
    os.chmod(p, 0o444)
    assert snapshots.sha256_cached(p) == first
    assert len(hashed) == 2


# --- SEC-004: health check uses the app's connection config --------------------------------


def test_rollback_accepts_previous_snapshot_held_open_by_app(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    a = fake_snapshot(cfg, "nba_20260929", age_days=1)
    b = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, a)
    store = LiveSnapshotStore(cfg)
    assert store.snapshot_id == a.snapshot_id  # app holds a's locked instance
    snapshots.health_check(a)  # same process, same file: must not be refused
    snapshots.publish(cfg, b)
    b.db.write_bytes(b"garbage")
    assert store.snapshot_id == a.snapshot_id
    assert snapshots.current(cfg).snapshot_id == a.snapshot_id  # type: ignore[union-attr]


# --- SEC-006: land ----------------------------------------------------------------------------

KEY = "commonallplayers"
RS = "CommonAllPlayers"


def _contract_headers() -> tuple[list[str], list[Any]]:
    schema = json.loads((SCHEMA_DIR / f"{KEY}.json").read_text())
    item = schema["properties"]["resultSets"]["allOf"][0]["contains"]["properties"]
    headers = item["headers"]["const"]
    row = []
    for cell in item["rowSet"]["items"]["prefixItems"]:
        t = cell["type"][0]
        row.append({"number": 1, "string": "x", "boolean": True, "null": None}[t])
    return headers, row


def _write_raw(raw: Path, headers: list[Any], rows: list[list[Any]]) -> None:
    d = raw / KEY / "_all" / "2026-10-01"
    d.mkdir(parents=True)
    doc = {
        "key": KEY,
        "season": "_all",
        "params": {},
        "fetched_at": "2026-10-01T05:00:00+00:00",
        "response": {"resultSets": [{"name": RS, "headers": headers, "rowSet": rows}]},
    }
    (d / "a.json").write_text(json.dumps(doc))


def _tables(db: Path) -> set[str]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute("select table_name from information_schema.tables").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def test_land_accepts_a_file_that_meets_its_contract(tmp_path: Path) -> None:
    headers, row = _contract_headers()
    _write_raw(tmp_path / "raw", headers, [row])
    counts = land.land(tmp_path / "raw", tmp_path / "l.duckdb", tmp_path / "w", [KEY])
    assert counts == {"commonallplayers__commonallplayers": 1}


@pytest.mark.parametrize("validator", [validate, None])
def test_land_rejects_sql_in_header(tmp_path: Path, validator: Any) -> None:
    evil = 'x" VARCHAR); CREATE TABLE pwned(a INT); CREATE TABLE z ("y'
    _write_raw(tmp_path / "raw", [evil], [])
    with pytest.raises(ContractError):
        land.land(
            tmp_path / "raw", tmp_path / "l.duckdb", tmp_path / "w", [KEY], validator=validator
        )
    assert not (tmp_path / "l.duckdb").exists()


@pytest.mark.parametrize("header", ["A'B", 'A"B', "A B", "A-B", "", "ÄB", 7, None])
def test_land_header_must_be_plain_identifier(tmp_path: Path, header: Any) -> None:
    _write_raw(tmp_path / "raw", [header], [["v"]])
    with pytest.raises(ContractError, match="plain identifier"):
        land.land(tmp_path / "raw", tmp_path / "l.duckdb", tmp_path / "w", [KEY], validator=None)


def test_land_rejects_file_that_breaks_its_contract(tmp_path: Path) -> None:
    headers, row = _contract_headers()
    tampered = [*headers[:-1], "RENAMED"]  # plain identifier, wrong contract
    _write_raw(tmp_path / "raw", tampered, [row])
    with pytest.raises(ContractError, match="breaks its contract"):
        land.land(tmp_path / "raw", tmp_path / "l.duckdb", tmp_path / "w", [KEY])
    assert not (tmp_path / "l.duckdb").exists()


def test_land_work_path_with_quote(tmp_path: Path) -> None:
    headers, row = _contract_headers()
    _write_raw(tmp_path / "raw", headers, [row])
    counts = land.land(tmp_path / "raw", tmp_path / "l.duckdb", tmp_path / "it's work", [KEY])
    assert counts["commonallplayers__commonallplayers"] == 1
    assert "pwned" not in _tables(tmp_path / "l.duckdb")


# --- SEC-009: snapshot ids ------------------------------------------------------------------

BAD_IDS = ["../victim", "/tmp/abs", "a/b", "A_1", "a.b", "a-b", "", "x\n", "..", " a"]


@pytest.mark.parametrize("sid", BAD_IDS)
def test_validate_id_rejects(sid: str) -> None:
    with pytest.raises(SnapshotIdError):
        snapshots.validate_id(sid)


@pytest.mark.parametrize("sid", ["nba_20260930", "eval_2025_26_rs", "asof_20260412"])
def test_validate_id_accepts(sid: str) -> None:
    assert snapshots.validate_id(sid) == sid


@pytest.mark.parametrize("sid", BAD_IDS)
def test_build_rejects_bad_id_before_touching_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sid: str
) -> None:
    cfg = cfg_for(tmp_path)
    (tmp_path / "snapshots").mkdir()
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / MARKER).write_text("x")
    (victim / "precious.txt").write_text("keep")
    _patch_build(monkeypatch)
    with pytest.raises(SnapshotIdError):
        snapshots.build(cfg, snapshot_id=sid, today=date(2026, 9, 30))
    assert (victim / "precious.txt").read_text() == "keep"
    assert list((tmp_path / "snapshots").iterdir()) == []


def test_build_refuses_symlinked_snapshot_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    (tmp_path / "snapshots").mkdir()
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / MARKER).write_text("x")
    (victim / "precious.txt").write_text("keep")
    os.symlink(victim, tmp_path / "snapshots" / "nba_20260930")
    _patch_build(monkeypatch)
    with pytest.raises(SnapshotIdError, match="symlink"):
        _build(cfg, 30)
    assert (victim / "precious.txt").exists()


def test_remove_tree_refuses_paths_outside_root(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    (tmp_path / "snapshots").mkdir()
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (tmp_path / "snapshots" / "link_dir").symlink_to(outside)
    for p in (
        outside,
        tmp_path / "snapshots" / ".." / "outside_dir",
        tmp_path / "snapshots" / "link_dir",
        tmp_path / "snapshots",
        Path("/"),
    ):
        with pytest.raises(SnapshotIdError):
            snapshots._remove_tree(cfg, p)
    assert outside.exists()


def test_manifest_id_must_match_folder(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    s = fake_snapshot(cfg, "nba_20260930")
    for bad in ("../../evil", "nba_20260929", None):
        (s.dir / MANIFEST).write_text(json.dumps(dict(s.manifest, snapshot_id=bad)))
        with pytest.raises(SnapshotIdError):
            snapshots.load(s.dir)


def test_mismatched_manifest_is_skipped_by_listing_and_rollback(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    good = fake_snapshot(cfg, "nba_20260928", age_days=2)
    evil = fake_snapshot(cfg, "nba_20260929", age_days=1)
    (evil.dir / MANIFEST).write_text(json.dumps(dict(evil.manifest, snapshot_id="../x")))
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    assert {s.snapshot_id for s in snapshots.published(cfg)} == {"nba_20260928", "nba_20260930"}
    cur.db.write_bytes(b"garbage")
    assert snapshots.open_current(cfg).snapshot_id == good.snapshot_id
    assert evil.dir.exists()


def test_current_pointing_outside_root_is_ignored(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    # A complete-looking snapshot outside the root, reached through `current`.
    other = cfg_for(tmp_path / "elsewhere")
    outside = fake_snapshot(other, "nba_20260930")
    os.symlink(outside.dir, cfg.resolve(cfg.snapshots.current_link))
    assert snapshots.current(cfg) is None
    assert snapshots.open_current(cfg).snapshot_id == prev.snapshot_id
    assert os.readlink(cfg.resolve(cfg.snapshots.current_link)) == prev.snapshot_id


def test_point_current_refuses_snapshot_outside_root(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    other = cfg_for(tmp_path / "elsewhere")
    outside = fake_snapshot(other, "nba_20260930")
    with pytest.raises(SnapshotIdError):
        snapshots.point_current(cfg, outside)
    assert not cfg.resolve(cfg.snapshots.current_link).is_symlink()


@pytest.mark.parametrize("sid", ["../x", "/abs", "Eval"])
def test_cli_rejects_bad_snapshot_id(
    sid: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    forbid_real_build(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        refresh.main(["--as-of", "2026-04-12", "--snapshot-id", sid])
    assert exc.value.code == 2
    assert "invalid snapshot id" in capsys.readouterr().err
