"""Entity resolver unit tests on the fixture (task 3.6). Examples are not eval cases."""

from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from app.entities import EntityResolver, norm


@pytest.fixture(scope="module")
def resolver(fixture_db_path: Path) -> Iterator[EntityResolver]:
    con = duckdb.connect(str(fixture_db_path), read_only=True)
    yield EntityResolver(con)
    con.close()


def ids(r: EntityResolver, q: str) -> dict[str, list[int]]:
    return r.resolve(q).ids()


def test_full_names_accents_and_nicknames(resolver: EntityResolver) -> None:
    assert ids(resolver, "How is Nikola Jokić playing?") == {"players": [203999]}
    assert ids(resolver, "How is Nikola Jokic playing?") == {"players": [203999]}
    assert ids(resolver, "KD's scoring") == {"players": [201142]}
    assert ids(resolver, "What does Wemby average?") == {"players": [1641705]}


def test_unique_surname_needs_capital_letter(resolver: EntityResolver) -> None:
    assert ids(resolver, "Wembanyama blocks") == {"players": [1641705]}
    assert ids(resolver, "his free throw rate this season") == {}


def test_misspelling_is_fuzzy_matched(resolver: EntityResolver) -> None:
    assert ids(resolver, "Is Stephen Cury shooting well?") == {"players": [201939]}


def test_shared_names_ask_which(resolver: EntityResolver) -> None:
    res = resolver.resolve("What is Ball averaging?")
    assert res.players == [] and len(res.ambiguous) == 1
    q = res.ambiguous[0].question()
    assert "LaMelo Ball" in q and "Lonzo Ball" in q


def test_teams_by_name_city_abbreviation_and_nickname(resolver: EntityResolver) -> None:
    assert ids(resolver, "Celtics vs Knicks") == {"teams": [1610612738, 1610612752]}
    assert ids(resolver, "the Dubs at home") == {"teams": [1610612744]}
    assert ids(resolver, "OKC's net rating") == {"teams": [1610612760]}


def test_norm() -> None:
    assert norm("Jokić's") == "jokic"
    assert norm("Gilgeous-Alexander") == "gilgeous alexander"
