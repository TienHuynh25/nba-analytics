"""The interface the harness drives, and the stub used for the baseline run (task 2.22).

The real pipeline (phase 3: stats path; phase 4: router, RAG, agent) implements
:class:`Answerer`. Until the router exists, the harness passes each case's gold path so stats
cases go straight to the stats path (gap G11).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Protocol

import yaml

from eval.harness.scorers import AnswerRecord


class Answerer(Protocol):
    name: str

    def new_conversation(self) -> None: ...

    def answer(self, question: str, gold_path: str | None = None) -> AnswerRecord: ...


class StubAnswerer:
    """Baseline: routes by the gold path if given, never resolves anything, answers nothing."""

    name = "stub"

    def new_conversation(self) -> None:
        pass

    def answer(self, question: str, gold_path: str | None = None) -> AnswerRecord:
        t = time.perf_counter()
        rec = AnswerRecord(path=gold_path, text="I don't know yet.", behaviour="answer")
        rec.latency_ms = (time.perf_counter() - t) * 1000
        return rec


def eval_db() -> Path:
    """The pinned eval snapshot's database, or NBA_EVAL_DB (dev smoke runs only)."""
    env = os.environ.get("NBA_EVAL_DB")
    if env:
        return Path(env)
    snaps = Path(__file__).resolve().parent.parent / "snapshots.yaml"
    data = yaml.safe_load(snaps.read_text()) if snaps.exists() else None
    if not data or "eval" not in data:
        raise RuntimeError("eval snapshot not built yet (task 2.1); set NBA_EVAL_DB to smoke-test")
    return Path(data["eval"]["db"])


class StatsAnswerer:
    """Phase 3: the stats path, with gold-path routing (G11). Non-stats cases are not answered."""

    name = "stats"

    def __init__(self) -> None:
        from app.config import models
        from app.interfaces import make_llm
        from app.rag.bm25 import BM25Retriever
        from app.rag.cards import schema_cards
        from app.snapshot import FileSnapshotStore
        from app.sql_fallback import SqlFallback
        from app.state import ConversationState
        from app.stats_path import StatsPath

        db = eval_db()
        shots = Path(os.environ.get("NBA_EVAL_SHOTS", db.parent / "shots"))
        store = FileSnapshotStore(db, shots_dir=shots)
        llm = make_llm(models().llm)
        fallback = SqlFallback(
            llm,
            BM25Retriever(schema_cards(store.connection())),
            db,
            shots if shots.exists() else None,
        )
        self.path = StatsPath(store, llm, fallback=fallback)
        self.model = llm.model
        self._new_state = ConversationState
        self.state = ConversationState()

    def new_conversation(self) -> None:
        self.state = self._new_state()

    def answer(self, question: str, gold_path: str | None = None) -> AnswerRecord:
        if gold_path not in (None, "stats", "mixed"):
            return AnswerRecord(path=gold_path, text="", behaviour="answer")
        a, self.state = self.path.answer(question, self.state)
        self.last = a
        return AnswerRecord(
            path="stats",
            entities=a.entities,
            tool_call=a.tool_call,
            sql=a.sql,
            rows=a.rows,
            text=a.text,
            behaviour=a.behaviour,
            args_text=a.args_text,
            unverified_numbers=a.unverified_numbers,
            latency_ms=a.latency_ms,
        )


class FullAnswerer(StatsAnswerer):
    """Phase 4: router -> stats, knowledge, mixed or refuse. Cache off, as the spec requires."""

    name = "full"

    def __init__(self) -> None:
        super().__init__()
        from app.assistant import Assistant, Session

        self.assistant = Assistant(self.path.store, self.path.llm, fallback=self.path.fallback)
        self.assistant.stats = self.path  # the same stats path (no cache)
        self._session = Session
        self.session = Session()

    def new_conversation(self) -> None:
        self.session = self._session()

    def answer(self, question: str, gold_path: str | None = None) -> AnswerRecord:
        r = self.assistant.ask(question, self.session)
        a, k = r.stats, r.knowledge
        rec = AnswerRecord(
            path=r.path,
            text=r.text,
            behaviour=r.behaviour,
            latency_ms=r.latency_ms,
            chunks=k.chunks if k else [],
        )
        if a is not None:
            rec.entities, rec.tool_call, rec.sql, rec.rows = a.entities, a.tool_call, a.sql, a.rows
            rec.args_text, rec.unverified_numbers = a.args_text, a.unverified_numbers
        return rec


ANSWERERS: dict[str, type] = {"stub": StubAnswerer, "stats": StatsAnswerer, "full": FullAnswerer}
