# Basketball Analytics RAG — Execution Plan

Sep 30, 2026 · companion to *Basketball Analytics RAG — Spec*. Tracks spec v3 (Sep 30, 2026; based on online v2 rev 26).

This plan turns the spec into ordered, checkable work. It follows the spec's development lifecycle diagram: five phases and four gates. Each gate is a test-set result, not a date. Every task has dependencies and a "done when" test, and the critical path is marked. The plan adds no scope beyond the spec. Section 2 lists the gaps it found in v2 and shows which ones the v3 spec now resolves.

**Effort assumption.** Estimates are in engineer-days for one engineer who knows Python and SQL. They exclude waiting on external decisions. No calendar dates are set, as the spec asks.

---

## 1. Summary

| Phase (from the spec) | Goal | Exit gate (from the spec) | Est. effort |
| --- | --- | --- | --- |
| Pre-work *(added by this plan)* | Close blocking decisions, set up the repo | Decisions recorded, CI green on an empty project | 2–3 d |
| 1. Data foundation | `nba_api` ingest, JSON contracts, dbt layers, snapshot swap, stint and availability tables, starter metric registry | **Gate 1:** dbt tests pass; 20 box scores match NBA.com | 14–20 d |
| 2. Test set and baseline | 85 seeds grown to 320 cases, pinned eval snapshot, harness, baseline score | **Gate 2:** harness runs every case on the pinned snapshot | 9–13 d |
| 3. Stats path (typed tools) | Complete the metric registry, 10 typed tools, SQL fallback, numeric verifier, conversation state | **Gate 3:** tool accuracy ≥ 90%, 0 unverified numbers | 16–22 d |
| 4. Knowledge path and router | Hybrid RAG, reranker, glossary, router, mixed agent, refusals, answer cache | **Gate 4 (release):** every v1 target in the Evaluation table met | 12–17 d |
| 5. Operate | Nightly refresh, freshness smoke test, tracing, eval on every change, wrong answers become cases | Ongoing; failures feed back into phase 2 | 4–6 d setup, then ongoing |

Total to release: roughly 53–75 engineer-days. Test-set authoring can overlap phase 1 (section 9), which shortens elapsed time by about 1–2 weeks.

**Critical path:** repo setup → extract and backfill → dbt marts → starter registry and semantic views → as-of build → pinned eval snapshot → gold values → typed tools and verifier → model benchmark → Gate 3 → RAG and router → Gate 4.

---

## 2. Gaps and inconsistencies in the spec

These gaps were found in spec v2. Most are now resolved in the v3 spec; the Status column says which. The owner confirms the resolutions in 0.5. G1's sourcing question is decided in phase 1 (1.3), once its evidence exists.

| # | Gap | Why it matters | Resolution | Status |
| --- | --- | --- | --- | --- |
| G1 | NBA.com game-level box scores may be incomplete for early seasons (first complete season to be confirmed in 1.3) | Q34 (most points in a game), Q35 (career triple-doubles) and Q42 need game-level history back to the 1960s | A small curated `records` table for single-game and career-count records, checked against Basketball-Reference | Table in spec v3. **Open:** may B-Ref source this table or only validate it? Decided in 1.3. |
| G2 | No table holds championships | Q29 (Kobe vs LeBron championships) and Q39 (most titles) cannot be answered | `team_titles` (franchise × season). A player's titles are seasons with at least one playoff appearance for the champion. | Resolved in spec v3 (Data model) |
| G3 | Only 5 of the 10 multi-turn conversations are written | The 25-turn target cannot be met | M06–M10, 3 turns each: team follow-ups, season switches, and a pronoun that must trigger clarification | Resolved in spec v3 (Test set) |
| G4 | "Rerun all 85 questions after each change" conflicts with the ~300-case dev split | Tuning on 85 seeds repeats the small-sample problem that review finding 5 fixes, and about 30% of the seeds are held-out | Rerun the full dev split after each change. Use the dev-split seeds as a fast smoke subset. | Resolved in spec v3 (Development lifecycle) |
| G5 | The split method is not specified | A seed in dev with its paraphrase in held-out leaks the held-out score | Split by seed family, stratified by category. Each multi-turn conversation and hard negative is its own family, except that M01 and M05 join their seeds' families (Q13, Q77). | Resolved in spec v3 (Test set) |
| G6 | Step-back 3s (Q76) depend on the shot `action_type` text | The case may be answerable, not a decline | Keep `action_type` in `shots`. Check the shot-chart endpoint in phase 1 (1.3) and set the gold answer from what the data holds. | Resolved in spec v3; data check in 1.3 |
| G7 | Play-by-play is listed as a source, but no table uses it | Backfilling it costs days of API time for no v1 question | Drop play-by-play from v1. Add it when a test case needs it. | Resolved in spec v3 (Data sources) |
| G8 | The eval snapshot ends at the 2025-26 regular season | "Last season's playoffs" and "the last Finals game" (Q12, Q53) then mean 2024-25. That is correct but easy to get wrong in gold answers. | State the rule, restate it in `eval/README.md`, and tag these cases `relative-time` | Resolved in spec v3 (Evaluation, Test set) |
| G9 | Plus-minus (Q22) and advanced stats start in 1996-97 | Earlier seasons need a "not tracked" answer | Add them to `stat_availability` with first season 1996-97 | Resolved in spec v3 (Data model) |
| G10 | The diagram puts the metric registry in phase 3, but phase 1 semantic views and phase 2 gold values need it | Gold values computed without the registry's formulas and qualification rules would disagree with the tools | Build a starter registry in phase 1 covering every metric the 85 seeds use. Phase 3 completes it and adds the NBA.com accuracy test. Any phase 3 formula fix triggers a gold-value recompute. | Resolved in spec v3 (Development lifecycle note; the diagram itself is unchanged) |
| G11 | The router is built in phase 4, but Gate 3 is measured in phase 3 | Stats cases need some way in before a router exists | In phase 3 the harness sends stats-path cases straight to the stats path using the gold path label. Router accuracy is first measured in phase 4. | Resolved in spec v3 (Development lifecycle note) |

