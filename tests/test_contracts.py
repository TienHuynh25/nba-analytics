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


# --- DEF-015: exact headers, row width and cell types, including varying-header endpoints ------

# Endpoints whose headers legitimately vary between responses; their schemas list each variant.
VARYING = ["commonplayerinfo", "leaguestandingsv3"]


def _variants(key: str) -> list[dict[str, Any]]:
    schema = json.loads((SCHEMA_DIR / f"{key}.json").read_text())
    name = SPECS[key].result_sets[0]
    for part in schema["properties"]["resultSets"]["allOf"]:
        item = part["contains"]
        if item["properties"]["name"]["const"] == name:
            variants: list[dict[str, Any]] = [
                v["properties"] for v in item.get("anyOf", [item["properties"]])
            ]
            return variants
    raise AssertionError(f"{key}: no schema entry for {name}")


@pytest.mark.parametrize("key", VARYING)
def test_varying_endpoint_lists_exact_variants(key: str) -> None:
    variants = _variants(key)
    assert len(variants) >= 2
    for v in variants:
        n = len(v["headers"]["const"])
        items = v["rowSet"]["items"]
        assert items["minItems"] == items["maxItems"] == len(items["prefixItems"]) == n


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_cell_type_change_fails(key: str) -> None:
    body = copy.deepcopy(sample(key))
    rs = _first_set(body, key)
    row = rs["rowSet"][0]
    i = next(i for i, v in enumerate(row) if v is not None)
    row[i] = 12345 if isinstance(row[i], str) else str(row[i])  # e.g. PERSON_ID 2544 -> "2544"
    with pytest.raises(ContractError):
        validate(key, body)


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_swapped_headers_fail(key: str) -> None:
    body = copy.deepcopy(sample(key))
    h = _first_set(body, key)["headers"]
    h[0], h[1] = h[1], h[0]
    with pytest.raises(ContractError):
        validate(key, body)


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_extra_column_fails(key: str) -> None:
    body = copy.deepcopy(sample(key))
    rs = _first_set(body, key)
    rs["headers"].append("EXTRA_COL")
    for row in rs["rowSet"]:
        row.append(0)
    with pytest.raises(ContractError):
        validate(key, body)


@pytest.mark.parametrize("key", RESULT_SET_KEYS)
def test_short_row_fails(key: str) -> None:
    body = copy.deepcopy(sample(key))
    _first_set(body, key)["rowSet"][0].pop()
    with pytest.raises(ContractError):
        validate(key, body)


@pytest.mark.parametrize("key", VARYING)
def test_headers_of_one_variant_with_rows_of_another_fail(key: str) -> None:
    body = copy.deepcopy(sample(key))
    rs = _first_set(body, key)
    other = next(v for v in _variants(key) if v["headers"]["const"] != rs["headers"])
    rs["headers"] = list(other["headers"]["const"])  # known header list, rows the wrong width
    with pytest.raises(ContractError):
        validate(key, body)
