"""SQL-fallback guardrails, part 1: the parser check (task 3.16).

A generated query is accepted only if, parsed with sqlglot (DuckDB dialect), it is exactly one
``SELECT`` (CTEs and set operations allowed) and every relation it reads is a semantic-layer
view from ``transform/semantic_allowlist.txt`` or one of its own CTE names. Table functions
(``read_csv``, ``read_parquet``, ...), file paths given as table names (``FROM 'x.json'``), and
any ``ATTACH``, ``COPY``, ``PRAGMA``, ``SET``, DDL or DML are rejected. A ``LIMIT 100`` is added
when the outer query has none; any outer limit that is not a plain integer from 0 to 100 (a
larger number, a percent, an expression, a parameter, ``WITH TIES``) is replaced by ``LIMIT 100``.

An unqualified name counts as a CTE only where SQL scoping makes it one (SEC-001): the CTE is
declared in a ``WITH`` of an enclosing query, and, inside a ``WITH`` list, only earlier CTEs are
visible. A CTE's own name inside its body is not a CTE reference, because DuckDB binds it to the
catalog table of that name (``sqlite_master``, ``duckdb_tables``, ...), so recursive CTEs are
rejected. Queries over ``MAX_SQL_CHARS`` and anything sqlglot cannot parse, including input
nested deeply enough to exhaust the recursion limit, raise :class:`GuardError` (SEC-005).
So do a NUL character or text that cannot be encoded as UTF-8 (a lone surrogate), which sqlglot
would pass through but DuckDB cannot run, and ``USING SAMPLE`` / ``TABLESAMPLE`` (SEC-012: the
LIMIT would be written in front of a ``USING SAMPLE`` clause, which is invalid SQL).

Part 2, the engine lockdown and the 5 s watchdog, is in :mod:`app.sql_fallback`. It also
blocks file reads if this parser check were ever bypassed.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "transform" / "semantic_allowlist.txt"
MAX_ROWS = 100
MAX_SQL_CHARS = 4000


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
    exp.TableSample,  # USING SAMPLE / TABLESAMPLE (SEC-012); no stats question needs a sample
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
    if len(sql) > MAX_SQL_CHARS:
        raise GuardError(f"the SQL is {len(sql)} characters; at most {MAX_SQL_CHARS} are allowed")
    if "\x00" in sql:
        raise GuardError("the SQL contains a NUL character")
    try:
        sql.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GuardError(f"the SQL contains text that is not valid UTF-8 ({exc.reason})") from None
    try:
        return _check(sql, allowed)
    except SqlglotError as exc:
        raise GuardError(f"could not parse the SQL: {str(exc).splitlines()[0]}") from exc
    except RecursionError:
        raise GuardError("the SQL is nested too deeply") from None


def _check(sql: str, allowed: frozenset[str]) -> str:
    statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    if len(statements) != 1:
        raise GuardError("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Select | exp.Union | exp.Intersect | exp.Except):
        raise GuardError(f"only SELECT is allowed, not {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN):
            raise GuardError(f"{node.key.upper()} is not allowed")
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
        if not table.db and name in _visible_ctes(table):
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


def _visible_ctes(table: exp.Table) -> set[str]:
    """CTE names an unqualified table reference can resolve to, by walking up its ancestors.

    A query's ``WITH`` is visible from the query body and everything nested in it. From inside
    the i-th CTE of a ``WITH`` list only CTEs 0..i-1 are visible: a later CTE or the CTE itself
    would bind to a catalog table in DuckDB (even under ``WITH RECURSIVE``, in the anchor term or
    a body without ``UNION``), so neither counts. A sibling subquery's ``WITH`` is never visible.
    """
    names: set[str] = set()
    child: object = table  # compared by identity only
    node = table.parent
    while node is not None:
        if isinstance(node, exp.With):
            for cte in node.expressions:
                if cte is child:
                    break
                names.add(cte.alias_or_name.lower())
        else:
            with_ = node.args.get("with_")
            if isinstance(with_, exp.With) and with_ is not child:
                names.update(c.alias_or_name.lower() for c in with_.expressions)
        child, node = node, node.parent
    return names


def _with_limit(tree: exp.Expression) -> exp.Expression:
    # Select, Union, Intersect and Except all take a trailing LIMIT, which for a set operation
    # caps the combined result (any WITH clause stays attached in front).
    assert isinstance(tree, exp.Query)  # narrowed by check(): Select or a set operation
    limit = tree.args.get("limit")
    if limit is None:
        return tree.limit(MAX_ROWS)
    if not _plain_limit_within_cap(limit):
        # Keeps any OFFSET (a separate node); drops PERCENT, WITH TIES, FETCH, expressions.
        tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))
    return tree


def _plain_limit_within_cap(limit: exp.Expression) -> bool:
    """True only for ``LIMIT n`` with n a plain integer literal from 0 to MAX_ROWS (SEC-002)."""
    if not isinstance(limit, exp.Limit):
        return False  # FETCH FIRST ... and anything else
    if any(limit.args.get(k) for k in ("this", "limit_options", "expressions")):
        return False  # PERCENT, WITH TIES, LIMIT BY
    n = limit.expression
    if not isinstance(n, exp.Literal) or n.is_string or not re.fullmatch(r"[0-9]+", n.name):
        return False  # expression, parameter, subquery, negative, decimal, exponent
    return int(n.name) <= MAX_ROWS
