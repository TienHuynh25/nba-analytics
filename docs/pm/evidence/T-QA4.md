# T-QA4 evidence (QA, independent verification of SEC-001..009 and governance condition 5)

Scripts (scratch, new for this task): scratchpad/qa3/{sec1,sec5,sec3,sec4,sec6,mutplug}.py. Logs T-QA4-1..12.log.

## AC-1 SEC-001 (T-QA4-1.log)
27 exploit variants (review exploit, duckdb_tables/databases, pg_settings, information_schema, own-name in body, forward ref, recursive, sibling and nested scopes, quoted, mixed case, schema-qualified, system.main): 27/27 rejected. 6 legit CTE shapes still accepted. Corpus docs/pm/evidence/seed-queries.sql: 75 queries, old guard (git show 4c08895) vs new: 75/75 accepted with byte-identical output SQL. Recursive CTEs are now rejected (documented by the developer; not in the corpus).

## AC-2 SEC-002
31 LIMIT forms x 4 wrappers (plain, UNION ALL, CTE, ORDER BY) on the fixture: 0 results over 100 rows. LIMIT 100%, 100 PERCENT, 5000, $1, ?, (SELECT 5), (SELECT 5000), -1, 50+50000, 1e5, 100.5, WITH TIES, FETCH FIRST 90 PERCENT, BY, OFFSET combos all become LIMIT 100 (OFFSET kept); 0x10 rejected at parse. fetchmany(MAX_ROWS) in run_with_timeout and tests exist.

## AC-3 SEC-005 (T-QA4-2.log, T-QA4-3.log)
132 depth probes (12 constructs x 11 depths 10..2000): 0 crashes, only OK or GuardError. Depth-800 parens, 10k tokens, >4000 chars, unterminated string/comment, fullwidth, homoglyph: GuardError. 44 hostile queries from T-QA3: 44/44 rejected; 21 allowed set-operation cases unchanged.
Note: NUL byte and lone surrogate pass the guard but fail later (DuckDB ParserException; UnicodeEncodeError is not a duckdb.Error and escapes SqlFallback.answer). check(None) raises TypeError (type-contract violation only).

## AC-4 SEC-003 (T-QA4-4.log)
Patched-dbt build of 10 snapshots in a scratch tree, publish + prune. Through connect_read_only: COPY to shots/x.csv, COPY into season dir, overwrite existing parquet, EXPORT DATABASE into shots: IOException; COPY to snapshot dir or /tmp: PermissionException; SET allowed_directories blocked. os-level create, mkdir, append, unlink in shots: PermissionError. Modes: every file 0444 and dir 0555 (0 exceptions), hard-linked shot nlink=7, still 0444. Prune keeps 7 plus current, removes sealed old folders. _remove_tree(current) refused; prune keep=0 never removes current, and current stays sealed. Sealed BUILDING leftover is cleaned and rebuilt; a build failing after files are sealed is removed. pytest --basetemp run twice (test_sec3_hardening, test_snapshots, test_snapshots_rollback): second run wipes the first, 0 unwritable dirs left (T-QA4-6.log).

## AC-5 SEC-004 (T-QA4-5.log)
App holds current and the rollback target with the locked connection: health check passes; corrupted current rolls back to the target held locked (nba_20260902). Health check first, then app connect: lockdown still applies (COPY fails).

## AC-6 SEC-006 (T-QA4-7.log, T-QA4-8.log)
Real franchisehistory raw file, tampered header (quote, space, semicolon, double quote, backslash, newline, non-ASCII, empty, dash): ContractError with default validator and with validator=None (header regex). Renamed column, short row, object in cell: ContractError by default. Quote in work path lands. ingest/land.py default is `validator=validate`; snapshots.build and ingest/fixture call land() with the default. Test that still exercises the default: tests/test_sec3_hardening.py::test_land_rejects_file_that_breaks_its_contract. Own mutation (plugin sets the default to None): exactly that test fails, so it carries the coverage. The validator=None edits in test_land_and_schema_gen.py affect only synthetic 4-column flattening tests; assertions unchanged.

## AC-7 SEC-009 (T-QA4-4.log)
Rejected at validate_id, build, Snapshot ctor, point_current and the CLI (exit 2): "..", "../x", "../../etc", absolute paths, uppercase, empty, spaces, slashes, leading dot, trailing newline, dot, non-ASCII, dash, NUL. Symlinked snapshot folder: build and _remove_tree raise SnapshotIdError, outside folder untouched. Manifest id != folder, and "../../evil": load/ctor raise; published() skips it, prune ignores it. "current" as an id: SnapshotIdError.
GAP: a 200-char (and 300-char) lowercase id is accepted (regex has no length limit); 200 builds, 250 raises OSError ENAMETOOLONG instead of SnapshotIdError. No escape, so S4.

## AC-8 SEC-007/008 (T-QA4-9.log)
ci.yml diff: top-level `permissions: contents: read`, checkout `persist-credentials: false`, both actions pinned by SHA. gh api: checkout 11d5960a... = tag v4.4.0 (head of v4); setup-uv d0cc045d... = tag v6.8.0 (head of v6). `flags: send_anonymous_usage_stats: false` is in transform/dbt_project.yml; `dbt --debug parse` exit 0 shows 'send_anonymous_usage_stats': 'False'; data/build/dev.duckdb mtime unchanged.

## AC-9 condition 5 (T-QA4-10.log)
Copy of dev.duckdb and landing.duckdb in scratch, NBA_SNAPSHOT_PATH/NBA_LANDING_PATH from transform/profiles.yml: `dbt test` on the six marts PASS=30 ERROR=0. Planted: (a) player_game row with id 99999999: relationships FAIL 1; (b) player 720 (class played-in-gamelogs) removed from players: FAIL 36; (c) control, restored: PASS 9/9 (79635 still excused). Extra: orphan rows in player_titles, team_aliases, player_advanced and player_season_stint.team_id each fail their new relationships test. (The other failing test in (a), player_points_sum_to_team_points, is caused by my duplicated row.)

## AC-10
pytest 1097 passed, 1 skipped, 1 deselected, 0 failed (T-QA4-12.log). ruff check clean, ruff format --check 198 files formatted, mypy no issues in 118 files.

## AC-11
`git diff --stat f961f25` on app/verifier.py, metrics/, transform/semantic, transform/seeds, semantic_allowlist.txt, eval/cases.yaml: empty; no tracked changes there. Changed since f961f25 and not security-batch: ingest/contracts.py, gen_schemas.py, two schemas, ENDPOINTS.md, test_contracts.py (T-CONTRACT, verified in T-QA3). Removed lines in tests: one renamed test (replaced by a stricter one) and one land.land call that gained validator=None. No assertion weakened; no existing test_sql_guard test line removed. Untracked: tests/test_sec3_hardening.py (24 tests) and the stray duplicates (` 2`, ` 3`, ` 4`, ` 5`), still not cleaned.

## AC-12
SEC-001..009 and condition 5: VERIFIED-FIXED (SEC-009 with the S4 length note, SEC-005 with the S4 downstream note).
