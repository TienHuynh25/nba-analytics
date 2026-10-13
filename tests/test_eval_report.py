"""Eval report, accept flow and stub answerer (test plan layer L7, invariant I10).

Reports go to a temp directory; nothing here runs the real pipeline or reads eval cases.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from eval.harness import report
from eval.harness.answerer import StubAnswerer, eval_db
from eval.harness.report import CaseResult, RunMeta


@pytest.fixture()
def reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(report, "REPORTS", tmp_path)
    monkeypatch.setattr(report, "ACCEPTED", tmp_path / "accepted.json")
    return tmp_path


def meta(run_id: str = "r1", split: str = "dev") -> RunMeta:
    return RunMeta(
        run_id=run_id,
        snapshot_id="eval_2025_26_rs",
        prompt_version="router.v1",
        model="qwen-test",
        index_version="idx-7",
        git_sha="a" * 40,
        answerer="stats",
        split=split,
    )


def case(cid: str, ok: bool, *, family: str | None = None, critical: bool = False,
         split: str = "dev", unverified: int = 0) -> CaseResult:  # fmt: skip
    return CaseResult(
        cid,
        family or cid,
        split,
        critical,
        [],
        {"answer": {"applicable": True, "passed": ok, "detail": "" if ok else "wrong number"}},
        unverified,
    )


def test_every_run_records_the_five_versions(reports: Path) -> None:
    path, verdict = report.write(meta(), [case("a", True)])
    data = json.loads(path.read_text())["meta"]
    for k in ("snapshot_id", "prompt_version", "model", "index_version", "git_sha"):
        assert data[k]
    md = path.with_suffix(".md").read_text()
    assert "eval_2025_26_rs" in md and "router.v1" in md and "qwen-test" in md
    assert "idx-7" in md and "a" * 12 in md
    assert verdict is None and "No accepted run yet" in md


def test_gold_path_routing_is_disclosed_in_the_report(reports: Path) -> None:
    path, _ = report.write(meta(), [case("a", True)])
    assert "gold path" in path.with_suffix(".md").read_text()


def test_accept_then_regression_is_judged_against_it(reports: Path) -> None:
    base = [case(f"c{i}", True) for i in range(12)]
    p1, _ = report.write(meta("base"), base)
    report.accept(p1)
    assert report.accepted_run() == p1
    # Same results: passes the rule.
    p2, v2 = report.write(meta("same"), base)
    assert v2 is not None and v2.ok
    assert "**PASS**" in p2.with_suffix(".md").read_text()
    # One critical case flips: fails even though accuracy barely moves.
    worse = [case("c0", False, critical=True), *base[1:]]
    # a critical flag on the baseline copy of c0 is what makes it critical in the comparison
    p0, _ = report.write(meta("base2"), [case("c0", True, critical=True), *base[1:]])
    report.accept(p0)
    p3, v3 = report.write(meta("worse"), worse)
    assert v3 is not None and not v3.ok and v3.pass_to_fail == ["c0"]
    md = p3.with_suffix(".md").read_text()
    assert "**FAIL**" in md and "c0" in md and "critical" in md


def test_any_unverified_number_fails_the_rule_even_if_accuracy_is_unchanged(reports: Path) -> None:
    base = [case(f"c{i}", True) for i in range(6)]
    p1, _ = report.write(meta("base"), base)
    report.accept(p1)
    bad = [case("c0", True, unverified=1), *base[1:]]
    _, v = report.write(meta("bad"), bad)
    assert v is not None and not v.ok and v.unverified_numbers == 1


def test_markdown_lists_failures_and_family_bootstrap(reports: Path) -> None:
    rs = [case("a1", True, family="a"), case("a2", False, family="a"), case("b1", True, family="b")]
    path, _ = report.write(meta(), rs)
    md = path.with_suffix(".md").read_text()
    assert "| a2 | answer | wrong number |" in md
    assert re.search(r"dev: 66\.7% \(3 items, 3 turn-units; family bootstrap 95% CI", md)
    assert "unverified numbers shown: 0" in md


def test_dev_vs_heldout_gap_needs_both_splits(reports: Path) -> None:
    only_dev = report.markdown(meta(), [case("a", True)], None, None)
    assert "- held-out: not run" in only_dev
    assert "- dev - held-out: not run (needs both splits)" in only_dev
    both = report.markdown(meta(), [case("a", True), case("b", False, split="heldout")], None, None)
    assert "dev - held-out: 95% CI" in both and "not run" not in both


def test_round_trip_outcomes(reports: Path) -> None:
    rs = [case("a", True, critical=True), case("b", False, unverified=2)]
    path, _ = report.write(meta(), rs)
    out = report.load_outcomes(path)
    assert out["a"].passed and out["a"].critical
    assert not out["b"].passed and out["b"].unverified_numbers == 2
    assert report.load_outcomes(None) == {}


def test_accepted_pointer_to_a_missing_run_is_ignored(reports: Path) -> None:
    (reports / "accepted.json").write_text(json.dumps({"run": "gone.json"}))
    assert report.accepted_run() is None


def test_git_sha_is_a_sha_or_unknown() -> None:
    assert re.fullmatch(r"[0-9a-f]{40}(\+dirty)?|unknown", report.git_sha())


def _repo(tmp_path: Path) -> Path:
    def g(*a: str) -> None:
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    g("config", "commit.gpgsign", "false")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    g("add", ".")
    g("commit", "-qm", "init")
    return tmp_path


def test_git_sha_clean_tree_has_no_flag(tmp_path: Path) -> None:
    assert re.fullmatch(r"[0-9a-f]{40}", report.git_sha(_repo(tmp_path)))


def test_git_sha_flags_a_modified_tracked_file(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "a.py").write_text("x = 2\n")
    assert re.fullmatch(r"[0-9a-f]{40}\+dirty", report.git_sha(root))


def test_git_sha_flags_an_untracked_file(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "new.py").write_text("y = 1\n")
    assert report.git_sha(root).endswith("+dirty")


def test_git_sha_ignores_reports_dir_and_gitignored_files(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "eval" / "reports").mkdir(parents=True)
    (root / "eval" / "reports" / "run.json").write_text("{}")
    (root / "ignored.txt").write_text("z")
    assert not report.git_sha(root).endswith("+dirty")


def test_short_sha_keeps_the_dirty_flag() -> None:
    assert report.short_sha("a" * 40 + "+dirty") == "a" * 12 + "+dirty"
    assert report.short_sha("a" * 40) == "a" * 12


def test_stub_answerer_answers_nothing_but_keeps_the_gold_path() -> None:
    rec = StubAnswerer().answer("Who led the league in scoring?", gold_path="stats")
    assert rec.path == "stats" and rec.text == "I don't know yet."
    assert rec.unverified_numbers == 0 and (rec.latency_ms or 0) >= 0


def test_eval_db_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NBA_EVAL_DB", str(tmp_path / "x.duckdb"))
    assert eval_db() == tmp_path / "x.duckdb"


def test_header_carries_snapshot_hashes_and_status(reports: Path) -> None:
    m = meta()
    m.manifest_sha256, m.db_sha256 = "m" * 64, "d" * 64
    m.snapshot_status, m.registry_version = "VERIFIED", "0.4.0"
    md = report.markdown(m, [case("a", True)], None, None)
    assert "**VERIFIED**" in md and "m" * 64 in md and "d" * 64 in md and "0.4.0" in md
    assert "**NOT VERIFIED**" in report.markdown(meta(), [case("a", True)], None, None)


def test_turn_units_are_counted_apart_from_items(reports: Path) -> None:
    conv = case("m1", True)
    conv.units = 3
    md = report.markdown(meta(), [conv, case("b", True)], None, None)
    assert "(2 items, 4 turn-units;" in md
