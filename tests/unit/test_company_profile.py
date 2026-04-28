from __future__ import annotations

from infrastructure.settings.company_profile import _normalize_settings_payload


def test_normalize_payload_dict_roundtrip() -> None:
    d = {"tick_seconds": 3, "mode": "streaming"}
    assert _normalize_settings_payload(d) == d


def test_normalize_payload_json_string_object() -> None:
    s = '{"seed": 99}'
    assert _normalize_settings_payload(s) == {"seed": 99}


def test_normalize_payload_invalid_json_returns_empty() -> None:
    assert _normalize_settings_payload("{no") == {}


def test_normalize_payload_json_array_returns_empty() -> None:
    assert _normalize_settings_payload("[1, 2]") == {}


def test_normalize_payload_unknown_type_returns_empty() -> None:
    assert _normalize_settings_payload(42) == {}
