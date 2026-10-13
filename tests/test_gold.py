"""Gold values (task 2.6): the gold.sql parser, sync with cases.yaml, and reproduction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.tools.schemas import STAT_LINE
from eval.gold import compute_gold as cg
from eval.schema import CASES_PATH, load

ROOT = Path(__file__).resolve().parents[1]


def test_parse_blocks_reads_directives() -> None:
    text = """-- header comment, ignored
-- @Q01
-- A comment line.
-- key: player_name, season
-- numbers: points_per_game, home_pts=game_points
-- totals: n=games_played
-- required-rows: compared
-- null: threes_made
-- ordered: true
-- ties: every row tied at the cut
--   is included
SELECT 1 AS x
FROM t;

-- ===== section =====

-- @M01.2
-- numbers: @stat_line
SELECT 2;
"""
    b = cg.parse_blocks(text)
    q = b["Q01"]
    assert q.sql == "SELECT 1 AS x\nFROM t" and q.line == 2
    assert q.key == ["player_name", "season"]
    assert q.numbers == [("points_per_game", "points_per_game"), ("home_pts", "game_points")]
    assert q.totals == [("n", "games_played")] and q.required_rows == "compared"
    assert q.nulls == ["threes_made"] and q.ordered
    assert q.ties == "every row tied at the cut is included"
    assert q.comment == ["A comment line."]
    assert [m for m, _ in b["M01.2"].numbers] == STAT_LINE and b["M01.2"].sql == "SELECT 2"


@pytest.mark.parametrize(
    "text",
    [
        "-- @Q01\nSELECT 1\n",
        "-- @Q01\nSELECT 1; SELECT 2;\n",
        "-- @Q01\nSELECT 1;\n-- @Q01\nSELECT 1;\n",
    ],
)
def test_parse_blocks_rejects_bad_blocks(text: str) -> None:
    with pytest.raises(ValueError):
        cg.parse_blocks(text)


def test_answer_numbers_tags_registry_metrics() -> None:
    from metrics.schema import registry

    b = cg.Block("Q99", "", 1, key=["player_name"], numbers=[("pts", "game_points")])
    b.totals = [("n", "games")]  # an alias resolves to the metric name
    rows: list[dict[str, Any]] = [
        {"player_name": "A", "pts": 30, "n": 2},
        {"player_name": "B", "pts": None, "n": 2},
    ]
    got = cg.answer_numbers(b, rows, registry())
    assert got == [
        {"metric": "games_played", "value": 2, "column": "n"},
        {"metric": "game_points", "value": 30, "column": "pts", "key": "A"},
    ]  # B's NULL is not a number to state
    with pytest.raises(ValueError):
        cg.answer_numbers(b, [{"player_name": "A", "pts": "x", "n": 2}], registry())


def test_gold_sql_in_cases_matches_gold_sql_file() -> None:
    blocks = cg.parse_blocks(cg.SQL_PATH.read_text())
    raw = yaml.safe_load(CASES_PATH.read_text())["cases"]
    sqls = set()
    for c in raw:
        golds = [t["gold"] for t in c["turns"]] if c.get("turns") else [c["gold"]]
        sqls |= {g["sql"] for g in golds if g.get("sql")}
    assert sqls == {b.sql for b in blocks.values()}


def test_knowledge_facts_are_glossary_text() -> None:
    for chunk, facts in cg.FACTS.items():
        body = " ".join((ROOT / "metrics/glossary" / f"{chunk}.md").read_text().split())
        for f in facts:
            assert " ".join(f.split()) in body, (chunk, f)


def test_gold_sql_reads_only_semantic_views() -> None:
    for b in cg.parse_blocks(cg.SQL_PATH.read_text()).values():
        tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+)", b.sql)
        assert tables and all(t.startswith("semantic.") for t in tables), b.id


def test_registry_constants_match_gold_sql() -> None:
    from metrics.schema import registry

    reg = registry()
    for (qual, attr), want in cg.SQL_CONSTANTS.items():
        rule = reg.qualification(qual).rule_for(cg.QUAL_SEASON.get(qual, "2025-26"))
        assert getattr(rule, attr) == want, (qual, attr)


def _snapshot_present() -> bool:
    pin = yaml.safe_load((ROOT / "eval/snapshots.yaml").read_text())["eval"]
    return bool((ROOT / str(pin["db"])).exists())


@pytest.mark.skipif(
    not _snapshot_present(),
    reason="pinned snapshot eval_2025_26_rs not built here (data/snapshots is git-ignored; CI)",
)
def test_compute_gold_reproduces_stored_gold() -> None:
    prov = cg.provenance()
    res = cg.compute(prov)
    assert cg.render_cases(res) == CASES_PATH.read_text()
    assert cg.render_report(res, prov) == (cg.GOLD_DIR / cg.REPORT_NAME).read_text()
    assert len(load().cases) == len(res.doc["cases"])


def test_allowed_numbers_are_context_from_every_row_minus_required() -> None:
    from metrics.schema import registry

    b = cg.Block("Q62", "", 1, key=["season"], numbers=[("v", "league_points_per_game")])
    b.required_rows = "compared"
    rows: list[dict[str, Any]] = [
        {"season": "1990-91", "v": 106.3, "compared": True},
        {"season": "2000-01", "v": 94.8, "compared": False},
        {"season": "2001-02", "v": None, "compared": False},
    ]
    reg = registry()
    required = cg.answer_numbers(b, rows, reg)
    spec = {"Q62": "v=league_points_per_game"}
    orig = cg.ALLOWED
    try:
        cg.ALLOWED = spec
        got = cg.allowed_numbers(b, rows, reg, required)
        assert got == [
            {"metric": "league_points_per_game", "value": 94.8, "column": "v", "key": "2000-01"}
        ]  # the required 1990-91 value is not repeated; NULL is skipped
        cg.ALLOWED = {"Q62": "missing_col"}
        with pytest.raises(ValueError):
            cg.allowed_numbers(b, rows, reg, required)
        cg.ALLOWED = {"Q62": "season=wins"}
        with pytest.raises(ValueError):
            cg.allowed_numbers(b, rows, reg, required)  # not numeric
    finally:
        cg.ALLOWED = orig
    assert cg.allowed_numbers(cg.Block("Q01", "", 1), rows, reg, []) == []


def test_allowed_annotations_in_cases_match_compute_gold() -> None:
    from eval.harness.scorers import gold_numbers

    raw = yaml.safe_load(CASES_PATH.read_text())["cases"]
    blocks_with_allowed = set()
    for c in raw:
        golds = (
            [(f"{c['id']}.{i}", t["gold"]) for i, t in enumerate(c["turns"], 1)]
            if c.get("turns")
            else [(c["id"], c["gold"])]
        )
        for uid, g in golds:
            v = g.get("value") or {}
            if "allowed" not in v:
                continue
            blocks_with_allowed.add(v["source"]["block"])
            assert not [a for a in v["allowed"] if a in v["answer"]], uid  # never also required
    assert blocks_with_allowed == set(cg.ALLOWED)
    for c in load().cases:
        for g in [c.gold] if c.gold else [t.gold for t in c.turns or []]:
            gold_numbers(g)  # every allowed metric is a registry metric (KeyError otherwise)


# ---- display check (DEF-022) -------------------------------------------------------------------


def test_display_check_rejects_a_stored_value_that_shows_differently() -> None:
    from metrics.schema import registry

    reg = registry()
    b = cg.Block("Q99", "", 1, key=["p"], numbers=[("ppg", "points_per_game")])
    stored = [{"p": "A", "ppg": 25.05}]
    with pytest.raises(cg.DisplayMismatch, match=r"Q99-x row 0 ppg"):
        cg.answer_numbers(b, stored, reg, [{"p": "A", "ppg": 25.0499}], "Q99-x")
    assert cg.answer_numbers(b, stored, reg, [{"p": "A", "ppg": 25.0500004}], "Q99-x")
    pct = cg.Block("Q98", "", 1, totals=[("fg", "field_goal_pct")])
    with pytest.raises(cg.DisplayMismatch):  # percent display: 47.65% vs 47.64%
        cg.answer_numbers(pct, [{"fg": 0.4765}], reg, [{"fg": 0.47649}], "Q98")


def test_display_check_covers_allowed_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    from metrics.schema import registry

    monkeypatch.setitem(cg.ALLOWED, "Q97", "ppg=points_per_game")
    b = cg.Block("Q97", "", 1, key=["p"])
    with pytest.raises(cg.DisplayMismatch, match="Q97"):
        cg.allowed_numbers(b, [{"p": "A", "ppg": 25.05}], registry(), [], [{"p": "A", "ppg": 25.0}])


@pytest.mark.skipif(not _snapshot_present(), reason="pinned snapshot not built here (CI)")
def test_display_check_runs_on_every_real_gold_number(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = cg._check_display

    def spy(raw: Any, stored: Any, metric: str, reg: Any, where: str = "") -> None:
        calls.append(where)
        real(raw, stored, metric, reg, where)

    monkeypatch.setattr(cg, "_check_display", spy)
    res = cg.compute(cg.provenance())  # passes: no real gold value displays differently
    seen: set[int] = set()
    n = 0
    for c in res.doc["cases"]:
        for g in [t["gold"] for t in c["turns"]] if c.get("turns") else [c["gold"]]:
            v = g["value"]
            if id(v) not in seen:
                seen.add(id(v))
                n += len(v.get("answer", [])) + len(v.get("allowed", []))
    assert n > 0 and len(calls) >= n


@pytest.mark.skipif(not _snapshot_present(), reason="pinned snapshot not built here (CI)")
def test_compute_gold_fails_loudly_on_a_display_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cg, "FLOAT_DECIMALS", 0)  # stored values would show as integers
    with pytest.raises(cg.DisplayMismatch, match=r"^Q\d{2}"):
        cg.compute(cg.provenance())
    assert cg.main(["--check"]) == 2


# ---- clarify candidate sets (DEF-024, D-027) ---------------------------------------------------


def _clarify_units() -> list[tuple[str, str | None, Any, Any]]:
    out: list[tuple[str, str | None, Any, Any]] = []
    for c in load().cases:
        pairs = [(t.question, t.gold) for t in c.turns] if c.turns else [(c.question, c.gold)]
        for i, (q, g) in enumerate(pairs, 1):
            if g is not None and g.expect.value == "clarify":
                out.append((f"{c.id}.{i}" if c.turns else c.id, q, g, c))
    return out


def test_h03_lists_every_antetokounmpo_including_kostas() -> None:
    (h03,) = [g for uid, _q, g, _c in _clarify_units() if uid == "H03"]
    ids = {r["player_id"] for r in h03.value["candidates"]}
    assert ids == {203507, 203648, 1628961, 1630828}  # Giannis, Thanasis, Kostas, Alex
    assert sorted(h03.entities["players"]) == sorted(ids)


def test_clarify_gold_has_entities_equal_to_candidates() -> None:
    units = _clarify_units()
    assert [u for u, *_ in units] == ["M10.3", "H01", "H02", "H03", "H04"]
    for uid, _q, g, _c in units:
        assert g.entities == {"players": [r["player_id"] for r in g.value["candidates"]]}, uid


@pytest.mark.skipif(not _snapshot_present(), reason="pinned snapshot not built here (CI)")
def test_clarify_candidates_equal_the_entity_resolvers_set() -> None:
    from app.entities import EntityResolver
    from app.snapshot import connect_read_only

    prov = cg.provenance()
    resolver = EntityResolver(connect_read_only(prov.db, prov.shots))
    for uid, q, g, case in _clarify_units():
        gold = {r["player_id"] for r in g.value["candidates"]}
        if uid == "M10.3":  # "he": the two players of turn 2, not a name lookup
            assert case.turns is not None
            assert gold == set(case.turns[1].gold.entities["players"]), uid
            continue
        assert q is not None
        res = resolver.resolve(q)
        assert len(res.ambiguous) == 1 and not res.players, uid
        assert gold == {e.id for e in res.ambiguous[0].candidates}, uid
