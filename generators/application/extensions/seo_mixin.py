from __future__ import annotations

import csv as csv_module
import io
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from common.factories.reference import UserRef
from domain.constants import (
    SEO_CATEGORIES,
    _sample_initial_rank,
    _weights_from_xm,
    _weighted_choice,
)

log = logging.getLogger(__name__)


class SeoExtensionMixin:
    def _seed_seo_keywords(self, oltp: OltpWriter) -> None:
        xm = self._xcfg("seo_keywords")
        nkw = int(xm.get("total", 1000))
        kcw = _weights_from_xm(xm, "keyword_category_weights", SEO_CATEGORIES)
        prefixes = xm.get("keyword_prefixes") or [
            "wireless headphones",
            "gaming laptop",
            "best smartphones",
            "techmart accessories",
            "tablet deals",
        ]
        mean_ln = float(xm.get("search_volume_mean", 7.0))
        sigma_ln = float(xm.get("search_volume_sigma", 1.5))
        rd = _weights_from_xm(
            xm,
            "rank_distribution",
            {
                "top_3": 0.05,
                "top_10": 0.15,
                "top_20": 0.20,
                "top_50": 0.30,
                "beyond": 0.30,
            },
        )

        kw_rows = []
        for i in range(nkw):
            cat = _weighted_choice(self.rng, kcw)
            base = self.rng.choice(prefixes)
            phrase = f"{base} #{i}"

            sv = int(
                np.clip(
                    self._np_rng.lognormal(mean_ln, sigma_ln),
                    100,
                    100_000,
                )
            )

            if sv > 10_000:
                comp_lo, comp_hi = 0.70, 1.0
            elif sv > 1_000:
                comp_lo, comp_hi = 0.40, 0.70
            else:
                comp_lo, comp_hi = 0.10, 0.40

            comp = round(self.rng.uniform(comp_lo, comp_hi), 2)

            rk = _sample_initial_rank(self.rng, rd, np_rng=self._np_rng)

            kw_rows.append(
                (
                    phrase,
                    cat,
                    f"/p/{phrase.replace(' ', '-')}",
                    sv,
                    comp,
                    round(self.rng.uniform(0.05, 3.0), 2),
                    "USD",
                    int(rk),
                    max(1, int(rk) - self.rng.randint(0, 5)),
                )
            )

        if kw_rows:
            oltp.insert_seo_keywords(kw_rows)
            log.info("Seeded seo_keywords rows=%s", len(kw_rows))

    def _minio_seo_rankings(
        self,
        cfg: Config,
        tick_no: int,
        minio: MinioUploader,
        oltp: OltpWriter,
    ) -> None:
        xm = self._xcfg("seo_rankings")
        every = int(xm.get("emit_every_ticks", 6))
        if tick_no % every != 0:
            return

        ids = oltp.fetch_keyword_ids()
        if not ids:
            return

        ym = datetime.now(timezone.utc).strftime("%Y/%m")

        csv_rows = []
        rdate = datetime.now(timezone.utc).date().isoformat()
        engines = _weights_from_xm(
            xm,
            "search_engine_weights",
            {"Google": 0.90, "Bing": 0.08, "Yahoo": 0.02},
        )
        devices = _weights_from_xm(
            xm,
            "device_type_weights",
            {"DESKTOP": 0.55, "MOBILE": 0.40, "TABLET": 0.05},
        )
        se = xm.get("seo_rank_edge_cases") or {}

        for kw_id in ids:
            prev = self.keyword_ranks.get(kw_id, self.rng.randint(1, 80))
            ch = prev + self.rng.randint(-5, 5)
            if self.rng.random() < float(se.get("drop_out_pct", 0.02)):
                ch = 120
            if self.rng.random() < float(se.get("viral_spike_pct", 0.01)):
                ch = max(1, prev - 22)
            if self.rng.random() < float(se.get("algo_drop_pct", 0.03)):
                ch = min(101, prev + 22)

            ch = max(1, min(999, ch))
            self.keyword_ranks[kw_id] = ch

            csv_rows.append({
                "keyword_id": kw_id,
                "keyword": f"phrase_{kw_id}",
                "rank_date": rdate,
                "position": ch,
                "previous_position": prev,
                "position_change": ch - prev,
                "url": f"/landing/{kw_id}",
                "search_engine": _weighted_choice(self.rng, engines),
                "device_type": _weighted_choice(self.rng, devices),
                "location": self.rng.choice(["US", "GB", "DE"]),
            })

        fn = f"rankings_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
        path = f"{cfg.minio_prefix_seo_rankings}/{ym}/{fn}"
        sbuf = io.StringIO()
        if csv_rows:
            w = csv_module.DictWriter(sbuf, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
        minio.put_bytes_at(
            cfg.minio_bucket_raw,
            path,
            sbuf.getvalue().encode("utf-8"),
            content_type="text/csv",
        )
        log.info("MinIO seo_rankings rows=%s", len(csv_rows))
    def _kafka_organic_sessions(
        self,
        cfg: Config,
        tick_no: int,
        kafka: KafkaPublisher,
        users: List[UserRef],
    ) -> None:
        xm = self._xcfg("organic_sessions")
        n = self.rng.randint(
            int(xm.get("events_per_tick_min", 5)),
            int(xm.get("events_per_tick_max", 25)),
        )
        lp_pool = xm.get("landing_pages") or ["/", "/blog", "/p/headphones", "/category/laptops"]
        kw_pool = xm.get("organic_keywords") or ["techmart", "best tablet", "noise cancelling", "how to choose laptop"]
        brmap = xm.get("bounce_rates") or {
            "homepage": 0.45,
            "product_page": 0.35,
            "category_page": 0.50,
            "blog_post": 0.70,
        }
        crmap = xm.get("conversion_rates") or {
            "branded_keyword": 0.08,
            "product_keyword": 0.05,
            "category_keyword": 0.02,
            "informational": 0.005,
        }

        def _bounce_p(lp: str) -> float:
            if "/blog" in lp:
                return float(brmap.get("blog_post", 0.70))
            if "/p/" in lp or "/product" in lp:
                return float(brmap.get("product_page", 0.35))
            if "categor" in lp:
                return float(brmap.get("category_page", 0.50))
            return float(brmap.get("homepage", 0.45))

        def _conv_p(kw: str) -> float:
            k = kw.lower()
            if "techmart" in k or "brand" in k:
                return float(crmap.get("branded_keyword", 0.08))
            if "how" in k or "choose" in k:
                return float(crmap.get("informational", 0.005))
            if "categor" in k or "best" == k.split()[0]:
                return float(crmap.get("category_keyword", 0.02))
            return float(crmap.get("product_keyword", 0.05))

        for _ in range(n):
            has_user = float(xm.get("identified_user_probability", 0.7))
            u = (
                self.rng.choice(users)
                if self.rng.random() < has_user and users
                else None
            )
            start = datetime.now(timezone.utc) - timedelta(seconds=self.rng.randint(2, 400))
            end = start + timedelta(seconds=self.rng.randint(5, 900))
            landing = self.rng.choice(lp_pool)
            kw = self.rng.choice(kw_pool)
            bounce = bool(self.rng.random() < _bounce_p(landing))
            conv = bool(self.rng.random() < _conv_p(kw))

            payload = {
                "event_id": str(uuid.uuid4()),
                "session_id": f"sorg_{uuid.uuid4().hex[:12]}",
                "customer_id": int(u.user_id) if u else None,
                "landing_page": landing,
                "keyword": kw,
                "search_engine": "Google",
                "device_type": self.rng.choice(["DESKTOP", "MOBILE", "TABLET"]),
                "location": {"country": "US", "city": "NYC"},
                "session_start": start.isoformat(),
                "session_end": end.isoformat(),
                "pages_viewed": self.rng.randint(1, 18),
                "bounce": bounce,
                "conversion": conv,
                "revenue": round(self.rng.uniform(0, 420), 2) if conv and self.rng.random() < 0.8 else None,
                "timestamp": start.isoformat(),
            }

            kafka.publish(cfg.kafka_topic_seo_organic, key=payload["session_id"], value=payload)
