"""The stats path: typed tools first, SQL fallback second (phase 3).

question -> relative time (snapshot clock) -> entities -> conversation carry-over
  -> clarify if ambiguous
  -> LLM picks a tool and fills its arguments (JSON-schema constrained)
  -> validate (one retry with the error) -> run on semantic views
     (no fitting tool, or two invalid calls -> SQL fallback)
  -> "not tracked" answers come straight from stat_availability
  -> LLM writes the words from display-rounded values
  -> numeric verifier (regenerate once, else the result table) -> source line

Numbers come from code, words from the model.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.cache import AnswerCache
from app.cache import key as cache_key
from app.entities import Entity, EntityResolver
from app.format import display_rows, table
from app.interfaces import LLMClient, Message, SnapshotStore
from app.rag.cards import tool_cards
from app.sql_fallback import SqlFallback
from app.state import Context, ConversationState, carry_over, update
from app.timeparse import SnapshotClock, resolve
from app.tools.base import INT, ToolArgError, ToolError, ToolResult
from app.tools.schemas import load_schema
from app.tools.stats import TOOLS, run_tool
from app.verifier import Evidence, ResultValue, finalize
from metrics.schema import registry

_TOKEN_LIKE = re.compile(r"\d{4}-\d{2}(-\d{2})?")
_ALL_PLAYERS = re.compile(
    r"\b(all players|no minimum|unqualified|regardless of games)\b", re.IGNORECASE
)
OPINION = re.compile(
    r"\b(better|best|greatest|goat|more dominant|overrated|underrated)\b", re.IGNORECASE
)


@dataclass
class Answer:
    text: str
    behaviour: str  # answer | clarify | not_tracked | no_verdict | error
    path: str = "stats"
    entities: dict[str, list[int]] = field(default_factory=dict)
    tool_call: dict[str, Any] | None = None
    sql: str | None = None
    rows: list[list[Any]] | None = None
    source: str | None = None
    status: str | None = None  # verified | regenerated | fallback
    unverified_numbers: int = 0
    args_text: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # numbers the verifier refused first
    latency_ms: float = 0.0


def metric_catalog() -> str:
    """Every registry metric the tools accept, with its label and aliases, for the model."""
    lines = ["Metrics (use these exact names in metric / metrics):"]
    for m in registry().metrics:
        alias = f" (also: {', '.join(m.aliases[:6])})" if m.aliases else ""
        lines.append(f"- {m.name}: {m.label}{alias}")
    return "\n".join(lines)


def call_schema() -> dict[str, Any]:
    """{"tool": name, "args": {...}} constrained to one tool's argument schema each."""
    options = []
    for name in TOOLS:
        s = load_schema(name)
        args = {k: v for k, v in s.items() if k not in ("$schema", "description")}
        options.append(
            {
                "type": "object",
                "properties": {"tool": {"const": name}, "args": args},
                "required": ["tool", "args"],
                "additionalProperties": False,
            }
        )
    options.append(
        {
            "type": "object",
            "properties": {"tool": {"const": "none"}, "args": {"type": "object"}},
            "required": ["tool", "args"],
            "additionalProperties": False,
        }
    )
    return {"anyOf": options}


TOOL_SYSTEM = """You turn an NBA stats question into ONE call of one of these tools.
Fill arguments only from the question and the resolved context below. Use the given ids.
Seasons are like "2025-26". Leave season_type out unless the question names playoffs or Play-In.
Conventions:
- "Who leads", "most", "highest", "best", "fastest" means limit 1; "top N" means limit N.
- Leave "qualified" out (the league's minimums apply) unless the question asks for all players.
- A player's "averages", "stats" or "stat line" means metrics ["stat_line"].
- "Rookie" stats mean the player's rookie season (given in the context) with get_player_stats.
- Career totals or all-time questions about one player use get_career; all-time leaders use
  get_leaders with scope "career".
If no tool fits, answer {"tool": "none", "args": {}}.

Tools:
"""

ANSWER_SYSTEM = """You answer an NBA stats question in one to three plain sentences.
Use ONLY the result rows given, and copy every number exactly as written there.
Do not add any other numbers, do not compute new numbers, and do not round differently.
Do not state a source line; it is added for you.
{extra}"""


