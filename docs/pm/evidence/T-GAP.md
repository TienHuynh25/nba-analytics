# T-GAP evidence

- Seed: transform/seeds/known_player_career_gaps.csv, 220 rows (203 played-in-gamelogs, 16 no-games, 1 commonplayerinfo). Log: T-GAP-1.log.
- Status: players 15509 + 220 documented = 15729 / 15729. With player 1852 removed from a scratch copy: 15728, MISSING 1 (T-GAP-1.log).
- Full suite: `uv run pytest -m "not network" --ignore-glob='* [23].py'` 862 passed, 1 skipped, 1 xfailed; ruff and mypy clean (T-GAP-2.log).
- OPEN: reconciliation on the full dev build (NBA_RECON_DB=data/build/dev.duckdb) finds 22 unexplained game-log player-seasons outside the 219:
  - player 1628467 Maxi Kleber, 16 player-seasons 2017-18 to 2025-26: playercareerstats returned a successful but EMPTY response (all result sets 0 rows), so he is not in the missing-file list.
  - player 79635, 1954-55 RS (63 games): no player_season row.
  - 5 early-era partial gaps: 77211 1946-47 RS, 77041 1951-52 PO, 76998 and 78072 1956-57 RS, 77899 1960-61 RS, 78585 1976-77 PO (these players have other player_season rows).
  - Reverse direction (player_season row without game-log rows, 1946-47 to 1995-96) also exists; not in 0009's scope.
- The 3 playoff player-seasons (2 players: 1852, 1629714) and 240 RS player-seasons (203 players) match the full build.
