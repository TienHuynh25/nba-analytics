"""Entity resolution: names, nicknames, misspellings -> player and team IDs (task 3.6).

Order of matching, longest phrase first, over the question's words:

1. exact alias (``semantic.player_aliases`` / ``semantic.team_aliases``, accent- and
   case-insensitive): full names, accent-free spellings, unique last names, curated nicknames;
2. a bare last name or "J. Williams" that several players share -> **ambiguous**: the
   resolver asks which one is meant, listing the candidates (spec: if ambiguous, ask);
3. fuzzy match for misspelled names ("Wembenyama", "Bill Russel"), only on spans that look like
   names (capitalized, not question words), with a high threshold.

The alias tables are read once per snapshot.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

import duckdb
from rapidfuzz import fuzz, process

FUZZY_THRESHOLD = 88
MAX_SPAN = 4
QUESTION_WORDS = {
    "how",
    "what",
    "who",
    "which",
    "when",
    "where",
    "why",
    "is",
    "are",
    "was",
    "were",
    "does",
    "did",
    "do",
    "has",
    "have",
    "compare",
    "show",
    "list",
    "give",
    "tell",
    "explain",
    "predict",
    "should",
    "between",
    "among",
    "nba",
    "the",
    "in",
    "of",
    "and",
    "or",
    "vs",
    "versus",
    "a",
}
# Hyphens split tokens ("Celtics-Knicks", "Gilgeous-Alexander"); aliases store them as spaces.
_TOKEN = re.compile(r"[A-Za-zÀ-ÿ0-9][\wÀ-ÿ.'\u2019]*")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("\u2019", "'").replace("-", " ")
    s = re.sub(r"'s\b|'(?=\s|$)", "", s)  # possessives
    return re.sub(r"\s+", " ", s).strip(' .,?!:;"')


@dataclass(frozen=True)
class Entity:
    kind: str  # player | team
    id: int
    name: str
    mention: str
    how: str  # alias kind or "fuzzy"


@dataclass(frozen=True)
class Ambiguity:
    mention: str
    candidates: list[Entity]

    def question(self) -> str:
        names = [c.name for c in self.candidates[:5]]
        listed = ", ".join(names[:-1]) + f" or {names[-1]}" if len(names) > 1 else names[0]
        return f'Which "{self.mention}" do you mean: {listed}?'


@dataclass
class Resolution:
    players: list[Entity] = field(default_factory=list)
    teams: list[Entity] = field(default_factory=list)
    ambiguous: list[Ambiguity] = field(default_factory=list)

    def ids(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        if self.players:
            out["players"] = [e.id for e in self.players]
        if self.teams:
            out["teams"] = [e.id for e in self.teams]
        return out


class EntityResolver:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self.player_alias: dict[str, set[int]] = defaultdict(set)
        self.team_alias: dict[str, set[int]] = defaultdict(set)
        self.kind: dict[tuple[str, int, str], str] = {}
        self.player_name: dict[int, str] = {}
        self.team_name: dict[int, str] = {}
        self.by_last: dict[str, list[int]] = defaultdict(list)
        self.recency: dict[int, int] = {}
        for pid, name, last, to_year in con.execute(
            "select player_id, name, last_name, to_year from semantic.players"
        ).fetchall():
            self.player_name[pid] = name
            self.recency[pid] = to_year or 0
            if last:
                self.by_last[norm(last)].append(pid)
        for pid, alias, kind in con.execute(
            "select player_id, alias, kind from semantic.player_aliases"
        ).fetchall():
            a = norm(alias)
            self.player_alias[a].add(pid)
            self.kind[("player", pid, a)] = kind
        for tid, name in con.execute(
            "select team_id, full_name from semantic.teams where is_current"
        ).fetchall():
            self.team_name[tid] = name
        for tid, alias, kind in con.execute(
            "select team_id, alias, kind from semantic.team_aliases"
        ).fetchall():
            a = norm(alias)
            if tid in self.team_name:
                self.team_alias[a].add(tid)
                self.kind[("team", tid, a)] = kind
        self._fuzzy_keys = [a for a in self.player_alias if " " in a]

    # -- helpers ---------------------------------------------------------------------------------
    def _player(self, pid: int, mention: str, how: str) -> Entity:
        return Entity("player", pid, self.player_name.get(pid, str(pid)), mention, how)

    def _team(self, tid: int, mention: str, how: str) -> Entity:
        return Entity("team", tid, self.team_name.get(tid, str(tid)), mention, how)

    def _ranked(self, pids: list[int]) -> list[int]:
        return sorted(pids, key=lambda p: (-self.recency.get(p, 0), self.player_name.get(p, "")))

    def _exact(self, span: str, mention: str) -> tuple[list[Entity], Ambiguity | None] | None:
        players = self.player_alias.get(span, set())
        teams = self.team_alias.get(span, set())
        if not players and not teams:
            return None
        # A unique-surname alias only counts when the word is capitalized ("Free" the player,
        # not "free throw"; "Center", "Season" are surnames too).
        if players and not mention[:1].isupper():
            players = {p for p in players if self.kind[("player", p, span)] != "last name"}
            if not players and not teams:
                return None
        if len(players) + len(teams) == 1:
            if players:
                pid = next(iter(players))
                return [self._player(pid, mention, self.kind[("player", pid, span)])], None
            tid = next(iter(teams))
            return [self._team(tid, mention, self.kind[("team", tid, span)])], None
        cands = [self._player(p, mention, "alias") for p in self._ranked(list(players))]
        cands += [self._team(t, mention, "alias") for t in sorted(teams)]
        return [], Ambiguity(mention, cands)

    def _shared_name(self, words: list[str], mention: str) -> Ambiguity | None:
        """A bare last name, or initial + last name, that several players share."""
        if len(words) == 1:
            pids = self.by_last.get(words[0], [])
        elif len(words) == 2 and re.fullmatch(r"[a-z]\.?", words[0]):
            pids = [
                p
                for p in self.by_last.get(words[1], [])
                if norm(self.player_name[p]).startswith(words[0][0])
            ]
        else:
            return None
        if len(pids) < 2:
            return None
        return Ambiguity(
            mention, [self._player(p, mention, "shared name") for p in self._ranked(pids)]
        )

    def _fuzzy(self, span: str, mention: str) -> Entity | None:
        hit = process.extractOne(
            span, self._fuzzy_keys, scorer=fuzz.ratio, score_cutoff=FUZZY_THRESHOLD
        )
        if hit is None:
            return None
        pids = self.player_alias[hit[0]]
        if len(pids) != 1:
            return None
        return self._player(next(iter(pids)), mention, "fuzzy")

    # -- main ------------------------------------------------------------------------------------
    def resolve(self, question: str) -> Resolution:
        raw = [m.group(0) for m in _TOKEN.finditer(question)]
        words = [norm(t) for t in raw]
        used = [False] * len(words)
        res = Resolution()

        def take(i: int, j: int) -> None:
            for k in range(i, j):
                used[k] = True

        for n in range(MAX_SPAN, 0, -1):
            for i in range(len(words) - n + 1):
                if any(used[i : i + n]):
                    continue
                span_words = words[i : i + n]
                if n == 1 and span_words[0] in QUESTION_WORDS:
                    continue
                span = " ".join(span_words)
                mention = " ".join(raw[i : i + n]).rstrip("?.,!")
                hit = self._exact(span, mention)
                if hit is not None:
                    found, amb = hit
                    for e in found:
                        (res.players if e.kind == "player" else res.teams).append(e)
                    if amb is not None:
                        res.ambiguous.append(amb)
                    take(i, i + n)
                    continue
                if n <= 2:
                    amb = self._shared_name(span_words, mention)
                    if amb is not None and raw[i + n - 1][:1].isupper():
                        res.ambiguous.append(amb)
                        take(i, i + n)
                        continue
                if (
                    n == 2
                    and all(raw[k][:1].isupper() for k in (i, i + 1))
                    and not any(w in QUESTION_WORDS for w in span_words)
                ):
                    fz = self._fuzzy(span, mention)
                    if fz is not None:
                        res.players.append(fz)
                        take(i, i + n)
        res.players = _unique(res.players)
        res.teams = _unique(res.teams)
        return res


def _unique(entities: list[Entity]) -> list[Entity]:
    """Each entity once, in question order."""
    seen: set[int] = set()
    out = []
    for e in entities:
        if e.id not in seen:
            seen.add(e.id)
            out.append(e)
    return out
