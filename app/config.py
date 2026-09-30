"""Typed loading of config/models.yaml and config/sources.yaml (task 0.10).

Both files are validated with pydantic on load. They hold tunables only, never secrets.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LLMConfig(_Strict):
    backend: Literal["ollama", "llamacpp"]
    base_url: HttpUrl
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    timeout_s: float = Field(gt=0)


class EmbeddingsConfig(_Strict):
    model: str


class RerankerConfig(_Strict):
    model: str
    keep: int = Field(gt=0)


class RetrievalConfig(_Strict):
    fusion_top_k: int = Field(gt=0)


class AgentConfig(_Strict):
    max_tool_calls: int = Field(gt=0, le=3)


class ModelsConfig(_Strict):
    llm: LLMConfig
    sql_fallback_llm: LLMConfig | None = None
    embeddings: EmbeddingsConfig
    reranker: RerankerConfig
    retrieval: RetrievalConfig
    agent: AgentConfig


class NbaApiConfig(_Strict):
    min_interval_s: float = Field(ge=0.6)
    timeout_s: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    backoff_initial_s: float = Field(gt=0)
    backoff_max_s: float = Field(gt=0)


class IngestConfig(_Strict):
    correction_window_days: int = Field(ge=1)
    row_count_tolerance: float = Field(gt=0, lt=1)


class PathsConfig(_Strict):
    raw: Path
    snapshots: Path
    checkpoints: Path
    logs: Path


class SnapshotsConfig(_Strict):
    keep: int = Field(ge=1)
    current_link: Path


class SourcesConfig(_Strict):
    nba_api: NbaApiConfig
    ingest: IngestConfig
    paths: PathsConfig
    snapshots: SnapshotsConfig
    timezone: str

    def resolve(self, p: Path) -> Path:
        """Resolve a configured relative path against the repo root."""
        return p if p.is_absolute() else REPO_ROOT / p


def _load_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_models(path: Path = CONFIG_DIR / "models.yaml") -> ModelsConfig:
    return ModelsConfig.model_validate(_load_yaml(path))


def load_sources(path: Path = CONFIG_DIR / "sources.yaml") -> SourcesConfig:
    return SourcesConfig.model_validate(_load_yaml(path))


@lru_cache(maxsize=1)
def models() -> ModelsConfig:
    return load_models()


@lru_cache(maxsize=1)
def sources() -> SourcesConfig:
    return load_sources()
