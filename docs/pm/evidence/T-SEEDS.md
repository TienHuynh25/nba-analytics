# T-SEEDS: Gate 1 'every Stats and Mixed seed answerable by a hand-written query on the semantic views'

Scope: **75 seeds** (73 stats + 2 mixed; 52 dev, 23 held-out). All 75 are PASS; 0 GAP. Queries: `docs/pm/evidence/seed-queries.sql`. Full run log: `docs/pm/evidence/T-SEEDS-1.log`.

Method: each query ran through `app.sql_guard.check` (the SQL-fallback parser: one SELECT, allowlisted `semantic.*` views only, function allowlist, LIMIT 100 added) and then executed on `data/build/dev.duckdb` via `app.snapshot.connect_read_only` (read-only, locked config). Guard accepted all 75; all executed without error and returned non-empty results. Sanity only: no comparison to gold or NBA.com. Runner: scratchpad `run.py` (reads the .sql file, so results reproduce from it).

Conventions: this season = 2025-26 Regular Season; last season = 2024-25; relative-time seeds use the eval snapshot cutoff 2026-04-12 (last RS game; as_of_date 2026-04-13). `dev.duckdb` also holds the 2026 postseason, 2025-26 title and award rows, so such queries carry explicit filters (see Observations).

| Seed | Split | Question | Views | Rows | First row | Verdict | Note |
|---|---|---|---|---|---|---|---|
| Q01 | d | How many points per game is Shai Gilgeous-Alexander averaging this season? | player_season_stats | 1 | Shai Gilgeous-Alexander, 2025-26, 68, 31.1324 | PASS |  |
| Q02 | d | What are Nikola Jokic's averages this season? | player_season_stats | 1 | Nikola Jokić, 65, 27.6769, 12.8615, 10.7231, 1.4154, 0.8154, 0.5689, 0.3797, 0.8313, 34.8462 | PASS |  |
| Q03 | d | How many triple-doubles does Jokic have this season? | player_season_stats | 1 | Nikola Jokić, 65, 34 | PASS |  |
| Q04 | d | What is Victor Wembanyama's blocks per game this season? | player_season_stats | 1 | Victor Wembanyama, 64, 3.0781 | PASS |  |
| Q05 | d | What are Cooper Flagg's rookie stats? | player_season_stats | 1 | Cooper Flagg, 2025-26, True, 70, 21.0429, 6.6571, 4.5143, 1.2, 0.9143, 0.4682, 0.2951 | PASS |  |
| Q06 | d | How many 3-pointers has Stephen Curry made this season? | player_season_stats | 1 | Stephen Curry, 43, 190 | PASS |  |
| Q07 | h | What is LeBron James averaging this season? | player_season_stats | 1 | LeBron James, 60, 20.9333, 6.0667, 7.2, 1.2, 0.5833, 0.5147, 0.3169, 0.7373, 33.15 | PASS |  |
| Q08 | h | What is Luka Doncic's field goal percentage with the Lakers? | player_stint_stats | 2 | Luka Dončić, 2024-25, Los Angeles Lakers, 28, 245, 0.4383 | PASS | Per-season rows; a combined Lakers FG% would need fga, which the stint view does not expose (derivable as fgm/pct). |
| Q09 | d | How many minutes per game does Anthony Edwards play? | player_season_stats | 1 | Anthony Edwards, 61, 35.0328 | PASS |  |
| Q10 | h | What is Giannis Antetokounmpo's free throw percentage this season? | player_season_stats | 1 | Giannis Antetokounmpo, 36, 232, 0.6499 | PASS |  |
| Q11 | d | How many games has Jayson Tatum played this season? | player_season_stats | 1 | Jayson Tatum, 16 | PASS |  |
| Q12 | d | What were Shai Gilgeous-Alexander's playoff stats last season? | player_season_stats | 1 | Shai Gilgeous-Alexander, 2024-25, Playoffs, 23, 29.913, 5.3478, 6.5217, 1.6522, 0.8696, 0.4623, 0.2832 | PASS |  |
| Q13 | d | Who leads the NBA in scoring this season? | player_season_stats | 5 | Luka Dončić, Los Angeles Lakers, 64, 33.4844 | PASS | Full 70% + would-still-lead rule written in SQL; views expose no qualified flag. |
| Q14 | d | Who are the top 5 rebounders in the NBA this season? | player_season_stats | 5 | Nikola Jokić, Denver Nuggets, 65, 12.8615, 836 | PASS |  |
| Q15 | h | Who leads the league in assists per game? | player_season_stats | 5 | Nikola Jokić, Denver Nuggets, 65, 10.7231 | PASS |  |
| Q16 | h | Who has the most blocks this season? | player_season_stats | 5 | Victor Wembanyama, San Antonio Spurs, 64, 197 | PASS |  |
| Q17 | d | Who has the highest 3-point percentage (qualified) this season? | player_season_stats | 5 | Luke Kennard, Los Angeles Lakers, 117, 245, 0.4776 | PASS |  |
| Q18 | h | Which player has the most double-doubles this season? | player_season_stats | 5 | Karl-Anthony Towns, New York Knicks, 75, 56 | PASS |  |
| Q19 | d | Who leads the NBA in steals per game? | player_season_stats | 5 | Ausar Thompson, Detroit Pistons, 73, 2.0 | PASS |  |
| Q20 | d | Which rookie is scoring the most this season? | player_season_stats | 5 | Cooper Flagg, Dallas Mavericks, 70, 21.0429 | PASS |  |
| Q21 | d | Who has the most 40-point games this season? | player_season_stats | 5 | Luka Dončić, Los Angeles Lakers, 64, 16 | PASS |  |
| Q22 | h | Who leads the league in plus-minus? | player_season_stats | 5 | Shai Gilgeous-Alexander, Oklahoma City Thunder, 68, 788 | PASS |  |
| Q23 | d | Who is better statistically this season: Jokic or Gilgeous-Alexander? | player_season_stats | 2 | Shai Gilgeous-Alexander, 68, 31.1324, 4.2941, 6.5882, 1.3971, 0.7647, 0.6652, 788 | PASS |  |
| Q24 | d | Compare LeBron James and Michael Jordan career playoff stats. | player_career_stats | 2 | LeBron James, Playoffs, 302, 28.2152, 8.9238, 7.1788, 1.6755, 0.9503, 0.4954, 0.3324 | PASS |  |
| Q25 | d | Compare Curry and Klay Thompson career 3-point percentage. | player_career_stats | 2 | Klay Thompson, 2899, 7089, 0.4089 | PASS |  |
| Q26 | h | Who has more career rebounds, Wilt Chamberlain or Bill Russell? | player_career_stats | 2 | Bill Russell, 963, 21620 | PASS |  |
| Q27 | d | How do Wembanyama's first two seasons compare to Tim Duncan's? | player_season_stats | 2 | Tim Duncan, 1997-98, 1998-99, 132, 21.3258, 11.7273, 2.6136, 2.5152 | PASS |  |
| Q28 | d | Compare Anthony Edwards and Ja Morant scoring this season. | player_season_stats | 2 | Ja Morant, 20, 389, 19.45 | PASS |  |
| Q29 | h | Kobe Bryant vs LeBron James: career points and championships | player_career_stats | 2 | Kobe Bryant, 33643, 5 | PASS |  |
| Q30 | h | Which team has a better defensive rating, the Celtics or the Thunder? | team_season_stats | 2 | Oklahoma City Thunder, 2025-26, 106.5 | PASS |  |
| Q31 | d | Who is the NBA's all-time leading scorer? | player_career_stats | 3 | LeBron James, 43440, 1622 | PASS |  |
| Q32 | h | Who has the most career assists in NBA history? | player_career_stats | 3 | John Stockton, 15806, 1504 | PASS |  |
| Q33 | d | Who has the most 3-pointers made in NBA history? | player_career_stats | 3 | Stephen Curry, 4248, 1069 | PASS |  |
| Q34 | d | What is the most points scored by a player in a single game? | records | 3 | Most points in a game, Wilt Chamberlain, 100.0, 1962-03-02, 1961-62 | PASS | Wilt 100 on top. |
| Q35 | h | Who has the most career triple-doubles? | player_career_stats | 5 | Russell Westbrook, 209, 1301 | PASS | Computed from box-score logs; a curated records entry (G1) is not needed for answerability. |
| Q36 | d | How many career points does LeBron James have? | player_career_stats | 1 | LeBron James, 43440 | PASS |  |
| Q37 | h | Who has the highest career points per game? | player_career_stats | 5 | Michael Jordan, 1072, 32292, 30.1231 | PASS |  |
| Q38 | h | Who has the most career blocks? | player_career_stats | 5 | Hakeem Olajuwon, 3830, 1238 | PASS |  |
| Q39 | d | Which team has won the most NBA championships? | franchises, team_titles | 3 | Boston Celtics, 18 | PASS |  |
| Q40 | d | What is the best regular-season record of all time? | team_season_stats | 3 | Golden State Warriors, 2015-16, 73, 9, 0.8902 | PASS |  |
| Q41 | d | Who has played the most games in NBA history? | player_career_stats | 3 | LeBron James, 1622 | PASS |  |
| Q42 | d | What is the most 3-pointers made in one game? | records | 3 | Most 3-pointers made in a game, Klay Thompson, 14.0, 2018-10-29, 2018-19 | PASS | Klay 14 on top. |
| Q43 | d | What are the current NBA standings in the Western Conference? | team_season_stats | 15 | 1, Oklahoma City Thunder, 64, 18, 0.7805 | PASS |  |
| Q44 | d | Which team has the best record this season? | team_season_stats | 3 | Oklahoma City Thunder, 64, 18, 0.7805 | PASS |  |
| Q45 | d | Which team scores the most points per game? | team_season_stats | 3 | Denver Nuggets, 122.0732 | PASS |  |
| Q46 | d | What is the Lakers' record at home this season? | team_season_stats | 1 | Los Angeles Lakers, 28, 13 | PASS |  |
| Q47 | h | Which team has the best net rating? | team_season_stats | 3 | Oklahoma City Thunder, 11.1 | PASS |  |
| Q48 | d | Who is the Warriors' leading scorer this season? | player_stint_stats | 3 | Brandin Podziemski, Golden State Warriors, 82, 13.8171 | PASS |  |
| Q49 | d | Which team plays at the fastest pace? | team_season_stats | 3 | Miami Heat, 104.22 | PASS |  |
| Q50 | h | What is the Knicks' longest winning streak this season? | games, teams | 1 | 8, 2026-01-21, 2026-02-04 | PASS |  |
| Q51 | h | Who won the last game between the Celtics and the Knicks? | games | 1 | 2026-04-09, Regular Season, New York Knicks, 112, Boston Celtics, 106 | PASS |  |
| Q52 | d | How many points did Jokic score in his last game? | player_game_log | 1 | Nikola Jokić, 2026-04-12, DEN @ SAS, 23 | PASS |  |
| Q53 | d | What was the final score of the last NBA Finals game? | games, team_titles | 1 | 2025-06-22, 2024-25, Oklahoma City Thunder, 103, Indiana Pacers, 91 | PASS | Finals found by joining team_titles; no round column in games. |
| Q54 | h | Who had the highest-scoring game this season? | player_game_log | 3 | Bam Adebayo, 83, 2026-03-10, MIA vs. WAS | PASS |  |
| Q55 | d | What were the box score leaders in last night's games? | player_game_log | 15 | 0022501186, Baylor Scheierman, BOS vs. ORL, 30, 7, 7 | PASS | Top scorer per game on 2026-04-12 (15 games). |
| Q56 | d | How many points did Curry score in his last 5 games? | player_game_log | 5 | 2026-04-12, GSW @ LAC, 24 | PASS |  |
| Q57 | d | Which games this season went to overtime? | games | 54 | 2025-10-21, Oklahoma City Thunder, 125, Houston Rockets, 124, 6 | PASS |  |
| Q58 | d | What was the largest margin of victory this season? | games | 3 | 2026-01-10, Utah Jazz, 95, Charlotte Hornets, 150, 55 | PASS |  |
| Q59 | h | How has the league-average 3-point attempt rate changed since 2010? | league_season_stats | 16 | 2010-11, 0.2218 | PASS |  |
| Q60 | d | How has Wembanyama's 3-point percentage changed each season? | player_season_stats | 3 | 2023-24, 128, 394, 0.3249 | PASS |  |
| Q61 | h | How has LeBron's scoring changed over his career? | player_season_stats | 23 | 2003-04, Cleveland Cavaliers, 79, 20.9367 | PASS |  |
| Q62 | d | Is league-wide scoring higher now than in the 1990s? | league_season_stats | 2 | 2025-26, 115.6077, 1 | PASS |  |
| Q63 | d | How have the Thunder's wins changed over the last 5 seasons? | team_season_stats | 5 | 2021-22, Oklahoma City Thunder, 24, 58 | PASS |  |
| Q64 | d | Has Jokic's assist average gone up every season? | player_season_stats | 11 | 2015-16, 80, 2.3625, None | PASS |  |
| Q71 | h | Who has the highest true shooting percentage this season, and what does it mean? | player_season_stats | 5 | Jalen Duren, Detroit Pistons, 70, 522, 0.6879 | PASS | Stats half only; "what it means" is glossary (knowledge path). |
| Q72 | d | Is Jokic's usage rate high for a center, and what is usage rate? | player_season_stats, players | 1 | 0.289, 0.1771, 52 | PASS | Stats half only; definition is glossary. UNION form hit DEF-? (guard), rewritten with CTEs. |
| Q73 | d | Where does Curry take most of his shots from? | shots | 6 | Above the Break 3, 451, 172 | PASS |  |
| Q74 | d | What is Giannis's field goal percentage in the restricted area? | player_season_stats | 1 | Giannis Antetokounmpo, 2025-26, 0.7736 | PASS |  |
| Q75 | d | Which player makes the most corner 3s? | player_season_stats | 5 | OG Anunoby, New York Knicks, 88 | PASS |  |
| Q76 | h | What is Luka's percentage on step-back 3s? | player_season_stats | 1 | Luka Dončić, 2025-26, 0.3594 | PASS | Tracked (shots action_type), value present. |
| Q77 | h | Who won MVP last season, and what were his stats? | awards, player_season_stats | 1 | Shai Gilgeous-Alexander, 2024-25, 76, 32.6842, 4.9868, 6.3947 | PASS |  |
| Q78 | d | Who has won the most MVP awards? | awards | 3 | Kareem Abdul-Jabbar, 6 | PASS |  |
| Q79 | d | Who won Rookie of the Year in 2024? | awards | 1 | Victor Wembanyama, 2023-24 | PASS |  |
| Q80 | d | How many All-Star selections does LeBron James have? | player_career_stats | 1 | LeBron James, 22 | PASS |  |
| Q85 | d | How many 3-pointers did Wilt Chamberlain make? | player_career_stats | 1 | Wilt Chamberlain, None, None | PASS | Expected NULL: fg3m first tracked 1979-80 (stat_availability). Not 0. |

