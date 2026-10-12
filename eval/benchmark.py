"""Model benchmark on the dev split (task 3.17, preliminary part).

Usage: ``NBA_EVAL_DB=... uv run python -m eval.benchmark qwen3.5:9b gemma4:e4b``

For each model: every dev-split case with a gold tool call, on the stats path (G11 routing),
one run each. Scores tool-call accuracy (canonical comparison) and latency, and counts answer
statuses. Writes ``eval/reports/benchmark-preliminary.md``. This is NOT the Gate 3 benchmark:
that needs the pinned eval snapshot and gold values (after the backfill).
"""

from __future__ import annotations

import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime

from app.config import models
from app.interfaces import make_llm
from app.stats_path import PROMPT_VERSION, StatsPath
from app.tools.schemas import canonical
from eval.harness.answerer import StatsAnswerer
from eval.harness.report import REPORTS, git_sha
from eval.latency import pct
from eval.schema import load


def cases() -> list[tuple[str, str, str, dict[str, object]]]:
    out: list[tuple[str, str, str, dict[str, object]]] = []
    for c in load().cases:
        if c.split != "dev" or c.question is None or c.gold is None:
            continue
        g = c.gold
        if g.tool_call is None or g.path.value not in ("stats", "mixed"):
            continue
        out.append((c.id, c.question, g.tool_call.tool, dict(g.tool_call.args)))
    return out


def run(model: str, base: StatsAnswerer) -> dict[str, object]:
    llm = make_llm(models().llm.model_copy(update={"model": model}))
    sp = StatsPath(base.path.store, llm, resolver=base.path.resolver, fallback=None)
    sp.answer("How many points per game is LeBron James averaging this season?")  # warm-up
    times: list[float] = []
    ok = 0
    statuses: Counter[str] = Counter()
    cs = cases()
    for _cid, q, tool, args in cs:
        t = time.perf_counter()
        a, _ = sp.answer(q)
        times.append(time.perf_counter() - t)
        call = a.tool_call
        if call and call["tool"] == tool and canonical(tool, call["args"]) == canonical(tool, args):
            ok += 1
        statuses[a.status or a.behaviour] += 1
    return {
        "model": model,
        "n": len(cs),
        "tool_ok": ok,
        "p50": statistics.median(times),
        "p95": pct(times, 0.95),
        "max": max(times),
        "statuses": dict(statuses),
    }


def main(model_names: list[str]) -> None:
    base = StatsAnswerer()
    results = [run(m, base) for m in model_names]
    lines = [
        "# Model benchmark: preliminary, not Gate 3",
        "",
        f"Dev split only, gold tool calls only, one run per case, stats path with gold-path "
        f"routing (G11), think off. Prompt {PROMPT_VERSION}, git {git_sha()[:12]}, "
        f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC, snapshot: dev build "
        "(not the pinned eval snapshot).",
        "",
        "| Model | Cases | Tool-call accuracy | p50 s | p95 s | max s | Answer statuses |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        n, ok = int(r["n"]), int(r["tool_ok"])  # type: ignore[call-overload]
        lines.append(
            f"| {r['model']} | {n} | {ok}/{n} = {100 * ok / n:.0f}% | {r['p50']:.2f} | "
            f"{r['p95']:.2f} | {r['max']:.2f} | {r['statuses']} |"
        )
    lines += ["", "Budget (spec): typed tool path p95 <= 3 s on the target Mac."]
    (REPORTS / "benchmark-preliminary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1:] or [models().llm.model])
