from __future__ import annotations

from app.observability.metrics import MODELS_TOTAL


class LineageService:
    def build_index(self, manifest: dict) -> dict[str, dict]:
        nodes = manifest.get("nodes", {})
        sources = manifest.get("sources", {})
        exposures = manifest.get("exposures", {})
        graph: dict[str, dict] = {}
        for unique_id, node in {**nodes, **sources, **exposures}.items():
            graph[unique_id] = {
                "name": node.get("name"),
                "resource_type": node.get("resource_type"),
                "depends_on": node.get("depends_on", {}).get("nodes", []),
                "package_name": node.get("package_name"),
                "schema": node.get("schema"),
                "tags": node.get("tags", []),
            }
        MODELS_TOTAL.set(len(graph))
        return graph

    def get_dependencies(self, index: dict[str, dict], unique_id: str) -> dict:
        node = index.get(unique_id, {})
        return {"unique_id": unique_id, "depends_on": node.get("depends_on", []), "node": node}
