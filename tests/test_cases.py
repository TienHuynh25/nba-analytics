from collections import Counter

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
