from __future__ import annotations

from fastapi import APIRouter, Request

from app.state import AppState

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.ctx


@router.get("/lineage")
def lineage_graph(
    request: Request,
    resource_type: str | None = None,
    schema: str | None = None,
    package_name: str | None = None,
    tag: str | None = None,
) -> dict:
    state = get_state(request)
    nodes: list[dict] = []
    edges: list[dict] = []
    for uid, item in state.model_index.items():
        if resource_type and item.get("resource_type") != resource_type:
            continue
        if schema and item.get("schema") != schema:
            continue
        if package_name and item.get("package_name") != package_name:
            continue
        if tag and tag not in (item.get("tags") or []):
            continue
        nodes.append(
            {
                "id": uid,
                "name": item.get("name"),
                "resource_type": item.get("resource_type"),
                "schema": item.get("schema"),
                "package_name": item.get("package_name"),
                "tags": item.get("tags", []),
            }
        )
        for dep in item.get("depends_on", []):
            edges.append({"source": dep, "target": uid})
    node_ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e["source"] in node_ids and e["target"] in node_ids]
    return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}


@router.get("/lineage/{unique_id}")
def lineage(unique_id: str, request: Request) -> dict:
    state = get_state(request)
    node = state.model_index.get(unique_id)
    if node is None:
        return {"unique_id": unique_id, "upstream": [], "downstream": []}
    upstream = node.get("depends_on", [])
    downstream = [
        uid for uid, item in state.model_index.items() if unique_id in item.get("depends_on", [])
    ]
    return {"unique_id": unique_id, "node": node, "upstream": upstream, "downstream": downstream}
