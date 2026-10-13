# T-QA6: independent verification of `eval_2025_26_rs` (plan 2.1)

Verdict: REOPENED on one S3 finding (staging schema leaks post-cutoff data inside the sealed DB). All numeric checks pass.
Scripts ran from a scratch dir with `python -I`; DB opened via `app.snapshot.connect_read_only`; no writes under data/.

| AC | Result | Log |
| --- | --- | --- |
| 1 checksums | manifest sha256 = yaml (d266ec87...0967); db + 30 shot files: 31/31 match, 0 extra files | T-QA6-1.log |
| 2 cutoff | raw team log + schedule: 002 last 2026-04-12 (1230 games), 005 2026-04-14..17, 004 2026-04-18..06-13, 006 2025-12-16. Scan of every date/timestamp/varchar column in marts, semantic, seeds, staging: marts/semantic clean (shots parquet max 2026-04-12); hits only in `staging` (see DEF) and metadata (teams.valid_to 2026-07-31, seed review dates, fetched_at) | T-QA6-2/3/5.log |
| 3 LeBron | playoffs 18 seasons/292 GP/8289 PTS/2628 REB/2095 AST/STL 493/BLK 284/TOV 1047 equal raw through 2024-25; RS 23 seasons/1622 GP/43440 PTS equal raw; semantic.player_career_stats same | T-QA6-4.log |
| 3 lines | 10 random raw player-game lines (seed 20260612), all 17 stat cols equal; 26651 RS rows = raw 26651; 5 team records (gp/W/L/PTS/home) equal raw; all 30 teams match | T-QA6-4.log |
| 3 counts | 1230 RS games, 82 gp per team. Home: 25 teams 41; 5 teams 40 + 1-3 neutral-site games (Cup semis, London/Berlin/Mexico): home+road+neutral = 82. By design, not a defect | T-QA6-4.log |
| 4 traded | 5 of 72 traded players: player_season == raw TOT row; stint sums equal totals for these (no divergence case in 2025-26); 5 divergences exist elsewhere in history. NULL rules (stl/blk <1973, 3PT <1979, +/- <1996) hold in marts and semantic; 2025-26 +/- 26669/26669 present | T-QA6-4.log |
| 5 | no `current` link; publish refuses (4 tests pass); files 0444, dirs 0555; dev.duckdb and landing.duckdb sha256 equal T-2.1-before.log | T-QA6-6/7.log |
| 6 | pytest 1123 passed, 1 skipped, 1 deselected; ruff clean; mypy 0 issues in 120 files; README states 2025-26 / day before as_of_date / 2024-25 | T-QA6-7.log |

# T-QA6b: re-verification of the FINAL pinned snapshot (after T-DET)

Verdict: DEF-020 VERIFIED-FIXED; DEF-021 VERIFIED-FIXED for the build (marts, views, shots); query-time nondeterminism remains in 12 seed queries (gold handling needed). Scripts in scratchpad qa6/ and qa6b/; all reads, scratch dbt builds only (landing copy in scratch).

| AC | Result | Log |
| --- | --- | --- |
| 1 checksums | manifest 6305f368...01e8 = yaml; db 1b51001b...4d59; 31/31 match; no extra files | T-QA6b-1.log |
| 2 leak | final DB has only marts 17, seeds 11, semantic 20 (no staging). 187 columns scanned: hits only teams.valid_to 2026-07-31 and seed review/note text. No 2025-26 Playoffs/PlayIn rows; Cup final = 1 (12-16). Awards 2025-26 in-season only (90), 0 titles. EXPORT DATABASE CSV: 0 files with the 91 sentinel ids; no 2025-26 champion/Finals MVP/MVP/All-NBA lines. Raw bytes: 17/91 sentinels, each the join of two adjacent in-cutoff ids (all 120 pattern matches: both neighbours are marts.games ids, 0 unexplained). Leaky control: 87/91, 230 occurrences, staging full of playoffs | T-QA6b-2.log, 2b |
| 3 determinism | 3 scratch dbt builds (threads 1/4/8, copy of landing.duckdb, as_of 2026-04-12): 145/145 pass each; 48 objects equal across builds in row count, ordered hash and unordered hash; 30 shot files byte-identical to each other AND to the pinned shots. Pinned vs scratch: equal in all objects except seeds.known_player_career_gaps (241 vs 242: the filtered Kleber 2025-26 Playoffs row, intended). 5 tie player-seasons: last_team_id = last stint in raw source order (WAS, LAL, PHL, DET, LAC) | T-QA6b-3.log, 3b, 3-dbt |
| 4 numeric | 46 PASS, 0 FAIL: LeBron RS 23 seasons/1622 GP/43440 PTS and playoffs 18/292/8289 equal raw; 26651 RS player-game rows; 30 teams equal raw; 1230 games, 82 per team (home 41 for 25 teams, 40 + neutral for 5: by design); 5 traded players equal source TOT; NULL rules hold; PPG Doncic 33.48, SGA 31.13, Edwards 28.80 | T-QA6b-4.log |
| 5 tools/seeds | 18 tool calls x5 on the snapshot: identical (get_career arg error was my call, not a defect). 75/75 seed queries run; row counts equal T-2.1-r1-scan.log for the 48 it lists | T-QA6b-5-*.log |
| 6 seal etc | 32 files 0444, dirs 0555, no current, dev/landing sha256 unchanged, snapshot hash unchanged after tests; 25 targeted tests pass; full suite 1147 passed, 1 skipped, 1 deselected; ruff clean; mypy 0 issues in 122 files | T-QA6b-6.log |
| 7 | eval/snapshots.yaml path data/snapshots/eval_2025_26_rs, pinned true, same hashes | T-QA6b-1.log |

AC-9 seed queries needing ordering handling (20 repeat runs on the pinned file, and pinned vs scratch build):
- Rows differ at a LIMIT tie: Q40, Q75 (Q42 stable now, but its ORDER BY value has ties at the cut, so add a tie-break anyway).
- Row order only (no unique ORDER BY): Q23, Q24, Q25, Q27, Q28, Q29, Q30, Q78. Compare as sets or add ORDER BY.
- Last float digit: Q62, Q72 (parallel AVG). Round before comparing.
Not compared to the rework-1 file: its views point at the old shots path, so 48 queries error there; comparison used the scratch build instead.
