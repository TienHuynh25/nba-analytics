"""Nightly incremental extract with a rolling correction window (tasks 1.7 and 1.8).

Each run re-fetches the last ``correction_window_days`` (7) of games, not only new ones, because
NBA.com revises box scores after games. Every re-fetch writes a new raw file (the store never
overwrites). Staging keeps the latest fetch per key, so a corrected row replaces the old one in the
next build.

Per run, for the season in progress:

1. team and player game logs for the window, for every season type active in it;
2. season totals (``playercareerstats``) for every player who appeared in the window;
3. season-level tables that change daily: standings and advanced team and player stats;
4. shots for every team that played in the window;
5. the player list, plus ``commonplayerinfo`` for players not yet cached (new rookies).

Before any of this is used, :func:`check_game_counts` compares fetched games per day with the
league schedule and stops the run when a day is off by more than the configured tolerance (10%).
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from ingest.endpoints import SPECS, result_sets, season_label
from ingest.raw_store import RawStore

log = logging.getLogger(__name__)

RS, PO, PI, IST = "Regular Season", "Playoffs", "PlayIn", "IST"
COUNTED_PREFIXES = ("002", "004", "005", "006")  # regular season, playoffs, Play-In, Cup final


class AnomalyError(RuntimeError):
    """Fetched games per day differ from the schedule by more than the tolerance."""


@dataclass
class IncrementalResult:
    season: str
    window: tuple[date, date]
    games_by_day: dict[date, set[str]] = field(default_factory=dict)
    players: set[int] = field(default_factory=set)
    teams: set[int] = field(default_factory=set)
    fetched: int = 0


def season_for(day: date) -> int:
    """Start year of the season a date belongs to (seasons run October to June)."""
    return day.year if day.month >= 8 else day.year - 1


def _nba_date(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def _parse_game_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def fetch_window(store: RawStore, today: date, window_days: int) -> IncrementalResult:
    start = today - timedelta(days=window_days)
    end = today - timedelta(days=1)  # "today" is the build date; its games are not final yet
    y = season_for(end)
    season = season_label(y)
    res = IncrementalResult(season, (start, end))

    for st in (RS, PO, PI, IST):
        for key in ("leaguegamelog_t", "leaguegamelog_p"):
            rec = store.get(
                SPECS[key],
                season,
                refresh=True,
                season=season,
                season_type_all_star=st,
                date_from_nullable=_nba_date(start),
                date_to_nullable=_nba_date(end),
            )
            res.fetched += 1
            for r in result_sets(rec.response)["LeagueGameLog"]:
                if key == "leaguegamelog_t":
                    day = _parse_game_date(r["GAME_DATE"])
                    res.games_by_day.setdefault(day, set()).add(r["GAME_ID"])
                    res.teams.add(int(r["TEAM_ID"]))
                else:
                    res.players.add(int(r["PLAYER_ID"]))

    if not res.games_by_day:
        log.info("no games in window", extra={"event": "incremental_empty", "season": season})

    for pid in sorted(res.players):
        store.get(SPECS["playercareerstats"], refresh=True, player_id=pid)
        res.fetched += 1

    for st in (RS, PO):
        for key in ("leaguedashteamstats_adv", "leaguedashplayerstats_adv"):
            store.get(SPECS[key], season, refresh=True, season=season, season_type_all_star=st)
            res.fetched += 1
    store.get(SPECS["leaguestandingsv3"], season, refresh=True, season=season)
    res.fetched += 1

    for st in (RS, PO):
        for tid in sorted(res.teams):
            store.get(
                SPECS["shotchartdetail"],
                season,
                refresh=True,
                team_id=tid,
                season_nullable=season,
                season_type_all_star=st,
            )
            res.fetched += 1

    players = store.get(SPECS["commonallplayers"], refresh=True, season=season)
    res.fetched += 1
    spec = SPECS["commonplayerinfo"]
    for r in result_sets(players.response)["CommonAllPlayers"]:
        pid = int(r["PERSON_ID"])
        if store.latest(spec, None, spec.params(player_id=pid)) is None:
            store.get(spec, player_id=pid)
            res.fetched += 1
    return res


def scheduled_games_by_day(schedule: Mapping[str, Any]) -> Counter[date]:
    """Count final, counted games per US Eastern date from a ``scheduleleaguev2`` body."""
    out: Counter[date] = Counter()
    for gd in schedule["leagueSchedule"]["gameDates"]:
        for g in gd["games"]:
            if g.get("gameStatus") != 3 or not str(g["gameId"]).startswith(COUNTED_PREFIXES):
                continue
            day = datetime.strptime(gd["gameDate"][:10], "%m/%d/%Y").date()
            out[day] += 1
    return out


def check_game_counts(
    fetched: Mapping[date, Iterable[str]],
    expected: Mapping[date, int],
    days: Iterable[date],
    tolerance: float,
) -> None:
    """Raise :class:`AnomalyError` if a day's fetched game count is off by > ``tolerance``."""
    bad = []
    for d in days:
        exp = expected.get(d, 0)
        got = len(set(fetched.get(d, ())))
        if exp == 0 and got == 0:
            continue
        if exp == 0 or abs(got - exp) / exp > tolerance:
            bad.append(f"{d}: fetched {got}, scheduled {exp}")
    if bad:
        raise AnomalyError("game counts off schedule: " + "; ".join(bad))
