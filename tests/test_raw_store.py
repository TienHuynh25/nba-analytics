from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from app.config import load_sources
from ingest.client import NbaClient
from ingest.endpoints import SPECS
from ingest.raw_store import RawStore


def client_counting(calls: list[str]) -> NbaClient:
    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        calls.append(ep)
        return {"resultSets": [{"name": "LeagueGameLog", "headers": [], "rowSet": []}]}

    return NbaClient(load_sources().nba_api, transport=transport, sleep=lambda s: None)


def test_warm_cache_makes_zero_api_calls(tmp_path: Path) -> None:
    spec = SPECS["leaguegamelog_t"]
    seasons = ["2023-24", "2024-25"]
    calls: list[str] = []
    store = RawStore(tmp_path, client_counting(calls))
    for s in seasons:
        store.get(spec, s, season=s)
    assert len(calls) == 2

    calls2: list[str] = []
    store2 = RawStore(tmp_path, client_counting(calls2))
    for s in seasons:
        rec = store2.get(spec, s, season=s)
        assert rec.params["Season"] == s
    assert calls2 == []


def test_refresh_writes_new_file_and_never_overwrites(tmp_path: Path) -> None:
    spec = SPECS["leaguegamelog_t"]
    calls: list[str] = []
    store = RawStore(tmp_path, client_counting(calls))
    first = store.get(spec, "2024-25", season="2024-25")
    second = store.get(spec, "2024-25", refresh=True, season="2024-25")
    assert first.path != second.path
    assert first.path.exists() and second.path.exists()
    assert store.latest(spec, "2024-25", first.params) == second.path


def test_offline_miss_raises(tmp_path: Path) -> None:
    with pytest.raises(LookupError):
        RawStore(tmp_path, None).get(SPECS["leaguegamelog_t"], "2024-25", season="2024-25")


def test_no_endpoint_takes_a_date_based_season_default() -> None:
    import pytest as _pytest

    with _pytest.raises(ValueError, match="pass Season explicitly"):
        SPECS["commonallplayers"].params()
    assert SPECS["commonallplayers"].params(season="2025-26")["Season"] == "2025-26"
    for key in ("playercareerstats", "playerawards", "commonplayerinfo"):
        SPECS[key].params(player_id=2544)  # no season involved: no error
