from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from app.config import load_sources
from ingest.backfill import Checkpoints, Unit, last_completed_season, run
from ingest.client import NbaClient
from ingest.raw_store import RawStore

EMPTY_LOG = {"resultSets": [{"name": "LeagueGameLog", "headers": [], "rowSet": []}]}


class Killed(BaseException):
    """Stands in for SIGKILL/KeyboardInterrupt: not caught by the backfill's error handling."""


def store_with(tmp: Path, calls: list[dict[str, Any]], die_after: int | None = None) -> RawStore:
    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        if die_after is not None and len(calls) >= die_after:
            raise Killed
        calls.append(dict(params))
        return EMPTY_LOG

    client = NbaClient(load_sources().nba_api, transport=transport, sleep=lambda s: None)
    return RawStore(tmp / "raw", client)


def test_kill_and_restart_resumes_at_next_unfinished_pair(tmp_path: Path) -> None:
    ckpt = Checkpoints(tmp_path / "ckpt")
    last = 2000  # 2000-01 .. 1946-47 regular season + playoffs, team + player: 55*2*2 units
    total = (2000 - 1946 + 1) * 2 * 2

    first: list[dict[str, Any]] = []
    with pytest.raises(Killed):
        run(store_with(tmp_path, first, die_after=7), ckpt, ["gamelogs"], last)
    assert len(first) == 7

    second: list[dict[str, Any]] = []
    stats = run(store_with(tmp_path, second), ckpt, ["gamelogs"], last)
    assert stats == {"fetched": total - 7, "skipped": 7, "failed": 0}
    done_first = {(c["Season"], c["SeasonType"], c["PlayerOrTeam"]) for c in first}
    done_second = {(c["Season"], c["SeasonType"], c["PlayerOrTeam"]) for c in second}
    assert not done_first & done_second
    assert len(done_first | done_second) == total

    third: list[dict[str, Any]] = []
    assert run(store_with(tmp_path, third), ckpt, ["gamelogs"], last)["fetched"] == 0
    assert third == []


def test_failed_unit_is_logged_and_retried(tmp_path: Path) -> None:
    ckpt = Checkpoints(tmp_path / "ckpt")
    calls: list[dict[str, Any]] = []

    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        calls.append(dict(params))
        if params["Season"] == "1999-00":
            raise ConnectionError("reset")
        return EMPTY_LOG

    cfg = load_sources().nba_api.model_copy(update={"max_retries": 0})
    store = RawStore(tmp_path / "raw", NbaClient(cfg, transport=transport, sleep=lambda s: None))
    stats = run(store, ckpt, ["gamelogs"], 2000)
    assert stats["failed"] == 4  # 1999-00: RS and playoffs, team and player
    failed = (tmp_path / "ckpt" / "_failed.jsonl").read_text().splitlines()
    assert len(failed) == 4 and all("1999-00" in line for line in failed)
    assert not ckpt.done(
        Unit.make(
            "leaguegamelog_t", "1999-00", season="1999-00", season_type_all_star="Regular Season"
        )
    )


def test_last_completed_season() -> None:
    from datetime import date

    assert last_completed_season(date(2026, 9, 30)) == 2025
    assert last_completed_season(date(2026, 10, 4)) == 2025  # preseason: no games yet
    assert last_completed_season(date(2026, 10, 21)) == 2026
