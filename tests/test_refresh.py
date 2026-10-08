"""One-command refresh orchestration (task 1.26): ordering, abort rules, run log.

Every collaborator is faked, so nothing touches the network or builds a database. What is
tested is the contract in the module docstring: an anomaly or a build failure never reaches
``publish`` (yesterday's snapshot stays live), an as-of build is pinned and never published,
and every run appends exactly one line to the ingest log.
"""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import SourcesConfig, load_sources
from ingest import refresh, snapshots
from ingest.incremental import AnomalyError, IncrementalResult


class Calls:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.build_kwargs: dict[str, Any] = {}
        self.fail_build: Exception | None = None
        self.anomaly: Exception | None = None


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Calls, Path]]:
    base = load_sources()
    cfg: SourcesConfig = base.model_copy(
        update={"paths": base.paths.model_copy(update={"logs": tmp_path / "logs"})}
    )
    calls = Calls()
    snap = SimpleNamespace(
        snapshot_id="nba_20261007",
        manifest={"as_of_date": "2026-10-08", "latest_game_date": "2026-10-07"},
    )

    class FakeStore:
        def __init__(self, *a: Any, **k: Any) -> None: ...

        def get(self, *a: Any, **k: Any) -> Any:
            calls.events.append("schedule")
            return SimpleNamespace(response={})

    def fetch_window(store: Any, today: date, days: int) -> IncrementalResult:
        calls.events.append("fetch")
        return IncrementalResult("2026-27", (date(2026, 10, 1), date(2026, 10, 7)), {})

    def check_game_counts(*a: Any, **k: Any) -> None:
        calls.events.append("check")
        if calls.anomaly:
            raise calls.anomaly

    def build(cfg: Any, **kw: Any) -> Any:
        calls.events.append("build")
        calls.build_kwargs = kw
        if calls.fail_build:
            raise calls.fail_build
        return snap

    def publish(cfg: Any, s: Any) -> None:
        calls.events.append("publish")

    monkeypatch.setattr(refresh, "sources", lambda: cfg)
    monkeypatch.setattr(refresh, "NbaClient", lambda *a, **k: object())
    monkeypatch.setattr(refresh, "RawStore", FakeStore)
    monkeypatch.setattr(refresh, "fetch_window", fetch_window)
    monkeypatch.setattr(refresh, "scheduled_games_by_day", lambda s: {})
    monkeypatch.setattr(refresh, "check_game_counts", check_game_counts)
    monkeypatch.setattr(snapshots, "build", build)
    monkeypatch.setattr(snapshots, "publish", publish)
    yield calls, tmp_path / "logs" / "ingest_log.jsonl"


def records(log: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in log.read_text().splitlines()]


def test_nightly_runs_in_order_and_publishes(env: tuple[Calls, Path]) -> None:
    calls, log = env
    assert refresh.main([]) == 0
    assert calls.events == ["fetch", "schedule", "check", "build", "publish"]
    [rec] = records(log)
    assert rec["status"] == "ok" and rec["mode"] == "nightly"
    assert rec["snapshot_id"] == "nba_20261007" and rec["duration_s"] >= 0


def test_anomaly_stops_before_build_and_publish(env: tuple[Calls, Path]) -> None:
    calls, log = env
    calls.anomaly = AnomalyError("2026-10-05: fetched 3 games, schedule says 9")
    assert refresh.main([]) == 1
    assert "build" not in calls.events and "publish" not in calls.events
    [rec] = records(log)
    assert rec["status"] == "failed" and "AnomalyError" in rec["error"]


def test_failed_build_is_never_published(env: tuple[Calls, Path]) -> None:
    calls, log = env
    calls.fail_build = RuntimeError("dbt test failed: not_null_games_game_id")
    assert refresh.main([]) == 1
    assert calls.events[-1] == "build"
    assert "dbt test failed" in records(log)[0]["error"]


def test_as_of_build_is_pinned_cached_and_not_published(env: tuple[Calls, Path]) -> None:
    calls, log = env
    assert refresh.main(["--as-of", "2026-04-12", "--snapshot-id", "eval_2025_26_rs"]) == 0
    assert calls.events == ["build"]  # no fetch, no schedule check, no publish
    kw = calls.build_kwargs
    assert kw == {"snapshot_id": "eval_2025_26_rs", "as_of": date(2026, 4, 12), "pinned": True}
    assert records(log)[0]["mode"] == "as_of"


def test_as_of_default_snapshot_id(env: tuple[Calls, Path]) -> None:
    calls, _ = env
    refresh.main(["--as-of", "2026-04-12"])
    assert calls.build_kwargs["snapshot_id"] == "asof_20260412"


def test_bad_date_is_a_logged_failure_not_a_crash(env: tuple[Calls, Path]) -> None:
    calls, log = env
    assert refresh.main(["--as-of", "12/04/2026"]) == 1
    assert calls.events == []
    assert records(log)[0]["status"] == "failed"


def test_each_run_appends_one_line(env: tuple[Calls, Path]) -> None:
    calls, log = env
    refresh.main([])
    calls.anomaly = AnomalyError("x")
    refresh.main([])
    assert [r["status"] for r in records(log)] == ["ok", "failed"]
    assert len({r["run_id"] for r in records(log)}) == 2
