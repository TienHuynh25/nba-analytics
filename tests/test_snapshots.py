import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from app.config import SourcesConfig, load_sources
from ingest import snapshots
from ingest.snapshots import MANIFEST, MARKER, HealthError, Snapshot


def cfg_for(tmp: Path) -> SourcesConfig:
    base = load_sources()
    paths = base.paths.model_copy(update={"snapshots": tmp / "snapshots"})
    snaps = base.snapshots.model_copy(update={"current_link": tmp / "snapshots" / "current"})
    return base.model_copy(update={"paths": paths, "snapshots": snaps})


def fake_snapshot(
    cfg: SourcesConfig, sid: str, age_days: int = 0, pinned: bool = False
) -> Snapshot:
    d = cfg.resolve(cfg.paths.snapshots) / sid
    (d / "shots" / "season=2025-26").mkdir(parents=True)
    db = d / f"{sid}.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create schema marts; create table marts.games as select 1 as game_id")
    con.close()
    (d / "shots" / "season=2025-26" / "data_0.parquet").write_bytes(b"PAR1 fake")
    manifest = {
        "snapshot_id": sid,
        "as_of_date": "2026-09-30",
        "built_at": (datetime.now(UTC) - timedelta(days=age_days)).isoformat(),
        "pinned": pinned,
        "checksums": snapshots._checksums(d, sid),
    }
    (d / MANIFEST).write_text(json.dumps(manifest))
    return snapshots.load(d)


def test_publish_points_current_and_prunes_to_keep(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    eval_snap = fake_snapshot(cfg, "eval_2025_26_rs", age_days=30, pinned=True)
    snaps = [fake_snapshot(cfg, f"nba_202609{d:02d}", age_days=20 - d) for d in range(1, 11)]
    snapshots.publish(cfg, snaps[-1])
    cur = snapshots.current(cfg)
    assert cur is not None and cur.snapshot_id == "nba_20260910"
    remaining = {s.snapshot_id for s in snapshots.published(cfg)}
    assert len([r for r in remaining if r.startswith("nba_")]) == cfg.snapshots.keep == 7
    assert eval_snap.snapshot_id in remaining  # pinned: never pruned
    assert "nba_20260901" not in remaining


def test_pinned_snapshot_is_never_published(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snap = fake_snapshot(cfg, "eval_2025_26_rs", pinned=True)
    with pytest.raises(snapshots.BuildError):
        snapshots.publish(cfg, snap)


def test_crash_mid_swap_leaves_valid_current(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    old = fake_snapshot(cfg, "nba_20260929", age_days=1)
    new = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, old)
    link = cfg.resolve(cfg.snapshots.current_link)
    # Simulate a kill after the new symlink is created but before the atomic rename.
    os.symlink(new.dir.name, link.with_name(".current.99999.tmp"))
    cur = snapshots.open_current(cfg)
    assert cur.snapshot_id == "nba_20260929"
    # A later publish still succeeds and replaces the link atomically.
    snapshots.publish(cfg, new)
    assert snapshots.open_current(cfg).snapshot_id == "nba_20260930"


def test_corrupted_current_rolls_back_to_previous(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    fake_snapshot(cfg, "nba_20260928", age_days=2)
    prev = fake_snapshot(cfg, "nba_20260929", age_days=1)
    new = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, new)
    new.db.write_bytes(b"not a duckdb file")
    cur = snapshots.open_current(cfg)
    assert cur.snapshot_id == prev.snapshot_id
    assert snapshots.current(cfg).snapshot_id == prev.snapshot_id  # type: ignore[union-attr]


def test_unfinished_build_is_not_listed_or_healthy(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snap = fake_snapshot(cfg, "nba_20260930")
    (snap.dir / MARKER).write_text("x")
    assert snapshots.published(cfg) == []
    with pytest.raises(HealthError):
        snapshots.health_check(snap)


def test_no_healthy_snapshot_raises(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    snap = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, snap)
    snap.db.unlink()
    with pytest.raises(HealthError):
        snapshots.open_current(cfg)
