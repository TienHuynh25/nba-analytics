"""Assign the dev / held-out split by seed family (task 2.13, gap G5).

Usage: ``uv run python -m eval.split`` rewrites the ``split`` field of every case.

A family is a seed with its paraphrases and entity variants, plus any multi-turn conversation
whose turn 1 repeats the seed (M01 -> Q13, M05 -> Q77). Every other conversation and every hard
negative is its own family. Within each category, families are ordered by a fixed hash and
assigned to held-out while that brings the category closer to 30% of its cases (a multi-turn
case counts as its number of turns). No family spans both splits. The result is deterministic.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

import yaml

from eval.schema import CASES_PATH, load

HELDOUT_SHARE = 0.30
SALT = "testset-v1"


def weight(case: dict[str, object]) -> int:
    turns = case.get("turns")
    return len(turns) if isinstance(turns, list) else 1


def assign(cases: list[dict[str, object]]) -> dict[str, str]:
    """family id -> split"""
    fam_weight: dict[str, int] = defaultdict(int)
    fam_cat: dict[str, str] = {}
    for c in cases:
        fam = str(c["seed_id"])
        fam_weight[fam] += weight(c)
        # The family's category is its seed's (or own, for standalone families).
        if c["type"] in ("seed", "multi_turn", "hard_negative") and fam not in fam_cat:
            fam_cat[fam] = str(c["category"])
    by_cat: dict[str, list[str]] = defaultdict(list)
    for fam, cat in fam_cat.items():
        by_cat[cat].append(fam)
    out: dict[str, str] = {}
    for _cat, fams in sorted(by_cat.items()):
        fams.sort(key=lambda f: hashlib.sha256(f"{SALT}:{f}".encode()).hexdigest())
        target = HELDOUT_SHARE * sum(fam_weight[f] for f in fams)
        held = 0
        for f in fams:
            # Take the family if that brings the category closer to its 30% target.
            if abs(held + fam_weight[f] - target) < abs(held - target):
                out[f] = "heldout"
                held += fam_weight[f]
            else:
                out[f] = "dev"
    return out


def main(path: Path = CASES_PATH) -> None:
    text = path.read_text()
    header = "".join(ln for ln in text.splitlines(keepends=True) if ln.startswith("#"))
    doc = yaml.safe_load(text)
    split = assign(doc["cases"])
    for c in doc["cases"]:
        c["split"] = split[str(c["seed_id"])]
    path.write_text(header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))
    load(path)  # validate
    n = {s: sum(weight(c) for c in doc["cases"] if c["split"] == s) for s in ("dev", "heldout")}
    print(f"dev {n['dev']} cases, held-out {n['heldout']} cases")


if __name__ == "__main__":
    main()
