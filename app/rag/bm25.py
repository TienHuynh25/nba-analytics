"""A small BM25 retriever behind the Retriever interface.

The SQL fallback uses it for schema cards until the hybrid index exists (task 3.16 -> 4.4).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from app.interfaces import Chunk

_WORD = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    # Split identifiers too: points_per_game -> points, per, game.
    return _WORD.findall(text.lower().replace("_", " ").replace(".", " "))


class BM25Retriever:
    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(c.text)) for c in self.chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / len(self.lens) if self.lens else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int) -> list[Chunk]:
        q = tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                f = d.get(t)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1))
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [
            Chunk(self.chunks[i].id, self.chunks[i].text, self.chunks[i].doc_type, s)
            for s, i in scored[:k]
        ]
