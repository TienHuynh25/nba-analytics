"""Reviewed source gaps for player season totals (decision 0009), read from the snapshot.

``seeds.known_player_career_gaps`` lists players and player-seasons for which NBA.com publishes
no season totals. Snapshots built before the seed existed have no such table: no gaps then.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from app.interfaces import SnapshotStore

NO_TOTALS = "The source has no season totals for this player."
PARTIAL_CLASSES = ("early-era-partial", "other")


@dataclass(frozen=True)
class Gap:
    cls: str
    season: str  # blank: the whole player
    season_type: str


def gaps(store: SnapshotStore, player_ids: list[int]) -> dict[int, list[Gap]]:
    """``playercareerstats`` gap rows per player id (only players that have some)."""
    if not player_ids:
        return {}
    marks = ",".join("?" for _ in player_ids)
    try:
        rows = (
            store.connection()
            .execute(
                "select player_id, class, coalesce(season, ''), coalesce(season_type, '') "
                f"from seeds.known_player_career_gaps where endpoint = 'playercareerstats' "
                f"and player_id in ({marks}) order by player_id, season, season_type",
                player_ids,
            )
            .fetchall()
        )
    except duckdb.CatalogException:
        return {}
    out: dict[int, list[Gap]] = {}
    for pid, cls, season, st in rows:
        out.setdefault(int(pid), []).append(Gap(str(cls), str(season), str(st)))
    return out


def covers(gs: list[Gap], season: str | None = None, season_type: str | None = None) -> bool:
    """Is this player (and season, when given) a documented gap?"""
    return any(
        not g.season
        or season is None
        or (g.season == season and (season_type is None or g.season_type == season_type))
        for g in gs
    )


def missing_note(gs: list[Gap]) -> list[str]:
    """Note for a player who has some season totals but whose listed seasons are missing."""
    part = [g for g in gs if g.cls in PARTIAL_CLASSES and g.season]
    if not part:
        return []
    seasons = ", ".join(f"{g.season} {g.season_type.lower()}" for g in part)
    return [
        f"The source is missing season totals for this player for: {seasons}. "
        "The totals here exclude those seasons."
    ]
