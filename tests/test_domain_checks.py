"""Task 1.20 done-when: each domain check fails on a planted error.

Each case copies the one-season fixture, plants one error with SQL, and runs dbt's singular
(domain) tests against the copy. The clean copy must pass every check, and each planted error
must fail the check it targets.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import duckdb
import pytest

from app.config import REPO_ROOT

pytestmark = pytest.mark.dbt
TRANSFORM = REPO_ROOT / "transform"

# Make the fixture's source career totals agree with its one season, so the careers check runs.
CONSISTENT_CAREERS = """
update staging.stg_player_career_totals c set
    gp = s.gp, pts = s.pts, reb = s.reb, ast = s.ast, fgm = s.fgm, ftm = s.ftm,
    fg3m = s.fg3m, stl = s.stl, blk = s.blk
from (select player_id, season_type, sum(gp) gp, sum(pts) pts, sum(reb) reb, sum(ast) ast,
             sum(fgm) fgm, sum(ftm) ftm, sum(fg3m) fg3m, sum(stl) stl, sum(blk) blk
      from marts.player_season group by all) s
where s.player_id = c.player_id and s.season_type = c.season_type;
delete from staging.stg_player_career_totals c
where not exists (select 1 from marts.player_season s
                  where s.player_id = c.player_id and s.season_type = c.season_type);
"""

PLANTS = {
    "player_points_sum_to_team_points": """
        update marts.player_game set pts = pts + 7
        where (game_id, player_id) in (select game_id, player_id from marts.player_game
                                       where pts > 0 limit 1)""",
    "stints_sum_to_season_total": """
        update marts.player_season_stint set pts = pts + 3
        where (player_id, season, season_type, team_id) in (
            select s.player_id, s.season, s.season_type, s.team_id
            from marts.player_season_stint s join marts.player_season t
              using (player_id, season, season_type)
            where t.team_count > 1 limit 1)""",
    "games_within_schedule_length": """
        update marts.team_season set gp = 90
        where (team_id, season) in (select team_id, season from marts.team_season
                                    where season_type = 'Regular Season' limit 1)
          and season_type = 'Regular Season'""",
    "careers_match_source": """
        update marts.player_season set pts = pts + 1
        where (player_id, season, season_type) in (
            select player_id, season, season_type from marts.player_season limit 1)""",
    "team_record_matches_source": """
        update staging.stg_team_year set wins = wins + 1
        where (team_id, season) in (select team_id, season from marts.team_season
                                    where season_type = 'Regular Season' limit 1)""",
    "untracked_stats_are_null": """
        update seeds.stat_availability set first_season_start = 2030 where stat = 'stl'""",
    "as_of_not_inside_season_type": """
        update staging.int_season_type_status set straddles_cutoff = true
        where season_type = 'Regular Season'""",
}


def run_domain_tests(db: Path, tmp: Path) -> dict[str, str]:
    landing = tmp / "empty_landing.duckdb"
    duckdb.connect(str(landing)).close()
    env = {
        **os.environ,
        "NBA_SNAPSHOT_PATH": str(db),
        "NBA_LANDING_PATH": str(landing),
        "NBA_SHOTS_DIR": str(tmp / "shots"),
    }
    target = tmp / "target"
    subprocess.run(
        [
            "dbt",
            "test",
            "--profiles-dir",
            ".",
            "--select",
            "test_type:singular",
            "--target-path",
            str(target),
            "--vars",
            json.dumps({"fixture": False}),
        ],
        cwd=TRANSFORM,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    results = json.loads((target / "run_results.json").read_text())["results"]
    return {r["unique_id"].split(".")[-1]: r["status"] for r in results}


@pytest.fixture(scope="module")
def clean_copy(fixture_db_path: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("clean")
    db = d / "fixture.duckdb"
    shutil.copy2(fixture_db_path, db)
    con = duckdb.connect(str(db))
    con.execute(CONSISTENT_CAREERS)
    con.close()
    return db


def test_clean_fixture_passes_every_domain_check(clean_copy: Path, tmp_path: Path) -> None:
    db = tmp_path / "db.duckdb"
    shutil.copy2(clean_copy, db)
    status = run_domain_tests(db, tmp_path)
    assert set(PLANTS) <= set(status)
    assert all(s == "pass" for s in status.values()), status


@pytest.mark.parametrize("check", sorted(PLANTS))
def test_planted_error_fails_its_check(check: str, clean_copy: Path, tmp_path: Path) -> None:
    db = tmp_path / "db.duckdb"
    shutil.copy2(clean_copy, db)
    con = duckdb.connect(str(db))
    con.execute(PLANTS[check])
    con.close()
    status = run_domain_tests(db, tmp_path)
    assert status[check] == "fail", status
