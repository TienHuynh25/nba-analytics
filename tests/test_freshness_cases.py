import re
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

ALLOW = {
    ln.strip()
    for ln in Path("transform/semantic_allowlist.txt").read_text().splitlines()
    if ln.strip() and not ln.startswith("#")
}
DOC = yaml.safe_load(Path("eval/freshness.yaml").read_text())


def test_ten_cases_each_one_select_on_semantic_views() -> None:
    cases = DOC["cases"]
    assert len(cases) == 10 and len({c["id"] for c in cases}) == 10
    for c in cases:
        sql = re.sub(r"\{\w+\}", "2026-04-13", c["sql"])
        tree = sqlglot.parse_one(sql, read="duckdb")
        assert isinstance(tree, exp.Select), c["id"]
        tables = {f"{t.db}.{t.name}" for t in tree.find_all(exp.Table)}
        assert tables and tables <= ALLOW, (c["id"], tables - ALLOW)


def test_checks_run_on_fixture(fixture_db_path: Path) -> None:
    import duckdb

    con = duckdb.connect(str(fixture_db_path), read_only=True)
    latest = con.execute("select max(game_date) from semantic.games").fetchone()[0]  # type: ignore[index]
    for c in DOC["cases"]:
        sql = c["sql"].format(as_of_date=latest, latest_game_date=latest, season="2024-25")
        con.execute(sql).fetchone()  # executes without error
    con.close()
