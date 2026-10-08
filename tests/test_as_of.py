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
from ingest.snapshots import BuildError, run_dbt, write_manifest

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
