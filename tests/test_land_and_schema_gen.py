"""Landing (task 1.9) and contract-schema generation (task 1.4) on small synthetic caches.

``land`` is the memory-sensitive step between raw JSON and dbt: it must keep every fetch (staging
picks the latest), write only text, never lose or reorder cells, and always create every table
so dbt sources resolve even before the first backfill stage has run.
"""

import copy
import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from ingest import land
from ingest.contracts import ContractError, generate_schema
from ingest.endpoints import SPECS

KEY = "commonallplayers"
RS = "CommonAllPlayers"
HEADERS = ["PERSON_ID", "DISPLAY_FIRST_LAST", "ROSTERSTATUS", "NOTE"]


def write_raw(
    root: Path,
    fetch_date: str,
    fetched_at: str,
    rows: list[list[Any]],
    name: str = RS,
    **extra: Any,
) -> Path:
    d = root / KEY / "_all" / fetch_date
    d.mkdir(parents=True, exist_ok=True)
    doc = {
        "key": KEY,
        "season": "_all",
        "params": {"is_only_current_season": 0},
        "fetched_at": fetched_at,
        "response": {"resultSets": [{"name": name, "headers": HEADERS, "rowSet": rows}], **extra},
    }
    p = d / f"abc.{fetched_at}.json"
    p.write_text(json.dumps(doc))
    return p


def landed(tmp: Path, **kw: Any) -> tuple[dict[str, int], duckdb.DuckDBPyConnection]:
    counts = land.land(tmp / "raw", tmp / "landing.duckdb", tmp / "work", [KEY], **kw)
    return counts, duckdb.connect(str(tmp / "landing.duckdb"), read_only=True)


def test_every_cell_lands_as_text_with_provenance(tmp_path: Path) -> None:
    write_raw(
        tmp_path / "raw",
        "2026-10-01",
        "2026-10-01T05:00:00+00:00",
        [[2544, "LeBron James", 1, None], [1.0, "A B", True, "x"]],
    )
    counts, con = landed(tmp_path)
    assert counts == {"commonallplayers__commonallplayers": 2}
    cols = {
        r[0]: r[1] for r in con.execute("describe commonallplayers__commonallplayers").fetchall()
    }
    assert set(cols.values()) == {"VARCHAR"}
    assert set(land.META) <= set(cols)
    rows = con.execute(
        "select PERSON_ID, ROSTERSTATUS, NOTE, _key, _partition, _fetched_at, _params, _file "
        "from commonallplayers__commonallplayers order by PERSON_ID desc"
    ).fetchall()
    assert rows[0][:3] == ("2544", "1", None)  # NULL stays NULL, never the string 'None'
    assert rows[1][:3] == ("1", "true", "x")  # float 1.0 -> '1', bool -> 'true'
    assert rows[0][3:7] == (
        "commonallplayers",
        "_all",
        "2026-10-01T05:00:00+00:00",
        '{"is_only_current_season": 0}',
    )
    assert rows[0][7].startswith("commonallplayers/_all/2026-10-01/")  # relative to raw root


