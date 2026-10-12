# T-KLEB: Maxi Kleber (1628467) playercareerstats re-fetch

Outcome: **STILL-EMPTY**. One HTTP call, no retries, contract validation passed, file stored.

## Before
data/raw/playercareerstats/_all/2026-09-30/43f75bdb1a219f36.20260930T235054550943Z.json
fetched_at 2026-09-30T23:50:54Z; params {PlayerID 1628467, PerMode Totals, LeagueID 00}.
All SeasonTotals*/CareerTotals*/SeasonRankings* sets have 0 rows; only SeasonHighs and CareerHighs have 1 row.
No other Kleber file existed before.

## Command
`uv run python -I <scratchpad>/f2.py` (RawStore.get(SPECS["playercareerstats"], None, refresh=True, player_id=1628467),
NbaClient with max_retries=0 and a counting transport wrapper, validator=ingest.contracts.validate; same path as backfill.run).
Note: first two attempts failed on `import app` before any client was built (0 calls); the scratchpad script then added the repo to sys.path.

## Output
HTTP CALL 1 playercareerstats {'PlayerID': 1628467, 'PerMode': 'Totals', 'LeagueID': '00'}
STORED data/raw/playercareerstats/_all/2026-10-11/43f75bdb1a219f36.20261012T033437883480Z.json
SeasonTotalsRegularSeason 0 / CareerTotalsRegularSeason 0 / SeasonTotalsPostSeason 0 / CareerTotalsPostSeason 0 (all other totals/rankings 0)
SeasonHighs 1, CareerHighs 1; season list: []
calls 1 1   (transport count 1, client.calls 1)

## After
The contract does not reject an empty response, so a second all-empty raw file now exists (2026-10-11). Old file untouched.
Staging picks the latest fetch per key, so the new file is the one used; content is identical in effect.
