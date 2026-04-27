from __future__ import annotations

import os

import pytest

from common.config import Config, load_config


def test_load_config_minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENERATOR_MODE", "streaming")
    monkeypatch.setenv("GENERATOR_SEED", "7")
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.mode == "streaming"
    assert cfg.seed == 7
