"""Schema for ``eval/cases.yaml`` (task 2.2). Pydantic validates every case on load.

A case is either a single question or a multi-turn conversation. Gold answers are written for the
pinned snapshot ``eval_2025_26_rs`` (see eval/README.md for the relative-time rule).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

CASES_PATH = Path(__file__).resolve().parent / "cases.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Category(StrEnum):
    """The spec's 11 category labels."""

    player_season = "Player season"
    leaders = "Leaders"
    comparison = "Comparison"
    records = "Records"
    team = "Team"
    game = "Game"
    trend = "Trend"
    definition = "Definition"
    shooting = "Shooting"
    awards = "Awards"
    scope_limits = "Scope limits"


class Path_(StrEnum):
    stats = "stats"
    knowledge = "knowledge"
    mixed = "mixed"
    refuse = "refuse"


class CaseType(StrEnum):
    seed = "seed"
    paraphrase = "paraphrase"
    entity_variant = "entity_variant"
    multi_turn = "multi_turn"
    hard_negative = "hard_negative"


class Expect(StrEnum):
    """What a correct answer does."""

    answer = "answer"  # give the gold value(s)
    decline = "decline"  # one plain sentence declining (predictions, betting, injuries, non-NBA)
    clarify = "clarify"  # ask which entity is meant
    not_tracked = "not_tracked"  # say the stat was not tracked and name its first season
    no_verdict = "no_verdict"  # opinion question: stats only, no verdict (owner rule 0005)


class ToolCall(_Strict):
    tool: Literal[
        "get_player_stats",
        "get_leaders",
        "compare",
        "get_team_stats",
        "get_standings",
        "get_games",
        "get_career",
        "get_record",
        "get_trend",
        "get_awards",
    ]
    args: dict[str, Any]


class Gold(_Strict):
    path: Path_
    expect: Expect = Expect.answer
    tool_call: ToolCall | None = None
    sql: str | None = None
    # Gold values: scalar, list of rows, or mapping; filled from the pinned snapshot (2.6).
    value: Any = None
    entities: dict[str, list[int]] = Field(default_factory=dict)  # players/teams -> ids
    chunks: list[str] = Field(default_factory=list)  # gold glossary chunk ids (knowledge)
    rule: str | None = None  # gold-answer rule for ambiguous seeds (spec table)
    note: str | None = None


class Turn(_Strict):
    question: str
    gold: Gold
    reuses: list[str] = Field(default_factory=list)  # entities/args carried from earlier turns


class Case(_Strict):
    id: str = Field(pattern=r"^(Q\d{2}|M\d{2}|H\d{2})(-[a-z0-9]+)?$")
    seed_id: str = Field(pattern=r"^(Q\d{2}|M\d{2}|H\d{2})$")  # the seed family
    type: CaseType
    category: Category
    question: str | None = None
    turns: list[Turn] | None = None
    gold: Gold | None = None
    source: str  # where the question came from (seed theme, LLM paraphrase, log, ...)
    critical: bool = False
    split: Literal["dev", "heldout"] | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> Case:
        single = self.question is not None and self.gold is not None
        multi = self.turns is not None and len(self.turns) >= 2
        if single == multi:
            raise ValueError(f"{self.id}: give question+gold, or 2+ turns, not both")
        if multi and self.type != CaseType.multi_turn:
            raise ValueError(f"{self.id}: turns are only for multi_turn cases")
        return self


class CaseSet(_Strict):
    version: str
    snapshot: str
    cases: list[Case]

    @model_validator(mode="after")
    def _unique(self) -> CaseSet:
        ids = [c.id for c in self.cases]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate case ids: {sorted(dupes)}")
        return self


def load(path: Path = CASES_PATH) -> CaseSet:
    with path.open(encoding="utf-8") as f:
        return CaseSet.model_validate(yaml.safe_load(f))


@lru_cache(maxsize=1)
def cases() -> CaseSet:
    return load()
