"""Display formatting under the registry's rounding rules.

The model is given values already rounded for display, so it copies numbers rather than
rounding them, and the deterministic fallback table uses the same strings.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from metrics.rounding import round_half_up
from metrics.schema import Registry, registry


def display(
    value: Any, column: str, metric_cols: Sequence[str], reg: Registry | None = None
) -> str:
    reg = reg or registry()
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int | float) and column in metric_cols:
        r = reg.metric(column).rounding
        if r.display == "percent":
            return f"{round_half_up(float(value) * 100, r.decimals)}%"
        v = round_half_up(float(value), r.decimals)
        return f"{v:,}" if r.decimals == 0 else str(v)
    if isinstance(value, float):
        return str(round_half_up(value, 0 if value.is_integer() else 1))
    if isinstance(value, int):
        return f"{value:,}" if abs(value) >= 10000 else str(value)
    return str(value)


HIDDEN = {
    "player_id",
    "team_id",
    "franchise_id",
    "game_id",
    "season_number",
    "team_gp",
    "opponent_team_id",
}


def display_rows(
    rows: Sequence[dict[str, Any]], metric_cols: Sequence[str], reg: Registry | None = None
) -> list[dict[str, str]]:
    return [
        {k: display(v, k, metric_cols, reg) for k, v in r.items() if k not in HIDDEN} for r in rows
    ]


def table(
    rows: Sequence[dict[str, Any]],
    metric_cols: Sequence[str],
    reg: Registry | None = None,
    max_rows: int = 25,
) -> str:
    """A plain-text table of the result, used when an answer fails verification twice."""
    shown = display_rows(rows[:max_rows], metric_cols, reg)
    if not shown:
        return "No rows."
    cols = list(shown[0])
    reg = reg or registry()
    head = [reg.metric(c).label if c in metric_cols else c.replace("_", " ") for c in cols]
    widths = [max(len(h), *(len(r[c]) for r in shown)) for h, c in zip(head, cols, strict=True)]
    lines = [
        " | ".join(h.ljust(w) for h, w in zip(head, widths, strict=True)),
        "-+-".join("-" * w for w in widths),
    ]
    lines += [" | ".join(r[c].ljust(w) for c, w in zip(cols, widths, strict=True)) for r in shown]
    return "\n".join(lines)
