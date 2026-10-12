"""One-command refresh: extract -> check -> land -> dbt build and tests -> publish (task 1.26).

Usage::

    make refresh                               # nightly: incremental extract, build, publish
    make refresh AS_OF=2026-04-12 SNAPSHOT_ID=eval_2025_26_rs
                                               # as-of build from the cache, pinned, not published

A nightly run fetches the 7-day correction window, stops if fetched games per day are off the
league schedule by more than 10% (1.8), builds a new snapshot, and repoints ``current`` only if
every dbt test passes. Any failure keeps yesterday's snapshot live. Every run appends one line to
``data/logs/ingest_log.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app import jsonlog
from app.config import sources
from ingest import snapshots
from ingest.client import NbaClient
from ingest.contracts import validate
from ingest.endpoints import SPECS, season_label
from ingest.incremental import check_game_counts, fetch_window, scheduled_games_by_day
from ingest.raw_store import RawStore

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def _log_run(record: dict[str, Any]) -> None:
    cfg = sources()
    path = cfg.resolve(cfg.paths.logs) / "ingest_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def nightly(today: date) -> snapshots.Snapshot:
    cfg = sources()
    client = NbaClient(cfg.nba_api)
    store = RawStore(cfg.resolve(cfg.paths.raw), client, validator=validate)
    res = fetch_window(store, today, cfg.ingest.correction_window_days)
    schedule = store.get(
        SPECS["scheduleleaguev2"], res.season, refresh=True, season=res.season
    ).response
    start, end = res.window
    days = [date.fromordinal(d) for d in range(start.toordinal(), end.toordinal() + 1)]
    check_game_counts(
        res.games_by_day, scheduled_games_by_day(schedule), days, cfg.ingest.row_count_tolerance
    )
    snap = snapshots.build(cfg, today=today)
    snapshots.publish(cfg, snap)
    return snap


def as_of_build(cutoff: date, snapshot_id: str | None) -> snapshots.Snapshot:
    cfg = sources()
    sid = snapshot_id or f"asof_{cutoff:%Y%m%d}"
    return snapshots.build(cfg, snapshot_id=sid, as_of=cutoff, pinned=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--as-of", help="cutoff date YYYY-MM-DD (last included game date)")
    ap.add_argument("--snapshot-id", help="name for an as-of snapshot, e.g. eval_2025_26_rs")
    args = ap.parse_args(argv)

    jsonlog.configure()
    run_id = jsonlog.set_run()
    started = time.monotonic()
    today = datetime.now(ET).date()
    record: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now(ET).isoformat(),
        "mode": "as_of" if args.as_of else "nightly",
        "season": season_label(today.year if today.month >= 8 else today.year - 1),
    }
    try:
        if args.as_of:
            snap = as_of_build(date.fromisoformat(args.as_of), args.snapshot_id)
        else:
            snap = nightly(today)
        record.update(
            status="ok",
            snapshot_id=snap.snapshot_id,
            as_of_date=snap.manifest["as_of_date"],
            latest_game_date=snap.manifest["latest_game_date"],
        )
        return_code = 0
    except Exception as exc:
        log.exception("refresh failed", extra={"event": "refresh_failed", "error": str(exc)[:500]})
        record.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])
        return_code = 1
    record["duration_s"] = round(time.monotonic() - started, 1)
    _log_run(record)
    print(json.dumps({k: record[k] for k in ("status", "snapshot_id", "error") if k in record}))
    return return_code


if __name__ == "__main__":
    sys.exit(main())
