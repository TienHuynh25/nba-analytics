"""Run metadata, results files and the diff report (tasks 2.17, 2.18).

Each run writes ``eval/reports/<run_id>.json`` (every case's stage scores) and
``eval/reports/<run_id>.md``. The header records the five versions every run must carry:
snapshot ID, prompt version, model, index version and git SHA. The diff is against the last
accepted run named in ``eval/reports/accepted.json``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.harness.regression import (
    CaseOutcome,
    Verdict,
    accuracy,
    compare,
    difference_bootstrap,
    family_bootstrap,
)

REPORTS = Path(__file__).resolve().parent.parent / "reports"
ACCEPTED = REPORTS / "accepted.json"


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


@dataclass
class RunMeta:
    run_id: str
    snapshot_id: str
    prompt_version: str
    model: str
    index_version: str
    git_sha: str
    answerer: str
    split: str
    routing: str = "gold-path"  # gold-path until the router exists (G11), then "router"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CaseResult:
    case_id: str
    family: str
    split: str | None
    critical: bool
    tags: list[str]
    stages: dict[str, dict[str, Any]]  # stage -> {applicable, passed, detail}
    unverified_numbers: int = 0

    @property
    def passed(self) -> bool:
        return bool(self.stages.get("answer", {}).get("passed"))

    def outcome(self) -> CaseOutcome:
        return CaseOutcome(
            self.case_id, self.family, self.passed, self.critical, self.unverified_numbers
        )


def write(meta: RunMeta, results: list[CaseResult]) -> tuple[Path, Verdict | None]:
    REPORTS.mkdir(exist_ok=True)
    data = {"meta": asdict(meta), "results": [asdict(r) for r in results]}
    jpath = REPORTS / f"{meta.run_id}.json"
    jpath.write_text(json.dumps(data, indent=1) + "\n")
    accepted = load_outcomes(accepted_run()) if accepted_run() else None
    verdict = compare(accepted, {r.case_id: r.outcome() for r in results}) if accepted else None
    (REPORTS / f"{meta.run_id}.md").write_text(markdown(meta, results, verdict, accepted))
    return jpath, verdict


def accepted_run() -> Path | None:
    if not ACCEPTED.exists():
        return None
    p = REPORTS / json.loads(ACCEPTED.read_text())["run"]
    return p if p.exists() else None


def accept(run_json: Path) -> None:
    ACCEPTED.write_text(json.dumps({"run": run_json.name}) + "\n")


def load_outcomes(path: Path | None) -> dict[str, CaseOutcome]:
    if path is None:
        return {}
    data = json.loads(path.read_text())
    out = {}
    for r in data["results"]:
        cr = CaseResult(**r)
        out[cr.case_id] = cr.outcome()
    return out


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def markdown(
    meta: RunMeta,
    results: list[CaseResult],
    verdict: Verdict | None,
    accepted: dict[str, CaseOutcome] | None,
) -> str:
    lines = [
        f"# Eval run {meta.run_id}",
        "",
        "| Snapshot | Prompt version | Model | Index version | Git SHA | Answerer | Split |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| {meta.snapshot_id} | {meta.prompt_version} | {meta.model} | {meta.index_version} "
        f"| {meta.git_sha[:12]} | {meta.answerer} | {meta.split} |",
        "",
        *(
            ["Routing uses each case's gold path (G11), so the router stage is not measured."]
            if meta.routing == "gold-path"
            else []
        ),
        "",
        "## Stage scores",
        "",
        "| Stage | Passed | Applicable | Rate |",
        "| --- | --- | --- | --- |",
    ]
    stages = sorted({s for r in results for s in r.stages})
    for s in stages:
        app = [r for r in results if r.stages.get(s, {}).get("applicable")]
        ok = [r for r in app if r.stages[s]["passed"]]
        rate = _pct(len(ok) / len(app)) if app else "n/a"
        lines.append(f"| {s} | {len(ok)} | {len(app)} | {rate} |")
    outs = [r.outcome() for r in results]
    lines += ["", "## Accuracy (end to end)", ""]
    for split in ("dev", "heldout", None):
        sub = [r.outcome() for r in results if r.split == split]
        if not sub:
            continue
        lo, hi = family_bootstrap(sub)
        name = split or "unsplit"
        lines.append(
            f"- {name}: {_pct(accuracy(sub))} ({len(sub)} cases; "
            f"family bootstrap 95% CI {_pct(lo)} to {_pct(hi)})"
        )
    dev = [r.outcome() for r in results if r.split == "dev"]
    held = [r.outcome() for r in results if r.split == "heldout"]
    if dev and held:
        lo, hi = difference_bootstrap(dev, held)
        lines.append(f"- dev - held-out: 95% CI {100 * lo:+.1f} to {100 * hi:+.1f} points")
    lines.append(f"- unverified numbers shown: {sum(o.unverified_numbers for o in outs)}")
    lines += ["", "## Against the last accepted run", ""]
    if verdict is None:
        lines.append("No accepted run yet.")
    else:
        lines.append(
            f"**{'PASS' if verdict.ok else 'FAIL'}** regression rule "
            f"(McNemar one-sided p = {verdict.p_value:.4f})."
        )
        lines += [f"- {r}" for r in verdict.reasons]
        lines.append(
            f"- pass -> fail ({len(verdict.pass_to_fail)}): "
            f"{', '.join(verdict.pass_to_fail) or 'none'}"
        )
        lines.append(
            f"- fail -> pass ({len(verdict.fail_to_pass)}): "
            f"{', '.join(verdict.fail_to_pass) or 'none'}"
        )
    lines += ["", "## Failures", "", "| Case | Stage | Detail |", "| --- | --- | --- |"]
    for r in results:
        for s, sc in r.stages.items():
            if sc.get("applicable") and not sc.get("passed"):
                lines.append(f"| {r.case_id} | {s} | {str(sc.get('detail', ''))[:120]} |")
    return "\n".join(lines) + "\n"
