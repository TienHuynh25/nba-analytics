"""Latency measurement for the stats path (task 4.11).

Usage: ``NBA_EVAL_DB=... uv run python -m eval.latency --label before``

Runs every dev-split stats seed once (one warm-up question first) and writes p50 and p95 for the
whole answer, the tool-choice call and the answer-writing call to
``eval/reports/latency-<label>.md``. Dev split only: never tune on held-out.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections.abc import Mapping, Sequence
from typing import Any

from app.interfaces import Message
from eval.harness.answerer import StatsAnswerer
from eval.harness.report import REPORTS
from eval.schema import load


def pct(xs: Sequence[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, round(p * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    cases = [
        c
        for c in load().cases
        if c.type == "seed"
        and c.split == "dev"
        and c.gold
        and c.gold.path.value == "stats"
        and c.question
    ]
    if args.limit:
        cases = cases[: args.limit]
    a = StatsAnswerer()
    calls: list[tuple[str, float]] = []
    orig = a.path.llm.complete

    def timed(msgs: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        t = time.perf_counter()
        out = orig(msgs, schema=schema)
        calls.append(("tool" if schema else "answer", time.perf_counter() - t))
        return out

    a.path.llm.complete = timed  # type: ignore[method-assign,assignment]
    a.answer("How many points per game is LeBron James averaging this season?", "stats")
    total, tool, answer = [], [], []
    for c in cases:
        calls.clear()
        a.new_conversation()
        t = time.perf_counter()
        a.answer(c.question or "", "stats")
        total.append(time.perf_counter() - t)
        tool += [d for k, d in calls if k == "tool"]
        answer += [d for k, d in calls if k == "answer"]
    lines = [
        f"# Stats-path latency: {args.label}",
        "",
        f"{len(cases)} dev-split stats seeds, model {a.model}, one warm-up first.",
        "",
        "| Step | n | p50 s | p95 s | max s |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, xs in (
        ("whole answer", total),
        ("tool-choice call", tool),
        ("answer-writing call", answer),
    ):
        if xs:
            lines.append(
                f"| {name} | {len(xs)} | {statistics.median(xs):.2f} | "
                f"{pct(xs, 0.95):.2f} | {max(xs):.2f} |"
            )
    lines.append("")
    lines.append("Budget (spec): typed tool path p95 <= 3 s on the target Mac.")
    out = REPORTS / f"latency-{args.label}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
