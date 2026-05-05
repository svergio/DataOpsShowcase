from __future__ import annotations

import base64
import os
import unittest
import urllib.error
import urllib.request


@unittest.skipUnless(
    os.environ.get("AIRFLOW_INGRESS_SMOKE") == "1",
    "set AIRFLOW_INGRESS_SMOKE=1 with stack up (ingress + airflow)",
)
class IngressAirflowSmokeTests(unittest.TestCase):
    def test_airflow_health_via_ingress(self) -> None:
        base = os.getenv("INGRESS_BASE_URL", "http://localhost:8090").rstrip("/")
        url = f"{base}/airflow/health"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                code = resp.getcode()
        except urllib.error.HTTPError as e:
            self.fail(f"{url}: HTTP {e.code}")
        except urllib.error.URLError as e:
            self.fail(f"{url}: {e.reason!r}")
        self.assertEqual(code, 200)

    def test_airflow_api_version_basic_auth_or_forbidden(self) -> None:
        base = os.getenv("INGRESS_BASE_URL", "http://localhost:8090").rstrip("/")
        url = f"{base}/airflow/api/v1/version"
        user = os.getenv("AIRFLOW_ADMIN_USER", "admin")
        password = os.getenv("AIRFLOW_ADMIN_PASSWORD", "admin")
        req = urllib.request.Request(url)
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                self.assertEqual(resp.getcode(), 200)
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (401, 403), msg=f"{url}: HTTP {e.code}")


if __name__ == "__main__":
    unittest.main()
