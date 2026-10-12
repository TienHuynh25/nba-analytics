# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Phase 1 (data foundation) code is done. Pre-work decisions 0.1, 0.2, 0.4 and 0.5 are recorded in `docs/decisions/`. Still open: 0.3 (paraphrase reviewer, needed in phase 2) and G1 (may Basketball-Reference *source* the curated `records` table, or only validate it). The historical backfill (1.6) is resumable and may still be incomplete: check `make backfill-status`. The planning documents are the source of truth. Their filenames contain spaces and an em dash, so quote them in shell commands:

- `Basketball Analytics RAG — Spec.md`: what to build and why (v3; the provisional rules were accepted in `docs/decisions/0005-v3-resolutions.md`).
- `Basketball Analytics RAG — Execution Plan.md`: ordered tasks (IDs like `1.16`, `3.11`), dependencies, "done when" checks, gates 1–4, and spec gaps `G1`–`G11`.

When implementing, cite the task ID you are working on and meet its "done when" check. Do not add scope beyond the spec. If the code diverges from a doc, flag it rather than silently picking one. Update this file as real commands and modules land. `ingest/ENDPOINTS.md` records what the source data actually looks like (G1/G6 evidence, game-ID prefixes, source errors); read it before touching ingest or marts.

**Critical path:** extract client → resumable backfill (1.5–1.6, slowest step due to rate limits) → dbt marts → starter metric registry → semantic views → as-of build → pinned eval snapshot → gold values → typed tools + verifier → model benchmark → Gate 3 → RAG + router → Gate 4.

## What it is

A fully local assistant that answers natural-language NBA questions with correct, cited numbers. NBA.com stats come through `nba_api` into DuckDB, and a small local LLM (Ollama/llama.cpp) runs the pipeline. Release bar: ≥ 85% correct on the held-out split with **zero unverified numbers**.

## Commands

```bash
uv sync                                   # install (Python 3.12, nba_api pinned to 1.11.4)
make check                                # lint (ruff), typecheck (mypy strict), tests
make test                                 # pytest, excluding network tests
uv run pytest tests/test_raw_store.py -v  # one file
uv run pytest -k test_kill_and_restart -v # one test by name
uv run pytest -m "not dbt"                # skip the slower tests that run dbt
uv run pytest tests/test_boxscore_match.py -m network   # Gate 1: 20 box scores vs NBA.com

make backfill                             # resumable historical backfill (hours; safe to kill)
make backfill-status                      # progress per stage, no API calls
make refresh                              # nightly: 7-day window -> anomaly check -> land -> dbt -> publish
make refresh AS_OF=<YYYY-MM-DD> SNAPSHOT_ID=eval_2025_26_rs
                                          # as-of build from cache: pinned, never made current.
                                          # AS_OF = last included game date; as_of_date = next day
uv run python -m metrics.generate_views   # regenerate semantic views after editing the registry
uv run python -m ingest.fixture           # rebuild the one-season test fixture export (needs raw cache)
uv run python -m ingest.gen_schemas       # regenerate endpoint JSON contracts from samples

# dbt by hand against a dev build. The shots path must be absolute and normalized (no ".."):
# the shots view stores it, and the app's file lockdown matches it by prefix.
cd transform && NBA_SHOTS_DIR=<repo>/data/build/dev_shots uv run dbt build --profiles-dir .

make eval                                 # stub answerer on dev; ANSWERER=stats|full, SPLIT=heldout only at gates
make eval ANSWERER=stats ACCEPT=1         # record the accepted baseline for the regression rule
make serve DB=data/build/dev.duckdb SHOTS=$PWD/data/build/dev_shots   # CLI on a dev build
uv run python -m app.tools.schemas        # regenerate tool argument schemas after registry edits
uv run python -m eval.split               # reassign dev/held-out by seed family (deterministic)
```

The `stats` and `full` answerers need the pinned eval snapshot (`eval/snapshots.yaml`, task 2.1), or `NBA_EVAL_DB` / `NBA_EVAL_SHOTS` for dev smoke runs. Ollama must be running with the model in `config/models.yaml`; keep `think: false` (Qwen 3.x thinking costs ~35 s per call). Run only one process that calls stats.nba.com at a time: the 0.6 s throttle is per process.

## Non-negotiable invariants

These come from the spec's review findings. Violating them produces wrong numbers or unreliable evals.

