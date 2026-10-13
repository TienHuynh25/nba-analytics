from collections import Counter
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from eval.schema import CASES_PATH, Case, CaseSet, Category, load

SPEC_MIX = {
    "Player season": 12,
    "Leaders": 10,
    "Comparison": 8,
    "Records": 12,
    "Team": 8,
    "Game": 8,
    "Trend": 6,
    "Definition": 8,
    "Shooting": 4,
    "Awards": 4,
    "Scope limits": 5,
}


def test_cases_validate() -> None:
    cs = load()
    assert cs.snapshot == "eval_2025_26_rs"


def test_seed_category_mix_matches_spec() -> None:
    seeds = [c for c in load().cases if c.type == "seed"]
    assert len(seeds) == 85
    assert dict(Counter(c.category.value for c in seeds)) == SPEC_MIX
    assert {c.value for c in Category} == set(SPEC_MIX)


def test_ambiguous_seeds_carry_their_rule() -> None:
    by_id = {c.id: c for c in load().cases}
    for q in ["Q13", "Q14", "Q15", "Q17", "Q19", "Q20", "Q22", "Q37", "Q48", "Q70", "Q79"]:
        gold = by_id[q].gold
        assert gold is not None and gold.rule, q


def test_critical_cases() -> None:
    crit = {c.id for c in load().cases if c.critical}
    assert {"Q81", "Q82", "Q83", "Q84", "Q85"} <= crit
    assert {f"Q{n}" for n in range(31, 43)} <= crit


def test_multi_turn_families_and_m10_clarify() -> None:
    by_id = {c.id: c for c in load().cases}
    assert by_id["M01"].seed_id == "Q13" and by_id["M05"].seed_id == "Q77"
    assert by_id["M02"].seed_id == "M02"
    m10 = by_id["M10"].turns
    assert m10 is not None and m10[2].gold.expect == "clarify"
    turns = sum(len(c.turns or []) for c in load().cases if c.type == "multi_turn")
    assert turns == 25


def test_date_dependent_cases_are_tagged() -> None:
    by_id = {c.id: c for c in load().cases}
    for q in ["Q01", "Q12", "Q51", "Q53", "Q55", "Q15", "Q73", "M08"]:
        assert "relative-time" in by_id[q].tags, q


def test_case_needs_question_or_turns() -> None:
    with pytest.raises(ValidationError):
        Case.model_validate(
            {"id": "Q99", "seed_id": "Q99", "type": "seed", "category": "Leaders", "source": "x"}
        )


