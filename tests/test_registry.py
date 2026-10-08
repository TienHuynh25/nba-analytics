import pytest
import yaml
from pydantic import ValidationError

from metrics.schema import REGISTRY_PATH, Registry, load

# Every metric the 85 seed questions need (task 1.22 done-when).
SEED_METRICS = {
    "points_per_game",
    "rebounds_per_game",
    "assists_per_game",
    "steals_per_game",
    "blocks_per_game",
    "minutes_per_game",
    "field_goal_pct",
    "three_point_pct",
    "free_throw_pct",
    "games_played",
    "points",
    "rebounds",
    "assists",
    "blocks",
    "threes_made",
    "triple_doubles",
    "double_doubles",
    "forty_point_games",
    "plus_minus",
    "game_points",
    "true_shooting_pct",
    "usage_rate",
    "offensive_rating",
    "defensive_rating",
    "net_rating",
    "pace",
    "wins",
    "losses",
    "win_pct",
    "home_wins",
    "home_losses",
    "team_points_per_game",
    "championships",
    "player_championships",
    "league_points_per_game",
    "league_three_point_attempt_rate",
    "shot_attempts",
    "shot_fg_pct",
    "restricted_area_fg_pct",
    "corner_threes_made",
    "step_back_three_pct",
    "mvp_awards",
    "all_star_selections",
}


def test_registry_validates_and_covers_seed_metrics() -> None:
    reg = load()
    assert {m.name for m in reg.metrics} >= SEED_METRICS


@pytest.mark.parametrize(
    ("alias", "name"),
    [
        ("PPG", "points_per_game"),
        ("3P%", "three_point_pct"),
        ("TS%", "true_shooting_pct"),
        ("boards", "rebounds"),
        ("+/-", "plus_minus"),
        ("titles", "championships"),
    ],
)
def test_aliases_resolve(alias: str, name: str) -> None:
    assert load().metric(alias).name == name


def test_duplicate_alias_rejected() -> None:
    raw = yaml.safe_load(REGISTRY_PATH.read_text())
    raw["metrics"][1]["aliases"].append("ppg")
    with pytest.raises(ValidationError, match="alias"):
        Registry.model_validate(raw)


def test_unknown_qualification_rejected() -> None:
    raw = yaml.safe_load(REGISTRY_PATH.read_text())
    raw["metrics"][0]["qualification"] = "nope"
    with pytest.raises(ValidationError, match="unknown qualification"):
        Registry.model_validate(raw)


def test_qualification_by_era() -> None:
    q = load().qualification("per_game_leader")
    rule = q.rule_for("2025-26")
    assert rule.min_games_pct == 0.70 and rule.would_still_lead
    with pytest.raises(LookupError):
        q.rule_for("1990-91")  # earlier eras not yet defined (completed in 3.1)
