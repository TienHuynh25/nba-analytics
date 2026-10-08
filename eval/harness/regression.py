"""Regression rule and run statistics (tasks 2.18, 2.19).

A change merges only if, on the dev split (eval/README.md):

1. a one-sided exact McNemar test against the last accepted run shows no significant drop;
2. no ``critical`` case moves from pass to fail;
3. no unverified number is shown.

Cases are paired by id. The McNemar test uses only the discordant pairs: b = pass -> fail,
c = fail -> pass. Under no change, b ~ Binomial(b + c, 1/2). The one-sided p-value is
P(X >= b), and a drop is significant when p < alpha.

Seeds and their paraphrases tend to pass or fail together, so accuracy intervals come from a
bootstrap over seed families, not over cases.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import comb

ALPHA = 0.05


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    family: str
    passed: bool
    critical: bool = False
    unverified_numbers: int = 0


@dataclass(frozen=True)
class Verdict:
    ok: bool
    p_value: float
    pass_to_fail: list[str]
    fail_to_pass: list[str]
    critical_regressions: list[str]
    unverified_numbers: int
    reasons: list[str]


def mcnemar_one_sided(b: int, c: int) -> float:
    """P(X >= b) for X ~ Binomial(b + c, 0.5): evidence that the new run is worse."""
    n = b + c
    if n == 0:
        return 1.0
    return float(sum(comb(n, k) for k in range(b, n + 1)) / (2**n))


def compare(
    accepted: Mapping[str, CaseOutcome], candidate: Mapping[str, CaseOutcome], alpha: float = ALPHA
) -> Verdict:
    shared = sorted(set(accepted) & set(candidate))
    p2f = [i for i in shared if accepted[i].passed and not candidate[i].passed]
    f2p = [i for i in shared if not accepted[i].passed and candidate[i].passed]
    crit = [i for i in p2f if candidate[i].critical or accepted[i].critical]
    unverified = sum(o.unverified_numbers for o in candidate.values())
    p = mcnemar_one_sided(len(p2f), len(f2p))
    reasons = []
    if p < alpha:
        reasons.append(f"significant drop: McNemar one-sided p = {p:.4f} < {alpha}")
    if crit:
        reasons.append(f"critical cases moved pass -> fail: {', '.join(crit)}")
    if unverified:
        reasons.append(f"{unverified} unverified number(s) shown")
    return Verdict(not reasons, p, p2f, f2p, crit, unverified, reasons)


def accuracy(outcomes: Sequence[CaseOutcome]) -> float:
    return sum(o.passed for o in outcomes) / len(outcomes) if outcomes else float("nan")


def family_bootstrap(
    outcomes: Sequence[CaseOutcome], n: int = 2000, seed: int = 0, level: float = 0.95
) -> tuple[float, float]:
    """Percentile interval for accuracy, resampling whole seed families."""
    fams: dict[str, list[bool]] = {}
    for o in outcomes:
        fams.setdefault(o.family, []).append(o.passed)
    groups = list(fams.values())
    if not groups:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        sample = [groups[rng.randrange(len(groups))] for _ in groups]
        cases = [x for g in sample for x in g]
        stats.append(sum(cases) / len(cases))
    stats.sort()
    lo = stats[int((1 - level) / 2 * n)]
    hi = stats[int((1 + level) / 2 * n) - 1]
    return (lo, hi)


def difference_bootstrap(
    a: Sequence[CaseOutcome], b: Sequence[CaseOutcome], n: int = 2000, seed: int = 0
) -> tuple[float, float]:
    """95% interval for accuracy(a) - accuracy(b), resampling families within each set."""
    rng = random.Random(seed)

    def groups(xs: Sequence[CaseOutcome]) -> list[list[bool]]:
        g: dict[str, list[bool]] = {}
        for o in xs:
            g.setdefault(o.family, []).append(o.passed)
        return list(g.values())

    ga, gb = groups(a), groups(b)
    diffs = []
    for _ in range(n):
        sa = [x for _ in ga for x in ga[rng.randrange(len(ga))]]
        sb = [x for _ in gb for x in gb[rng.randrange(len(gb))]]
        diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    diffs.sort()
    return (diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1])
