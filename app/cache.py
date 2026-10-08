"""Answer cache keyed by (tool, normalized arguments, snapshot ID) (task 4.9).

The key is known only after tool choice, so a hit saves the query and the answer generation,
not routing or tool choice. A snapshot swap clears the whole cache, so a cached answer is never
stale. The eval harness runs with the cache off.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from typing import Any

from app.tools.schemas import canonical


def key(tool: str, args: dict[str, Any], snapshot_id: str) -> str:
    return json.dumps([tool, canonical(tool, args), snapshot_id], sort_keys=True, default=str)


class AnswerCache:
    def __init__(self, max_items: int = 2000) -> None:
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._max = max_items
        self._lock = threading.Lock()
        self.hits = 0

    def get(self, k: str) -> Any | None:
        with self._lock:
            if k in self._data:
                self._data.move_to_end(k)
                self.hits += 1
                return self._data[k]
            return None

    def put(self, k: str, value: Any) -> None:
        with self._lock:
            self._data[k] = value
            self._data.move_to_end(k)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self, _snapshot_id: str | None = None) -> None:
        """Called on a snapshot swap (LiveSnapshotStore on_swap)."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
