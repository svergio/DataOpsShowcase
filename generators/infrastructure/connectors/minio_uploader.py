import csv
import io
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

from minio import Minio
from minio.error import S3Error


log = logging.getLogger("connectors.minio")


class MinioUploader:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool = False):
        self.endpoint = endpoint
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    def ensure_bucket(self, bucket: str, retries: int = 20, delay: float = 2.0) -> None:
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    log.info("MinIO bucket created: %s", bucket)
                else:
                    log.info("MinIO bucket exists: %s", bucket)
                return
            except (S3Error, Exception) as exc:
                last_err = exc
                log.warning("MinIO bucket attempt %s failed: %s", attempt, exc)
                time.sleep(delay)
        raise RuntimeError(f"Cannot ensure MinIO bucket: {last_err}")

    @staticmethod
    def _date_partition(prefix: str) -> str:
        now = datetime.now(timezone.utc)
        return f"{prefix}/{now:%Y}/{now:%m}/{now:%d}"

    def put_json_lines(
        self, bucket: str, prefix: str, records: List[Dict[str, Any]], filename: str
    ) -> str:
        path = f"{self._date_partition(prefix)}/{filename}"
        body = "\n".join(json.dumps(r, default=str) for r in records).encode("utf-8")
        self.client.put_object(
            bucket,
            path,
            data=io.BytesIO(body),
            length=len(body),
            content_type="application/x-ndjson",
        )
        return path

    def put_csv(
        self,
        bucket: str,
        prefix: str,
        records: List[Dict[str, Any]],
        filename: str,
    ) -> str:
        if not records:
            return ""
        path = f"{self._date_partition(prefix)}/{filename}"
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        body = buf.getvalue().encode("utf-8")
        self.client.put_object(
            bucket,
            path,
            data=io.BytesIO(body),
            length=len(body),
            content_type="text/csv",
        )
        return path

    def put_parquet(
        self,
        bucket: str,
        object_path: str,
        df: pd.DataFrame,
        content_type: str = "application/vnd.apache.parquet.file",
    ) -> str:
        buf = io.BytesIO()
        df.to_parquet(buf, index=False, engine="pyarrow")
        body = buf.getvalue()
        self.client.put_object(
            bucket,
            object_path,
            data=io.BytesIO(body),
            length=len(body),
            content_type=content_type,
        )
        return object_path

    def put_bytes_at(
        self,
        bucket: str,
        object_path: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.client.put_object(
            bucket,
            object_path,
            data=io.BytesIO(body),
            length=len(body),
            content_type=content_type,
        )
        return object_path

    def put_ndjson(
        self,
        bucket: str,
        object_path: str,
        lines: List[Dict[str, Any]],
    ) -> str:
        body = ("\n".join(json.dumps(r, default=str) for r in lines)).encode("utf-8")
        self.client.put_object(
            bucket,
            object_path,
            data=io.BytesIO(body),
            length=len(body),
            content_type="application/x-ndjson",
        )
        return object_path
