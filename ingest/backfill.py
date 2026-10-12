"""Resumable historical backfill (task 1.5).

Usage::

    uv run python -m ingest.backfill                 # everything through the last completed season
    uv run python -m ingest.backfill --stage gamelogs --through 2025-26
    uv run python -m ingest.backfill --status        # progress per stage, no API calls

Work is split into units, one per (endpoint, partition). The partition is a season (and season
type) for season-grained endpoints and a player or team for per-entity endpoints. When a unit's
raw file is written, a checkpoint marker goes to ``data/checkpoints/backfill/``. A killed or
crashed run resumes at the next unit without a marker. A unit that fails (network or contract) is
logged to ``_failed.jsonl`` and skipped, and a re-run retries it. Stages run in critical-path
order: game logs first, then per-player data, then shots.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app import jsonlog
from app.config import sources
from ingest.client import FetchError, NbaClient
from ingest.contracts import ContractError, validate
from ingest.endpoints import (
    FIRST_ADVANCED_SEASON,
    FIRST_IST_SEASON,
    FIRST_PLAYIN_SEASON,
    FIRST_SEASON,
    FIRST_STANDINGS_SEASON,
    SPECS,
    result_sets,
    season_label,
)
from ingest.raw_store import ALL, RawStore

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

RS, PO, PI, IST = "Regular Season", "Playoffs", "PlayIn", "IST"


@dataclass(frozen=True)
class Unit:
    key: str
    partition: str  # season label or "_all"
    kwargs: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    uid: str = ""

    @staticmethod
    def make(key: str, partition: str | None, **kwargs: Any) -> Unit:
        parts = [f"{k}={kwargs[k]}" for k in sorted(kwargs)]
        slug = re.sub(r"[^A-Za-z0-9=._-]+", "_", "__".join(parts)) or "once"
        return Unit(key, partition or ALL, kwargs, f"{key}/{partition or ALL}/{slug}")


# Regular seasons open in the second half of October; before this day the new season has no games.
SEASON_OPENS = (10, 15)


def last_completed_season(today: date) -> int:
    """Start year of the most recent season that has begun playing."""
    return today.year if (today.month, today.day) >= SEASON_OPENS else today.year - 1


class Checkpoints:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, unit: Unit) -> Path:
        return self.root / f"{unit.uid}.done"

    def done(self, unit: Unit) -> bool:
        return self._path(unit).exists()

    def mark(self, unit: Unit, raw_path: Path) -> None:
        p = self._path(unit)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"raw": str(raw_path), "at": datetime.now(UTC).isoformat()}))
        tmp.replace(p)

    def fail(self, unit: Unit, error: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "_failed.jsonl").open("a", encoding="utf-8") as f:
            rec = {"uid": unit.uid, "error": error[:500], "at": datetime.now(UTC).isoformat()}
            f.write(json.dumps(rec) + "\n")

    def count(self, prefix: str) -> int:
        base = self.root / prefix
        return sum(1 for _ in base.rglob("*.done")) if base.exists() else 0


# --- stage planners -----------------------------------------------------------------------------
# Each planner gets the store (to read already-fetched parents, e.g. the player list) and the last
# season start year, and yields units. Planners that depend on another stage's output read it from
# the raw cache, so they only work once that stage has run.


def plan_reference(store: RawStore, last: int) -> Iterator[Unit]:
    yield Unit.make("commonallplayers", None, season=season_label(last))
    yield Unit.make("franchisehistory", None)


def _season_types(y: int) -> list[str]:
    types = [RS, PO]
    if y >= FIRST_PLAYIN_SEASON:
        types.append(PI)
    if y >= FIRST_IST_SEASON:
        types.append(IST)
    return types


def plan_gamelogs(store: RawStore, last: int) -> Iterator[Unit]:
    for y in range(last, FIRST_SEASON - 1, -1):  # newest first: the eval snapshot needs recent data
        s = season_label(y)
        for st in _season_types(y):
            for key in ("leaguegamelog_t", "leaguegamelog_p"):
                yield Unit.make(key, s, season=s, season_type_all_star=st)


def plan_team_history(store: RawStore, last: int) -> Iterator[Unit]:
    body = store.get(SPECS["franchisehistory"]).response
    sets = result_sets(body)
    # Defunct franchises (e.g. the 1948-champion Baltimore Bullets) are needed for team_titles.
    team_ids = sorted(
        {r["TEAM_ID"] for name in ("FranchiseHistory", "DefunctTeams") for r in sets[name]}
    )
    for tid in team_ids:
        yield Unit.make("teamyearbyyearstats", None, team_id=tid)


def plan_season_dash(store: RawStore, last: int) -> Iterator[Unit]:
    for y in range(last, FIRST_ADVANCED_SEASON - 1, -1):
        s = season_label(y)
        for st in (RS, PO):
            yield Unit.make("leaguedashteamstats_adv", s, season=s, season_type_all_star=st)
            yield Unit.make("leaguedashplayerstats_adv", s, season=s, season_type_all_star=st)
    for y in range(last, FIRST_STANDINGS_SEASON - 1, -1):
        s = season_label(y)
        yield Unit.make("leaguestandingsv3", s, season=s)


def _player_ids(store: RawStore, last: int) -> list[int]:
    body = store.get(SPECS["commonallplayers"], season=season_label(last)).response
    return sorted({int(r["PERSON_ID"]) for r in result_sets(body)["CommonAllPlayers"]})


def plan_players(store: RawStore, last: int) -> Iterator[Unit]:
    for pid in _player_ids(store, last):
        yield Unit.make("playercareerstats", None, player_id=pid)
    for pid in _player_ids(store, last):
        yield Unit.make("playerawards", None, player_id=pid)
    for pid in _player_ids(store, last):
        yield Unit.make("commonplayerinfo", None, player_id=pid)


def plan_shots(store: RawStore, last: int) -> Iterator[Unit]:
    for y in range(last, FIRST_ADVANCED_SEASON - 1, -1):
        s = season_label(y)
        for st in (RS, PO):
            try:
                body = store.get(SPECS["leaguegamelog_t"], s, season=s, season_type_all_star=st)
            except LookupError:
                continue  # game logs for this season not fetched yet
            teams = sorted({r["TEAM_ID"] for r in result_sets(body.response)["LeagueGameLog"]})
            for tid in teams:
                yield Unit.make(
                    "shotchartdetail", s, team_id=tid, season_nullable=s, season_type_all_star=st
                )


STAGES: dict[str, Callable[[RawStore, int], Iterator[Unit]]] = {
    "reference": plan_reference,
    "gamelogs": plan_gamelogs,
    "team_history": plan_team_history,
    "season_dash": plan_season_dash,
    "players": plan_players,
    "shots": plan_shots,
}


def run(
    store: RawStore,
    ckpt: Checkpoints,
    stages: Iterable[str],
    last: int,
    limit: int | None = None,
) -> dict[str, int]:
    """Fetch every unit without a checkpoint. Returns counts of done, skipped and failed units."""
    stats = {"fetched": 0, "skipped": 0, "failed": 0}
    for stage in stages:
        log.info("stage start", extra={"event": "stage_start", "status": stage})
        try:
            units = list(STAGES[stage](store, last))
        except LookupError as exc:
            log.error(
                "stage needs an earlier stage",
                extra={"event": "stage_blocked", "status": stage, "error": str(exc)},
            )
            stats["failed"] += 1
            continue
        for unit in units:
            if ckpt.done(unit):
                stats["skipped"] += 1
                continue
            if limit is not None and stats["fetched"] >= limit:
                return stats
            spec = SPECS[unit.key]
            try:
                rec = store.get(
                    spec, unit.partition if unit.partition != ALL else None, **unit.kwargs
                )
            except (FetchError, ContractError) as exc:
                stats["failed"] += 1
                ckpt.fail(unit, f"{type(exc).__name__}: {exc}")
                log.error(
                    "unit failed",
                    extra={
                        "event": "unit_failed",
                        "endpoint": unit.key,
                        "path": unit.uid,
                        "error": str(exc)[:300],
                    },
                )
                continue
            ckpt.mark(unit, rec.path)
            stats["fetched"] += 1
            log.info(
                "unit done", extra={"event": "unit_done", "endpoint": unit.key, "path": unit.uid}
            )
    return stats


def status(store: RawStore, ckpt: Checkpoints, last: int) -> list[tuple[str, int, int]]:
    rows = []
    for stage, planner in STAGES.items():
        try:
            units = list(planner(store, last))
        except LookupError:
            rows.append((stage, 0, -1))
            continue
        rows.append((stage, sum(ckpt.done(u) for u in units), len(units)))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--stage", action="append", choices=list(STAGES), help="repeatable")
    ap.add_argument("--through", help="last season to fetch, e.g. 2025-26")
    ap.add_argument("--limit", type=int, help="stop after this many fetched units")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    cfg = sources()
    logs = cfg.resolve(cfg.paths.logs)
    logs.mkdir(parents=True, exist_ok=True)
    jsonlog.configure()
    fh = logging.FileHandler(logs / "backfill.jsonl")
    fh.setFormatter(jsonlog.JsonFormatter())
    logging.getLogger().addHandler(fh)
    jsonlog.set_run()

    last = int(args.through[:4]) if args.through else last_completed_season(datetime.now(ET).date())
    ckpt = Checkpoints(cfg.resolve(cfg.paths.checkpoints) / "backfill")
    if args.status:
        store = RawStore(cfg.resolve(cfg.paths.raw), None)
        for stage, done, total in status(store, ckpt, last):
            print(f"{stage:13} {done:>6} / {total if total >= 0 else '(needs earlier stage)'}")
        return 0
    store = RawStore(cfg.resolve(cfg.paths.raw), NbaClient(cfg.nba_api), validator=validate)
    stats = run(store, ckpt, args.stage or list(STAGES), last, args.limit)
    log.info("backfill finished", extra={"event": "backfill_done", "status": json.dumps(stats)})
    print(json.dumps(stats))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
