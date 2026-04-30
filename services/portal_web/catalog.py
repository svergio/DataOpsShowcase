from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CATALOG_PATH_ENV = "PORTAL_CATALOG_PATH"


def _default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "catalog.json"


def _normalize_service_entry(raw: dict[str, Any]) -> dict[str, str | None]:
    out: dict[str, str | None] = {
        "id": str(raw["id"]),
        "name": str(raw["name"]),
        "route": str(raw.get("route") or ""),
        "purpose": str(raw["purpose"]),
        "container": str(raw.get("container") or ""),
    }
    if raw.get("probe_url") is not None:
        out["probe_url"] = str(raw["probe_url"])
    else:
        out["probe_url"] = None
    if "kind" in raw and raw["kind"] is not None:
        out["kind"] = str(raw["kind"])
    if "checklist_what" in raw and raw["checklist_what"] is not None:
        out["checklist_what"] = str(raw["checklist_what"])
    if "checklist_how" in raw and raw["checklist_how"] is not None:
        out["checklist_how"] = str(raw["checklist_how"])
    return out


def _normalize_graph_nodes(raw: list[dict[str, Any]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for n in raw:
        item: dict[str, object] = {
            "id": str(n["id"]),
            "label_ru": str(n["label_ru"]),
            "container": str(n["container"]),
            "shape_kind": str(n["shape_kind"]),
            "group": int(n.get("group", 0)),
            "is_init": bool(n.get("is_init", False)),
        }
        if "optional" in n:
            item["optional"] = bool(n["optional"])
        out.append(item)
    return out


def validate_catalog(data: dict[str, Any]) -> None:
    v = int(data.get("version", 0))
    if v < 1:
        raise ValueError("catalog: missing or invalid version")

    for key in ("init_containers", "optional_graph_containers", "web_ui_services", "api_and_tools", "graph_nodes", "graph_links"):
        if key not in data:
            raise ValueError(f"catalog: missing key {key!r}")

    web = data["web_ui_services"]
    api = data["api_and_tools"]
    nodes = data["graph_nodes"]
    links = data["graph_links"]

    ids_web = [str(x["id"]) for x in web]
    ids_api = [str(x["id"]) for x in api]
    if len(ids_web) != len(set(ids_web)):
        raise ValueError("catalog: duplicate id in web_ui_services")
    if len(ids_api) != len(set(ids_api)):
        raise ValueError("catalog: duplicate id in api_and_tools")

    node_ids = {str(n["id"]) for n in nodes}
    if len(node_ids) != len(nodes):
        raise ValueError("catalog: duplicate id in graph_nodes")

    for i, link in enumerate(links):
        if not isinstance(link, (list, tuple)) or len(link) != 2:
            raise ValueError(f"catalog: graph_links[{i}] must be [source, target]")
        a, b = str(link[0]), str(link[1])
        if a not in node_ids:
            raise ValueError(f"catalog: graph_links unknown source {a!r}")
        if b not in node_ids:
            raise ValueError(f"catalog: graph_links unknown target {b!r}")


def load_catalog_dict(path: Path | None = None) -> dict[str, Any]:
    raw = (os.environ.get(_CATALOG_PATH_ENV) or "").strip()
    p = Path(path) if path is not None else (Path(raw) if raw else _default_catalog_path())
    p = Path(p)
    if not p.is_file():
        raise FileNotFoundError(f"portal catalog not found: {p}")
    text = p.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("catalog: root must be an object")
    validate_catalog(data)
    return data


def _build_from_disk(path: Path | None = None) -> tuple[
    frozenset[str],
    frozenset[str],
    list[dict[str, str | None]],
    list[dict[str, str | None]],
    list[dict[str, object]],
    list[tuple[str, str]],
]:
    data = load_catalog_dict(path)
    init_c = frozenset(str(x) for x in data["init_containers"])
    opt_c = frozenset(str(x) for x in data["optional_graph_containers"])
    web = [_normalize_service_entry(x) for x in data["web_ui_services"]]
    api = [_normalize_service_entry(x) for x in data["api_and_tools"]]
    gn = _normalize_graph_nodes(data["graph_nodes"])
    gl = [(str(pair[0]), str(pair[1])) for pair in data["graph_links"]]
    return init_c, opt_c, web, api, gn, gl


_INIT_C, _OPT_C, _WEB, _API, _GNODES, _GLINKS = _build_from_disk()

INIT_CONTAINERS: frozenset[str] = _INIT_C
OPTIONAL_GRAPH_CONTAINERS: frozenset[str] = _OPT_C
WEB_UI_SERVICES: list[dict[str, str | None]] = _WEB
API_AND_TOOLS: list[dict[str, str | None]] = _API
GRAPH_NODES: list[dict[str, object]] = _GNODES
GRAPH_LINKS: list[tuple[str, str]] = _GLINKS

SERVICE_ENTRIES = WEB_UI_SERVICES
C4_NODES: list[dict[str, object]] = []
