from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "infra" / "metadata" / "atlas" / "scripts"))

from entity_publish import validate_entities  # noqa: E402


def test_validate_duplicate_qualified_names_rejected() -> None:
    entities = [
        {"typeName": "Process", "attributes": {"qualifiedName": "dup", "name": "a"}},
        {"typeName": "Process", "attributes": {"qualifiedName": "dup", "name": "b"}},
    ]
    errors = validate_entities(entities)
    assert errors


def test_validate_unique_ok() -> None:
    entities = [
        {"typeName": "Process", "attributes": {"qualifiedName": "a", "name": "a"}},
        {"typeName": "Process", "attributes": {"qualifiedName": "b", "name": "b"}},
    ]
    assert not validate_entities(entities)


def test_kafka_topic_requires_uri() -> None:
    entities = [
        {
            "typeName": "kafka_topic",
            "attributes": {"name": "x", "topic": "t", "qualifiedName": "kafka://dataops@dataops_net/t"},
        },
    ]
    assert validate_entities(entities)


def test_kafka_topic_with_uri_ok() -> None:
    entities = [
        {
            "typeName": "kafka_topic",
            "attributes": {
                "name": "x",
                "topic": "t",
                "qualifiedName": "kafka://dataops@dataops_net/t",
                "uri": "kafka://kafka:9092/t",
            },
        },
    ]
    assert not validate_entities(entities)


def test_hive_table_requires_db_reference() -> None:
    entities = [
        {
            "typeName": "hive_table",
            "attributes": {"name": "t", "qualifiedName": "db.public.t@cluster"},
        },
    ]
    assert validate_entities(entities)


def test_hive_table_unknown_db_reference() -> None:
    entities = [
        {
            "typeName": "hive_db",
            "attributes": {"name": "good", "qualifiedName": "good@cluster", "clusterName": "cluster"},
        },
        {
            "typeName": "hive_table",
            "relationshipAttributes": {
                "db": {"typeName": "hive_db", "uniqueAttributes": {"qualifiedName": "missing@cluster"}}
            },
            "attributes": {"name": "t", "qualifiedName": "good.public.t@cluster"},
        },
    ]
    assert validate_entities(entities)


def test_hive_db_table_ok() -> None:
    entities = [
        {
            "typeName": "hive_db",
            "attributes": {"name": "good", "qualifiedName": "good@cluster", "clusterName": "cluster"},
        },
        {
            "typeName": "hive_table",
            "relationshipAttributes": {
                "db": {"typeName": "hive_db", "uniqueAttributes": {"qualifiedName": "good@cluster"}}
            },
            "attributes": {"name": "t", "qualifiedName": "good.public.t@cluster"},
        },
    ]
    assert not validate_entities(entities)