class StatsPath:
    def __init__(
        self,
        store: SnapshotStore,
        llm: LLMClient,
        resolver: EntityResolver | None = None,
        fallback: SqlFallback | None = None,
        cache: AnswerCache | None = None,
    ) -> None:
        self.store = store
        self.cache = cache
        self.llm = llm
        self.resolver = resolver or EntityResolver(store.connection())
        self.fallback = fallback
        self._cards = "\n\n".join(c.text for c in tool_cards()) + "\n\n" + metric_catalog()
        self._system = TOOL_SYSTEM + self._cards
        self._schema = call_schema()
        row = (
            store.connection()
            .execute("select max(season) from semantic.games where season_type = 'Regular Season'")
            .fetchone()
        )
        self.clock = SnapshotClock(
            date.fromisoformat(str(store.manifest["as_of_date"])[:10]), str(row[0]) if row else ""
        )

    # -- step: choose the tool ------------------------------------------------------------------
    def _context_text(self, ctx: Context, state: ConversationState) -> str:
        lines = []
        con = self.store.connection()
        for e in ctx.players:
            row = con.execute(
                "select rookie_season from semantic.players where player_id = ?", [e.id]
            ).fetchone()
            rookie = f", rookie season {row[0]}" if row and row[0] else ""
            lines.append(f"player: {e.name} -> player_ids [{e.id}]{rookie}")
        for e in ctx.teams:
            lines.append(f"team: {e.name} -> team_ids [{e.id}]")
        if ctx.season:
            lines.append(f"season: {ctx.season}")
        if ctx.season_type:
            lines.append(f"season_type: {ctx.season_type}")
        lines.append(
            f"today: {self.clock.today}, last night: {self.clock.last_night}, "
            f"this season: {self.clock.this_season}, "
            f"last season: {self.clock.last_season}"
        )
        lines.append(f"conversation so far: {state.summary()}")
        return "\n".join(lines)

    def _choose(
        self, question: str, ctx: Context, state: ConversationState, feedback: str | None
    ) -> tuple[str, dict[str, Any]]:
        msgs = [
            Message("system", self._system),
            Message(
                "user",
                f"Resolved context:\n{self._context_text(ctx, state)}\n\nQuestion: {question}",
            ),
        ]
        if feedback:
            msgs.append(Message("user", f"That call was invalid: {feedback}. Fix it."))
        raw = self.llm.complete(msgs, schema=self._schema)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ToolArgError(f"not a JSON tool call: {raw[:200]}") from exc
        if not isinstance(data, dict):
            raise ToolArgError("the tool call must be a JSON object")
        tool, args = data.get("tool"), data.get("args")
        if not isinstance(tool, str) or (tool not in TOOLS and tool != "none"):
            raise ToolArgError(f"unknown tool {tool!r}; use one of {', '.join(TOOLS)} or none")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ToolArgError("args must be a JSON object")
        return tool, args

    def _fill(
        self, tool: str, args: dict[str, Any], ctx: Context, question: str = ""
    ) -> dict[str, Any]:
        """Fill resolved ids and the season from the context when the model left them out.

        These are facts the code already resolved, not choices for the model.
        """
        props = load_schema(tool)["properties"]
        out = dict(args)
        if (
            "player_ids" in props
            and not out.get("player_ids")
            and ctx.players
            and not (tool == "compare" and out.get("team_ids"))
        ):
            cap = props["player_ids"].get("maxItems", len(ctx.players))
            out["player_ids"] = [e.id for e in ctx.players][:cap]
        if (
            "team_ids" in props
            and not out.get("team_ids")
            and ctx.teams
            and not (out.get("player_ids"))
        ):
            cap = props["team_ids"].get("maxItems", len(ctx.teams))
            out["team_ids"] = [e.id for e in ctx.teams][:cap]
        needs_season = tool in ("get_player_stats", "get_team_stats", "get_standings") or (
            tool in ("get_leaders", "compare") and out.get("scope", "season") == "season"
        )
        if needs_season and "season" in props and not out.get("season"):
            out["season"] = ctx.season or self.clock.this_season
        if ctx.season_type and "season_type" in props and "season_type" not in out:
            out["season_type"] = ctx.season_type
        # Ids must come from the resolved context: drop any the model invented.
        known_p = {e.id for e in ctx.players}
        known_t = {e.id for e in ctx.teams}
        for k, known in (("player_ids", known_p), ("team_ids", known_t)):
            if isinstance(out.get(k), list):
                out[k] = [i for i in out[k] if i in known]
                if not out[k]:
                    del out[k]
        if "team_id" in out and out["team_id"] not in known_t:
            del out["team_id"]
        # Qualification minimums are the registry's default, not the model's choice (spec).
        if "qualified" in out and not _ALL_PLAYERS.search(question):
            del out["qualified"]
        return out

    # -- step: write the answer -----------------------------------------------------------------
    def _compose(
        self, question: str, result: ToolResult, opinion: bool
    ) -> tuple[str, str, list[str]]:
        rows = display_rows(result.rows[:25], result.metrics)
        measured = ", ".join(registry().metric(m).label for m in result.metrics) or "see rows"
        extra = f"The rows measure: {measured}. Describe them as exactly that. " + (
            "This is an opinion question: give the relevant stats side by side and "
            "do not say who is better."
            if opinion
            else ""
        )
        if result.notes:
            extra += " Notes to mention if relevant: " + " ".join(result.notes)
        values = [*result.values(), ResultValue(float(len(result.rows)), INT)]
        # Seasons and dates that appear in the result rows (a career's first and last season,
        # a game date) may be stated too, as whole tokens.
        literals = [
            str(v)
            for r in result.rows
            for v in r.values()
            if isinstance(v, str | date) and _TOKEN_LIKE.fullmatch(str(v))
        ]
        ev = Evidence(values=values, args_text=[*result.args_text(), *literals])

        def generate(feedback: list[str] | None) -> str:
            msgs = [
                Message("system", ANSWER_SYSTEM.format(extra=extra)),
                Message("user", f"Question: {question}\nResult rows: {json.dumps(rows)}"),
            ]
            if feedback:
                msgs.append(
                    Message(
                        "user",
                        "These numbers were not in the result rows: "
                        + ", ".join(feedback)
                        + ". Rewrite without them.",
                    )
                )
            return self.llm.complete(msgs).strip()

        def fallback() -> str:
            return "Here are the numbers:\n" + table(result.rows, result.metrics)

        final = finalize(generate, ev, fallback)
        return final.text, final.status, final.first_check.unmatched

    # -- main -----------------------------------------------------------------------------------
    def answer(
        self, question: str, state: ConversationState | None = None
    ) -> tuple[Answer, ConversationState]:
        t0 = time.perf_counter()
        state = state or ConversationState()
        when = resolve(question, self.clock)
        res = self.resolver.resolve(question)
        ctx = carry_over(question, res, when, state)
        ents = {
            k: v
            for k, v in (
                ("players", [e.id for e in ctx.players]),
                ("teams", [e.id for e in ctx.teams]),
            )
            if v
        }

        def done(a: Answer, new_state: ConversationState) -> tuple[Answer, ConversationState]:
            a.latency_ms = (time.perf_counter() - t0) * 1000
            a.entities = a.entities or ents
            return a, new_state

        if ctx.ambiguous:
            return done(Answer(ctx.ambiguous[0].question(), "clarify"), state)

        feedback = None
        result: ToolResult | None = None
        tool: str = "none"
        args: dict[str, Any] = {}
        for _ in range(2):
            try:
                tool, args = self._choose(question, ctx, state, feedback)
                if tool == "none":
                    break
                args = self._fill(tool, args, ctx, question)
                if self.cache is not None:
                    hit = self.cache.get(cache_key(tool, args, self.store.snapshot_id))
                    if hit is not None:
                        a, new_state = hit
                        return done(
                            dataclasses.replace(a),
                            update(
                                state,
                                ctx,
                                tool,
                                args,
                                new_state.result_players,
                                new_state.result_teams,
                            ),
                        )
                result = run_tool(tool, args, self.store)
                break
            except (ToolArgError, ToolError) as exc:
                feedback = str(exc)
                result = None
        if result is None:
            return done(self._sql(question, ctx), state)

        call = {"tool": tool, "args": args}
        if result.not_tracked and not result.metrics:
            # Every requested stat predates tracking: say so and name the first season.
            text = " ".join(n.sentence() for n in result.not_tracked)
            a = Answer(
                f"{text}\n\n{result.source}",
                "not_tracked",
                tool_call=call,
                source=result.source,
                args_text=result.args_text(),
            )
            return done(a, update(state, ctx, tool, args))
        opinion = bool(OPINION.search(question))
        text, status, rejected = self._compose(question, result, opinion)
        if result.not_tracked:
            text += " " + " ".join(n.sentence() for n in result.not_tracked)
        a = Answer(
            f"{text}\n\n{result.source}",
            "no_verdict" if opinion else "answer",
            tool_call=call,
            source=result.source,
            status=status,
            rows=[list(r.values()) for r in result.rows],
            args_text=result.args_text(),
            rejected=rejected,
        )
        # The first row's player or team (e.g. the leader) is what "his" or "their" refers to next.
        top = result.rows[0] if result.rows else {}
        rp = (
            (Entity("player", top["player_id"], str(top.get("player_name")), "", "result"),)
            if "player_id" in top
            else ()
        )
        rt = (
            (Entity("team", top["team_id"], str(top.get("team_name")), "", "result"),)
            if "team_id" in top and "player_id" not in top
            else ()
        )
        new_state = update(state, ctx, tool, args, result_players=rp, result_teams=rt)
        if self.cache is not None and a.status != "fallback":
            self.cache.put(cache_key(tool, args, self.store.snapshot_id), (a, new_state))
        return done(a, new_state)

    def _sql(self, question: str, ctx: Context) -> Answer:
        if self.fallback is None:
            return Answer("I couldn't find a tool for that question.", "error")
        r = self.fallback.answer(question)
        if not r.ok:
            return Answer("I couldn't answer that from the stats data.", "error", sql=r.sql)
        rows = [dict(zip(r.columns, row, strict=True)) for row in r.rows]
        result = ToolResult("sql_fallback", {}, r.columns, rows, [], "query on semantic views")
        text, status, rejected = self._compose(question, result, False)
        latest = self.store.manifest.get("latest_game_date") or ""
        src = f"SQL on semantic views · data through {latest}".strip()
        return Answer(
            f"{text}\n\n{src}",
            "answer",
            path="stats",
            sql=r.sql,
            rows=[list(x) for x in r.rows],
            source=src,
            status=status,
            rejected=rejected,
        )
