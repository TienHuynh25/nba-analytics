"""Flatten the raw JSON cache into landing tables for dbt (task 1.9).

DuckDB cannot unnest the raw ``headers`` + ``rowSet`` layout directly at full scale on the
target Mac. Reading 26 player game-log files that way used more than 11 GB. So this step streams
every raw file once and writes one newline-delimited JSON file per (endpoint key, result set), with
every value as text. It then loads those into ``landing.duckdb``, which the dbt profile attaches
read-only as ``landing``. Staging models do all typing and deduplication. The landing file is
build-only and is never published.

Each landing row carries ``_key``, ``_partition``, ``_file``, ``_fetched_at`` and ``_params`` (the
request parameters as JSON), so staging can keep the latest fetch per natural key.

Every raw file is checked against its JSON contract before it lands, and column names must be
plain ``[A-Za-z0-9_]+`` identifiers, because they are written into SQL on a full-privilege
connection (SEC-006).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TextIO

import duckdb

from ingest.contracts import ContractError, validate
from ingest.endpoints import SPECS

log = logging.getLogger(__name__)

META = ("_key", "_partition", "_file", "_fetched_at", "_params")
HEADER = re.compile(r"[A-Za-z0-9_]+")

# (endpoint key, response body) -> None, or raise ContractError
Validator = Callable[[str, dict[str, Any]], None]


def _sql_str(s: str) -> str:
    """A single-quoted SQL string literal."""
    return "'" + s.replace("'", "''") + "'"


def _check_header(h: object, path: Path) -> str:
    if not isinstance(h, str) or not HEADER.fullmatch(h):
        raise ContractError(f"{path}: column name {h!r} is not a plain identifier [A-Za-z0-9_]+")
    return h


def table_name(key: str, result_set: str) -> str:
    return f"{key}__{result_set}".lower()


def _cell(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v)) if abs(v) < 1e15 else repr(v)
    return str(v)


def raw_files(raw_root: Path, key: str) -> Iterator[Path]:
    base = raw_root / key
    if base.exists():
        yield from sorted(base.glob("*/*/*.json"))


# (endpoint key, raw file path, decoded doc) -> keep?
FileFilter = Callable[[str, Path, dict[str, Any]], bool]


def land(
    raw_root: Path,
    landing_db: Path,
    work_dir: Path,
    keys: list[str] | None = None,
    keep: FileFilter | None = None,
    validator: Validator | None = validate,
) -> dict[str, int]:
    """Rebuild ``landing_db`` from the raw cache. Returns row counts per landing table.

    ``keep`` selects raw files (used to build the one-season test fixture). ``validator``
    checks each kept file's response against its contract (``None`` skips it, for synthetic
    test caches only); a failure raises :class:`ContractError` and nothing is landed.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    columns: dict[str, list[str]] = {}
    handles: dict[str, TextIO] = {}
    try:
        for key in keys or list(SPECS):
            wanted = set(SPECS[key].result_sets)
            for path in raw_files(raw_root, key):
                doc = json.loads(path.read_text(encoding="utf-8"))
                if keep is not None and not keep(key, path, doc):
                    continue
                if validator is not None:
                    validator(key, doc["response"])
                meta = {
                    "_key": key,
                    "_partition": doc["season"],
                    "_file": str(path.relative_to(raw_root)),
                    "_fetched_at": doc["fetched_at"],
                    "_params": json.dumps(doc["params"], sort_keys=True),
                }
                sets = doc["response"].get("resultSets", [])
                for rs in sets if isinstance(sets, list) else [sets]:
                    if rs["name"] not in wanted:
                        continue
                    t = table_name(key, rs["name"])
                    cols = columns.setdefault(t, [])
                    for h in rs["headers"]:
                        _check_header(h, path)
                        if h not in cols:
                            cols.append(h)
                    f = handles.get(t)
                    if f is None:
                        f = handles[t] = (work_dir / f"{t}.ndjson").open("w", encoding="utf-8")
                        counts[t] = 0
                    for row in rs["rowSet"]:
                        rec = dict(meta)
                        for h, v in zip(rs["headers"], row, strict=True):
                            rec[h] = _cell(v)
                        f.write(json.dumps(rec, separators=(",", ":")))
                        f.write("\n")
                        counts[t] += 1
    finally:
        for f in handles.values():
            f.close()

    tmp = landing_db.with_suffix(".building.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.execute("SET preserve_insertion_order = false")
        for t, cols in columns.items():
            spec = {c: "VARCHAR" for c in (*META, *cols)}
            col_sql = "{" + ", ".join(f"{_sql_str(c)}: 'VARCHAR'" for c in spec) + "}"
            src = _sql_str((work_dir / f"{t}.ndjson").as_posix())
            if counts[t] == 0:
                ddl = ", ".join(f'"{c}" VARCHAR' for c in spec)
                con.execute(f'CREATE TABLE "{t}" ({ddl})')
                continue
            con.execute(
                f"""CREATE TABLE "{t}" AS SELECT * FROM read_json({src},
                    format='newline_delimited', columns={col_sql})"""
            )
        # Every key gets its tables, even with no raw files yet, so dbt sources always resolve.
        for key in keys or list(SPECS):
            for rs_name in SPECS[key].result_sets:
                t = table_name(key, rs_name)
                if t not in columns:
                    ddl = ", ".join(f'"{c}" VARCHAR' for c in META)
                    con.execute(f'CREATE TABLE "{t}" ({ddl})')
                    counts[t] = 0
    finally:
        con.close()
    tmp.replace(landing_db)
    for p in work_dir.glob("*.ndjson"):
        p.unlink()
    log.info("landing built", extra={"event": "land_done", "rows": sum(counts.values())})
    return counts
