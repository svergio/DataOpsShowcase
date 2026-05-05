from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass
from typing import Iterable, Iterator
from urllib.parse import urlparse

from minio import Minio

from services.common.logging_utils import get_logger

logger = get_logger(__name__)


def _strip_scheme(endpoint: str) -> tuple[str, bool]:
    if "://" in endpoint:
        parsed = urlparse(endpoint)
        secure = parsed.scheme == "https"
        host = parsed.netloc or parsed.path
        return host, secure
    return endpoint, False


def get_client(
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    secure: bool | None = None,
) -> Minio:
    endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = access_key or os.environ.get("MINIO_ROOT_USER", "minio")
    secret_key = secret_key or os.environ.get("MINIO_ROOT_PASSWORD", "minio12345")
    host, scheme_secure = _strip_scheme(endpoint)
    if secure is None:
        secure = scheme_secure
    return Minio(host, access_key=access_key, secret_key=secret_key, secure=secure)


@dataclass(frozen=True)
class MinioObject:
    bucket: str
    key: str
    size: int
    etag: str

    @property
    def path(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


def list_objects(
    client: Minio,
    bucket: str,
    prefix: str,
    *,
    recursive: bool = True,
) -> Iterator[MinioObject]:
    for obj in client.list_objects(bucket, prefix=prefix, recursive=recursive):
        if obj.is_dir:
            continue
        yield MinioObject(
            bucket=bucket,
            key=obj.object_name,
            size=obj.size or 0,
            etag=(obj.etag or "").strip('"'),
        )


def get_object_bytes(client: Minio, bucket: str, key: str) -> bytes:
    response = client.get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def read_jsonl(client: Minio, bucket: str, key: str) -> list[dict]:
    raw = get_object_bytes(client, bucket, key)
    text = raw.decode("utf-8").strip()
    if not text:
        return []
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning(
                "skip invalid jsonl line",
                extra={"extra_payload": {"key": key, "preview": line[:200]}},
            )
    return rows


def read_csv(client: Minio, bucket: str, key: str) -> list[dict]:
    raw = get_object_bytes(client, bucket, key)
    if not raw:
        return []
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    return list(reader)


def put_jsonl(client: Minio, bucket: str, key: str, records: Iterable[dict]) -> int:
    body = "\n".join(json.dumps(r, default=str, ensure_ascii=False) for r in records)
    data = body.encode("utf-8")
    stream = io.BytesIO(data)
    client.put_object(
        bucket,
        key,
        stream,
        length=len(data),
        content_type="application/x-ndjson",
    )
    return len(data)


def ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info(
            "minio bucket created",
            extra={"extra_payload": {"bucket": bucket}},
        )
