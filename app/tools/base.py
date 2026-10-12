"""Typed tool framework (task 3.8): validation, registry defaults, results, source lines.

- Arguments are validated against the tool's JSON schema *before* any query runs; invalid
  arguments raise :class:`ToolArgError`.
- Defaults (regular season, so Play-In is excluded; qualification on) come from the schema,
  which the registry generates, never from prompts.
- Every result carries the values the answer may state, each with its registry rounding rule,
  for the numeric verifier (3.11), and a source line (3.12).
- A stat asked for a season before it was tracked returns "not tracked" with its first season
  (3.10), from ``stat_availability``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator

from app.interfaces import SnapshotStore
from app.tools.schemas import STAT_LINE, expand_metrics, load_schema
from app.verifier import ResultValue
from metrics.schema import Metric, Registry, Rounding, registry

__all__ = ["STAT_LINE"]

INT = Rounding(decimals=0)
FLOAT1 = Rounding(decimals=1)


class ToolArgError(ValueError):
    """Arguments failed schema validation; nothing was queried."""


class ToolError(RuntimeError):
    """The query could not be answered (e.g. no qualification rule for that era)."""


@dataclass(frozen=True)
class NotTracked:
    metric: str
    label: str
    season: str
    first_season: str

    def sentence(self) -> str:
        return (
            f"{self.label} was not tracked in {self.season}; "
            f"the NBA first tracked it in {self.first_season}."
        )


@dataclass
class ToolResult:
    tool: str
    args: dict[str, Any]
    columns: list[str]
    rows: list[dict[str, Any]]
    metrics: list[str]  # registry metric columns in the rows
    source: str
    not_tracked: list[NotTracked] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    entities: dict[str, list[int]] = field(default_factory=dict)

    def values(self, reg: Registry | None = None) -> list[ResultValue]:
        """Every number the answer may state, with the rounding rule it is shown with."""
        reg = reg or registry()
        out = []
        for row in self.rows:
            for col, v in row.items():
                if isinstance(v, bool) or not isinstance(v, int | float):
                    continue
                if col in self.metrics:
                    out.append(ResultValue(float(v), reg.metric(col).rounding))
                elif col.endswith("_id"):
                    continue  # ids are never shown
                else:
                    out.append(ResultValue(float(v), INT if float(v).is_integer() else FLOAT1))
        return out

    def args_text(self) -> list[str]:
        out = []
        for k, v in self.args.items():
            if k.endswith("_ids") or k in ("team_id",):
                continue
            if isinstance(v, list):
                out += [str(x) for x in v]
            elif not isinstance(v, bool):
                out.append(str(v))
        out += [f"top {self.args['limit']}"] if "limit" in self.args else []
        return out


class BaseTool:
    name: str = ""

    def __init__(self, reg: Registry | None = None) -> None:
        self.reg = reg or registry()
        self.schema = load_schema(self.name)
        self._validator = Draft202012Validator(self.schema)

    def validate(self, args: Mapping[str, Any]) -> dict[str, Any]:
        errors = sorted(self._validator.iter_errors(dict(args)), key=lambda e: list(e.path))
        if errors:
            raise ToolArgError("; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3]))
        out = {k: v["default"] for k, v in self.schema["properties"].items() if "default" in v}
        out.update(args)
        if "metrics" in out:
            out["metrics"] = expand_metrics(list(out["metrics"]))
        return out

    def run(self, args: Mapping[str, Any], store: SnapshotStore) -> ToolResult:
        a = self.validate(args)
        return self._run(a, store)

    def _run(self, args: dict[str, Any], store: SnapshotStore) -> ToolResult:
        raise NotImplementedError

    # -- shared helpers --------------------------------------------------------------------------
    def metric(self, name: str) -> Metric:
        return self.reg.metric(name)

    def not_tracked(
        self, store: SnapshotStore, metrics: Sequence[str], seasons: Sequence[str]
    ) -> list[NotTracked]:
        """Metrics whose required stats were not tracked in any of ``seasons``."""
        if not seasons:
            return []
        con = store.connection()
        avail = dict(
            con.execute("select stat, first_season from semantic.stat_availability").fetchall()
        )
        out = []
        for name in metrics:
            m = self.metric(name)
            for stat in m.requires:
                first = avail.get(stat)
                if first is None:
                    continue
                if all(s < first for s in seasons):
                    out.append(NotTracked(name, m.label, max(seasons), first))
                    break
        return out


def latest_game_date(store: SnapshotStore) -> str:
    row = store.connection().execute("select max(game_date) from semantic.games").fetchone()
    return str(row[0]) if row and row[0] is not None else "unknown"


def source_line(
    labels: Sequence[str],
    seasons: str,
    filters: Sequence[str],
    store: SnapshotStore,
) -> str:
    """metric · season(s) · filters · data through <latest game date>."""
    latest = store.manifest.get("latest_game_date") or latest_game_date(store)
    parts = [", ".join(labels), seasons, *[f for f in filters if f], f"data through {latest}"]
    return " · ".join(p for p in parts if p)


def season_phrase(season: str | None, season_type: str) -> str:
    st = season_type.lower() if season_type != "PlayIn" else "Play-In"
    return f"{season} {st}" if season else st
