from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.skipif(
    os.environ.get("INGRESS_SMOKE") != "1",
    reason="set INGRESS_SMOKE=1 and run stack so nginx exposes /prometheus/",
)
def test_prometheus_home_contains_title() -> None:
    base = os.getenv("INGRESS_BASE_URL", "http://localhost:8090").rstrip("/")
    url = f"{base}/prometheus/graph"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            code = resp.getcode()
            body = resp.read().decode(errors="replace").lower()
    except urllib.error.HTTPError as e:
        pytest.fail(f"{url}: HTTP {e.code}")
    except urllib.error.URLError as e:
        pytest.fail(f"{url}: {e.reason!r}")

    assert code == 200, f"{url}: unexpected HTTP {code}"
    assert "prometheus" in body, f"{url}: expected Prometheus UI substring in body"
