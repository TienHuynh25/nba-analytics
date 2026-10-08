"""Build or refresh the vector index (task 4.3). Run by ``make refresh`` after publishing.

Usage: ``uv run python -m app.rag.build_index [--db path]`` (default: the current snapshot)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from app.config import models, sources
from app.interfaces import Chunk
from app.rag.cards import schema_cards, tool_cards
from app.rag.glossary import glossary_chunks
from app.rag.index import VectorIndex, ollama_embedder
from ingest import snapshots
from metrics.schema import load


def corpus(con: duckdb.DuckDBPyConnection) -> list[Chunk]:
    reg = load()
    return [*glossary_chunks(reg), *tool_cards(reg), *schema_cards(con, reg)]


def build(db: Path, index: VectorIndex | None = None) -> int:
    con = duckdb.connect(str(db), read_only=True)
    try:
        chunks = corpus(con)
    finally:
        con.close()
    return (index or VectorIndex()).build(
        chunks, ollama_embedder(models().embeddings), load().version
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path)
    a = ap.parse_args()
    db = a.db or snapshots.open_current(sources()).db
    n = build(db)
    print(f"index built from {db.name}: {n} chunk(s) embedded")


if __name__ == "__main__":
    main()
