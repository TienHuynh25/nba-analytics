from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.config import load_sources
from ingest.client import NbaClient
from ingest.endpoints import SPECS
from ingest.incremental import (
    AnomalyError,
    check_game_counts,
    fetch_window,
    scheduled_games_by_day,
    season_for,
)
from ingest.raw_store import RawStore

LOG_H = ["SEASON_ID", "TEAM_ID", "PLAYER_ID", "GAME_ID", "GAME_DATE", "PTS"]


def fake_body(endpoint: str, params: Mapping[str, Any], pts: int) -> dict[str, Any]:
    if endpoint == "leaguegamelog":
        rows = []
        if params["SeasonType"] == "Regular Season":
            rows = [
                ["22025", 1610612738, 201, "0022501200", "2026-04-10", pts],
                ["22025", 1610612752, 202, "0022501200", "2026-04-10", 99],
            ]
        return {"resultSets": [{"name": "LeagueGameLog", "headers": LOG_H, "rowSet": rows}]}
    if endpoint == "commonallplayers":
        return {
            "resultSets": [
                {"name": "CommonAllPlayers", "headers": ["PERSON_ID"], "rowSet": [[201], [202]]}
            ]
        }
    return {"resultSets": []}


def store(tmp: Path, pts: int, calls: list[tuple[str, dict[str, Any]]]) -> RawStore:
    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        calls.append((ep, dict(params)))
        return fake_body(ep, params, pts)

    client = NbaClient(load_sources().nba_api, transport=transport, sleep=lambda s: None)
    return RawStore(tmp, client)


def test_window_refetch_writes_new_files_with_corrected_rows(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    first = fetch_window(store(tmp_path, 30, calls), date(2026, 4, 13), 7)
    assert first.season == "2025-26"
    assert first.window == (date(2026, 4, 6), date(2026, 4, 12))
    assert first.games_by_day == {date(2026, 4, 10): {"0022501200"}}
    assert first.players == {201, 202}
    windowed = [p for ep, p in calls if ep == "leaguegamelog"]
    assert windowed and all(p["DateFrom"] == "04/06/2026" for p in windowed)

    # Next night: the stat correction (30 -> 31 points) lands in a new raw file; the old one stays.
    s2 = store(tmp_path, 31, [])
    fetch_window(s2, date(2026, 4, 14), 7)
    spec = SPECS["leaguegamelog_t"]
    files = sorted((tmp_path / "leaguegamelog_t" / "2025-26").rglob("*.json"))
    assert len(files) >= 2
    latest = s2.get(
        spec,
        "2025-26",
        season="2025-26",
        season_type_all_star="Regular Season",
        date_from_nullable="04/07/2026",
        date_to_nullable="04/13/2026",
    )
    rows = latest.response["resultSets"][0]["rowSet"]
    assert rows[0][LOG_H.index("PTS")] == 31


def test_new_players_get_info_once(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    fetch_window(store(tmp_path, 30, calls), date(2026, 4, 13), 7)
    assert sum(ep == "commonplayerinfo" for ep, _ in calls) == 2
    calls2: list[tuple[str, dict[str, Any]]] = []
    fetch_window(store(tmp_path, 30, calls2), date(2026, 4, 14), 7)
    assert sum(ep == "commonplayerinfo" for ep, _ in calls2) == 0


def test_short_day_stops_the_run() -> None:
    days = [date(2026, 4, 10), date(2026, 4, 11)]
    expected = {days[0]: 10, days[1]: 8}
    fetched = {days[0]: [f"g{i}" for i in range(10)], days[1]: [f"h{i}" for i in range(6)]}
    with pytest.raises(AnomalyError, match="2026-04-11: fetched 6, scheduled 8"):
        check_game_counts(fetched, expected, days, 0.10)


def test_count_within_tolerance_passes() -> None:
    d = date(2026, 4, 10)
    check_game_counts({d: [f"g{i}" for i in range(10)]}, {d: 10}, [d], 0.10)
    check_game_counts({}, {}, [d], 0.10)  # off day


def test_unscheduled_games_fail() -> None:
    d = date(2026, 7, 4)
    with pytest.raises(AnomalyError):
        check_game_counts({d: ["x"]}, {}, [d], 0.10)


def test_schedule_parsing_counts_only_final_counted_games() -> None:
    body = {
        "leagueSchedule": {
            "gameDates": [
                {
                    "gameDate": "04/10/2026 00:00:00",
                    "games": [
                        {"gameId": "0022501200", "gameStatus": 3},
                        {"gameId": "0012500001", "gameStatus": 3},  # preseason: not counted
                        {"gameId": "0022501201", "gameStatus": 1},  # not final
                    ],
                },
            ]
        }
    }
    assert scheduled_games_by_day(body) == {date(2026, 4, 10): 1}


def test_season_for() -> None:
    assert season_for(date(2026, 4, 12)) == 2025
    assert season_for(date(2026, 6, 20)) == 2025
    assert season_for(date(2026, 10, 22)) == 2026
