"""Pydantic schema for ``metrics/registry.yaml`` (task 1.22).

The registry is the one definition of every metric. Tools, semantic views, schema and glossary
cards, the numeric verifier and the eval numeric scorer all read it through :func:`load`.

A metric's ``sql`` is an *aggregate* expression over the rows of its ``base`` table (for example
``sum(pts) / nullif(sum(gp), 0)`` over ``player_season``). The same expression then works at every
grain the metric allows: one player-season row, a career (all of a player's season rows), or a
team stint. Leaders and careers therefore never need a second formula.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REGISTRY_PATH = Path(__file__).resolve().parent / "registry.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Base(StrEnum):
    """The mart whose rows a metric's aggregate runs over."""

    player_season = "player_season"  # season totals (source total row for traded players)
    player_stint = "player_stint"  # one team's share of a player's season (Q08, Q48)
    player_game = "player_game"  # box scores (counts of games, plus-minus)
    player_advanced = "player_advanced"  # NBA.com published advanced stats (usage rate)
    team_season = "team_season"
    team_titles = "team_titles"
    league_season = "league_season"  # league-wide totals per season (trends: Q59, Q62)
    shots = "shots"
    awards = "awards"
    player_titles = "player_titles"  # one row per player per title season


class Grain(StrEnum):
    player_season = "player_season"
    player_career = "player_career"
    player_stint = "player_stint"
    player_game = "player_game"
    team_season = "team_season"
    team_all_time = "team_all_time"
    league_season = "league_season"


class Rounding(_Strict):
    decimals: int = Field(ge=0, le=4)
    # Values are stored as fractions for percentages; display multiplies by 100 (47.6%).
    display: Literal["number", "percent"] = "number"


class EraRule(_Strict):
    from_season: str = Field(pattern=r"^\d{4}-\d{2}$")
    min_games_pct: float | None = Field(default=None, gt=0, le=1)
    min_made: int | None = Field(default=None, gt=0)
    min_made_stat: str | None = None
    min_career_games: int | None = Field(default=None, gt=0)
    min_career_total: int | None = Field(default=None, gt=0)
    min_career_total_stat: str | None = None
    would_still_lead: bool = False
    confirmed: bool = False
    source: str

    @model_validator(mode="after")
    def _one_kind(self) -> EraRule:
        kinds = [
            self.min_games_pct is not None,
            self.min_made is not None,
            self.min_career_games is not None or self.min_career_total is not None,
        ]
        if sum(kinds) != 1:
            raise ValueError("an era rule sets exactly one of games %, made shots, or career")
        if self.min_made is not None and not self.min_made_stat:
            raise ValueError("min_made needs min_made_stat")
        return self


class Qualification(_Strict):
    name: str
    description: str
    season_type: Literal["Regular Season", "Playoffs"] = "Regular Season"
    eras: list[EraRule] = Field(min_length=1)

    def rule_for(self, season: str) -> EraRule:
        rules = [e for e in self.eras if e.from_season <= season]
        if not rules:
            raise LookupError(f"{self.name}: no rule for {season}")
        return max(rules, key=lambda e: e.from_season)


class Metric(_Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    label: str
    description: str
    formula: str  # human-readable, for the glossary
    base: Base
    filter: str | None = None  # SQL predicate on base rows, applied before the aggregate
    sql: str
    grains: list[Grain] = Field(min_length=1)
    unit: Literal["count", "per_game", "percent", "rating", "minutes", "rate"]
    rounding: Rounding
    higher_is_better: bool = True
    qualification: str | None = None  # name of a Qualification, for leader lists
    per_game_of: str | None = None  # the total this per-game metric divides (would-still-lead)
    requires: list[str] = Field(default_factory=list)  # stat_availability stats
    aliases: list[str] = Field(default_factory=list)
    caveats: str | None = None

    @field_validator("aliases")
    @classmethod
    def _aliases_lower(cls, v: list[str]) -> list[str]:
        return [a.strip() for a in v]


class Registry(_Strict):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    default_season_type: Literal["Regular Season"] = "Regular Season"
    qualifications: list[Qualification]
    metrics: list[Metric]

    @model_validator(mode="after")
    def _consistent(self) -> Registry:
        names = [m.name for m in self.metrics]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate metric names: {sorted(dupes)}")
        quals = {q.name for q in self.qualifications}
        for m in self.metrics:
            if m.qualification and m.qualification not in quals:
                raise ValueError(f"{m.name}: unknown qualification {m.qualification!r}")
            if m.per_game_of and m.per_game_of not in names:
                raise ValueError(f"{m.name}: per_game_of names unknown metric {m.per_game_of!r}")
        for q in self.qualifications:
            for e in q.eras:
                for stat in (e.min_made_stat, e.min_career_total_stat):
                    if stat and stat not in names:
                        raise ValueError(f"{q.name}: {stat!r} is not a metric name")
        seen: dict[str, str] = {}
        for m in self.metrics:
            for a in [m.name, *m.aliases]:
                key = a.lower()
                if key in seen and seen[key] != m.name:
                    raise ValueError(f"alias {a!r} used by {seen[key]} and {m.name}")
                seen[key] = m.name
        return self

    def metric(self, name_or_alias: str) -> Metric:
        key = name_or_alias.strip().lower()
        for m in self.metrics:
            if key == m.name or key in (a.lower() for a in m.aliases):
                return m
        raise KeyError(name_or_alias)

    def qualification(self, name: str) -> Qualification:
        return next(q for q in self.qualifications if q.name == name)


def load(path: Path = REGISTRY_PATH) -> Registry:
    with path.open(encoding="utf-8") as f:
        return Registry.model_validate(yaml.safe_load(f))


@lru_cache(maxsize=1)
def registry() -> Registry:
    return load()
