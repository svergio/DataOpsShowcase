from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.xml_config import load_generator_xml


MINIMAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<scenario name="test_campaigns">
  <volume>
    <total>10</total>
  </volume>
  <weights>
    <weight name="EMAIL" value="1.0" />
  </weights>
</scenario>
"""


def test_load_generator_xml_reads_volume_and_weights(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "marketing_campaigns.xml").write_text(MINIMAL_XML, encoding="utf-8")
    out = load_generator_xml("marketing_campaigns", str(cfg_dir))
    assert out["_name"] == "test_campaigns"
    assert out["total"] == 10
    assert out["weights"]["EMAIL"] == pytest.approx(1.0)


def test_load_generator_xml_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_generator_xml("nonexistent", str(tmp_path)) == {}
