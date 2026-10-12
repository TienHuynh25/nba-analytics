# T-CONTRACT: exact contracts for varying-header endpoints (DEF-015, plan 1.4)

FROM: developer · Date: 2026-10-11 · No network, data/raw read only, no git operations.

## 1. Triage of the 32 mutations accepted in T-1.4v-2.log

| endpoint | mutation | verdict |
|---|---|---|
| commonplayerinfo | swap first two headers | defect (DEF-015), now caught |
| commonplayerinfo | type change first non-null cell (PERSON_ID int -> str) | defect, now caught |
| commonplayerinfo | add EXTRA_COL | defect, now caught |
| leaguestandingsv3 | swap first two headers | defect, now caught |
| leaguestandingsv3 | type change first non-null cell | defect, now caught |
| leaguestandingsv3 | add EXTRA_COL | defect, now caught |
| leaguestandingsv3 | truncate one row by one cell | defect, now caught |
| all 12 result-set endpoints | empty rowSet | by design here (R-013; content check lives elsewhere) |
| all 12 result-set endpoints | null in a non-key cell | by design (untracked stats are NULL) |
| scheduleleaguev2 | unexpected key in a game object | by design: hand-written schema covers only the fields the anomaly check reads (`$comment` in the schema); outside the generated machinery |

Only `commonplayerinfo` and `leaguestandingsv3` used the old "varying" branch (survey of all 17,447 raw files: every other result set has exactly one header list).

## 2. Fix

- `ingest/contracts.py` `generate_schema`: each distinct header list in the samples becomes a variant with `headers: {const: [...]}`, `minItems = maxItems = len(headers)` and `prefixItems` types taken only from that variant's samples. One variant is emitted inline (byte-identical to before for the 11 single-variant schemas); several are emitted as `anyOf`. The "shared headers + minItems" branch is gone.
- `ingest/gen_schemas.py`: added the 2019-20 `leaguestandingsv3` sample (third variant, 124 columns).
- `ingest/schemas/commonplayerinfo.json` (2 variants: 34/33 columns), `ingest/schemas/leaguestandingsv3.json` (3 variants: 87/124/92) regenerated with `gen_schemas.main` from the cache with no client (a cache miss would raise; none did). Fixture samples unchanged.
- `ingest/ENDPOINTS.md`: new section "Contract header variants (DEF-015)" with counts and the cited file.

## 3. Full raw-cache validation (log T-CONTRACT-4.log)

17,447 files checked, 0 rejected. Before the 2019-20 sample was added, one file was rejected: `data/raw/leaguestandingsv3/2019-20/2026-09-30/1588eba07151bc4a.20260930T224342622755Z.json` (real variant: restart-season seeding columns). It was added as a sample, not by loosening types.

## 4. Matrix (log T-CONTRACT-2.log)

Before: 137 cases, 105 caught, 32 accepted. After: 137 cases, 112 caught, 25 accepted (12 empty rowSet, 12 non-key null, 1 schedule extra key; all by design). Per-variant check on 5 real raw files (one per variant), 4 mutation kinds each: 20/20 caught (T-CONTRACT-5.log).

## 5. Tests

- `tests/test_contracts.py`: type change, header swap, extra column, short row, each parametrized over all 12 result-set endpoints; exact-variant shape and "headers of one variant with rows of another" for the 2 varying endpoints. Against the old schemas, 11 of these fail (T-CONTRACT-3.log); against the new schemas all pass.
- `tests/test_land_and_schema_gen.py`: the varying-column generator test now asserts swap/extra/short/long/type rejection, with empty rowSet and non-key null still accepted; added per-variant typing and single-variant-format tests.

Logs: T-CONTRACT-1 (regen), -2 (matrix), -3 (new tests vs old schemas), -4 (raw cache), -5 (variant mutations), -6 (full pytest: 954 passed, 1 skipped), -7 (ruff, format, mypy clean).
