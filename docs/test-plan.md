# Test plan

Owner: test session (`tests/`, this file). Source fixes are made by the development session;
bugs travel as a repro plus a proposed fix, and each lands as a strict `xfail` test that flips
to a normal test once fixed. Baseline on 2026-10-07: ruff and mypy clean, 522 tests passing,
line coverage 69% (`uv run --with pytest-cov pytest -m "not network" --cov=app --cov=ingest
--cov=metrics --cov=eval`).

## Ground rules

- Never call stats.nba.com (the 0.6 s throttle is per process). Network tests keep the `network`
  marker and stay deselected.
- Never read or assert against held-out eval cases. Use invented inputs or the dev split.
- Tests run without Ollama: scripted LLMs (`tests/test_stats_path.py::Script`).
- Expected values come from an independent path (marts, box scores, closed-form), not from the
  code under test.
- `tests/fixtures/nba_fixture/` is generated; ask the developer if it needs to cover more.

## Invariants (the release bar, each needs at least one test that can fail)

| ID | Invariant | Main tests |
|----|-----------|------------|
| I1 | No unverified number in any user-visible text, incl. fallback table and clarifications | `test_verifier`, `test_adversarial`, `test_stats_path_adversarial` |
| I2 | Numbers come from tool results; model picks tool/args only; invented ids dropped | `test_stats_path`, `test_tools_oracle` |
| I3 | SQL fallback is SELECT-only on semantic views; engine is locked and bounded | `test_sql_guard`, `test_sql_fallback`, `test_adversarial` |
| I4 | Traded players, careers: totals from `player_season`, never summed stints | `test_tools`, `test_tools_oracle`, dbt domain tests |
| I5 | Untracked stats are NULL, answered as "not tracked" with first season | `test_tools`, `test_registry` |
| I6 | Live DuckDB is never written; snapshot swap atomic; rollback works | `test_snapshots` |
| I7 | Relative dates resolve against snapshot date in US Eastern | `test_timeparse`, `test_freshness_cases` |
| I8 | Defaults from registry: regular season, Play-In excluded, 70% rule | `test_tools`, `test_semantic_views` |
| I9 | Every answer has a source line; predictions, betting, injuries, non-NBA refused in one sentence | `test_assistant`, `test_stats_path` |
| I10 | Eval harness is deterministic, split by seed family, regression rule enforced | `test_cases`, `test_scorers`, `test_regression` |

## Layers

| Layer | Scope | Status |
|-------|-------|--------|
| L1 Unit | registry, rounding, schemas, timeparse, entities, state, cache, config | covered, 82-99% |
| L2 Data contracts | raw store, contracts, landing, dbt staging/marts, domain checks, as-of builds | `ingest/land.py` 17%, `contracts.py` 30%, `refresh.py` 0%: **gap G-A** |
| L3 Tools vs oracles | all 10 tools against marts/box scores; sweep of every registry metric | new: `test_tools_oracle.py` (tools 55% -> see below) |
| L4 Guards | verifier and sql_guard adversarial, engine resource limits | new: `test_adversarial.py` |
| L5 Stats path | scripted-model end to end: garbage, injection, fuzz | new: `test_stats_path_adversarial.py` |
| L6 Knowledge/RAG | cards, BM25 + dense + rerank, cited numbers | `test_retrieval.py` (developer), **gap G-B**: paraphrase set, rerank order |
| L7 Eval harness | scorers, splits, regression, report | `eval/harness/report.py`, `answerer.py` untested: **gap G-C** |
| L8 CLI/e2e | `app/cli.py` with a scripted LLM, `make eval` stub run | **gap G-D** |
| L9 Network (manual) | Gate 1 box-score match | deselected, user runs |

## Adversarial matrix (L4/L5)

Verifier: number forms (commas, signs, percent, fractions, unicode, full-width, NBSP, glued
letters `99pts`, ranges, ordinals), spelled-out numbers, quantity words (dozen, hundred,
million), seasons and dates as tokens, resolved-argument echoes, wrong-metric labels.
SQL guard: stacked statements, table functions, path-as-table, catalog qualification, CTE
shadowing, comment tricks, DDL/DML/utility statements, LIMIT variants, engine memory/time.
Model: non-JSON, unknown tool, wrong arg types, nulls, oversize limits, prompt injection in the
question, drafts with planted numbers (fuzz).

## Findings so far

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | High | Verifier ignored numbers glued to letters/symbols (`99pts`, `12reb`, `99k`, `99th`, `99½`) | fixed, tests live |
| 2 | Medium | Quantity words were not claims (`a dozen`, `33.5 million`) | fixed, tests live |
| 3 | Medium | `repeat('x', 4000000000)` allocates ~3.9 GB; DuckDB `memory_limit` does not bound scalar results | fixed by the guard's function allowlist; engine-only bypass is a documented limit (not testable in-process: `ru_maxrss` is a process-wide high-water mark) |
| 4 | Medium | Unknown tool name, non-dict args or null tool raised out of `StatsPath.answer` | fixed, tests live |
| 5 | Low | Guard allowed `current_setting`/`version` (path leak) | fixed by the allowlist |
| 6 | Design | Verifier checks numbers, not meaning (right number, wrong metric word) | semantic guard agreed; tests to follow the API |

## Loop

1. Run `make check`; run the new layer; triage failures as test bug, source bug or spec gap.
2. Source bug: write the failing test as strict xfail, message the developer with repro and
   fix, rerun after they land it, remove the marker.
3. Spec gap or ambiguity: ask the user (G-numbers in the execution plan).
4. Re-baseline coverage after each round; target L2 and L7 gaps next, then L8.

## Exit criteria

Zero strict xfails; coverage of `app/` at least 90%, `app/tools/stats.py` at least 85%; every
invariant has a test that fails when the behaviour is broken (mutation spot checks on
verifier, guard and `_fill`).

## Manual / user-run checks

| Check | Command | Pass criteria |
|-------|---------|---------------|
| Gate 1: 20 box scores vs NBA.com (network) | `uv run pytest tests/test_boxscore_match.py -m network` (stop `make backfill` first: one process at a time) | all 20 games match |
| Latency | `make serve` on the target Mac with Ollama running, ask the 20 dev stats questions | p95 at most 3 s |
| Claim definition | decision, not a test | verifier treats digits, spelled numbers, scale and quantity words (dozen, hundred, million) as claims; "half" and "twice" are excluded |
| Backfill completeness | `make backfill-status` | every stage at n / n |
