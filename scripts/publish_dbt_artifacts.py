#!/usr/bin/env python3
"""Publish dbt artifacts (manifest/catalog/run_results/index.html) to MinIO.

Used by CI/CD to publish dbt documentation artifacts for downstream consumers.
Idempotent: re-uploads overwrite the same keys.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ARTIFACT_NAMES = (
    "manifest.json",
    "catalog.json",
    "run_results.json",
    "static_index.html",
)


def _client() -> "Minio":  # type: ignore[name-defined]
    from minio import Minio

    endpoint = os.environ["MINIO_ENDPOINT"].replace("http://", "").replace("https://", "")
    secure = os.environ.get("MINIO_SECURE", "false").lower() in {"1", "true", "yes"}
    return Minio(
        endpoint,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=secure,
    )


def _ensure_bucket(client: "Minio", bucket: str) -> None:  # type: ignore[name-defined]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _put(client: "Minio", bucket: str, key: str, path: Path) -> None:  # type: ignore[name-defined]
    content_type = "application/json" if path.suffix == ".json" else "text/html"
    client.fput_object(bucket, key, str(path), content_type=content_type)
    print(f"uploaded s3://{bucket}/{key} ({path.stat().st_size} bytes)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--latest-prefix", default=None)
    parser.add_argument("--names", nargs="*", default=list(ARTIFACT_NAMES))
    args = parser.parse_args(argv)

    target_dir = Path(args.target_dir)
    if not target_dir.is_dir():
        print(f"target directory missing: {target_dir}", file=sys.stderr)
        return 1

    client = _client()
    _ensure_bucket(client, args.bucket)

    uploaded = 0
    for name in args.names:
        src = target_dir / name
        if not src.exists():
            print(f"skip missing artifact: {src}")
            continue
        # Run-scoped copy.
        run_key = f"dbt-artifacts/{args.prefix.rstrip('/')}/{name}"
        _put(client, args.bucket, run_key, src)
        # Latest-success copy (optional consumers: mirrors, static hosting).
        if args.latest_prefix:
            latest_key = f"dbt-artifacts/{args.latest_prefix.rstrip('/')}/{name}"
            _put(client, args.bucket, latest_key, src)
        uploaded += 1

    if uploaded == 0:
        print("no artifacts uploaded", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
