"""Conversation state (task 3.14).

Each session keeps a small structured state: the last resolved players, teams, season, season
type and metric, plus the last tool call. A follow-up ("what about his assists?", "and in the
playoffs?") fills its missing arguments from this state. The model never re-reads the raw
transcript for it. A pronoun that could mean two players ("he" after comparing LeBron James and
Kevin Durant) is ambiguous, and the answer is a clarifying question.

States are plain objects passed in and out, with no globals, so they work per request behind
the team service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.entities import Ambiguity, Entity, Resolution
from app.timeparse import TimeRef

_PLAYER_PRONOUN = re.compile(r"\b(he|him|his|he's|himself)\b", re.IGNORECASE)
_TEAM_PRONOUN = re.compile(r"\b(they|them|their|they're)\b", re.IGNORECASE)
_BOTH = re.compile(r"\b(both|each|either|the two|those two|them)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ConversationState:
    players: tuple[Entity, ...] = ()
    teams: tuple[Entity, ...] = ()
    season: str | None = None
    season_type: str | None = None
    metric: str | None = None
    last_tool: str | None = None
    last_args: dict[str, Any] = field(default_factory=dict)
    # Entities that came out of the last result (e.g. the leader), for "his", "their".
    result_players: tuple[Entity, ...] = ()
    result_teams: tuple[Entity, ...] = ()

    def summary(self) -> str:
        parts = []
        if self.players:
            parts.append("players: " + ", ".join(f"{e.name} (id {e.id})" for e in self.players))
        if self.teams:
            parts.append("teams: " + ", ".join(f"{e.name} (id {e.id})" for e in self.teams))
        if self.result_players:
            parts.append(
                "last answer was about: "
                + ", ".join(f"{e.name} (id {e.id})" for e in self.result_players)
            )
        if self.result_teams:
            parts.append(
                "last answer was about team: "
                + ", ".join(f"{e.name} (id {e.id})" for e in self.result_teams)
            )
        if self.season:
            parts.append(f"season: {self.season}")
        if self.season_type:
            parts.append(f"season type: {self.season_type}")
        if self.metric:
            parts.append(f"metric: {self.metric}")
        if self.last_tool:
            parts.append(f"last tool call: {self.last_tool} {self.last_args}")
        return "; ".join(parts) or "empty"


@dataclass(frozen=True)
class Context:
    """Entities and time for one turn, after carry-over from the state."""

    players: tuple[Entity, ...]
    teams: tuple[Entity, ...]
    season: str | None
    season_type: str | None
    carried: tuple[str, ...]  # what came from the state, for the eval's carry-over scorer
    ambiguous: tuple[Ambiguity, ...] = ()


def carry_over(question: str, res: Resolution, time: TimeRef, state: ConversationState) -> Context:
    players: tuple[Entity, ...] = tuple(res.players)
    teams: tuple[Entity, ...] = tuple(res.teams)
    carried: list[str] = []
    ambiguous = list(res.ambiguous)

    if not players and not res.ambiguous:
        if _PLAYER_PRONOUN.search(question):
            pool = state.result_players or state.players
            if len(pool) == 1:
                players = pool
                carried.append("players")
            elif len(pool) > 1 and not _BOTH.search(question):
                ambiguous.append(
                    Ambiguity(
                        _PLAYER_PRONOUN.search(question).group(0),  # type: ignore[union-attr]
                        list(pool),
                    )
                )
            elif len(pool) > 1:
                players = pool
                carried.append("players")
        elif not teams and state.players and _is_follow_up(question):
            # Carry the players the user named. A previous answer's players (the leader) are
            # only carried through a pronoun ("his assists").
            players = state.players
            carried.append("players")
    if not teams and not res.ambiguous:
        if _TEAM_PRONOUN.search(question) and (state.result_teams or state.teams):
            teams = state.result_teams or state.teams
            carried.append("teams")
        elif not players and state.teams and _is_follow_up(question):
            teams = state.teams
            carried.append("teams")

    season = time.season
    season_type = time.season_type
    if season is None and time.seasons is None and state.season is not None:
        season = state.season
        carried.append("season")
    if season_type is None and state.season_type is not None and not time.phrase:
        season_type = state.season_type
        carried.append("season_type")
    return Context(players, teams, season, season_type, tuple(carried), tuple(ambiguous))


_FOLLOW_UP = re.compile(
    r"^\s*(and|what about|how about|and what about|compare that|over|in the|what's their|"
    r"what is their|how many has|how many did)\b",
    re.IGNORECASE,
)


def _is_follow_up(question: str) -> bool:
    return bool(_FOLLOW_UP.search(question)) or len(question.split()) <= 5


def update(
    state: ConversationState,
    ctx: Context,
    tool: str | None,
    args: dict[str, Any],
    result_players: tuple[Entity, ...] = (),
    result_teams: tuple[Entity, ...] = (),
) -> ConversationState:
    metric = args.get("metric") or (args.get("metrics") or [None])[0] or state.metric
    return replace(
        state,
        players=ctx.players or state.players,
        teams=ctx.teams or state.teams,
        season=args.get("season") or ctx.season or state.season,
        season_type=args.get("season_type") or ctx.season_type or state.season_type,
        metric=metric,
        last_tool=tool,
        last_args=args,
        result_players=result_players,
        result_teams=result_teams,
    )
