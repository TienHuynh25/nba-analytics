"""pytest wiring for the eval harness (task 2.15). Run with ``make eval``.

Options: ``--split dev|heldout|all`` (default dev; cases not yet split count as dev until task
2.13 assigns splits), ``--answerer stub``, ``--accept`` (record this run as the accepted
baseline). The session exits non-zero only when the regression rule fails against the last
accepted run.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.config import models
from eval.harness import report
from eval.harness.report import CaseResult, RunMeta

SNAPSHOTS = Path(__file__).resolve().parent.parent / "snapshots.yaml"
_results: list[CaseResult] = []
_meta: dict[str, RunMeta] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("eval")
    g.addoption("--split", default="dev", choices=["dev", "heldout", "all"])
    g.addoption("--answerer", default="stub")
    g.addoption("--accept", action="store_true", help="accept this run as the baseline")


def _snapshot_id() -> str:
    if SNAPSHOTS.exists():
        data = yaml.safe_load(SNAPSHOTS.read_text()) or {}
        if data.get("eval"):
            return str(data["eval"]["snapshot_id"])
    return "eval_2025_26_rs (not built yet)"


def pytest_configure(config: pytest.Config) -> None:
    answerer = config.getoption("--answerer", default="stub")
    _meta["run"] = RunMeta(
        run_id=f"{answerer}-{uuid.uuid4().hex[:8]}",
        snapshot_id=_snapshot_id(),
        prompt_version="none" if answerer == "stub" else "router.v1",
        model="none" if answerer == "stub" else models().llm.model,
        index_version="none",
        git_sha=report.git_sha(),
        answerer=answerer,
        split=config.getoption("--split", default="dev"),
    )


@pytest.fixture(scope="session")
def run_meta() -> RunMeta:
    return _meta["run"]


@pytest.fixture(scope="session")
def results() -> list[CaseResult]:
    return _results


def pytest_sessionfinish(session: pytest.Session, exitstatus: Any) -> None:
    if not _results:
        return
    path, verdict = report.write(_meta["run"], _results)
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"eval report: {path.with_suffix('.md')}")
    if session.config.getoption("--accept"):
        report.accept(path)
        if reporter is not None:
            reporter.write_line(f"accepted as baseline: {path.name}")
    elif verdict is not None and not verdict.ok:
        session.exitstatus = 1