def test_duplicate_ids_rejected() -> None:
    raw = yaml.safe_load(CASES_PATH.read_text())
    raw["cases"].append(raw["cases"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        CaseSet.model_validate(raw)


def test_definition_cases_name_existing_gold_chunks() -> None:
    from pathlib import Path

    glossary = {p.stem for p in (Path(__file__).parent.parent / "metrics/glossary").glob("*.md")}
    for c in load().cases:
        if c.gold is not None and c.gold.path.value in ("knowledge", "mixed"):
            assert c.gold.chunks, c.id
            assert set(c.gold.chunks) <= glossary, c.id


def test_split_by_family_without_leakage() -> None:
    cs = load().cases
    fam_splits: dict[str, set[str]] = {}
    for c in cs:
        assert c.split in ("dev", "heldout"), c.id
        fam_splits.setdefault(c.seed_id, set()).add(c.split)
    assert all(len(s) == 1 for s in fam_splits.values())
    weight = {"dev": 0, "heldout": 0}
    for c in cs:
        assert c.split is not None
        weight[c.split] += len(c.turns) if c.turns else 1
    assert weight["dev"] + weight["heldout"] == 320
    assert 85 <= weight["heldout"] <= 105  # about 96 (30%)
    by_id = {c.id: c for c in cs}
    assert by_id["M01"].split == by_id["Q13"].split and by_id["M05"].split == by_id["Q77"].split


def test_split_is_deterministic(tmp_path: object) -> None:
    import yaml

    from eval.split import assign

    raw = yaml.safe_load(CASES_PATH.read_text())["cases"]
    assert assign(raw) == assign(list(reversed(raw)))


# ---- gold values (task 2.6) ------------------------------------------------------------------


def _units() -> list[tuple[str, Case, Any]]:
    """(unit id, case, gold) for every single case and every turn."""
    out: list[tuple[str, Case, Any]] = []
    for c in load().cases:
        if c.turns:
            out += [(f"{c.id}.{i}", c, t.gold) for i, t in enumerate(c.turns, 1)]
        else:
            assert c.gold is not None
            out.append((c.id, c, c.gold))
    return out


def test_every_case_has_a_gold_value() -> None:
    units = _units()
    assert len(units) == 320
    kinds: Counter[str] = Counter()
    for uid, _c, g in units:
        assert isinstance(g.value, dict), uid
        kind = g.value["kind"]
        kinds[kind] += 1
        if g.expect.value == "decline":
            assert kind == "decline" and g.value["reason"], uid
        elif g.path.value == "knowledge":
            assert kind == "knowledge" and g.value["facts"], uid
        elif g.expect.value in ("clarify", "not_tracked", "no_verdict"):
            assert kind == g.expect.value, uid
        else:
            assert kind == "answer", uid
            assert g.sql and g.value["rows"], uid  # gold SQL ran and returned rows
    assert kinds == {
        "answer": 276,
        "knowledge": 18,
        "decline": 12,
        "not_tracked": 6,
        "clarify": 5,
        "no_verdict": 3,
    }


def test_answers_have_required_numbers_under_registry_rounding() -> None:
    from eval.harness.scorers import gold_numbers

    no_number = {"Q79", "M05.1"}  # name-only answers, scored by the judge
    for uid, _c, g in _units():
        if g.value.get("kind") != "answer":
            continue
        nums = gold_numbers(g).required  # raises KeyError on a non-registry metric
        assert nums or uid.split("-")[0] in no_number, uid
        assert all(n["value"] is not None for n in g.value["answer"]), uid


def test_not_tracked_values_are_null_not_zero() -> None:
    for uid, _c, g in _units():
        if g.value.get("kind") == "not_tracked":
            col = g.value["column"]
            assert g.value["rows"] and all(r[col] is None for r in g.value["rows"]), uid
            assert g.value["first_season_tracked"], uid


def test_inheriting_cases_share_their_seeds_gold() -> None:
    by_id = {c.id: c for c in load().cases}
    for c in load().cases:
        if c.type.value in ("paraphrase", "entity_variant"):
            seed = by_id[c.seed_id]
            assert c.gold is not None and seed.gold is not None
            if c.gold.tool_call == seed.gold.tool_call:
                assert c.gold.value == seed.gold.value, c.id
                assert c.gold.sql == seed.gold.sql, c.id


def test_gold_provenance_matches_the_pinned_snapshot() -> None:
    from metrics.schema import registry

    pin = yaml.safe_load((CASES_PATH.parent / "snapshots.yaml").read_text())["eval"]
    for uid, _c, g in _units():
        src = g.value.get("source")
        if src and "snapshot" in src:
            assert src["snapshot"] == pin["snapshot_id"], uid
            assert src["manifest_sha256"] == pin["manifest_sha256"], uid
            assert src["registry_version"] == registry().version, uid


def test_q48_family_names_the_warriors() -> None:
    # R-003: the team is an entity of the question, not only a tool argument.
    for c in load().cases:
        if c.seed_id == "Q48":
            assert c.gold is not None and c.gold.entities == {"teams": [1610612744]}, c.id


def test_split_unchanged_by_gold_work() -> None:
    from eval.split import assign

    raw = yaml.safe_load(CASES_PATH.read_text())["cases"]
    split = assign(raw)
    assert all(c["split"] == split[c["seed_id"]] for c in raw)
