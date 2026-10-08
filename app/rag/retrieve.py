"""Hybrid retrieval (task 4.4): BM25 + dense, Reciprocal Rank Fusion to the top 40, then the
``bge-reranker-v2-m3`` cross-encoder keeps 6. Implements the Retriever interface, optionally
limited to some doc types (knowledge answers read the glossary; the SQL fallback reads schema
cards).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from app.config import RerankerConfig
from app.interfaces import Chunk, Retriever
from app.rag.bm25 import BM25Retriever
from app.rag.index import Embed, VectorIndex

RRF_K = 60
Rerank = Callable[[str, Sequence[str]], list[float]]


def cross_encoder(cfg: RerankerConfig) -> Rerank:
    import torch
    from sentence_transformers import CrossEncoder

    device = cfg.device
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    kwargs = {"torch_dtype": torch.float16} if cfg.half_precision and device != "cpu" else {}
    model = CrossEncoder(cfg.model, device=device, model_kwargs=kwargs)

    def rerank(query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        return [float(s) for s in model.predict([(query, t) for t in texts])]

    return rerank


def rrf(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda c: (-scores[c], c))


class HybridRetriever:
    def __init__(
        self,
        index: VectorIndex,
        embed: Embed,
        rerank: Rerank | None,
        doc_types: Sequence[str] | None = None,
        fusion_top_k: int = 40,
        keep: int = 6,
    ) -> None:
        self.index = index
        self.embed = embed
        self.rerank = rerank
        self.doc_types = list(doc_types) if doc_types else None
        self.fusion_top_k = fusion_top_k
        self.keep = keep
        self._chunks = {c.id: c for c in index.chunks(self.doc_types)}
        self._bm25 = BM25Retriever(list(self._chunks.values()))

    def search(self, query: str, k: int) -> list[Chunk]:
        dense = self.index.search(self.embed([query])[0], self.fusion_top_k, self.doc_types)
        sparse = self._bm25.search(query, self.fusion_top_k)
        fused = rrf([[c.id for c in dense], [c.id for c in sparse]])[: self.fusion_top_k]
        cands = [self._chunks[i] for i in fused if i in self._chunks]
        if self.rerank is not None:
            scores = self.rerank(query, [c.text for c in cands])
            order = sorted(range(len(cands)), key=lambda i: -scores[i])
            cands = [Chunk(cands[i].id, cands[i].text, cands[i].doc_type, scores[i]) for i in order]
        return cands[: min(k, self.keep)]


def default_retrievers(
    fallback_chunks: Sequence[Chunk], use_reranker: bool = True
) -> tuple[Retriever, Retriever]:
    """(knowledge retriever, schema-card retriever): hybrid when the index exists, else BM25."""
    from app.config import models
    from app.rag.index import INDEX_DIR, ollama_embedder

    if not (INDEX_DIR / "chunks.lance").exists():
        from app.rag.glossary import glossary_chunks

        return BM25Retriever(glossary_chunks()), BM25Retriever(list(fallback_chunks))
    cfg = models()
    index = VectorIndex()
    embed = ollama_embedder(cfg.embeddings)
    rerank = cross_encoder(cfg.reranker) if use_reranker else None
    kw = {"fusion_top_k": cfg.retrieval.fusion_top_k, "keep": cfg.reranker.keep}
    return (
        HybridRetriever(index, embed, rerank, ["glossary"], **kw),
        HybridRetriever(index, embed, rerank, ["schema_card"], fusion_top_k=40, keep=12),
    )
