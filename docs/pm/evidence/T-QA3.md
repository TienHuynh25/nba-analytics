# T-QA3 evidence (QA, independent verification of DEF-015/016/017)

Scripts (scratch, not committed): scratchpad/qa3/{whole,mut,guard,plant}.py. Logs: T-QA3-1..5.log.

## AC-1 mutation table (T-QA3-2.log)
Real raw files, in-memory mutation, `ingest.contracts.validate`. 15 cases x 14 kinds = 210 mutations, 210 caught, 0 accepted.
Kinds: object-in-cell, number->string, header swap (headers only), header+cell swap, extra column, short row, long row, renamed header, dropped column, null key, result set removed, rowSet not array, row as object, reversed columns.
Cases: commonallplayers, franchisehistory, leaguedashplayerstats_adv, leaguedashteamstats_adv, leaguegamelog_p, leaguegamelog_t, playerawards, playercareerstats, shotchartdetail, teamyearbyyearstats, commonplayerinfo (33 and 34 col), leaguestandingsv3 (87, 92, 124 col).
scheduleleaguev2 (own shape): 10 mutations caught; 2 accepted by design (empty `games` list, extra key).

## AC-2 whole cache (T-QA3-1.log)
17447 files checked, 0 rejected. Variants: commonplayerinfo CommonPlayerInfo 34 col (704 files) and 33 col (4538); standings 87 col (34), 92 col (21), 124 col (1). 3 files sampled per variant, listed in the log.

## AC-3 no loosening
`git diff 4c08895 -- ingest/schemas` changes only commonplayerinfo.json and leaguestandingsv3.json; the other 11 are byte-identical (`git show 4c08895:f | cmp`). gen_schemas.py adds one sample: ("2019-20", {"season": "2019-20"}) for leaguestandingsv3 plus a comment. The cache has the file (leaguestandingsv3/2019-20/2026-09-30/1588eba07151bc4a...json, the only 124-col file).

## AC-4 guard (T-QA3-3.log)
21 allowed cases (UNION, UNION ALL, INTERSECT, EXCEPT x plain/LIMIT 5/LIMIT 5000/ORDER+LIMIT, CTE+UNION, 3-way, plain) all executed read-only on a copy of the fixture: LIMIT capped at 100, LIMIT 5 and 7 kept. 44 hostile queries all rejected with GuardError (raw/staging/landing table in any branch, subqueries, CTE, read_csv/read_parquet/path/glob, ATTACH/COPY/PRAGMA/SET/INSTALL/CALL/EXPLAIN, stacked, comment tricks, non-allowlisted functions, main.games, catalog-qualified, quoted/mixed-case identifiers, DDL/DML with UNION).

## AC-5 DEF-017 (T-QA3-4.log)
Planted a file with the forbidden path in a scratch git tree: guard returns ['transform/dirty.sql']; clean again returns []. `git ls-files tests transform -z | xargs -0 grep -l /Desktop/` returns nothing (181 files).

## AC-6
pytest: 954 passed, 1 skipped, 1 deselected (T-QA3-5.log). ruff check clean, ruff format 190 files clean, mypy no issues in 117 files.
`git diff 4c08895 --stat` for app/verifier.py, metrics/, transform/semantic, transform/seeds, eval/cases.yaml: empty. HEAD..4c08895 also touches eval/contamination.md (T-SEEDS held-out disclosure, explained) and tests/test_career_gaps.py, tests/test_sql_guard.py, app/sql_guard.py (DEF-016/017 fixes).

## AC-7
DEF-015 VERIFIED-FIXED, DEF-016 VERIFIED-FIXED, DEF-017 VERIFIED-FIXED.
