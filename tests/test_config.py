from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.config import CONFIG_DIR, load_models, load_sources


def test_models_yaml_loads() -> None:
    cfg = load_models()
    assert cfg.llm.backend in {"ollama", "llamacpp"}
    assert cfg.reranker.keep == 6
    assert cfg.retrieval.fusion_top_k == 40
    assert cfg.agent.max_tool_calls <= 3


def test_sources_yaml_loads() -> None:
    cfg = load_sources()
    assert cfg.nba_api.min_interval_s >= 0.6
    assert cfg.ingest.correction_window_days == 7
    assert cfg.snapshots.keep == 7
    assert cfg.timezone == "America/New_York"


def test_unknown_key_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text())
    raw["api_key"] = "secret"
    p = tmp_path / "sources.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValidationError):
        load_sources(p)


def test_throttle_below_spec_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text())
    raw["nba_api"]["min_interval_s"] = 0.1
    p = tmp_path / "sources.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValidationError):
        load_sources(p)
