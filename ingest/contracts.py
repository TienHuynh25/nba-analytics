"""JSON contract tests on raw responses (task 1.4).

Each endpoint key has a schema in ``ingest/schemas/<key>.json``. The schemas are generated from
real samples by :func:`generate_schema` and then tightened:

- every result set we rely on must be present, with its ``headers`` equal to the stored list,
  in order;
- every row has exactly ``len(headers)`` cells;
- each cell's JSON type is limited to the types seen in the samples, plus ``null``;
- key columns (IDs, dates, season) may never be ``null``.

A renamed field, a dropped or added column, or a key that turns ``null`` fails validation, so the
run stops before bad data reaches staging.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

NON_NULL_COLUMNS = frozenset(
    {
        "GAME_ID",
        "GAME_DATE",
        "PLAYER_ID",
        "PERSON_ID",
        "TEAM_ID",
        "SEASON_ID",
        "MATCHUP",
        "TeamID",
        "SeasonID",
        "YEAR",
    }
)


class ContractError(ValueError):
    pass


def _json_type(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int | float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def _sets(body: dict[str, Any]) -> list[dict[str, Any]]:
    sets = body.get("resultSets", body.get("resultSet"))
    if isinstance(sets, dict):
        sets = [sets]
    if not isinstance(sets, list):
        raise ContractError("body has no resultSets")
    return sets


def generate_schema(
    key: str, samples: Iterable[dict[str, Any]], names: Iterable[str]
) -> dict[str, Any]:
    """Build a tightened schema from one or more sample bodies of the same endpoint."""
    wanted = list(names)
    headers: dict[str, list[str]] = {}
    types: dict[str, list[set[str]]] = {}
    for body in samples:
        for rs in _sets(body):
            name = rs["name"]
            if name not in wanted:
                continue
            h = list(rs["headers"])
            if name in headers and headers[name] != h:
                raise ContractError(f"{key}.{name}: headers differ between samples")
            headers[name] = h
            cols = types.setdefault(name, [set() for _ in h])
            for row in rs["rowSet"]:
                for i, cell in enumerate(row):
                    cols[i].add(_json_type(cell))
    missing = [n for n in wanted if n not in headers]
    if missing:
        raise ContractError(f"{key}: samples lack result sets {missing}")

    contains = []
    for name in wanted:
        cells = []
        for col, seen in zip(headers[name], types[name], strict=True):
            observed = sorted(seen - {"null"})
            if col in NON_NULL_COLUMNS:
                allowed = observed or ["string", "number"]
            else:
                allowed = (
                    [*observed, "null"] if observed else ["string", "number", "boolean", "null"]
                )
            cells.append({"type": allowed, "$comment": col})
        n = len(headers[name])
        contains.append(
            {
                "contains": {
                    "type": "object",
                    "required": ["name", "headers", "rowSet"],
                    "properties": {
                        "name": {"const": name},
                        "headers": {"const": headers[name]},
                        "rowSet": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "minItems": n,
                                "maxItems": n,
                                "prefixItems": cells,
                            },
                        },
                    },
                }
            }
        )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": key,
        "type": "object",
        "required": ["resultSets"],
        "properties": {"resultSets": {"type": "array", "allOf": contains}},
    }


@cache
def _validator(key: str) -> Draft202012Validator:
    path = SCHEMA_DIR / f"{key}.json"
    if not path.exists():
        raise ContractError(f"no JSON schema for endpoint {key!r} at {path}")
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def validate(key: str, body: dict[str, Any]) -> None:
    """Raise :class:`ContractError` if ``body`` breaks the stored contract for ``key``."""
    if "resultSet" in body and "resultSets" not in body:
        body = {**body, "resultSets": _sets(body)}
    errors = sorted(_validator(key).iter_errors(body), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{list(e.path)}: {e.message[:200]}" for e in errors[:3])
        raise ContractError(f"{key}: response breaks its contract: {detail}")