---

## 3. Pre-work

Not a phase in the spec's diagram. It removes decisions that would force rework and gives every later task a working repo.

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 0.1 | Decide the NBA.com terms-of-use position (personal or research only) | — | Decision note in `docs/decisions/` | Owner signs off. If commercial use is planned, stop and scope a licensed feed. |
| 0.2 | Fix the target Mac (chip, RAM) | — | `docs/decisions/target-mac.md` | Model size ceiling and latency budgets are confirmed against it. |
| 0.3 | Name the reviewer for paraphrases and gold answers | — | Name in this plan | Reviewer has time blocked in phase 2. |
| 0.4 | Decide on a team deployment (scaling stage 2) | — | Decision note | If yes, add task 3.20 (FastAPI boundary) to phase 3, as the spec asks. |
| 0.5 | Accept or amend the v3 gap resolutions (section 2) and the spec's provisional rules: opinion questions (stats with no verdict, or decline), Q14 read as per game, Q20 and Q48 qualification (Q48 provisionally uses the Warriors stint; perhaps with no minimum), Q22 plus-minus total or per game, the playoff per-game minimum, Q85 on the Stats path and the "Scope limits" category name, M10's clarification expectation, and α = 0.05 | — | Decision note; spec updated where a rule changes | Each resolution and provisional rule is accepted or amended, and the spec drops its "provisional" marks. |
| 0.6 | Create the repo with the spec's layout | — | `config/ metrics/ ingest/ transform/ app/ prompts/ eval/ tests/ docs/ data/ Makefile` | Tree matches the spec, and `data/` is git-ignored. |
| 0.7 | Python 3.12, `uv` lockfile, `ruff`, `mypy`, pre-commit | 0.6 | `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml` | Pre-commit passes on all files. |
| 0.8 | Makefile skeleton: `refresh`, `eval`, `test`, `serve` | 0.6 | `Makefile` | Each target runs and exits 0 (stubs allowed). |
| 0.9 | CI: lint, type check, unit tests | 0.7 | CI workflow | A pull request shows green checks. |
| 0.10 | Config loading for `models.yaml` and `sources.yaml`, validated with pydantic, no secrets in code | 0.7 | `app/config.py` | Unit test loads and validates both files. |
| 0.11 | Structured JSON logging with run and snapshot IDs | 0.7 | `app/jsonlog.py` | Every log line carries `run_id`. No personal data fields exist. |

---

## 4. Phase 1: Data foundation

**Goal:** a pipeline that builds validated, versioned DuckDB snapshots from `nba_api` and swaps them in atomically. It includes the stint and availability tables and a starter metric registry (G10).