## GAPs
None. Seeds unanswerable-by-design: **Q85** returns NULL for `threes_made` (no 3-point line before 1979-80), labelled **expected** (NULL, not 0). Mixed seeds Q71, Q72: only the stats half is checkable on views; the definition half is glossary text (knowledge path), out of scope here.

## Findings
- **DEF-? (S3) guard builds invalid SQL for UNION without LIMIT.** `app.sql_guard.check("SELECT player_id FROM semantic.players UNION ALL SELECT player_id FROM semantic.players")` returns `SELECT * FROM SELECT FROM (...) AS q LIMIT 100`, which DuckDB rejects with a parser error. `_with_limit` wraps a Union via `exp.subquery`. Same for INTERSECT/EXCEPT and for CTE+UNION. Found via Q72's first draft. Workaround: add an explicit LIMIT, or avoid set operations; but the SQL fallback LLM would not know, and spends its one repair on it. Evidence: the repro above (the first Q72 draft failed with this parser error; the final log shows the CTE rewrite).
- **Observation (S4, not filed as a defect):** the views carry no "qualified" flag, so per-game leaders (Q13-Q22, Q48, Q71) hand-code the registry rule in SQL. Q13 shows the full "70% or would-still-lead" rule works as one CTE query. The stint view has no `fga`, limiting Q08 to per-season answers.

## Observations on the dev vs pinned snapshot
`dev.duckdb` is not `eval_2025_26_rs`: it has playoffs through 2026-06-13, the 2025-26 title (Knicks) and 2025-26 awards. Seeds with "last/latest" or all-time awards (Q51, Q52, Q53, Q55, Q56, Q78) were answered with date or season filters. On the real pinned snapshot those filters are no-ops, but T-2.6 should recompute against it.
