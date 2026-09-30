"""Generate ``ingest/schemas/*.json`` from real samples (task 1.4).

Usage: ``uv run python -m ingest.gen_schemas``

Samples span early and modern seasons, so NULL-era column types are covered. Each sample goes
through the raw store, so re-running uses the cache. Trimmed copies are written to
``tests/fixtures/raw_samples/`` for the contract tests.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app import jsonlog
from app.config import sources
from ingest.client import NbaClient
from ingest.contracts import SCHEMA_DIR, generate_schema
from ingest.endpoints import SPECS
from ingest.raw_store import RawStore

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "raw_samples"

RS, PO, PI = "Regular Season", "Playoffs", "PlayIn"

# key -> list of (season label or None, kwargs)
SAMPLES: dict[str, list[tuple[str | None, dict[str, Any]]]] = {
    "leaguegamelog_t": [
        ("1961-62", {"season": "1961-62", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": PO}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": PI}),
    ],
    "leaguegamelog_p": [
        ("1961-62", {"season": "1961-62", "season_type_all_star": RS}),
        ("1979-80", {"season": "1979-80", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": PO}),
    ],
    "commonallplayers": [(None, {})],
    "commonplayerinfo": [(None, {"player_id": 2544}), (None, {"player_id": 76375})],
    "playercareerstats": [
        (None, {"player_id": 2544}),
        (None, {"player_id": 76375}),
        (None, {"player_id": 1629029}),
    ],
    "playerawards": [(None, {"player_id": 2544}), (None, {"player_id": 76375})],
    "franchisehistory": [(None, {})],
    "teamyearbyyearstats": [(None, {"team_id": 1610612738}), (None, {"team_id": 1610612760})],
    "leaguedashteamstats_adv": [
        ("1996-97", {"season": "1996-97", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": PO}),
    ],
    "leaguedashplayerstats_adv": [
        ("1996-97", {"season": "1996-97", "season_type_all_star": RS}),
        ("2024-25", {"season": "2024-25", "season_type_all_star": PO}),
    ],
    "leaguestandingsv3": [
        ("1970-71", {"season": "1970-71"}),
        ("2024-25", {"season": "2024-25"}),
    ],
    "shotchartdetail": [
        (
            "1996-97",
            {"team_id": 1610612741, "season_nullable": "1996-97", "season_type_all_star": RS},
        ),
        (
            "2024-25",
            {"team_id": 1610612742, "season_nullable": "2024-25", "season_type_all_star": PO},
        ),
    ],
}


def trim(body: dict[str, Any], names: tuple[str, ...], n: int = 5) -> dict[str, Any]:
    sets = [{**rs, "rowSet": rs["rowSet"][:n]} for rs in body["resultSets"] if rs["name"] in names]
    return {"resultSets": sets}


def main() -> None:
    jsonlog.configure()
    jsonlog.set_run()
    cfg = sources()
    store = RawStore(cfg.resolve(cfg.paths.raw), NbaClient(cfg.nba_api))
    SCHEMA_DIR.mkdir(exist_ok=True)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for key, samples in SAMPLES.items():
        spec = SPECS[key]
        bodies = [store.get(spec, season, **kw).response for season, kw in samples]
        schema = generate_schema(key, bodies, spec.result_sets)
        (SCHEMA_DIR / f"{key}.json").write_text(json.dumps(schema, indent=1) + "\n")
        (FIXTURES / f"{key}.json").write_text(
            json.dumps(trim(bodies[-1], spec.result_sets), separators=(",", ":")) + "\n"
        )
        logging.getLogger(__name__).info("schema written", extra={"endpoint": key})


if __name__ == "__main__":
    main()
