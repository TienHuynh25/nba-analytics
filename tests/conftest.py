from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from ingest.fixture import ensure_fixture_db


@pytest.fixture(scope="session")
def fixture_db_path() -> Path:
    """tests/fixtures/nba_fixture.duckdb, rebuilt from the committed export when needed."""
    return ensure_fixture_db()


@pytest.fixture()
def fixture_db(fixture_db_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect(str(fixture_db_path), read_only=True)
    try:
        yield con
    finally:
        con.close()
