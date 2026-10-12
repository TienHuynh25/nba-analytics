"""Small interfaces the pipeline is built on (task 3.4).

Models and stores are swapped in ``config/models.yaml``, not code: :func:`make_llm` picks the
backend from config. Implementations hold no process-wide state, so the same objects work per
worker behind the planned team service (docs/decisions/0004-team-deployment.md).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import duckdb

from app.config import LLMConfig


@dataclass(frozen=True)
class Message:
    role: str  # system | user | assistant
    content: str


class LLMClient(Protocol):
    model: str

    def complete(self, messages: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        """Return the model's reply. With ``schema``, the reply is JSON valid for it."""
        ...


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    doc_type: str
    score: float = 0.0


class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[Chunk]: ...


class SnapshotStore(Protocol):
    def connection(self) -> duckdb.DuckDBPyConnection: ...

    @property
    def snapshot_id(self) -> str: ...

    @property
    def manifest(self) -> Mapping[str, Any]: ...


class Tool(Protocol):
    name: str
    schema: Mapping[str, Any]

    def run(self, args: Mapping[str, Any], store: SnapshotStore) -> Any: ...


# HTTP transport: (url, json body, timeout seconds) -> decoded JSON. Swappable in tests.
Post = Callable[[str, Mapping[str, Any], float], dict[str, Any]]


def http_post(url: str, body: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data: dict[str, Any] = json.loads(resp.read())
        return data


class OllamaClient:
    """Ollama ``/api/chat``. Structured output via ``format`` = JSON schema."""

    def __init__(self, cfg: LLMConfig, post: Post = http_post) -> None:
        self.cfg = cfg
        self.model = cfg.model
        self._post = post

    def complete(self, messages: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": self.cfg.think,
            "keep_alive": self.cfg.keep_alive,
            "options": {"temperature": self.cfg.temperature, "num_ctx": self.cfg.num_ctx},
        }
        if schema is not None:
            body["format"] = dict(schema)
        out = self._post(f"{str(self.cfg.base_url).rstrip('/')}/api/chat", body, self.cfg.timeout_s)
        return str(out["message"]["content"])


class LlamaCppClient:
    """llama.cpp server, OpenAI-compatible ``/v1/chat/completions`` with a JSON schema."""

    def __init__(self, cfg: LLMConfig, post: Post = http_post) -> None:
        self.cfg = cfg
        self.model = cfg.model
        self._post = post

    def complete(self, messages: Sequence[Message], schema: Mapping[str, Any] | None = None) -> str:
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.cfg.temperature,
            "chat_template_kwargs": {"enable_thinking": self.cfg.think},
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": dict(schema), "strict": True},
            }
        url = f"{str(self.cfg.base_url).rstrip('/')}/v1/chat/completions"
        out = self._post(url, body, self.cfg.timeout_s)
        return str(out["choices"][0]["message"]["content"])


def make_llm(cfg: LLMConfig, post: Post = http_post) -> LLMClient:
    if cfg.backend == "ollama":
        return OllamaClient(cfg, post)
    if cfg.backend == "llamacpp":
        return LlamaCppClient(cfg, post)
    raise ValueError(f"unknown LLM backend {cfg.backend!r}")