- **Numbers come from code, words from the model.** The LLM picks a tool/metric and fills arguments; deterministic code computes values. Every answer passes the **numeric verifier** (`app/verifier.py`): each number in the draft must match a result value under the registry's rounding rule. Numbers that repeat resolved arguments (seasons, dates, "top 5") match those arguments. In knowledge answers, a number must appear in a cited chunk. If any number fails, regenerate once, then fall back to the result table with a one-line summary.
- **One metric registry** (`metrics/registry.yaml`) defines every metric: SQL expression, grain, qualification rule, rounding, first season tracked, aliases. Tools, semantic views, schema/glossary cards, the verifier and the eval numeric scorer all read it. Adding a metric means one YAML entry, no new code. A renamed metric keeps an alias.
- **Typed tools first, SQL as fallback.** Free SQL is parsed with `sqlglot`, may only be a `SELECT` on semantic-layer views (never raw or staging tables), and runs on a read-only connection with a 5 s timeout and `LIMIT 100`. It gets one repair attempt. The parser also rejects table functions (`read_csv`, `read_parquet`) and `ATTACH`/`COPY`/`PRAGMA`/`SET`. The engine is locked down too (`enable_external_access=false`, `allowed_directories` limited to the snapshot's shots folder, `lock_configuration=true`), so raw-file reads fail even if the parser is bypassed. DuckDB has no statement timeout, so the 5 s limit is a watchdog that calls `interrupt()`.
- **Traded players:** `player_season` holds the source's total row. Leaders, totals and careers read only that table and **never SUM `player_season_stint`**. Careers are sums of `player_season` total rows in every build, including as-of builds. The one exception: team-scoped leaders (Q48) read that team's stint row.
- **Untracked stats are NULL, not 0** (steals/blocks before 1973-74, 3PT before 1979-80, plus-minus/advanced before 1996-97). `stat_availability` drives "not tracked" answers.
- **Never write the live DuckDB file.** Each build writes a new `nba_<YYYYMMDD>.duckdb`, validates it, then atomically repoints the `current` link. Keep the last 7 snapshots. The app opens `current` read-only.
- **Stat rows are never embedded.** The vector index holds only the glossary, schema cards and tool cards, tagged with `registry_version`.
- Relative dates ("this season", "last night") resolve in US Eastern time against the **snapshot date**, not the wall clock. "Today" is the manifest's `as_of_date`, and "last night" is the day before it.
- Default filters come from the registry, not from prompts: regular season unless playoffs are named, so Play-In games are excluded. The NBA Cup final is never counted in regular-season stats. Per-game leaders need 70% of team games, or fewer if the player's total divided by that minimum would still lead (NBA.com's rule).
- Every answer carries a source line: metric · season(s) · filters · snapshot date.
- Decline predictions, betting, injuries and non-NBA leagues in one plain sentence.

## Architecture

A router (stats / knowledge / mixed / refuse) sends each question to one path:

1. **Stats, typed tools:** entity resolution (`player_aliases`, fuzzy match, ask if ambiguous) → tool with JSON-schema-constrained args → semantic views → verifier. v1 tools: `get_player_stats`, `get_leaders`, `compare`, `get_team_stats`, `get_standings`, `get_games`, `get_career`, `get_record`, `get_trend`, `get_awards`.
2. **Stats, SQL fallback:** retrieve schema cards → generate SQL → guardrails → run → verifier.
3. **Knowledge, hybrid RAG:** BM25 + `bge-m3` dense, RRF top 40 → `bge-reranker-v2-m3` keeps 6 → cited answer.
4. **Mixed agent:** both paths, at most 3 tool calls.

Conversation state keeps the last resolved players, teams, season and metric, so follow-ups fill in missing arguments without re-reading the transcript. The answer cache is keyed by (tool, normalized args, snapshot ID) and is cleared on a snapshot swap. Components sit behind small interfaces (`LLMClient`, `Retriever`, `Tool`, `SnapshotStore`), so model and store swaps happen in `config/models.yaml`, not code.

**Data layers:** raw JSON (`data/raw/<endpoint>/<season>/<fetch_date>/`, immutable, validated against `ingest/schemas/*.json`) → dbt-duckdb staging → marts → semantic views generated from the registry. Shots are stored as Parquet partitioned by season, inside each snapshot (`data/snapshots/<snapshot_id>/shots/`), with unchanged seasons hard-linked, so the swap, rollback and manifest checksum cover them. Ingest pins the `nba_api` version, throttles it to about 1 request per 0.6 s, re-fetches a rolling 7-day window for stat corrections, and the backfill checkpoints each (endpoint, season) pair.

**Phase 3 note (Gate 3 before the router):** the router is built in phase 4. Until then, the harness sends stats cases straight to the stats path using their gold path label. Router accuracy is first measured in phase 4.

## Data pipeline as built

