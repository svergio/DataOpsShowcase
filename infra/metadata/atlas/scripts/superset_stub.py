#!/usr/bin/env python3
"""Placeholder: GET /api/v1/dashboard/ via Superset API and mirror datasets to Atlas."""

from __future__ import annotations

import os

import urllib.request


def main() -> None:
    base = os.environ.get("SUPERSET_BASE_URL", "http://localhost:8088/")
    urllib.request.urlopen(base, timeout=5)
    print("superset_stub: reachable", base)


if __name__ == "__main__":
    main()
