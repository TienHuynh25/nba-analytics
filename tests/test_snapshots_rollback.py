"""QA tests for snapshot publish, prune, health check and rollback (tasks 1.24, 1.25; T-1.25).

Complements tests/test_snapshots.py. Everything runs in tmp dirs; nothing touches data/.
"""

from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
import textwrap
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.config import REPO_ROOT, SourcesConfig
from app.snapshot import LiveSnapshotStore
from ingest import snapshots
from ingest.snapshots import MANIFEST, MARKER, MARTS, HealthError, Snapshot
from metrics import generate_views
from tests.test_snapshots import cfg_for, fake_snapshot


def _link(cfg: SourcesConfig) -> Path:
    return cfg.resolve(cfg.snapshots.current_link)


def _nightlies(cfg: SourcesConfig, n: int) -> list[Snapshot]:
    """n nightly snapshots, oldest first (nba_20260901 ...)."""
    return [fake_snapshot(cfg, f"nba_202609{d:02d}", age_days=n + 1 - d) for d in range(1, n + 1)]


def _dirs_on_disk(cfg: SourcesConfig) -> set[str]:
    root = cfg.resolve(cfg.paths.snapshots)
    return {d.name for d in root.iterdir() if d.is_dir() and not d.is_symlink()}


def _corrupt_middle(path: Path) -> None:
    """Overwrite a block in the middle of the file (DuckDB still opens it; scans fail)."""
    size = path.stat().st_size
    with path.open("r+b") as f:
        f.seek(size // 3)
        f.write(b"\xff" * 4096)


def _big_snapshot(cfg: SourcesConfig, sid: str, age_days: int) -> Snapshot:
    """A snapshot whose games table spans many blocks, so mid-file corruption hits data."""
    snap = fake_snapshot(cfg, sid, age_days=age_days)
    con = duckdb.connect(str(snap.db))
    con.execute(
        "create or replace table marts.games as "
        "select range as game_id, 'g' || range as label from range(200000)"
    )
    con.close()
    manifest = dict(snap.manifest, checksums=snapshots._checksums(snap.dir, sid))
    (snap.dir / MANIFEST).write_text(json.dumps(manifest))
    return snapshots.load(snap.dir)


# --- 1.24: a failed health check never moves `current` -------------------------------------


def test_failed_health_check_leaves_current_unchanged(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    old = fake_snapshot(cfg, "nba_20260929", age_days=1)
    snapshots.publish(cfg, old)
    new = fake_snapshot(cfg, "nba_20260930")
    new.db.write_bytes(b"not a duckdb file")
    before = os.readlink(_link(cfg))
    with pytest.raises(HealthError):
        snapshots.publish(cfg, new)
    assert os.readlink(_link(cfg)) == before == "nba_20260929"
    assert snapshots.open_current(cfg).snapshot_id == "nba_20260929"


def test_tampered_shot_file_blocks_publish(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    old = fake_snapshot(cfg, "nba_20260929", age_days=1)
    snapshots.publish(cfg, old)
    new = fake_snapshot(cfg, "nba_20260930")
    (new.shots / "season=2025-26" / "data_0.parquet").write_bytes(b"PAR1 tampered")
    with pytest.raises(HealthError, match="shots/"):
        snapshots.publish(cfg, new)
    assert os.readlink(_link(cfg)) == "nba_20260929"


def test_failed_publish_does_not_prune(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snaps = _nightlies(cfg, 9)
    snapshots.publish(cfg, snaps[-2])  # prunes to 7
    on_disk = _dirs_on_disk(cfg)
    bad = fake_snapshot(cfg, "nba_20260930")
    bad.db.unlink()
    with pytest.raises(HealthError):
        snapshots.publish(cfg, bad)
    assert _dirs_on_disk(cfg) == on_disk | {"nba_20260930"}


# --- 1.24: atomic swap, including a real SIGKILL mid-swap ----------------------------------


def test_swap_only_ever_renames_over_the_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    a = fake_snapshot(cfg, "nba_20260929", age_days=1)
    b = fake_snapshot(cfg, "nba_20260930")
    link = _link(cfg)
    calls: list[tuple[str, str, str]] = []
    real_symlink: Callable[..., None] = os.symlink
    real_replace: Callable[..., None] = os.replace

    def spy_symlink(src: Any, dst: Any, *args: Any, **kw: Any) -> None:
        calls.append(("symlink", str(src), str(dst)))
        real_symlink(src, dst, *args, **kw)

    def spy_replace(src: Any, dst: Any, *args: Any, **kw: Any) -> None:
        calls.append(("replace", str(src), str(dst)))
        real_replace(src, dst, *args, **kw)

    monkeypatch.setattr(os, "symlink", spy_symlink)
    monkeypatch.setattr(os, "replace", spy_replace)
    snapshots.publish(cfg, a)
    snapshots.publish(cfg, b)
    assert [c[0] for c in calls] == ["symlink", "replace", "symlink", "replace"]
    assert all(c[2] != str(link) for c in calls if c[0] == "symlink")  # never written in place
    assert all(c[2] == str(link) for c in calls if c[0] == "replace")
    assert os.readlink(link) == "nba_20260930"  # relative target
    assert not list(link.parent.glob(".current.*.tmp"))


_SWAPPER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from app.config import load_sources
    from ingest import snapshots

    tmp = Path(sys.argv[1])
    base = load_sources()
    paths = base.paths.model_copy(update={"snapshots": tmp / "snapshots"})
    snaps = base.snapshots.model_copy(update={"current_link": tmp / "snapshots" / "current"})
    cfg = base.model_copy(update={"paths": paths, "snapshots": snaps})
    pair = [snapshots.load(tmp / "snapshots" / s) for s in sys.argv[2:4]]
    snapshots.point_current(cfg, pair[0])
    print("ready", flush=True)
    i = 0
    while True:
        i += 1
        snapshots.point_current(cfg, pair[i % 2])
    """
)


def test_sigkill_mid_swap_always_leaves_valid_current(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    a = fake_snapshot(cfg, "nba_20260929", age_days=1)
    b = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, a)
    rng = random.Random(1225)
    for _ in range(12):
        proc = subprocess.Popen(
            [sys.executable, "-c", _SWAPPER, str(tmp_path), a.snapshot_id, b.snapshot_id],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
        # Let it swap thousands of times, then kill it without warning.
        deadline = datetime.now() + timedelta(seconds=rng.uniform(0.02, 0.2))
        while datetime.now() < deadline:
            pass
        proc.send_signal(signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        link = _link(cfg)
        assert link.is_symlink()
        cur = snapshots.open_current(cfg)
        assert cur.snapshot_id in {a.snapshot_id, b.snapshot_id}
        assert os.readlink(link) == cur.snapshot_id  # open_current did not need to roll back
    # Stale temp links from killed swaps are never listed as snapshots.
    assert {s.snapshot_id for s in snapshots.published(cfg)} == {a.snapshot_id, b.snapshot_id}


# --- 1.24: keep the last 7 -----------------------------------------------------------------


def test_prune_keeps_exactly_seven_on_disk(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    fake_snapshot(cfg, "eval_2025_26_rs", age_days=40, pinned=True)
    snaps = _nightlies(cfg, 12)
    snapshots.publish(cfg, snaps[-1])
    nightly = {d for d in _dirs_on_disk(cfg) if d.startswith("nba_")}
    assert nightly == {s.snapshot_id for s in snaps[-7:]}
    assert "eval_2025_26_rs" in _dirs_on_disk(cfg)
    # Publishing again is idempotent: still 7.
    snapshots.publish(cfg, snaps[-1])
    assert len({d for d in _dirs_on_disk(cfg) if d.startswith("nba_")}) == 7


def test_prune_with_fewer_than_seven_removes_nothing(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snaps = _nightlies(cfg, 7)
    snapshots.publish(cfg, snaps[-1])
    assert len(_dirs_on_disk(cfg)) == 7


def test_prune_never_removes_current_after_rollback(tmp_path: Path) -> None:
    """Documented design: the snapshot `current` points at is kept even outside the newest 7."""
    cfg = cfg_for(tmp_path)
    snaps = _nightlies(cfg, 8)
    snapshots.point_current(cfg, snaps[0])  # e.g. after a manual rollback to the oldest
    removed = snapshots.prune(cfg)
    assert removed == []
    assert snaps[0].snapshot_id in _dirs_on_disk(cfg)
    assert len(_dirs_on_disk(cfg)) == 8


def test_prune_leaves_building_folders_alone(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snaps = _nightlies(cfg, 9)
    building = fake_snapshot(cfg, "nba_20261001")
    (building.dir / MARKER).write_text("x")
    snapshots.publish(cfg, snaps[-1])
    assert "nba_20261001" in _dirs_on_disk(cfg)
    assert len({d for d in _dirs_on_disk(cfg) if d != "nba_20261001"}) == 7


# --- 1.24 / 1.25: a BUILDING snapshot is never served --------------------------------------


def test_building_snapshot_cannot_be_published(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    old = fake_snapshot(cfg, "nba_20260929", age_days=1)
    snapshots.publish(cfg, old)
    new = fake_snapshot(cfg, "nba_20260930")
    (new.dir / MARKER).write_text("x")
    with pytest.raises(HealthError, match="did not finish"):
        snapshots.publish(cfg, new)
    assert os.readlink(_link(cfg)) == "nba_20260929"


def test_rollback_skips_newer_building_folder(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260928", age_days=2)
    cur = fake_snapshot(cfg, "nba_20260929", age_days=1)
    building = fake_snapshot(cfg, "nba_20260930")
    (building.dir / MARKER).write_text("x")
    snapshots.publish(cfg, cur)
    cur.db.write_bytes(b"garbage")
    assert snapshots.open_current(cfg).snapshot_id == prev.snapshot_id
    assert os.readlink(_link(cfg)) == prev.snapshot_id


def test_current_pointing_at_building_folder_rolls_back(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    building = fake_snapshot(cfg, "nba_20260930")
    (building.dir / MARKER).write_text("x")
    snapshots.point_current(cfg, building)
    assert snapshots.open_current(cfg).snapshot_id == prev.snapshot_id


def test_only_building_folders_means_no_snapshot(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    b = fake_snapshot(cfg, "nba_20260930")
    (b.dir / MARKER).write_text("x")
    with pytest.raises(HealthError, match="no healthy snapshot"):
        snapshots.open_current(cfg)
    assert not _link(cfg).exists()


# --- 1.25: rollback ------------------------------------------------------------------------


def test_rollback_skips_pinned_and_unhealthy_previous(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    good = fake_snapshot(cfg, "nba_20260927", age_days=3)
    bad_prev = fake_snapshot(cfg, "nba_20260928", age_days=2)
    fake_snapshot(cfg, "eval_2025_26_rs", age_days=1, pinned=True)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    bad_prev.db.unlink()
    cur.db.write_bytes(b"garbage")
    assert snapshots.open_current(cfg).snapshot_id == good.snapshot_id
    assert os.readlink(_link(cfg)) == good.snapshot_id
    assert not list(_link(cfg).parent.glob(".current.*.tmp"))


def test_dangling_current_rolls_back(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    link = _link(cfg)
    os.symlink("nba_missing", link)
    assert snapshots.open_current(cfg).snapshot_id == prev.snapshot_id


def test_reader_opens_previous_when_current_db_is_garbage(tmp_path: Path) -> None:
    """Done-when 1.25 end to end through the app's reader (LiveSnapshotStore, defaults)."""
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    cur.db.write_bytes(b"not a duckdb file")
    store = LiveSnapshotStore(cfg)
    assert store.snapshot_id == prev.snapshot_id
    row = store.connection().execute("select count(*) from marts.games").fetchone()
    assert row == (1,)


def test_full_check_rolls_back_on_tampered_shots(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    (cur.shots / "season=2025-26" / "data_0.parquet").write_bytes(b"PAR1 tampered")
    assert snapshots.open_current(cfg, full_check=True).snapshot_id == prev.snapshot_id


def test_full_check_rolls_back_on_mid_file_db_corruption(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = _big_snapshot(cfg, "nba_20260929", age_days=1)
    cur = _big_snapshot(cfg, "nba_20260930", age_days=0)
    snapshots.publish(cfg, cur)
    _corrupt_middle(cur.db)
    assert snapshots.open_current(cfg, full_check=True).snapshot_id == prev.snapshot_id


def test_reader_rolls_back_on_mid_file_db_corruption(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = _big_snapshot(cfg, "nba_20260929", age_days=1)
    cur = _big_snapshot(cfg, "nba_20260930", age_days=0)
    snapshots.publish(cfg, cur)
    _corrupt_middle(cur.db)
    store = LiveSnapshotStore(cfg)
    assert store.snapshot_id == prev.snapshot_id


def test_reader_rolls_back_on_tampered_shots(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    (cur.shots / "season=2025-26" / "data_0.parquet").write_bytes(b"PAR1 tampered")
    store = LiveSnapshotStore(cfg)
    assert store.snapshot_id == prev.snapshot_id


def test_reader_digest_cache_misses_on_in_place_rewrite(tmp_path: Path) -> None:
    """DEF-005: the per-process digest cache must not hide corruption after a first clean open."""
    cfg = cfg_for(tmp_path)
    prev = _big_snapshot(cfg, "nba_20260929", age_days=1)
    cur = _big_snapshot(cfg, "nba_20260930", age_days=0)
    snapshots.publish(cfg, cur)
    assert LiveSnapshotStore(cfg).snapshot_id == cur.snapshot_id  # caches cur's digests
    _corrupt_middle(cur.db)  # same size, same path, same inode
    assert LiveSnapshotStore(cfg).snapshot_id == prev.snapshot_id


def test_reader_reuses_digests_of_unchanged_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    cur = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, cur)
    assert LiveSnapshotStore(cfg).snapshot_id == cur.snapshot_id
    hashed: list[Path] = []
    real = snapshots.sha256

    def spy(path: Path) -> str:
        hashed.append(path)
        return real(path)

    monkeypatch.setattr(snapshots, "sha256", spy)
    assert LiveSnapshotStore(cfg).snapshot_id == cur.snapshot_id
    assert hashed == []


# --- 1.24: manifest contents and the nightly as_of_date ------------------------------------


def _write_marts(db: Path, latest: date) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute("create schema if not exists marts")
    for t in MARTS:
        if t != "games":
            con.execute(f"create table marts.{t} as select 1 as x")
    con.execute(
        "create table marts.games as select * from (values "
        "(1, ?::date - 1), (2, ?::date)) t(game_id, game_date)",
        [latest, latest],
    )
    con.close()


def _frozen(instant: datetime) -> type[datetime]:
    class Frozen(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Frozen:
            return cls.fromtimestamp(instant.timestamp(), tz or UTC)

    return Frozen


def _patch_build(monkeypatch: pytest.MonkeyPatch, latest: date) -> None:
    def fake_dbt(db: Path, shots: Path, landing: Path, as_of: date | None) -> None:
        _write_marts(db, latest)
        (shots / "season=2025-26").mkdir(parents=True)
        (shots / "season=2025-26" / "data_0.parquet").write_bytes(b"PAR1 shots")

    monkeypatch.setattr(generate_views, "write", lambda: None)  # no repo writes
    monkeypatch.setattr(snapshots, "land", lambda *a, **k: None)
    monkeypatch.setattr(snapshots, "run_dbt", fake_dbt)


def test_nightly_as_of_date_is_build_date_in_eastern_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, latest=date(2026, 9, 29))
    # 02:30 UTC on Oct 1 is 22:30 EDT on Sep 30: the build date must be Sep 30.
    monkeypatch.setattr(snapshots, "datetime", _frozen(datetime(2026, 10, 1, 2, 30, tzinfo=UTC)))
    snap = snapshots.build(cfg)
    assert snap.snapshot_id == "nba_20260930"
    assert snap.manifest["as_of_date"] == "2026-09-30"
    assert snap.manifest["as_of_cutoff"] is None
    assert not (snap.dir / MARKER).exists()


def test_manifest_has_ids_counts_latest_game_and_shot_checksums(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, latest=date(2026, 4, 12))
    snap = snapshots.build(cfg, today=date(2026, 9, 30))
    m = json.loads((snap.dir / MANIFEST).read_text())
    assert m["snapshot_id"] == "nba_20260930"
    assert m["latest_game_date"] == "2026-04-12"
    assert set(m["row_counts"]) == set(MARTS) and m["row_counts"]["games"] == 2
    assert set(m["checksums"]) == {
        "nba_20260930.duckdb",
        "shots/season=2025-26/data_0.parquet",
    }
    assert m["checksums"]["shots/season=2025-26/data_0.parquet"] == snapshots.sha256(
        snap.shots / "season=2025-26" / "data_0.parquet"
    )
    snapshots.health_check(snapshots.load(snap.dir))


def test_as_of_manifest_date_is_day_after_last_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    _patch_build(monkeypatch, latest=date(2026, 4, 12))
    snap = snapshots.build(
        cfg, snapshot_id="eval_test", as_of=date(2026, 4, 12), today=date(2026, 9, 30), pinned=True
    )
    assert snap.manifest["as_of_date"] == "2026-04-13"
    assert snap.manifest["pinned"] is True
    # T-2.1 rework: dbt's full build file is gone; the published file is a fresh copy.
    assert not (snap.dir / snapshots.STAGING_DIR).exists()
    assert set(snap.manifest["checksums"]) == {
        "eval_test.duckdb",
        "shots/season=2025-26/data_0.parquet",
    }
    with pytest.raises(snapshots.BuildError):
        snapshots.publish(cfg, snap)
    assert not _link(cfg).exists()


def test_failed_build_removes_folder_and_keeps_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = cfg_for(tmp_path)
    old = fake_snapshot(cfg, "nba_20260929", age_days=1)
    snapshots.publish(cfg, old)

    def boom(*a: Any, **k: Any) -> None:
        raise snapshots.BuildError("dbt build failed")

    monkeypatch.setattr(generate_views, "write", lambda: None)
    monkeypatch.setattr(snapshots, "land", lambda *a, **k: None)
    monkeypatch.setattr(snapshots, "run_dbt", boom)
    with pytest.raises(snapshots.BuildError):
        snapshots.build(cfg, today=date(2026, 9, 30))
    assert "nba_20260930" not in _dirs_on_disk(cfg)
    assert os.readlink(_link(cfg)) == "nba_20260929"
