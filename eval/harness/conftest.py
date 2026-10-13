"""pytest wiring for the eval harness (task 2.15). Run with ``make eval``.

Options: ``--split dev|heldout|all`` (default dev; cases not yet split count as dev until task
2.13 assigns splits), ``--answerer stub``, ``--accept`` (record this run as the accepted
baseline), ``--run-id`` (name the report; ``make gate2`` uses it). Before any case runs the
pinned snapshot is verified (eval.harness.snapshot_check); a missing or altered snapshot aborts the
run. The held-out split also needs ``HELDOUT_OK=1``: it runs only at plan gates, on the user's
approval. The session exits non-zero only when the regression rule fails against the last
accepted run.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.config import models
from eval.harness import report, snapshot_check
from eval.harness.report import CaseResult, RunMeta
from metrics.schema import load as load_registry

SNAPSHOTS = Path(__file__).resolve().parent.parent / "snapshots.yaml"
_results: list[CaseResult] = []
_meta: dict[str, RunMeta] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("eval")
    g.addoption("--split", default="dev", choices=["dev", "heldout", "all"])
    g.addoption("--answerer", default="stub")
    g.addoption("--accept", action="store_true", help="accept this run as the baseline")
    g.addoption("--run-id", default=None, help="report name (default <answerer>-<random>)")


def heldout_allowed(split: str, env: dict[str, str] | None = None) -> bool:
    """Held-out (alone or in ``all``) runs only with an explicit ``HELDOUT_OK=1``."""
    env = dict(os.environ) if env is None else env
    return split == "dev" or env.get("HELDOUT_OK") == "1"


def pytest_configure(config: pytest.Config) -> None:
    answerer = config.getoption("--answerer", default="stub")
    split = config.getoption("--split", default="dev")
    if not heldout_allowed(split):
        raise pytest.UsageError(
            f"--split {split} includes the held-out split, which runs only at plan gates on the "
            "user's approval. Set HELDOUT_OK=1 to confirm."
        )
    try:
        check = snapshot_check.check_for_run(answerer, registry=SNAPSHOTS)
    except snapshot_check.SnapshotCheckError as exc:
        raise pytest.UsageError(f"eval aborted, pinned snapshot not usable: {exc}") from exc
    _meta["run"] = RunMeta(
        run_id=config.getoption("--run-id", default=None) or f"{answerer}-{uuid.uuid4().hex[:8]}",
        snapshot_id=check.snapshot_id,
        manifest_sha256=check.manifest_sha256,
        db_sha256=check.db_sha256,
        snapshot_status=check.status,
        registry_version=load_registry().version,
        prompt_version="none" if answerer == "stub" else "router.v1",
        model="none" if answerer == "stub" else models().llm.model,
        index_version="none",
        git_sha=report.git_sha(),
        answerer=answerer,
        split=split,
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
