"""SQL fallback: engine lockdown, watchdog, repair, cards (tasks 3.13, 3.15, 3.16)."""

import json
import shutil
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.interfaces import Message
from app.rag.bm25 import BM25Retriever
from app.rag.cards import schema_cards, tool_cards
from app.sql_fallback import QueryTimeout, SqlFallback, locked_connection, run_with_timeout


@pytest.fixture()
def shots_snapshot(tmp_path: Path, fixture_db_path: Path) -> tuple[Path, Path]:
    """A copy of the fixture whose shots are a view over Parquet, as in real snapshots."""
    db = tmp_path / "nba_fixture.duckdb"  # views name their catalog: keep the file name
    shutil.copy2(fixture_db_path, db)
    shots = tmp_path / "shots"
    shots.mkdir()
    con = duckdb.connect(str(db))
    con.execute(f"copy marts.shots to '{shots}/s.parquet' (format parquet)")
    con.execute("drop table marts.shots")
    con.execute(f"create view marts.shots as select * from read_parquet('{shots}/*.parquet')")
    con.close()
    secret = tmp_path / "raw.json"
    secret.write_text('{"a": 1}')
    return db, shots


def test_engine_blocks_files_but_reads_its_shots(shots_snapshot: tuple[Path, Path]) -> None:
    db, shots = shots_snapshot
    con = locked_connection(db, shots)
    assert con.execute("select count(*) from semantic.shots").fetchone() is not None
    # Parser bypassed: the engine itself refuses file reads and config changes.
    for sql in [
        f"select * from '{db.parent / 'raw.json'}'",
        "select * from read_csv('/etc/hosts')",
        "SET enable_external_access = true",
        # A different database file (re-attaching the open snapshot itself is allowed by
        # DuckDB but exposes nothing new; the parser rejects ATTACH anyway).
        f"ATTACH '{db.parent / 'other.duckdb'}' AS other",
    ]:
        with pytest.raises(duckdb.Error):
            con.execute(sql).fetchall()
    with pytest.raises(duckdb.Error):
        con.execute("create table x (i int)")  # read-only


def test_watchdog_stops_slow_query_at_timeout(fixture_db_path: Path) -> None:
    con = locked_connection(fixture_db_path, None)
    t = time.monotonic()
    with pytest.raises(QueryTimeout):
        run_with_timeout(con, "select count(*) from range(100000000000) a, range(10) b", 1.0)
    assert time.monotonic() - t < 4


class ScriptedLLM:
    model = "scripted"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.seen: list[Sequence[Message]] = []

    def complete(self, messages: Sequence[Message], schema: Any = None) -> str:
        self.seen.append(messages)
        return json.dumps({"sql": self.replies.pop(0)})


def make(fixture_db_path: Path, replies: list[str]) -> tuple[SqlFallback, ScriptedLLM]:
    con = duckdb.connect(str(fixture_db_path), read_only=True)
    cards = schema_cards(con)
    con.close()
    llm = ScriptedLLM(replies)
    return SqlFallback(llm, BM25Retriever(cards), fixture_db_path, None), llm


def test_good_sql_runs_with_limit(fixture_db_path: Path) -> None:
    fb, _ = make(
        fixture_db_path,
        [
            "select player_name, points_per_game from "
            "semantic.player_season_stats where season = '2024-25' "
            "order by points_per_game desc"
        ],
    )
    r = fb.answer("who scored the most per game")
    assert r.ok and r.attempts == 1 and len(r.rows) == 100 and r.sql and "LIMIT 100" in r.sql


def test_one_repair_attempt_with_the_error(fixture_db_path: Path) -> None:
    fb, llm = make(
        fixture_db_path,
        ["select * from marts.player_season", "select count(*) from semantic.games"],
    )
    r = fb.answer("how many games")
    assert r.ok and r.attempts == 2
    assert "not a semantic-layer view" in llm.seen[1][-1].content


def test_gives_up_after_one_repair(fixture_db_path: Path) -> None:
    fb, _ = make(fixture_db_path, ["drop table x", "select nope from semantic.games"])
    r = fb.answer("anything")
    assert not r.ok and r.attempts == 2 and r.error


def test_every_view_and_column_has_a_schema_card(fixture_db_path: Path) -> None:
    con = duckdb.connect(str(fixture_db_path), read_only=True)
    cards = {c.id for c in schema_cards(con)}
    cols = con.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_schema = 'semantic'"
    ).fetchall()
    con.close()
    assert all(f"column:semantic.{t}.{c}" in cards for t, c in cols)
    retr = BM25Retriever(
        [c for c in schema_cards(duckdb.connect(str(fixture_db_path), read_only=True))]
    )
    top = [c.id for c in retr.search("true shooting percentage", 5)]
    assert any(i.endswith(".true_shooting_pct") for i in top)


def test_tool_cards_regenerate_from_schemas() -> None:
    cards = {c.id: c.text for c in tool_cards()}
    assert len(cards) == 10
    assert "metric (required)" in cards["tool:get_leaders"]
    assert "Example questions" in cards["tool:get_games"]
