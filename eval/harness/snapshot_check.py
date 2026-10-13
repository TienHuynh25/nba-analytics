"""Verify the pinned eval snapshot before any eval run (T-GATE2, DEF-A).

A run's report names the snapshot it claims to use, so the harness proves that snapshot is the
pinned one: the folder exists, ``manifest.json`` and the database hash to the values in
``eval/snapshots.yaml``, and :func:`ingest.snapshots.health_check` (every manifest checksum, then
an open through the app's locked reader) passes. Nothing is written; sealed files are only read.

``NBA_EVAL_SKIP_SNAPSHOT_CHECK=1`` skips the check for the stub answerer only (CI has no
snapshot). The report then says ``NOT VERIFIED``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT
from ingest import snapshots

REGISTRY = REPO_ROOT / "eval" / "snapshots.yaml"
SKIP_ENV = "NBA_EVAL_SKIP_SNAPSHOT_CHECK"
VERIFIED = "VERIFIED"
NOT_VERIFIED = "NOT VERIFIED"


class SnapshotCheckError(RuntimeError):
    """The pinned snapshot is missing, altered or unhealthy: the run must not start."""


@dataclass(frozen=True)
class SnapshotCheck:
    snapshot_id: str
    manifest_sha256: str
    db_sha256: str
    status: str  # VERIFIED | NOT VERIFIED


def pinned_entry(registry: Path = REGISTRY) -> dict[str, Any]:
    data = yaml.safe_load(registry.read_text()) or {}
    entry = data.get("eval")
    if not isinstance(entry, dict):
        raise SnapshotCheckError(f"{registry} has no 'eval' entry")
    return entry


def verify(entry: dict[str, Any], root: Path = REPO_ROOT) -> SnapshotCheck:
    """Return a VERIFIED check or raise :class:`SnapshotCheckError` saying what is wrong."""
    sid = str(entry["snapshot_id"])
    d = root / entry["path"]
    manifest = d / snapshots.MANIFEST
    if not manifest.is_file():
        raise SnapshotCheckError(
            f"pinned snapshot {sid} not found at {d} (build it: make refresh AS_OF=... "
            f"SNAPSHOT_ID={sid})"
        )
    got = snapshots.sha256(manifest)
    if got != entry["manifest_sha256"]:
        raise SnapshotCheckError(
            f"{sid}: manifest.json sha256 {got} != pinned {entry['manifest_sha256']}"
        )
    try:
        snap = snapshots.load(d)
    except (ValueError, KeyError, OSError) as exc:
        raise SnapshotCheckError(f"{sid}: manifest unreadable: {exc}") from exc
    if snap.snapshot_id != sid:
        raise SnapshotCheckError(f"{sid}: manifest names snapshot {snap.snapshot_id}")
    if not snap.db.is_file():
        raise SnapshotCheckError(f"{sid}: database file missing")
    db = snapshots.sha256(snap.db)
    if db != entry["db_sha256"]:
        raise SnapshotCheckError(f"{sid}: database sha256 {db} != pinned {entry['db_sha256']}")
    try:
        snapshots.health_check(snap, full=True)
    except snapshots.HealthError as exc:
        raise SnapshotCheckError(f"health check failed: {exc}") from exc
    return SnapshotCheck(sid, got, db, VERIFIED)


def unchecked(entry: dict[str, Any]) -> SnapshotCheck:
    return SnapshotCheck(str(entry["snapshot_id"]), "n/a", "n/a", NOT_VERIFIED)


def check_for_run(
    answerer: str,
    env: dict[str, str] | None = None,
    registry: Path = REGISTRY,
    root: Path = REPO_ROOT,
) -> SnapshotCheck:
    """Verify, or label NOT VERIFIED when the CI escape hatch is set (stub answerer only)."""
    env = dict(os.environ) if env is None else env
    entry = pinned_entry(registry)
    if env.get(SKIP_ENV) == "1":
        if answerer != "stub":
            raise SnapshotCheckError(f"{SKIP_ENV}=1 is only allowed with the stub answerer")
        return unchecked(entry)
    return verify(entry, root)
