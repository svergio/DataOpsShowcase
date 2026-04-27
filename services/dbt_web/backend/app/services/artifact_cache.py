from __future__ import annotations

from app.clients.storage_client import StorageClient
from app.observability.metrics import CACHE_HITS_TOTAL, CACHE_MISS_TOTAL
from app.schemas.contracts import ArtifactEnvelope


class ArtifactCacheService:
    def __init__(self, storage: StorageClient) -> None:
        self.storage = storage

    def cache_key(self, run_id: str, name: str) -> str:
        return f"dbt-artifacts/{run_id}/{name}"

    def latest_key(self, target: str, name: str) -> str:
        return f"dbt-artifacts/latest-success/{target}/{name}"

    def get_cached(self, run_id: str, name: str, target: str = "unknown") -> ArtifactEnvelope | None:
        key = self.cache_key(run_id, name)
        payload = self.storage.get_json(key)
        if payload is None:
            CACHE_MISS_TOTAL.labels(target=target).inc()
            return None
        CACHE_HITS_TOTAL.labels(target=target).inc()
        return ArtifactEnvelope(
            run_id=run_id,
            name=name,  # type: ignore[arg-type]
            content=payload,
            cached=True,
        )

    def save_cached(self, run_id: str, target: str, artifact: ArtifactEnvelope) -> None:
        payload = artifact.content if isinstance(artifact.content, dict) else {"raw": artifact.content}
        self.storage.put_json(self.cache_key(run_id, artifact.name), payload)
        self.storage.put_json(self.latest_key(target, artifact.name), payload)
