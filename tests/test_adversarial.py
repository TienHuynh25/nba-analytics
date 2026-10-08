# ruff: noqa: RUF001  (ambiguous unicode is the point of these cases)
"""Adversarial cases for the two safety gates: the numeric verifier and the SQL guard.

Invented inputs only (no held-out eval cases). Cases marked ``xfail(strict=True)`` are known
bugs reported to the developer; when the fix lands the strict xfail fails the run, which is the
signal to delete the marker.
"""

import resource
import time
from pathlib import Path

import pytest

from app.sql_fallback import QueryTimeout, locked_connection, run_with_timeout
from app.sql_guard import GuardError
from app.sql_guard import check as guard
from app.verifier import Evidence, ResultValue, check
from metrics.schema import Rounding

EV = Evidence(
    values=[ResultValue(33.48, Rounding(decimals=1)), ResultValue(1234, Rounding(decimals=0))],
    args_text=["2025-26", "top 5"],
)


# --- verifier: forms that must be caught -------------------------------------------------


@pytest.mark.parametrize(
    "draft,bad",
    [
        ("He scored 47.6 percent of shots", "47.6"),
        ("He scored 1,235 points", "1,235"),
        ("He scored 33 and a half points", "33"),
        ("thirty-three point five points", "33"),
        ("That is 1/3 of games", "1"),
        ("He played in 2024-25", "2024-25"),
        ("On 2026-01-02 he scored 33.5", "2026-01-02"),
        ("Averaged -33.5", "-33.5"),
        ("33.5 vs 99.9", "99.9"),
        ("Scored 33.5 and 12 rebounds", "12"),
        ("(12)", "12"),
        ("#12 overall", "12"),
        ("$12", "12"),
        ("12–15 range", "12"),
    ],
)
def test_wrong_numbers_in_unusual_forms_are_caught(draft: str, bad: str) -> None:
    assert bad in check(draft, EV).unmatched


@pytest.mark.parametrize(
    "draft",
    [
        "He averaged 33.5 points in 2025-26.",
        "He scored 1,234 points and 1234 is the total.",
        "Top 5 in 2025-26 with 33.5.",
    ],
)
def test_correct_numbers_in_unusual_forms_pass(draft: str) -> None:
    assert check(draft, EV).ok


# --- verifier: known bypasses (BUG 1 and BUG 2 reported to the developer) -------------------


@pytest.mark.parametrize(
    "draft", ["99pts", "He had 99pts and 12reb", "99ppg", "99k points", "99th career game"]
)
def test_numbers_glued_to_letters_are_still_checked(draft: str) -> None:
    assert not check(draft, EV).ok


@pytest.mark.parametrize("draft", ["99½ points", "99²"])
def test_unicode_fractions_are_not_a_bypass(draft: str) -> None:
    assert not check(draft, EV).ok


@pytest.mark.parametrize(
    "draft",
    ["about a dozen games", "a hundred points", "a hundred and five points", "33.5 million"],
)
def test_quantity_words_are_not_a_bypass(draft: str) -> None:
    assert not check(draft, EV).ok


# --- sql_guard ---------------------------------------------------------------------------

V = "semantic.player_season_stats"
ALLOWED = frozenset({V, "semantic.players"})


@pytest.mark.parametrize(
    "sql",
    [
        f"select * from {V}; select 1",
        f"select * from {V} where x in (select * from read_csv('/etc/passwd'))",
        "select read_text('/etc/passwd')",
        f"select * from {V}, '/etc/passwd'",
        f"select * from {V} t join (select * from 'a.json') u on 1=1",
        "with a as (select * from raw.games) select * from a",
        f"select * from main.{V}",
        "select * from duckdb_tables()",
        "select * from information_schema.tables",
        "select * from pragma_database_list()",
        "select * from glob('*')",
        "select * from query_table('raw_games')",
        "select * from parquet_scan('x')",
        "select * from sqlite_scan('x', 'y')",
        "install httpfs",
        "load httpfs",
        "call pragma_version()",
        "explain select 1",
        "summarize " + V,
        "describe " + V,
        "show tables",
        f"insert into {V} values (1)",
        f"create table t as select * from {V}",
        f"copy {V} to '/tmp/x.csv'",
        "attach '/tmp/x.duckdb' as x",
        "pragma enable_external_access",
        "set enable_external_access=true",
        "",
        "   ",
    ],
)
def test_guard_rejects(sql: str) -> None:
    with pytest.raises(GuardError):
        guard(sql, ALLOWED)


@pytest.mark.parametrize(
    "sql,tail",
    [
        (f"select * from {V} limit 100000", "LIMIT 100"),
        (f"select * from {V} limit all", "LIMIT 100"),
        (f"select * from {V} fetch first 500 rows only", "LIMIT 100"),
        (f"select * from {V}", "LIMIT 100"),
        (f"select * from {V} limit 5", "LIMIT 5"),
        (f"select * from {V.upper()}", "LIMIT 100"),
        (f"select * from {V} where 1=1 -- ; drop table x", "LIMIT 100"),
    ],
)
def test_guard_accepts_and_bounds_rows(sql: str, tail: str) -> None:
    assert guard(sql, ALLOWED).rstrip().endswith(tail)


def test_guard_comment_cannot_hide_a_second_statement() -> None:
    out = guard(f"select * from {V} /* ; drop table x */", ALLOWED)
    assert ";" not in out.replace("/* ; drop table x */", "")


@pytest.mark.parametrize(
    "sql",
    [
        "select repeat('x', 4000000000)",
        "select lpad('x', 4000000000, 'y')",
        "select unnest(range(100000000000))",
        "select current_setting('allowed_directories')",
        "select version()",
        "select getenv('HOME')",
        "select sleep_ms(100000)",
        f"select string_agg('x', '') from {V}",
    ],
)
def test_guard_rejects_allocators_and_environment_functions(sql: str) -> None:
    """BUG 3 resolution: DuckDB's memory_limit does not bound scalar allocation, so the guard's
    function allowlist is the control."""
    with pytest.raises(GuardError):
        guard(sql, ALLOWED)


def test_expensive_allowed_query_is_stopped_by_the_watchdog(fixture_db_path: Path) -> None:
    con = locked_connection(fixture_db_path, None)
    sql = guard(
        "select count(*) from semantic.player_game_log a, semantic.player_game_log b, "
        "semantic.player_game_log c",
        frozenset({"semantic.player_game_log"}),
    )
    t = time.monotonic()
    with pytest.raises(QueryTimeout):
        run_with_timeout(con, sql, 2.0)
    assert time.monotonic() - t < 6
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 2.5 * 2**30


def test_fullwidth_digits_are_normalised() -> None:
    assert check("\uff11\uff12\uff13\uff14 points", EV).ok


def test_only_the_guarded_fallback_runs_model_sql() -> None:
    """The guard is the control for scalar allocation, so no app code may run SQL without it."""
    root = Path(__file__).resolve().parent.parent / "app"
    callers = [
        p.relative_to(root.parent).as_posix()
        for p in root.rglob("*.py")
        if "run_with_timeout(" in p.read_text() and "def run_with_timeout" not in p.read_text()
    ]
    assert callers == ["app/sql_fallback.py"] or callers == []
    text = (root / "sql_fallback.py").read_text()
    assert text.index("check(sql)") < text.index("run_with_timeout(self.con, safe)")
