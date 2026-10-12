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
