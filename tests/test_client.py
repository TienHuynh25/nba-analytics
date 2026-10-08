from collections.abc import Mapping
from itertools import pairwise
from typing import Any

import pytest

from app.config import load_sources
from ingest.client import FetchError, NbaClient


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        assert s >= 0
        self.t += s


def make(transport: Any, clock: FakeClock) -> NbaClient:
    return NbaClient(
        load_sources().nba_api, transport=transport, clock=clock.now, sleep=clock.sleep
    )


def test_throttle_never_exceeds_rate_over_100_calls() -> None:
    clock = FakeClock()
    starts: list[float] = []

    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        starts.append(clock.t)
        clock.t += 0.05  # a fast response must not let the next call start early
        return {"resultSets": []}

    client = make(transport, clock)
    for _ in range(100):
        client.fetch("leaguegamelog", {})
    gaps = [b - a for a, b in pairwise(starts)]
    assert len(starts) == 100
    assert min(gaps) >= 0.6 - 1e-9


def test_retries_with_backoff_then_succeeds() -> None:
    clock = FakeClock()
    calls = {"n": 0}

    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("reset")
        return {"ok": True}

    assert make(transport, clock).fetch("x", {}) == {"ok": True}
    assert calls["n"] == 3


def test_gives_up_after_max_retries() -> None:
    clock = FakeClock()

    def transport(ep: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        raise TimeoutError

    client = make(transport, clock)
    with pytest.raises(FetchError):
        client.fetch("x", {})
    assert client.calls == client.cfg.max_retries + 1
