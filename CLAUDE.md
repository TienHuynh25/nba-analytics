# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Pre-code, and not yet a git repository (task 0.6 creates it). The repo holds only two planning documents, which are the source of truth. Their filenames contain spaces and an em dash, so quote them in shell commands:

- `Basketball Analytics RAG — Spec.md`: what to build and why (v3, with all gap resolutions applied).
- `Basketball Analytics RAG — Execution Plan.md`: ordered tasks (IDs like `1.16`, `3.11`), dependencies, "done when" checks, gates 1–4, and spec gaps `G1`–`G11` with resolutions.

When implementing, cite the task ID you are working on and meet its "done when" check. Do not add scope beyond the spec. If the code diverges from a doc, flag it rather than silently picking one. Update this file as real commands and modules land.

Rules the spec marks **provisional** (opinion questions, Q14/Q20/Q22/Q48 readings, the playoff per-game minimum, Q85's path, M10's clarification, α = 0.05) await owner decision 0.5. Check `docs/decisions/` before hard-coding one.

**Start here:** five owner decisions (tasks 0.1–0.5) must be recorded in `docs/decisions/` before any code is written. They are: NBA.com terms-of-use position, target Mac specs, paraphrase reviewer name, whether a team deployment is planned, and acceptance of the v3 gap resolutions and provisional rules. Then create the repo structure (0.6) and toolchain (0.7–0.11).

**Critical path:** repo setup → extract client → resumable backfill (1.5–1.6, start early — slowest step due to rate limits) → dbt marts → starter metric registry → semantic views → as-of build → pinned eval snapshot → gold values → typed tools + verifier → model benchmark → Gate 3 → RAG + router → Gate 4.

## What it is

A fully local assistant that answers natural-language NBA questions with correct, cited numbers. NBA.com stats come through `nba_api` into DuckDB, and a small local LLM (Ollama/llama.cpp) runs the pipeline. Release bar: ≥ 85% correct on the held-out split with **zero unverified numbers**.

## Commands

None of these exist yet. They are the targets the plan defines (tasks 0.7, 0.8, 1.26, 1.28). Update this section as Makefile targets and test paths solidify.

```bash
# Install deps and activate environment
uv sync

# Lint and type-check (also runs via pre-commit)
uv run ruff check .
uv run mypy .

# Unit tests (run against tests/fixtures/nba_fixture.duckdb, one season)
make test
# Run a single test file
uv run pytest tests/test_boxscore_match.py -v
# Run a single test by name
uv run pytest tests/ -k "<test_name>" -v

# Build a snapshot (extract → transform → dbt tests → publish → index)
make refresh
# As-of build: AS_OF is the cutoff (last included game date). The manifest's
# as_of_date becomes the day after it. For eval_2025_26_rs, use the last
# 2025-26 regular-season game date.
make refresh AS_OF=<YYYY-MM-DD>

# Run the full eval harness (dev split, temperature 0, cache off)
make eval
# Launch the local assistant
make serve
```

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

## Directory layout

```
config/     models.yaml, sources.yaml (pydantic-validated; no secrets)
metrics/    registry.yaml, schema.py, glossary/
ingest/     nba_api client, raw store, JSON schemas, backfill, publish/rollback
transform/  dbt-duckdb project (staging, marts, semantic views, domain tests)
app/        router, tools/, sql_fallback, rag/, verifier, state, entities, timeparse
prompts/    versioned prompt files (e.g. router.v1.md)
eval/       cases.yaml, schema.py, harness/, reports/, snapshots.yaml
tests/      unit tests on tests/fixtures/nba_fixture.duckdb (one season)
docs/       decisions/, runbooks
data/       raw JSON cache, snapshots, local logs (git-ignored)
```

Stack: Python 3.12 managed with `uv`, plus `ruff`, `mypy` and pre-commit.

## Evaluation rules

- Evals run against the pinned snapshot `eval_2025_26_rs` (end of the 2025-26 regular season), never the live one. "This season" means 2025-26, and "last season's playoffs" means 2024-25.
- Cases are split 70% dev / 30% held-out **by seed family**, so a seed and its paraphrases stay in one split. Held-out runs only at gates and releases. Don't tune against it.
- Prompts, registry and config changes go through `make eval` like code changes. A change merges only if the paired McNemar test shows no significant drop on dev, no `critical` case (all-time records, refusals, Q85) goes from pass to fail, and there are zero unverified numbers.
- Any registry formula change requires recomputing gold values in `eval/cases.yaml`.
- Every run records snapshot ID, prompt version, model, index version and git SHA.
- Test-set authoring (phase 2, tasks 2.2–2.12) can run in parallel with phase 1 data work to shorten elapsed time.
