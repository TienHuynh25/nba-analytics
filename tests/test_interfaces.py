from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest

from app.config import load_models
from app.interfaces import LlamaCppClient, Message, OllamaClient, make_llm
from app.snapshot import FileSnapshotStore, LiveSnapshotStore
from tests.test_snapshots import cfg_for, fake_snapshot


def recorder(reply: dict[str, Any], calls: list[tuple[str, Mapping[str, Any]]]) -> Any:
    def post(url: str, body: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        calls.append((url, body))
        return reply

    return post


def test_backend_switches_by_config_alone() -> None:
    base = load_models().llm
    calls: list[tuple[str, Mapping[str, Any]]] = []
    o = make_llm(base, recorder({"message": {"content": "{}"}}, calls))
    assert isinstance(o, OllamaClient)
    assert o.complete([Message("user", "hi")], schema={"type": "object"}) == "{}"
    assert calls[-1][0].endswith("/api/chat") and calls[-1][1]["format"] == {"type": "object"}

    cpp_cfg = base.model_copy(update={"backend": "llamacpp"})
    c = make_llm(cpp_cfg, recorder({"choices": [{"message": {"content": "ok"}}]}, calls))
    assert isinstance(c, LlamaCppClient)
    assert c.complete([Message("user", "hi")], schema={"type": "object"}) == "ok"
    assert calls[-1][0].endswith("/v1/chat/completions")
    assert calls[-1][1]["response_format"]["type"] == "json_schema"
    assert calls[-1][1]["temperature"] == base.temperature


def test_live_store_is_read_only_and_reopens_on_swap(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    from ingest import snapshots

    a = fake_snapshot(cfg, "nba_20260929", age_days=1)
    b = fake_snapshot(cfg, "nba_20260930")
    snapshots.publish(cfg, a)
    swaps: list[str] = []
    store = LiveSnapshotStore(cfg, on_swap=swaps.append)
    assert store.snapshot_id == "nba_20260929"
    with pytest.raises(duckdb.Error):
        store.connection().execute("create table x (i int)")  # never a write lock
    snapshots.publish(cfg, b)
    assert store.snapshot_id == "nba_20260930"
    assert swaps == ["nba_20260930"]


def test_file_store_on_fixture(fixture_db_path: Path) -> None:
    s = FileSnapshotStore(fixture_db_path)
    con = s.connection()
    latest = con.execute("select max(game_date) from semantic.games").fetchone()[0]  # type: ignore[index]
    assert s.manifest["as_of_date"] == str(latest + timedelta(days=1))
    assert s.snapshot_id == "nba_fixture"
