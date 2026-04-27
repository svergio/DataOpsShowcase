from __future__ import annotations

import io
import json

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.errors import DbtWebError


class StorageClient:
    def __init__(self) -> None:
        self.bucket = settings.dbt_web_artifact_bucket
        self._memory: dict[str, dict] = {}
        self.available = True
        endpoint = settings.dbt_web_storage_endpoint.replace("http://", "").replace("https://", "")
        try:
            self.client = Minio(
                endpoint,
                access_key=settings.dbt_web_storage_access_key,
                secret_key=settings.dbt_web_storage_secret_key,
                secure=settings.dbt_web_storage_secure,
            )
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception:  # noqa: BLE001
            self.available = False
            self.client = None

    def put_json(self, key: str, payload: dict) -> None:
        if not self.available or self.client is None:
            self._memory[key] = payload
            return
        body = json.dumps(payload).encode("utf-8")
        self.client.put_object(
            self.bucket,
            key,
            io.BytesIO(body),
            length=len(body),
            content_type="application/json",
        )

    def get_json(self, key: str) -> dict | None:
        if not self.available or self.client is None:
            return self._memory.get(key)
        try:
            response = self.client.get_object(self.bucket, key)
        except S3Error:
            return None
        try:
            return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise DbtWebError("STORAGE_DECODE_ERROR", str(exc)) from exc
        finally:
            response.close()
            response.release_conn()
