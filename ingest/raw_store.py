"""Immutable raw JSON cache (task 1.2).

Layout: ``data/raw/<key>/<season>/<fetch_date>/<request_hash>.<fetched_at>.json``.

- ``season`` is ``_all`` for endpoints not keyed by season (per-player, once-only).
- ``fetch_date`` is the US Eastern date of the fetch.
- Files are never overwritten. A re-fetch writes a new file next to the old one, and staging
  keeps the latest fetch per key.
- A cache hit makes no API call, so rebuilds never re-hit stats.nba.com.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ingest.client import PINNED_NBA_API, NbaClient
from ingest.endpoints import EndpointSpec

ET = ZoneInfo("America/New_York")
ALL = "_all"

Validator = Callable[[str, dict[str, Any]], None]


def request_hash(endpoint: str, params: Mapping[str, Any]) -> str:
    canon = json.dumps({"endpoint": endpoint, "params": dict(params)}, sort_keys=True, default=str)
    return hashlib.sha1(canon.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class RawRecord:
    path: Path
    key: str
    season: str
    params: dict[str, Any]
    fetched_at: str
    response: dict[str, Any]


class RawStore:
    def __init__(
        self,
        root: Path,
        client: NbaClient | None,
        validator: Validator | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.root = root
        self.client = client
        self.validator = validator
        self._now = now

    def _dir(self, key: str, season: str) -> Path:
        return self.root / key / season

    def latest(
        self, spec: EndpointSpec, partition: str | None, params: Mapping[str, Any]
    ) -> Path | None:
        h = request_hash(spec.endpoint, params)
        base = self._dir(spec.key, partition or ALL)
        if not base.exists():
            return None
        hits = sorted(base.glob(f"*/{h}.*.json"))
        return hits[-1] if hits else None

    def get(
        self,
        spec: EndpointSpec,
        partition: str | None = None,
        refresh: bool = False,
        **kwargs: Any,
    ) -> RawRecord:
        """Return the cached response, fetching it only on a miss or when ``refresh`` is set.

        ``partition`` is the season folder (``_all`` when None). ``kwargs`` are the endpoint's
        own parameters (which may include ``season``).
        """
        params = spec.params(**kwargs)
        if not refresh:
            hit = self.latest(spec, partition, params)
            if hit is not None:
                return load(hit)
        if self.client is None:
            raise LookupError(f"cache miss for {spec.key} {partition} {kwargs} and no client")
        body = self.client.fetch(spec.endpoint, params)
        if self.validator is not None:
            self.validator(spec.key, body)
        return self._write(spec, partition or ALL, params, body)

    def _write(
        self, spec: EndpointSpec, season: str, params: dict[str, Any], body: dict[str, Any]
    ) -> RawRecord:
        now = self._now()
        fetched_at = now.isoformat()
        fetch_date = now.astimezone(ET).date().isoformat()
        stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
        d = self._dir(spec.key, season) / fetch_date
        d.mkdir(parents=True, exist_ok=True)
        final = d / f"{request_hash(spec.endpoint, params)}.{stamp}.json"
        doc = {
            "key": spec.key,
            "endpoint": spec.endpoint,
            "season": season,
            "params": params,
            "fetched_at": fetched_at,
            "nba_api_version": PINNED_NBA_API,
            "response": body,
        }
        tmp = d / f".{final.name}.tmp"
        tmp.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        try:
            os.link(tmp, final)  # fails if the file exists: never overwrite
        finally:
            tmp.unlink()
        return RawRecord(final, spec.key, season, params, fetched_at, body)


def load(path: Path) -> RawRecord:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return RawRecord(
        path, doc["key"], doc["season"], doc["params"], doc["fetched_at"], doc["response"]
    )
