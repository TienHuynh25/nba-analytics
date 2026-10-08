"""JSON argument schemas for the 10 typed tools (task 2.5; implemented in 3.8).

Usage: ``uv run python -m app.tools.schemas`` writes ``app/tools/schemas/<tool>.json``.

Arguments carry resolved IDs (``player_ids``, ``team_ids``): entity resolution runs before the
tool call, so gold tool calls are stable and comparable. Metric enums come from the registry's
grains, so a new registry metric becomes a valid argument with no code change. Defaults for
season type and qualification come from the registry, never from prompts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metrics.schema import Grain, Registry, load

OUT = Path(__file__).resolve().parent / "schemas"

# The stat line for "averages" / "stats" questions (docs/decisions/0006-stat-line.md).
STAT_LINE = [
    "games_played",
    "minutes_per_game",
    "points_per_game",
    "rebounds_per_game",
    "assists_per_game",
    "steals_per_game",
    "blocks_per_game",
    "field_goal_pct",
    "three_point_pct",
    "free_throw_pct",
]
STAT_LINE_NAME = "stat_line"

SEASON = {"type": "string", "pattern": r"^\d{4}-\d{2}$", "description": "e.g. 2025-26"}
SEASON_TYPE = {
    "type": "string",
    "enum": ["Regular Season", "Playoffs", "PlayIn"],
    "default": "Regular Season",
}
DATE = {"type": "string", "format": "date"}
PLAYER_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1}
TEAM_IDS = {"type": "array", "items": {"type": "integer"}, "minItems": 1}

AWARDS = [
    "NBA Most Valuable Player",
    "NBA Rookie of the Year",
    "NBA Defensive Player of the Year",
    "NBA Sixth Man of the Year",
    "NBA Most Improved Player",
    "NBA Finals Most Valuable Player",
    "NBA All-Star",
    "All-NBA",
    "All-Defensive Team",
    "All-Rookie Team",
]
RECORDS = [
    "most_points_game",
    "most_threes_game",
    "most_rebounds_game",
    "most_assists_game",
    "career_triple_doubles",
    "best_regular_season_record",
    "most_championships",
]


def _metrics(reg: Registry, *grains: Grain) -> list[str]:
    return sorted(m.name for m in reg.metrics if any(g in m.grains for g in grains))


def _obj(props: dict[str, Any], required: list[str], desc: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "description": desc,
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def schemas(reg: Registry) -> dict[str, dict[str, Any]]:
    player_m = _metrics(reg, Grain.player_season)
    career_m = _metrics(reg, Grain.player_career)
    team_m = _metrics(reg, Grain.team_season)
    stint_m = _metrics(reg, Grain.player_stint)
    leader_m = sorted(set(player_m) | set(career_m) | set(team_m))
    trend_m = sorted(set(player_m) | set(team_m) | set(_metrics(reg, Grain.league_season)))

    def metric_list(enum: list[str]) -> dict[str, Any]:
        # "stat_line" is shorthand for the stat-line metrics (expanded before running).
        extra = [STAT_LINE_NAME] if set(STAT_LINE) <= set(enum) else []
        return {
            "type": "array",
            "items": {"type": "string", "enum": [*extra, *enum]},
            "minItems": 1,
        }

    return {
        "get_player_stats": _obj(
            {
                "player_ids": {**PLAYER_IDS, "maxItems": 1},
                "season": SEASON,
                "season_type": SEASON_TYPE,
                "metrics": metric_list(sorted(set(player_m) | set(stint_m))),
                "team_id": {"type": "integer", "description": "only this team's stint (Q08)"},
                "breakdown": {
                    "type": "string",
                    "enum": ["zone"],
                    "description": "split shot metrics by court zone (Q73)",
                },
            },
            ["player_ids", "season", "metrics"],
            "One player's stats for one season (or one team stint of it).",
        ),
        "get_leaders": _obj(
            {
                "entity": {"type": "string", "enum": ["player", "team"], "default": "player"},
                "metric": {"type": "string", "enum": leader_m},
                "scope": {"type": "string", "enum": ["season", "career"], "default": "season"},
                "season": SEASON,
                "season_type": SEASON_TYPE,
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 5},
                "qualified": {
                    "type": "boolean",
                    "default": True,
                    "description": "apply the registry's qualification rule",
                },
                "rookies_only": {"type": "boolean", "default": False},
                "team_id": {"type": "integer", "description": "rank within one team (Q48)"},
            },
            ["metric"],
            "Ranked leaders for a metric in a season, or all-time (career).",
        ),
        "compare": _obj(
            {
                "player_ids": {**PLAYER_IDS, "minItems": 2, "maxItems": 4},
                "team_ids": {**TEAM_IDS, "minItems": 2, "maxItems": 4},
                "metrics": metric_list(sorted(set(player_m) | set(career_m) | set(team_m))),
                "scope": {
                    "type": "string",
                    "enum": ["season", "career", "first_n_seasons", "last_n_seasons"],
                    "default": "season",
                },
                "n_seasons": {"type": "integer", "minimum": 1, "maximum": 25},
                "season": SEASON,
                "season_type": SEASON_TYPE,
            },
            ["metrics"],
            "Side-by-side players or teams. Give player_ids or team_ids.",
        ),
        "get_team_stats": _obj(
            {
                "team_ids": {**TEAM_IDS, "maxItems": 1},
                "season": SEASON,
                "season_type": SEASON_TYPE,
                "metrics": metric_list(team_m),
            },
            ["team_ids", "season", "metrics"],
            "One team's stats for one season.",
        ),
        "get_standings": _obj(
            {
                "season": SEASON,
                "conference": {"type": "string", "enum": ["East", "West"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            ["season"],
            "Regular-season standings, league-wide or for one conference.",
        ),
        "get_games": _obj(
            {
                "team_ids": {**TEAM_IDS, "maxItems": 2},
                "player_ids": {**PLAYER_IDS, "maxItems": 1},
                "season": SEASON,
                "season_types": {
                    "type": "array",
                    "items": SEASON_TYPE,
                    "minItems": 1,
                    "default": ["Regular Season"],
                },
                "date": DATE,
                "last_n": {"type": "integer", "minimum": 1, "maximum": 82},
                "overtime_only": {"type": "boolean", "default": False},
                "finals_only": {"type": "boolean", "default": False},
                "sort": {
                    "type": "string",
                    "enum": ["date_desc", "margin_desc", "player_points_desc"],
                    "default": "date_desc",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "box_leaders": {
                    "type": "boolean",
                    "default": False,
                    "description": "include each game's points/rebounds/assists leaders",
                },
                "streak": {
                    "type": "string",
                    "enum": ["win", "loss"],
                    "description": "longest streak for the team in the season",
                },
            },
            [],
            "Games and box scores: last games, head-to-head, overtime, margins, streaks.",
        ),
        "get_career": _obj(
            {
                "player_ids": {**PLAYER_IDS, "maxItems": 1},
                "season_type": SEASON_TYPE,
                "metrics": metric_list(career_m),
            },
            ["player_ids", "metrics"],
            "One player's career totals and averages.",
        ),
        "get_record": _obj(
            {
                "record": {"type": "string", "enum": RECORDS},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
            },
            ["record"],
            "All-time records: single-game highs, best seasons, titles.",
        ),
        "get_trend": _obj(
            {
                "entity": {"type": "string", "enum": ["player", "team", "league"]},
                "player_ids": {**PLAYER_IDS, "maxItems": 1},
                "team_ids": {**TEAM_IDS, "maxItems": 1},
                "metric": {"type": "string", "enum": trend_m},
                "season_from": SEASON,
                "season_to": SEASON,
                "season_type": SEASON_TYPE,
            },
            ["entity", "metric"],
            "A metric season by season (a player's career, a team, or the league).",
        ),
        "get_awards": _obj(
            {
                "award": {"type": "string", "enum": AWARDS},
                "season": SEASON,
                "player_ids": {**PLAYER_IDS, "maxItems": 1},
                "mode": {
                    "type": "string",
                    "enum": ["winners", "count_by_player"],
                    "default": "winners",
                },
                "include_stats": {
                    "type": "boolean",
                    "default": False,
                    "description": "add the winner's season stat line (Q77)",
                },
            },
            ["award"],
            "Award winners by season, or award counts by player.",
        ),
    }


def write(reg: Registry | None = None, out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    for name, schema in schemas(reg or load()).items():
        (out / f"{name}.json").write_text(json.dumps(schema, indent=1) + "\n")


if __name__ == "__main__":
    write()


def load_schema(tool: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((OUT / f"{tool}.json").read_text())
    return data


def expand_metrics(metrics: list[str]) -> list[str]:
    out: list[str] = []
    for m in metrics:
        for x in STAT_LINE if m == STAT_LINE_NAME else [m]:
            if x not in out:
                out.append(x)
    return out


def canonical(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Args with schema defaults filled, "stat_line" expanded and id lists sorted, so two calls
    that mean the same thing compare equal."""
    props = load_schema(tool)["properties"]
    out = {k: v["default"] for k, v in props.items() if "default" in v}
    out.update(args)
    if "metrics" in out:
        out["metrics"] = sorted(expand_metrics(list(out["metrics"])))
    for k in ("player_ids", "team_ids", "season_types"):
        if isinstance(out.get(k), list):
            out[k] = sorted(out[k])
    return out
