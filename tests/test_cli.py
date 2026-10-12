"""``make serve`` loop (task 4.10) with a fake assistant: commands, sessions, output format."""

import io
from types import SimpleNamespace
from typing import Any

import pytest

from app import cli


class FakeAssistant:
    def __init__(self) -> None:
        self.sessions: list[Any] = []
        self.questions: list[str] = []

    def ask(self, q: str, session: Any) -> Any:
        self.questions.append(q)
        self.sessions.append(session)
        return SimpleNamespace(text=f"answer to {q}", path="stats", latency_ms=1500)


def run(monkeypatch: pytest.MonkeyPatch, stdin: str) -> tuple[FakeAssistant, int]:
    fake = FakeAssistant()
    monkeypatch.setattr(cli, "build", lambda db, shots: fake)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    return fake, cli.main([])


def test_question_gets_text_path_and_latency(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake, rc = run(monkeypatch, "Who leads in scoring?\n")
    out = capsys.readouterr().out
    assert rc == 0 and fake.questions == ["Who leads in scoring?"]
    assert "answer to Who leads in scoring?" in out and "[stats, 1.5 s]" in out


def test_blank_lines_are_ignored_and_quit_stops_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, _ = run(monkeypatch, "\n   \nfirst\n/quit\nnever asked\n")
    assert fake.questions == ["first"]


def test_follow_ups_share_a_session_and_new_resets_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake, _ = run(monkeypatch, "one\ntwo\n/new\nthree\n")
    s = fake.sessions
    assert s[0] is s[1] and s[2] is not s[0]
    assert "New conversation." in capsys.readouterr().out


def test_end_of_input_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    _, rc = run(monkeypatch, "")
    assert rc == 0
