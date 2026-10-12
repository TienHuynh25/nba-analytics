# Held-out contamination log

The held-out split is for gates and releases only. Any time held-out cases influenced a change,
it is recorded here, so gate results can be read with that in mind.

| Date | Change | Held-out cases that influenced it | Also seen on dev? |
| --- | --- | --- | --- |
| 2026-09-30 | Entity resolver (3.6): unique-surname aliases match only when capitalized ("free throw" matched World B. Free) | Q10 family | Yes: Q72 family ("center") |
| 2026-09-30 | Entity resolver (3.6): tokens split on hyphens ("Celtics-Knicks", "Gilgeous Alexander") | Q51-p1 | Yes: Q01-v2 |
| 2026-09-30 | Curated alias "Shaq" -> Shaquille O'Neal | H07 | No. A standard nickname, but its only evidence was held-out |

The resolver was checked once against all cases, held-out included. From then on, tuning checks
run on dev only (`make eval SPLIT=dev`).
