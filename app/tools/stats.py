"""The 10 typed tools (task 3.9), thin wrappers over the registry and the semantic views.

Column names in SQL come only from registry metric names (validated against each tool's JSON
schema enum) and fixed view names. Every value is a bound parameter.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, ClassVar

from app.interfaces import SnapshotStore
from app.tools.base import (
    STAT_LINE,
    BaseTool,
    ToolArgError,
    ToolError,
    ToolResult,
    season_phrase,
    source_line,
)
from metrics.schema import EraRule, Grain, Metric

SEASON_VIEW = "semantic.player_season_stats"
CAREER_VIEW = "semantic.player_career_stats"
STINT_VIEW = "semantic.player_stint_stats"
TEAM_VIEW = "semantic.team_season_stats"
TEAM_ALL_TIME_VIEW = "semantic.team_all_time_stats"
LEAGUE_VIEW = "semantic.league_season_stats"


def _rows(store: SnapshotStore, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    cur = store.connection().execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def _cols(metrics: Sequence[str]) -> str:
    return ", ".join(metrics)


def _require_grain(tool: BaseTool, metrics: Sequence[str], grain: Grain, what: str) -> None:
    bad = [m for m in metrics if grain not in tool.metric(m).grains]
    if bad:
        raise ToolArgError(f"{', '.join(bad)} not available {what}")


def _labels(tool: BaseTool, metrics: Sequence[str]) -> list[str]:
    if set(STAT_LINE) <= set(metrics):
        rest = [m for m in metrics if m not in STAT_LINE]
        return ["stat line", *(tool.metric(m).label.lower() for m in rest)]
    return [tool.metric(m).label.lower() for m in metrics]


class GetPlayerStats(BaseTool):
    name = "get_player_stats"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        pid, season, st, metrics = a["player_ids"][0], a["season"], a["season_type"], a["metrics"]
        nt = self.not_tracked(store, metrics, [season])
        tracked = [m for m in metrics if m not in {n.metric for n in nt}]
        filters = []
        if a.get("breakdown") == "zone":
            return self._zones(a, store, tracked, nt)
        if "team_id" in a:
            _require_grain(self, tracked, Grain.player_stint, "for one team stint")
            sql = (
                f"select player_id, player_name, season, season_type, team_id, team_name, gp"
                f"{', ' + _cols(tracked) if tracked else ''} from {STINT_VIEW} "
                "where player_id = ? and season = ? and season_type = ? and team_id = ?"
            )
            rows = _rows(store, sql, [pid, season, st, a["team_id"]])
            filters.append(f"with {rows[0]['team_name']}" if rows else "team stint")
        else:
            _require_grain(self, tracked, Grain.player_season, "for a player season")
            sql = (
                f"select player_id, player_name, season, season_type, team_name, gp"
                f"{', ' + _cols(tracked) if tracked else ''} from {SEASON_VIEW} "
                "where player_id = ? and season = ? and season_type = ?"
            )
            rows = _rows(store, sql, [pid, season, st])
        notes = (
            []
            if rows
            else [
                f"No {season_phrase(season, st)} games for this player"
                + (" with that team" if "team_id" in a else "")
                + "."
            ]
        )
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            tracked,
            source_line(_labels(self, metrics), season_phrase(season, st), filters, store),
            nt,
            notes,
            {"players": [pid]},
        )

    def _zones(
        self, a: dict[str, Any], store: SnapshotStore, metrics: list[str], nt: list[Any]
    ) -> ToolResult:
        """Shot metrics split by court zone (Q73)."""
        for m in metrics:
            if self.metric(m).base.value != "shots":
                raise ToolArgError(f"{m} cannot be split by zone")
        parts = []
        for m in metrics:
            met = self.metric(m)
            cond = f" filter (where {met.filter})" if met.filter else ""
            parts.append(met.sql.replace("count(*)", f"count(*){cond}", 1) + f" as {m}")
        sql = (
            f"select zone, {', '.join(parts)} from semantic.shots "
            "where player_id = ? and season = ? and season_type = ? "
            f"group by zone order by {metrics[0]} desc"
        )
        rows = _rows(store, sql, [a["player_ids"][0], a["season"], a["season_type"]])
        total = sum(r[metrics[0]] or 0 for r in rows)
        for r in rows:
            r["share_pct"] = round(100 * (r[metrics[0]] or 0) / total, 1) if total else None
        return ToolResult(
            self.name,
            a,
            ["zone", *metrics, "share_pct"],
            rows,
            metrics,
            source_line(
                _labels(self, metrics),
                season_phrase(a["season"], a["season_type"]),
                ["by zone"],
                store,
            ),
            nt,
            [] if rows else ["No shot chart data for this player season."],
            {"players": a["player_ids"]},
        )


class GetLeaders(BaseTool):
    name = "get_leaders"

    def _rule(self, m: Metric, scope: str, season: str | None, st: str) -> EraRule | None:
        q = m.qualification
        if q is None:
            return None
        if scope == "career":
            if m.unit != "per_game":
                return None
            return self.reg.qualification("career_per_game").rule_for("1946-47")
        if st == "Playoffs":
            if q != "per_game_leader":
                return None  # no playoff minimum defined for this metric
            q = "per_game_leader_playoffs"
        try:
            return self.reg.qualification(q).rule_for(season or "")
        except LookupError as exc:
            raise ToolError(
                f"No {m.label.lower()} qualification rule is defined for {season} yet."
            ) from exc

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        m = self.metric(a["metric"])
        scope, st, limit = a["scope"], a["season_type"], a["limit"]
        season = a.get("season")
        order = "desc" if m.higher_is_better else "asc"
        notes: list[str] = []
        if a["entity"] == "team":
            _require_grain(self, [m.name], Grain.team_season, "for teams")
            if season is None:
                raise ToolArgError("season is required for team leaders")
            rows = _rows(
                store,
                f"select team_id, team_name, gp, {m.name} from {TEAM_VIEW} "
                f"where season = ? and season_type = ? and {m.name} is not null "
                f"order by {m.name} {order} limit ?",
                [season, st, limit],
            )
            src = source_line([m.label.lower()], season_phrase(season, st), [], store)
            return self._result(a, rows, m, src, notes)

        if scope == "career":
            _require_grain(self, [m.name], Grain.player_career, "as a career total")
            view, where, params = CAREER_VIEW, "season_type = ?", [st]
            extra = ", games_played, " + (m.per_game_of or m.name)
        else:
            if season is None:
                raise ToolArgError("season is required for season leaders")
            if "team_id" in a:
                view, where = STINT_VIEW, "season = ? and season_type = ? and team_id = ?"
                params = [season, st, a["team_id"]]
            else:
                view, where, params = SEASON_VIEW, "season = ? and season_type = ?", [season, st]
            if a["rookies_only"]:
                if view != SEASON_VIEW:
                    raise ToolArgError("rookies_only is for league-wide season leaders")
                where += " and is_rookie_season"
            extra = ", gp, team_gp"
        rule = self._rule(m, scope, season, st) if a["qualified"] else None
        if rule is not None:
            for s in (rule.min_made_stat, rule.min_career_total_stat, m.per_game_of):
                if s and s not in extra:
                    extra += f", {s}"
        sql = (
            f"select player_id, player_name{', team_name' if scope != 'career' else ''}"
            f"{extra}, {m.name} from {view} where {where} and {m.name} is not null"
        )
        cands = _rows(store, sql, params)

        def qualifies(r: dict[str, Any]) -> bool:
            if rule is None:
                return True
            if rule.min_games_pct is not None:
                return bool(r["gp"] >= math.ceil(rule.min_games_pct * (r["team_gp"] or 0)))
            if rule.min_made is not None and rule.min_made_stat:
                return bool((r[rule.min_made_stat] or 0) >= rule.min_made)
            games_ok = (
                rule.min_career_games is not None
                and (r["games_played"] or 0) >= rule.min_career_games
            )
            total_ok = (
                rule.min_career_total is not None
                and rule.min_career_total_stat
                and (r[rule.min_career_total_stat] or 0) >= rule.min_career_total
            )
            return bool(games_ok or total_ok)

        reverse = m.higher_is_better
        qualified = sorted(
            (r for r in cands if qualifies(r)), key=lambda r: r[m.name], reverse=reverse
        )
        ranked = qualified
        if rule is not None and rule.would_still_lead and rule.min_games_pct and m.per_game_of:
            # NBA.com: fewer games still qualify if total / minimum games would still lead.
            best = qualified[0][m.name] if qualified else None
            for r in cands:
                if qualifies(r) or best is None:
                    continue
                min_games = math.ceil(rule.min_games_pct * (r["team_gp"] or 0))
                if min_games and (r[m.per_game_of] or 0) / min_games > best:
                    ranked = sorted([*ranked, r], key=lambda x: x[m.name], reverse=reverse)
                    notes.append(
                        f"{r['player_name']} qualifies under the 'would still lead' "
                        f"rule ({r[m.per_game_of]} / {min_games} games)."
                    )
        rows = ranked[:limit]
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        filters = []
        if rule is not None:
            if rule.min_games_pct:
                filters.append(
                    f"qualified (at least {round(100 * rule.min_games_pct)}% of team games)"
                )
            elif rule.min_made:
                filters.append(
                    f"qualified (at least {rule.min_made} "
                    f"{self.metric(rule.min_made_stat or '').label.lower()})"
                )
            else:
                filters.append(
                    f"qualified (at least {rule.min_career_games} games or "
                    f"{rule.min_career_total:,} points)"
                )
        elif m.qualification and not a["qualified"]:
            filters.append("all players")
        if a["rookies_only"]:
            filters.append("rookies")
        if "team_id" in a and rows:
            filters.append(f"with {rows[0].get('team_name')}")
        seasons = "career" if scope == "career" else season_phrase(season, st)
        if scope == "career":
            seasons = f"career, {st.lower()}"
        src = source_line([m.label.lower()], seasons, filters, store)
        return self._result(a, rows, m, src, notes)

    def _result(
        self, a: dict[str, Any], rows: list[dict[str, Any]], m: Metric, src: str, notes: list[str]
    ) -> ToolResult:
        metric_cols = [m.name] + [c for c in (m.per_game_of,) if c and rows and c in rows[0]]
        for c in ("threes_made", "field_goals_made", "free_throws_made", "points"):
            if rows and c in rows[0] and c not in metric_cols:
                metric_cols.append(c)
        if not rows:
            notes.append("No players or teams met the criteria.")
        return ToolResult(
            self.name, a, list(rows[0]) if rows else [], rows, metric_cols, src, [], notes
        )


class Compare(BaseTool):
    name = "compare"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        metrics, scope, st = a["metrics"], a["scope"], a["season_type"]
        if ("player_ids" in a) == ("team_ids" in a):
            raise ToolArgError("give player_ids or team_ids")
        if "team_ids" in a:
            _require_grain(self, metrics, Grain.team_season, "for teams")
            if scope != "season" or "season" not in a:
                raise ToolArgError("team comparisons need scope=season and a season")
            ids = a["team_ids"]
            rows = _rows(
                store,
                f"select team_id, team_name, season, gp, {_cols(metrics)} "
                f"from {TEAM_VIEW} where team_id in ({','.join('?' * len(ids))}) "
                "and season = ? and season_type = ? order by team_id",
                [*ids, a["season"], st],
            )
            src = source_line(_labels(self, metrics), season_phrase(a["season"], st), [], store)
            return ToolResult(
                self.name,
                a,
                list(rows[0]) if rows else [],
                rows,
                metrics,
                src,
                entities={"teams": ids},
            )
        ids = a["player_ids"]
        marks = ",".join("?" * len(ids))
        if scope == "career":
            _require_grain(self, metrics, Grain.player_career, "as career values")
            rows = _rows(
                store,
                f"select player_id, player_name, seasons, first_season, "
                f"last_season, {_cols(metrics)} from {CAREER_VIEW} "
                f"where player_id in ({marks}) and season_type = ?",
                [*ids, st],
            )
            seasons_desc = f"career, {st.lower()}"
            seasons_all = [r["first_season"] for r in rows] + [r["last_season"] for r in rows]
        else:
            _require_grain(self, metrics, Grain.player_season, "per season")
            if scope == "season":
                if "season" not in a:
                    raise ToolArgError("season is required for scope=season")
                where, params = "season = ?", [a["season"]]
                rows = _rows(
                    store,
                    f"select player_id, player_name, season, team_name, gp, "
                    f"{_cols(metrics)} from {SEASON_VIEW} where player_id in ({marks}) "
                    f"and {where} and season_type = ?",
                    [*ids, *params, st],
                )
                seasons_desc = season_phrase(a["season"], st)
            else:
                n = a.get("n_seasons")
                if not n:
                    raise ToolArgError(f"{scope} needs n_seasons")
                direction = "asc" if scope == "first_n_seasons" else "desc"
                rows = _rows(
                    store,
                    f"select * from (select player_id, player_name, season, "
                    f"team_name, gp, {_cols(metrics)}, row_number() over (partition "
                    f"by player_id order by season {direction}) as season_number "
                    f"from {SEASON_VIEW} where player_id in ({marks}) and "
                    f"season_type = ?) where season_number <= ? "
                    "order by player_id, season",
                    [*ids, st, n],
                )
                which = "first" if scope == "first_n_seasons" else "last"
                seasons_desc = f"each player's {which} {n} seasons, {st.lower()}"
            seasons_all = [r["season"] for r in rows]
        # Keep the requested player order.
        rows.sort(key=lambda r: (ids.index(r["player_id"]), r.get("season") or ""))
        nt = self.not_tracked(store, metrics, sorted(set(seasons_all))) if seasons_all else []
        notes = []
        missing = set(ids) - {r["player_id"] for r in rows}
        if missing:
            notes.append(f"No {seasons_desc} data for player id(s) {sorted(missing)}.")
        src = source_line(_labels(self, metrics), seasons_desc, [], store)
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            metrics,
            src,
            nt,
            notes,
            {"players": ids},
        )


class GetTeamStats(BaseTool):
    name = "get_team_stats"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        tid, season, st, metrics = a["team_ids"][0], a["season"], a["season_type"], a["metrics"]
        nt = self.not_tracked(store, metrics, [season])
        tracked = [m for m in metrics if m not in {n.metric for n in nt}]
        rows = _rows(
            store,
            f"select team_id, team_name, season, season_type, gp"
            f"{', ' + _cols(tracked) if tracked else ''} from {TEAM_VIEW} "
            "where team_id = ? and season = ? and season_type = ?",
            [tid, season, st],
        )
        src = source_line(_labels(self, metrics), season_phrase(season, st), [], store)
        notes = [] if rows else [f"No {season_phrase(season, st)} games for this team."]
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            tracked,
            src,
            nt,
            notes,
            {"teams": [tid]},
        )


class GetStandings(BaseTool):
    name = "get_standings"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        where, params = "season = ? and season_type = 'Regular Season'", [a["season"]]
        if "conference" in a:
            where += " and conference = ?"
            params.append(a["conference"])
        order = "conference_rank nulls last" if "conference" in a else "win_pct desc, wins desc"
        sql = (
            f"select team_id, team_name, conference, conference_rank, wins, losses, win_pct "
            f"from {TEAM_VIEW} where {where} order by {order}"
        )
        rows = _rows(store, sql, params)
        if "limit" in a:
            rows = rows[: a["limit"]]
        if "conference" not in a:
            for i, r in enumerate(rows, 1):
                r["league_position"] = i
        conf = f"{a['conference']}ern Conference" if "conference" in a else "league-wide"
        src = source_line(
            ["standings"], season_phrase(a["season"], "Regular Season"), [conf], store
        )
        return ToolResult(
            self.name, a, list(rows[0]) if rows else [], rows, ["wins", "losses", "win_pct"], src
        )


class GetGames(BaseTool):
    name = "get_games"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        types = a.get("season_types") or ["Regular Season"]
        tmarks = ",".join("?" * len(types))
        limit = a.get("limit", a.get("last_n", 100))
        if a.get("streak"):
            return self._streak(a, store, types)
        if a.get("player_ids"):
            pid = a["player_ids"][0]
            pwhere, pparams = f"player_id = ? and season_type in ({tmarks})", [pid, *types]
            if "season" in a:
                pwhere += " and season = ?"
                pparams.append(a["season"])
            sql = (
                f"select game_id, player_id, player_name, game_date, matchup, wl, minutes, pts, "
                f"reb, ast, fg3m from semantic.player_game_log where {pwhere} "
                f"order by game_date desc limit ?"
            )
            rows = _rows(store, sql, [*pparams, a.get("last_n", limit)])
            src = source_line(
                ["game log"],
                a.get("season", "most recent games"),
                [f"last {a['last_n']}" if "last_n" in a else ""],
                store,
            )
            return ToolResult(
                self.name,
                a,
                list(rows[0]) if rows else [],
                rows,
                [],
                src,
                entities={"players": [pid]},
                notes=[] if rows else ["No games found."],
            )
        if a.get("sort") == "player_points_desc":
            sql = (
                f"select game_id, player_id, player_name, game_date, matchup, pts "
                f"from semantic.player_game_log where season = ? and season_type in "
                f"({tmarks}) order by pts desc nulls last, game_date limit ?"
            )
            rows = _rows(store, sql, [a["season"], *types, limit])
            src = source_line(["points in a game"], season_phrase(a["season"], types[0]), [], store)
            return ToolResult(self.name, a, list(rows[0]) if rows else [], rows, [], src)
        where, params = [f"season_type in ({tmarks})"], list(types)
        if "season" in a:
            where.append("season = ?")
            params.append(a["season"])
        if "date" in a:
            where.append("game_date = ?")
            params.append(a["date"])
        if a.get("overtime_only"):
            where.append("overtime")
        for tid in a.get("team_ids", []):
            where.append("? in (home_team_id, away_team_id)")
            params.append(tid)
        if a.get("finals_only"):
            # Finals games: playoff games between that season's champion and its opponent.
            where.append("""game_id in (
                select g.game_id from semantic.games g join semantic.team_titles t
                  on t.season = g.season
                 and least(g.home_team_id, g.away_team_id) = least(t.team_id, t.opponent_team_id)
                 and greatest(g.home_team_id, g.away_team_id)
                     = greatest(t.team_id, t.opponent_team_id)
                where g.season_type = 'Playoffs')""")
        order = "margin desc, game_date" if a.get("sort") == "margin_desc" else "game_date desc"
        sql = (
            f"select game_id, season, season_type, game_date, home_team_name, away_team_name, "
            f"home_pts, away_pts, margin, periods from semantic.games where "
            f"{' and '.join(where)} order by {order} limit ?"
        )
        rows = _rows(store, sql, [*params, limit])
        notes = []
        if not rows:
            notes.append(f"No games on {a['date']}." if "date" in a else "No games found.")
        if a.get("box_leaders") and rows:
            for r in rows:
                for stat in ("pts", "reb", "ast"):
                    lead = _rows(
                        store,
                        f"select player_name, {stat} from "
                        "semantic.player_game_log where game_id = ? "
                        f"order by {stat} desc nulls last limit 1",
                        [r["game_id"]],
                    )
                    if lead:
                        r[f"{stat}_leader"] = lead[0]["player_name"]
                        r[f"{stat}_leader_value"] = lead[0][stat]
        filters = [
            "overtime" if a.get("overtime_only") else "",
            "NBA Finals" if a.get("finals_only") else "",
            f"on {a['date']}" if "date" in a else "",
        ]
        src = source_line(
            ["games"], season_phrase(a.get("season"), ", ".join(types)), filters, store
        )
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            [],
            src,
            [],
            notes,
            {"teams": a["team_ids"]} if a.get("team_ids") else {},
        )

    def _streak(self, a: dict[str, Any], store: SnapshotStore, types: list[str]) -> ToolResult:
        if not a.get("team_ids") or "season" not in a:
            raise ToolArgError("streak needs one team and a season")
        tid = a["team_ids"][0]
        rows = _rows(
            store,
            f"select game_date, winner_team_id = ? as won from semantic.games "
            f"where season = ? and season_type in ({','.join('?' * len(types))}) "
            "and ? in (home_team_id, away_team_id) order by game_date",
            [tid, a["season"], *types, tid],
        )
        want = a["streak"] == "win"
        best = cur = 0
        start = best_start = best_end = None
        for r in rows:
            if r["won"] == want:
                cur += 1
                start = start if cur > 1 else r["game_date"]
                if cur > best:
                    best, best_start, best_end = cur, start, r["game_date"]
            else:
                cur, start = 0, None
        out = [{"team_id": tid, "streak": best, "from": best_start, "to": best_end}]
        src = source_line(
            [f"longest {a['streak']} streak"], season_phrase(a["season"], types[0]), [], store
        )
        return ToolResult(self.name, a, list(out[0]), out, [], src, entities={"teams": [tid]})


class GetCareer(BaseTool):
    name = "get_career"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        pid, st, metrics = a["player_ids"][0], a["season_type"], a["metrics"]
        seasons = [
            r["season"]
            for r in _rows(
                store,
                f"select season from {SEASON_VIEW} where player_id = ? and season_type = ?",
                [pid, st],
            )
        ]
        nt = self.not_tracked(store, metrics, seasons)
        tracked = [m for m in metrics if m not in {n.metric for n in nt}]
        rows = _rows(
            store,
            f"select player_id, player_name, seasons, first_season, last_season"
            f"{', ' + _cols(tracked) if tracked else ''} from {CAREER_VIEW} "
            "where player_id = ? and season_type = ?",
            [pid, st],
        )
        src = source_line(_labels(self, metrics), f"career, {st.lower()}", [], store)
        notes = [] if rows else [f"No {st.lower()} games for this player."]
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            tracked,
            src,
            nt,
            notes,
            {"players": [pid]},
        )


class GetRecord(BaseTool):
    name = "get_record"
    SINGLE_GAME: ClassVar[dict[str, str]] = {
        "most_points_game": "pts",
        "most_threes_game": "fg3m",
        "most_rebounds_game": "reb",
        "most_assists_game": "ast",
    }

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        rec, limit = a["record"], a["limit"]
        notes: list[str] = []
        if rec in self.SINGLE_GAME:
            rows = _rows(
                store,
                "select record, player_id, player_name, value, game_id, "
                "game_date, season from semantic.records where stat = ? "
                "order by value desc, game_date limit ?",
                [self.SINGLE_GAME[rec], limit],
            )
            label = rows[0]["record"].lower() if rows else rec
        elif rec == "career_triple_doubles":
            rows = _rows(
                store,
                "select record, player_id, player_name, value, valid_from from "
                "semantic.records where record_kind = 'career_count' and record ilike "
                "'%triple-double%' order by value desc limit ?",
                [limit],
            )
            label = "career triple-doubles"
            if not rows:
                # Curated table empty (G1 pending): count from box scores, with the caveat.
                rows = _rows(
                    store,
                    f"select player_id, player_name, triple_doubles as value "
                    f"from {CAREER_VIEW} where season_type = 'Regular Season' and "
                    "triple_doubles is not null order by value desc limit ?",
                    [limit],
                )
                notes.append(
                    "Counted from box scores, which are partial before 1996-97; "
                    "earlier players' counts may be low."
                )
        elif rec == "best_regular_season_record":
            rows = _rows(
                store,
                f"select team_id, team_name, season, wins, losses, win_pct "
                f"from {TEAM_VIEW} where season_type = 'Regular Season' "
                "order by win_pct desc, wins desc limit ?",
                [limit],
            )
            label = "best regular-season record"
        else:  # most_championships
            rows = _rows(
                store,
                f"select franchise_id, team_name, championships from "
                f"{TEAM_ALL_TIME_VIEW} where season_type = 'Regular Season' and "
                "championships is not null order by championships desc limit ?",
                [limit],
            )
            label = "championships"
        src = source_line([label], "all time", [], store)
        metric_cols = ["championships"] if rec == "most_championships" else []
        return ToolResult(
            self.name, a, list(rows[0]) if rows else [], rows, metric_cols, src, [], notes
        )


class GetTrend(BaseTool):
    name = "get_trend"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        m, st, entity = self.metric(a["metric"]), a["season_type"], a["entity"]
        where, params = ["season_type = ?"], [st]
        if "season_from" in a:
            where.append("season >= ?")
            params.append(a["season_from"])
        if "season_to" in a:
            where.append("season <= ?")
            params.append(a["season_to"])
        ents: dict[str, list[int]] = {}
        if entity == "player":
            _require_grain(self, [m.name], Grain.player_season, "per player season")
            if not a.get("player_ids"):
                raise ToolArgError("entity=player needs player_ids")
            where.append("player_id = ?")
            params.append(a["player_ids"][0])
            view, keys = SEASON_VIEW, "player_id, player_name, season, gp"
            ents = {"players": a["player_ids"]}
        elif entity == "team":
            _require_grain(self, [m.name], Grain.team_season, "per team season")
            if not a.get("team_ids"):
                raise ToolArgError("entity=team needs team_ids")
            where.append("team_id = ?")
            params.append(a["team_ids"][0])
            view, keys = TEAM_VIEW, "team_id, team_name, season, gp"
            ents = {"teams": a["team_ids"]}
        else:
            _require_grain(self, [m.name], Grain.league_season, "league-wide")
            view, keys = LEAGUE_VIEW, "season, teams"
        rows = _rows(
            store,
            f"select {keys}, {m.name} from {view} where {' and '.join(where)} order by season",
            params,
        )
        seasons = [r["season"] for r in rows]
        nt = self.not_tracked(store, [m.name], seasons[:1]) if seasons else []
        span = f"{seasons[0]} to {seasons[-1]}" if seasons else "no seasons"
        src = source_line(
            [m.label.lower()],
            f"{span}, {st.lower()}",
            ["league-wide" if entity == "league" else ""],
            store,
        )
        return ToolResult(
            self.name,
            a,
            list(rows[0]) if rows else [],
            rows,
            [m.name],
            src,
            nt,
            [] if rows else ["No seasons found."],
            ents,
        )


class GetAwards(BaseTool):
    name = "get_awards"

    def _run(self, a: dict[str, Any], store: SnapshotStore) -> ToolResult:
        award = a["award"]
        where, params = ["award = ?"], [award]
        if "season" in a:
            where.append("season = ?")
            params.append(a["season"])
        if a.get("player_ids"):
            where.append("player_id = ?")
            params.append(a["player_ids"][0])
        if a["mode"] == "count_by_player":
            rows = _rows(
                store,
                "select player_id, player_name, count(*) as awards, "
                "min(season) as first_season, max(season) as last_season "
                f"from semantic.awards where {' and '.join(where)} "
                "group by all order by awards desc, last_season limit 10",
                params,
            )
            src = source_line([f"{award} awards"], "all time", [], store)
            return ToolResult(self.name, a, list(rows[0]) if rows else [], rows, [], src)
        rows = _rows(
            store,
            "select player_id, player_name, season, team_name, team_number "
            f"from semantic.awards where {' and '.join(where)} order by season desc, "
            "team_number nulls first, player_name",
            params,
        )
        metrics: list[str] = []
        if a["include_stats"] and rows:
            metrics = STAT_LINE
            for r in rows:
                stats = _rows(
                    store,
                    f"select {_cols(STAT_LINE)} from {SEASON_VIEW} where "
                    "player_id = ? and season = ? and season_type = 'Regular Season'",
                    [r["player_id"], r["season"]],
                )
                if stats:
                    r.update(stats[0])
        notes = [] if rows else ["No winner in this snapshot for that award and season."]
        src = source_line(
            [award] + (_labels(self, metrics) if metrics else []),
            a.get("season", "all seasons"),
            [],
            store,
        )
        return ToolResult(
            self.name, a, list(rows[0]) if rows else [], rows, metrics, src, [], notes
        )


TOOLS: dict[str, type[BaseTool]] = {
    t.name: t
    for t in (
        GetPlayerStats,
        GetLeaders,
        Compare,
        GetTeamStats,
        GetStandings,
        GetGames,
        GetCareer,
        GetRecord,
        GetTrend,
        GetAwards,
    )
}


def run_tool(name: str, args: dict[str, Any], store: SnapshotStore) -> ToolResult:
    if name not in TOOLS:
        raise ToolArgError(f"unknown tool {name!r}")
    return TOOLS[name]().run(args, store)