def test_every_fetch_is_kept_so_staging_can_pick_the_latest(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_raw(raw, "2026-10-01", "2026-10-01T05:00:00+00:00", [[1, "Old Name", 1, None]])
    write_raw(raw, "2026-10-02", "2026-10-02T05:00:00+00:00", [[1, "New Name", 1, None]])
    counts, con = landed(tmp_path)
    assert counts["commonallplayers__commonallplayers"] == 2
    latest = con.execute(
        "select DISPLAY_FIRST_LAST from commonallplayers__commonallplayers "
        "order by _fetched_at desc limit 1"
    ).fetchone()
    assert latest == ("New Name",)


def test_unlisted_result_sets_are_skipped(tmp_path: Path) -> None:
    write_raw(
        tmp_path / "raw",
        "2026-10-01",
        "2026-10-01T05:00:00+00:00",
        [[1, "A", 1, None]],
        name="Surprise",
    )
    counts, _ = landed(tmp_path)
    assert counts["commonallplayers__commonallplayers"] == 0


def test_all_tables_exist_even_with_no_raw_files(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    land.land(tmp_path / "raw", tmp_path / "landing.duckdb", tmp_path / "work")  # all keys
    con = duckdb.connect(str(tmp_path / "landing.duckdb"), read_only=True)
    have = {
        r[0] for r in con.execute("select table_name from information_schema.tables").fetchall()
    }
    want = {land.table_name(k, rs) for k, s in SPECS.items() for rs in s.result_sets}
    assert want <= have
    for t in want:
        assert con.execute(f'select count(*) from "{t}"').fetchone() == (0,)


def test_keep_filter_selects_files(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    write_raw(raw, "2026-10-01", "2026-10-01T05:00:00+00:00", [[1, "A", 1, None]])
    write_raw(raw, "2026-10-02", "2026-10-02T05:00:00+00:00", [[2, "B", 1, None]])
    counts, _ = landed(tmp_path, keep=lambda key, path, doc: "2026-10-02" in str(path))
    assert counts["commonallplayers__commonallplayers"] == 1


def test_rebuild_is_idempotent_and_cleans_work_files(tmp_path: Path) -> None:
    write_raw(tmp_path / "raw", "2026-10-01", "2026-10-01T05:00:00+00:00", [[1, "A", 1, None]])
    first, _ = landed(tmp_path)
    second, con = landed(tmp_path)
    assert first == second
    assert con.execute("select count(*) from commonallplayers__commonallplayers").fetchone() == (1,)
    assert not list((tmp_path / "work").glob("*.ndjson"))
    assert not (tmp_path / "landing.building.duckdb").exists()


def test_ragged_row_fails_loudly_instead_of_shifting_cells(tmp_path: Path) -> None:
    write_raw(tmp_path / "raw", "2026-10-01", "2026-10-01T05:00:00+00:00", [[1, "A", 1]])  # 3 cells
    with pytest.raises(ValueError):
        land.land(tmp_path / "raw", tmp_path / "landing.duckdb", tmp_path / "work", [KEY])


def test_awkward_strings_survive_roundtrip(tmp_path: Path) -> None:
    nasty = ['O\'Neal, "Shaq"', "line\nbreak", "tab\there", "ß/日本", "", "NULL", "[1,2]"]
    write_raw(
        tmp_path / "raw",
        "2026-10-01",
        "2026-10-01T05:00:00+00:00",
        [[i, s, 1, None] for i, s in enumerate(nasty)],
    )
    _, con = landed(tmp_path)
    got = [
        r[0]
        for r in con.execute(
            "select DISPLAY_FIRST_LAST from commonallplayers__commonallplayers "
            "order by PERSON_ID::int"
        ).fetchall()
    ]
    assert got == nasty


# --- generate_schema -------------------------------------------------------------------------


def body(headers: list[str], rows: list[list[Any]], name: str = "T") -> dict[str, Any]:
    return {"resultSets": [{"name": name, "headers": headers, "rowSet": rows}]}


def test_generated_schema_accepts_its_samples_and_rejects_drift() -> None:
    from jsonschema import Draft202012Validator

    s = body(["GAME_ID", "PTS"], [["001", 10], ["002", None]])
    v = Draft202012Validator(generate_schema("t", [s], ["T"]))
    assert v.is_valid(s)
    renamed = body(["GAME_ID", "POINTS"], [["001", 10]])
    assert not v.is_valid(renamed)
    null_key = body(["GAME_ID", "PTS"], [[None, 10]])
    assert not v.is_valid(null_key)  # GAME_ID may never be null
    wrong_type = body(["GAME_ID", "PTS"], [["001", "ten"]])
    assert not v.is_valid(wrong_type)
    ragged = copy.deepcopy(s)
    ragged["resultSets"][0]["rowSet"][0].append(1)
    assert not v.is_valid(ragged)


def test_samples_with_a_varying_column_only_require_the_shared_ones() -> None:
    from jsonschema import Draft202012Validator

    a = body(["PERSON_ID", "EXTRA"], [[1, "x"]])
    b = body(["PERSON_ID"], [[2]])
    v = Draft202012Validator(generate_schema("t", [a, b], ["T"]))
    assert v.is_valid(a) and v.is_valid(b)
    assert not v.is_valid(body(["OTHER"], [[1]]))


def test_missing_result_set_in_samples_is_an_error() -> None:
    with pytest.raises(ContractError):
        generate_schema("t", [body(["A"], [[1]])], ["T", "Missing"])
