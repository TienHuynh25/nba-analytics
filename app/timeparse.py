"""Relative-time resolution against the snapshot, in US Eastern time (task 3.7).

"Today" is the manifest's ``as_of_date``, never the wall clock. "Last night" is the day before
it. "This season" is the season in progress on ``as_of_date``, or, in the off-season, the season
that just ended. Phrases resolve to explicit seasons, season types and dates, which then fill tool
arguments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# A season "starts" for date purposes on Aug 1: from then until the first game in October, the
# coming season is not yet in progress, so "this season" still means the one that just ended.
SEASON_ROLLOVER_MONTH = 8


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def season_start(label: str) -> int:
    return int(label[:4])


@dataclass(frozen=True)
class SnapshotClock:
    """What "now" means: the snapshot's as_of_date and the newest season with games."""

    as_of_date: date
    latest_season: str  # newest season with at least one game in the snapshot

    @property
    def today(self) -> date:
        return self.as_of_date

    @property
    def last_night(self) -> date:
        return self.as_of_date - timedelta(days=1)

    @property
    def this_season(self) -> str:
        # The season in progress, or in the off-season the one that just ended.
        return self.latest_season

    @property
    def last_season(self) -> str:
        return season_label(season_start(self.this_season) - 1)


@dataclass(frozen=True)
class TimeRef:
    season: str | None = None
    season_type: str | None = None  # None = registry default (Regular Season)
    date: date | None = None
    seasons: tuple[str, str] | None = None  # inclusive range
    phrase: str | None = None


_YEAR_SEASON = re.compile(r"\b(?:in |the )?(\d{4})-(\d{2})\b")
_SEASON_ENDING = re.compile(r"\bin (\d{4})\b")
_SINCE = re.compile(r"\bsince (\d{4})\b")
_DECADE = re.compile(r"\b(?:the )?(\d{2,4})s\b")
_LAST_N_SEASONS = re.compile(r"\b(?:last|past) (\d+|five|three|two|ten) seasons\b")
_WORDS = {"two": 2, "three": 3, "five": 5, "ten": 10}


def resolve(text: str, clock: SnapshotClock) -> TimeRef:
    """Resolve the first relative or explicit time phrase in ``text``."""
    t = text.lower()
    playoffs = "playoff" in t or "finals" in t
    st = "Playoffs" if playoffs else None
    if "last night" in t:
        return TimeRef(season=clock.this_season, date=clock.last_night, phrase="last night")
    if re.search(r"\btoday\b|\btonight\b", t):
        return TimeRef(season=clock.this_season, date=clock.today, phrase="today")
    m = _YEAR_SEASON.search(t)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return TimeRef(season=f"{m.group(1)}-{m.group(2)}", season_type=st, phrase=m.group(0))
    m = _SINCE.search(t)
    if m:
        # "Since 2010" means 2010-11 onward (spec gold rule Q59).
        return TimeRef(
            seasons=(season_label(int(m.group(1))), clock.this_season),
            season_type=st,
            phrase=m.group(0),
        )
    m = _DECADE.search(t)
    if m and len(m.group(1)) in (2, 4):
        y = int(m.group(1))
        y = y if y > 100 else (1900 + y if y >= 40 else 2000 + y)
        if y % 10 == 0:
            # "The 1990s" means 1990-91 to 1999-00 (spec gold rule Q62).
            return TimeRef(
                seasons=(season_label(y), season_label(y + 9)), season_type=st, phrase=m.group(0)
            )
    m = _LAST_N_SEASONS.search(t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _WORDS[m.group(1)]
        end = season_start(clock.this_season)
        return TimeRef(
            seasons=(season_label(end - n + 1), season_label(end)),
            season_type=st,
            phrase=m.group(0),
        )
    if re.search(r"\blast (season|year)\b|\blast season's\b|\blast year's\b", t):
        return TimeRef(season=clock.last_season, season_type=st, phrase="last season")
    if re.search(r"\blast nba finals\b|\bmost recent (nba )?finals\b|\blast finals\b", t):
        # The last completed Finals: this season's if its playoffs are in the snapshot, else
        # last season's. Callers check the snapshot; default is last season's (eval rule G8).
        return TimeRef(season=clock.last_season, season_type="Playoffs", phrase="last Finals")
    m = _SEASON_ENDING.search(t)
    if m:
        # "In 2024" means the season that ended in 2024 (spec gold rule Q79).
        return TimeRef(season=season_label(int(m.group(1)) - 1), season_type=st, phrase=m.group(0))
    if re.search(r"\bthis (season|year)\b|\bcurrent(ly)?\b|\bright now\b|\bnow\b", t):
        return TimeRef(season=clock.this_season, season_type=st, phrase="this season")
    return TimeRef(season_type=st)
