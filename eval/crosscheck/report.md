# Gold cross-check report (T-2.7)

Author: `qa-tester` agent (independent of the gold builder). Saved by the PM because the harness blocked the agent from writing this file. Detail: `crosscheck.csv` (one row per unit), `layer_values.csv` (every required number per layer), `docs/pm/evidence/T-2.7.md` and logs `T-2.7-1..4.log`.

Snapshot: `eval_2025_26_rs` (cutoff 2026-04-12). Gold computed by `eval/gold/compute_gold.py` (T-2.6).

## Result for all 320 gold units

| Status | Units | Meaning |
|---|---|---|
| MATCH (raw recomputation and NBA.com) | 275 | Layer A and Layer B agree with gold |
| MATCH-RAW, NBA.com has no data for part | 3 | Q62 seasons 1990-91 to 1995-96: `leaguedashteamstats` has no rows; two raw sources agree |
| OWNER-MANUAL | 6 | Q34 (+p1, p2), Q35 (+p1, p2): need a manual Basketball-Reference check |
| CLASS-CHECKED (no number) | 35 | decline, not_tracked, clarify, no_verdict, knowledge: class checked against stat_availability, the Spec scope rules and the glossary chunks |
| MISMATCH | 1 | H03 (clarify candidates incomplete), DEF-024 |

## Layers

- **Layer A (no network):** recomputed every numeric Stats/Mixed gold from the raw JSON in `data/raw` with independent scratch code (not the semantic views, `gold.sql` or the tools), registry rules from `metrics/registry.yaml`. 98 numeric blocks MATCH, 2 name-only MATCH. 473 of 473 numbers matched; largest raw difference below 1e-6; no silent skips.
- **Layer B (NBA.com, 133 requests, about 102 s):** all 13 critical numeric blocks plus 91 others across 9 categories. 466 numbers OK, 6 MISSING (the Q62 seasons above), 0 differ.
- **Scope floor R-039:** box scores against `BoxScoreTraditionalV3`: 23 games (17 from 2025-26 including all 15 on 2026-04-12, and 6 earlier playoff games), 475 player lines x 16 fields, 0 mismatches (`test_boxscore_crosscheck.py`, `-m network`).

## For the owner: check manually on Basketball-Reference (nothing was scraped)

| Case | Claim | Gold | Why NBA.com cannot verify | Page type |
|---|---|---|---|---|
| Q34 (+p1, p2) | Wilt Chamberlain scored 100 points on 1962-03-02 | 100 | NBA.com's game finder returns no games before 1983-84 | single-game scoring records |
| Q35 (+p1, p2) | Russell Westbrook has the most career triple-doubles | 209 | NBA.com confirms 209 (Jokic 198), but box scores before 1996-97 are partial, so ranking him above older careers is unverified | career triple-double leaders |

## Findings

- **H03 (DEF-024, S3):** the clarify candidates for "Antetokounmpo's career rebounds" omit Kostas Antetokounmpo (id 1628961, 22 NBA games, DAL/LAL 2018-21). PM decision D-027: list every resolvable player; the T-2.6 developer fixes it and audits all clarify units.
- **Q37 (owner note):** NBA.com shows Jordan and Chamberlain both at 30.1 career points per game; Jordan leads on exact values (30.123 vs 30.066). Should the answer wording reflect the tie at one decimal?
- **Independence limits:** `playerprofilev2` answers from the same backend as `playercareerstats`, and `playerawards`, the standings order and the advanced team ratings were re-fetches of ingest endpoints; those checks are weaker evidence than Layer A and the box scores.
- **Qualification rule not independently confirmed:** the `leagueleaders` endpoint returns HTML, so our leader picks could not be compared with NBA.com's official qualified list. The registry rule was applied to NBA.com totals instead. Recheck in plan task 3.2.
- **Plan deviation (D-026):** plan 2.7 names Basketball-Reference and `eval/crosscheck/bref.csv`. Decision 0008 limits Basketball-Reference to hand entry by the owner, so the cross-check used NBA.com and independent raw recomputation (`crosscheck.csv`), and the Basketball-Reference part is the OWNER-MANUAL list above.