### 1A. Extract (raw layer)

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 1.1 | Pin the `nba_api` version. Write a client wrapper with 0.6 s throttle, backoff retries and headers. | 0.7 | `ingest/client.py` | The wrapper never exceeds the rate in a 100-call test. |
| 1.2 | Raw cache that writes every response to `data/raw/<endpoint>/<season>/<fetch_date>/` and never overwrites | 1.1 | `ingest/raw_store.py` | A second run with a warm cache makes zero API calls. |
| 1.3 | Endpoint inventory mapping every core table and every test question to an endpoint | 0.5, 1.1 | `ingest/ENDPOINTS.md` | Each Stats and Mixed seed names its source endpoints. The first complete season of player game logs is recorded (G1), and a shot-chart sample shows whether step-back 3s can be identified for Q76 (G6). With this evidence, the owner decides whether B-Ref may source `records` (G1). |
| 1.4 | JSON schema per endpoint, generated from samples, then hand-tightened | 1.2, 1.3 | `ingest/schemas/*.json` | The contract test fails on a mutated sample (renamed field, missing column). |
| 1.5 | Resumable historical backfill with (endpoint, season) checkpoints | 1.2, 1.4 | `ingest/backfill.py` | Killing and restarting the job resumes at the next unfinished pair. |
| 1.6 | Run the backfill: 1946-47 onward for traditional stats, 1996-97 onward for advanced stats, plus-minus and shots. No play-by-play (spec v3). | 1.5 | Full raw cache | Every pair is checkpointed. This runs for days, so start it as soon as 1.5 works. |
| 1.7 | Incremental extract: new games plus a rolling 7-day correction window | 1.2, 1.4 | `ingest/incremental.py` | A changed box-score row inside the window appears in the next build. |
| 1.8 | Row-count anomaly check against expected games per day (±10%) | 1.7 | Check in the extract step | A simulated short day stops the run. |

### 1B. Transform (staging and marts)

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 1.9 | dbt-duckdb project that reads raw JSON and writes a new `nba_<YYYYMMDD>.duckdb` | 0.7, 1.2 | `transform/` | The build never opens the live file. |
| 1.10 | Staging models: typed, deduplicated, latest fetch wins per key | 1.9 | `transform/models/staging/` | Key tests for unique and not null pass. |
| 1.11 | `players` and `player_aliases`, seeded with nicknames, initials and accent-free names | 1.10 | Marts | "Jokic", "KD", "Greek Freak", "Wemby" and "SGA" each resolve to one ID. |
| 1.12 | `franchises` and `teams` with `valid_from` and `valid_to` | 1.10 | Marts | Seattle and OKC share a `franchise_id` with no overlapping validity. Charlotte's 1988–2002 seasons belong to the Charlotte franchise, as on NBA.com. |
| 1.13 | `games` with US Eastern dates, season, season type (regular season, Play-In, playoffs), periods, and an NBA Cup final flag | 1.10 | Mart | No game has a NULL season or type. The NBA Cup final and Play-In games are outside regular-season totals. |
| 1.14 | `stat_availability` seed: steals and blocks 1973-74, 3PT 1979-80, plus-minus and advanced 1996-97 (G9), tracking 2013-14 | 0.5 | dbt seed | Every stat column has a first-season value. |
| 1.15 | `player_game` with NULL, not 0, for untracked stats | 1.10, 1.14 | Mart | A 1970 game has NULL steals. |
| 1.16 | `player_season_stint` and `player_season`, with the total row taken from source, never summed | 1.10 | Marts | A traded player has one stint row per team and one total row that matches NBA.com. |
| 1.17 | `team_season`, `awards`, `team_titles` (G2) and curated `records` (G1) | 1.3, 1.10, 1.12, 1.16 | Marts | Q29, Q34, Q35, Q39, Q42 and Q78 are answerable by a query. Titles count by franchise. Each `records` value has a valid-from date. |
| 1.18 | `shots` as Parquet partitioned by season, with zone, shot type and `action_type` | 1.10 | `data/snapshots/<snapshot_id>/shots/season=*/` | A DuckDB view reads all partitions of its own snapshot. Unchanged seasons are hard-linked, not copied. Q73–Q75 are answerable by a query. |

