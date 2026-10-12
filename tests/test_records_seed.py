"""Curated records seed (decision 0008, task 1.17): provenance rules, checked on the CSV itself.

The seed is hand-entered from Basketball-Reference, so every row needs a source URL and a
valid-from date. The CSV is currently header-only; these rules bite as soon as rows land.
"""

import csv
import re
from datetime import date
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parent.parent / "transform" / "seeds" / "records_curated.csv"
COLUMNS = ["record", "record_kind", "stat", "player", "value", "source_url", "valid_from", "note"]
KINDS = {"single_game", "career_count"}


def rows() -> list[dict[str, str]]:
    with SEED.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_header_is_the_agreed_columns() -> None:
    with SEED.open(newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == COLUMNS


@pytest.mark.parametrize("col", ["record", "record_kind", "player", "value", "source_url"])
def test_required_columns_are_never_blank(col: str) -> None:
    blank = [i + 2 for i, r in enumerate(rows()) if not (r[col] or "").strip()]
    assert not blank, f"{col} blank on seed lines {blank}"


def test_kind_and_stat_are_consistent() -> None:
    for i, r in enumerate(rows(), start=2):
        assert r["record_kind"] in KINDS, f"line {i}: kind {r['record_kind']!r}"
        if r["record_kind"] == "single_game":
            assert r["stat"], f"line {i}: single-game rows name their stat"


def test_source_urls_are_https_basketball_reference_pages() -> None:
    bad = [
        i
        for i, r in enumerate(rows(), start=2)
        if not re.match(r"https://www\.basketball-reference\.com/\S+$", r["source_url"])
    ]
    assert not bad, f"source_url must be a Basketball-Reference https page: lines {bad}"


def test_valid_from_is_an_iso_date_not_in_the_future() -> None:
    for i, r in enumerate(rows(), start=2):
        d = date.fromisoformat(r["valid_from"])
        assert d <= date.today(), f"line {i}: valid_from {d} is in the future"


def test_values_are_positive_numbers_and_rows_are_unique() -> None:
    seen: set[tuple[str, str, str]] = set()
    for i, r in enumerate(rows(), start=2):
        assert float(r["value"]) > 0, f"line {i}"
        key = (r["record"], r["stat"], r["player"])
        assert key not in seen, f"line {i}: duplicate {key}"
        seen.add(key)
