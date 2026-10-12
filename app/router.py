"""Router: stats, knowledge, mixed or refuse (tasks 4.6, 4.7).

The model classifies with structured output; the prompt is a versioned file
(``prompts/router.v1.md``) whose version is recorded with every run. Refusals are one plain,
fixed sentence per reason: predictions, betting, injuries, non-NBA leagues.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.interfaces import LLMClient, Message

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
ROUTER_VERSION = "router.v1"

Route = Literal["stats", "knowledge", "mixed", "refuse"]
Reason = Literal["prediction", "betting", "injury", "non_nba"]

REFUSALS: dict[str, str] = {
    "prediction": "I can't predict future results; I can only answer with NBA stats so far.",
    "betting": "I can't give betting advice; I can only answer with NBA stats.",
    "injury": "I don't have injury news or player status; I can only answer with NBA stats.",
    "non_nba": "I only cover the NBA, so I can't answer about other leagues.",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "enum": ["stats", "knowledge", "mixed", "refuse"]},
        "refusal_reason": {"anyOf": [{"type": "string", "enum": list(REFUSALS)}, {"type": "null"}]},
    },
    "required": ["path", "refusal_reason"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Decision:
    path: Route
    reason: str | None = None

    @property
    def refusal(self) -> str | None:
        return (
            REFUSALS.get(self.reason or "", REFUSALS["prediction"])
            if (self.path == "refuse")
            else None
        )


class Router:
    def __init__(self, llm: LLMClient, version: str = ROUTER_VERSION) -> None:
        self.llm = llm
        self.version = version
        self.prompt = (PROMPTS / f"{version}.md").read_text()

    def route(self, question: str, history: str = "") -> Decision:
        user = f"Conversation so far: {history or 'none'}\nQuestion: {question}"
        raw = self.llm.complete(
            [Message("system", self.prompt), Message("user", user)], schema=SCHEMA
        )
        try:
            data = json.loads(raw)
            path = data["path"]
            if path not in ("stats", "knowledge", "mixed", "refuse"):
                raise ValueError(path)
            reason = data.get("refusal_reason") if path == "refuse" else None
            return Decision(path, reason)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return Decision("stats")  # the stats path still verifies every number
