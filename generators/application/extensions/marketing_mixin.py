from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from common.factories.reference import UserRef
from domain.constants import CHANNELS_BY_TYPE, _season_mult_for_date, _weights_from_xm

log = logging.getLogger(__name__)


class MarketingExtensionMixin:
    def _seed_campaigns(self, oltp: OltpWriter) -> None:
        xm = self._xcfg("marketing_campaigns")
        n = int(xm.get("total", 500))
        weights = xm.get(
            "weights",
            {},
        )
        if not weights:
            weights = {
                "EMAIL": 0.30,
                "GOOGLE_ADS": 0.25,
                "SOCIAL_ADS": 0.20,
                "DISPLAY": 0.10,
                "PUSH": 0.08,
                "SMS": 0.05,
                "AFFILIATE": 0.02,
            }

        budgets: Dict[str, tuple[float, float]] = {}
        for t in xm.get("budget_ranges", []) or []:
            if isinstance(t, (list, tuple)) and len(t) >= 3:
                budgets[str(t[0])] = (float(t[1]), float(t[2]))
        if not budgets:
            budgets = {
                "EMAIL": (500, 5000),
                "GOOGLE_ADS": (5000, 50000),
                "SOCIAL_ADS": (3000, 30000),
                "DISPLAY": (2000, 15000),
                "PUSH": (300, 2000),
                "SMS": (500, 3000),
                "AFFILIATE": (1000, 10000),
            }

        edges = xm.get("edge_cases", {})

        statuses = ["RUNNING", "COMPLETED", "SCHEDULED", "PAUSED", "DRAFT", "CANCELLED"]
        rows = []
        today = date.today()

        def pick_duration_days() -> int:
            buckets = xm.get("duration_buckets")
            if buckets and isinstance(buckets, list) and len(buckets) > 0:
                wts = [float(b.get("weight", 1.0)) for b in buckets]
                ws = sum(wts)
                if ws <= 0:
                    wts = [1.0] * len(buckets)
                chosen = self.rng.choices(buckets, weights=wts, k=1)[0]
                dm = int(chosen.get("days_min", 1))
                dx = int(chosen.get("days_max", 7))
                return self.rng.randint(dm, max(dm, dx))
            bucket = self.rng.random()
            if bucket < 0.40:
                return self.rng.randint(1, 7)
            if bucket < 0.85:
                return self.rng.randint(7, 28)
            return self.rng.randint(28, 90)

        list_types = list(weights.keys())
        warr = np.array([weights[k] for k in list_types], dtype=float)
        warr /= warr.sum()

        for i in range(n):
            ctype = str(
                self.rng.choices(list_types, weights=warr.tolist(), k=1)[0],
            )
            lo, hi = budgets.get(ctype, (500, 5000))
            budget_amt = self.rng.uniform(lo, hi)
            start_d = today - timedelta(days=self.rng.randint(0, 365))
            mult = _season_mult_for_date(start_d, xm)

            zero_p = float(edges.get("zero_budget_pct", 0.05))
            invert_p = float(edges.get("invert_dates_pct", 0.02))
            long_p = float(edges.get("long_campaign_pct", 0.03))

            if self.rng.random() < zero_p:
                budget_amt = 0.0
            else:
                budget_amt *= mult

            duration = pick_duration_days()
            if self.rng.random() < long_p:
                duration += self.rng.randint(91, 200)

            end_d = start_d + timedelta(days=duration)
            if self.rng.random() < invert_p:
                start_d, end_d = end_d, start_d

            ar = xm.get("age_ranges") or ["18-34", "25-45", "35-54"]
            co_pool = xm.get("countries_pool") or ["US", "GB", "CA", "DE"]
            int_pool = xm.get("interests_pool") or ["technology", "gadgets", "gaming"]
            aud_obj: Dict[str, Any] = {
                "age_range": self.rng.choice(ar),
                "countries": self.rng.sample(co_pool, k=min(2, len(co_pool))),
                "interests": self.rng.sample(
                    int_pool, k=min(self.rng.randint(1, min(3, len(int_pool))), len(int_pool))
                ),
            }
            seg = xm.get("customer_segments")
            if seg:
                aud_obj["customer_segment"] = self.rng.sample(seg, k=min(2, len(seg)))
            devp = xm.get("device_preferences")
            if devp:
                aud_obj["device_preference"] = self.rng.sample(devp, k=min(1, len(devp)))
            aud = json.dumps(aud_obj)
            ch = self.rng.choice(CHANNELS_BY_TYPE.get(ctype, ["FACEBOOK"]))
            rows.append(
                (
                    f"Campaign {ctype} #{i}",
                    ctype,
                    ch,
                    round(budget_amt, 2),
                    self.rng.choice(["USD", "EUR", "GBP"]),
                    start_d,
                    end_d,
                    aud,
                    self.rng.choice(statuses),
                    "generator",
                ),
            )

        if rows:
            oltp.insert_marketing_campaigns(rows)
            log.info("Seeded marketing_campaigns rows=%s", len(rows))
    def _campaign_ids_lazy(self, oltp: OltpWriter) -> List[int]:
        return oltp.fetch_campaign_ids()
    def _minio_performance(
        self,
        cfg: Config,
        tick_no: int,
        minio: MinioUploader,
        oltp: OltpWriter,
    ) -> None:
        xm = self._xcfg("campaign_performance")
        every = int(xm.get("emit_every_ticks", xm.get("limit_emit_every_ticks", 5)))
        if tick_no % every != 0:
            return

        cids = self._campaign_ids_lazy(oltp)
        if not cids:
            return

        r_min = int(xm.get("rows_min", 80))
        r_max = int(xm.get("rows_max", 200))
        nrows = self.rng.randint(r_min, r_max)

        rpt = datetime.now(timezone.utc).date()
        pb_raw = xm.get("performance_benchmarks") or {}
        pb: Dict[str, Dict[str, tuple[float, float]]] = {}
        for kt, vv in pb_raw.items():
            if isinstance(vv, dict):
                inner: Dict[str, tuple[float, float]] = {}
                for mk, tup in vv.items():
                    if isinstance(tup, (tuple, list)) and len(tup) >= 2:
                        inner[mk] = (float(tup[0]), float(tup[1]))
                pb[kt] = inner
        pe = xm.get("campaign_perf_edge_cases") or {}
        mix_w = _weights_from_xm(
            xm,
            "campaign_type_mix",
            {"EMAIL": 30.0, "GOOGLE_ADS": 35.0, "SOCIAL_ADS": 35.0},
        )
        mix_keys = list(mix_w.keys())

        rows = []

        def _subtype_bench(ct: str) -> Dict[str, tuple[float, float]]:
            bd = pb.get(ct) or pb.get("EMAIL") or {}
            ctr = bd.get("ctr", (0.02, 0.05))
            conv = bd.get("conversion", (0.01, 0.03))
            cpc_rng = bd.get("cpc", (0.10, 0.50))
            return {"ctr": ctr, "conversion": conv, "cpc": cpc_rng}

        for _ in range(min(nrows, len(cids) * 10)):
            cid = self.rng.choice(cids)
            mw = np.array([mix_w[k] for k in mix_keys], dtype=float)
            mw /= mw.sum()
            ctype = str(self.rng.choices(mix_keys, weights=mw.tolist(), k=1)[0])

            bsub = _subtype_bench(ctype)
            ctr_lo, ctr_hi = bsub["ctr"]
            cv_lo, cv_hi = bsub["conversion"]

            impressions = max(50, self.rng.randint(800, 200_000))
            if self.rng.random() < float(pe.get("zero_impressions_pct", 0.03)):
                impressions = 0

            ctr_f = (
                self.rng.triangular(ctr_lo, ctr_hi, (ctr_lo + ctr_hi) / 2)
                if impressions
                else 0.0
            )

            clicks = int(impressions * ctr_f) if impressions else 0

            conv_frac = self.rng.uniform(cv_lo, cv_hi)
            convert = impressions * conv_frac if impressions else 0.0

            if impressions:
                conversions = min(max(0, int(round(convert))), impressions)
            else:
                conversions = 0

            revenue = round(self.rng.uniform(10, max(120.0, impressions / 900 + 120)), 2)
            spend = round(revenue * self.rng.uniform(0.1, 0.95), 2)

            if self.rng.random() < float(pe.get("overspend_pct", 0.05)):
                spend = revenue * 1.1
            neg_roas = self.rng.random() < float(pe.get("negative_roas_pct", 0.01))
            if neg_roas and spend > 0:
                revenue = round(spend * self.rng.uniform(0.2, 0.7), 2)
            ctr_anom = self.rng.random() < float(pe.get("high_ctr_anomaly_pct", 0.02))
            if ctr_anom:
                ctr_f = self.rng.uniform(0.5, 0.65)
                clicks = int(impressions * ctr_f) if impressions else 0

            ctr_c = clicks / impressions if impressions else 0
            cpc = spend / clicks if clicks else 0
            cpa = spend / conversions if conversions else 0
            roas = revenue / spend if spend else 0

            rows.append({
                "campaign_id": cid,
                "report_date": rpt.isoformat(),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "revenue": revenue,
                "currency": self.rng.choice(["USD"]),
                "spend": spend,
                "ctr": round(ctr_c, 4),
                "cpc": round(cpc, 2),
                "cpa": round(cpa, 2),
                "roas": round(roas, 2),
                "unique_users": self.rng.randint(100, max(120, impressions // max(int(ctr_f * 1000), 1))),
                "new_customers": max(1, conversions // max(10, impressions // 10_000)),
                "repeat_customers": self.rng.randint(0, max(0, conversions)),
            })

        df = pd.DataFrame(rows)
        ym = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        fn = f"performance_{datetime.now(timezone.utc).strftime('%Y%m%d')}.parquet"
        path = f"{cfg.minio_prefix_marketing_perf}/{ym}/{fn}"
        minio.put_parquet(cfg.minio_bucket_raw, path, df)
        log.info("MinIO campaign_performance %s rows=%s", path, len(rows))
    def _kafka_email_streams(
        self,
        cfg: Config,
        tick_no: int,
        kafka: KafkaPublisher,
        oltp: OltpWriter,
        users: List[UserRef],
    ) -> None:
        xm = self._xcfg("email_events")
        emin = int(xm.get("events_per_tick_min", 8))
        emax = int(xm.get("events_per_tick_max", 40))
        n = self.rng.randint(emin, emax)
        cmap = self._campaign_ids_lazy(oltp)
        if not cmap or not users:
            return

        ev_types = xm.get("email_event_types") or [
            "EMAIL_SENT",
            "EMAIL_DELIVERED",
            "EMAIL_OPENED",
            "EMAIL_CLICKED",
            "EMAIL_BOUNCED",
            "EMAIL_UNSUBSCRIBED",
            "EMAIL_SPAM_REPORTED",
        ]
        brs = xm.get("bounce_reasons") or [
            "MAILBOX_FULL",
            "INVALID_EMAIL",
            "DOMAIN_NOT_FOUND",
            "SPAM_FILTER",
            "USER_UNKNOWN",
        ]
        ecw = _weights_from_xm(
            xm,
            "email_client_weights",
            {"Gmail": 0.45, "Apple Mail": 0.25, "Outlook": 0.15, "Yahoo": 0.08, "Other": 0.07},
        )
        ek = list(ecw.keys())

        for _ in range(n):
            cid = self.rng.choice(cmap)
            u = self.rng.choice(users)
            et = self.rng.choice(ev_types)
            now = int(datetime.now(timezone.utc).timestamp() * 1000)

            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": et,
                "campaign_id": cid,
                "customer_id": int(u.user_id),
                "email_address": u.email,
                "subject_line": "TechMart deal",
                "send_timestamp": now - 120_000,
                "event_timestamp": now,
                "device_type": self.rng.choice(["MOBILE", "DESKTOP"]),
                "email_client": str(self.rng.choices(ek, weights=[ecw[k] for k in ek], k=1)[0]),
                "link_clicked": "/p/1" if et == "EMAIL_CLICKED" else None,
                "bounce_reason": self.rng.choice(brs) if et == "EMAIL_BOUNCED" else None,
            }

            kafka.publish(
                cfg.kafka_topic_marketing_email,
                key=str(payload["event_id"]),
                value=payload,
            )
