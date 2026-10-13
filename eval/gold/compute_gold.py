"""Compute the gold values in ``eval/cases.yaml`` from the pinned snapshot (task 2.6).

Usage::

    uv run python -m eval.gold.compute_gold            # rewrite cases.yaml and gold_report.md
    uv run python -m eval.gold.compute_gold --check    # recompute; exit 1 if anything differs
    uv run python -m eval.gold.compute_gold --out DIR  # write both files to DIR instead
    uv run python -m eval.gold.compute_gold --threads 1

Deterministic code only (no LLM). Each Stats/Mixed answer runs one SQL block from
``eval/gold/gold.sql`` on ``eval_2025_26_rs``, opened read-only through
:func:`app.snapshot.connect_read_only`, after checking the snapshot's manifest and database
hashes against ``eval/snapshots.yaml``. Knowledge cases get their gold chunk ids and key facts
(exact glossary sentences); refusals get the refusal class. See eval/gold/README.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

from app.snapshot import APP_MEMORY_LIMIT, connect_read_only
from app.tools.schemas import STAT_LINE, expand_metrics
from metrics.rounding import round_half_up
from metrics.schema import Registry, registry

ROOT = Path(__file__).resolve().parents[2]
GOLD_DIR = Path(__file__).resolve().parent
SQL_PATH = GOLD_DIR / "gold.sql"
REPORT_NAME = "gold_report.md"
CASES_PATH = ROOT / "eval" / "cases.yaml"
SNAPSHOTS_PATH = ROOT / "eval" / "snapshots.yaml"
GLOSSARY = ROOT / "metrics" / "glossary"
FLOAT_DECIMALS = 6  # stored precision; scoring uses the registry rounding (D-025)

# Registry constants the gold SQL hard-codes (checked against metrics/registry.yaml on each run).
SQL_CONSTANTS: dict[tuple[str, str], Any] = {
    ("per_game_leader", "min_games_pct"): 0.70,
    ("per_game_leader", "would_still_lead"): True,
    ("per_game_leader_playoffs", "min_games_pct"): 0.70,
    ("per_game_leader_playoffs", "would_still_lead"): False,
    ("fg3_pct_leader", "min_made"): 82,
    ("ts_pct_leader", "min_games_pct"): 0.70,
    ("ts_pct_leader", "min_made"): 300,
    ("career_per_game", "min_career_games"): 400,
    ("career_per_game", "min_career_total"): 10000,
}
QUAL_SEASON = {"career_per_game": "1946-47", "per_game_leader_playoffs": "2024-25"}

# Knowledge gold: chunk id -> key facts, each an exact fragment of the glossary chunk (compared
# with whitespace collapsed).
FACTS: dict[str, list[str]] = {
    "true_shooting_pct": [
        "TS% = PTS / (2 \u00d7 (FGA + 0.44 \u00d7 FTA))",
        "The 0.44 factor estimates how many possessions free throw attempts use",
        "counts 2-pointers, 3-pointers and free throws together",
    ],
    "player_efficiency_rating": [
        "created by basketball analyst John Hollinger",
        "scales the result so the league average is 15",
        "NBA.com does not publish PER, and this assistant does not compute it",
    ],
    "usage_rate": [
        'share of a team\'s plays a player "uses" while on the floor',
        "field goal attempt, free throw trip or turnover",
    ],
    "net_rating": [
        "offensive rating minus defensive rating",
        "point differential per 100 possessions",
    ],
    "triple_doubles": [
        "10 or more in at least three of five categories: points, rebounds, assists, "
        "steals and blocks",
    ],
    "per_game_leader": [
        "at least 70% of his team's games",
        "In an 82-game season that is 58 games",
        "would still be the highest in the league",
        "separate from the 65-game minimum for awards",
    ],
}

# Gold-answer rule for name clarifications (PM decision D-027), mirroring app/entities.py.
_SHARED = (
    "Clarify (D-027): the candidates are every player in the snapshot the name resolves to under "
    "the entity resolver's shared-name rule (app/entities.py): "
)
CLARIFY_RULE = {
    "H01": _SHARED + "a bare surname matches every player with that last name, accent- and "
    "case-insensitive, any era and any number of games.",
    "H02": _SHARED + "a bare surname matches every player with that last name, accent- and "
    "case-insensitive, any era and any number of games.",
    "H03": _SHARED + "a bare surname matches every player with that last name, accent- and "
    "case-insensitive, any era and any number of games.",
    "H04": _SHARED + "an initial plus surname matches every player with that last name whose "
    "name starts with the initial, any era; 'this season' does not narrow the set.",
}

# Refusal class from the seed table's answer type.
DECLINE = {
    "Q81": "prediction",
    "Q82": "betting",
    "Q83": "injury news",
    "Q84": "non-NBA league (WNBA)",
}

# Allowed-but-not-required numbers (T-2.15b): block id -> "column[=metric], ..." of result
# columns an answer may state as context. They are taken from every result row and tagged with
# the registry metric whose rounding applies (same convention as `numbers:`). A stated number
# that matches one passes the numeric scorer; none of them is required.
ALLOWED: dict[str, str] = {
    "Q43": "conference_rank=games_played, win_pct",
    "Q57": "home_pts=game_points, away_pts=game_points",
    "Q62": "league_points_per_game",
    "Q72": "centers_avg_usage_rate=usage_rate, centers=games_played",
    "Q73": "made=field_goals_made, share=shot_fg_pct",
    "M03.2": "threes_made, threes_attempted, pooled_three_point_pct=three_point_pct",
}

# Interpretations the owner should approve (written into gold_report.md).
ASSUMPTIONS = [
    "Gold SQL reads the generated semantic views (registry formulas), not the tools, so tools "
    "are checked against it in 3.9; every id is an exact snapshot id from the gold tool call.",
    "Required numbers (`answer`) are the values of the gold tool call's metrics for the rows a "
    "correct answer lists; other columns are context. Values are stored as fractions/raw "
    f"numbers rounded to {FLOAT_DECIMALS} decimals; scoring applies the registry rounding.",
    "A number with no registry metric of its own carries the registry count metric whose "
    "rounding applies (0 decimals): game scores, player game points and margins -> "
    "game_points; win streak -> wins; overtime-game count -> games_played; MVP count -> "
    "mvp_awards; single-game 3-pointers -> threes_made; box rebounds/assists -> rebounds/assists.",
    "Ranked answers keep every row tied at the cut (RANK() <= limit) and list ties by id or "
    "date (D-025); row order is scored only when `ordered: true`.",
    "Per-game leaders: games >= ceil(0.70 x team games) from the view's team_gp (the last "
    "team's games for traded players), or fewer if total / that minimum beats the best "
    "qualified average. Playoff leaders: 70% of the team's playoff games, no would-still-lead.",
    "Regular season unless the case names playoffs; Q51 alone counts any season type.",
    "Not-tracked cases assert the value is NULL (not 0) and record stat_availability's first "
    "season.",
    "Clarify cases list every snapshot player the name resolves to under the entity resolver's "
    "shared-name rule (D-027), any era and any number of games; gold entities equal that list. "
    "M10 turn 3 ('he') lists the two players of the conversation.",
    "Knowledge facts are exact glossary fragments; text answers are scored by the judge (2.20).",
    "Allowed numbers (`allowed`) are context columns of the result rows that an answer may "
    "state but need not (Q43 rank and win percentage, Q57 game scores, Q62 the other seasons, "
    "Q72 the centers' average and count, Q73 makes and share, M03 turn 2 makes, attempts and "
    "pooled 3P%); they carry a registry metric for rounding like required numbers.",
]

# Seeds and turns whose gold depends on an interpretation the owner should confirm.
AMBIGUOUS = {
    "Q05": "Rookie season = first regular season in player_season (rule).",
    "Q08": "2025-26 Lakers stint only (rule); gold entities list the player, not the Lakers.",
    "Q27": "One row per season for each player's first two seasons (compare tool scope), not a "
    "two-season average.",
    "Q35": "Box-score count (partial before 1996-97); the curated records table has no career "
    "triple-double row yet (G1).",
    "Q37": "Registry career minimum is 400 games OR 10,000 points (unconfirmed); the T-SEEDS "
    "query used AND. Same leader either way.",
    "Q43": "Wins and losses required for all 15 teams; win percentage is context.",
    "Q48": "Warriors stint rows; the 'would still lead' benchmark is the best qualified "
    "Warrior, so Curry (43 games, 26.6) leads; with a plain 70% games rule it would be "
    "Podziemski (as in T-SEEDS).",
    "Q55": "Points, rebounds and assists leaders of each 2026-04-12 game; tied leaders all named.",
    "Q57": "Required: the number of overtime games; the list of games is context.",
    "Q62": "Required: 1990-91..1999-00 and 2025-26 values; higher_than_1990s compares 2025-26 "
    "with the best 1990s season.",
    "Q64": "'Gone up every season' = strictly higher than the previous season, every season.",
    "Q71": "TS% minimum (70% of games and 300 FGM, decision 0007) is unconfirmed (3.2).",
    "Q72": "Required: Jokic's usage rate; the centers' average (position 'Center%', 500+ "
    "minutes) is context only.",
    "Q73": "Attempts in every zone required; share is context.",
    "M03": "Turn 2: one row per season for each player's last three seasons; pooled 3P% is "
    "context.",
    "M06": "Turn 3: required number is the 2024-25 rating only (turn 2 gave 2025-26).",
    "H04": "Candidate set = every J* Williams in the snapshot (resolver rule, D-027), not only "
    "2025-26 players: should 'this season' narrow a clarification?",
    "H01": "Justin Holiday (last season 2022-23) is a candidate for 'averaging this season' "
    "under the resolver rule (D-027).",
}


@dataclass
class Block:
    id: str
    sql: str
    line: int
    comment: list[str] = field(default_factory=list)
    key: list[str] = field(default_factory=list)
    numbers: list[tuple[str, str]] = field(default_factory=list)  # (column, registry metric)
    totals: list[tuple[str, str]] = field(default_factory=list)  # constant columns, stated once
    required_rows: str | None = None  # boolean column selecting the rows whose numbers count
    nulls: list[str] = field(default_factory=list)  # columns that must be NULL (not tracked)
    ordered: bool = False
    ties: str | None = None


@dataclass(frozen=True)
class Provenance:
    snapshot_id: str
    manifest_sha256: str
    db_sha256: str
    registry_version: str
    db: Path
    shots: Path


def _pairs(spec: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        if part == "@stat_line":
            out += [(m, m) for m in STAT_LINE]
            continue
        col, _, metric = part.partition("=")
        out.append((col.strip(), (metric or col).strip()))
    return out


def parse_blocks(text: str) -> dict[str, Block]:
    """Split gold.sql into blocks keyed by id (``-- @Q01``)."""
    blocks: dict[str, Block] = {}
    cur: Block | None = None
    sql_lines: list[str] = []
    cont: str | None = None  # directive continued on the next comment line

    def close() -> None:
        if cur is not None:
            # Section comments between blocks are not part of the SQL.
            while sql_lines and (not sql_lines[-1].strip() or sql_lines[-1].startswith("--")):
                sql_lines.pop()
            sql = "\n".join(sql_lines).strip()
            if not sql.endswith(";") or sql.count(";") != 1:
                raise ValueError(f"gold.sql block {cur.id} must be one statement ending with ';'")
            cur.sql = sql[:-1].rstrip()
            blocks[cur.id] = cur

    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        m = re.match(r"^-- @([A-Z]\d{2}(?:\.\d|-[a-z0-9]+)?)\s*$", line)
        if m:
            close()
            if m.group(1) in blocks:
                raise ValueError(f"duplicate gold.sql block {m.group(1)}")
            cur, sql_lines, cont = Block(m.group(1), "", n), [], None
            continue
        if cur is None:
            continue
        if line.startswith("--") and not sql_lines:
            body = line[2:].strip()
            d = re.match(r"^(key|numbers|totals|required-rows|null|ordered|ties):\s*(.*)$", body)
            if d:
                name, val = d.groups()
                cont = None
                if name == "key":
                    cur.key = [c.strip() for c in val.split(",") if c.strip()]
                elif name == "numbers":
                    cur.numbers = _pairs(val)
                elif name == "totals":
                    cur.totals = _pairs(val)
                elif name == "required-rows":
                    cur.required_rows = val.strip()
                elif name == "null":
                    cur.nulls = [c.strip() for c in val.split(",") if c.strip()]
                elif name == "ordered":
                    cur.ordered = val.strip() == "true"
                else:
                    cur.ties, cont = val.strip(), "ties"
            elif cont == "ties" and raw.startswith("--   "):
                cur.ties = f"{cur.ties} {body}"
            else:
                cont = None
                cur.comment.append(body)
            continue
        sql_lines.append(raw)
    close()
    return blocks


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def provenance() -> Provenance:
    """The pinned snapshot, after checking its hashes against eval/snapshots.yaml."""
    pin = yaml.safe_load(SNAPSHOTS_PATH.read_text())["eval"]
    snap = ROOT / pin["path"]
    manifest = snap / "manifest.json"
    db = ROOT / pin["db"]
    if not manifest.exists() or not db.exists():
        raise FileNotFoundError(f"pinned snapshot {pin['snapshot_id']} not found at {snap}")
    msha, dsha = _sha256(manifest), _sha256(db)
    if msha != pin["manifest_sha256"]:
        raise RuntimeError(f"manifest sha256 {msha} != snapshots.yaml {pin['manifest_sha256']}")
    if dsha != pin["db_sha256"]:
        raise RuntimeError(f"database sha256 {dsha} != snapshots.yaml {pin['db_sha256']}")
    return Provenance(
        pin["snapshot_id"], msha, dsha, str(pin["registry_version"]), db, ROOT / pin["shots"]
    )


def check_registry(reg: Registry, prov: Provenance) -> None:
    """The SQL's hard-coded qualification constants and versions still match the registry."""
    if reg.version != prov.registry_version:
        raise RuntimeError(
            f"registry {reg.version} != snapshot registry {prov.registry_version}: rebuild first"
        )
    for (qual, attr), want in SQL_CONSTANTS.items():
        rule = reg.qualification(qual).rule_for(QUAL_SEASON.get(qual, "2025-26"))
        got = getattr(rule, attr)
        if got != want:
            raise RuntimeError(f"registry {qual}.{attr} = {got}, gold.sql assumes {want}")