- `ingest/`: `client.py` (throttle, retries, pinned version) → `raw_store.py` (write-once JSON cache, `data/raw/<key>/<season|_all>/<fetch_date>/`) validated by `contracts.py` against `ingest/schemas/*.json` → `land.py` flattens raw JSON into an all-VARCHAR `landing.duckdb` (reading raw JSON directly in DuckDB runs out of memory) → dbt → `snapshots.py` (build in place with a `BUILDING` marker, manifest, atomic `current` symlink, prune, health check and rollback). `refresh.py` and `backfill.py` are the entry points.
- `transform/`: `staging/` types and dedups (latest fetch wins per key; season type comes from the game-ID prefix, never the request). `marts/` are the spec's tables. `semantic/` is **generated** from `metrics/registry.yaml` by `metrics/generate_views.py`, as `sem_<view>.sql` files with dbt aliases. Never hand-edit them; a test fails on drift. `transform/semantic_allowlist.txt` is the SQL-fallback allowlist.
- Known source quirks are handled with reviewed seed allowlists, each row with a note: `known_boxscore_gaps`, `known_stint_total_gaps`, `known_team_record_gaps`, `tiebreaker_games` (1948–57 division tiebreakers get season type `Tiebreaker`). A new mismatch fails the build. Don't widen a tolerance to make a test pass; add a row with a note, or fix the cause.
- As-of builds keep a (season, season type) only if all its games are on or before the cutoff. A cutoff inside a season type fails the build. Postseason awards and titles need that season's playoffs to be complete.
- Tests use `tests/fixtures/nba_fixture/` (a committed Parquet export of a 2024-25 build); `tests/conftest.py` rebuilds `nba_fixture.duckdb` from it.

## App layer as built

- `app/stats_path.py`: time (`timeparse`, snapshot clock) -> entities (`entities`, aliases + fuzzy + clarify) -> carry-over (`state`) -> LLM picks one tool call (JSON schema from `app/tools/schemas`) -> `_fill` puts resolved ids/season in, drops invented ids, and resets `qualified` (defaults come from the registry, not the model) -> `app/tools/stats.py` runs SQL on semantic views -> LLM writes words from display-rounded values (`format`) -> `verifier` (regenerate once, else table) -> source line. No fitting tool -> `sql_fallback` (`sql_guard` parser check + locked connection + 5 s watchdog + one repair).
- `app/assistant.py`: `router` (prompt file `prompts/router.v1.md`) -> stats / knowledge (`rag/answer.py`, numbers only from cited glossary chunks) / mixed / refusal sentence. `cache.py` keys on (tool, canonical args, snapshot id).
- Every app connection to a snapshot goes through `app/snapshot.connect_read_only`: read-only, file access limited to the snapshot's shots folder, configuration locked. DuckDB shares one instance per file in a process, so this lockdown applies to all connections at once.
- Tool calls are compared with `app/tools/schemas.canonical` (defaults filled, `stat_line` expanded, id lists sorted). `stat_line` is shorthand for the 10-metric stat line (a gold convention pending owner confirmation).
- Tuning checks use the dev split only. Log any held-out influence in `eval/contamination.md`.

## Directory layout

```
config/     models.yaml, sources.yaml (pydantic-validated; no secrets)
metrics/    registry.yaml, schema.py, generate_views.py, glossary/
ingest/     client, raw store, contracts + schemas/, land, backfill, incremental, snapshots, refresh, fixture
transform/  dbt-duckdb project (staging, marts, generated semantic views, seeds, tests/domain)
app/        config, jsonlog; later router, tools/, sql_fallback, rag/, verifier, state, entities, timeparse
prompts/    versioned prompt files (e.g. router.v1.md)
eval/       cases.yaml, schema.py, harness/, reports/, snapshots.yaml
tests/      unit tests; fixtures/nba_fixture/ export, raw_samples/
docs/       decisions/, runbooks
data/       raw/, checkpoints/, build/, snapshots/, logs/ (git-ignored)
```

Stack: Python 3.12 managed with `uv`, plus `ruff` (line length 100), `mypy --strict` and pre-commit.

## Evaluation rules

- Evals run against the pinned snapshot `eval_2025_26_rs` (end of the 2025-26 regular season), never the live one. "This season" means 2025-26, and "last season's playoffs" means 2024-25.
- Cases are split 70% dev / 30% held-out **by seed family**, so a seed and its paraphrases stay in one split. Held-out runs only at gates and releases. Don't tune against it.
- Prompts, registry and config changes go through `make eval` like code changes. A change merges only if the paired McNemar test shows no significant drop on dev, no `critical` case (all-time records, refusals, Q85) goes from pass to fail, and there are zero unverified numbers.
- Any registry formula change requires recomputing gold values in `eval/cases.yaml`.
- Every run records snapshot ID, prompt version, model, index version and git SHA.
- Test-set authoring (phase 2, tasks 2.2–2.12) can run in parallel with phase 1 data work to shorten elapsed time.
