from __future__ import annotations

from app.schemas.contracts import ArtifactEnvelope


class DocsService:
    def docs_payload(self, manifest: dict, catalog: dict, run_results: dict) -> dict:
        return {
            "manifest": manifest,
            "catalog": catalog,
            "run_results": run_results,
            "graph": {
                "nodes": list(manifest.get("nodes", {}).keys()),
                "sources": list(manifest.get("sources", {}).keys()),
            },
        }

    def envelope_as_json(self, artifact: ArtifactEnvelope) -> dict:
        if isinstance(artifact.content, dict):
            return artifact.content
        return {"content": artifact.content or ""}
