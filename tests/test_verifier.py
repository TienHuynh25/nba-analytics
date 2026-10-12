import random

from app.verifier import Evidence, ResultValue, check, finalize, words_to_digits
from metrics.schema import Rounding

ONE = Rounding(decimals=1)
PCT = Rounding(decimals=1, display="percent")
INT = Rounding(decimals=0)


def ev() -> Evidence:
    return Evidence(
        values=[ResultValue(33.48, ONE), ResultValue(64, INT), ResultValue(0.4891, PCT)],
        args_text=["2025-26", "top 5"],
    )


def test_correct_draft_passes() -> None:
    c = check(
        "Luka Doncic led the league at 33.5 points per game over 64 games in 2025-26, "
        "shooting 48.9% from the field.",
        ev(),
    )
    assert c.ok, c.unmatched


def test_wrong_number_and_wrong_season_fail() -> None:
    assert check("He averaged 33.6 points.", ev()).unmatched == ["33.6"]
    assert check("In 2024-25 he averaged 33.5.", ev()).unmatched == ["2024-25"]


def test_spelled_out_numbers_are_checked_but_idioms_are_not() -> None:
    assert words_to_digits("sixty-four games") == "64 games"
    assert check("He played sixty-four games.", ev()).ok
    assert check("He played sixty-five games.", ev()).unmatched == ["65"]
    assert check("One of the best three-point shooters, with a triple-double.", ev()).ok


def test_numbers_in_cited_chunks_are_allowed_for_knowledge_answers() -> None:
    chunk = "TS% = PTS / (2 * (FGA + 0.44 * FTA))"
    assert check("Free throws count as 0.44 of a possession.", Evidence(chunks=[chunk])).ok
    assert not check("Free throws count as 0.45 of a possession.", Evidence(chunks=[chunk])).ok


def test_regenerate_once_then_fallback() -> None:
    drafts = iter(["33.6 points", "33.5 points"])
    f = finalize(lambda fb: next(drafts), ev(), lambda: "TABLE")
    assert f.status == "regenerated" and f.text == "33.5 points"
    drafts2 = iter(["33.6 points", "33.7 points"])
    f2 = finalize(lambda fb: next(drafts2), ev(), lambda: "TABLE")
    assert f2.status == "fallback" and f2.text == "TABLE"


def test_planted_wrong_number_never_reaches_output_across_1000_fuzzed_drafts() -> None:
    # Task 3.11 done-when.
    rng = random.Random(311)
    for _ in range(1000):
        rules = [ONE, PCT, INT]
        vals = []
        for _ in range(rng.randint(1, 4)):
            r = rng.choice(rules)
            x = rng.uniform(0.2, 0.7) if r is PCT else rng.uniform(0, 3000)
            vals.append(ResultValue(x, r))
        e = Evidence(values=vals, args_text=["2025-26"])

        def render(v: ResultValue) -> str:
            if v.rounding is PCT:
                return f"{100 * v.value:.1f}%"
            return f"{v.value:.{v.rounding.decimals}f}"

        parts = [render(v) for v in vals]
        good = "Values in 2025-26: " + ", ".join(parts) + "."
        # Plant one wrong number: shift a value by one unit in its last shown decimal.
        i = rng.randrange(len(vals))
        target = vals[i]
        step = 10**-target.rounding.decimals
        shown = float(parts[i].rstrip("%"))
        wrong = shown + rng.choice([-1, 1]) * step * rng.randint(1, 5)
        if any(abs(float(p.rstrip("%")) - wrong) < step / 2 for p in parts):
            continue  # the shift landed on another true value: not a wrong number
        planted = list(parts)
        suffix = "%" if target.rounding is PCT else ""
        planted[i] = f"{wrong:.{target.rounding.decimals}f}{suffix}"
        bad = "Values in 2025-26: " + ", ".join(planted) + "."
        assert check(good, e).ok, good

        def draft(feedback: list[str] | None, text: str = bad) -> str:
            return text

        out = finalize(draft, e, lambda: "result table")
        assert out.status == "fallback" and out.text == "result table", bad
