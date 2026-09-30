# Basketball Analytics RAG — Spec

Sep 29, 2026 · @Tim · v3 local refinement, Sep 30, 2026

## Overview and goals

We are building a local assistant that answers natural-language NBA questions with correct, cited numbers from NBA stats data. Success means at least 85% correct answers on the held-out split, with zero unverified numbers, on a versioned test set of 320 cases grown from 85 seed questions.

**Users:** fans, fantasy players and analysts who ask questions like "Who leads the league in assists?" or "How has Wembanyama's 3P% changed since his rookie year?"

**Goals**

1. Answer stat lookups, comparisons, rankings, trends and history questions from structured stats, not from the model's memory.
2. Show the source (metric, season, filters, data snapshot date) behind every number.
3. Handle follow-up questions in a conversation ("what about his assists?").
4. Run fully local as a standalone project, with its own repo, model setup and data store. Refresh data nightly during the season.
5. Evaluate every change automatically against a versioned test set on a pinned data snapshot before merging.

**Design principles**

- **Numbers come from code, words from the model.** The model picks a metric and its filters; deterministic code computes the number and checks it.
- **Define each metric once.** "Points per game", "qualified leader" and "TS%" live in one metric registry that every path uses.
- **Everything is versioned together.** Each answer and eval run records the data snapshot, prompt, model and index versions.
- **Keep it simple first.** Add a component (agent loop, graph, new source) only when a test-set failure shows it is needed.

**Non-goals (v1):** betting advice, game predictions, live in-game scores, injury news, and non-NBA leagues (WNBA, G League, NCAA).

## Review findings (v2)

The v1 plan had five high-severity gaps. Three could produce wrong numbers, and two made evaluation unreliable. Each fix below is already written into the section it affects.

| # | Finding | Severity | Fix | Section |
| --- | --- | --- | --- | --- |
| 1 | Free-form text-to-SQL over raw tables is the biggest accuracy risk for a small local model | High | Semantic layer (curated views + metric registry) plus typed stat tools for common intents; free SQL only as a fallback | Architecture, Retrieval |
| 2 | Traded players have one row per team plus a total row; a naive SUM double-counts | High | Model team stints and season totals explicitly; leaders and totals read only the total row | Data model |
| 3 | "Every number comes from data" is a prompt rule, not a check | High | Post-generation numeric verifier: every number in the answer must match a result value | Retrieval |
| 4 | Gold answers recompute on live data, so scores change nightly without code changes | High | Evaluate against a pinned, versioned data snapshot; log the snapshot ID with every run | Evaluation |
| 5 | 85 questions cannot detect small regressions: at 85% accuracy the 95% interval is about ±8 points | High | Grow to about 300 cases (paraphrases, nicknames, typos, multi-turn); compare runs question by question | Test set, Evaluation |
| 6 | Nightly ingest writes the same DuckDB file the app reads (single-writer lock) | Medium | Build a new snapshot file, validate it, then swap it in atomically | Data model |
| 7 | NBA.com revises stats after games; load-once upserts miss corrections | Medium | Re-fetch a rolling 7-day window every night | Data sources |
| 8 | Stats not tracked in early eras (steals and blocks before 1973-74, 3PT before 1979-80) could be stored as 0 | Medium | Store NULL plus a stat-availability table; answer "not tracked" | Data model |
| 9 | Generated game recaps duplicate SQL data, can add errors and mean tens of thousands of chunks to maintain | Medium | Drop recaps from v1; game questions go through SQL | Data model |
| 10 | One unofficial source; endpoint changes can break ingestion silently | Medium | Schema contract tests on raw JSON, pinned client version, row-count anomaly alerts | Data sources |
| 11 | No follow-up questions ("what about his assists?") | Medium | Conversation state that carries resolved entities; multi-turn test cases | Retrieval, Test set |
| 12 | Test questions are not validated as trending | Medium | Repeatable sourcing from Google Trends, "People also ask" and r/nba, refreshed each season | Test set |
| 13 | No repo structure, configuration, CI or versioning plan | Medium | New Engineering and scaling section | Engineering |
| 14 | 8 s p95 with a 4-step agent loop on a laptop is unlikely | Low | Latency budget per path; cap agent steps; cache repeated questions | Evaluation |

**v3 refinements (Sep 30, 2026):** this local copy folds in the execution plan's gap resolutions G1–G11 (except whether Basketball-Reference may source `records`) and fixes smaller errors in the sections they affect. Some v3 rules are provisional defaults awaiting the owner; each is marked "provisional" in its section and listed under Risks and open questions.

## Data sources

NBA.com stats, pulled through the open-source `nba_api` Python client, is the single source of truth for v1. Other sources only fill gaps it cannot cover.

