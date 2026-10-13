"""Task 1.28 done-when: an as-of build holds no row after its cutoff, and its manifest's
as_of_date is the day after the cutoff game.

Builds from the one-season fixture's landing file (data/build/fixture/landing.duckdb, written by
``python -m ingest.fixture`` from the raw cache), so it is skipped where that file is absent.
"""

import datetime as dt
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.config import REPO_ROOT
from ingest.snapshots import BuildError, copy_published, run_dbt, write_manifest

pytestmark = pytest.mark.dbt
LANDING = REPO_ROOT / "data" / "build" / "fixture" / "landing.duckdb"
CUTOFF = dt.date(2025, 4, 13)  # last game of the 2024-25 regular season

needs_landing = pytest.mark.skipif(not LANDING.exists(), reason="fixture landing not built")


@pytest.fixture(scope="module")
def as_of_snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("asof") / "asof_test"
    d.mkdir()
    run_dbt(d / "asof_test.duckdb", d / "shots", LANDING, CUTOFF, {"fixture": True})
    return d


@needs_landing
def test_no_row_after_cutoff(as_of_snapshot: Path) -> None:
    con = duckdb.connect(str(as_of_snapshot / "asof_test.duckdb"), read_only=True)

    def q(sql: str) -> Any:
        row = con.execute(sql).fetchone()
        assert row is not None
        return row[0]

    assert q("select max(game_date) from marts.games") == CUTOFF
    assert q("select max(game_date) from marts.player_game") <= CUTOFF
    assert q("select count(*) from marts.shots where game_date > date '2025-04-13'") == 0
    for t in ("games", "player_game", "player_season", "player_season_stint", "team_season"):
        # Play-In and playoffs come after the cutoff; the December NBA Cup final does not.
        n = q(f"select count(*) from marts.{t} where season_type in ('Playoffs', 'PlayIn')")
        assert n == 0, t
    assert q("select count(*) from marts.team_titles where season = '2024-25'") == 0
    assert (
        q(
            "select count(*) from marts.awards where season = '2024-25' "
            "and award = 'NBA Most Valuable Player'"
        )
        == 0
    )
    assert q("select count(*) from marts.records where valid_from > date '2025-04-13'") == 0
    con.close()


@needs_landing
def test_manifest_as_of_date_is_day_after_cutoff(as_of_snapshot: Path) -> None:
    m = write_manifest(as_of_snapshot, "asof_test", CUTOFF, dt.date(2026, 9, 30), pinned=True)
    assert m["as_of_date"] == "2025-04-14"
    assert m["latest_game_date"] == "2025-04-13"
    assert m["pinned"] is True


@needs_landing
def test_cutoff_inside_a_season_type_fails_the_build(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="as_of_not_inside_season_type"):
        run_dbt(
            tmp_path / "x.duckdb",
            tmp_path / "shots",
            LANDING,
            dt.date(2025, 1, 15),
            {"fixture": True},
        )


# T-2.1 rework: the published as-of file holds nothing after the cutoff in ANY schema. dbt
# builds a full file (its tests read staging), then copy_published writes a fresh file with
# only marts, seeds and semantic.
PLAYOFF_ID = "0042400407"  # 2025 Finals game 7, after the cutoff
PLAYIN_ID = "0052400101"
# Metadata dates that are not games, awards, titles, standings or shots: franchise validity
# ends, seed review dates and fetch timestamps.
METADATA_DATE_COLUMNS = {"valid_to", "reviewed", "fetched_at", "_fetched_at"}


@pytest.fixture(scope="module")
def published_as_of(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("asofpub") / "asof_pub"
    (d / "_dbt_build").mkdir(parents=True)
    staged = d / "_dbt_build" / "asof_pub.duckdb"
    run_dbt(staged, d / "shots", LANDING, CUTOFF, {"fixture": True})
    final = d / "asof_pub.duckdb"
    copy_published(staged, final)
    return final


def after_cutoff_hits(con: duckdb.DuckDBPyConnection, cutoff: dt.date, season: str) -> list[str]:
    """Every (schema.table.column) holding a date after ``cutoff`` or a post-cutoff season type."""
    hits = []
    cols = con.execute(
        "select schema_name, table_name, column_name, data_type from duckdb_columns() "
        "where database_name = current_database() order by 1, 2, 3"
    ).fetchall()
    for s, t, c, typ in cols:
        ref = f'"{s}"."{t}"."{c}"'
        q = f'select count(*) from "{s}"."{t}" where '
        if typ in ("DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE"):
            q += f'"{c}"::date > ?'
        elif typ == "VARCHAR":
            q += (
                f"(regexp_matches(\"{c}\", '^\\d{{4}}-\\d{{2}}-\\d{{2}}') "
                f'and try_cast(left("{c}", 10) as date) > ?)'
            )
        else:
            continue
        row = con.execute(q, [cutoff]).fetchone()
        if row and row[0] and c not in METADATA_DATE_COLUMNS:
            hits.append(f"{ref}: {row[0]}")
        if typ == "VARCHAR" and c == "season_type":
            has_season = con.execute(
                "select count(*) from duckdb_columns() where schema_name = ? and table_name = ? "
                "and column_name = 'season'",
                [s, t],
            ).fetchone()
            if has_season and has_season[0]:
                n = con.execute(
                    f'select count(*) from "{s}"."{t}" where season = ? '
                    f"and season_type in ('Playoffs', 'PlayIn')",
                    [season],
                ).fetchone()
                if n and n[0]:
                    hits.append(f"{ref} post-cutoff season type: {n[0]}")
    return hits


@needs_landing
def test_published_as_of_file_has_nothing_after_cutoff(published_as_of: Path) -> None:
    con = duckdb.connect(str(published_as_of), read_only=True)
    try:
        schemas = {
            r[0]
            for r in con.execute(
                "select distinct schema_name from duckdb_tables() "
                "where database_name = current_database() union "
                "select distinct schema_name from duckdb_views() "
                "where database_name = current_database() and not internal"
            ).fetchall()
        }
        assert schemas == {"marts", "seeds", "semantic"}
        assert after_cutoff_hits(con, CUTOFF, "2024-25") == []
        # The views were re-created and still read the copied tables and the shots folder.
        n = con.execute("select count(*) from semantic.player_season_stats").fetchone()
        assert n is not None and n[0] > 0
        n = con.execute(
            "select count(*) from semantic.shots where game_date > ?", [CUTOFF]
        ).fetchone()
        assert n == (0,)
    finally:
        con.close()
    blob = published_as_of.read_bytes()
    for sentinel in (PLAYOFF_ID, PLAYIN_ID):
        assert sentinel.encode() not in blob


@needs_landing
def test_the_dbt_build_file_did_hold_post_cutoff_rows(published_as_of: Path) -> None:
    """Guards the test above: the staging file it was copied from does leak, so the scan works."""
    staged = published_as_of.parent / "_dbt_build" / published_as_of.name
    con = duckdb.connect(str(staged), read_only=True)
    try:
        hits = after_cutoff_hits(con, CUTOFF, "2024-25")
        assert any(h.startswith('"staging".') for h in hits)
        # marts apply the cutoff themselves; seeds and staging are what copy_published filters
        assert not any(h.startswith(('"marts".', '"semantic".')) for h in hits)
    finally:
        con.close()


def test_copy_published_needs_the_same_stem(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="stem"):
        copy_published(tmp_path / "a.duckdb", tmp_path / "b.duckdb")
