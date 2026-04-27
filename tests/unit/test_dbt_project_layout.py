from __future__ import annotations

from pathlib import Path

import yaml


def test_dbt_project_and_layer_folders() -> None:
    root = Path(__file__).resolve().parents[2]
    project = root / "dbt" / "dbt_project.yml"
    assert project.is_file()
    models = root / "dbt" / "models"
    assert (models / "staging").is_dir()
    assert (models / "vault").is_dir()
    assert (models / "marts").is_dir()
    assert (models / "serving").is_dir()


def test_dbt_yaml_parse() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "dbt" / "dbt_project.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert data.get("name") == "dataops_showcase"
