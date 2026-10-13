"""DEF-021: two dbt builds of the same landing data store the same rows in the same order.

Builds the one-season fixture landing twice into tmp files and compares, per table, an
order-sensitive hash (rows in storage order), plus the shots Parquet bytes. Skipped where the
fixture landing (data/build/fixture/landing.duckdb) is absent.
"""

import hashlib
from pathlib import Path

import duckdb
import pytest

from app.config import REPO_ROOT
from ingest.snapshots import run_dbt

pytestmark = pytest.mark.dbt
LANDING = REPO_ROOT / "data" / "build" / "fixture" / "landing.duckdb"


def fingerprint(db: Path, shots: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    con = duckdb.connect(str(db), read_only=True)
    try:
        tables = con.execute(
            "select schema_name, table_name from duckdb_tables() "
            "where database_name = current_database() order by 1, 2"
        ).fetchall()
        for s, t in tables:
            row = con.execute(
                f'select count(*), hash(list(hash(x) order by rowid))::varchar from "{s}"."{t}" x'
            ).fetchone()
            out[f"{s}.{t}"] = str(row)
    finally:
        con.close()
    for f in sorted(shots.rglob("*.parquet")):
        out[f"file:{f.relative_to(shots)}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


@pytest.mark.skipif(not LANDING.exists(), reason="fixture landing not built")
def test_two_builds_are_identical(tmp_path: Path) -> None:
    prints = []
    for i in (1, 2):
        d = tmp_path / f"b{i}"
        d.mkdir()
        run_dbt(d / "det.duckdb", d / "shots", LANDING, None, {"fixture": True})
        prints.append(fingerprint(d / "det.duckdb", d / "shots"))
    assert prints[0].keys() == prints[1].keys()
    assert any(k.startswith("marts.") for k in prints[0])
    diff = sorted(k for k in prints[0] if prints[0][k] != prints[1][k])
    assert diff == []
