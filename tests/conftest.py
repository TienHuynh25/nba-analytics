import os
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


@pytest.fixture(autouse=True)
def _unseal_tmp_path(request: pytest.FixtureRequest) -> Iterator[None]:
    """Published snapshots are sealed (folders 0555, SEC-003); make a test's tmp_path folders
    writable again afterwards so pytest can always remove it."""
    yield
    tmp = request.node.funcargs.get("tmp_path")
    if isinstance(tmp, Path) and tmp.exists():
        for dirpath, _dirs, _files in os.walk(tmp):
            if not os.path.islink(dirpath):
                os.chmod(dirpath, 0o755)
