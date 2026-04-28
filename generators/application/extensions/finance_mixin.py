from __future__ import annotations

import json
import logging
import random
from datetime import date, timedelta
from typing import Any, Dict

from common.connectors.oltp import OltpWriter
from domain.constants import CHART_ACCOUNTS

log = logging.getLogger(__name__)


class FinanceExtensionMixin:
    def _seed_gl(self, oltp: OltpWriter) -> None:
        xm = self._xcfg("general_ledger")
        total = min(50000, int(xm.get("total_entries", 2000)))
        rows = []
        seq = 0

        for _ in range(total // 2):
            ed = date.today() - timedelta(days=self.rng.randint(0, 730))
            en = f"JE-{ed.strftime('%Y%m%d')}-{seq:05d}"

            ref_id = self.rng.randint(1, 999999)
            sale_am = round(self.rng.uniform(20, 799), 2)

            gl_edge = xm.get("gl_edge_cases") or {}
            unbalanced = self.rng.random() < float(gl_edge.get("unbalanced_pct", 0.005))
            debit_amt = sale_am + (1.0 if unbalanced else 0.0)

            seq += 1

            rows.append(
                (
                    ed,
                    en + "-d",
                    "1020",
                    CHART_ACCOUNTS["1020"][0],
                    CHART_ACCOUNTS["1020"][1],
                    debit_amt,
                    0.0,
                    "USD",
                    "SALE",
                    ref_id,
                    "ORDER",
                    "sale debit",
                    "generator",
                ),
            )

            rows.append(
                (
                    ed,
                    en + "-c",
                    "4000",
                    CHART_ACCOUNTS["4000"][0],
                    CHART_ACCOUNTS["4000"][1],
                    0.0,
                    sale_am,
                    "USD",
                    "SALE",
                    ref_id,
                    "ORDER",
                    "sale credit",
                    "generator",
                ),
            )

        if rows:
            oltp.insert_gl_lines(rows[: min(len(rows), total)])
            log.info("Seeded general_ledger rows=%s", min(len(rows), total))
