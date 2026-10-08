"""Read-only access to the published snapshot (task 3.5).

The app never holds a write lock: every connection is ``read_only``. On each request the store
checks which snapshot ``current`` points at. When the ID changes (a nightly swap), it closes
its connection and opens the new snapshot, and the answer cache is cleared (4.9). The open path
runs the health check and automatic rollback from task 1.25.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import duckdb

from app.config import SourcesConfig, sources
from ingest import snapshots

APP_MEMORY_LIMIT = "2GB"  # docs/decisions/target-mac.md


def connect_read_only(db: Path, shots_dir: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Read-only, with file access locked to the snapshot's own shots folder.

    DuckDB shares one database instance per file within a process, and these settings belong
    to the instance. So every app connection to a snapshot (tools and SQL fallback alike) gets
    the same lockdown, applied here in one place.
    """
    con = duckdb.connect(str(db), read_only=True, config={"memory_limit": APP_MEMORY_LIMIT})
    locked = con.execute("select current_setting('lock_configuration')").fetchone()
    if locked and locked[0]:
        # Another connection already locked this shared instance; make sure it is our lockdown.
        ext = con.execute("select current_setting('enable_external_access')").fetchone()
        if ext is None or ext[0]:
            con.close()
            raise RuntimeError(f"{db} is open with external access enabled and locked")
        return con
    shots = shots_dir if shots_dir is not None else db.parent / "shots"
    dirs = [str(shots.resolve()) + "/"] if shots.exists() else []
    con.execute("SET allowed_directories = ?", [dirs])
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


class LiveSnapshotStore:
    """The live ``current`` snapshot. One instance per worker process."""

    def __init__(
        self,
        cfg: SourcesConfig | None = None,
        on_swap: Callable[[str], None] | None = None,
        full_check: bool = False,
    ) -> None:
        self.cfg = cfg or sources()
        self._on_swap = on_swap
        self._full_check = full_check
        self._lock = threading.Lock()
        self._snap: snapshots.Snapshot | None = None
        self._con: duckdb.DuckDBPyConnection | None = None

    def _target_id(self) -> str | None:
        link = self.cfg.resolve(self.cfg.snapshots.current_link)
        return link.resolve().name if link.is_symlink() else None

    def _ensure(self) -> None:
        with self._lock:
            if self._snap is not None and self._snap.snapshot_id == self._target_id():
                return
            old = self._snap.snapshot_id if self._snap else None
            snap = snapshots.open_current(self.cfg, full_check=self._full_check)
            if self._con is not None:
                self._con.close()
            self._con = connect_read_only(snap.db, snap.shots)
            self._snap = snap
            if old is not None and self._on_swap is not None:
                self._on_swap(snap.snapshot_id)

    def connection(self) -> duckdb.DuckDBPyConnection:
        self._ensure()
        assert self._con is not None
        return self._con

    @property
    def snapshot_id(self) -> str:
        self._ensure()
        assert self._snap is not None
        return self._snap.snapshot_id

    @property
    def manifest(self) -> Mapping[str, Any]:
        self._ensure()
        assert self._snap is not None
        return self._snap.manifest


class FileSnapshotStore:
    """A fixed database file (the eval snapshot, the test fixture)."""

    def __init__(
        self, db: Path, manifest: Mapping[str, Any] | None = None, shots_dir: Path | None = None
    ) -> None:
        self._db = db
        self._con = connect_read_only(db, shots_dir)
        self._manifest = dict(manifest or {})
        if "as_of_date" not in self._manifest:
            row = self._con.execute(
                "select max(game_date) + interval 1 day, max(season) from semantic.games"
            ).fetchone()
            assert row is not None
            self._manifest.setdefault("as_of_date", str(row[0])[:10])
            self._manifest.setdefault("latest_game_date", None)
        self._manifest.setdefault("snapshot_id", db.stem)

    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    @property
    def snapshot_id(self) -> str:
        return str(self._manifest["snapshot_id"])

    @property
    def manifest(self) -> Mapping[str, Any]:
        return self._manifest
