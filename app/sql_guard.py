"""SQL-fallback guardrails, part 1: the parser check (task 3.16).

A generated query is accepted only if, parsed with sqlglot (DuckDB dialect), it is exactly one
``SELECT`` (CTEs and set operations allowed) and every relation it reads is a semantic-layer
view from ``transform/semantic_allowlist.txt`` or one of its own CTE names. Table functions
(``read_csv``, ``read_parquet``, ...), file paths given as table names (``FROM 'x.json'``), and
any ``ATTACH``, ``COPY``, ``PRAGMA``, ``SET``, DDL or DML are rejected. A ``LIMIT 100`` is added
when the outer query has none, and a larger limit is lowered to 100.

Part 2, the engine lockdown and the 5 s watchdog, is in :mod:`app.sql_fallback`. It also
blocks file reads if this parser check were ever bypassed.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "transform" / "semantic_allowlist.txt"
MAX_ROWS = 100


class GuardError(ValueError):
    """The query is not allowed; the message says why (fed back for the one repair attempt)."""


@cache
def allowlist(path: Path = ALLOWLIST_PATH) -> frozenset[str]:
    return frozenset(
        ln.strip().lower()
        for ln in path.read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    )


_FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Set,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Merge,
    exp.TruncateTable,
    exp.Use,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
)


# Functions a stats query may call; everything else is rejected. An allowlist rather than a
# deny-list: functions such as repeat(), lpad() or scalar range() allocate unbounded memory that
# DuckDB's memory_limit does not cap (3.7 GB and 19 s for repeat('x', 4e9)), and others leak the
# environment (current_setting, version).
ALLOWED_FUNCTIONS = frozenset(
    {
        "Count",
        "CountIf",
        "Sum",
        "Avg",
        "Min",
        "Max",
        "AnyValue",
        "First",
        "Last",
        "ArgMax",
        "ArgMin",
        "Median",
        "PercentileCont",
        "PercentileDisc",
        "Stddev",
        "StddevPop",
        "StddevSamp",
        "Variance",
        "VariancePop",
        "Corr",
        "Round",
        "Floor",
        "Ceil",
        "Abs",
        "Sqrt",
        "Sign",
        "Pow",
        "Ln",
        "Log",
        "Exp",
        "Coalesce",
        "Nullif",
        "Greatest",
        "Least",
        "If",
        "Cast",
        "TryCast",
        "Lower",
        "Upper",
        "Length",
        "Substring",
        "Concat",
        "StartsWith",
        "Trim",
        "Rank",
        "DenseRank",
        "RowNumber",
        "Lag",
        "Lead",
        "Ntile",
        "PercentRank",
        "CumeDist",
        "FirstValue",
        "LastValue",
        "Year",
        "Month",
        "Day",
        "DayOfWeek",
        "Extract",
        "DateDiff",
        "TimeToStr",
        "CurrentDate",
        "Case",
    }
)
ALLOWED_ANONYMOUS = frozenset({"date_part", "datepart", "ifnull", "round_even"})


def check(sql: str, allowed: frozenset[str] | None = None) -> str:
    """Return the query to run (with a LIMIT), or raise :class:`GuardError`."""
    allowed = allowed if allowed is not None else allowlist()
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except ParseError as exc:
        raise GuardError(f"could not parse the SQL: {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise GuardError("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Select | exp.Union | exp.Intersect | exp.Except):
        raise GuardError(f"only SELECT is allowed, not {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN):
            raise GuardError(f"{node.key.upper()} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            # FROM read_csv(...), FROM 'data/raw/x.json', FROM some_function()
            raise GuardError(
                f"reading {table.this.sql(dialect='duckdb')} is not allowed; "
                "query semantic views only"
            )
        if table.catalog:
            raise GuardError("database-qualified names are not allowed")
        name = table.name.lower()
        full = f"{table.db.lower()}.{name}" if table.db else name
        if not table.db and name in ctes:
            continue
        if full not in allowed:
            raise GuardError(
                f"{full} is not a semantic-layer view; allowed views: " + ", ".join(sorted(allowed))
            )
    for fn in tree.find_all(exp.Func):
        if isinstance(fn, exp.Binary | exp.Unary | exp.Predicate):
            continue  # operators sqlglot models as functions: AND, OR, EXISTS, ...
        kind = type(fn).__name__
        if isinstance(fn, exp.Anonymous):
            if fn.name.lower() in ALLOWED_ANONYMOUS:
                continue
            name = fn.name.lower()
        elif kind in ALLOWED_FUNCTIONS:
            continue
        else:
            name = fn.sql_name().lower() if hasattr(fn, "sql_name") else kind.lower()
        raise GuardError(
            f"function {name}() is not allowed; use aggregates, arithmetic, "
            "round/coalesce/cast, window ranks and date parts"
        )
    return _with_limit(tree).sql(dialect="duckdb")


def _with_limit(tree: exp.Expression) -> exp.Expression:
    limit = tree.args.get("limit")
    if limit is None:
        if isinstance(tree, exp.Select):
            return tree.limit(MAX_ROWS)
        return exp.select("*").from_(exp.subquery(tree, "q")).limit(MAX_ROWS)
    try:
        n = int(limit.expression.name)
    except (AttributeError, ValueError):
        n = MAX_ROWS + 1
    if n > MAX_ROWS:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))
    return tree
