import pytest

from eval.harness.regression import (
    CaseOutcome,
    compare,
    family_bootstrap,
    mcnemar_one_sided,
)


def outcomes(passes: list[bool], critical: set[int] = frozenset()) -> dict[str, CaseOutcome]:  # type: ignore[assignment]
    return {
        f"Q{i:02d}": CaseOutcome(f"Q{i:02d}", f"Q{i:02d}", p, critical=i in critical)
        for i, p in enumerate(passes)
    }


def test_mcnemar_values() -> None:
    assert mcnemar_one_sided(0, 0) == 1.0
    assert mcnemar_one_sided(5, 0) == pytest.approx(1 / 32)
    assert mcnemar_one_sided(3, 3) == pytest.approx(0.65625)


def test_planted_regression_fails() -> None:
    # Task 2.19 done-when: a planted regression fails the check.
    base = outcomes([True] * 200)
    worse = outcomes([False] * 8 + [True] * 192)
    v = compare(base, worse)
    assert not v.ok and v.p_value < 0.05 and len(v.pass_to_fail) == 8


def test_noise_passes() -> None:
    base = outcomes([True] * 100 + [False] * 100)
    cand = outcomes([False, True] + [True] * 98 + [True, False] + [False] * 98)
    v = compare(base, cand)
    assert v.ok, v.reasons


def test_one_critical_regression_fails_even_without_significance() -> None:
    base = outcomes([True] * 50, critical={3})
    cand = outcomes([True, True, True, False] + [True] * 46, critical={3})
    v = compare(base, cand)
    assert not v.ok and v.critical_regressions == ["Q03"]


def test_unverified_number_fails() -> None:
    base = outcomes([True] * 10)
    cand = dict(base)
    cand["Q01"] = CaseOutcome("Q01", "Q01", True, unverified_numbers=1)
    assert not compare(base, cand).ok


def test_family_bootstrap_is_wider_when_families_correlate() -> None:
    indep = [CaseOutcome(f"c{i}", f"f{i}", i % 5 != 0) for i in range(300)]
    corr = [CaseOutcome(f"c{i}", f"f{i // 3}", (i // 3) % 5 != 0) for i in range(300)]
    lo1, hi1 = family_bootstrap(indep)
    lo2, hi2 = family_bootstrap(corr)
    assert lo1 < 0.8 < hi1 and lo2 < 0.8 < hi2
    assert hi2 - lo2 > hi1 - lo1
