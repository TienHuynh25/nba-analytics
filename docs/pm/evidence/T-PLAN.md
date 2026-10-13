# T-PLAN evidence: Execution Plan text update (D-032, D-029, D-026)

$ git diff --stat -- "Basketball Analytics RAG — Execution Plan.md"
 1 file changed, 21 insertions(+), 10 deletions(-)

$ grep -n "publish.py\|rollback.py" "Basketball Analytics RAG — Execution Plan.md"
332:  - Tasks 1.24 and 1.25 (D-032, R-004): the output files `ingest/publish.py` and `ingest/rollback.py` were replaced 

## Full diff (pre-edit copy vs edited plan)

```diff
--- /private/tmp/claude-501/-Users-tienhuynh-dev-nba-analytics/bb1d3a71-4e8f-41b0-b4b5-4d0c344a4c1b/scratchpad/plan_before.md	2026-10-12 22:55:37
+++ Basketball Analytics RAG — Execution Plan.md	2026-10-12 22:56:03
@@ -14,7 +14,7 @@
 | --- | --- | --- | --- |
 | Pre-work *(added by this plan)* | Close blocking decisions, set up the repo | Decisions recorded, CI green on an empty project | 2–3 d |
 | 1. Data foundation | `nba_api` ingest, JSON contracts, dbt layers, snapshot swap, stint and availability tables, starter metric registry | **Gate 1:** dbt tests pass; 20 box scores match NBA.com | 14–20 d |
-| 2. Test set and baseline | 85 seeds grown to 320 cases, pinned eval snapshot, harness, baseline score | **Gate 2:** harness runs every case on the pinned snapshot | 9–13 d |
+| 2. Test set and baseline | 85 seeds grown to 320 turn-units in 305 case items, pinned eval snapshot, harness, baseline score | **Gate 2:** harness runs every case on the pinned snapshot | 9–13 d |
 | 3. Stats path (typed tools) | Complete the metric registry, 10 typed tools, SQL fallback, numeric verifier, conversation state | **Gate 3:** tool accuracy ≥ 90%, 0 unverified numbers | 16–22 d |
 | 4. Knowledge path and router | Hybrid RAG, reranker, glossary, router, mixed agent, refusals, answer cache | **Gate 4 (release):** every v1 target in the Evaluation table met | 12–17 d |
 | 5. Operate | Nightly refresh, freshness smoke test, tracing, eval on every change, wrong answers become cases | Ongoing; failures feed back into phase 2 | 4–6 d setup, then ongoing |
@@ -106,8 +106,8 @@
 | 1.21 | Box-score check: 20 sampled box scores match NBA.com | 1.15 | `tests/test_boxscore_match.py` | All 20 match exactly. This is the spec's Gate 1 check. |
 | 1.22 | Starter metric registry covering every metric the 85 seeds use (G10): name, SQL expression, grain, qualification rule (by era, including NBA.com's "would still lead" exception), rounding rule, first season, aliases | 1.14 | `metrics/registry.yaml`, `metrics/schema.py` | Every seed metric is present and passes schema validation. Q37's career minimum is confirmed against NBA.com and recorded. |
 | 1.23 | Semantic-layer views generated from the registry, including `records`, `team_titles` and `stat_availability` | 1.11–1.18, 1.22 | `transform/models/semantic/`, view allowlist file | The views cover every Stats and Mixed seed, and their names are exported as the allowlist that the SQL fallback (3.16) enforces. |
-| 1.24 | Publish: manifest (snapshot ID, `as_of_date`, row counts, latest game date, checksums including shots), atomic swap of the `current` link, keep the last 7 | 1.20, 1.23 | `ingest/publish.py` | Killing the process mid-swap leaves a valid `current`. A nightly manifest's `as_of_date` is the build date in US Eastern time. |
-| 1.25 | Rollback: health check on open and automatic fallback to the previous snapshot | 1.24 | `ingest/rollback.py` | A corrupted `current` makes the reader open the previous snapshot. |
+| 1.24 | Publish: manifest (snapshot ID, `as_of_date`, row counts, latest game date, checksums including shots), atomic swap of the `current` link, keep the last 7 | 1.20, 1.23 | `ingest/snapshots.py` | Killing the process mid-swap leaves a valid `current`. A nightly manifest's `as_of_date` is the build date in US Eastern time. |
+| 1.25 | Rollback: health check on open and automatic fallback to the previous snapshot | 1.24 | `ingest/snapshots.py` | A corrupted `current` makes the reader open the previous snapshot. |
 | 1.26 | `ingest_log` and one `make refresh` command, run by hand for now | 0.8, 1.7, 1.8, 1.24 | Makefile target | One command runs extract to publish and logs the outcome. A failure keeps yesterday's snapshot live. |
 | 1.27 | One-season fixture database for unit tests | 1.23 | `tests/fixtures/nba_fixture.duckdb` | It builds in under a minute. |
 | 1.28 | As-of build mode: an `as_of` dbt variable makes every table keyed by game, date, or season and season type keep only rows up to the cutoff | 1.23, 1.24 | `as_of` variable in `transform/`, `make refresh AS_OF=<date>` | A build with a test cutoff holds no row after it in `games`, `player_game`, `player_season_stint`, `player_season`, `team_season`, awards, titles, `records` or shots, and its manifest's `as_of_date` is the day after the cutoff game. |
@@ -127,7 +127,7 @@
 
 ## 5. Phase 2: Test set and baseline
 
-**Goal:** a frozen, reviewed set of 320 cases with gold answers on the pinned snapshot, and a harness that scores every stage. No retrieval tuning happens before this gate.
+**Goal:** a frozen, reviewed set of 320 turn-units in 305 case items with gold answers on the pinned snapshot, and a harness that scores every stage. No retrieval tuning happens before this gate.
 
 | ID | Task | Depends on | Output | Done when |
 | --- | --- | --- | --- | --- |
@@ -137,7 +137,7 @@
 | 2.4 | Sourcing pass: Google Trends, "People also ask" for the 30 most-searched players, top weekly r/nba threads | — | `eval/sourcing/2026-10.md` | Each seed links to a source theme or is replaced before gold calls, paraphrases and variants are written (2.5, 2.9, 2.10). |
 | 2.5 | Draft JSON argument schemas for the 10 tools, then write gold tool calls and gold SQL for each Stats and Mixed seed | 1.23, 2.1, 2.3, 2.4 | `app/tools/schemas/`, fields in `cases.yaml` | Gold SQL runs on the pinned snapshot. 3.8 implements these schemas; a schema change there updates the gold calls. |
 | 2.6 | Compute gold values from the pinned snapshot | 2.1, 2.5 | Values in `cases.yaml` | Recomputing twice gives identical values. |
-| 2.7 | Cross-check records and career gold values against Basketball-Reference, once | 2.6 | `eval/crosscheck/bref.csv` | Every records and career case matches or has a documented difference. |
+| 2.7 | Cross-check records and career gold values against Basketball-Reference, once | 2.6 | `eval/crosscheck/bref.csv` | Every records and career case matches or has a documented difference. Method changed by D-026: the cross-check uses NBA.com endpoints plus an independent raw-JSON recomputation (`eval/crosscheck/crosscheck.csv`), and Basketball-Reference is checked by the owner by hand only for Q34 and Q35, because decision 0008 forbids scraping. |
 | 2.8 | Draft the glossary chunks that Q65–Q72 need and record them as gold chunks | 1.22, 2.3 | Draft in `metrics/glossary/`, chunk IDs in `cases.yaml` | Each case names at least one gold chunk ID. IDs are metric or rule names, so they survive glossary rewrites in 4.1. |
 | 2.9 | Paraphrases: 2 per seed, drafted by an LLM and reviewed by a person | 0.3, 2.3, 2.4 | 170 cases | The reviewer approves each one. |
 | 2.10 | Entity variants: nicknames, misspellings, missing accents | 1.11, 1.12, 2.3, 2.4 | 30 cases | Each has gold entity IDs. |
@@ -152,17 +152,17 @@
 | 2.19 | Regression rule: exact one-sided McNemar test on dev (α = 0.05, provisional, unless `eval/README.md` sets another), no critical case moves from pass to fail, zero unverified numbers | 2.18 | `eval/harness/regression.py` | A planted regression fails the check. |
 | 2.20 | LLM-judge calibration on 30 human-labelled text answers, drafted by a candidate local model | 0.3, 2.8, 2.15 | Agreement report | Agreement is at least 90%, or the judge is not used. |
 | 2.21 | Author the 10 freshness smoke-test cases (run in phase 5) | 2.2 | `eval/freshness.yaml` | Cases are time-sensitive and check the pipeline only. |
-| 2.22 | Baseline run with a stub answerer, recorded as the first accepted run | 2.6–2.18 | Baseline report | Every case runs on the pinned snapshot. |
+| 2.22 | Baseline run with a stub answerer, recorded as the first accepted run | 2.6–2.18 | Baseline report | Every case runs on the pinned snapshot. Dev baseline recorded on committed code (`eval/reports/accepted.json`); the gate2 report records the held-out run. |
 
 ### Gate 2: test set and baseline
 
 The spec's gate is "harness runs every case on the pinned snapshot".
 
-- [ ] The harness runs every case on `eval_2025_26_rs` in CI and writes a diffable report.
-- [ ] 320 cases, schema-valid and reviewed by the named reviewer.
-- [ ] Records and career values cross-checked against Basketball-Reference.
+- [ ] A local `make gate2` run on `eval_2025_26_rs` (dev and held-out, held-out only with `HELDOUT_OK=1` at the gate and the owner's approval) writes a diffable report that is committed under `eval/reports/gate2-<sha>.md/.json`; CI checks that the committed report covers every case in `cases.yaml`, was VERIFIED against the pinned snapshot, ran on a clean git SHA and ran both splits.
+- [ ] 320 turn-units in 305 case items, schema-valid and reviewed by the named reviewer.
+- [ ] Records and career values cross-checked against Basketball-Reference. Method changed by D-026: the cross-check uses NBA.com endpoints plus an independent raw-JSON recomputation (`eval/crosscheck/crosscheck.csv`), and Basketball-Reference is checked by the owner by hand only for Q34 and Q35, because decision 0008 forbids scraping.
 - [ ] Splits are by seed family with no leakage.
-- [ ] Baseline recorded. Test set tagged `testset-v1.0` in git.
+- [ ] Baseline recorded. Dev baseline recorded on committed code (`eval/reports/accepted.json`); the gate2 report records the held-out run. Test set tagged `testset-v1.0` in git.
 
 ---
 
@@ -323,3 +323,14 @@
 During phase 1:
 
 6. Whether Basketball-Reference may source the curated `records` table or only validate it (G1), decided with the evidence from 1.3.
+
+---
+
+## Plan revisions
+
+- **2026-10-12.** Changes made to match the build and owner decisions. Original wording is kept where noted; no other plan text changed.
+  - Tasks 1.24 and 1.25 (D-032, R-004): the output files `ingest/publish.py` and `ingest/rollback.py` were replaced with `ingest/snapshots.py`. The code is there: `publish` (line 523), `prune` (532), `health_check` (447), `point_current` (496) and `open_current` (544). Earlier plan text named the two files that were never created.
+  - Gate 2 box 1 (D-029, D-032): "runs every case on `eval_2025_26_rs` in CI" was reworded to the accepted reading, a local `make gate2` run with a committed report. CI has no snapshot because the snapshot is git-ignored and built locally.
+  - Task 2.7 and Gate 2 box 3 (D-026, decision 0008): the Basketball-Reference cross-check method changed. The original requirement is kept, and a sentence after it describes the NBA.com and raw-JSON method. Basketball-Reference is checked by the owner by hand only for Q34 and Q35.
+  - Task 2.22 and Gate 2 box 5 (D-032): added the dev baseline on committed code and the held-out run recorded in the gate2 report. Both are additions only.
+  - Counts (DEF-027, eval/README.md): "320 cases" became "320 turn-units in 305 case items" in the phase 2 summary, the phase 2 goal and Gate 2 box 2. The 2.13 estimate ("about 224 dev and 96 held-out cases") was not changed.
```
