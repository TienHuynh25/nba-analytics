from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from app.config import load_sources
from ingest.backfill import STAGES, Checkpoints, Unit, last_completed_season, run, status
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


# --- kill and resume across every stage --------------------------------------------------------

LAST = 1997  # 1996-97 and 1997-98: both advanced-stat seasons, so every stage has work


def _body(name: str, headers: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    return {"resultSets": [{"name": name, "headers": headers, "rowSet": rows}]}


def _respond(endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
    if endpoint == "commonallplayers":
        return _body("CommonAllPlayers", ["PERSON_ID"], [[101], [102], [103]])
    if endpoint == "franchisehistory":
        return {
            "resultSets": [
                {"name": "FranchiseHistory", "headers": ["TEAM_ID"], "rowSet": [[1], [2]]},
                {"name": "DefunctTeams", "headers": ["TEAM_ID"], "rowSet": [[3]]},
            ]
        }
    if endpoint == "leaguegamelog" and params.get("PlayerOrTeam") == "T":
        return _body("LeagueGameLog", ["TEAM_ID"], [[1], [2]])
    return _body("Other", [], [])


def _fake_store(tmp: Path, calls: list[str], die_after: int | None) -> RawStore:
    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        if die_after is not None and len(calls) >= die_after:
            raise Killed
        calls.append(ep + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params)))
        return _respond(ep, params)

    client = NbaClient(load_sources().nba_api, transport=transport, sleep=lambda s: None)
    return RawStore(tmp / "raw", client)


def _run_all(tmp: Path, ckpt: Checkpoints, calls: list[str], die_after: int | None) -> Any:
    return run(_fake_store(tmp, calls, die_after), ckpt, list(STAGES), LAST)


def test_kill_anywhere_then_resume_fetches_every_unit_exactly_once(tmp_path: Path) -> None:
    clean: list[str] = []
    clean_stats = _run_all(tmp_path / "clean", Checkpoints(tmp_path / "clean" / "ck"), clean, None)
    assert clean_stats["failed"] == 0
    assert len(clean) == len(set(clean)) > 100  # every stage contributed, no unit twice

    for kill_at in (1, 2, 5, 17, 60, len(clean) - 1):
        work = tmp_path / f"kill_{kill_at}"
        ckpt = Checkpoints(work / "ck")
        seen: list[str] = []
        with pytest.raises(Killed):
            _run_all(work, ckpt, seen, kill_at)
        assert len(seen) == kill_at
        # Resume, killing again part-way, then finish.
        if kill_at < len(clean) - 4:
            with pytest.raises(Killed):
                _run_all(work, ckpt, seen, len(seen) + 3)
        _run_all(work, ckpt, seen, None)
        # Units may be re-fetched only for the cached reference reads that planners make before
        # a checkpoint exists; the unit set and the total must match a clean run.
        assert set(seen) == set(clean), kill_at
        assert len(seen) == len(clean), f"duplicate fetches after kill at {kill_at}"
        again: list[str] = []
        assert _run_all(work, ckpt, again, None)["fetched"] == 0 and again == []


def test_status_counts_progress_and_flags_stages_that_need_earlier_ones(tmp_path: Path) -> None:
    ckpt = Checkpoints(tmp_path / "ck")
    cold = RawStore(tmp_path / "raw", None)
    rows = {s: (d, t) for s, d, t in status(cold, ckpt, LAST)}
    assert rows["reference"] == (0, 2) and rows["gamelogs"][0] == 0
    assert rows["team_history"] == (0, -1) and rows["players"] == (0, -1)  # cache is empty
    calls: list[str] = []
    run(_fake_store(tmp_path, calls, None), ckpt, list(STAGES), LAST)
    warm = RawStore(tmp_path / "raw", None)
    after = {s: (d, t) for s, d, t in status(warm, ckpt, LAST)}
    assert all(d == t > 0 for d, t in after.values()), after
    assert after["players"][1] == 3 * 3  # careers, awards, info for 3 players
    assert after["team_history"][1] == 3  # 2 current + 1 defunct franchise team


def test_limit_stops_after_n_fetches_and_resumes(tmp_path: Path) -> None:
    ckpt = Checkpoints(tmp_path / "ck")
    calls: list[str] = []
    stats = run(_fake_store(tmp_path, calls, None), ckpt, ["gamelogs"], LAST, limit=3)
    assert stats["fetched"] == 3 and len(calls) == 3
    stats = run(_fake_store(tmp_path, calls, None), ckpt, ["gamelogs"], LAST)
    assert stats["skipped"] == 3 and len(set(calls)) == len(calls)
