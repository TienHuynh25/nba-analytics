# 0007 — Open divergences from the spec (owner to approve)

- Date: 2026-10-08
- Status: **accepted (owner, 2026-10-07)**: all three recommendations approved (1 A, 2 A, 3 B).
  Only 3 B changes behaviour: the TS% rule in `metrics/registry.yaml` gains the 300-made-field-goals
  minimum, and Q71's gold value is recomputed (task 3.2).

Three places where real NBA.com data forced a choice the spec did not anticipate. Each lists the
evidence, the options and a recommendation.

## 1. "Player points must sum to team points" before 1996-97 (task 1.20)

**Spec:** the domain check holds for every game.
**Evidence:** checking every season after the backfill, 1,217 team-games mismatch. All but one are before 1996-97,
where NBA.com box scores are partial. The other is an NBA.com source error (NJN @ DET, 1999-04-28: players
sum to 97, team row 93). See `ingest/ENDPOINTS.md`, G1.
**Current behaviour:** exact match required; known mismatches are allowed only through
`transform/seeds/known_boxscore_gaps.csv` (same game, team and values), so any new mismatch fails.

| Option | Effect |
| --- | --- |
| A. Keep the reviewed allowlist (current) | Check stays strict for all seasons; old gaps documented row by row |
| B. Enforce only from 1996-97 | Simpler, but a new pre-1997 error would go unnoticed |
| C. Drop pre-1996-97 player box scores | Loses Wilt's 100-point game and other early single-game records |

**Recommendation: A.**

## 2. Stint minutes vs. the season total row (task 1.20)

**Spec:** counting stats in stints must sum to the season total row.
**Evidence:** every counting stat matches exactly except minutes. NBA.com rounds stint minutes and
total minutes separately (differences of 1 minute per stint), and in five 2003-05 player-seasons the
total row itself is wrong (e.g. 1,016 vs 2,664). Three 1978-79 games-played gaps come from the
replayed Nets–76ers game; two 1940s gaps are source errors.
**Current behaviour:** minutes may differ by max(1 minute per stint, 1%); every other stat is exact;
the larger cases are listed with a note each in `transform/seeds/known_stint_total_gaps.csv`.

| Option | Effect |
| --- | --- |
| A. Keep slack for minutes only, plus the reviewed list (current) | Catches real errors, tolerates rounding |
| B. Exact minutes, every mismatch in the reviewed list | Hundreds of rounding rows to maintain |
| C. Exclude minutes from the check | Misses errors like the 2003-05 rows |

**Recommendation: A.** The list must be regenerated and reviewed once the per-player backfill
finishes (it covers about a third of players today).

## 3. True shooting percentage leaders have no volume minimum (Q71, task 1.22)

**Spec:** qualification comes from the registry. NBA.com lists no separate TS% minimum.
**Evidence:** with only the 70%-of-games rule, the 2025-26 TS% leader is a low-volume center
(Jericho Sims, 77.2%), which few people would accept as the answer to "who has the best TS%".
**Current behaviour:** TS% uses the per-game leader rule (games only).

| Option | Effect |
| --- | --- |
| A. Games only (current) | Faithful to "no published minimum", odd leaders |
| B. Games plus the FG% minimum (300 made field goals) | Matches how NBA.com ranks efficiency stats in practice; one registry line |
| C. Games plus a shot-attempt minimum chosen by the owner | Most control, needs a number |

**Recommendation: B.** Confirm against NBA.com's published leader list in task 3.2. Any change
recomputes Q71's gold value.
