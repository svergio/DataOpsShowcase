from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTAL = ROOT / "services" / "portal_web"


class PortalCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(PORTAL))
        import catalog as cat

        cls._catalog = cat

    def test_catalog_json_loads_and_validate(self):
        cat = self._catalog
        p = PORTAL / "data" / "catalog.json"
        data = cat.load_catalog_dict(p)
        self.assertGreaterEqual(int(data["version"]), 1)
        self.assertGreaterEqual(len(data["web_ui_services"]), 1)
        cat.validate_catalog(data)

    def test_graph_links_reference_nodes(self):
        cat = self._catalog
        ids = {str(n["id"]) for n in cat.GRAPH_NODES}
        for a, b in cat.GRAPH_LINKS:
            self.assertIn(a, ids, msg=a)
            self.assertIn(b, ids, msg=b)

    def test_service_ids_unique(self):
        cat = self._catalog
        w = [e["id"] for e in cat.WEB_UI_SERVICES]
        a = [e["id"] for e in cat.API_AND_TOOLS]
        self.assertEqual(len(w), len(set(w)))
        self.assertEqual(len(a), len(set(a)))

    def test_catalog_rejects_bad_link(self):
        from catalog import validate_catalog

        base = json.loads((PORTAL / "data" / "catalog.json").read_text(encoding="utf-8"))
        base["graph_links"] = [["dataops_ingress", "nonexistent_node"]]
        with self.assertRaises(ValueError) as ctx:
            validate_catalog(base)
        self.assertIn("unknown target", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
