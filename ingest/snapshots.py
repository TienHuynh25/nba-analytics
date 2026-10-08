"""Snapshot build, publish, prune and rollback (tasks 1.24, 1.25, 1.28).

Layout::

    data/snapshots/<snapshot_id>/<snapshot_id>.duckdb
    data/snapshots/<snapshot_id>/shots/season=<season>/*.parquet
    data/snapshots/<snapshot_id>/manifest.json
    data/snapshots/current -> <snapshot_id>          (symlink; the app opens this read-only)

A build writes into its final folder with a ``BUILDING`` marker file, removed only after dbt's
tests pass and the manifest is written (the folder cannot be renamed afterwards, because the shots
view stores its absolute Parquet path). A folder with the marker is never listed or published, so
a failed or killed build never touches a published snapshot. Publishing repoints
``current`` by renaming a new symlink over the old one, which is atomic on POSIX file systems. A
crash at any point leaves ``current`` pointing at a complete snapshot. Nightly snapshots beyond the
newest ``keep`` (7) are pruned; pinned snapshots (the eval snapshot) and the one ``current`` points
at are never pruned.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

from app.config import REPO_ROOT, SourcesConfig
from ingest.land import land
from metrics import generate_views
from metrics.schema import load as load_registry

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
TRANSFORM = REPO_ROOT / "transform"
MANIFEST = "manifest.json"
MARKER = "BUILDING"
MARTS = (
    "players",
    "player_aliases",
    "franchises",
    "teams",
    "games",
    "player_game",
    "player_season_stint",
    "player_season",
    "team_season",
    "team_titles",
    "awards",
    "records",
    "stat_availability",
    "shots",
)


class BuildError(RuntimeError):
    pass


class HealthError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    dir: Path
    manifest: dict[str, Any]

    @property
    def db(self) -> Path:
        return self.dir / f"{self.snapshot_id}.duckdb"

    @property
    def shots(self) -> Path:
        return self.dir / "shots"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run_dbt(
    db: Path,
    shots: Path,
    landing: Path,
    as_of: date | None,
    extra_vars: dict[str, Any] | None = None,
) -> None:
    env = {
        **os.environ,
        "NBA_SNAPSHOT_PATH": str(db),
        "NBA_SHOTS_DIR": str(shots),
        "NBA_LANDING_PATH": str(landing),
    }
    cmd = ["dbt", "build", "--profiles-dir", ".", "--project-dir", "."]
    dbt_vars: dict[str, Any] = dict(extra_vars or {})
    if as_of is not None:
        dbt_vars["as_of"] = as_of.isoformat()
    if dbt_vars:
        cmd += ["--vars", json.dumps(dbt_vars)]
    res = subprocess.run(cmd, cwd=TRANSFORM, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        tail = "\n".join(res.stdout.splitlines()[-40:])
        raise BuildError(f"dbt build failed:\n{tail}")


def _checksums(snap_dir: Path, snapshot_id: str) -> dict[str, str]:
    files = [snap_dir / f"{snapshot_id}.duckdb", *sorted((snap_dir / "shots").rglob("*.parquet"))]
    return {str(p.relative_to(snap_dir)): sha256(p) for p in files}


def write_manifest(
    snap_dir: Path, snapshot_id: str, as_of: date | None, today: date, pinned: bool
) -> dict[str, Any]:
    db = snap_dir / f"{snapshot_id}.duckdb"
    con = duckdb.connect(str(db), read_only=True)
    try:
        counts = {}
        for t in MARTS:
            counts[t] = con.execute(f"select count(*) from marts.{t}").fetchone()[0]  # type: ignore[index]
        latest = con.execute("select max(game_date) from marts.games").fetchone()[0]  # type: ignore[index]
    finally:
        con.close()
    # Nightly: the build date in US Eastern time. As-of: the day after the last included game.
    as_of_date = (latest + timedelta(days=1)) if as_of is not None else today
    manifest = {
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date.isoformat(),
        "as_of_cutoff": as_of.isoformat() if as_of else None,
        "latest_game_date": latest.isoformat() if latest else None,
        "built_at": datetime.now(UTC).isoformat(),
        "pinned": pinned,
        "registry_version": load_registry().version,
        "git_sha": git_sha(),
        "row_counts": counts,
        "checksums": _checksums(snap_dir, snapshot_id),
    }
    (snap_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def link_unchanged_shots(new: Path, prev: Path | None) -> int:
    """Replace shot files identical to the previous snapshot's with hard links (spec: shots)."""
    if prev is None or not (prev / "shots").exists():
        return 0
    linked = 0
    for f in (new / "shots").rglob("*.parquet"):
        old = prev / "shots" / f.relative_to(new / "shots")
        if old.exists() and old.stat().st_size == f.stat().st_size and sha256(old) == sha256(f):
            tmp = f.with_suffix(".link")
            os.link(old, tmp)
            tmp.replace(f)
            linked += 1
    return linked


