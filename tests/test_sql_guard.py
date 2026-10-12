"""SQL-fallback parser guardrails (task 3.16 done-when, parser half)."""

from pathlib import Path

import duckdb
import pytest

from app.sql_guard import GuardError, check


@pytest.mark.parametrize(
    "sql",
    [
        "drop table marts.games",
        "create table x as select 1",
        "insert into semantic.games values (1)",
        "update marts.players set name = 'x'",
        "delete from marts.games",
        "select * from marts.player_season",  # mart, not semantic
        "select * from staging.stg_team_game",  # staging
        "select * from landing.leaguegamelog_p__leaguegamelog",
        "select * from read_csv('data/raw/x.csv')",
        "select * from read_parquet('data/snapshots/x/shots/*/*.parquet')",
        "select * from 'data/raw/x.json'",
        "select * from read_json_auto('x.json')",
        "attach 'other.duckdb' as o",
        "copy semantic.games to 'out.csv'",
        "pragma database_list",
        "set threads = 1",
        "select 1; select 2",
        "select * from semantic.games; drop table x",
        "with t as (select * from marts.games) select * from t",
        "select * from other_db.semantic.games",
        "select * from glob('*')",
    ],
)
def test_rejected(sql: str) -> None:
    with pytest.raises(GuardError):
        check(sql)


def test_allowed_select_gets_limit() -> None:
    out = check(
        "select player_name, points_per_game from semantic.player_season_stats "
        "where season = '2025-26' order by points_per_game desc"
    )
    assert out.rstrip().upper().endswith("LIMIT 100")


def test_large_limit_is_lowered_and_small_kept() -> None:
    assert check("select * from semantic.games limit 5000").upper().endswith("LIMIT 100")
    assert check("select * from semantic.games limit 3").upper().endswith("LIMIT 3")


def test_ctes_and_unions_on_semantic_views() -> None:
    sql = (
        "with w as (select team_id, wins from semantic.team_season_stats) "
        "select * from w join semantic.teams t using (team_id)"
    )
    assert "LIMIT 100" in check(sql).upper()
    assert (
        "LIMIT 100"
        in check("select 1 as x from semantic.games union all select 2 from semantic.teams").upper()
    )


def test_error_names_the_allowed_views_for_repair() -> None:
    with pytest.raises(GuardError, match=r"semantic\.player_season_stats"):
        check("select * from marts.player_season")


_SET_OPS = ["UNION", "UNION ALL", "INTERSECT", "EXCEPT"]
_A = "SELECT player_id FROM semantic.players"


@pytest.mark.parametrize("op", _SET_OPS)
def test_set_operation_gets_valid_limit(op: str, fixture_db_path: Path) -> None:
    out = check(f"{_A} {op} {_A}")
    assert out.endswith("LIMIT 100") and "SELECT * FROM" not in out
    _run(out, fixture_db_path)


@pytest.mark.parametrize("op", _SET_OPS)
def test_set_operation_limit_is_capped(op: str, fixture_db_path: Path) -> None:
    assert check(f"{_A} {op} {_A} LIMIT 5").endswith("LIMIT 5")
    out = check(f"{_A} {op} {_A} LIMIT 5000")
    assert out.endswith("LIMIT 100") and "5000" not in out
    assert len(_run(out, fixture_db_path)) <= 100


def test_cte_with_union_gets_limit(fixture_db_path: Path) -> None:
    out = check(f"WITH t AS ({_A}) SELECT player_id FROM t UNION ALL SELECT player_id FROM t")
    assert out.startswith("WITH t AS") and out.endswith("LIMIT 100")
    assert len(_run(out, fixture_db_path)) == 100


def test_chained_set_operations_and_inner_limit(fixture_db_path: Path) -> None:
    out = check(f"{_A} UNION ALL {_A} EXCEPT ({_A} LIMIT 500)")
    assert out.endswith("LIMIT 100")
    _run(out, fixture_db_path)


def _run(sql: str, db: Path) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.mark.parametrize(
    "sql",
    [
        f"{_A} UNION SELECT game_id FROM marts.games",
        f"SELECT game_id FROM marts.games UNION ALL {_A}",
        f"{_A} INTERSECT SELECT x FROM staging.stg_team_game",
        f"{_A} EXCEPT SELECT * FROM read_csv('x.csv')",
        f"{_A} UNION ALL SELECT * FROM 'x.json'",
        f"WITH t AS ({_A}) SELECT * FROM t UNION SELECT * FROM marts.players",
        f"{_A} UNION ALL {_A}; DROP TABLE x",
        f"{_A} UNION ALL {_A}; SELECT 1",
        f"{_A} UNION ALL SELECT repeat('x', 4000000000)",
        "ATTACH 'o.duckdb'",
        "COPY (SELECT 1 UNION SELECT 2) TO 'o.csv'",
        "PRAGMA database_list",
        "SET threads = 1",
        f"({_A} UNION {_A})",
    ],
)
def test_set_operation_rejections_unchanged(sql: str) -> None:
    with pytest.raises(GuardError):
        check(sql)


