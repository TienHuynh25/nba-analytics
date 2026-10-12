"""Task 1.8 done-when checks: the row-count anomaly check against the schedule (+/-10%).

Plan 1.8: "Row-count anomaly check against expected games per day (+/-10%). A simulated short day
stops the run." The existing unit tests in ``test_incremental.py`` cover one short day at -25%
and ``test_refresh.py`` fakes the check entirely. This file adds what they do not:

- the tolerance boundary (exactly 10% passes, one game more than 10% fails, both directions);
- a day with games fetched but none scheduled, and a scheduled day with none fetched;
- an end-to-end nightly run with the real fetch, schedule parse and check (only the network
  transport, the snapshot build and publish are faked): a short day stops before build and
  publish, and a day within tolerance reaches publish.

Nothing here touches the network: the NBA client gets a fake transport and no sleeps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import SourcesConfig, load_sources
from ingest import refresh, snapshots
from ingest.client import NbaClient
from ingest.incremental import AnomalyError, check_game_counts

DAY = date(2026, 4, 10)
TEAMS = (1610612738, 1610612752)


def games(prefix: str, n: int) -> list[str]:
    return [f"{prefix}{i:07d}" for i in range(n)]


# ---- tolerance boundary (pure function) -------------------------------------------------------


@pytest.mark.parametrize(
    ("fetched", "scheduled", "ok"),
    [
        (10, 10, True),  # exact
        (9, 10, True),  # -10% exactly: inclusive, passes
        (11, 10, True),  # +10% exactly: inclusive, passes
        (8, 10, False),  # -20%
        (12, 10, False),  # +20%
        (1, 10, False),  # -90%
        (0, 10, False),  # short day with no games at all
        (1, 1, True),
        (0, 1, False),  # one scheduled game missing
    ],
)
def test_tolerance_boundary(fetched: int, scheduled: int, ok: bool) -> None:
    fetched_map = {DAY: games("g", fetched)} if fetched else {}
    expected = {DAY: scheduled}
    if ok:
        check_game_counts(fetched_map, expected, [DAY], 0.10)
    else:
        with pytest.raises(AnomalyError, match=f"fetched {fetched}, scheduled {scheduled}"):
            check_game_counts(fetched_map, expected, [DAY], 0.10)


def test_fetched_duplicates_do_not_inflate_the_count() -> None:
    # Two fetches of the same game id (correction window) must count once.
    dup = games("g", 8) + games("g", 8)
    with pytest.raises(AnomalyError, match="fetched 8, scheduled 10"):
        check_game_counts({DAY: dup}, {DAY: 10}, [DAY], 0.10)


def test_games_fetched_on_a_day_with_no_schedule_fail() -> None:
    with pytest.raises(AnomalyError, match="fetched 2, scheduled 0"):
        check_game_counts({DAY: games("g", 2)}, {}, [DAY], 0.10)


def test_scheduled_day_with_nothing_fetched_fails() -> None:
    with pytest.raises(AnomalyError, match="fetched 0, scheduled 5"):
        check_game_counts({}, {DAY: 5}, [DAY], 0.10)


def test_every_bad_day_is_reported_in_one_error() -> None:
    d1, d2 = date(2026, 4, 10), date(2026, 4, 11)
    with pytest.raises(AnomalyError) as exc:
        check_game_counts(
            {d1: games("g", 5), d2: games("h", 8)},
            {d1: 10, d2: 8},
            [d1, d2],
            0.10,
        )
    msg = str(exc.value)
    assert "2026-04-10: fetched 5, scheduled 10" in msg
    assert "2026-04-11" not in msg  # d2 is exactly on schedule


# ---- end to end through nightly(): real fetch, schedule parse and check -----------------------

Transport = Callable[[str, Mapping[str, Any], float], dict[str, Any]]


def make_transport(fetched: Mapping[str, int], scheduled: Mapping[str, int]) -> Transport:
    """Fake stats.nba.com. ``fetched``/``scheduled`` map 'YYYY-MM-DD' to a game count."""

    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        if ep == "leaguegamelog":
            rows: list[list[Any]] = []
            if params.get("SeasonType") == "Regular Season":
                for day, n in fetched.items():
                    for i in range(n):
                        gid = f"0022501{i:03d}{day[-2:]}"
                        rows.append(["22025", TEAMS[0], 201, gid, day, 1])
                        rows.append(["22025", TEAMS[1], 202, gid, day, 1])
            headers = ["SEASON_ID", "TEAM_ID", "PLAYER_ID", "GAME_ID", "GAME_DATE", "PTS"]
            return {"resultSets": [{"name": "LeagueGameLog", "headers": headers, "rowSet": rows}]}
        if ep == "scheduleleaguev2":
            day_games = []
            for day, n in scheduled.items():
                mm, dd, yyyy = day[5:7], day[8:10], day[:4]
                day_games.append(
                    {
                        "gameDate": f"{mm}/{dd}/{yyyy} 00:00:00",
                        "games": [
                            {"gameId": f"0022501{i:03d}{day[-2:]}", "gameStatus": 3}
                            for i in range(n)
                        ],
                    }
                )
            return {"leagueSchedule": {"gameDates": day_games}}
        if ep == "commonallplayers":
            return {
                "resultSets": [
                    {"name": "CommonAllPlayers", "headers": ["PERSON_ID"], "rowSet": [[201], [202]]}
                ]
            }
        return {"resultSets": []}

    return transport


@pytest.fixture()
def nightly_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[Mapping[str, int], Mapping[str, int]], list[str]]]:
    base = load_sources()
    cfg: SourcesConfig = base.model_copy(
        update={
            "paths": base.paths.model_copy(
                update={"raw": tmp_path / "raw", "logs": tmp_path / "logs"}
            )
        }
    )
    events: list[str] = []

    def run(fetched: Mapping[str, int], scheduled: Mapping[str, int]) -> list[str]:
        events.clear()
        transport = make_transport(fetched, scheduled)

        def client(c: Any, *a: Any, **k: Any) -> NbaClient:
            return NbaClient(c, transport=transport, sleep=lambda s: None, check_version=False)

        def build(cfg_: Any, **kw: Any) -> SimpleNamespace:
            events.append("build")
            return SimpleNamespace(
                snapshot_id="nba_20260413",
                manifest={"as_of_date": "2026-04-13", "latest_game_date": "2026-04-12"},
            )

        def publish(cfg_: Any, s: Any) -> None:
            events.append("publish")

        # Contract validation is covered by test_contracts.py; these fake bodies carry only the
        # columns the check reads, so the contract is bypassed here on purpose.
        monkeypatch.setattr(refresh, "validate", lambda key, body: None)
        monkeypatch.setattr(refresh, "sources", lambda: cfg)
        monkeypatch.setattr(refresh, "NbaClient", client)
        monkeypatch.setattr(snapshots, "build", build)
        monkeypatch.setattr(snapshots, "publish", publish)
        return events

    yield run


def test_e2e_short_day_stops_before_build_and_publish(nightly_env: Any) -> None:
    # 2026-04-10 is in the 7-day window ending 2026-04-12; NBA.com returned 6 of 10 games.
    events = nightly_env({"2026-04-10": 3}, {"2026-04-10": 5, "2026-04-11": 0})
    with pytest.raises(AnomalyError, match="2026-04-10: fetched 3, scheduled 5"):
        refresh.nightly(date(2026, 4, 13))
    assert events == []  # no build, no publish: yesterday's snapshot stays live


def test_e2e_day_at_the_tolerance_edge_reaches_publish(nightly_env: Any) -> None:
    events = nightly_env({"2026-04-10": 9}, {"2026-04-10": 10})  # exactly -10%
    snap = refresh.nightly(date(2026, 4, 13))
    assert events == ["build", "publish"]
    assert snap.snapshot_id == "nba_20260413"


def test_e2e_day_just_past_the_edge_stops(nightly_env: Any) -> None:
    events = nightly_env({"2026-04-10": 8}, {"2026-04-10": 10})  # -20%
    with pytest.raises(AnomalyError):
        refresh.nightly(date(2026, 4, 13))
    assert events == []


def test_e2e_missing_day_is_caught_even_when_others_match(nightly_env: Any) -> None:
    # Two scheduled days; the one NBA.com returned nothing for must stop the run.
    events = nightly_env({"2026-04-11": 4}, {"2026-04-10": 6, "2026-04-11": 4})
    with pytest.raises(AnomalyError, match="2026-04-10: fetched 0, scheduled 6"):
        refresh.nightly(date(2026, 4, 13))
    assert events == []
