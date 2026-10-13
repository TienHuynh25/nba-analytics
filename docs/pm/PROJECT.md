# Project charter: NBA analytics RAG assistant

Status: G0 passed 2026-10-11. G1 passed 2026-10-12. Active phase: Phase 2 (test set and baseline), Gate 2 review: governance APPROVE-WITH-CONDITIONS, four conditions (two the owner's, two the PM's).

Source of truth: `CLAUDE.md`, `Basketball Analytics RAG — Spec.md` (v3), `Basketball Analytics RAG — Execution Plan.md` (edited 2026-10-12 per D-026/D-029/D-032: see its "Plan revisions" note). This file only tracks PM state; it does not restate them.

- **Goal:** a fully local assistant answering NBA questions with correct, cited numbers.
- **Success metric:** at least 85% correct on the held-out split with zero unverified numbers (Gate 4).
- **Tier:** Full.
- **Stack:** Python 3.12 / uv, nba_api 1.11.4, DuckDB + dbt-duckdb, Ollama, ruff, mypy strict.
- **Scope/constraints:** as in CLAUDE.md invariants and the Spec; no scope beyond the Spec.

## Gates (mapped to the Execution Plan)

| PM gate | Plan gate | Status |
|---|---|---|
| G0 charter approved | n/a | ✅ 2026-10-11 |
| G1 | Gate 1: data foundation | ✅ 2026-10-12 (governance APPROVE-WITH-CONDITIONS, conditions closed; security 0 Critical/High/Medium; CI green) |
| G2 | Gate 2: test set and baseline | ⏳ governance T-G2-GOV: APPROVE-WITH-CONDITIONS. Boxes 1, 2, 4 MET; boxes 3, 5 PARTIAL. Conditions: (1) owner checks Q34/Q35 on Basketball-Reference by hand and records the values; (2) owner ratifies D-026 (method change for box 3); (3) PM updates PROJECT.md, SEC-010, crosscheck report (done in this revision); (4) PM merges the plan edit through a PR with CI green. Then tag `testset-v1.0` |
| G3 | Gate 3: stats path | ⬜ prerequisites: T-REC (records_curated filled), DEF-023 (verifier digit-bearing names) fixed in 3.11, Ollama running for the model benchmark |
| G4 | Gate 4: release | ⬜ prerequisite: judge calibrated (T-2.20) or declared unused |

## Repo state (2026-10-12)

- `main` carries all Phase 1 and Phase 2 work (PRs #4, #8, #9, #10, #11, #12, #13 merged; CI green).
- Pinned snapshot `eval_2025_26_rs` (cutoff 2026-04-12, as_of_date 2026-04-13): built from cache, fresh file with only marts/seeds/semantic, sealed 0444/0555, never current, manifest sha256 `6305f368…`, db sha256 `1b51001b…`; independently verified (T-QA6b).
- Gold for 320 turn-units (305 case items) computed by `eval/gold/compute_gold.py` (deterministic, hashes pinned) and independently cross-checked (275 MATCH-NBA, 7 MATCH-RAW, 32 NOT-APPLICABLE, 6 OWNER-MANUAL, 0 MISMATCH). The owner approved the gold interpretations and the 170 paraphrases (D-032).
- Harness verifies the snapshot at the start of every run; `make gate2` writes a committed, CI-checked report; dev baseline `stub-00ed80a2` accepted on committed code (git SHA 68ceafe84935); the one approved held-out gate run is `gate2-0e22b45f` (stub, no LLM; D-033).
- Open defects: DEF-023 (S3, Phase 3 verifier), SEC-014/015/016 (accepted for Phase 3), SEC-010 Ollama host (warning, R-029).
- Stray Finder duplicates: quarantined in `data/quarantine/finder_duplicates_20261012/` (none held unique content); the owner may delete that folder.

## Assumptions

- A-005: partial-career note in get_career/get_player_stats/compare (PM clarification inside D-013; acknowledged by the owner, D-032).

## Open owner decisions / actions

1. **Gate 2 condition 1:** check Q34 (Wilt, 100 points, 1962-03-02) and Q35 (Westbrook, 209 career triple-doubles) on Basketball-Reference by hand (terms first, decision 0008) and tell the PM the values.
2. **Gate 2 condition 2:** ratify D-026: the Gate 2 box 3 cross-check was done with NBA.com plus an independent raw-JSON recomputation, with Basketball-Reference only by the owner's hand for Q34/Q35 (decision 0008 forbids scraping).
3. **Governance question:** confirm that the 30 entity variants, 10 hard negatives, 10 multi-turn items and the critical-tag list (plan 2.14, 51 critical) were reviewed (OWNER-REVIEW covered the gold interpretations and the 170 paraphrases).
4. **T-REC (before Gate 3):** the records list for `records_curated` and confirmation that Basketball-Reference's terms were checked.
5. **T-2.20 (before Gate 4):** label 30 answers to calibrate the judge, or declare the judge unused.
