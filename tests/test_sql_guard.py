"""SQL-fallback parser guardrails (task 3.16 done-when, parser half)."""

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
