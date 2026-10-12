# Paraphrase pre-screen (task 2.9)

Generated from `tests/test_paraphrase_prescreen.py` (run: `.venv/bin/python -m pytest tests/test_paraphrase_prescreen.py`). Decision 0008: the owner approves or rejects; this list is what the machine could see first.

Scope: 170 paraphrases (85 seeds x 2), all tagged `unreviewed`. Held-out items are listed by ID and check only; their wording is not reproduced here.

## Checks

| Check | What it flags | Result |
|---|---|---|
| P1 | gold, split, critical differ from seed | 0 flags |
| P2 | exact duplicate question (normalised) | 0 flags |
| P3 | number/year/season lost or added | 0 flags |
| P4 | seed wording copied (similarity >= 0.9 or long shared run) | 2 flags |
| P5 | scope word (playoff, rookie, career, all-time) dropped or added | 3 flags |
| P6 | not a plausible user message (length, LLM boilerplate) | 0 flags |
| P7 | wrong or lost entity (app resolver over fixture, name fallback) | 1 flag |
| P8 (new) | near-duplicate: sibling >= 0.80, other family >= 0.90 | 0 flags |
| P9 (new, advisory) | similarity to seed 0.80-0.90 (light copy) | 9 flags |

P2 and P8 cover duplicates across all 305 cases, including entity variants and hard negatives. Pairs that look alike by design (Q52 vs H02, Q07 vs Q07-v2) are variants or hard negatives, not paraphrases, and are not flagged.

## Flags by case

| Case | Split | Check | Detail | Owner action |
|---|---|---|---|---|
| Q06-p1 | dev | P9 | similarity to seed 0.84; text: "How many threes has Stephen Curry made this season?" (seed: "How many 3-pointers has Stephen Curry made this season?") | approve or rewrite |
| Q08-p2 | heldout | P7 | a team in the seed is not found in the paraphrase (owner to review) | approve or rewrite |
| Q11-p1 | dev | P9 | similarity to seed 0.84; text: "How many games has Jayson Tatum appeared in this season?" (seed: "How many games has Jayson Tatum played this season?") | approve or rewrite |
| Q13-p1 | dev | P9 | similarity to seed 0.80; text: "Who's the NBA scoring leader this season?" (seed: "Who leads the NBA in scoring this season?") | approve or rewrite |
| Q14-p1 | dev | P9 | similarity to seed 0.82; text: "Who are the five best rebounders in the league this season?" (seed: "Who are the top 5 rebounders in the NBA this season?") | approve or rewrite |
| Q37-p2 | heldout | P4 | shares a long word run with its seed (owner to review) | approve or rewrite |
| Q40-p2 | dev | P5 | drops 'of all time' from the best-record question; text: "What is the NBA record for the best regular season, by wins and losses?" (seed: "What is the best regular-season record of all time?") | approve or rewrite |
| Q41-p1 | dev | P5 | drops 'history'; 'holds the record' implies all-time (probably fine); text: "Who holds the record for most games played in the NBA?" (seed: "Who has played the most games in NBA history?") | approve or rewrite |
| Q41-p2 | dev | P5 | drops 'history': reads as season-scoped or career, ambiguous; text: "Which player has appeared in the most NBA games?" (seed: "Who has played the most games in NBA history?") | approve or rewrite |
| Q45-p1 | dev | P9 | similarity to seed 0.88; text: "Which team averages the most points per game?" (seed: "Which team scores the most points per game?") | approve or rewrite |
| Q49-p1 | dev | P9 | similarity to seed 0.86; text: "Which team plays the fastest, by pace?" (seed: "Which team plays at the fastest pace?") | approve or rewrite |
| Q50-p1 | heldout | P9 | (held-out: open the case to review) | approve or rewrite |
| Q61-p1 | heldout | P9 | (held-out: open the case to review) | approve or rewrite |
| Q79-p2 | dev | P4 | only 'Who' -> 'Which player'; adds no wording variety; text: "Which player won Rookie of the Year in 2024?" (seed: "Who won Rookie of the Year in 2024?") | approve or rewrite |
| Q79-p2 | dev | P9 | similarity to seed 0.82; text: "Which player won Rookie of the Year in 2024?" (seed: "Who won Rookie of the Year in 2024?") | approve or rewrite |

## Not flagged

All other paraphrases passed every check. They still need the owner's approval (the `unreviewed` tag stays until then). The mechanical checks cannot judge meaning: cross-family closeness (a paraphrase nearer a different seed, e.g. Q31-p1 vs Q32) was scanned and is template overlap between all-time-leader questions, not a wrong metric. No paraphrase changes a metric by this scan, but P1 only proves the gold is copied, not that the new wording still asks for it.
