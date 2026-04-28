from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from common.connectors.redis_publisher import RedisPublisher
from common.factories.reference import UserRef
from common.xml_config import load_generator_xml

from application.extensions.finance_mixin import FinanceExtensionMixin
from application.extensions.hr_mixin import HrExtensionMixin
from application.extensions.marketing_mixin import MarketingExtensionMixin
from application.extensions.seo_mixin import SeoExtensionMixin
from application.extensions.telemetry_mixin import TelemetryExtensionMixin


@dataclass
class SyntheticExtensions(
    MarketingExtensionMixin,
    SeoExtensionMixin,
    HrExtensionMixin,
    TelemetryExtensionMixin,
    FinanceExtensionMixin,
):
    cfg: Config
    rng: random.Random
    keyword_ranks: Dict[int, int] = field(default_factory=dict)
    _np_rng: np.random.Generator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        seed_mix = (int(self.cfg.seed) ^ 2654435769) % (2**64)
        object.__setattr__(self, "_np_rng", np.random.default_rng(seed_mix))

    def _xcfg(self, name: str) -> Dict[str, Any]:
        return load_generator_xml(name, self.cfg.generator_config_dir)

    def seed_oltp(
        self,
        oltp: OltpWriter,
        users: List[UserRef],
    ) -> None:
        if oltp.get_table_count("marketing_campaigns") == 0:
            self._seed_campaigns(oltp)
        if oltp.get_table_count("seo_keywords") == 0:
            self._seed_seo_keywords(oltp)
        if oltp.get_table_count("feature_flags") == 0:
            self._seed_feature_flags(oltp)
        if oltp.get_table_count("employees") == 0:
            self._seed_employees(oltp)
        if oltp.get_table_count("general_ledger") == 0:
            self._seed_gl(oltp)

    def on_tick_extensions(
        self,
        cfg: Config,
        tick_no: int,
        oltp: Optional[OltpWriter],
        kafka: Optional[KafkaPublisher],
        redis: Optional[RedisPublisher],
        minio: Optional[MinioUploader],
        users: List[UserRef],
    ) -> None:
        if kafka and users:
            if oltp:
                self._kafka_email_streams(cfg, tick_no, kafka, oltp, users)
                self._kafka_time_tracking(cfg, tick_no, kafka, oltp)
            self._kafka_organic_sessions(cfg, tick_no, kafka, users)
            self._kafka_feature_eval(cfg, tick_no, kafka, users)

        if minio:
            self._minio_web_perf_errors(cfg, tick_no, minio)
            if oltp:
                self._minio_performance(cfg, tick_no, minio, oltp)
                self._minio_seo_rankings(cfg, tick_no, minio, oltp)
                self._minio_hr_performance(cfg, tick_no, minio, oltp)

        if redis:
            self._redis_web_vitals(cfg, tick_no, redis)
