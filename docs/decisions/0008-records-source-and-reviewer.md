# 0008 — Records table source (G1) and paraphrase reviewer (0.3)

- Tasks: 0.3, 1.17 (`records`), 2.7, 2.9, 2.20
- Date: 2026-10-07
- Status: accepted (owner)

## Decision

**G1.** Basketball-Reference may *source* the curated `records` table, not only validate it, under these limits:

- Rows are entered by hand from Basketball-Reference. Nothing is scraped or bulk-copied.
- Each row carries its source URL and a valid-from date.
- From 1996-97, each row is also checked against NBA.com box scores (`player_game`). A mismatch fails the build or gets a reviewed allowlist row with a note.
- Basketball-Reference's current terms are checked by the owner before the first entry.

**0.3.** The owner is the reviewer for paraphrases (2.9), gold answers and the 30 human-labelled judge-calibration answers (2.20). Phase 2 time is blocked for this. Before the owner sees them, the tester pre-screens paraphrases mechanically (duplicates, seed wording leaked, wrong entities) and the gold values are checked against NBA.com or Basketball-Reference, so the owner only approves or rejects.

## Why

- `ingest/ENDPOINTS.md` shows NBA.com player game logs reconcile with team totals only from 1996-97. Career triple-doubles (Q35) and early single-game records (Q34, Q42) cannot come from NBA.com before then, so validate-only would leave the table without a source.
- Paraphrases are drafted by an LLM, so an LLM reviewing them is circular. The plan requires a person.

## Consequences

- The `records` mart (1.17) is built from a reviewed seed file with a source URL column. A test checks that every row has a URL and a valid-from date.
- This stays inside 0001 (personal and research use, nothing redistributed). A public deployment needs a new decision.
- Closes the open parts of G1 and 0.3 in the Execution Plan.
