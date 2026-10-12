import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ingest.contracts import SCHEMA_DIR, ContractError, validate
from ingest.endpoints import SPECS

SAMPLES = Path(__file__).parent / "fixtures" / "raw_samples"
KEYS = sorted(p.stem for p in SCHEMA_DIR.glob("*.json"))


def sample(key: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((SAMPLES / f"{key}.json").read_text())
    return body


def test_every_endpoint_has_schema_and_sample() -> None:
    assert set(KEYS) == set(SPECS)
    for key in KEYS:
        assert (SAMPLES / f"{key}.json").exists()


@pytest.mark.parametrize("key", KEYS)
def test_real_sample_passes(key: str) -> None:
    validate(key, sample(key))


def _first_set(body: dict[str, Any], key: str) -> dict[str, Any]:
    name = SPECS[key].result_sets[0]
    rs: dict[str, Any] = next(r for r in body["resultSets"] if r["name"] == name)
    return rs


RESULT_SET_KEYS = [k for k in KEYS if SPECS[k].result_sets]


def test_schedule_without_game_ids_fails() -> None:
    body = copy.deepcopy(sample("scheduleleaguev2"))
    del body["leagueSchedule"]["gameDates"][0]["games"][0]["gameId"]
    with pytest.raises(ContractError):
        validate("scheduleleaguev2", body)


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_renamed_field_fails(key: str) -> None:
    body = copy.deepcopy(sample(key))
    rs = _first_set(body, key)
    rs["headers"][0] = rs["headers"][0] + "_RENAMED"
    with pytest.raises(ContractError):
        validate(key, body)


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_missing_column_fails(key: str) -> None:
    body = copy.deepcopy(sample(key))
    rs = _first_set(body, key)
    del rs["headers"][1]
    for row in rs["rowSet"]:
        del row[1]
    if not rs["rowSet"]:
        pytest.skip("sample has no rows")
    with pytest.raises(ContractError):
        validate(key, body)


def test_missing_result_set_fails() -> None:
    body = sample("playercareerstats")
    kept = [r for r in body["resultSets"] if r["name"] != "CareerTotalsRegularSeason"]
    body = {"resultSets": kept}
    with pytest.raises(ContractError):
        validate("playercareerstats", body)


def test_null_key_column_fails() -> None:
    body = copy.deepcopy(sample("leaguegamelog_p"))
    rs = _first_set(body, "leaguegamelog_p")
    rs["rowSet"][0][rs["headers"].index("GAME_ID")] = None
    with pytest.raises(ContractError):
        validate("leaguegamelog_p", body)
