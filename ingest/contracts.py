"""JSON contract tests on raw responses (task 1.4).

Each endpoint key has a schema in ``ingest/schemas/<key>.json``. The schemas are generated from
real samples by :func:`generate_schema` and then tightened:

- every result set we rely on must be present, with its ``headers`` equal to the stored list,
  in order. Where samples legitimately differ (``CommonPlayerInfo`` omits
  ``SUPPLEMENTAL_STATUS`` for retired players; ``Standings`` columns change with the division
  layout and the 2019-20 restart), each observed header list is stored as its own *variant*
  and the headers must equal one variant exactly, in order (``anyOf``);
- every row has exactly ``len(headers)`` cells of the matched variant;
- each cell's JSON type is limited to the types seen in that variant's samples, plus ``null``;
- key columns (IDs, dates, season) may never be ``null``.

A renamed, swapped, dropped or added column, a short or long row, a changed cell type, or a key
that turns ``null`` fails validation, so the run stops before bad data reaches staging. An empty
``rowSet`` and a ``null`` in a non-key cell pass by design (content checks live elsewhere;
untracked stats are ``NULL``).
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


def _cell_types(col: str, seen: set[str]) -> list[str]:
    observed = sorted(seen - {"null"})
    if col in NON_NULL_COLUMNS:
        return observed or ["string", "number"]
    return [*observed, "null"] if observed else ["string", "number", "boolean", "null"]


def _variant(headers: list[str], types: dict[str, set[str]]) -> dict[str, Any]:
    """Exact headers, exact row width and per-cell types for one observed header list."""
    cells = [{"type": _cell_types(col, types.get(col, set())), "$comment": col} for col in headers]
    n = len(headers)
    return {
        "headers": {"const": headers},
        "rowSet": {
            "type": "array",
            "items": {"type": "array", "minItems": n, "maxItems": n, "prefixItems": cells},
        },
    }


def generate_schema(
    key: str, samples: Iterable[dict[str, Any]], names: Iterable[str]
) -> dict[str, Any]:
    """Build a tightened schema from one or more sample bodies of the same endpoint.

    Each distinct header list seen for a result set becomes one variant, typed only from the
    samples that carry it. One variant is stored inline; several are stored as ``anyOf``.
    """
    wanted = list(names)
    # result set -> header tuple (first-seen order) -> column -> JSON types seen
    variants: dict[str, dict[tuple[str, ...], dict[str, set[str]]]] = {}
    for body in samples:
        for rs in _sets(body):
            name = rs["name"]
            if name not in wanted:
                continue
            h = list(rs["headers"])
            cols = variants.setdefault(name, {}).setdefault(tuple(h), {})
            for row in rs["rowSet"]:
                for col, cell in zip(h, row, strict=True):
                    cols.setdefault(col, set()).add(_json_type(cell))
    missing = [n for n in wanted if n not in variants]
    if missing:
        raise ContractError(f"{key}: samples lack result sets {missing}")

    contains: list[dict[str, Any]] = []
    for name in wanted:
        found = [_variant(list(h), types) for h, types in variants[name].items()]
        item: dict[str, Any] = {
            "type": "object",
            "required": ["name", "headers", "rowSet"],
            "properties": {"name": {"const": name}},
        }
        if len(found) == 1:
            item["properties"].update(found[0])
        else:
            item["anyOf"] = [{"properties": v} for v in found]
        contains.append({"contains": item})
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
