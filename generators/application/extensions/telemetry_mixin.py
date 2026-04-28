from __future__ import annotations

import csv as csv_module
import io
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from common.connectors.redis_publisher import RedisPublisher
from common.factories.reference import UserRef
from domain.constants import _weights_from_xm

log = logging.getLogger(__name__)


class TelemetryExtensionMixin:
    def _seed_feature_flags(self, oltp: OltpWriter) -> None:
        xm = self._xcfg("feature_flags")
        definitions = xm.get("flag_definitions")
        seed_rows = []
        if definitions:
            for d in definitions:
                k = d.get("key")
                if not k:
                    continue
                tgt = d.get("targeting", "{}")
                seed_rows.append(
                    (
                        k,
                        d.get("flag_name", k),
                        d.get("description", ""),
                        bool(d.get("enabled", False)),
                        int(d.get("rollout", 0)),
                        tgt if tgt.strip() else "{}",
                    ),
                )
        if not seed_rows:
            seed_rows = [
                (
                    "new_checkout_flow",
                    "New checkout flow",
                    "A/B test checkout",
                    True,
                    25,
                    json.dumps({"customer_segments": ["VIP", "REGULAR"]}),
                ),
                (
                    "crypto_payments",
                    "Cryptocurrency payments",
                    "",
                    False,
                    5,
                    json.dumps({"countries": ["US", "GB"]}),
                ),
                (
                    "ai_recommendations",
                    "AI recommendations",
                    "Fully rolled",
                    True,
                    100,
                    "{}",
                ),
            ]
        extras: List[tuple[Any, ...]] = []
        extra_n = int(xm.get("extra_random_flags", 9))
        extra_roll_max = int(xm.get("extra_random_rollout_max", 60))
        titles = ["dark_mode_shop", "fast_return_portal", "loyalty_bonus_v3"]
        self.rng.shuffle(titles)
        for fk in titles[:extra_n]:
            extras.append(
                (
                    fk,
                    fk.replace("_", " ").title(),
                    "",
                    self.rng.random() < 0.5,
                    self.rng.randint(10, extra_roll_max),
                    json.dumps({}) if self.rng.random() > 0.5 else "{}",
                ),
            )
        cap = int(xm.get("total", 12))
        merged = seed_rows + extras[: max(0, cap - len(seed_rows))]
        oltp.insert_feature_flags(merged)
        log.info("Seeded feature_flags")

    def _minio_web_perf_errors(
        self,
        cfg: Config,
        tick_no: int,
        minio: MinioUploader,
    ) -> None:
        xv = self._xcfg("web_vitals")
        xe = self._xcfg("error_logs")

        if tick_no % int(xv.get("emit_every_ticks", 4)) == 0:
            nrows = int(xv.get("records_per_emit", 120))

            default_tb: Dict[str, Dict[str, tuple[float, float]]] = {
                "DESKTOP": {"lcp": (1200, 2500), "fid": (50, 100), "cls": (0.05, 0.15), "ttfb": (200, 600)},
                "MOBILE": {"lcp": (2000, 4000), "fid": (100, 300), "cls": (0.10, 0.25), "ttfb": (400, 1200)},
            }
            ov = xv.get("device_benchmarks") or {}
            benches: Dict[str, Dict[str, tuple[float, float]]] = {k: dict(v) for k, v in default_tb.items()}
            for dn, vals in ov.items():
                dk = dn.upper()
                if dk not in benches:
                    benches[dk] = {}
                for mn, tup in vals.items():
                    if isinstance(tup, (tuple, list)) and len(tup) >= 2:
                        benches[dk][mn] = (float(tup[0]), float(tup[1]))
            conn_m = xv.get("connection_multipliers") or {"5G": 1.0, "WiFi": 1.1, "4G": 1.5, "3G": 3.0, "2G": 8.0}
            dev_choices = [d for d in benches.keys()]
            wt = xv.get("device_mix_weights") if isinstance(xv.get("device_mix_weights"), dict) else None
            url_pool = xv.get("page_urls_sample") or ["/", "/products", "/cart"]
            pve = xv.get("perf_edge_cases") or {}

            perf_rows = []
            for _ in range(nrows):
                if wt and len(wt) == len(dev_choices):
                    dev = str(self.rng.choices(dev_choices, weights=[float(wt.get(d, 1.0)) for d in dev_choices], k=1)[0])
                else:
                    dev = self.rng.choice(dev_choices)
                b = benches.get(dev) or benches["DESKTOP"]
                lcp = self.rng.uniform(*b["lcp"])
                fid = self.rng.uniform(*b["fid"])
                cls = self.rng.uniform(*b["cls"])
                ttfb = self.rng.uniform(*b["ttfb"])

                conn_types = list(conn_m.keys())
                conn = str(self.rng.choice(conn_types))
                mult = float(conn_m.get(conn, 1.0))
                lcp *= mult
                fid *= mult
                ttfb *= mult

                if self.rng.random() < float(pve.get("slow_lcp_pct", 0.05)):
                    lcp *= 4
                if self.rng.random() < float(pve.get("negative_fid_pct", 0.02)):
                    fid = -lcp * 0.001
                if self.rng.random() < float(pve.get("zero_metrics_pct", 0.01)):
                    lcp = fid = cls = ttfb = 0.0

                perf_rows.append({
                    "metric_id": f"pf_{uuid.uuid4().hex[:12]}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": f"sess_{uuid.uuid4().hex[:10]}",
                    "page_url": self.rng.choice(url_pool),
                    "browser": self.rng.choice(["Chrome", "Safari", "Firefox"]),
                    "lcp": round(lcp, 2),
                    "fid": round(fid, 2),
                    "cls": round(cls, 6),
                    "ttfb": round(ttfb, 2),
                    "fcp": round(lcp * 0.92, 2),
                    "tti": round(ttfb + lcp / 1000 + 220, 2),
                    "tbt": round(self.rng.uniform(10, 60), 2),
                    "device_type": dev,
                    "connection_type": conn,
                    "country_code": self.rng.choice(["US", "GB", "DE"]),
                })

            ym = datetime.now(timezone.utc).strftime("%Y/%m/%d")
            fn_h = datetime.now(timezone.utc).strftime("%Y%m%d_%H")
            path = f"{cfg.minio_prefix_telemetry_perf}/{ym}/perf_metrics_{fn_h}.parquet"
            minio.put_parquet(cfg.minio_bucket_raw, path, pd.DataFrame(perf_rows))

        if tick_no % int(xe.get("emit_every_ticks", 7)) == 0:
            nln = int(xe.get("lines_per_emit", 35))
            etw = _weights_from_xm(
                xe,
                "error_type_weights",
                {"JAVASCRIPT_ERROR": 0.60, "API_ERROR": 0.20, "NETWORK_ERROR": 0.10,
                 "PAYMENT_ERROR": 0.05, "RESOURCE_NOT_FOUND": 0.03, "TIMEOUT": 0.02},
            )
            sew = _weights_from_xm(
                xe,
                "severity_weights",
                {"CRITICAL": 0.05, "ERROR": 0.25, "WARNING": 0.45, "INFO": 0.25},
            )
            et_keys = list(etw.keys())
            se_keys = list(sew.keys())
            msg_pool = xe.get("common_error_messages") or [
                "Cannot read property 'price' of undefined",
                "NetworkError: Failed to fetch",
            ]
            lines = []
            for _ in range(nln):
                et = str(self.rng.choices(et_keys, weights=[etw[k] for k in et_keys], k=1)[0])
                sev = str(self.rng.choices(se_keys, weights=[sew[k] for k in se_keys], k=1)[0])
                lines.append({
                    "error_id": f"err_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": et,
                    "severity": sev,
                    "message": self.rng.choice(msg_pool),
                    "stack_trace": "Error at ProductCard.render",
                    "page_url": "/products/wireless-headphones",
                    "user_agent": "Mozilla/5.0",
                    "session_id": f"sess_{uuid.uuid4().hex[:8]}",
                    "customer_id": self.rng.randint(1, 50_000),
                    "browser": "Chrome",
                    "browser_version": "122.0.0",
                    "os": "Windows",
                    "device_type": "DESKTOP",
                    "additional_context": json.dumps({"product_id": 5432, "action": "add_to_cart"}),
                })

            ym = datetime.now(timezone.utc).strftime("%Y/%m/%d")
            fn = f"errors_{datetime.now(timezone.utc).strftime('%Y%m%d_%H')}.jsonl"
            path = f"{cfg.minio_prefix_telemetry_errors}/{ym}/{fn}"
            minio.put_ndjson(cfg.minio_bucket_raw, path, lines)
    def _redis_web_vitals(
        self,
        cfg: Config,
        tick_no: int,
        redis: RedisPublisher,
    ) -> None:
        xv = self._xcfg("web_vitals")
        every = int(xv.get("redis_aggregate_every_ticks", 3))
        if tick_no % every != 0:
            return

        hr = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        key = f"{cfg.redis_key_web_vitals_prefix}:{hr}"
        redis.hset_expire(
            key,
            {
                "lcp_p95": str(self.rng.randint(1800, 3200)),
                "fid_p95": str(self.rng.randint(50, 120)),
                "cls_p95": str(round(self.rng.uniform(0.06, 0.18), 4)),
            },
            ttl_seconds=86400,
        )
    def _kafka_feature_eval(
        self,
        cfg: Config,
        tick_no: int,
        kafka: KafkaPublisher,
        users: List[UserRef],
    ) -> None:
        xf = self._xcfg("feature_flags")
        every = int(xf.get("feature_eval_every_ticks", 4))
        if tick_no % every != 0 or not users:
            return

        u = self.rng.choice(users)
        fds = xf.get("flag_definitions") or []
        keys_pool = [d.get("key") for d in fds if d.get("key")]
        if not keys_pool:
            keys_pool = ["new_checkout_flow", "crypto_payments"]
        fk = str(self.rng.choice(keys_pool))
        payload = {
            "event_type": "FEATURE_FLAG_EVALUATED",
            "flag_key": fk,
            "session_id": f"s_{uuid.uuid4().hex[:8]}",
            "customer_id": int(u.user_id),
            "evaluated_to": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        kafka.publish(cfg.kafka_topic_feature_flag_eval, key=fk, value=payload)
