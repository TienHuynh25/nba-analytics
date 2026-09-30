"""Throttled, retrying wrapper around ``nba_api`` (task 1.1).

All traffic to stats.nba.com goes through :class:`NbaClient`. Consecutive request *starts* are
spaced by at least ``min_interval_s`` (0.6 s per the spec), including retries. Failures back off
exponentially. The ``nba_api`` version is pinned, and a mismatch stops the client, because
endpoint shapes change between versions.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from importlib.metadata import version
from typing import Any

from app.config import NbaApiConfig

log = logging.getLogger(__name__)

PINNED_NBA_API = "1.11.4"

# (endpoint name, params, timeout seconds) -> decoded JSON body
Transport = Callable[[str, Mapping[str, Any], float], dict[str, Any]]


class FetchError(RuntimeError):
    """Raised when a request still fails after all retries."""


class Throttle:
    """Keeps the start of consecutive calls at least ``min_interval`` seconds apart."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            gap = self._last + self.min_interval - now
            if gap > 0:
                self._sleep(gap)
                now = self._clock()
        self._last = now


def nba_transport(endpoint: str, params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    """Send one request with ``nba_api``'s HTTP layer and browser-like stats.nba.com headers."""
    from nba_api.stats.library.http import NBAStatsHTTP

    resp = NBAStatsHTTP().send_api_request(
        endpoint=endpoint, parameters=dict(params), timeout=timeout
    )
    # NBAResponse keeps the status code only in a private attribute.
    status = resp._status_code
    if status != 200:
        raise FetchError(f"{endpoint}: HTTP {status}")
    body = resp.get_dict()
    if not isinstance(body, dict):
        raise FetchError(f"{endpoint}: response is not a JSON object")
    return body


def check_pinned_version() -> None:
    installed = version("nba_api")
    if installed != PINNED_NBA_API:
        raise RuntimeError(f"nba_api {installed} installed, but {PINNED_NBA_API} is pinned")


class NbaClient:
    def __init__(
        self,
        cfg: NbaApiConfig,
        transport: Transport = nba_transport,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        check_version: bool = True,
    ) -> None:
        if check_version:
            check_pinned_version()
        self.cfg = cfg
        self._transport = transport
        self._sleep = sleep
        self.throttle = Throttle(cfg.min_interval_s, clock=clock, sleep=sleep)
        self.calls = 0

    def fetch(self, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        delay = self.cfg.backoff_initial_s
        last_exc: Exception | None = None
        for attempt in range(self.cfg.max_retries + 1):
            self.throttle.wait()
            self.calls += 1
            try:
                return self._transport(endpoint, params, self.cfg.timeout_s)
            except Exception as exc:  # network errors, HTTP errors, bad JSON
                last_exc = exc
                log.warning(
                    "fetch failed",
                    extra={
                        "event": "fetch_retry",
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "error": f"{type(exc).__name__}: {exc}"[:300],
                    },
                )
                if attempt < self.cfg.max_retries:
                    self._sleep(delay)
                    delay = min(delay * 2, self.cfg.backoff_max_s)
        raise FetchError(
            f"{endpoint} failed after {self.cfg.max_retries + 1} attempts"
        ) from last_exc
