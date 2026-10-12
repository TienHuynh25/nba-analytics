"""Router, refusals, knowledge answers, answer cache, assistant (phase 4)."""

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from app.assistant import Assistant, Session
from app.cache import AnswerCache
from app.interfaces import Chunk, Message
from app.rag.answer import KnowledgePath
from app.rag.bm25 import BM25Retriever
from app.rag.glossary import glossary_chunks
from app.router import REFUSALS, Router
from app.snapshot import FileSnapshotStore

SGA = 1628983


class Script:
    model = "script"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.prompts: list[Sequence[Message]] = []

    def complete(self, messages: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        self.prompts.append(messages)
        r = self.replies.pop(0)
        return json.dumps(r) if isinstance(r, dict) else str(r)


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def test_router_parses_and_falls_back_to_stats() -> None:
    r = Router(Script([{"path": "refuse", "refusal_reason": "betting"}, "garbage"]))
    d = r.route("Should I bet on the Lakers tonight?")
    assert d.path == "refuse" and d.refusal == REFUSALS["betting"]
    assert r.route("something").path == "stats"  # unparseable: stats still verifies numbers


def test_refusals_are_one_plain_sentence() -> None:
    for text in REFUSALS.values():
        assert text.count(".") == 1 and text.endswith(".")


def test_glossary_has_every_metric_rule_and_per() -> None:
    ids = {c.id for c in glossary_chunks()}
    assert {
        "true_shooting_pct",
        "usage_rate",
        "net_rating",
        "per_game_leader",
        "player_efficiency_rating",
    } <= ids


def test_knowledge_numbers_must_come_from_cited_chunks() -> None:
    retr = BM25Retriever(glossary_chunks())
    ok = KnowledgePath(
        Script(["TS% = PTS / (2 x (FGA + 0.44 x FTA)) [true_shooting_pct]."]), retr
    ).answer("What is true shooting percentage?")
    assert ok.status == "verified" and ok.cited == ["true_shooting_pct"]
    assert "true_shooting_pct" in ok.chunks[:6]
    bad = KnowledgePath(Script(["It uses 0.5 [true_shooting_pct].", "Still 0.5."]), retr).answer(
        "What is true shooting percentage?"
    )
    assert bad.status == "fallback" and "0.44" in bad.text


def test_uncited_number_fails_even_if_true() -> None:
    k = KnowledgePath(
        Script(["The factor is 0.44.", "The factor is 0.44."]),
        BM25Retriever([Chunk("ts", "TS uses 0.44 * FTA", "glossary")]),
    )
    assert k.answer("ts factor").status == "fallback"


def test_cache_hit_skips_query_and_generation(store: FileSnapshotStore) -> None:
    call = {
        "tool": "get_player_stats",
        "args": {"player_ids": [SGA], "season": "2024-25", "metrics": ["points_per_game"]},
    }
    llm = Script(
        [
            {"path": "stats", "refusal_reason": None},
            call,
            "Shai Gilgeous-Alexander averaged 32.7 points per game.",
            {"path": "stats", "refusal_reason": None},
            call,
        ]
    )
    cache = AnswerCache()
    a = Assistant(store, llm, cache=cache)
    first = a.ask("SGA points per game this season?", Session())
    second = a.ask("SGA scoring average this season?", Session())
    assert first.text == second.text and cache.hits == 1
    assert llm.replies == []  # no answer generation the second time
    cache.clear("nba_20991231")
    assert len(cache) == 0


def test_refuse_path_never_calls_tools(store: FileSnapshotStore) -> None:
    llm = Script([{"path": "refuse", "refusal_reason": "non_nba"}])
    r = Assistant(store, llm).ask("What is Caitlin Clark averaging?", Session())
    assert r.path == "refuse" and r.behaviour == "decline" and r.text == REFUSALS["non_nba"]
