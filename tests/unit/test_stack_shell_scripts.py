from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    "olap_fresh_volume.sh",
    "ingress_portal_reload.sh",
    "generators_wait_ready.sh",
    "stand_refresh.sh",
    "smoke_ingress.sh",
    "airflow_code_sync.sh",
    "verify_raw_layer.sh",
    "verify_staging_post_spark.sh",
    "superset_full_reset.sh",
]
MARKERS = ("set -euo pipefail", "pg_olap_data", "dbt debug")


class StackShellScriptTests(unittest.TestCase):
    def test_syntax(self) -> None:
        for name in SCRIPTS:
            path = ROOT / "scripts" / name
            self.assertTrue(path.is_file(), msg=str(path))
            subprocess.run(["bash", "-n", str(path)], check=True)

    def test_olap_fresh_volume_markers(self) -> None:
        text = (ROOT / "scripts" / "olap_fresh_volume.sh").read_text(encoding="utf-8")
        for m in MARKERS:
            self.assertIn(m, text)

    def test_smoke_ingress_airflow_urls(self) -> None:
        text = (ROOT / "scripts" / "smoke_ingress.sh").read_text(encoding="utf-8")
        self.assertIn("/airflow/health", text)
        self.assertIn("/airflow/api/v1/version", text)


if __name__ == "__main__":
    unittest.main()
