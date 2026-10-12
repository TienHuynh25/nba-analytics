# 0009 — NBA.com player career-stat source gaps

- Tasks: 1.6 (backfill), 1.16 (marts), T-GAP (implementation), T-GAP2 (amendment); PM decisions D-011, D-013
- Date: 2026-10-11
- Status: accepted (owner)
- Amended 2026-10-11 (see the Amendment at the end). Where the two differ, the Amendment wins: 265 player-seasons and 211 players, not 243 player-seasons.

## Context

All figures below are from `docs/pm/evidence/T-1.6a.md` (E) and `docs/pm/evidence/T-1.6a-missing.csv` (CSV).

- The player list has 5,243 ids; 5,024 have a `playercareerstats` file, so 219 do not (E, AC-1).
- `--status` counts 3 endpoints x 5,243 = 15,729 units. 15,509 are done, 220 pending: 219 `playercareerstats` plus 1 `commonplayerinfo` (player 200603) (E, AC-1).
- Of the 219: 203 played in the game logs (1,841 games, 33 seasons); 16 have no games (all 2026 signees) (E, AC-2).
- They failed with "missing resultSets" or "empty body" while 5,000 neighbours succeeded. 22 of 241 recovered on retry, so 219 are persistent (E, AC-4).
- Impact: 240 regular-season player-seasons of 25,736 in the game logs (0.93%). No season's top-10 leaders are affected. Career totals, rosters and per-player lookups are (E, AC-3).

## Decision

Accept these gaps as reviewed NBA.com source gaps and document them. Do not derive the missing rows from game logs and do not add a fallback source. `player_season` keeps the source's total row, and careers sum only those rows (CLAUDE.md invariant).

## Why

- Game-log sums would put numbers beside NBA.com's rows that NBA.com never published. That breaks "numbers come from the source's total row" and the traded-player rule.
- The rows lost are low-minute fringe players (max 267 pts in one season; E, AC-3), so a leader answer is never wrong.
- A second source would need its own reconciliation and terms check for under 1% of player-seasons.
- A listed, tested gap is safe: a wrong or new gap fails the build.

## Consequences

Spec for the implementer (T-GAP):

- **Seed** `transform/seeds/known_player_career_gaps.csv`, columns `player_id,endpoint,class,gamelog_games,gamelog_seasons,note,reviewed`.
  - `endpoint` is `playercareerstats` (219 rows) or `commonplayerinfo` (1 row: 200603).
  - `class` is `played-in-gamelogs` (203), `no-games` (16) or `commonplayerinfo`.
  - Values for the 219 come from the CSV (`gamelog_games`, `gl_seasons`). One note per row, `reviewed` is `2026-10-11`.
- **Backfill status.** `make backfill-status` reads the seed and prints done, accounted gaps and pending separately. Accounted = 15,509 + 220 = 15,729 of 15,729. Pending is 0. An id that fails and is not in the seed stays pending.
- **Reconciliation test.** Compare player-seasons in `player_season` with player-seasons in `player_game` (same season type). Any difference not in the seed fails. The listed difference must match too: 240 regular-season player-seasons for 203 players, plus the playoff ones for 2 players.
- **App behaviour.** A listed player has no `player_season` row, so tools return an empty result, never 0. The answer says there is no coverage for that player from NBA.com. The verifier is unchanged. Leaders, totals and careers do not change; season sums over players can be low by up to 0.7% of games (2021-22) (E, AC-3).
- **Recovery.** If NBA.com later returns an id, backfill lands it, and that id's row is removed from the seed in the same change. The test fails while a recovered id is still listed.

T-GAP acceptance checks:

1. The seed has 220 rows, unique on (`player_id`, `endpoint`), with a non-empty note and `reviewed` on each. Class counts are 203 / 16 / 1.
2. `make backfill-status` shows 15,729 of 15,729 accounted, 0 pending, on the current raw cache.
3. The reconciliation test passes on the full build, and fails when one seed row is deleted (checked once by hand or by a unit test on the fixture).
4. `get_player_stats` and `get_career` for a listed id (for example Justin James) return an empty result with a no-coverage message, and `uv run pytest -m "not dbt"` passes with the verifier untouched.
5. The test also fails if a listed id has a `player_season` row.

Proposed one-line addendum for `ingest/ENDPOINTS.md` (not applied): "playercareerstats returns no data for 219 persistent player ids (203 with game-log games, 16 without) and commonplayerinfo for 200603; all are listed in `known_player_career_gaps.csv` (decision 0009)."

Risks: the cause on NBA.com's side is unknown, so more ids may fail later. Each one then fails the build until reviewed.

## Amendment 2026-10-11 (owner option B, D-013)

Sources: T-1.6b = `docs/pm/evidence/T-1.6b.md`, T-GAP = `T-GAP.md`, T-KLEB = `T-KLEB.md` (same folder). The original decision stands: accept, document, no derived rows, no second source.

### What the first pass missed

- The 219 ids were found from missing files only. A file that came back successful but empty was counted as done (DEF-011, R-011).
- 124 raw files have no regular-season totals. 116 are fully empty and 8 have college or playoff rows only. Of the 116, 115 never played; **Kleber (1628467) has 531 games over 9 seasons** (T-1.6b, AC-1).
- Reconciling against the full dev build found 22 more game-log player-seasons with no `player_season` row (T-1.6b, AC-2; T-GAP, OPEN).

### New classes (all 22 player-seasons are outside the 219)