### 1C. Test, starter registry, publish

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 1.19 | dbt tests: unique, not null and relationships on every mart | 1.11–1.18 | Tests | All pass. |
| 1.20 | Domain checks: player points sum to team points, counting stats in stints sum to the season total row, games per team within the season's schedule length (seed table), careers summed over `player_season` match NBA.com's source career totals | 1.19 | `transform/tests/domain/` | Each check fails on a planted error. The schedule rule handles shortened and pre-82-game seasons. |
| 1.21 | Box-score check: 20 sampled box scores match NBA.com | 1.15 | `tests/test_boxscore_match.py` | All 20 match exactly. This is the spec's Gate 1 check. |
| 1.22 | Starter metric registry covering every metric the 85 seeds use (G10): name, SQL expression, grain, qualification rule (by era, including NBA.com's "would still lead" exception), rounding rule, first season, aliases | 1.14 | `metrics/registry.yaml`, `metrics/schema.py` | Every seed metric is present and passes schema validation. Q37's career minimum is confirmed against NBA.com and recorded. |
| 1.23 | Semantic-layer views generated from the registry, including `records`, `team_titles` and `stat_availability` | 1.11–1.18, 1.22 | `transform/models/semantic/`, view allowlist file | The views cover every Stats and Mixed seed, and their names are exported as the allowlist that the SQL fallback (3.16) enforces. |
| 1.24 | Publish: manifest (snapshot ID, `as_of_date`, row counts, latest game date, checksums including shots), atomic swap of the `current` link, keep the last 7 | 1.20, 1.23 | `ingest/publish.py` | Killing the process mid-swap leaves a valid `current`. A nightly manifest's `as_of_date` is the build date in US Eastern time. |
| 1.25 | Rollback: health check on open and automatic fallback to the previous snapshot | 1.24 | `ingest/rollback.py` | A corrupted `current` makes the reader open the previous snapshot. |
| 1.26 | `ingest_log` and one `make refresh` command, run by hand for now | 0.8, 1.7, 1.8, 1.24 | Makefile target | One command runs extract to publish and logs the outcome. A failure keeps yesterday's snapshot live. |
| 1.27 | One-season fixture database for unit tests | 1.23 | `tests/fixtures/nba_fixture.duckdb` | It builds in under a minute. |
| 1.28 | As-of build mode: an `as_of` dbt variable makes every table keyed by game, date, or season and season type keep only rows up to the cutoff | 1.23, 1.24 | `as_of` variable in `transform/`, `make refresh AS_OF=<date>` | A build with a test cutoff holds no row after it in `games`, `player_game`, `player_season_stint`, `player_season`, `team_season`, awards, titles, `records` or shots, and its manifest's `as_of_date` is the day after the cutoff game. |

### Gate 1: data foundation

The spec's gate is "dbt tests pass; 20 box scores match NBA.com". This plan adds the supporting checks under it.

- [ ] All dbt tests pass (1.19).
- [ ] 20 box scores match NBA.com (1.21).
- [ ] Domain checks pass, and each fails on a planted error (1.20).
- [ ] Contract tests catch a mutated response, and the anomaly check catches a short day (1.4, 1.8).
- [ ] Publish survives a crash mid-swap, and rollback works (1.24, 1.25).
- [ ] Every Stats and Mixed seed is answerable by a hand-written query on the semantic views.

---

## 5. Phase 2: Test set and baseline

**Goal:** a frozen, reviewed set of 320 cases with gold answers on the pinned snapshot, and a harness that scores every stage. No retrieval tuning happens before this gate.

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 2.1 | Build and freeze `eval_2025_26_rs`, the snapshot at the end of the 2025-26 regular season, with an as-of cutoff at the last regular-season game date | 1.6, 1.28 | Named snapshot, never rotated; `eval/README.md` with the relative-time rule | Its manifest checksum, covering shots, is stored in `eval/snapshots.yaml`. It holds no game, award or title after the cutoff, and LeBron James's career playoff totals match his totals through the 2025 playoffs. |
| 2.2 | Case schema: id, seed id, question or turns, category, gold path, gold tool call or SQL, gold value, gold entity IDs, source tag, critical flag, split, tags | 0.7 | `eval/schema.py` | Pydantic validates every case on load. `category` is an enum of the spec's 11 labels. |
| 2.3 | Enter the 85 seed questions with the spec's gold-answer rules for ambiguous seeds | 2.2 | `eval/cases.yaml` | The category mix matches the spec (11 categories), each ambiguous seed carries its rule, and date-dependent cases are tagged `relative-time`. |
| 2.4 | Sourcing pass: Google Trends, "People also ask" for the 30 most-searched players, top weekly r/nba threads | — | `eval/sourcing/2026-10.md` | Each seed links to a source theme or is replaced before gold calls, paraphrases and variants are written (2.5, 2.9, 2.10). |
| 2.5 | Draft JSON argument schemas for the 10 tools, then write gold tool calls and gold SQL for each Stats and Mixed seed | 1.23, 2.1, 2.3, 2.4 | `app/tools/schemas/`, fields in `cases.yaml` | Gold SQL runs on the pinned snapshot. 3.8 implements these schemas; a schema change there updates the gold calls. |
| 2.6 | Compute gold values from the pinned snapshot | 2.1, 2.5 | Values in `cases.yaml` | Recomputing twice gives identical values. |
| 2.7 | Cross-check records and career gold values against Basketball-Reference, once | 2.6 | `eval/crosscheck/bref.csv` | Every records and career case matches or has a documented difference. |
| 2.8 | Draft the glossary chunks that Q65–Q72 need and record them as gold chunks | 1.22, 2.3 | Draft in `metrics/glossary/`, chunk IDs in `cases.yaml` | Each case names at least one gold chunk ID. IDs are metric or rule names, so they survive glossary rewrites in 4.1. |
| 2.9 | Paraphrases: 2 per seed, drafted by an LLM and reviewed by a person | 0.3, 2.3, 2.4 | 170 cases | The reviewer approves each one. |
| 2.10 | Entity variants: nicknames, misspellings, missing accents | 1.11, 1.12, 2.3, 2.4 | 30 cases | Each has gold entity IDs. |
| 2.11 | Multi-turn M01–M10 from the spec (M06–M10 added in v3, G3) | 1.11, 1.12, 2.3 | 25 turns | Each later turn lists the entities it must reuse. M10's turn 3 expects a clarifying question (provisional). |
| 2.12 | Hard negatives: similar names, opinion questions, stats not tracked | 2.3 | 10 cases | Each has the expected behaviour: clarify, "not tracked", or, for opinion questions, a stat answer with no verdict that the LLM judge checks (provisional; owner decides in 0.5). |
| 2.13 | Split 70% dev and 30% held-out by seed family, stratified by category (G5). Each hard negative is its own family, and so is each multi-turn conversation unless its turn 1 repeats a seed (M01 joins Q13's family, M05 joins Q77's). | 2.9–2.12 | `split` field | No seed family spans both splits. About 224 dev and 96 held-out cases. |
| 2.14 | Tag critical cases: all-time records, refusals and Q85 | 2.3 | `critical: true` | Tag list reviewed. |
| 2.15 | Harness: `pytest` over `cases.yaml` at temperature 0, one scorer per stage (router, entities, tool arguments, SQL rows, Recall@6, answer, refusals, carry-over, latency) | 0.11, 2.2 | `eval/harness/` | Each scorer passes its own unit tests on hand-made pass and fail examples. |
| 2.16 | Exact numeric scorer using the registry's rounding rules | 1.22, 2.15 | `eval/harness/numeric.py` | "27.3" matches 27.33 for a one-decimal metric, and "27.4" does not. |
| 2.17 | Run metadata: snapshot ID, prompt version, model, index version, git SHA | 2.15 | Report header | Every report shows all five. |
| 2.18 | Report that diffs each case against the last accepted run | 2.15 | `eval/reports/<run_id>.md` | It lists pass-to-fail and fail-to-pass cases, and reports family-level bootstrap 95% intervals for dev, held-out and their difference. |
| 2.19 | Regression rule: exact one-sided McNemar test on dev (α = 0.05, provisional, unless `eval/README.md` sets another), no critical case moves from pass to fail, zero unverified numbers | 2.18 | `eval/harness/regression.py` | A planted regression fails the check. |
| 2.20 | LLM-judge calibration on 30 human-labelled text answers, drafted by a candidate local model | 0.3, 2.8, 2.15 | Agreement report | Agreement is at least 90%, or the judge is not used. |
| 2.21 | Author the 10 freshness smoke-test cases (run in phase 5) | 2.2 | `eval/freshness.yaml` | Cases are time-sensitive and check the pipeline only. |
| 2.22 | Baseline run with a stub answerer, recorded as the first accepted run | 2.6–2.18 | Baseline report | Every case runs on the pinned snapshot. |

### Gate 2: test set and baseline

The spec's gate is "harness runs every case on the pinned snapshot".

- [ ] The harness runs every case on `eval_2025_26_rs` in CI and writes a diffable report.
- [ ] 320 cases, schema-valid and reviewed by the named reviewer.
- [ ] Records and career values cross-checked against Basketball-Reference.
- [ ] Splits are by seed family with no leakage.
- [ ] Baseline recorded. Test set tagged `testset-v1.0` in git.

---

## 6. Phase 3: Stats path (typed tools)

**Goal:** the stats path meets Gate 3 on the dev split, and a local model is chosen by benchmark. Until the router exists, the harness sends stats cases straight to this path (G11).

### 3A. Registry and core services

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 3.1 | Complete the metric registry: every metric the tools expose, plus aliases for renamed metrics | 1.22 | `metrics/registry.yaml` | Registry version is bumped and recorded in run metadata. |
| 3.2 | Registry accuracy test: 20 player-seasons against NBA.com published values (TS%, usage rate, qualification; PER is not published by NBA.com) | 2.1, 3.1 | `tests/test_registry_accuracy.py` | All 20 match within the rounding rule, and the registry's 2025-26 per-game leader lists match NBA.com's, including players who qualify through the "would still lead" exception. Runs on every registry change. |
| 3.3 | Recompute gold values if any formula changed | 2.6, 3.2 | Updated `cases.yaml` | The change is reviewed like code. |
| 3.4 | Interfaces: `LLMClient`, `Retriever`, `Tool`, `SnapshotStore` | 0.10 | `app/interfaces.py` | Ollama and llama.cpp backends switch by config alone. |
| 3.5 | `SnapshotStore`: read-only DuckDB connection to `current`, using the rollback from 1.25 | 1.25, 3.4 | `app/snapshot.py` | The app never holds a write lock, and it reopens when the manifest's snapshot ID changes. |
| 3.6 | Entity resolver: fuzzy match on aliases and teams, with a clarifying question when ambiguous | 1.11, 1.12, 2.15, 3.5 | `app/entities.py` | Unit tests pass on nickname, accent and ambiguity cases. Dev accuracy is recorded; the ≥ 97% target gates at Gate 4. |
| 3.7 | Relative-time resolver ("this season", "last night", "last year's playoffs") in US Eastern time against the snapshot date | 1.24 | `app/timeparse.py` | Unit tests cover season boundaries and the off-season. "Today" is the manifest's `as_of_date` and "last night" the day before it; a day with no games returns "no games". |

### 3B. Tools, verifier and state

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 3.8 | Tool framework: JSON schema per tool (from the 2.5 drafts), argument validation, registry-driven defaults (regular season without Play-In, qualification) | 2.5, 3.1, 3.4 | `app/tools/base.py` | Invalid arguments are rejected before any query runs. |
| 3.9 | The 10 tools: `get_player_stats`, `get_leaders`, `compare`, `get_team_stats`, `get_standings`, `get_games`, `get_career`, `get_record`, `get_trend`, `get_awards` | 1.27, 2.6, 3.5, 3.7, 3.8 | `app/tools/*.py` | Unit tests pass on the fixture DB, and each tool returns the gold value for its gold calls on the pinned snapshot. |
| 3.10 | "Not tracked" answers from `stat_availability` | 1.14, 3.8 | Shared tool behaviour | Q85 and the not-tracked hard negatives name the first tracked season. |
| 3.11 | Numeric verifier: extract every number, match it to result values with registry rounding (numbers that repeat resolved arguments match those arguments), regenerate once, then fall back to the result table | 1.22 | `app/verifier.py` | A planted wrong number never reaches the output across 1,000 fuzzed drafts. |
| 3.12 | Source line under every answer: metric, seasons, filters, the snapshot's latest game date | 2.18, 3.9 | Answer formatter | Every stats answer in the report has one. |
| 3.13 | Tool cards: one chunk per tool with arguments and example questions | 3.9 | Generated from tool schemas | Cards regenerate when a schema changes. |
| 3.14 | Conversation state: last resolved players, teams, season and metric; follow-ups fill missing arguments | 2.11, 2.15, 3.6, 3.7, 3.9 | `app/state.py` | Unit tests pass on M01–M10. Carry-over on multi-turn stats cases is recorded; the ≥ 90% target gates at Gate 4. |

### 3C. SQL fallback and model choice

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 3.15 | Schema cards: one chunk per view and column with example values | 1.23 | Generated from the semantic layer | Every view and column has a card. |
| 3.16 | SQL fallback: retrieve schema cards, generate SQL, parse with `sqlglot`, allow one `SELECT` on semantic views only, add `LIMIT 100`, 5 s watchdog that calls `interrupt()`, one repair attempt. Until the hybrid index exists (4.4), schema cards are retrieved with BM25 behind the `Retriever` interface. | 3.5, 3.15 | `app/sql_fallback.py` | Guardrail tests reject DDL, DML, raw and staging tables, table functions, `ATTACH`/`COPY`/`PRAGMA`/`SET`, and multi-statement input. A slow query stops at 5 s. `SELECT * FROM 'data/raw/...json'` is rejected by the parser and, with the parser bypassed, by the engine (`enable_external_access=false`, `allowed_directories` set to the shots folder, `lock_configuration=true`). |
| 3.17 | Model benchmark: 2–4 instruct models that fit the target Mac, same prompts, dev split | 0.2, 2.22, 3.9, 3.16 | `eval/reports/model-benchmark.md` | Winner chosen on tool-argument accuracy, then latency, and recorded in `config/models.yaml`. |
| 3.18 | Tool-coverage report: share of stats cases answered by a tool vs the fallback | 3.17 | Section in the eval report | Each fallback case is listed as a candidate tool or metric. |
| 3.19 | Tune one variable at a time (prompt, tool descriptions, model), rerunning the full dev split after each change (G4) | 2.19, 3.17 | Accepted runs | Each change passes the regression rule. |
| 3.20 | *(Only if 0.4 is yes)* FastAPI service boundary around the pipeline | 0.4, 3.9 | `app/api.py` | Eval results through the API equal in-process results. |

### Gate 3: stats path

The spec's gate is "tool accuracy at least 90%, 0 unverified numbers".

- [ ] Typed-tool and argument accuracy ≥ 90% on dev.
- [ ] Zero unverified numbers shown.
- [ ] Recorded but not gating yet: entity resolution, SQL execution accuracy, carry-over, and typed-tool and SQL latency. These must meet their targets by Gate 4.

**If tool accuracy stays below 90%:** cut and clarify tools, tighten structured output, or send only the SQL fallback to a larger local model, as the spec's risk table says.

---

## 7. Phase 4: Knowledge path and router

**Goal:** every v1 target in the spec's Evaluation table is met, which is the release gate.

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 4.1 | Complete the stat glossary: one chunk per metric generated from the registry and one per qualification rule, plus curated NBA.com definition text. PER gets a curated definition only. | 2.8, 3.1 | `metrics/glossary/*.md` | Every metric has definition, formula and caveats. Chunk IDs match the gold chunk IDs from 2.8. |
| 4.2 | Vector store (LanceDB or Qdrant) with BM25 and chunk metadata (doc_type, metric, registry_version, updated_at) | 3.4 | `app/rag/index.py` | The index carries the registry version. |
| 4.3 | `bge-m3` embeddings, re-embedding only changed chunks | 3.13, 3.15, 4.1, 4.2 | Index step in `make refresh` | An unchanged registry causes no re-embed. |
| 4.4 | Hybrid retrieval: BM25 plus dense, Reciprocal Rank Fusion top 40, `bge-reranker-v2-m3` keeps 6 | 4.3 | `app/rag/retrieve.py` | Recall@6 ≥ 90% on knowledge and mixed cases. The SQL fallback's schema-card retrieval switches to it. |
| 4.5 | Knowledge answers with citations, where only numbers in cited chunks pass the verifier | 2.20, 3.11, 4.4 | `app/rag/answer.py` | Q65–Q70 pass. |
| 4.6 | Router: stats, knowledge, mixed or refuse, with structured output | 2.22, 3.4 | `app/router.py`, `prompts/router.v1.md` | Path accuracy ≥ 95% on dev. |
| 4.7 | Refusals: one plain sentence for predictions, betting, injuries and non-NBA leagues | 4.6 | Refusal prompt and rules | Out-of-scope cases 100% declined, with no false declines. |
| 4.8 | Mixed agent: calls both paths, at most 3 tool calls, one answer | 3.9, 4.5, 4.6 | `app/agent.py` | Q71 and Q72 pass. Mixed p95 ≤ 10 s. |
| 4.9 | Answer cache keyed by (tool, normalized arguments, snapshot ID), cleared on a snapshot swap | 3.5, 3.9 | `app/cache.py` | A swap clears the cache. A hit skips the query and answer generation; routing and tool choice still run. The eval harness runs with the cache off. |
| 4.10 | `make serve`: a local interface (CLI or minimal web UI) for asking, following up and seeing source lines | 3.14, 4.7–4.9 | Entry point | A user can hold a multi-turn conversation end to end. |
| 4.11 | Latency pass against the per-path budgets | 0.2, 4.8 | Latency section in the report | Typed ≤ 3 s, SQL ≤ 6 s, RAG ≤ 4 s and mixed ≤ 10 s at p95 on the target Mac. |
| 4.12 | Tune chunking, reranker settings and prompts one variable at a time | 2.19, 4.4–4.8 | Accepted runs | Each change passes the regression rule. |
| 4.13 | Docs: README, runbook for refresh and rollback, how to add a metric or tool | 4.1–4.12 | `docs/` | A new engineer adds a metric with one YAML entry by following the doc. |
| 4.14 | Held-out run and release report | 2.20, 4.1–4.12 | `eval/reports/release-v1.md` | The report lists snapshot, prompt, model and index versions. |

### Gate 4: release

The spec's gate is "every v1 target in Evaluation met".

- [ ] End-to-end correctness ≥ 85% on held-out, with zero unverified numbers.
- [ ] Router ≥ 95%, entity resolution ≥ 97%, typed tools ≥ 90%, SQL fallback ≥ 80%, Recall@6 ≥ 90%.
- [ ] Refusals 100% with no false declines. Multi-turn carry-over ≥ 90%.
- [ ] All four per-path latency budgets met on the target Mac.
- [ ] All critical cases pass. As an overfitting check, held-out accuracy is not further below dev than the one-sided 95% bound of the family-bootstrap difference (2.18). With independent cases that bound would be about 7 points; correlated paraphrases make it wider.
- [ ] Release tagged `v1.0` with its test-set tag and eval snapshot ID.

---

## 8. Phase 5: Operate

**Goal:** keep the live snapshot fresh and turn every wrong answer into a test case. The diagram shows failures here feeding back into phase 2.

| ID | Task | Depends on | Output | Done when |
| --- | --- | --- | --- | --- |
| 5.1 | Schedule `make refresh` with launchd: nightly in season, weekly off-season | 1.26 | `config/launchd/com.nba-analytics.refresh.plist` | Seven consecutive runs succeed or fail safely. |
| 5.2 | Run the freshness smoke test after each refresh and alert on failure | 2.21, 5.1 | Alert hook | A planted stale snapshot triggers the alert. |
| 5.3 | Tracing with Langfuse or Arize Phoenix (local), linked by run ID | 2.15 | Config and wrapper | A run's traces open from its report. |
| 5.4 | `make eval` required on every pull request that touches code, prompts, registry or config | 0.9, 2.19 | CI rule | A change that fails the regression rule cannot merge. |
| 5.5 | Anonymized local question logging | 0.11, 4.10 | `data/logs/questions.jsonl` | Each logged answer records its snapshot, prompt, model and index versions. No personal data is stored. |
| 5.6 | Feedback loop: triage wrong answers into new cases through the phase 2 review | 5.5 | New cases in `cases.yaml` | Each accepted case bumps the test-set version. |
| 5.7 | Manual CSV import path for when `nba_api` is blocked | 1.10 | `ingest/csv_import.py`, runbook | One season imports through the same dbt models. |
| 5.8 | Yearly refresh each October: rerun the sourcing pass and refresh cases, rerun the historical endpoint pull (the spec's "once, then yearly"), and rerun the Basketball-Reference cross-check (2.7) | 1.5, 2.4, 2.7 | `eval/sourcing/<YYYY-10>.md` | New seeds go through the same review and split rules. |

---

## 9. Dependencies and parallel work

```
Pre-work ─► 1A extract ─► 1.6 backfill (days; start early) ─┐
               │                                            ▼
               └─► 1B transform ─► 1C tests, starter registry, publish ─► Gate 1
                                                                           │
   Test-set authoring (2.2–2.4, 2.9–2.12) runs alongside 1B and 1C         ▼
         1.28 as-of build ─► 2.1 pinned snapshot ─► 2.5–2.7 gold values ─► harness ─► Gate 2
                                                                                       │
                     3A registry, entities ─► 3B tools, verifier, state ─► 3C SQL, model ─► Gate 3
                                                                                              │
                          4.1 glossary ─► 4.2–4.5 RAG ─► 4.6–4.8 router, refusals, agent ─► Gate 4
                                                                                              │
                                                             Phase 5 operate ─(failures)─► Phase 2
```

**What can start early**

- The historical backfill (1.6) is the slowest task because of rate limits. Start it as soon as 1.5 works.
- Test-set authoring (2.2–2.4, 2.9–2.12) needs no pipeline output and can run during phase 1. 2.10 and 2.11 need entity IDs from 1.11 and 1.12, which land early in phase 1.
- Tool argument schemas are drafted in 2.5 and implemented in 3.8, so gold tool calls exist before the tools do.
- The numeric verifier (3.11) needs only the registry. It can be built at the end of phase 1.
- A glossary draft for the definition cases is written in 2.8, because gold chunks need it. 4.1 completes the glossary.

---

## 10. Risk checkpoints by phase

| Phase | Risk from the spec | Check | Action if it fires |
| --- | --- | --- | --- |
| 1 | stats.nba.com blocks the client or changes endpoints | Contract tests, anomaly check, backfill error rate | Slow the throttle, pause and resume from checkpoint |
| 1 | Early-era game data is missing (G1) | Endpoint inventory (1.3), then records cross-check (2.7) | Fill the curated `records` table |
| 1 | Snapshot swap fails midway | Crash test on publish (1.24) | Fix before Gate 1 |
| 3 | Registry formulas drift from NBA.com | Registry accuracy test (3.2) | Fix the formula and recompute gold values (3.3) |
| 3 | The local model is weak at tool calling | Tool accuracy below 90% | Fewer tools, stricter output, a larger model for SQL only |
| 3–4 | Tuning overfits the test set | Dev rises while held-out stays flat | Stop tuning, add cases, refresh in October |
| 4 | Latency over budget | Per-path p95 in each report | Smaller router model, cache, cap agent steps |
| All | Scope creep | Requests outside the non-goals | Log them for v2 and decide after Gate 4 |

---

## 11. Owner decisions

Before phase 1:

1. The NBA.com terms-of-use position (0.1).
2. The target Mac's chip and RAM (0.2).
3. The named reviewer for paraphrases and gold answers (0.3).
4. Whether a shared team deployment is planned (0.4).
5. Accept or amend the v3 gap resolutions and the spec's provisional rules (0.5): opinion questions (stats with no verdict, or decline); Q14 read as per game; Q20 and Q48 qualification (Q48 provisionally uses the Warriors stint; perhaps with no minimum); Q22 plus-minus total or per game; the playoff per-game minimum; Q85 on the Stats path and the "Scope limits" category name; M10's clarification expectation; α = 0.05.

During phase 1:

6. Whether Basketball-Reference may source the curated `records` table or only validate it (G1), decided with the evidence from 1.3.
