"""``make serve``: a local command-line assistant (task 4.10).

Ask questions, follow up, and see the source line under every answer. Commands: /new starts a
new conversation, /quit exits. Reads the published ``current`` snapshot (read-only), or --db.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.assistant import Assistant, Session
from app.cache import AnswerCache
from app.config import models
from app.interfaces import SnapshotStore, make_llm
from app.rag.cards import schema_cards
from app.rag.retrieve import default_retrievers
from app.snapshot import FileSnapshotStore, LiveSnapshotStore
from app.sql_fallback import SqlFallback


def build(db: Path | None, shots: Path | None) -> Assistant:
    cache = AnswerCache()
    store: SnapshotStore
    if db is not None:
        store = FileSnapshotStore(db, shots_dir=shots)
        db_path, shots_dir = db, shots or db.parent / "shots"
    else:
        live = LiveSnapshotStore(on_swap=cache.clear)
        store = live
        snap_dir = live.cfg.resolve(live.cfg.snapshots.current_link).resolve()
        db_path, shots_dir = snap_dir / f"{live.snapshot_id}.duckdb", snap_dir / "shots"
    llm = make_llm(models().llm)
    knowledge, schema = default_retrievers(schema_cards(store.connection()))
    fallback = SqlFallback(llm, schema, db_path, shots_dir if shots_dir.exists() else None)
    return Assistant(store, llm, retriever=knowledge, fallback=fallback, cache=cache)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, help="a snapshot database (default: current)")
    ap.add_argument("--shots", type=Path, help="that snapshot's shots folder")
    args = ap.parse_args(argv)
    assistant = build(args.db, args.shots)
    session = Session()
    print("NBA stats assistant. /new for a new conversation, /quit to exit.")
    for line in sys.stdin if not sys.stdin.isatty() else iter(lambda: input("\n> "), None):
        q = line.strip()
        if not q:
            continue
        if q == "/quit":
            break
        if q == "/new":
            session = Session()
            print("New conversation.")
            continue
        reply = assistant.ask(q, session)
        print(f"\n{reply.text}\n[{reply.path}, {reply.latency_ms / 1000:.1f} s]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
