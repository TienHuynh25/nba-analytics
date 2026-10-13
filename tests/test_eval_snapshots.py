"""Task 2.1: the pinned eval snapshot registry (``eval/snapshots.yaml``).

Every snapshot listed there is pinned: ``publish`` refuses to make it current, and the built
snapshot (when present on this machine) matches the recorded manifest checksum and is not what
``current`` points at. The built-snapshot checks skip where ``data/snapshots`` has no build.
"""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.config import REPO_ROOT, load_sources
from ingest import snapshots
from ingest.snapshots import MANIFEST
from tests.test_snapshots import cfg_for, fake_snapshot

REGISTRY = REPO_ROOT / "eval" / "snapshots.yaml"


def _entries() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(REGISTRY.read_text())
    assert isinstance(data, dict)
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _built(entry: dict[str, Any]) -> Path | None:
    d = REPO_ROOT / entry["path"]
    return d if (d / MANIFEST).exists() else None


def test_registry_lists_the_pinned_eval_snapshot() -> None:
    e = _entries()["eval"]
    assert snapshots.validate_id(e["snapshot_id"]) == "eval_2025_26_rs"
    assert e["pinned"] is True
    assert e["path"] == f"data/snapshots/{e['snapshot_id']}"
    assert e["db"] == f"{e['path']}/{e['snapshot_id']}.duckdb"
    cutoff = date.fromisoformat(e["as_of_cutoff"])
    assert date.fromisoformat(e["as_of_date"]) == cutoff + timedelta(days=1)
    assert len(e["manifest_sha256"]) == 64


@pytest.mark.parametrize("key", sorted(_entries()))
def test_publish_refuses_every_registered_snapshot(tmp_path: Path, key: str) -> None:
    e = _entries()[key]
    cfg = cfg_for(tmp_path)
    snap = fake_snapshot(cfg, e["snapshot_id"], pinned=bool(e["pinned"]))
    with pytest.raises(snapshots.BuildError, match="pinned"):
        snapshots.publish(cfg, snap)
    assert not cfg.resolve(cfg.snapshots.current_link).is_symlink()


def test_built_eval_snapshot_matches_registry_and_is_not_current() -> None:
    e = _entries()["eval"]
    built = _built(e)
    if built is None:
        pytest.skip("eval snapshot not built on this machine")
    assert snapshots.sha256(built / MANIFEST) == e["manifest_sha256"]
    snap = snapshots.load(built)
    m = snap.manifest
    assert m["pinned"] is True
    assert m["snapshot_id"] == e["snapshot_id"]
    assert m["as_of_cutoff"] == e["as_of_cutoff"] == m["latest_game_date"]
    assert m["as_of_date"] == e["as_of_date"]
    assert m["checksums"][f"{e['snapshot_id']}.duckdb"] == e["db_sha256"]
    assert any(k.startswith("shots/") for k in m["checksums"])  # the checksum covers shots
    cfg = load_sources()
    cur = snapshots.current(cfg)
    assert cur is None or cur.dir.resolve() != built.resolve()
    assert snap.dir.stat().st_mode & 0o777 == snapshots.DIR_MODE
    assert (built / MANIFEST).stat().st_mode & 0o777 == snapshots.FILE_MODE
    # T-2.1 rework: only the published schemas; staging (post-cutoff rows) is not shipped.
    from app.snapshot import connect_read_only

    con = connect_read_only(snap.db, snap.shots)
    try:
        rows = con.execute(
            "select distinct schema_name from duckdb_tables() where database_name = "
            "current_database() union select distinct schema_name from duckdb_views() "
            "where database_name = current_database() and not internal"
        ).fetchall()
    finally:
        con.close()
    assert {r[0] for r in rows} == set(snapshots.PUBLISHED_SCHEMAS)


def test_registry_entry_survives_copy_without_becoming_publishable(tmp_path: Path) -> None:
    """A copy of the real manifest under a tmp root is still refused (pinned travels with it)."""
    e = _entries()["eval"]
    built = _built(e)
    if built is None:
        pytest.skip("eval snapshot not built on this machine")
    cfg = cfg_for(tmp_path)
    d = cfg.resolve(cfg.paths.snapshots) / e["snapshot_id"]
    d.mkdir(parents=True)
    shutil.copyfile(built / MANIFEST, d / MANIFEST)
    manifest = json.loads((d / MANIFEST).read_text())
    snap = snapshots.Snapshot(e["snapshot_id"], d, manifest)
    with pytest.raises(snapshots.BuildError, match="never made current"):
        snapshots.publish(cfg, snap)
    assert not cfg.resolve(cfg.snapshots.current_link).is_symlink()