# --- T-SEC1: SEC-001 (CTE scoping), SEC-002 (LIMIT forms), SEC-005 (parse errors, size) ---

_LOG = "SELECT player_id FROM semantic.player_game_log"  # 28k rows in the fixture


@pytest.mark.parametrize(
    "sql",
    [
        # The review's exploit: a CTE declared in a nested subquery made the outer name pass.
        "SELECT name, sql FROM (WITH sqlite_master AS (SELECT 1) SELECT 1) q, sqlite_master",
        "SELECT * FROM (WITH duckdb_tables AS (SELECT 1) SELECT 1) q, duckdb_tables",
        "SELECT * FROM (WITH duckdb_databases AS (SELECT 1) SELECT 1) q, duckdb_databases",
        "SELECT * FROM (WITH pg_settings AS (SELECT 1) SELECT 1) q, pg_settings",
        f"{_A} WHERE EXISTS (WITH duckdb_tables AS (SELECT 1) SELECT 1) "
        "AND player_id IN (SELECT 1 FROM duckdb_tables)",
        "SELECT 1 AS x FROM duckdb_settings UNION ALL "
        "(WITH duckdb_settings AS (SELECT 1) SELECT 1 FROM duckdb_settings)",
        # A CTE's own name inside its body, or a later CTE's name, binds to the catalog table.
        "WITH sqlite_master AS (SELECT * FROM sqlite_master) SELECT * FROM sqlite_master",
        "WITH a AS (SELECT * FROM duckdb_tables), duckdb_tables AS (SELECT 1) SELECT * FROM a",
        "WITH RECURSIVE sqlite_master AS (SELECT count(*) AS n FROM sqlite_master "
        "UNION ALL SELECT n + 1 FROM sqlite_master WHERE n < 3) SELECT * FROM sqlite_master",
        "WITH RECURSIVE a AS (SELECT count(*) AS n FROM duckdb_tables), "
        "duckdb_tables AS (SELECT 1 AS x) SELECT * FROM a",
    ],
)
def test_cte_name_outside_its_scope_is_rejected(sql: str) -> None:
    with pytest.raises(GuardError, match="not a semantic-layer view"):
        check(sql)


@pytest.mark.parametrize(
    "sql",
    [
        f"WITH a AS ({_A}), b AS (SELECT player_id FROM a) SELECT * FROM b",
        f"WITH a AS ({_A}) SELECT * FROM (SELECT player_id FROM a) q",
        f"WITH a AS ({_A}) SELECT * FROM semantic.players WHERE player_id IN (SELECT * FROM a)",
        f"WITH a AS ({_A}), b AS (SELECT * FROM (SELECT player_id FROM a) q) SELECT * FROM b",
        f"SELECT * FROM (WITH a AS ({_A}) SELECT player_id FROM a) q",
        f"WITH a AS ({_A}) SELECT * FROM (WITH b AS (SELECT * FROM a) SELECT * FROM b) q",
        f"WITH a AS ({_A}) SELECT player_id FROM a UNION SELECT player_id FROM a",
    ],
)
def test_cte_in_scope_still_accepted(sql: str, fixture_db_path: Path) -> None:
    out = check(sql)
    assert out.endswith("LIMIT 100")
    assert 0 < len(_run(out, fixture_db_path)) <= 100


@pytest.mark.parametrize(
    "limit",
    [
        "100%",
        "100 PERCENT",
        "50 + 50000",
        "$1",
        "?",
        "(SELECT 100000)",
        "99.9",
        "1e5",
        "-1",
        "101",
        "5 WITH TIES",
    ],
)
def test_non_plain_limit_becomes_100(limit: str, fixture_db_path: Path) -> None:
    sql = f"{_LOG} ORDER BY player_id LIMIT {limit}" if "TIES" in limit else f"{_LOG} LIMIT {limit}"
    out = check(sql)
    assert out.endswith(f"{_LOG} LIMIT 100") or out.endswith("ORDER BY player_id LIMIT 100")
    assert len(_run(out, fixture_db_path)) == 100


def test_fetch_first_and_offset(fixture_db_path: Path) -> None:
    assert check(f"{_LOG} FETCH FIRST 100000 ROWS ONLY").endswith("LIMIT 100")
    out = check(f"{_LOG} LIMIT 100% OFFSET 10")
    assert out.endswith("LIMIT 100 OFFSET 10") and len(_run(out, fixture_db_path)) == 100


