# 0006 — Stat line convention

- Task: 2.5 (gold tool calls), used by the tools in 3.9
- Date: 2026-10-07
- Status: accepted (owner)

## Decision

A question about a player's "averages", "stats" or "stat line" is answered with these 10 metrics:
games played, minutes per game, points, rebounds, assists, steals and blocks per game, field goal
percentage, 3-point percentage and free throw percentage.

## Consequences

- Tools accept `stat_line` as shorthand for these metrics (`app/tools/schemas.py`).
- Gold calls for Q02, Q05, Q07, Q12, Q23, Q24, Q27, M02 and M07 use this list. Changing it
  means updating those gold calls and recomputing their gold values.
