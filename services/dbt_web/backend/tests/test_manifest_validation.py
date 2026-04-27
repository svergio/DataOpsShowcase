from __future__ import annotations

import pytest

from app.core.errors import DbtWebError
from app.services.validators import validate_manifest


def test_manifest_min_schema() -> None:
    validate_manifest({"metadata": {}, "nodes": {}, "sources": {}})


def test_manifest_missing_key() -> None:
    with pytest.raises(DbtWebError):
        validate_manifest({"metadata": {}, "nodes": {}})
