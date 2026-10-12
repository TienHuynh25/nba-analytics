"""The assistant: router -> stats, knowledge, mixed or a refusal (phase 4).

Mixed questions (4.8) run the stats path (one tool call) and the knowledge path (one
retrieval), at most 3 tool calls in all, and return one answer made of both verified parts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.cache import AnswerCache
from app.interfaces import LLMClient, Retriever, SnapshotStore
from app.rag.answer import KnowledgeAnswer, KnowledgePath
from app.rag.bm25 import BM25Retriever
from app.rag.glossary import glossary_chunks
from app.router import Router
from app.sql_fallback import SqlFallback
from app.state import ConversationState
from app.stats_path import Answer, StatsPath


@dataclass
class Session:
    state: ConversationState = field(default_factory=ConversationState)


@dataclass
class Reply:
    text: str
    path: str  # stats | knowledge | mixed | refuse
    behaviour: str
    stats: Answer | None = None
    knowledge: KnowledgeAnswer | None = None
    latency_ms: float = 0.0


class Assistant:
    def __init__(
        self,
        store: SnapshotStore,
        llm: LLMClient,
        retriever: Retriever | None = None,
        fallback: SqlFallback | None = None,
        cache: AnswerCache | None = None,
    ) -> None:
        self.router = Router(llm)
        self.stats = StatsPath(store, llm, fallback=fallback, cache=cache)
        self.knowledge = KnowledgePath(llm, retriever or BM25Retriever(glossary_chunks()))

    def ask(self, question: str, session: Session) -> Reply:
        t0 = time.perf_counter()
        decision = self.router.route(question, session.state.summary())
        if decision.path == "refuse":
            r = Reply(decision.refusal or "", "refuse", "decline")
        elif decision.path == "knowledge":
            k = self.knowledge.answer(question)
            r = Reply(
                f"{k.text}\n\nSource: stat glossary ({', '.join(k.cited) or 'none'})",
                "knowledge",
                "answer",
                knowledge=k,
            )
        elif decision.path == "mixed":
            a, session.state = self.stats.answer(question, session.state)
            k = self.knowledge.answer(question)
            r = Reply(f"{a.text}\n\n{k.text}", "mixed", a.behaviour, stats=a, knowledge=k)
        else:
            a, session.state = self.stats.answer(question, session.state)
            r = Reply(a.text, "stats", a.behaviour, stats=a)
        r.latency_ms = (time.perf_counter() - t0) * 1000
        return r