| Source | What we take | Access | Refresh | Role |
| --- | --- | --- | --- | --- |
| [NBA.com Stats](https://www.nba.com/stats) via [nba\_api](https://github.com/swar/nba_api) | Player and team box scores, season totals, advanced stats, shot charts, standings, awards. Play-by-play is not fetched in v1, because no v1 case needs it. | Python client over stats.nba.com endpoints | Nightly during the season, weekly off-season | Primary |
| NBA.com historical endpoints | Pre-1996 season stats; career totals and all-time leaders (used only to check the careers computed from `player_season`) | Same client, one backfill run | Once, then yearly | Primary (history) |
| [Basketball-Reference](https://www.basketball-reference.com) | Cross-checks for historical records, pre-tracking-era stats | Manual CSV export only | Yearly | Validation only (whether it may also source the `records` table is an open question) |
| Glossary text (NBA.com stat definitions and league-leader minimums) | Definitions of TS%, usage rate, net rating; qualification rules. PER is not published by NBA.com, so its entry is a curated definition only and v1 does not compute it. | Hand-curated markdown | When stats change | RAG corpus |

**Scope of data:** all regular seasons and playoffs from 1946-47 for traditional stats. On NBA.com, advanced stats, plus-minus and shot charts start in 1996-97, and player tracking stats start in 2013-14. Game-level box scores for early seasons may be incomplete; phase 1 records the first complete season per endpoint. Play-In games are stored as their own season type, and the NBA Cup final is stored but kept out of regular-season stats, as NBA.com does.

**Rate limits and backfill:** throttle `nba_api` calls (about 1 request every 0.6 s) and cache raw JSON to disk so rebuilds never re-hit the API. The historical backfill is a resumable job: it checkpoints each finished (endpoint, season) pair, so a crash or block resumes where it stopped.

**Stat corrections:** NBA.com sometimes revises box scores after a game. Each nightly run re-fetches the last 7 days of games and upserts any changed rows, so corrections flow through.

**Source reliability:** `nba_api` wraps unofficial endpoints that can change without notice. Pin the client version, and validate every raw response against a stored JSON schema (contract test). Alert when row counts differ from the expected games per day by more than 10%. A failed check stops the run and keeps yesterday's snapshot live.

## Architecture

Numbers come from typed stat tools over a semantic layer in DuckDB; free-form text-to-SQL is only a fallback. Hybrid RAG handles explanations and never computes a stat; the only numbers it states (formula constants, qualification minimums) come from a cited chunk. This keeps a small local model on tasks it does reliably: choosing a tool and filling its arguments.

&#91;embedded content: architecture · router, 3 paths, 2 stores\]

A router sends each question to one path. The stats path first tries a typed tool (for example `get_leaders(metric, season, qualified)`). It writes SQL against curated views only when no tool fits. Every answer passes a numeric check before the user sees it. The app always reads a complete, validated snapshot, because nightly builds are swapped in only after they pass checks.

## Data model and ingestion

Data moves through four layers, and each has one job. Only definitions and schema text are embedded. Stat rows are never embedded, because vector search cannot filter, sum or rank exactly.

1. **Raw:** immutable JSON exactly as fetched, one folder per endpoint, season and fetch date.
2. **Staging:** typed, deduplicated tables, built with dbt-duckdb models.
3. **Marts:** the analysis tables below, tested on every build.
4. **Semantic layer:** views plus a YAML metric registry. Each metric has a name, SQL expression, grain, qualification rule (by era, since the NBA has changed its minimums), rounding rule, first season tracked and aliases. Tools, schema cards, gold values and the verifier all read this registry.

**Core tables (DuckDB)**

| Table | Grain | Key columns and rules |
| --- | --- | --- |
| `players` | One row per player | player\_id, name, birth\_date, position, active |
| `player_aliases` | Player × alias | Nicknames, initials, accent-free spellings ("Jokic", "KD") |
| `franchises` / `teams` | Franchise, then team per era | franchise\_id; team\_id with valid\_from/valid\_to, so relocations (Seattle → OKC) keep history. Lineage follows NBA.com (Charlotte's 1988–2002 Hornets seasons belong to today's Charlotte franchise). Team records and titles count by franchise |
| `games` | One row per game | game\_id, date (US Eastern), season, season\_type (regular season, Play-In, playoffs), home\_id, away\_id, scores, periods (for overtime). The NBA Cup final is flagged and excluded from regular-season stats |
| `player_game` | Player × game | Box score; NULL (not 0) for stats not tracked that season |
| `player_season_stint` | Player × season × type × team | One row per team a player played for |
| `player_season` | Player × season × type | Season total across all teams. Leaders and totals read only this table, never a SUM of stints. Team-scoped leaders (Q48, provisional) read the team's stint instead |
| `team_season` | Team × season × type | W-L, off/def/net rating, pace, standings rank |
| `team_titles` | Franchise × season | Champion and Finals opponent. A player's titles are the seasons he appeared in at least one playoff game for the champion |
| `records` | Record × holder | Curated single-game records and career counts that early game logs may not support (confirmed in phase 1), e.g. most points in a game, career triple-doubles. Each value has a valid-from date. Cross-checked against Basketball-Reference |
| `shots` | One row per shot attempt | Parquet partitioned by season, stored per snapshot (`data/snapshots/<snapshot_id>/shots/`; unchanged seasons are hard-linked, not copied), so the swap, rollback and manifest checksum cover it; x, y, zone, distance, shot type, action\_type (e.g. step-back), made |
| `awards` | Player × season × award | MVP, DPOY, ROY, All-NBA, All-Star |
| `stat_availability` | One row per stat | First season tracked (e.g. steals and blocks 1973-74, 3PT 1979-80, plus-minus and advanced stats 1996-97 on NBA.com), so answers can say "not tracked" |

**As-of builds:** a build can take an as-of cutoff (used for the eval snapshot). Every table keyed by game, date, or season and season type (including `games`, `player_game`, `player_season_stint`, `player_season`, `team_season`, awards, titles, `records` values and shots) keeps only rows up to the cutoff. Career and all-time values are always summed over `player_season` total rows (a sum over seasons, never over stints), in every build, so an as-of build needs no separate career path.

**Text corpus (vector index)**

- Stat glossary: one chunk per metric (definition, formula, caveats), generated from the metric registry, plus one chunk per qualification rule (for Q70). Chunk IDs are the metric or rule name, so they stay stable across rewrites.
- Schema cards: one chunk per view and column with example values. The SQL fallback retrieves these.
- Tool cards: one chunk per typed tool, with its arguments and example questions.
- Game recaps are dropped from v1. Game questions go through SQL, which is exact and has no extra text to keep in sync.
- Metadata on every chunk: doc\_type, metric, registry\_version, updated\_at.

**Pipeline**

1. **Extract:** fetch new games plus a 7-day correction window → `data/raw/<endpoint>/<season>/<fetch_date>/`, then validate each file against its JSON schema.
2. **Transform:** dbt-duckdb builds staging and marts into a new file, `nba_<YYYYMMDD>.duckdb`, and never writes to the live file.
3. **Test:** dbt tests (unique, not null, relationships) plus domain checks. Player points must sum to team points, counting stats in stints must sum to the season total row, and no team may play more regular-season games than its season's schedule length. That length comes from a seed table: 82 in most seasons since 1967-68, fewer in earlier seasons and in 1998-99, 2011-12, 2019-20 and 2020-21.
4. **Publish:** if checks pass, write a manifest (snapshot ID, `as_of_date`, row counts, latest game date, checksums including shots) and repoint the `current` link to the new file atomically. `as_of_date` is the build date in US Eastern time for nightly builds, and the day after the last included game for an as-of build. Keep the last 7 snapshots for rollback. The app checks the manifest on each request and reopens its connection when the snapshot ID changes.
5. **Index:** rebuild the glossary, schema and tool cards only when the registry changes; re-embed changed chunks and tag the index with the registry version.
6. **Schedule and log:** one `make refresh` command, run nightly by launchd or cron. Each run is recorded in `ingest_log`, and a failure keeps the previous snapshot live.

## Retrieval and generation

A router sends each question to a path. Stats questions try typed tools first and fall back to SQL. Concept questions use hybrid RAG, and mixed questions use both. Every path ends in the numeric verifier.

| Path | Triggered by | Steps |
| --- | --- | --- |
| **Stats: typed tools** | Numbers, rankings, comparisons, trends, records | Resolve entities → choose a tool, with arguments constrained to its JSON schema → run on semantic views → verify → answer |
| **Stats: SQL fallback** | A stats question no tool fits | Retrieve schema cards → generate SQL against views only → parse and allowlist-check → run → verify → answer |
| **Knowledge: hybrid RAG** | "What is…", "how is… calculated", rules | BM25 + dense search, merged with Reciprocal Rank Fusion (top 40) → cross-encoder rerank (`bge-reranker-v2-m3`, keep 6) → answer with citations |
| **Mixed: agent** | "Is Jokic's usage rate high for a center, and what is it?" | Calls both paths, at most 3 tool calls, then one answer |

**Typed tools (v1):** `get_player_stats`, `get_leaders`, `compare`, `get_team_stats`, `get_standings`, `get_games`, `get_career`, `get_record`, `get_trend`, `get_awards`. Each tool is a thin wrapper over the metric registry. Adding a metric means one YAML entry, no new code. Phase 3 measures what share of the test set the tools cover; each fallback question becomes a candidate for a new tool.

**Entity resolution:** map names, nicknames and abbreviations ("KD", "The Greek Freak", "Dubs") to IDs from `player_aliases` and `teams`, using fuzzy matching. Resolve relative time ("this season", "last year's playoffs") against the snapshot, as the answer rules below state. If a name is ambiguous, ask the user.

**SQL guardrails**

- Parse generated SQL with `sqlglot` (DuckDB dialect). Accept exactly one `SELECT` statement (CTEs allowed). Every table it reads, other than its own CTE names, must be a semantic-layer view, never a raw or staging table. Reject table functions (`read_csv`, `read_parquet`) and `ATTACH`, `COPY`, `PRAGMA` and `SET`.
- Open the SQL-fallback connection read-only, with `enable_external_access=false`, `allowed_directories` limited to the snapshot's shots folder, and `lock_configuration=true`, so the engine also blocks file reads such as `FROM 'data/raw/x.json'`. Add `LIMIT 100` if missing, and stop queries after 5 s. DuckDB has no statement timeout setting, so a watchdog calls `interrupt()` on the connection.
- If SQL fails, send the error back to the model once for repair, then give up and say so.
- Default filters come from the metric registry (regular season unless playoffs are named, so Play-In games are excluded by default; NBA qualification minimums), not from the prompt.

**Answer rules**

- **Numeric verifier:** extract every number from the draft answer and match it to a result value, allowing for the registry's rounding rules. Numbers that repeat the resolved arguments (seasons, dates, "top 5") match against those arguments. In knowledge answers, numbers must appear in a cited chunk. If any number fails, regenerate once. If it fails again, return the result table with a one-line summary.
- Put a source line under every answer: metric, season(s), filters and the snapshot's latest game date (for example `points per game · 2025-26 regular season · qualified · data through 2026-04-12`).
- If a stat was not tracked in the season asked about, say so and name the first season it was tracked.
- Decline predictions, betting, injuries and non-NBA leagues with one plain sentence.
- Resolve relative dates ("last night", "this season") in US Eastern time against the snapshot, not the clock. "Today" is the snapshot's `as_of_date` and "last night" is the day before it. If no games were played then, say so.

**Conversation state:** each session keeps a small structured state: the last resolved players, teams, season and metric. A follow-up ("what about his assists?") fills in its missing arguments from this state. The model never re-reads the raw transcript for this.

**Caching:** cache final answers by (tool, normalized arguments, snapshot ID). A snapshot swap invalidates the whole cache, so a cached answer is never stale. The key is known only after tool choice, so a cache hit saves the query and answer generation, not routing. The eval harness runs with the cache off, so paraphrases of one seed are each scored on a fresh answer.

**Local model stack:** an instruct model served by Ollama or llama.cpp, with structured output (JSON schema or grammar) for tool arguments. Also `bge-m3` embeddings, `bge-reranker-v2-m3`, and LanceDB or Qdrant for vectors plus BM25. Model names, prompts and endpoints live in one config file, so swapping a model needs no code change. Pick the model by benchmark on the dev split in phase 3.

## Test set (85 seed questions, 320 cases)

The v1 test set has 85 questions across 11 categories. They cover player stats, league leaders, comparisons, all-time records, and "what is" stat definitions. Five questions test scope limits: four are out of scope and must be declined, and one (Q85) asks about 3-pointers before the 3-point line existed and must say so (introduced 1979-80).

The seed questions are modeled on common search themes, not taken from a measured ranking. They are validated and refreshed each October through a repeatable sourcing pass. That pass uses Google Trends (NBA topics, last 12 months), "People also ask" boxes for the 30 most-searched players, and top weekly r/nba threads. Once the app runs, anonymized real questions from local logs become the main source.

**Growing the set:** 85 questions are too few to detect small regressions, so each seed is expanded:

| Case type | Count | How it's made |
| --- | --- | --- |
| Seed questions | 85 | The table below |
| Paraphrases | 170 | 2 per seed, drafted by an LLM and reviewed by a person |
| Entity variants | 30 | Nicknames, misspellings, missing accents ("Jokic", "Giannis", "Wemby") |
| Multi-turn | 25 turns | 10 conversations: M01–M05 have 2 turns, M06–M10 have 3 (table after the seed questions) |
| Ambiguous and hard negatives | 10 | Two players with similar names (clarify), opinion questions (stats only, no verdict; provisional), stats not tracked |
| **Total** | **320** | The diagram's "~300" |

**Splits:** 70% dev for day-to-day tuning, 30% held-out and run only at phase gates, so prompts are not tuned to the test. The split is by seed family: a seed, its paraphrases and its entity variants all go to the same split. Each hard negative is its own family, and so is each multi-turn conversation, unless its turn 1 repeats a seed: then it joins that seed's family (M01 with Q13, M05 with Q77). Families are stratified by category. This gives about 224 dev and 96 held-out cases.

**Gold answers:** each case stores its tool call or gold SQL, the expected value on the pinned eval snapshot, and a source tag. Gold values are computed with the metric registry's formulas and qualification rules. Records and career questions are cross-checked against Basketball-Reference once. Cases whose meaning depends on the date are tagged `relative-time`. Cases live in `eval/cases.yaml` in git, so every change to the set is reviewed like code.

| ID | Question | Category | Path | Answer type |
| --- | --- | --- | --- | --- |
| Q01 | How many points per game is Shai Gilgeous-Alexander averaging this season? | Player season | Stats | Number |
| Q02 | What are Nikola Jokic's averages this season? | Player season | Stats | Stat line |
| Q03 | How many triple-doubles does Jokic have this season? | Player season | Stats | Number |
| Q04 | What is Victor Wembanyama's blocks per game this season? | Player season | Stats | Number |
| Q05 | What are Cooper Flagg's rookie stats? | Player season | Stats | Stat line |
| Q06 | How many 3-pointers has Stephen Curry made this season? | Player season | Stats | Number |
| Q07 | What is LeBron James averaging this season? | Player season | Stats | Stat line |
| Q08 | What is Luka Doncic's field goal percentage with the Lakers? | Player season | Stats | Percent |
| Q09 | How many minutes per game does Anthony Edwards play? | Player season | Stats | Number |
| Q10 | What is Giannis Antetokounmpo's free throw percentage this season? | Player season | Stats | Percent |
| Q11 | How many games has Jayson Tatum played this season? | Player season | Stats | Number |
| Q12 | What were Shai Gilgeous-Alexander's playoff stats last season? | Player season | Stats | Stat line |
| Q13 | Who leads the NBA in scoring this season? | Leaders | Stats | Ranked list |
| Q14 | Who are the top 5 rebounders in the NBA this season? | Leaders | Stats | Ranked list |
| Q15 | Who leads the league in assists per game? | Leaders | Stats | Ranked list |
| Q16 | Who has the most blocks this season? | Leaders | Stats | Ranked list |
| Q17 | Who has the highest 3-point percentage (qualified) this season? | Leaders | Stats | Ranked list |
| Q18 | Which player has the most double-doubles this season? | Leaders | Stats | Ranked list |
| Q19 | Who leads the NBA in steals per game? | Leaders | Stats | Ranked list |
| Q20 | Which rookie is scoring the most this season? | Leaders | Stats | Ranked list |
| Q21 | Who has the most 40-point games this season? | Leaders | Stats | Ranked list |
| Q22 | Who leads the league in plus-minus? | Leaders | Stats | Ranked list |
| Q23 | Who is better statistically this season: Jokic or Gilgeous-Alexander? | Comparison | Stats | Side-by-side |
| Q24 | Compare LeBron James and Michael Jordan career playoff stats. | Comparison | Stats | Side-by-side |
| Q25 | Compare Curry and Klay Thompson career 3-point percentage. | Comparison | Stats | Side-by-side |
| Q26 | Who has more career rebounds, Wilt Chamberlain or Bill Russell? | Comparison | Stats | Side-by-side |
| Q27 | How do Wembanyama's first two seasons compare to Tim Duncan's? | Comparison | Stats | Side-by-side |
| Q28 | Compare Anthony Edwards and Ja Morant scoring this season. | Comparison | Stats | Side-by-side |
| Q29 | Kobe Bryant vs LeBron James: career points and championships | Comparison | Stats | Side-by-side |
| Q30 | Which team has a better defensive rating, the Celtics or the Thunder? | Comparison | Stats | Side-by-side |
| Q31 | Who is the NBA's all-time leading scorer? | Records | Stats | Name + number |
| Q32 | Who has the most career assists in NBA history? | Records | Stats | Name + number |
| Q33 | Who has the most 3-pointers made in NBA history? | Records | Stats | Name + number |
| Q34 | What is the most points scored by a player in a single game? | Records | Stats | Name + number + game |
| Q35 | Who has the most career triple-doubles? | Records | Stats | Name + number |
| Q36 | How many career points does LeBron James have? | Records | Stats | Number |
| Q37 | Who has the highest career points per game? | Records | Stats | Name + number |
| Q38 | Who has the most career blocks? | Records | Stats | Name + number |
| Q39 | Which team has won the most NBA championships? | Records | Stats | Name + number |
| Q40 | What is the best regular-season record of all time? | Records | Stats | Team + W-L |
| Q41 | Who has played the most games in NBA history? | Records | Stats | Name + number |
| Q42 | What is the most 3-pointers made in one game? | Records | Stats | Name + number + game |
| Q43 | What are the current NBA standings in the Western Conference? | Team | Stats | Table |
| Q44 | Which team has the best record this season? | Team | Stats | Team + W-L |
| Q45 | Which team scores the most points per game? | Team | Stats | Ranked list |
| Q46 | What is the Lakers' record at home this season? | Team | Stats | W-L |
| Q47 | Which team has the best net rating? | Team | Stats | Ranked list |
| Q48 | Who is the Warriors' leading scorer this season? | Team | Stats | Name + number |
| Q49 | Which team plays at the fastest pace? | Team | Stats | Ranked list |
| Q50 | What is the Knicks' longest winning streak this season? | Team | Stats | Number |
| Q51 | Who won the last game between the Celtics and the Knicks? | Game | Stats | Score |
| Q52 | How many points did Jokic score in his last game? | Game | Stats | Number |
| Q53 | What was the final score of the last NBA Finals game? | Game | Stats | Score |
| Q54 | Who had the highest-scoring game this season? | Game | Stats | Name + number + game |
| Q55 | What were the box score leaders in last night's games? | Game | Stats | Table |
| Q56 | How many points did Curry score in his last 5 games? | Game | Stats | List |
| Q57 | Which games this season went to overtime? | Game | Stats | List |
| Q58 | What was the largest margin of victory this season? | Game | Stats | Game + margin |
| Q59 | How has the league-average 3-point attempt rate changed since 2010? | Trend | Stats | Series |
| Q60 | How has Wembanyama's 3-point percentage changed each season? | Trend | Stats | Series |
| Q61 | How has LeBron's scoring changed over his career? | Trend | Stats | Series |
| Q62 | Is league-wide scoring higher now than in the 1990s? | Trend | Stats | Comparison + series |
| Q63 | How have the Thunder's wins changed over the last 5 seasons? | Trend | Stats | Series |
| Q64 | Has Jokic's assist average gone up every season? | Trend | Stats | Yes/no + series |
| Q65 | What is true shooting percentage and how is it calculated? | Definition | RAG | Text + formula |
| Q66 | What is PER in basketball? | Definition | RAG | Text |
| Q67 | What does usage rate mean? | Definition | RAG | Text |
| Q68 | What is net rating? | Definition | RAG | Text |
| Q69 | What counts as a triple-double? | Definition | RAG | Text |
| Q70 | What is the minimum number of games to qualify for scoring leader? | Definition | RAG | Text + number |
| Q71 | Who has the highest true shooting percentage this season, and what does it mean? | Definition | Mixed | Ranked list + text |
| Q72 | Is Jokic's usage rate high for a center, and what is usage rate? | Definition | Mixed | Number + text |
| Q73 | Where does Curry take most of his shots from? | Shooting | Stats | Zone breakdown |
| Q74 | What is Giannis's field goal percentage in the restricted area? | Shooting | Stats | Percent |
| Q75 | Which player makes the most corner 3s? | Shooting | Stats | Ranked list |
| Q76 | What is Luka's percentage on step-back 3s? | Shooting | Stats | Percent, or "not tracked" (set in phase 1 from the shot data) |
| Q77 | Who won MVP last season, and what were his stats? | Awards | Stats | Name + stat line |
| Q78 | Who has won the most MVP awards? | Awards | Stats | Name + number |
| Q79 | Who won Rookie of the Year in 2024? | Awards | Stats | Name |
| Q80 | How many All-Star selections does LeBron James have? | Awards | Stats | Number |
| Q81 | Who will win the NBA championship this year? | Scope limits | Refuse | Decline (prediction) |
| Q82 | Should I bet on the Lakers tonight? | Scope limits | Refuse | Decline (betting) |
| Q83 | Is Joel Embiid injured right now? | Scope limits | Refuse | Decline (injury news) |
| Q84 | What is Caitlin Clark averaging this season? | Scope limits | Refuse | Decline (WNBA) |
| Q85 | How many 3-pointers did Wilt Chamberlain make? | Scope limits | Stats | No 3-point line in his career (introduced 1979-80). Path provisional. |

**Category mix:** Player season 12 · Leaders 10 · Comparison 8 · Records 12 · Team 8 · Game 8 · Trend 6 · Definition 8 · Shooting 4 · Awards 4 · Scope limits 5 (renamed from "Out of scope"; provisional).

**Gold-answer rules for ambiguous seeds**

These rules fix what each seed means on the pinned snapshot, so gold values do not depend on guesses about rosters or wording.

| Seeds | Rule |
| --- | --- |
| Q13, Q15, Q19 | "Leads in scoring" and other per-game rankings use the registry's qualification: 70% of team games (58 in an 82-game season), or fewer games if the player's total divided by that minimum would still lead (NBA.com's league-leader rule). |
| Q14, Q20, Q48 | Provisional: Q14 reads "top 5 rebounders" as rebounds per game. Q20 ranks rookies by points per game. Q48 ranks Warriors players by points per game over their Warriors stint (for a traded player, only his Golden State games). All three use the same games rule as Q13. |
| Playoff per-game leaders (M08 turn 3) | NBA.com lists no playoff minimum. Provisional: 70% of the team's playoff games. |
| Q16, Q18, Q21, Q75 | "Most" ranks season totals, with no games minimum. |
| Q17 | 3P% leaders use NBA.com's minimum of 82 made 3-pointers. |
| Q22 | Provisional: plus-minus is the regular-season total; the answer names the measure. |
| Q37 | Regular season only, with the registry's career minimum. The answer states the minimum. Confirm the minimum in phase 1. |
| Q05, Q08 | Q05's rookie season is the player's first season in `player_season`. Q08 uses the default season (2025-26 regular season) and his Lakers stint. If the snapshot has no such stint, the gold answer says so. |
| Q12, Q53, Q77 | On the eval snapshot, "last season" is 2024-25 and "the last NBA Finals" is the 2025 Finals. |
| Q51, Q52, Q55, Q56 | "Last game" and "last night" resolve against the snapshot's latest game date. Q51 counts games of any season type. |
| Q59, Q62 | "Since 2010" means 2010-11 onward. "The 1990s" means 1990-91 to 1999-00. "Now" means the snapshot's season. |
| Q70 | The gold answer is the league-leader minimum above, not the 65-game minimum for awards. |
| Q79 | "In 2024" means the award for the season that ended in 2024 (2023-24). The answer names the season it used. |
| All | A gold value of 0 (for example, a player with no games) is answered, not declined. |

**Multi-turn cases**

| ID | Turn 1 | Turn 2 | Turn 3 | What later turns must reuse |
| --- | --- | --- | --- | --- |
| M01 | Who leads the NBA in scoring this season? | What about assists? | — | Season, leader metric type |
| M02 | What were Jokic's averages last season? | And in the playoffs? | — | Player, season (the eval snapshot has no 2025-26 playoffs) |
| M03 | Compare Curry and Klay's career 3P% | Over their last 3 seasons only | — | Both players, metric |
| M04 | Who has the best record in the West? | What's their net rating? | — | Team from the turn-1 result |
| M05 | Who won MVP last season? | How many has he won in total? | — | Player from the turn-1 result |
| M06 | How many points per game are the Celtics scoring this season? | And their defensive rating? | How does that compare to last season? | Team; then team and metric, with the season switched |
| M07 | What were Wembanyama's averages in his rookie season? | And in his second season? | Which of those seasons had more blocks per game? | Player; then both seasons |
| M08 | Who leads the league in rebounds per game this season? | What about last season? | And in the playoffs? | Metric; then metric and season, with the season type switched |
| M09 | Compare Jokic and Embiid scoring this season. | What about rebounds? | Who has played more games? | Both players and season; then the metric switches |
| M10 | What are LeBron James's career playoff totals? | Compare that with Kevin Durant. | How many points did he score last season? | Metric and scope; turn 3's "he" is ambiguous and must trigger a clarifying question (provisional) |

## Evaluation

Each stage is scored separately on a frozen data snapshot, so a score changes only when code, prompts or models change. The release bar is at least 85% end-to-end accuracy on the held-out split, with zero unverified numbers.

**Pinned eval snapshot:** evaluation runs on a snapshot frozen at the end of the 2025-26 regular season (`eval_2025_26_rs`). It is an as-of build (see Data model) with its cutoff at the last regular-season game date, so games (Play-In, playoffs), awards and titles after it are excluded, and career totals stop at it. Its `as_of_date` is the day after that game. Relative time resolves against it: "this season" is 2025-26, "last season" is 2024-25, and "last night" is the last regular-season game date. The rule is restated in `eval/README.md`. A separate freshness smoke test (10 time-sensitive cases) runs against the live snapshot after each nightly build. It checks the pipeline, not the model.

| Stage | Metric | How measured | v1 target |
| --- | --- | --- | --- |
| Router | Path accuracy | Predicted path vs gold path | ≥ 95% |
| Entity resolution | Correct player/team/season IDs | Compare to gold IDs, including variant and multi-turn cases | ≥ 97% |
| Typed tools | Tool and argument accuracy | Chosen tool and arguments equal gold | ≥ 90% |
| SQL fallback | Execution accuracy | Result rows match gold rows (order-insensitive, within rounding) | ≥ 80% |
| Hybrid RAG | Recall@6 | Share of knowledge and mixed cases whose gold chunk is in the top 6 after reranking | ≥ 90% |
| Answer | Correctness | Numbers checked exactly in code; LLM judge for text only | ≥ 85% held-out |
| Answer | Unverified numbers shown | Verifier passes that reach the user unmatched | 0 |
| Answer | Refusals | Out-of-scope declined; in-scope not declined | 100% / 0 false declines |
| Multi-turn | Carry-over accuracy | Turn 2+ resolves the same entities as gold | ≥ 90% |
| Latency (p95, local) | Per path | Typed tool ≤ 3 s · SQL fallback ≤ 6 s · RAG ≤ 4 s · Mixed ≤ 10 s | Met on the target Mac |

**Tooling:** `make eval` runs a `pytest` harness over `eval/cases.yaml` at temperature 0. It writes a report that diffs each case against the last accepted run. Every run records its snapshot ID, prompt version, model and index version. Langfuse or Arize Phoenix (local) keeps the traces, linked by run ID. The LLM judge is used only after it agrees with human labels on 30 answers at least 90% of the time.

**Regression rule:** a change merges only if all three hold on the dev split:

1. A paired, question-by-question comparison with the last accepted run shows no significant drop. Use the exact (binomial) McNemar test on the discordant cases, one-sided, at α = 0.05 (provisional) unless `eval/README.md` sets another level.
2. No case tagged critical (all-time records, refusals, Q85) moves from pass to fail.
3. No unverified number is shown.

Rules 2 and 3 backstop rule 1. The held-out split runs only at phase gates and releases. At about 96 held-out cases and 85% accuracy, the 95% interval is at least ±7 points, and the dev split (about 224 cases) at least ±5. Both are wider in practice, because a seed and its paraphrases tend to pass or fail together (this also inflates McNemar's false-alarm rate). The harness therefore reports family-level bootstrap intervals, and the release bar is read as a point estimate.

## Engineering and scaling

The codebase is split by responsibility, so each part can be tested and replaced on its own. v1 is one local process; the same interfaces carry it to a shared service later with no rewrite.

**Repo layout**

```
nba-analytics/
  config/       models.yaml, sources.yaml (all tunables, no secrets in code)
  metrics/      metric registry (YAML, versioned)
  ingest/       extractors, JSON schemas, backfill checkpoints
  transform/    dbt-duckdb project (staging, marts, views, tests)
  app/          router, tools, sql_fallback, rag, verifier, state
  prompts/      prompt files with version IDs
  eval/         cases.yaml, harness, reports
  tests/        unit tests on a one-season fixture database
  docs/         decisions, runbooks
  data/         raw JSON cache, snapshots (each with its shots Parquet), local logs (git-ignored)
  Makefile      refresh, eval, test, serve
```

**Practices**

- Python 3.12 with a `uv` lockfile, `ruff`, `mypy` and pre-commit hooks.
- Small interfaces (`LLMClient`, `Retriever`, `Tool`, `SnapshotStore`), so models and stores are swapped by config, not code.
- Prompts are files, and changing one goes through `make eval` like any code change.
- Unit tests run tools and the verifier against a small fixture database in seconds. The full eval runs before merge.
- Metric registry changes are versioned; a renamed metric keeps an alias so old test cases and caches still resolve.
- Structured JSON logs with run and snapshot IDs; no personal data in logs.

**Scaling path**

| Stage | Users | What changes | What stays |
| --- | --- | --- | --- |
| v1 local | 1 | DuckDB file, Ollama, one process | — |
| Small team | Up to about 20 at once | FastAPI service, llama.cpp server or vLLM on one GPU machine, read-only snapshot per worker, shared answer cache | Registry, tools, verifier, eval |
| Public app | Many | Managed analytics store (MotherDuck or ClickHouse), batched model serving, Dagster for ingest, auth and rate limits; requires a licensed NBA data feed | Registry, tools, verifier, eval |

## Development lifecycle

The test set is built in phase 2, before any retrieval tuning. Each later phase moves forward only when its gate passes on that set.

&#91;embedded content: development lifecycle · 5 phases, 4 gates\]

Two clarifications to the diagram:

- **Registry placement.** The diagram lists the metric registry under phase 3. A starter registry covering every metric the 85 seeds use is built in phase 1, because the semantic views and the phase 2 gold values need its formulas and qualification rules. Phase 3 completes it. Any phase 3 formula fix triggers a gold-value recompute.
- **Gate 3 before the router.** The router is built in phase 4. Until then, the harness sends stats cases straight to the stats path using their gold path label, and router accuracy is first measured in phase 4.

Phases 3 and 4 change one variable at a time (chunking, reranker, prompt, model) and rerun the full dev split after each change. The dev-split seeds serve as a fast smoke subset between full runs. No dates are set yet; add them once the team and hardware are known.

## Risks and open questions

These risks remain after the v2 fixes. Each has a named early signal, so it is caught in a specific phase, not at release.

| Risk | Early signal | Mitigation |
| --- | --- | --- |
| stats.nba.com blocks the client or changes endpoints | Contract test or row-count alert fails | Keep the last good snapshot live; pinned client; manual CSV import path; licensed feed before any public launch |
| The local model is weak at tool calling | Tool accuracy below 90% in phase 3 | Structured output; fewer, clearer tools; send the SQL fallback to a larger local model |
| Registry formulas drift from NBA.com definitions (e.g. TS%, qualification minimums) | Unit test mismatch | Test computed metrics against NBA.com published values for 20 player-seasons on every registry change |
| Tuning overfits the test set | Dev accuracy rises while held-out stays flat | Held-out split used only at gates; refresh cases each October |
| Snapshot swap fails midway | App cannot open `current` | Atomic link swap; health check on start; auto-rollback to the previous snapshot |
| Scope creep (live scores, predictions) | Requests outside the non-goals | Non-goals list; decide v2 scope after the release gate |

- [ ] Are the NBA.com terms of use acceptable for this project (personal/research vs commercial)?
- [ ] Which Mac is the target (chip and RAM)? It sets the model size and the latency budgets.
- [ ] Who reviews paraphrases and gold answers before the set is frozen?
- [ ] May Basketball-Reference source the curated `records` table, or only validate it? (Decided after phase 1 shows the first complete game-log season.)
- [ ] Confirm or change the provisional v3 rules: opinion questions answered with stats and no verdict (or declined); Q14 read as per game; Q20 and Q48 qualification (Q48 provisionally uses the Warriors stint; perhaps with no minimum); Q22 plus-minus total or per game; the playoff per-game minimum; Q85 on the Stats path and the "Scope limits" category name; the M10 clarification expectation; α = 0.05.
- [ ] Is a shared team deployment (scaling stage 2) planned? If so, build the FastAPI service boundary in phase 3.
- [ ] Should v2 add live scores and injury reports, and from which source?
