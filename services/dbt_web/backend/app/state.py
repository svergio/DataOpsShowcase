from __future__ import annotations

from dataclasses import dataclass, field

from app.clients.dbt_rest_client import DbtRestClient
from app.clients.storage_client import StorageClient
from app.services.artifact_cache import ArtifactCacheService
from app.services.docs_service import DocsService
from app.services.freshness_service import FreshnessService
from app.services.lineage_service import LineageService


@dataclass
class AppState:
    dbt_rest: DbtRestClient = field(default_factory=DbtRestClient)
    storage: StorageClient = field(default_factory=StorageClient)
    cache: ArtifactCacheService = field(init=False)
    docs: DocsService = field(default_factory=DocsService)
    lineage: LineageService = field(default_factory=LineageService)
    freshness: FreshnessService = field(default_factory=FreshnessService)
    model_index: dict[str, dict] = field(default_factory=dict)
    seen_events: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.cache = ArtifactCacheService(self.storage)