def connect(prov: Provenance, threads: int | None = None) -> duckdb.DuckDBPyConnection:
    """Read-only, locked-down connection (app.snapshot), optionally with a fixed thread count."""
    pre = None
    if threads is not None:
        # Same config as connect_read_only so the shared instance is reused; set threads before
        # it locks the configuration.
        pre = duckdb.connect(
            str(prov.db), read_only=True, config={"memory_limit": APP_MEMORY_LIMIT}
        )
        pre.execute(f"SET threads = {int(threads)}")
    con = connect_read_only(prov.db, prov.shots)
    if pre is not None:
        pre.close()
    return con


def _cell(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        r = round(v, FLOAT_DECIMALS)
        return 0.0 if r == 0 else r
    if isinstance(v, dt.datetime):
        return v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    return v


def run_block_raw(
    con: duckdb.DuckDBPyConnection, b: Block
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(stored rows, raw rows): stored floats keep FLOAT_DECIMALS; raw rows are as DuckDB gave."""
    cur = con.execute(b.sql)
    cols = [d[0] for d in cur.description]
    fetched = cur.fetchall()
    raw = [dict(zip(cols, r, strict=True)) for r in fetched]
    rows = [{k: _cell(v) for k, v in r.items()} for r in raw]
    for c in [n for n, _ in b.numbers + b.totals] + b.key + b.nulls:
        if c not in cols:
            raise ValueError(f"gold.sql {b.id}: no column {c!r} in {cols}")
    return rows, raw


def run_block(con: duckdb.DuckDBPyConnection, b: Block) -> list[dict[str, Any]]:
    return run_block_raw(con, b)[0]


class DisplayMismatch(ValueError):
    """A stored (rounded) gold value would display differently from the raw value."""


def _check_display(raw: Any, stored: Any, metric: str, reg: Registry, where: str = "") -> None:
    """Fail if the stored value shows differently from the raw one under the registry rounding
    (half-up, percent metrics x100). Called for every required and allowed gold number."""
    if isinstance(raw, decimal.Decimal):
        raw = float(raw)
    r = reg.metric(metric).rounding
    scale = 100 if r.display == "percent" else 1
    if round_half_up(float(raw) * scale, r.decimals) != round_half_up(
        float(stored) * scale, r.decimals
    ):
        raise DisplayMismatch(
            f"{where}: {metric} raw {raw!r} stored as {stored!r} displays differently "
            f"under the registry rounding ({r.decimals} decimals, {r.display})"
        )


def _raw_of(raw: list[dict[str, Any]] | None, i: int, col: str, stored: Any) -> Any:
    return stored if raw is None else raw[i][col]


def answer_numbers(
    b: Block,
    rows: list[dict[str, Any]],
    reg: Registry,
    raw: list[dict[str, Any]] | None = None,
    where: str = "",
) -> list[dict[str, Any]]:
    """The numbers a correct answer states, tagged with the registry metric for rounding.

    With ``raw`` (the unrounded rows), each number is checked by :func:`_check_display`.
    """
    out: list[dict[str, Any]] = []
    where = where or b.id
    for col, metric in b.totals:
        vals = {r[col] for r in rows}
        if len(vals) != 1:
            raise ValueError(f"gold.sql {b.id}: totals column {col} is not constant")
        v = vals.pop()
        if v is not None:
            for i, r in enumerate(rows):
                _check_display(_raw_of(raw, i, col, v), r[col], metric, reg, f"{where} {col}")
            out.append({"metric": reg.metric(metric).name, "value": v, "column": col})
    for i, r in enumerate(rows):
        if b.required_rows and not r[b.required_rows]:
            continue
        key = ", ".join(str(r[k]) for k in b.key)
        for col, metric in b.numbers:
            v = r[col]
            if v is None:
                continue  # not tracked: nothing to state
            if isinstance(v, bool) or not isinstance(v, int | float):
                raise ValueError(f"gold.sql {b.id}: {col} is not numeric ({v!r})")
            _check_display(_raw_of(raw, i, col, v), v, metric, reg, f"{where} row {i} {col}")
            item: dict[str, Any] = {"metric": reg.metric(metric).name, "value": v, "column": col}
            if key:
                item["key"] = key
            out.append(item)
    return out


def allowed_numbers(
    b: Block,
    rows: list[dict[str, Any]],
    reg: Registry,
    required: list[dict[str, Any]],
    raw: list[dict[str, Any]] | None = None,
    where: str = "",
) -> list[dict[str, Any]]:
    """Context numbers an answer may state (ALLOWED), from every row, minus required ones."""
    spec = ALLOWED.get(b.id)
    if not spec:
        return []
    out: list[dict[str, Any]] = []
    where = where or b.id
    for i, r in enumerate(rows):
        key = ", ".join(str(r[k]) for k in b.key)
        for col, metric in _pairs(spec):
            if col not in r:
                raise ValueError(f"gold.sql {b.id}: allowed column {col!r} not in the result")
            v = r[col]
            if v is None:
                continue
            if isinstance(v, bool) or not isinstance(v, int | float):
                raise ValueError(f"gold.sql {b.id}: allowed {col} is not numeric ({v!r})")
            _check_display(_raw_of(raw, i, col, v), v, metric, reg, f"{where} row {i} {col}")
            item: dict[str, Any] = {"metric": reg.metric(metric).name, "value": v, "column": col}
            if key:
                item["key"] = key
            if item not in required and item not in out:
                out.append(item)
    return out


def _tool_metrics(gold: dict[str, Any]) -> set[str] | None:
    tc = gold.get("tool_call")
    if not tc:
        return None
    args = tc["args"]
    if "metrics" in args:
        return set(expand_metrics(list(args["metrics"])))
    if "metric" in args:
        return {str(args["metric"])}
    return None


def build_value(
    gold: dict[str, Any],
    block: Block | None,
    rows: list[dict[str, Any]] | None,
    prov: Provenance,
    reg: Registry,
    case_id: str,
    raw: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    path, expect = gold["path"], gold.get("expect", "answer")
    src: dict[str, Any] = {"snapshot": prov.snapshot_id, "manifest_sha256": prov.manifest_sha256}
    src["registry_version"] = reg.version
    if expect == "decline":
        return {"kind": "decline", "reason": DECLINE[case_id.split("-")[0]]}
    if path == "knowledge":
        return {
            "kind": "knowledge",
            "chunks": list(gold["chunks"]),
            "facts": [f for c in gold["chunks"] for f in FACTS[c]],
            "source": {"glossary": [f"metrics/glossary/{c}.md" for c in gold["chunks"]]},
        }
    if block is None or rows is None:
        if expect == "no_verdict":
            return {
                "kind": "no_verdict",
                "answer": [],
                "rows": [],
                "note": "No gold tool call: any stats-based answer without a verdict passes.",
            }
        raise ValueError(f"{case_id}: no gold.sql block for a {path}/{expect} case")
    src["block"] = block.id
    if not rows:
        raise ValueError(f"{case_id}: gold.sql {block.id} returned no rows")
    if expect == "clarify":
        return {"kind": "clarify", "candidates": rows, "source": src}
    if expect == "not_tracked":
        if len(block.nulls) != 1:
            raise ValueError(f"{case_id}: a not-tracked block names one `null:` column")
        col = block.nulls[0]
        if any(r[col] is not None for r in rows):
            raise ValueError(f"{case_id}: {col} should be NULL (not tracked), not a number")
        return {
            "kind": "not_tracked",
            "column": col,
            "stat": rows[0]["stat"],
            "first_season_tracked": rows[0]["first_season_tracked"],
            "rows": rows,
            "source": src,
        }
    if raw is None or len(raw) != len(rows):
        raise ValueError(f"{case_id}: raw rows are needed to check displayed values")
    nums = answer_numbers(block, rows, reg, raw, case_id)
    want = _tool_metrics(gold)
    if want is not None and nums:
        got = {n["metric"] for n in nums}
        if not got <= want:
            raise ValueError(f"{case_id}: numbers {sorted(got)} not in tool metrics {sorted(want)}")
    if not nums and block.numbers:
        raise ValueError(f"{case_id}: no numbers to state")
    value: dict[str, Any] = {"kind": expect if expect == "no_verdict" else "answer"}
    value["ordered"] = block.ordered
    if block.ties:
        value["ties"] = block.ties
    value["answer"] = nums
    allowed = allowed_numbers(block, rows, reg, nums, raw, case_id)
    if allowed:
        value["allowed"] = allowed
    value["rows"] = rows
    if path == "mixed":
        value["chunks"] = list(gold["chunks"])
        value["facts"] = [f for c in gold["chunks"] for f in FACTS[c]]
    value["source"] = src
    return value


def _block_id(
    case: dict[str, Any], by_id: dict[str, dict[str, Any]], blocks: dict[str, Block]
) -> str:
    cid = str(case["id"])
    if cid in blocks:
        return cid
    if case["type"] in ("paraphrase", "entity_variant"):
        seed = by_id[str(case["seed_id"])]
        if case["gold"].get("tool_call") != seed["gold"].get("tool_call"):
            raise ValueError(f"{cid}: tool call differs from its seed; add a gold.sql block @{cid}")
        return str(case["seed_id"])
    return cid


@dataclass
class Result:
    doc: dict[str, Any]
    report_rows: list[tuple[str, str, str, str, str, str]]
    counts: dict[str, int]


def compute(prov: Provenance, threads: int | None = None) -> Result:
    reg = registry()
    check_registry(reg, prov)
    sql_text = SQL_PATH.read_text()
    blocks = parse_blocks(sql_text)
    text = CASES_PATH.read_text()
    doc = yaml.safe_load(text)
    by_id = {str(c["id"]): c for c in doc["cases"]}
    con = connect(prov, threads)
    got = con.execute("select registry_version from semantic.registry_info").fetchone()
    if got is None or got[0] != reg.version:
        raise RuntimeError(f"snapshot registry_info {got} != registry {reg.version}")
    results: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}
    used: set[str] = set()
    values: dict[str, dict[str, Any]] = {}  # block id / case id -> value (shared by inheritors)
    report: list[tuple[str, str, str, str, str, str]] = []
    counts: dict[str, int] = {}

    def gold_for(unit: str, question: str, gold: dict[str, Any], bid: str, split: str) -> None:
        block = blocks.get(bid)
        rows = raw = None
        if block is not None:
            used.add(bid)
            if bid not in results:
                results[bid] = run_block_raw(con, block)
            rows, raw = results[bid]
        # Inheriting cases share their seed's value object (a YAML anchor/alias pair).
        cache_key = f"{bid}|{gold['path']}|{gold.get('expect', 'answer')}"
        if cache_key not in values:
            values[cache_key] = build_value(gold, block, rows, prov, reg, unit, raw)
        value = values[cache_key]
        gold["value"] = value
        if block is not None:
            gold["sql"] = block.sql
        if value["kind"] == "clarify":
            # D-027: the expected entities are exactly the computed candidates.
            gold["entities"] = {"players": [int(r["player_id"]) for r in value["candidates"]]}
            if bid in CLARIFY_RULE:
                gold["rule"] = CLARIFY_RULE[bid]
        kind = str(value["kind"])
        counts[kind] = counts.get(kind, 0) + 1
        # One report row per computed block, and per seed without one (knowledge, refusals).
        if (block is not None and unit == bid) or (block is None and "-" not in unit):
            where = f"gold.sql:{block.line}" if block is not None else "-"
            note = " ".join(block.comment) if block is not None else ""
            report.append((unit, split, question, _summary(value, reg), where, note))

    for case in doc["cases"]:
        cid, split = str(case["id"]), str(case.get("split"))
        if case.get("turns"):
            for i, turn in enumerate(case["turns"], 1):
                gold_for(f"{cid}.{i}", turn["question"], turn["gold"], f"{cid}.{i}", split)
        else:
            gold_for(cid, case["question"], case["gold"], _block_id(case, by_id, blocks), split)
    stray = set(ALLOWED) - used
    if stray:
        raise ValueError(f"ALLOWED names blocks used by no case: {sorted(stray)}")
    unused = set(blocks) - used
    if unused:
        raise ValueError(f"gold.sql blocks used by no case: {sorted(unused)}")
    con.close()
    return Result(doc, report, counts)


def _fmt(n: dict[str, Any], reg: Registry) -> str:
    r = reg.metric(n["metric"]).rounding
    v = float(n["value"])
    if r.display == "percent":
        s = f"{round_half_up(v * 100, r.decimals)}%"
    else:
        s = str(round_half_up(v, r.decimals))
    return f"{n.get('key', '')} {n['column']} {s}".strip()


def _summary(value: dict[str, Any], reg: Registry) -> str:
    kind = value["kind"]
    if kind == "decline":
        return f"decline ({value['reason']})"
    if kind == "knowledge":
        return "chunks: " + ", ".join(value["chunks"])
    if kind == "clarify":
        names = ", ".join(f"{r['player_name']} ({r['player_id']})" for r in value["candidates"])
        return f"clarify: {names}"
    if kind == "not_tracked":
        return f"not tracked: {value['stat']} from {value['first_season_tracked']} (NULL)"
    nums = value.get("answer", [])
    if not nums:
        rows = value.get("rows", [])
        if rows and "player_name" in rows[0]:
            return "; ".join(str(r["player_name"]) for r in rows) or kind
        return str(value.get("note", kind))
    shown = [_fmt(n, reg) for n in nums[:6]]
    more = f" (+{len(nums) - 6} more)" if len(nums) > 6 else ""
    return "; ".join(shown) + more


def _cell_md(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def render_report(res: Result, prov: Provenance) -> str:
    reg = registry()
    lines = [
        "# Gold values report (task 2.6)",
        "",
        "Generated by `uv run python -m eval.gold.compute_gold`; do not edit by hand.",
        "",
        f"- Snapshot: `{prov.snapshot_id}`",
        f"- Manifest sha256: `{prov.manifest_sha256}`",
        f"- Database sha256: `{prov.db_sha256}`",
        f"- Registry version: `{reg.version}`",
        f"- Gold SQL: `eval/gold/gold.sql` sha256 `{_sha256(SQL_PATH)}`",
        "- Values by kind: "
        + ", ".join(f"{k} {v}" for k, v in sorted(res.counts.items()))
        + " (case units, turns counted one by one)",
        "",
        "Paraphrases and entity variants with the seed's gold tool call inherit the seed's value "
        "and are not listed. Numbers are shown under the registry rounding; the stored values "
        "keep 6 decimals. Held-out cases are included (logged in eval/contamination.md).",
        "",
        "## Assumptions (owner to approve)",
        "",
    ]
    lines += [f"{i}. {a}" for i, a in enumerate(ASSUMPTIONS, 1)]
    lines += ["", "## Seeds with an interpretation to confirm", ""]
    lines += [f"- **{k}**: {v}" for k, v in AMBIGUOUS.items()]
    lines += [
        "",
        "## Gold values",
        "",
        "| Case | Split | Question | Gold value | Source | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in res.report_rows:
        lines.append("| " + " | ".join(_cell_md(c) for c in row) + " |")
    return "\n".join(lines) + "\n"


def render_cases(res: Result) -> str:
    text = CASES_PATH.read_text()
    header = "".join(ln for ln in text.splitlines(keepends=True) if ln.startswith("#"))
    return header + yaml.safe_dump(res.doc, sort_keys=False, allow_unicode=True, width=100)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    p.add_argument("--check", action="store_true", help="exit 1 if stored gold differs")
    p.add_argument("--out", type=Path, help="write cases.yaml and gold_report.md here")
    p.add_argument("--threads", type=int, help="DuckDB threads (determinism checks)")
    a = p.parse_args(argv)
    prov = provenance()
    try:
        res = compute(prov, a.threads)
    except DisplayMismatch as exc:
        print(f"gold display check failed: {exc}", file=sys.stderr)
        return 2
    cases_text, report_text = render_cases(res), render_report(res, prov)
    if a.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, new in ((CASES_PATH, cases_text), (GOLD_DIR / REPORT_NAME, report_text))
            if not path.exists() or path.read_text() != new
        ]
        if stale:
            print(f"gold is stale: {', '.join(stale)}", file=sys.stderr)
            return 1
        print("gold up to date")
        return 0
    out_cases = CASES_PATH if a.out is None else a.out / "cases.yaml"
    out_report = GOLD_DIR / REPORT_NAME if a.out is None else a.out / REPORT_NAME
    if a.out is not None:
        a.out.mkdir(parents=True, exist_ok=True)
    out_cases.write_text(cases_text)
    out_report.write_text(report_text)
    if a.out is None:
        from eval.schema import load

        load(out_cases)  # validate
    for path in (out_cases, out_report):
        print(f"{_sha256(path)}  {path}")
    print("values by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(res.counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
