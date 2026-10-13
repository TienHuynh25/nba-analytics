"""T-GATE2 DEF-A: the harness proves the pinned snapshot before it runs. Uses tmp copies only."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from eval.harness import conftest as harness_conftest
from eval.harness import snapshot_check as sc
from ingest import snapshots
from tests.test_snapshots import cfg_for, fake_snapshot

SID = "eval_2025_26_rs"


def _entry(tmp_path: Path, **over: Any) -> dict[str, Any]:
    snap = fake_snapshot(cfg_for(tmp_path), SID, pinned=True)
    e = {
        "snapshot_id": SID,
        "path": f"snapshots/{SID}",
        "manifest_sha256": snapshots.sha256(snap.dir / snapshots.MANIFEST),
        "db_sha256": snapshots.sha256(snap.db),
    }
    return {**e, **over}


def _registry(tmp_path: Path, entry: dict[str, Any]) -> Path:
    p = tmp_path / "snapshots.yaml"
    p.write_text(yaml.safe_dump({"eval": entry}))
    return p


def test_good_snapshot_is_verified_with_both_hashes(tmp_path: Path) -> None:
    e = _entry(tmp_path)
    c = sc.verify(e, tmp_path)
    assert c.status == "VERIFIED" == sc.VERIFIED
    assert c.manifest_sha256 == e["manifest_sha256"] and c.db_sha256 == e["db_sha256"]


def test_missing_snapshot_is_refused(tmp_path: Path) -> None:
    e = _entry(tmp_path, path="snapshots/eval_bogus", snapshot_id="eval_bogus")
    with pytest.raises(sc.SnapshotCheckError, match="not found"):
        sc.verify(e, tmp_path)


def test_wrong_manifest_hash_is_refused(tmp_path: Path) -> None:
    with pytest.raises(sc.SnapshotCheckError, match=r"manifest\.json sha256"):
        sc.verify(_entry(tmp_path, manifest_sha256="0" * 64), tmp_path)


def test_wrong_db_hash_is_refused(tmp_path: Path) -> None:
    with pytest.raises(sc.SnapshotCheckError, match="database sha256"):
        sc.verify(_entry(tmp_path, db_sha256="0" * 64), tmp_path)


def test_tampered_shot_file_fails_the_health_check(tmp_path: Path) -> None:
    e = _entry(tmp_path)
    shot = tmp_path / "snapshots" / SID / "shots" / "season=2025-26" / "data_0.parquet"
    shot.write_bytes(b"tampered")
    with pytest.raises(sc.SnapshotCheckError, match="health check failed"):
        sc.verify(e, tmp_path)


def test_tampered_database_is_refused(tmp_path: Path) -> None:
    e = _entry(tmp_path)
    db = tmp_path / "snapshots" / SID / f"{SID}.duckdb"
    db.write_bytes(db.read_bytes() + b"x")
    with pytest.raises(sc.SnapshotCheckError):
        sc.verify(e, tmp_path)


def test_check_for_run_blocks_a_bogus_snapshot(tmp_path: Path) -> None:
    reg = _registry(tmp_path, _entry(tmp_path, path="snapshots/none", snapshot_id="none"))
    with pytest.raises(sc.SnapshotCheckError):
        sc.check_for_run("stub", env={}, registry=reg, root=tmp_path)


def test_check_for_run_verifies_a_good_snapshot(tmp_path: Path) -> None:
    reg = _registry(tmp_path, _entry(tmp_path))
    c = sc.check_for_run("stub", env={}, registry=reg, root=tmp_path)
    assert c.status == "VERIFIED"


def test_escape_hatch_labels_not_verified_for_stub_only(tmp_path: Path) -> None:
    reg = _registry(tmp_path, _entry(tmp_path, path="snapshots/none"))  # nothing built there
    env = {sc.SKIP_ENV: "1"}
    c = sc.check_for_run("stub", env=env, registry=reg, root=tmp_path)
    assert c.status == "NOT VERIFIED" and c.manifest_sha256 == "n/a"
    with pytest.raises(sc.SnapshotCheckError, match="only allowed with the stub"):
        sc.check_for_run("stats", env=env, registry=reg, root=tmp_path)


def test_heldout_needs_an_explicit_ok() -> None:
    assert harness_conftest.heldout_allowed("dev", {})
    for split in ("heldout", "all"):
        assert not harness_conftest.heldout_allowed(split, {})
        assert not harness_conftest.heldout_allowed(split, {"HELDOUT_OK": "yes"})
        assert harness_conftest.heldout_allowed(split, {"HELDOUT_OK": "1"})
