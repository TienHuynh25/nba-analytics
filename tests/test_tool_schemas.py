from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.tools import schemas
from eval.schema import load
from metrics.schema import load as load_registry


def gold_calls() -> list[tuple[str, str, dict[str, object]]]:
    out: list[tuple[str, str, dict[str, object]]] = []
    for c in load().cases:
        golds = [c.gold] if c.gold else [t.gold for t in c.turns or []]
        for i, g in enumerate(golds):
            if g is not None and g.tool_call is not None:
                out.append((f"{c.id}.{i}", g.tool_call.tool, g.tool_call.args))
    return out


def test_committed_schemas_match_registry(tmp_path: Path) -> None:
    schemas.write(load_registry(), tmp_path)
    for p in tmp_path.glob("*.json"):
        assert (schemas.OUT / p.name).read_text() == p.read_text(), p.name


@pytest.mark.parametrize(("cid", "tool", "args"), gold_calls(), ids=lambda x: str(x)[:20])
def test_gold_call_validates(cid: str, tool: str, args: dict[str, object]) -> None:
    errors = list(Draft202012Validator(schemas.load_schema(tool)).iter_errors(args))
    assert not errors, f"{cid}: {[e.message for e in errors]}"


def test_every_stats_and_mixed_seed_has_a_gold_call() -> None:
    missing = [
        c.id
        for c in load().cases
        if c.type == "seed"
        and c.gold
        and c.gold.path.value in ("stats", "mixed")
        and c.gold.tool_call is None
    ]
    assert missing == []


def test_canonical_fills_defaults() -> None:
    a = schemas.canonical("get_leaders", {"metric": "points_per_game"})
    b = schemas.canonical(
        "get_leaders", {"metric": "points_per_game", "limit": 5, "qualified": True}
    )
    assert a == b
