"""SQL fallback for stats questions no typed tool fits (task 3.16).

retrieve schema cards -> generate SQL -> parser guardrails (:mod:`app.sql_guard`) -> run on a
locked-down, read-only connection with a 5 s watchdog -> numeric verifier.

The connection allows no file access except the snapshot's own shots folder
(``enable_external_access=false``, ``allowed_directories``, ``lock_configuration=true``), so
even a query that bypassed the parser could not read ``data/raw``. DuckDB has no statement
timeout, so a watchdog thread calls ``interrupt()`` after 5 s. If the SQL fails (guardrail or
execution error), the error goes back to the model once for repair. Then the fallback gives up
and says so.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from app.interfaces import LLMClient, Message, Retriever
from app.snapshot import connect_read_only
from app.sql_guard import GuardError, check

TIMEOUT_S = 5.0
CARDS_K = 12


class QueryTimeout(RuntimeError):
    pass


def locked_connection(db: Path, shots_dir: Path | None) -> duckdb.DuckDBPyConnection:
    """Read-only, no file access outside the snapshot's shots folder, configuration locked."""
    return connect_read_only(db, shots_dir if shots_dir is not None else Path("/nonexistent"))


def run_with_timeout(
    con: duckdb.DuckDBPyConnection, sql: str, timeout_s: float = TIMEOUT_S
) -> tuple[list[str], list[tuple[Any, ...]]]:
    fired = threading.Event()

    def stop() -> None:
        fired.set()
        con.interrupt()

    timer = threading.Timer(timeout_s, stop)
    timer.start()
    try:
        cur = con.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return cols, rows
    except duckdb.InterruptException as exc:
        raise QueryTimeout(f"query stopped after {timeout_s:.0f} s") from exc
    except duckdb.Error:
        if fired.is_set():
            raise QueryTimeout(f"query stopped after {timeout_s:.0f} s") from None
        raise
    finally:
        timer.cancel()


SQL_SCHEMA = {
    "type": "object",
    "properties": {"sql": {"type": "string"}},
    "required": ["sql"],
    "additionalProperties": False,
}

SYSTEM = """You write one DuckDB SELECT query that answers an NBA stats question.
Use only the semantic views and columns described below. Never invent columns.
Seasons are strings like '2025-26'. season_type is 'Regular Season', 'Playoffs' or 'PlayIn';
use 'Regular Season' unless the question names the playoffs or Play-In.
Percentages are stored as fractions (0.476 means 47.6%).
Return JSON: {"sql": "..."}."""


@dataclass
class FallbackResult:
    ok: bool
    sql: str | None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    attempts: int = 0
    error: str | None = None
    cards: list[str] = field(default_factory=list)


class SqlFallback:
    def __init__(
        self, llm: LLMClient, retriever: Retriever, db: Path, shots_dir: Path | None
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.con = locked_connection(db, shots_dir)

    def _generate(self, question: str, cards: Sequence[str], feedback: str | None) -> str:
        msgs = [
            Message("system", SYSTEM + "\n\nSchema:\n" + "\n".join(cards)),
            Message("user", question),
        ]
        if feedback:
            msgs.append(Message("user", f"That query failed: {feedback}\nFix it."))
        raw = self.llm.complete(msgs, schema=SQL_SCHEMA)
        try:
            return str(json.loads(raw)["sql"])
        except (json.JSONDecodeError, KeyError, TypeError):
            m = re.search(r"select .*", raw, re.IGNORECASE | re.DOTALL)
            return m.group(0) if m else raw

    def answer(self, question: str) -> FallbackResult:
        cards = [c.text for c in self.retriever.search(question, CARDS_K)]
        feedback: str | None = None
        sql: str | None = None
        for attempt in (1, 2):  # one repair attempt
            sql = self._generate(question, cards, feedback)
            try:
                safe = check(sql)
                cols, rows = run_with_timeout(self.con, safe)
                return FallbackResult(True, safe, cols, rows, attempt, None, cards)
            except (GuardError, QueryTimeout, duckdb.Error) as exc:
                feedback = str(exc).splitlines()[0][:500]
        return FallbackResult(False, sql, attempts=2, error=feedback, cards=cards)