def build(
    cfg: SourcesConfig,
    snapshot_id: str | None = None,
    as_of: date | None = None,
    today: date | None = None,
    pinned: bool = False,
) -> Snapshot:
    today = today or datetime.now(ET).date()
    sid = snapshot_id or f"nba_{today:%Y%m%d}"
    root = cfg.resolve(cfg.paths.snapshots)
    work = root / sid
    if work.exists() and not (work / MARKER).exists():
        raise BuildError(f"snapshot {sid} already exists; snapshots are immutable")
    if work.exists():
        shutil.rmtree(work)  # leftover of a killed build
    work.mkdir(parents=True)
    (work / MARKER).write_text(datetime.now(UTC).isoformat())
    build_dir = REPO_ROOT / "data" / "build"
    landing = build_dir / f"landing_{sid}.duckdb"
    try:
        generate_views.write()  # semantic views always match the registry being built
        land(cfg.resolve(cfg.paths.raw), landing, build_dir / f"landing_work_{sid}")
        run_dbt(work / f"{sid}.duckdb", work / "shots", landing, as_of)
        prev = current(cfg)
        linked = link_unchanged_shots(work, prev.dir if prev else None)
        manifest = write_manifest(work, sid, as_of, today, pinned)
        (work / MARKER).unlink()
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    finally:
        landing.unlink(missing_ok=True)
    log.info(
        "snapshot built",
        extra={"event": "snapshot_built", "path": str(work), "rows": linked},
    )
    return Snapshot(sid, work, manifest)


def load(snap_dir: Path) -> Snapshot:
    manifest = json.loads((snap_dir / MANIFEST).read_text())
    return Snapshot(manifest["snapshot_id"], snap_dir, manifest)


def health_check(snap: Snapshot, full: bool = True) -> None:
    """Raise :class:`HealthError` unless the snapshot's files match its manifest and it opens."""
    if (snap.dir / MARKER).exists():
        raise HealthError(f"{snap.snapshot_id}: build did not finish")
    if not snap.db.exists():
        raise HealthError(f"{snap.snapshot_id}: database file missing")
    if full:
        for rel, digest in snap.manifest["checksums"].items():
            p = snap.dir / rel
            if not p.exists() or sha256(p) != digest:
                raise HealthError(f"{snap.snapshot_id}: {rel} does not match its manifest checksum")
    try:
        con = duckdb.connect(str(snap.db), read_only=True)
        try:
            con.execute("select count(*) from marts.games").fetchone()
        finally:
            con.close()
    except duckdb.Error as exc:
        raise HealthError(f"{snap.snapshot_id}: cannot open: {exc}") from exc


def _link(cfg: SourcesConfig) -> Path:
    return cfg.resolve(cfg.snapshots.current_link)


def current(cfg: SourcesConfig) -> Snapshot | None:
    link = _link(cfg)
    if not link.is_symlink():
        return None
    target = link.resolve()
    return load(target) if (target / MANIFEST).exists() else None


def point_current(cfg: SourcesConfig, snap: Snapshot) -> None:
    """Atomically repoint ``current`` at ``snap`` (rename a fresh symlink over the old one)."""
    link = _link(cfg)
    tmp = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    os.symlink(snap.dir.name, tmp)  # relative target, so the tree can move as a whole
    os.replace(tmp, link)


def published(cfg: SourcesConfig) -> list[Snapshot]:
    """All complete snapshots, newest build first."""
    root = cfg.resolve(cfg.paths.snapshots)
    snaps = (
        [
            load(d)
            for d in root.iterdir()
            if d.is_dir()
            and not d.is_symlink()
            and not (d / MARKER).exists()
            and (d / MANIFEST).exists()
        ]
        if root.exists()
        else []
    )
    return sorted(snaps, key=lambda s: s.manifest["built_at"], reverse=True)


def publish(cfg: SourcesConfig, snap: Snapshot) -> None:
    if snap.manifest.get("pinned"):
        raise BuildError(f"{snap.snapshot_id} is pinned (eval snapshot) and is never made current")
    health_check(snap)
    point_current(cfg, snap)
    log.info("published", extra={"event": "published", "path": snap.snapshot_id})
    prune(cfg)


def prune(cfg: SourcesConfig) -> list[str]:
    cur = current(cfg)
    nightly = [s for s in published(cfg) if not s.manifest.get("pinned")]
    removed = []
    for s in nightly[cfg.snapshots.keep :]:
        if cur is not None and s.dir == cur.dir:
            continue
        shutil.rmtree(s.dir)
        removed.append(s.snapshot_id)
    return removed


def open_current(cfg: SourcesConfig, full_check: bool = True) -> Snapshot:
    """Return a healthy current snapshot, rolling back to the newest healthy one (1.25)."""
    cur = current(cfg)
    if cur is not None:
        try:
            health_check(cur, full=full_check)
            return cur
        except HealthError as exc:
            log.error("current snapshot unhealthy", extra={"event": "rollback", "error": str(exc)})
    for snap in published(cfg):
        if snap.manifest.get("pinned") or (cur is not None and snap.dir == cur.dir):
            continue
        try:
            health_check(snap, full=full_check)
        except HealthError:
            continue
        point_current(cfg, snap)
        log.warning("rolled back", extra={"event": "rollback", "path": snap.snapshot_id})
        return snap
    raise HealthError("no healthy snapshot available")
