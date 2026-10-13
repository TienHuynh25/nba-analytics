"""T-GATE2: ``make gate2`` plan, and the committed gate2 report matches cases.yaml (CI-safe)."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from eval import gate2
from eval.harness.report import REPORTS
from eval.harness.snapshot_check import pinned_entry
from eval.schema import load


def test_gate2_plans_dev_only_unless_heldout_is_explicit() -> None:
    assert gate2.plan({}) == "dev"
    assert gate2.plan({"HELDOUT_OK": ""}) == "dev"
    assert gate2.plan({"HELDOUT_OK": "true"}) == "dev"
    assert gate2.plan({"HELDOUT_OK": "1"}) == "all"


@pytest.fixture(autouse=True)
def _fixed_run_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate2, "run_id", lambda: "gate2-test")


def test_gate2_dev_only_run_is_flagged_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[list[str]] = []

    def fake(cmd: list[str], env: dict[str, str]) -> int:
        seen.append(cmd)
        return 0

    monkeypatch.setattr(gate2, "_run", fake)
    assert gate2.main({}) == 1
    assert "GATE2 INCOMPLETE" in capsys.readouterr().out
    assert seen[0][seen[0].index("--split") + 1] == "dev"


def test_gate2_propagates_a_harness_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate2, "_run", lambda cmd, env: 4)
    assert gate2.main({"HELDOUT_OK": "1"}) == 4


def test_gate2_complete_only_with_heldout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate2, "_run", lambda cmd, env: 0)
    assert gate2.main({"HELDOUT_OK": "1"}) == 0


def _committed() -> list[Path]:
    return sorted(REPORTS.glob("gate2-*.json"))


def check_gate2_report(path: Path, want_ids: set[str], pinned: dict[str, Any]) -> list[str]:
    """Problems that stop a committed gate2 report from being the Gate 2 deliverable (DEF-030)."""
    data = json.loads(path.read_text())
    meta = data["meta"]
    bad: list[str] = []
    if meta.get("split") != "all":
        bad.append(f"split is {meta.get('split')!r}, not 'all' (held-out did not run)")
    got = [r["case_id"] for r in data["results"]]
    if len(got) != len(set(got)):
        bad.append("duplicate case ids")
    if set(got) != want_ids:
        bad.append(
            f"case ids differ from cases.yaml (missing {len(want_ids - set(got))}, "
            f"extra {len(set(got) - want_ids)})"
        )
    if meta.get("snapshot_status") != "VERIFIED":
        bad.append(f"snapshot status is {meta.get('snapshot_status')!r}")
    for key in ("manifest_sha256", "db_sha256"):
        if meta.get(key) != pinned[key]:
            bad.append(f"{key} does not match eval/snapshots.yaml")
    if "dirty" in str(meta.get("git_sha", "")) or not meta.get("git_sha"):
        bad.append(f"git sha {meta.get('git_sha')!r} is not clean")
    if not path.with_suffix(".md").exists():
        bad.append("no .md report beside the json")
    return bad


@pytest.mark.skipif(not _committed(), reason="no gate2 report committed yet")
@pytest.mark.parametrize("path", _committed(), ids=lambda p: p.name)
def test_committed_gate2_report_is_the_complete_verified_run(path: Path) -> None:
    ids = {c.id for c in load().cases}
    assert check_gate2_report(path, ids, pinned_entry()) == []


# --- the checker itself, on tmp reports (no real gate2 report is created) --------------------

PINNED = {"manifest_sha256": "m" * 64, "db_sha256": "d" * 64}
IDS = {"a", "b", "c"}


def _report(tmp_path: Path, ids: Sequence[str] = tuple(sorted(IDS)), **meta: Any) -> Path:
    base: dict[str, Any] = {
        "split": "all", "snapshot_status": "VERIFIED", "git_sha": "da58e845" + "0" * 32,
        **PINNED,
    }  # fmt: skip
    base.update(meta)
    p = tmp_path / "gate2-x.json"
    p.write_text(json.dumps({"meta": base, "results": [{"case_id": i} for i in ids]}))
    p.with_suffix(".md").write_text("r")
    return p


def test_correct_gate2_report_passes(tmp_path: Path) -> None:
    assert check_gate2_report(_report(tmp_path), IDS, PINNED) == []


@pytest.mark.parametrize(
    ("kw", "needle"),
    [
        ({"split": "dev"}, "not 'all'"),
        ({"ids": ["a", "b"]}, "missing 1"),
        ({"ids": ["a", "b", "c", "d"]}, "extra 1"),
        ({"snapshot_status": "NOT VERIFIED"}, "snapshot status"),
        ({"git_sha": "da58e845+dirty"}, "not clean"),
        ({"db_sha256": "x"}, "db_sha256"),
        ({"manifest_sha256": "x"}, "manifest_sha256"),
    ],
)
def test_incomplete_gate2_report_fails(tmp_path: Path, kw: dict[str, Any], needle: str) -> None:
    ids = kw.pop("ids", sorted(IDS))
    problems = check_gate2_report(_report(tmp_path, ids, **kw), IDS, PINNED)
    assert any(needle in p for p in problems), problems


def test_dev_only_report_with_all_dev_ids_fails(tmp_path: Path) -> None:
    """DEF-030: split 'dev' covering every dev id used to pass."""
    assert check_gate2_report(_report(tmp_path, ["a", "b"], split="dev"), {"a", "b"}, PINNED)
