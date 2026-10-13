# Gold values (task 2.6)

`compute_gold.py` fills `gold.sql` and `gold.value` for every case in `eval/cases.yaml` from the
pinned snapshot `eval_2025_26_rs`, with deterministic code only (no LLM). `gold_report.md` is a
generated table of every computed value, for the Basketball-Reference cross-check (2.7) and the
owner's review.

```bash
uv run python -m eval.gold.compute_gold             # rewrite cases.yaml and gold_report.md
uv run python -m eval.gold.compute_gold --check     # exit 1 if the stored gold is stale
uv run python -m eval.gold.compute_gold --out DIR   # write both files to DIR (determinism runs)
uv run python -m eval.gold.compute_gold --threads 1 # fix DuckDB's thread count
```

Rerun it after any change to `gold.sql`, the registry (task 3.3), the snapshot, or a case's gold
tool call. `tests/test_cases.py` fails when the stored gold no longer matches (it skips when the
snapshot is absent, as in CI).

## How a value is computed

1. Check the snapshot: sha256 of `manifest.json` and of the database must equal
   `eval/snapshots.yaml`; the registry version must equal the snapshot's `registry_info` and
   `metrics/registry.yaml`; the qualification constants hard-coded in `gold.sql` (70% of team
   games, 82 made threes, 300 made field goals, 400 games or 10,000 points) must equal the
   registry's.
2. Open the database through `app.snapshot.connect_read_only` (read-only, locked down).
3. Run the case's block from `gold.sql`: seeds and hard negatives use `@<id>`, turn *n* of a
   conversation uses `@<id>.<n>`. Paraphrases and entity variants inherit their seed's block,
   and the script refuses if their gold tool call differs from the seed's (such a case needs its
   own `@<case id>` block). Every block is one `SELECT` on the semantic views with exact snapshot
   ids, a full `ORDER BY`, and floats rounded to 6 decimals when stored.
4. Build the value (below) and write it with the block's SQL text into the case.

## Value shape (`gold.value`)

| `kind` | When | Fields |
| --- | --- | --- |
| `answer` | Stats/Mixed answers | `answer`: required numbers; `allowed` (some cases): context numbers; `rows`: the full result; `ordered`; `ties`; `source`; Mixed adds `chunks`, `facts` |
| `no_verdict` | Opinion hard negatives | as `answer` (H05, H07), or a note (H06, no tool call) |
| `not_tracked` | Q85, H08–H10 | `stat`, `first_season_tracked`, `rows` with the NULL value |
| `clarify` | H01–H04, M10 turn 3 | `candidates` (player id and name) |
| `knowledge` | Q65–Q70 | `chunks`, `facts` (exact glossary fragments) |
| `decline` | Q81–Q84 | `reason` |

`answer` items look like `{metric, value, column, key}`. `metric` is a registry metric, so the
harness (`eval/harness/scorers.gold_numbers`) applies its rounding; `value` is the raw number
(percentages as fractions); `key` names the row (player, team, season or game). `source` records
the snapshot id, manifest sha256, registry version and block id.

### Number tags

A number with no registry metric of its own is tagged with the registry count metric whose
rounding applies (all 0 decimals); `column` keeps its real meaning: game scores, player points in
a game and margins use `game_points`; a win streak uses `wins`; the overtime-game count uses
`games_played`; an MVP count uses `mvp_awards`; single-game 3-pointers use `threes_made`;
box-score rebounds and assists use `rebounds` and `assists`.

### Allowed numbers (T-2.15b)

`allowed` lists numbers an answer may state but need not: context columns of the result rows,
named per block in `compute_gold.ALLOWED` (Q43 conference rank and win percentage, Q57 game
scores, Q62 the seasons outside the comparison, Q72 the centers' average usage rate and count,
Q73 makes and share, M03 turn 2 makes, attempts and pooled 3P%). Items have the `answer` item
shape and come from every row; a value that is also required is not repeated. `eval/schema.py`
(`GoldNumber`) validates them.

The numeric scorer (`eval/harness/numeric.py`, inputs from `scorers.gold_numbers`) then passes
a stated number if it matches a required or allowed number under its registry rounding, the
gold row count, or a resolved argument; a season or date token if it is an argument or appears
in the gold rows; and it blanks gold-row names that contain digits ("Philadelphia 76ers",
"Left Corner 3") before reading numbers. Every other number is unverified; every required
number must be stated.

## Scoring rules (PM decision D-025)

- Floats compare under the registry rounding; stored values keep 6 decimals.
- Row order matters only when `ordered: true` (the question asks for a ranking or a series).
- Ranked answers keep every row tied at the cut (`RANK() <= limit`) and list ties by id or date;
  the rule text is in `ties` and, for Q40, Q42 and Q75, in the case's `gold.rule`.
- `sql_rows` (SQL fallback only) compares the result with `rows` (`candidates` for clarify):
  same row count (so a LIMIT that cuts a tie fails), and each scored gold column (the required
  numbers' columns, or every column when there are none) maps to a distinct result column with
  equal values row for row, under the registry rounding. Column names and order are free.

## Assumptions

`gold_report.md` lists every interpretation the owner should approve and the seeds whose
interpretation is ambiguous.
