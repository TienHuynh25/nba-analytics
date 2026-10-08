"""Vector index and hybrid retrieval (tasks 4.2-4.4), with a fake embedder: no Ollama needed."""

import hashlib
from collections.abc import Sequence
from pathlib import Path

from app.interfaces import Chunk
from app.rag.glossary import glossary_chunks
from app.rag.index import VectorIndex
from app.rag.retrieve import HybridRetriever, rrf

DIM = 64


class FakeEmbed:
    """Bag-of-words hashing embedder: similar texts get similar vectors."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += len(texts)
        out = []
        for t in texts:
            v = [0.0] * DIM
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
            n = sum(x * x for x in v) ** 0.5 or 1.0
            out.append([x / n for x in v])
        return out


def test_rebuild_reembeds_only_changed_chunks(tmp_path: Path) -> None:
    idx = VectorIndex(tmp_path)
    emb = FakeEmbed()
    chunks = glossary_chunks()
    assert idx.build(chunks, emb, "0.3.0") == len(chunks)
    assert idx.build(chunks, emb, "0.3.0") == 0  # unchanged registry: no re-embed
    edited = [
        Chunk(c.id, c.text + " Edited.", c.doc_type) if c.id == "net_rating" else c for c in chunks
    ]
    assert idx.build(edited, emb, "0.3.1") == 1
    assert idx.registry_version() == "0.3.1"


def test_hybrid_finds_the_definition_and_respects_doc_types(tmp_path: Path) -> None:
    idx = VectorIndex(tmp_path)
    chunks = [
        *glossary_chunks(),
        Chunk("tool:get_leaders", "Tool get_leaders: true shooting leaders", "tool_card"),
    ]
    emb = FakeEmbed()
    idx.build(chunks, emb, "0.3.0")
    r = HybridRetriever(idx, emb, None, ["glossary"])
    top = [c.id for c in r.search("How is true shooting percentage calculated?", 6)]
    assert "true_shooting_pct" in top and len(top) <= 6
    assert all(not i.startswith("tool:") for i in top)


def test_reranker_order_wins(tmp_path: Path) -> None:
    idx = VectorIndex(tmp_path)
    emb = FakeEmbed()
    idx.build(glossary_chunks(), emb, "0.3.0")

    def rerank(q: str, texts: Sequence[str]) -> list[float]:
        return [1.0 if "Net rating" in t else 0.0 for t in texts]

    r = HybridRetriever(idx, emb, rerank, ["glossary"])
    assert r.search("rating", 6)[0].id == "net_rating"


def test_rrf_fuses_rankings() -> None:
    assert rrf([["a", "b", "c"], ["b", "c", "a"]])[0] == "b"
