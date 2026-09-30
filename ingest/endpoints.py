"""Endpoint specs from ``ingest/ENDPOINTS.md`` (task 1.3).

Each spec names a raw-store key, the ``nba_api`` endpoint class that builds the full parameter
set, the fixed parameters we always set, and the result sets we rely on (the ones the JSON
contract checks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nba_api.stats import endpoints as E

SEASON_TYPES = ("Regular Season", "Playoffs", "PlayIn", "IST")

FIRST_SEASON = 1946  # 1946-47
FIRST_ADVANCED_SEASON = 1996  # 1996-97: advanced stats, plus-minus, shot charts
FIRST_PLAYIN_SEASON = 2020  # 2020-21: first Play-In tournament on NBA.com
FIRST_IST_SEASON = 2023  # 2023-24: first NBA Cup
FIRST_STANDINGS_SEASON = 1970  # earliest season probed for LeagueStandingsV3 (1.3)


def season_label(start_year: int) -> str:
    """1996 -> '1996-97'."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def season_start(label: str) -> int:
    return int(label[:4])


@dataclass(frozen=True)
class EndpointSpec:
    key: str
    cls: Any
    fixed: dict[str, Any] = field(default_factory=dict)
    result_sets: tuple[str, ...] = ()

    @property
    def endpoint(self) -> str:
        return str(self.cls.endpoint)

    def params(self, **kwargs: Any) -> dict[str, Any]:
        """The full query parameters ``nba_api`` would send, without sending anything."""
        ep = self.cls(**self.fixed, **kwargs, get_request=False)
        return dict(ep.parameters)


SPECS: dict[str, EndpointSpec] = {
    s.key: s
    for s in [
        EndpointSpec(
            "leaguegamelog_t",
            E.LeagueGameLog,
            {"player_or_team_abbreviation": "T"},
            ("LeagueGameLog",),
        ),
        EndpointSpec(
            "leaguegamelog_p",
            E.LeagueGameLog,
            {"player_or_team_abbreviation": "P"},
            ("LeagueGameLog",),
        ),
        EndpointSpec(
            "commonallplayers",
            E.CommonAllPlayers,
            {"is_only_current_season": 0},
            ("CommonAllPlayers",),
        ),
        EndpointSpec("commonplayerinfo", E.CommonPlayerInfo, {}, ("CommonPlayerInfo",)),
        EndpointSpec(
            "playercareerstats",
            E.PlayerCareerStats,
            {"per_mode36": "Totals"},
            (
                "SeasonTotalsRegularSeason",
                "CareerTotalsRegularSeason",
                "SeasonTotalsPostSeason",
                "CareerTotalsPostSeason",
            ),
        ),
        EndpointSpec("playerawards", E.PlayerAwards, {}, ("PlayerAwards",)),
        EndpointSpec(
            "franchisehistory", E.FranchiseHistory, {}, ("FranchiseHistory", "DefunctTeams")
        ),
        EndpointSpec(
            "teamyearbyyearstats",
            E.TeamYearByYearStats,
            {"per_mode_simple": "Totals"},
            ("TeamStats",),
        ),
        EndpointSpec(
            "leaguedashteamstats_adv",
            E.LeagueDashTeamStats,
            {"measure_type_detailed_defense": "Advanced"},
            ("LeagueDashTeamStats",),
        ),
        EndpointSpec(
            "leaguedashplayerstats_adv",
            E.LeagueDashPlayerStats,
            {"measure_type_detailed_defense": "Advanced"},
            ("LeagueDashPlayerStats",),
        ),
        EndpointSpec("leaguestandingsv3", E.LeagueStandingsV3, {}, ("Standings",)),
        EndpointSpec(
            "shotchartdetail",
            E.ShotChartDetail,
            {"player_id": 0, "context_measure_simple": "FGA"},
            ("Shot_Chart_Detail",),
        ),
    ]
}


def result_sets(body: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Turn a stats.nba.com body into {result set name: list of row dicts}."""
    sets = body.get("resultSets", body.get("resultSet", []))
    if isinstance(sets, dict):
        sets = [sets]
    out: dict[str, list[dict[str, Any]]] = {}
    for rs in sets:
        headers = rs["headers"]
        out[rs["name"]] = [dict(zip(headers, row, strict=True)) for row in rs["rowSet"]]
    return out
