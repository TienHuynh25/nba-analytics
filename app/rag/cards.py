"""Schema cards (task 3.15) and tool cards (task 3.13): text chunks for retrieval.

Schema cards: one chunk per semantic view and one per column, with the column type, the registry
description for metric columns, and example values from the snapshot. The SQL fallback retrieves
them. Tool cards: one chunk per typed tool, generated from its JSON argument schema, with example
questions. Cards are regenerated from the schemas and the snapshot, so they never drift.
Metadata on every chunk: doc_type, registry_version.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from app.interfaces import Chunk
from metrics.schema import Registry, load

TOOL_SCHEMAS = Path(__file__).resolve().parent.parent / "tools" / "schemas"

# Example questions per tool. Invented for the cards; never taken from eval/cases.yaml, so
# retrieval is not tuned to the test set.
TOOL_EXAMPLES = {
    "get_player_stats": [
        "What is Devin Booker shooting from three this season?",
        "How many rebounds per game did Rudy Gobert average in 2021-22?",
    ],
    "get_leaders": [
        "Who led the league in rebounds per game in 2018-19?",
        "Which team had the best defensive rating in 2015-16?",
    ],
    "compare": [
        "Compare Chris Paul and Steve Nash career assists per game.",
        "Who scored more in 2019-20, Damian Lillard or Bradley Beal?",
    ],
    "get_team_stats": [
        "What was the Heat's pace in 2022-23?",
        "How many road games did the Bucks win in 2020-21?",
    ],
    "get_standings": ["Show the Eastern Conference standings for 2016-17."],
    "get_games": [
        "How many points did Kevin Love score in his last 3 games?",
        "Which 2018-19 games had the biggest margins?",
    ],
    "get_career": [
        "How many career assists does Chris Paul have?",
        "What are Dirk Nowitzki's career playoff averages?",
    ],
    "get_record": ["What is the record for most rebounds in a game?"],
    "get_trend": [
        "How has Devin Booker's 3-point percentage changed by season?",
        "How has league-wide pace changed since 2000?",
    ],
    "get_awards": [
        "Who won Defensive Player of the Year in 2019?",
        "How many All-Star selections does Dirk Nowitzki have?",
    ],
}


def tool_cards(reg: Registry | None = None) -> list[Chunk]:
    reg = reg or load()
    out = []
    for path in sorted(TOOL_SCHEMAS.glob("*.json")):
        schema = json.loads(path.read_text())
        name = path.stem
        lines = [f"Tool {name}: {schema.get('description', '')}", "Arguments:"]
        for arg, spec in schema["properties"].items():
            req = " (required)" if arg in schema.get("required", []) else ""
            enum = spec.get("enum") or spec.get("items", {}).get("enum")
            kind = (
                f"one of {len(enum)} values"
                if enum and len(enum) > 8
                else (f"one of {', '.join(map(str, enum))}" if enum else spec.get("type", ""))
            )
            desc = f" - {spec['description']}" if spec.get("description") else ""
            lines.append(f"- {arg}{req}: {kind}{desc}")
        lines.append("Example questions: " + " | ".join(TOOL_EXAMPLES.get(name, [])))
        out.append(Chunk(f"tool:{name}", "\n".join(lines), "tool_card"))
    return out


def schema_cards(
    con: duckdb.DuckDBPyConnection, reg: Registry | None = None, examples: int = 3
) -> list[Chunk]:
    reg = reg or load()
    metrics = {m.name: m for m in reg.metrics}
    views = [
        r[0]
        for r in con.execute(
            "select table_name from information_schema.tables where table_schema = 'semantic' "
            "order by 1"
        ).fetchall()
    ]
    out = []
    for v in views:
        cols = con.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = 'semantic' and table_name = ? order by ordinal_position",
            [v],
        ).fetchall()
        col_names = ", ".join(c for c, _ in cols)
        out.append(
            Chunk(
                f"view:semantic.{v}",
                f"View semantic.{v} ({len(cols)} columns): {col_names}",
                "schema_card",
            )
        )
        for col, dtype in cols:
            # Deterministic examples (sorted), so unchanged data gives unchanged cards and the
            # index re-embeds nothing (task 4.3).
            sample = con.execute(
                f'select distinct "{col}" from semantic."{v}" where "{col}" is not null '
                f"order by 1 limit {examples}"
            ).fetchall()
            ex = ", ".join(str(r[0])[:40] for r in sample)
            m = metrics.get(col)
            desc = f" {m.label}: {m.description} Formula: {m.formula}." if m else ""
            out.append(
                Chunk(
                    f"column:semantic.{v}.{col}",
                    f"Column {col} ({dtype}) of view semantic.{v}.{desc} Examples: {ex}",
                    "schema_card",
                )
            )
    return out
