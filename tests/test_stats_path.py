"""Stats path end to end on the fixture, with a scripted model (phase 3)."""

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from app.entities import Entity
from app.interfaces import Message
from app.snapshot import FileSnapshotStore
from app.state import ConversationState
from app.stats_path import StatsPath

SGA, JOKIC = 1628983, 203999


class Script:
    """Replies in order. Tool-call replies are dicts, answer drafts are strings."""

    model = "script"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.prompts: list[Sequence[Message]] = []

    def complete(self, messages: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        self.prompts.append(messages)
        r = self.replies.pop(0)
        return json.dumps(r) if isinstance(r, dict) else str(r)


@pytest.fixture(scope="module")
def store(fixture_db_path: Path) -> Iterator[FileSnapshotStore]:
    yield FileSnapshotStore(fixture_db_path)


def path(store: FileSnapshotStore, replies: list[Any]) -> tuple[StatsPath, Script]:
    llm = Script(replies)
    return StatsPath(store, llm), llm


def call(tool: str, **args: Any) -> dict[str, Any]:
    return {"tool": tool, "args": args}


def test_verified_answer_with_source_line(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call(
                "get_player_stats", player_ids=[SGA], season="2024-25", metrics=["points_per_game"]
            ),
            "Shai Gilgeous-Alexander is averaging 32.7 points per game this season.",
        ],
    )
    a, _ = sp.answer("How many points per game is SGA averaging this season?")
    assert a.behaviour == "answer" and a.status == "verified"
    assert a.text.endswith("data through 2025-06-22")
    assert "points per game · 2024-25 regular season" in a.text
    assert a.entities == {"players": [SGA]}
    ctx = llm.prompts[0][1].content
    assert "player_ids [1628983]" in ctx and "season: 2024-25" in ctx


def test_bad_numbers_twice_fall_back_to_the_table(store: FileSnapshotStore) -> None:
    sp, _ = path(
        store,
        [
            call(
                "get_player_stats", player_ids=[SGA], season="2024-25", metrics=["points_per_game"]
            ),
            "He averages 33.9 points.",
            "He averages 34.1 points.",
        ],
    )
    a, _ = sp.answer("How many points per game is SGA averaging this season?")
    assert a.status == "fallback" and "32.7" in a.text and "33.9" not in a.text


def test_ambiguous_name_asks(store: FileSnapshotStore) -> None:
    sp, llm = path(store, [])
    a, _ = sp.answer("What is Ball averaging this season?")
    assert a.behaviour == "clarify" and "LaMelo Ball" in a.text
    assert llm.prompts == []  # no model call needed


def test_not_tracked_needs_no_model_for_the_answer(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call("get_player_stats", player_ids=[SGA], season="1970-71", metrics=["blocks"]),
        ],
    )
    a, _ = sp.answer("How many blocks did SGA have in 1970-71?")
    assert a.behaviour == "not_tracked" and "1973-74" in a.text
    assert len(llm.prompts) == 1


def test_follow_up_carries_season_and_result_player(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call("get_leaders", metric="points_per_game", season="2024-25", limit=1),
            "Shai Gilgeous-Alexander leads at 32.7 points per game.",
            call(
                "get_player_stats", player_ids=[SGA], season="2024-25", metrics=["assists_per_game"]
            ),
            "He averages 6.4 assists.",
        ],
    )
    _, state = sp.answer("Who leads the NBA in scoring this season?")
    assert state.result_players and state.result_players[0].id == SGA
    a, _ = sp.answer("What about his assists?", state)
    ctx = llm.prompts[2][1].content
    assert "player_ids [1628983]" in ctx and "season: 2024-25" in ctx
    assert a.entities == {"players": [SGA]}


def test_pronoun_with_two_players_asks(store: FileSnapshotStore) -> None:
    two = (
        Entity("player", 2544, "LeBron James", "", "x"),
        Entity("player", 201142, "Kevin Durant", "", "x"),
    )
    sp, _ = path(store, [])
    a, _ = sp.answer("How many points did he score last season?", ConversationState(players=two))
    assert a.behaviour == "clarify" and "LeBron James" in a.text and "Kevin Durant" in a.text


def test_invalid_call_is_retried_once_with_the_error(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call("get_leaders", metric="points_per_gam", season="2024-25"),
            call("get_leaders", metric="points_per_game", season="2024-25", limit=1),
            "Shai Gilgeous-Alexander leads with 32.7 points per game.",
        ],
    )
    a, _ = sp.answer("Who leads the league in scoring this season?")
    assert a.status == "verified"
    assert "invalid" in llm.prompts[1][-1].content


def test_opinion_question_gets_stats_without_verdict(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call("compare", player_ids=[JOKIC, SGA], metrics=["points_per_game"], season="2024-25"),
            "Nikola Jokic averaged 29.6 points and Shai Gilgeous-Alexander 32.7.",
        ],
    )
    a, _ = sp.answer("Is Jokic better than SGA this season?")
    assert a.behaviour == "no_verdict"
    assert "do not say who is better" in llm.prompts[1][0].content


def test_invented_ids_are_dropped(store: FileSnapshotStore) -> None:
    sp, _ = path(
        store,
        [
            call(
                "get_leaders",
                metric="assists_per_game",
                season="2024-25",
                limit=1,
                team_id=1610612759,
            ),
            "Trae Young leads with 11.6 assists per game.",
        ],
    )
    a, _ = sp.answer("Who leads the league in assists per game this season?")
    assert a.tool_call is not None and "team_id" not in a.tool_call["args"]


def test_bare_follow_up_does_not_carry_the_previous_answer(store: FileSnapshotStore) -> None:
    sp, llm = path(
        store,
        [
            call("get_leaders", metric="points_per_game", season="2024-25", limit=1),
            "Shai Gilgeous-Alexander leads at 32.7 points per game.",
            call("get_leaders", metric="assists_per_game", season="2024-25", limit=1),
            "Trae Young leads with 11.6 assists per game.",
        ],
    )
    _, state = sp.answer("Who leads the NBA in scoring this season?")
    sp.answer("What about assists?", state)
    assert "player_ids" not in llm.prompts[2][1].content
