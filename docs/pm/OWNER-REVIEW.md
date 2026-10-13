# Owner review: Phase 2 (test set and gold answers)

Everything here needs your approval, a change, or an answer. Each item has a recommendation; reply "approve all" to accept every recommendation, or list the numbers you want changed. Sources: `eval/gold/gold_report.md` (gold interpretations), `eval/crosscheck/report.md` (independent cross-check, 320 units), `eval/reports/paraphrase-prescreen.md`.

## A. Gold interpretations (the answer key must match what you mean)

| # | Case | What the gold does | Recommend |
|---|---|---|---|
| A1 | Q05 | "Rookie season" = the player's first regular season in `player_season` | Approve |
| A2 | Q08 | Counts the 2025-26 Lakers stint only; gold entities list the player, not the Lakers | Approve (add the Lakers as an entity only if you want team resolution checked here) |
| A3 | Q27 | One row per season for each player's first two seasons (the compare tool's scope), not a two-season average | Approve |
| A4 | Q35 | Career triple-doubles from box scores (partial before 1996-97): Westbrook 209, Jokic 198 | Approve, then do the manual Basketball-Reference check in section B |
| A5 | Q37 | Registry career minimum is "400 games OR 10,000 points" (unconfirmed); an earlier query used AND. Same leader either way. NBA.com shows Jordan and Chamberlain both at 30.1; Jordan leads on exact values (30.123 vs 30.066) | Confirm OR is the Spec's rule. The answer may state Jordan 30.1; mentioning the tie is optional |
| A6 | Q43 | Wins and losses required for all 15 teams; win percentage allowed as context | Approve |
| A7 | Q48 | Warriors per-game leader. With NBA.com's "would still lead" rule (CLAUDE.md) the leader is Curry (43 games, 26.6). A plain 70% games rule would give Podziemski (my earlier seed query). | Approve Curry: it follows the invariant in CLAUDE.md |
| A8 | Q55 | Points, rebounds and assists leaders of each 2026-04-12 game; tied leaders all named | Approve |
| A9 | Q57 | Required number is the count of overtime games; the game list is context | Approve |
| A10 | Q62 | Required: 1990-91 to 1999-00 and 2025-26 values; "higher than the 1990s" compares 2025-26 with the best 1990s season. The row scorer currently requires all 36 seasons, not just these 11 | Approve; require only the 11 seasons and treat the other 25 as allowed context (less brittle) |
| A11 | Q64 | "Gone up every season" = strictly higher than the previous season, every season | Approve |
| A12 | Q71 | TS% minimum (70% of games and 300 FGM, decision 0007) unconfirmed | Approve provisionally; confirm in plan task 3.2 |
| A13 | Q72 | Required: Jokic's usage rate; the centers' average (500+ minutes) is context | Approve |
| A14 | Q73 | Attempts in every zone required; share is context | Approve |
| A15 | M03 | Turn 2: one row per season for each player's last three seasons; pooled 3P% is context | Approve |
| A16 | M06 | Turn 3 requires the 2024-25 rating only (turn 2 gave 2025-26) | Approve |
| A17 | H01-H04 | Clarify questions list every player the name can resolve to, in any era (decision D-027): H04 has 11 J* Williams though only 2 played in 2025-26; H01 includes Justin Holiday (last season 2022-23). This mirrors the app's entity resolver. | Approve. Narrowing to "this season" would change the product's behaviour, not just the gold |

## B. Check by hand on Basketball-Reference (nothing was scraped)

Check their terms of use first (decision 0008). NBA.com could not verify these:
- Q34 (+ paraphrases): Wilt Chamberlain scored 100 points on 1962-03-02. Look at the single-game scoring records page.
- Q35 (+ paraphrases): Westbrook has the most career triple-doubles (209). Look at the career triple-double leaders page, because box scores before 1996-97 are partial.

## C. Paraphrases and judge labels

- 170 paraphrases and 15 pre-screen flags on 14 of them are in `eval/reports/paraphrase-prescreen.md`. Approve or reject each. You are the reviewer under decision 0008.
- Later (task 2.20): label 30 answers by hand to calibrate the judge.

## D. Records table (T-REC)

`records_curated` is empty. Pre-1996 records (early single-game records, career triple-doubles) cannot be answered until it is filled. Tell me which records you want and that you have checked the terms; I will have them entered by hand with a source URL and valid-from date on each row.

## E. Other open decisions

| # | Item | Recommend |
|---|---|---|
| E1 | Anomaly check (R-001): the nightly row-count check uses a plain +-10% rule, so one missing game on a 15-game day is not flagged (two are). Add an absolute floor of one game? | Leave as is (it matches the Spec) |
| E2 | Plan filenames (R-004): the plan names `ingest/publish.py` and `ingest/rollback.py`; the code is in `ingest/snapshots.py` | Update the plan text |
| E3 | 51 stray Finder duplicates (`* 2.*`, `* 3.*`), including `records_curated 2.csv` that may hold your data | Let me diff each against its original and report which hold unique content; you decide the rest |
| E4 | Sourcing pass (task 2.4): Google Trends, People-also-ask, r/nba threads need web research my agents cannot do | Skip for v1 (nothing in the gold depends on it) |
| E5 | Acknowledgements already given in chat: D-014 (partial-career note) and D-019 (three low security items deferred to Phase 3) | Nothing to do |
