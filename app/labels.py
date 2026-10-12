"""Metric names as they appear in prose, for the verifier's semantic guard.

Maps a normalized phrase ("points per game", "ppg", "from the field") to the result columns it
can describe. Built from the registry: each metric's label and aliases; a per-game metric also
answers to its base total's words ("32.7 points" for points per game); plus a few plain columns
(games, rank) and common phrasings. Aliases of two characters or fewer only count when written
in uppercase, so "to lead the league" is not read as turnovers.
"""

from __future__ import annotations

import re
from functools import lru_cache

from metrics.schema import Registry, registry

PLAIN = {
    "gp": ["games", "game", "games played", "gp"],
    "rank": ["rank", "ranked", "ranking"],
    "team_gp": ["team games"],
}
EXTRA = {
    "field_goal_pct": ["from the field", "field goal", "field goals"],
    "three_point_pct": ["from three", "from 3", "from deep", "from beyond the arc"],
    "free_throw_pct": ["from the line", "from the free throw line", "free throws"],
    "minutes_per_game": ["minutes a game"],
}


def norm(s: str) -> str:
    s = s.lower().replace("-", " ").replace("\u2019", "'")
    s = re.sub(r"'s\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=4)
def _lexicon(reg_version: str) -> tuple[dict[str, frozenset[str]], set[str]]:
    reg: Registry = registry()
    out: dict[str, set[str]] = {}

    def add(phrase: str, col: str) -> None:
        out.setdefault(norm(phrase), set()).add(col)

    by_name = {m.name: m for m in reg.metrics}
    for m in reg.metrics:
        for p in [m.label, *m.aliases, *EXTRA.get(m.name, [])]:
            add(p, m.name)
        if m.per_game_of and m.per_game_of in by_name:
            base = by_name[m.per_game_of]
            for p in [base.label, *base.aliases]:
                add(p, m.name)
    for m in reg.metrics:  # games played also answers to the plain gp column, and vice versa
        if m.name == "games_played":
            for p in PLAIN["gp"]:
                add(p, "games_played")
    for col, phrases in PLAIN.items():
        for p in phrases:
            add(p, col)
    out.setdefault("games played", set()).add("gp")
    short = {p for p in out if len(p.replace(" ", "")) <= 2}
    return {p: frozenset(c) for p, c in out.items()}, short


def lexicon() -> tuple[dict[str, frozenset[str]], set[str]]:
    return _lexicon(registry().version)


_WORD = re.compile(r"[A-Za-z%][A-Za-z%']*")


def first_label(window: str, max_words: int = 5) -> tuple[str, frozenset[str]] | None:
    """The first metric phrase in ``window`` (longest match first at each word), if any."""
    lex, short = lexicon()
    words = _WORD.findall(window)[:max_words]
    longest = max((len(p.split()) for p in lex), default=1)
    for i in range(len(words)):
        for n in range(min(longest, len(words) - i), 0, -1):
            raw = " ".join(words[i : i + n])
            phrase = norm(raw)
            if phrase in lex:
                if phrase in short and raw != raw.upper():
                    continue
                return raw, lex[phrase]
    return None
