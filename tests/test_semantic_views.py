from pathlib import Path

import pytest

from metrics import generate_views
from metrics.schema import Base, Grain, Metric, load


def test_committed_views_match_registry(tmp_path: Path) -> None:
    out = tmp_path / "semantic"
    allow = tmp_path / "allow.txt"
    generate_views.write(load(), out, allow)
    committed = {p.name: p.read_text() for p in generate_views.OUT_DIR.glob("*.sql")}
    fresh = {p.name: p.read_text() for p in out.glob("*.sql")}
    assert committed == fresh, "run: uv run python -m metrics.generate_views"
    assert generate_views.ALLOWLIST.read_text() == allow.read_text()


def test_every_metric_lands_in_each_of_its_grain_views() -> None:
    reg = load()
    files = generate_views.render(reg)
    for m in reg.metrics:
        for g in m.grains:
            view = generate_views.SPINES[g][0]
            assert f" as {m.name}\n" in files[f"sem_{view}.sql"], (m.name, g)


def test_adding_a_metric_is_one_yaml_entry() -> None:
    reg = load()
    new = Metric(
        name="free_throw_attempts",
        label="Free throw attempts",
        description="Total free throw attempts.",
        formula="FTA",
        base=Base.player_season,
        sql="sum(fta)",
        grains=[Grain.player_season, Grain.player_career],
        unit="count",
        rounding={"decimals": 0},  # type: ignore[arg-type]
    )
    reg2 = reg.model_copy(update={"metrics": [*reg.metrics, new]})
    files = generate_views.render(reg2)
    assert "sum(fta) as free_throw_attempts" in files["sem_player_season_stats.sql"]
    assert "sum(fta) as free_throw_attempts" in files["sem_player_career_stats.sql"]


def test_allowlist_names_only_semantic_views() -> None:
    lines = [
        ln for ln in generate_views.ALLOWLIST.read_text().splitlines() if not ln.startswith("#")
    ]
    assert lines and all(ln.startswith("semantic.") for ln in lines)
    assert "semantic.player_season_stats" in lines


def test_metric_without_source_for_grain_is_rejected() -> None:
    reg = load()
    bad = reg.metrics[0].model_copy(update={"name": "bad", "base": Base.awards})
    with pytest.raises(ValueError, match="no source"):
        generate_views.render(reg.model_copy(update={"metrics": [*reg.metrics, bad]}))