@pytest.mark.parametrize("n", ["0", "1", "7", "100"])
def test_plain_limit_up_to_100_is_kept(n: str) -> None:
    assert check(f"{_LOG} LIMIT {n}").endswith(f"LIMIT {n}")


def test_set_operation_percent_limit_is_capped(fixture_db_path: Path) -> None:
    out = check(f"{_LOG} UNION ALL {_LOG} LIMIT 100 PERCENT")
    assert out.endswith("LIMIT 100") and "PERCENT" not in out
    assert len(_run(out, fixture_db_path)) == 100


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT " + "(" * 800 + "1" + ")" * 800 + " FROM semantic.players",
        f"{_A} WHERE " + "NOT " * 900 + "TRUE",
        "SELECT 'abc FROM semantic.players",
        'SELECT "abc FROM semantic.players',
        "SELECT $$x FROM semantic.players",
        "SELECT 1 FROM semantic.players WHERE",
    ],
)
def test_parse_failures_raise_guard_error(sql: str) -> None:
    with pytest.raises(GuardError):
        check(sql)


def test_sql_length_cap() -> None:
    from app.sql_guard import MAX_SQL_CHARS

    assert MAX_SQL_CHARS == 4000
    check(_A.ljust(MAX_SQL_CHARS))  # whitespace padding up to the cap is fine
    with pytest.raises(GuardError, match="at most 4000"):
        check(_A.ljust(MAX_SQL_CHARS + 1))


# T-QA3's 44 hostile queries (docs/pm/evidence/T-QA3.md, AC-4), kept as a regression set.
_QA3_HOSTILE = [
    f"{_A} UNION SELECT game_id FROM marts.games",
    f"SELECT game_id FROM marts.games UNION ALL {_A}",
    f"{_A} INTERSECT SELECT x FROM staging.stg_team_game",
    f"WITH t AS (SELECT * FROM marts.players) {_A} EXCEPT SELECT player_id FROM t",
    f"{_A} WHERE player_id IN (SELECT player_id FROM marts.player_season)",
    "SELECT (SELECT count(*) FROM marts.games) AS c FROM semantic.players",
    "SELECT * FROM landing.leaguegamelog_p__leaguegamelog UNION ALL " + _A,
    f"{_A} UNION SELECT * FROM read_csv('x.csv')",
    f"{_A} UNION ALL SELECT * FROM read_parquet('x.parquet')",
    f"{_A} UNION ALL SELECT * FROM 'x.json'",
    "ATTACH 'o.duckdb' AS o",
    "COPY (SELECT 1 UNION SELECT 2) TO 'o.csv'",
    "PRAGMA database_list",
    "SET threads=1",
    f"{_A} UNION {_A}; DROP TABLE x",
    f"{_A}; {_A}",
    f"{_A} /* ; */ UNION SELECT game_id FROM marts.games -- semantic.games",
    f"{_A} -- \n; DROP TABLE x",
    f"{_A} UNION ALL SELECT repeat('x', 4000000000)",
    "SELECT current_setting('threads') FROM semantic.players",
    "SELECT version()",
    "SELECT read_text('/etc/passwd')",
    f"{_A} EXCEPT SELECT range(100000000000)",
    "SELECT * FROM main.games",
    "SELECT * FROM nba.semantic.players",
    'SELECT * FROM "marts"."games" UNION ALL ' + _A,
    'SELECT * FROM "MARTS"."Games"',
    "SELECT * FROM MaRtS.GaMeS",
    'SELECT * FROM "semantic.players.x"',
    'SELECT * FROM "marts.games"',
    f"WITH t AS (SELECT * FROM glob('*')) {_A} UNION SELECT 1 FROM t",
    "SELECT * FROM semantic.players, LATERAL (SELECT * FROM marts.games)",
    f"({_A} UNION {_A})",
    "",
    "VALUES (1)",
    "DESCRIBE semantic.players",
    "SHOW TABLES",
    "EXPLAIN SELECT 1",
    "INSTALL httpfs",
    "CALL pragma_database_list()",
    "COPY semantic.players FROM 'x.csv'",
    f"CREATE VIEW v AS {_A} UNION {_A}",
    f"INSERT INTO semantic.players {_A} UNION {_A}",
    f"WITH t AS ({_A}) INSERT INTO x SELECT * FROM t",
]


def test_qa3_hostile_list_is_complete() -> None:
    assert len(_QA3_HOSTILE) == 44


@pytest.mark.parametrize("sql", _QA3_HOSTILE)
def test_qa3_hostile_still_rejected(sql: str) -> None:
    with pytest.raises(GuardError):
        check(sql)
