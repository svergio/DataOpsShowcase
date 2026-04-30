from __future__ import annotations

import csv as csv_module
import io
import json
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from domain.constants import DEPTS, ENG_LEVELS, _weights_from_xm

log = logging.getLogger(__name__)


class HrExtensionMixin:
    def _seed_employees(self, oltp: OltpWriter) -> None:
        xm = self._xcfg("employees")
        nemp = int(xm.get("total", 250))
        dept_pool = xm.get("department_weights")
        if isinstance(dept_pool, dict) and dept_pool:
            depts_list = list(dept_pool.keys())
            dw = np.array([float(dept_pool[d]) for d in depts_list], dtype=float)
        else:
            depts_list = list(DEPTS.keys())
            dw = np.array([DEPTS[d] for d in depts_list], dtype=float)
        dw /= dw.sum()

        eng_lv = _weights_from_xm(xm, "engineering_level_weights", ENG_LEVELS)
        flat_lv = _weights_from_xm(xm, "level_weights", ENG_LEVELS)
        sal_rng = xm.get("salary_ranges") or {}

        first = xm.get("first_names") or ["Anna", "Max", "Lena", "Dan", "Ivy", "Owen", "Mia"]
        last = xm.get("last_names") or ["Smith", "Nguyen", "Garcia", "Khan", "Lopez", "Deng", "Berg"]

        rows_phase1 = []
        for i in range(nemp):
            email = f"emp{i+1:04d}@techmart.lab"
            dept = self.rng.choices(depts_list, weights=dw.tolist(), k=1)[0]
            lv_pool = eng_lv if dept == "ENGINEERING" else flat_lv
            lv_keys = list(lv_pool.keys())
            lv_w = list(lv_pool.values())
            lvl = str(self.rng.choices(lv_keys, weights=lv_w, k=1)[0])

            dept_sr = sal_rng.get(dept, {})
            lvl_t = dept_sr.get(lvl) if isinstance(dept_sr, dict) else None
            sal_base_defaults = {"JUNIOR": 65000, "MID": 100000, "SENIOR": 150000,
                                "LEAD": 200000, "PRINCIPAL": 290000}[lvl]
            if isinstance(lvl_t, (tuple, list)) and len(lvl_t) >= 2:
                salary = round(self.rng.uniform(float(lvl_t[0]), float(lvl_t[1])), 2)
            else:
                salary = round(sal_base_defaults * self.rng.uniform(0.9, 1.15), 2)
            hd = date.today() - timedelta(days=self.rng.randint(30, 8 * 365))
            emp_no = f"E{i+1:05d}"

            rs_w = _weights_from_xm(
                xm,
                "remote_status_weights",
                {"FULL_REMOTE": 0.40, "HYBRID": 0.45, "OFFICE": 0.15},
            )
            rs_keys = list(rs_w.keys())
            rs = str(self.rng.choices(rs_keys, weights=[rs_w[k] for k in rs_keys], k=1)[0])

            rows_phase1.append(
                (
                    emp_no,
                    self.rng.choice(first),
                    self.rng.choice(last),
                    email,
                    dept,
                    f"{lvl} Engineer" if dept == "ENGINEERING" else f"{dept.title()} Analyst",
                    lvl,
                    None,
                    hd,
                    None if self.rng.random() > 0.88 else hd + timedelta(days=self.rng.randint(200, 500)),
                    "ACTIVE" if self.rng.random() > 0.06 else ("ON_LEAVE" if self.rng.random() > 0.5 else "TERMINATED"),
                    self.rng.choice(["NYC", "London", "Berlin"]),
                    rs,
                    salary,
                    "USD",
                ),
            )

        oltp.insert_employees(tuple(rows_phase1))
        ids = oltp.fetch_employee_ids_active()
        mgr_pairs = []
        for eid in ids[50:]:
            mgr = self.rng.choice(ids[: max(1, len(ids) // 2)])
            if mgr != eid:
                mgr_pairs.append((eid, mgr))

        if mgr_pairs:
            oltp.update_employee_managers(mgr_pairs[: min(len(mgr_pairs), nemp)])

        log.info("Seeded employees rows=%s", nemp)
    def _minio_hr_performance(
        self,
        cfg: Config,
        tick_no: int,
        minio: MinioUploader,
        oltp: OltpWriter,
    ) -> None:
        xm = self._xcfg("employee_performance")
        every = int(xm.get("emit_every_ticks", 100))
        if tick_no % every != 0:
            return

        eids = oltp.fetch_employee_ids_active()
        if not eids:
            return

        now = datetime.now(timezone.utc)
        q = (now.month - 1) // 3 + 1
        y = now.year
        fn = f"performance_reviews_{y}Q{q}.csv"

        rev = []
        rw = _weights_from_xm(
            xm,
            "rating_weights",
            {"1": 0.03, "2": 0.12, "3": 0.45, "4": 0.30, "5": 0.10},
        )
        rw = {str(k): float(v) for k, v in rw.items()}
        rk = list(rw.keys())
        for eid in eids:
            overall = float(self.rng.choices(rk, weights=[rw[k] for k in rk], k=1)[0])
            reviewer = self.rng.choice(eids)
            promo = overall >= 4.5 and self.rng.random() < 0.3

            rev.append({
                "employee_id": eid,
                "review_period": f"{y}Q{q}",
                "reviewer_id": reviewer,
                "overall_rating": overall,
                "technical_skills": round(overall + self.rng.uniform(-0.5, 0.5), 2),
                "communication": round(overall + self.rng.uniform(-0.5, 0.5), 2),
                "teamwork": round(overall + self.rng.uniform(-0.5, 0.5), 2),
                "goals_met": self.rng.choice(["80%", "90%", "100%"]),
                "promotion_recommended": "Y" if promo else "N",
                "notes": "synthetic review",
                "review_date": date.today().isoformat(),
            })

        path = f"{cfg.minio_prefix_hr_perf}/{y}/Q{q}/{fn}"
        sbuf = io.StringIO()
        if rev:
            w = csv_module.DictWriter(sbuf, fieldnames=list(rev[0].keys()))
            w.writeheader()
            w.writerows(rev)
        minio.put_bytes_at(cfg.minio_bucket_raw, path, sbuf.getvalue().encode("utf-8"), content_type="text/csv")
        log.info("MinIO HR performance reviews=%s", len(rev))
    def _kafka_time_tracking(
        self,
        cfg: Config,
        tick_no: int,
        kafka: KafkaPublisher,
        oltp: OltpWriter,
    ) -> None:
        xm = self._xcfg("time_tracking")
        n = self.rng.randint(
            int(xm.get("events_per_tick_min", 2)),
            int(xm.get("events_per_tick_max", 12)),
        )
        ids = oltp.fetch_employee_ids_active()
        if not ids:
            return

        evt_types = xm.get("time_event_types") or ["CLOCK_IN", "CLOCK_OUT", "BREAK_START", "BREAK_END"]
        offs = xm.get("office_codes") or ["NYC-HQ", "REMOTE"]

        for _ in range(n):
            eid = self.rng.choice(ids)
            evt = self.rng.choice(evt_types)
            ts = datetime.now(timezone.utc)

            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": evt,
                "employee_id": eid,
                "timestamp": ts.isoformat(),
                "location": {
                    "office": self.rng.choice(offs),
                    "ip_address": f"10.0.{self.rng.randint(0,250)}.{self.rng.randint(1,250)}",
                    "geolocation": {"lat": 40.7, "lon": -74.0},
                },
                "device": self.rng.choice(["badge", "desktop", "mobile"]),
            }

            kafka.publish(cfg.kafka_topic_hr_time_tracking, key=str(eid), value=payload)
