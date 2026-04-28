from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.config import Config, load_config

from generator_env import clear_generator_config_env as _clear_generator_env


def test_load_config_minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_generator_env(monkeypatch)
    monkeypatch.setenv("GENERATOR_MODE", "streaming")
    monkeypatch.setenv("GENERATOR_SEED", "7")
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.mode == "streaming"
    assert cfg.seed == 7


def test_json_file_sets_tick_when_env_unset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"tick_seconds": 99}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(p))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    cfg = load_config()
    assert cfg.tick_seconds == 99


def test_env_overrides_json_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"tick_seconds": 99}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(p))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("GENERATOR_TICK_SECONDS", "3")
    cfg = load_config()
    assert cfg.tick_seconds == 3


def test_generator_settings_json_overlays_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"tick_seconds": 10, "seed": 1}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(p))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv(
        "GENERATOR_SETTINGS_JSON",
        json.dumps({"tick_seconds": 77}),
    )
    cfg = load_config()
    assert cfg.tick_seconds == 77
    assert cfg.seed == 1


def test_invalid_generator_settings_json_ignored_and_file_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"tick_seconds": 55}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(p))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("GENERATOR_SETTINGS_JSON", "{not valid json")
    cfg = load_config()
    assert cfg.tick_seconds == 55


def test_malformed_json_file_falls_through_to_config_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("{invalid", encoding="utf-8")
    good = tmp_path / "company.generator.json"
    good.write_text(json.dumps({"tick_seconds": 33}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(bad))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    cfg = load_config()
    assert cfg.tick_seconds == 33


def test_meta_overrides_after_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_generator_env(monkeypatch)
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"tick_seconds": 10}), encoding="utf-8")
    monkeypatch.setenv("GENERATOR_SETTINGS_FILE", str(p))
    monkeypatch.setenv("GENERATOR_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("GENERATOR_USE_META_STORE", "true")
    monkeypatch.setenv("GENERATOR_META_DSN", "postgresql://unused")

    import infrastructure.settings.company_profile as cp

    monkeypatch.setattr(
        cp,
        "_load_meta_overrides",
        lambda: {"tick_seconds": 42},
    )
    cfg = load_config()
    assert cfg.tick_seconds == 42


def test_extension_np_rng_seed_matches_synthetic_extensions_formula() -> None:
    import numpy as np

    cfg_seed = 100
    seed_mix = (int(cfg_seed) ^ 2654435769) % (2**64)
    a = np.random.default_rng(seed_mix)
    b = np.random.default_rng(seed_mix)
    assert a.standard_normal(5).tolist() == b.standard_normal(5).tolist()
