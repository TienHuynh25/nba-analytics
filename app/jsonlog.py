"""Structured JSON logging with run and snapshot IDs (task 0.11).

Every line carries ``run_id``. The formatter emits only an allowlisted set of fields, so
personal data cannot reach the logs through ``extra=``.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_run_id: ContextVar[str] = ContextVar("run_id", default="")
_snapshot_id: ContextVar[str | None] = ContextVar("snapshot_id", default=None)

# Only these keys from ``extra=`` reach the output. Free-text user questions are not among them.
ALLOWED_EXTRA = frozenset(
    {
        "event",
        "endpoint",
        "season",
        "season_type",
        "status",
        "duration_ms",
        "rows",
        "attempt",
        "tool",
        "path",
        "prompt_version",
        "model",
        "index_version",
        "registry_version",
        "case_id",
        "error",
    }
)


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def set_run(run_id: str | None = None, snapshot_id: str | None = None) -> str:
    rid = run_id or new_run_id()
    _run_id.set(rid)
    _snapshot_id.set(snapshot_id)
    return rid


def set_snapshot(snapshot_id: str | None) -> None:
    _snapshot_id.set(snapshot_id)


def current_run_id() -> str:
    rid = _run_id.get()
    if not rid:
        rid = set_run()
    return rid


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "run_id": current_run_id(),
            "snapshot_id": _snapshot_id.get(),
        }
        for key in ALLOWED_EXTRA:
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(level: int = logging.INFO, stream: Any = None) -> None:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
