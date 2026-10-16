# Held-out contamination log

The held-out split is for gates and releases only. Any time held-out cases influenced a change,
it is recorded here, so gate results can be read with that in mind.

| Date | Change | Held-out cases that influenced it | Also seen on dev? |
| --- | --- | --- | --- |
| 2026-09-30 | Entity resolver (3.6): unique-surname aliases match only when capitalized ("free throw" matched World B. Free) | Q10 family | Yes: Q72 family ("center") |
| 2026-09-30 | Entity resolver (3.6): tokens split on hyphens ("Celtics-Knicks", "Gilgeous Alexander") | Q51-p1 | Yes: Q01-v2 |
| 2026-09-30 | Curated alias "Shaq" -> Shaquille O'Neal | H07 | No. A standard nickname, but its only evidence was held-out |
| 2026-10-08 | Paraphrase pre-screen (`tests/test_paraphrase_prescreen.py`) | All paraphrases, held-out included, checked by code only (duplicates, leaked seed wording, entities) | n/a: no held-out text was read by a person and nothing was tuned |
| 2026-10-11 | T-2.9 audit and pre-screen extension (P8, P9) | Counts of all cases; question text of held-out cases Q08/Q08-p2, Q16/Q16-p1, Q32, Q37/Q37-p1, Q38/Q38-p1 and similarity ratios for held-out paraphrases were printed by QA while checking flags | n/a: read for review only; no prompt, registry, config or code was tuned on it |

The resolver was checked once against all cases, held-out included. From then on, tuning checks
run on dev only (`make eval SPLIT=dev`).

## 2026-10-11, T-SEEDS (Gate 1 answerability check)

QA read the question text and ran one hand-written query for each held-out Stats/Mixed seed, and saw the first result rows. Read for review only; no prompt, tool, registry, config or code was changed because of it, and no gold values were written.

Held-out seeds viewed: Q07, Q08, Q10, Q15, Q16, Q18, Q22, Q26, Q29, Q30, Q32, Q35, Q37, Q38, Q47, Q50, Q51, Q54, Q59, Q61, Q71, Q76, Q77 (23). Also seen on dev: n/a (no tuning).

## 2026-10-12, T-2.6 (gold values)

The developer computed gold values for **all 320 case units, held-out included** (`eval/gold/compute_gold.py` on `eval_2025_26_rs`), as the plan requires (2.6). Held-out question text and gold rows were read while writing `eval/gold/gold.sql` and reviewing `eval/gold/gold_report.md`. Gold is deterministic SQL on the semantic views; no prompt, tool, registry, verifier, semantic view or config was changed or tuned because of it. The app tools were run once on every gold tool call (sanity cross-check, scratch only, not saved) and agreed with gold; nothing was changed as a result. Also seen on dev: n/a (no tuning).

## 2026-10-12, T-GATE2RUN (Gate 2 held-out run)

Run `gate2-0e22b45f`: Gate 2 held-out run with the stub answerer (no model, no retrieval); results not used to change any prompt, tool, registry or gold; one run approved by the owner (D-032). Per-case held-out results were not inspected for tuning. Also seen on dev: n/a (no tuning).

## 2026-10-15, T-Q35 (gold wording)

Q35 gold wording only (owner decision D-037, owner-checked against Basketball-Reference): a `rule` text now says the answer is a REGULAR-SEASON career count (Westbrook 209; 221 including playoffs), and the Q35 note in `eval/gold/gold.sql` and `gold_report.md` was reworded. No gold value, `allowed` number, split, prompt, tool, registry or config changed; no held-out run or result was used; no tuning. Also seen on dev: n/a (no tuning).