| Class | Player-seasons | Players | Detail |
|---|---|---|---|
| `empty-response` | 15 (9 RS + 6 PO, 2017-18 to 2025-26) | 1 | Kleber. T-GAP said 16; RS and PO counted apart it is 15 (T-1.6b, AC-2) |
| `early-era-partial` | 6 | 6 | 76998 (1956-57 RS), 77041 (1951-52 PO), 77211 (1946-47 RS), 77899 (1960-61 RS), 78072 (1956-57 RS), 78585 (1976-77 PO). Each has other `player_season` rows (T-1.6b, AC-2) |
| `other` | 1 | 1 | 79635, 1954-55 RS, 63 games, no `player_season` row, not in `marts.players` (T-1.6b, AC-2) |

### Corrected totals (T-1.6b, AC-2)

- 243 listed player-seasons (240 RS + 3 PO, original seed) + 22 new = **265 player-seasons**.
- 203 players in the original played-in-gamelogs class + 8 new (Kleber, 79635, 6 early-era ids; 1 + 1 + 6) = **211 players**.
- The 16 no-games ids and commonplayerinfo 200603 have no player-seasons, so they stay in the seed but do not change these counts.
- Share: worst season 2021-22 has 33 of 789 rows (4.2%) and 0.42% of RS points (T-1.6b, AC-4).

### Kleber outcome (T-KLEB)

One re-fetch on 2026-10-11 returned **STILL-EMPTY**: every totals set has 0 rows. He stays a documented gap, class `empty-response`. The only active 2025-26 player affected is Kleber; anything asked about him has no season totals (T-1.6b, AC-4).

### Impact (T-1.6b, AC-4)

- 265 synthetic player_season rows were added and top 10 compared: no change in 30 stat/mode/scope combinations. Playoff leaders were not checked.
- `records` has 54 rows, all single-game from `player_game`; none belong to a gap player.
- A gap player's own lines and career totals are absent or low. Rankings are unaffected.

### Reverse direction (DEF-012)

22 `player_season` rows (13 players) have no game-log rows, all before 1996-97: 1940s 3, 1950s 5, 1990s 14 (T-1.6b, AC-3). Cause: partial game-log coverage. Not chased and no value changes, because `player_season` is the source of truth. Pinned as a known list so a new one fails the test.

### T-GAP2 spec (developer, then independent QA)

Files likely touched: `app/tools/stats.py`, `ingest/backfill.py`, `ingest/career_gaps.py`, the seed, `tests/test_career_gaps.py`, the fixture export. No change to `app/verifier.py`, `metrics/` or `transform/semantic/`.

1. **Wording.** For a seeded player and season, empty results say "The source has no season totals for this player." Replace the text at `app/tools/stats.py:83-92`, `:394` (may use "players" and the ids) and `:628`. Unseeded players keep today's text. Tests through `get_player_stats`, `get_career` and `compare` assert the sentence for Kleber and assert the old "games for this player" text is gone for him. The `app/format.py:68` text "No rows." stays: a test checks the fallback table for Kleber contains it together with the new sentence. The app reads the gap list from the snapshot (a seed table), not from `ingest/`; the SQL fallback allowlist (`transform/semantic_allowlist.txt`) does not change.
2. **Empty-but-successful check.** `make backfill-status` flags a `playercareerstats` file with no `SeasonTotalsRegularSeason` rows when the player has regular-season game-log games (read from the dev or current build; say "skipped" if none), unless seeded. Tests on synthetic files: Kleber-like unseeded is flagged; seeded is not; a never-played player is not (115 cases); Vildoza 1630492 (playoff-only, 7 games) is not. On the real cache: 0 flagged after step 3, and 1 (Kleber) with his row removed from a scratch seed.
3. **Seed.** `known_player_career_gaps.csv` keeps its 220 rows and gains columns `season,season_type` (blank on whole-player rows) plus the 22 new rows, one per player-season, so 242 rows. Classes: 203 / 16 / 1 as before plus `empty-response` 15, `early-era-partial` 6, `other` 1. Each row has a non-empty note and `reviewed` 2026-10-11. The seed covers 265 player-seasons and 211 players; a test recomputes both numbers from the seed. Unique on (`player_id`, `endpoint`, `season`, `season_type`).
4. **Reconciliation.** The `xfail` at `tests/test_career_gaps.py:128` is removed. With `NBA_RECON_DB=data/build/dev.duckdb`, `reconcile_player_seasons` returns unexplained 0, listed_gap 265, listed_with_rows 0. Deleting any one new seed row makes it fail. The 22 reverse-direction rows are pinned and a 23rd fails.
5. **Status math.** `make backfill-status` still shows 15,729 of 15,729 accounted, 0 pending. The 22 new rows are not endpoint units (Kleber's file counts as done), so the total does not change.
6. **Untouched.** `git diff --stat` for `app/verifier.py`, `metrics/`, `transform/semantic/` is empty; `make check` passes.
7. **Fixture.** The fixture export holds the seed table so the tool tests run without the full build.

Proposed addendum for `ingest/ENDPOINTS.md` (not applied): "playercareerstats can return a successful but empty response (every set 0 rows) for a player with games (Maxi Kleber 1628467, one re-fetch on 2026-10-11 stayed empty). Raw files with no regular-season totals must be checked against the game logs; reviewed gaps are in `known_player_career_gaps.csv` (decision 0009)."

Risks: empty responses may recur for other ids on a refresh; check 2 turns that into a flag instead of silence. Season sums over players can still be low in a few seasons; the worst case is in the share line above.
