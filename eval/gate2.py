"""Gate 2 run (T-GATE2): ``make gate2``.

Runs the harness on the pinned snapshot (verified first, by the harness) and writes
``eval/reports/gate2-<git short sha>.md/.json``, diffed against the accepted run. The dev split
always runs. The held-out split runs only with ``HELDOUT_OK=1`` (plan gates, on the user's
approval). Without it the run prints ``GATE2 INCOMPLETE`` and exits 1, so a dev-only run can
never be read as a finished gate. Exit 0 means: held-out included, snapshot verified, and the
regression rule held.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from eval.harness.report import git_sha

ROOT = Path(__file__).resolve().parent.parent


def plan(env: dict[str, str]) -> str:
    """The split to run: ``all`` only when held-out is explicitly approved."""
    return "all" if env.get("HELDOUT_OK") == "1" else "dev"


def run_id() -> str:
    return f"gate2-{git_sha()[:8]}"


def command(split: str, answerer: str, rid: str) -> list[str]:
    return [
        sys.executable, "-m", "pytest", "eval/harness", "-p", "no:cacheprovider",
        "--split", split, "--answerer", answerer, "--run-id", rid,
    ]  # fmt: skip


def _run(cmd: list[str], env: dict[str, str]) -> int:
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def main(env: dict[str, str] | None = None) -> int:
    env = dict(os.environ) if env is None else env
    split = plan(env)
    rid = run_id()
    answerer = env.get("ANSWERER") or "stub"
    # The harness verifies the snapshot before running a case and aborts (non-zero) if it fails.
    code = _run(command(split, answerer, rid), env)
    if code != 0:
        print(f"GATE2 FAILED: harness exit {code} (snapshot check or regression rule)")
        return code
    if split != "all":
        print(
            "GATE2 INCOMPLETE: held-out not run, by policy. It runs only at the plan gate on "
            "the user's approval: make gate2 HELDOUT_OK=1."
        )
        return 1
    print(f"GATE2 COMPLETE: eval/reports/{rid}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
