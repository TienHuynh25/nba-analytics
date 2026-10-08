"""The vector index (tasks 4.2, 4.3): glossary, schema cards and tool cards in LanceDB.

Stat rows are never embedded. Every chunk carries doc_type, metric, registry_version, updated_at
and a content hash. A rebuild re-embeds only chunks whose text changed, so an unchanged registry
causes no re-embedding. The index lives in ``data/index/`` (git-ignored).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

from app.config import REPO_ROOT, EmbeddingsConfig
from app.interfaces import Chunk, http_post

INDEX_DIR = REPO_ROOT / "data" / "index"
TABLE = "chunks"

Embed = Callable[[Sequence[str]], list[list[float]]]


def ollama_embedder(cfg: EmbeddingsConfig) -> Embed:
    url = f"{str(cfg.base_url).rstrip('/')}/api/embed"

    def embed(texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), cfg.batch):
            r = http_post(url, {"model": cfg.model, "input": list(texts[i : i + cfg.batch])}, 120)
            out += r["embeddings"]
        return out

    return embed


def content_hash(c: Chunk) -> str:
    return hashlib.sha256(f"{c.doc_type}\0{c.id}\0{c.text}".encode()).hexdigest()[:16]


class VectorIndex:
    def __init__(self, path: Path = INDEX_DIR) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(path))

    def _existing(self) -> dict[str, dict[str, Any]]:
        if TABLE not in self.db.list_tables().tables:
            return {}
        rows = self.db.open_table(TABLE).to_arrow().to_pylist()
        return {r["id"]: r for r in rows}

    def build(self, chunks: Sequence[Chunk], embed: Embed, registry_version: str) -> int:
        """Write the index; returns how many chunks were (re-)embedded."""
        old = self._existing()
        todo = [c for c in chunks if old.get(c.id, {}).get("hash") != content_hash(c)]
        vectors = dict(
            zip([c.id for c in todo], embed([c.text for c in todo]) if todo else [], strict=True)
        )
        now = datetime.now(UTC).isoformat()
        rows: list[dict[str, Any]] = []
        for c in chunks:
            prev = old.get(c.id)
            fresh = c.id in vectors
            rows.append(
                {
                    "id": c.id,
                    "text": c.text,
                    "doc_type": c.doc_type,
                    "metric": c.id if c.doc_type == "glossary" else None,
                    "registry_version": registry_version,
                    "updated_at": now if fresh or prev is None else prev["updated_at"],
                    "hash": content_hash(c),
                    "vector": vectors[c.id] if fresh else prev["vector"],  # type: ignore[index]
                }
            )
        dim = len(rows[0]["vector"]) if rows else 0
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("text", pa.string()),
                ("doc_type", pa.string()),
                ("metric", pa.string()),
                ("registry_version", pa.string()),
                ("updated_at", pa.string()),
                ("hash", pa.string()),
                ("vector", pa.list_(pa.float32(), dim)),
            ]
        )
        self.db.create_table(
            TABLE, data=pa.Table.from_pylist(rows, schema=schema), mode="overwrite"
        )
        return len(todo)

    def search(
        self, vector: Sequence[float], k: int, doc_types: Sequence[str] | None = None
    ) -> list[Chunk]:
        q = self.db.open_table(TABLE).search(list(vector)).limit(k)
        if doc_types:
            q = q.where(
                "doc_type IN (" + ", ".join(f"'{d}'" for d in doc_types) + ")", prefilter=True
            )
        return [
            Chunk(r["id"], r["text"], r["doc_type"], float(-r["_distance"])) for r in q.to_list()
        ]

    def chunks(self, doc_types: Sequence[str] | None = None) -> list[Chunk]:
        rows = self.db.open_table(TABLE).to_arrow().to_pylist()
        return [
            Chunk(r["id"], r["text"], r["doc_type"])
            for r in rows
            if not doc_types or r["doc_type"] in doc_types
        ]

    def registry_version(self) -> str | None:
        rows = self._existing()
        return next(iter(rows.values()))["registry_version"] if rows else None
