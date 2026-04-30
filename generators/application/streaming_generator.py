import logging
import random
import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from common.config import Config
from common.connectors.kafka_producer import KafkaPublisher
from common.connectors.minio_uploader import MinioUploader
from common.connectors.oltp import OltpWriter
from common.connectors.redis_publisher import RedisPublisher
from common.factories.events import (
    build_catalog_update,
    build_clickstream_event,
    build_order_payload,
    build_payment_event,
    build_return_record,
    build_shipment_event,
)
from common.factories.reference import (
    ProductRef,
    ReferenceFactory,
    ReferenceState,
    UserRef,
)

log = logging.getLogger("generator")

ALIVE_FILE = "/tmp/generator.alive"


class StreamingGenerator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.factory = ReferenceFactory(seed=cfg.seed)
        self.state = ReferenceState()
        self.oltp: OltpWriter | None = None
        self.kafka: KafkaPublisher | None = None
        self.redis: RedisPublisher | None = None
        self.minio: MinioUploader | None = None
        self.extensions: Any = None
        if cfg.enable_extensions:
            from application.extensions import SyntheticExtensions

            self.extensions = SyntheticExtensions(cfg, random.Random(cfg.seed ^ 917_521))
        self._stop = False
        self._tick_no = 0
        self._payment_seq = 1
        self._shipment_seq = 1

    def _heartbeat(self) -> None:
        try:
            with open(ALIVE_FILE, "w", encoding="utf-8") as fh:
                fh.write(datetime.now(timezone.utc).isoformat())
        except OSError as exc:
            log.warning("Failed to write heartbeat: %s", exc)

    def stop(self, *_: Any) -> None:
        log.info("Stop signal received, finishing current tick")
        self._stop = True

    def _campaign_ids_for_orders(self) -> List[int]:
        if not self.oltp or not self.cfg.enable_extensions:
            return []
        try:
            return self.oltp.fetch_campaign_ids()
        except Exception:
            return []

    def _init_connectors(self) -> None:
        if self.cfg.enable_oltp:
            self.oltp = OltpWriter(self.cfg.oltp_dsn)
            self.oltp.connect()
            if self.cfg.enable_extensions:
                ddl_path = self.cfg.oltp_extensions_sql.strip()
                if not ddl_path:
                    ddl_path = "/app/sql/02b_oltp_marketing_hr_finance.sql"
                self.oltp.ensure_extension_tables(ddl_path)
            self.oltp.ensure_extension_tables(
                "/app/sql/02c_oltp_retail_legacy.sql"
            )
        if self.cfg.enable_kafka:
            self.kafka = KafkaPublisher(self.cfg.kafka_bootstrap)
            topics = {
                self.cfg.kafka_topic_clickstream: 12,
                self.cfg.kafka_topic_orders: 8,
                self.cfg.kafka_topic_payments: 6,
                self.cfg.kafka_topic_shipments: 4,
            }
            if self.cfg.enable_extensions:
                topics.update(
                    {
                        self.cfg.kafka_topic_marketing_email: 4,
                        self.cfg.kafka_topic_seo_organic: 4,
                        self.cfg.kafka_topic_hr_time_tracking: 3,
                        self.cfg.kafka_topic_feature_flag_eval: 2,
                    }
                )
            self.kafka.ensure_topics(topics)
        if self.cfg.enable_redis:
            self.redis = RedisPublisher(self.cfg.redis_url)
            self.redis.connect()
        if self.cfg.enable_minio:
            self.minio = MinioUploader(
                self.cfg.minio_endpoint,
                self.cfg.minio_access_key,
                self.cfg.minio_secret_key,
            )
            self.minio.ensure_bucket(self.cfg.minio_bucket_raw)

    def seed_reference(self) -> None:
        log.info(
            "Seeding reference data: users=%s sellers=%s products=%s",
            self.cfg.seed_users,
            self.cfg.seed_sellers,
            self.cfg.seed_products,
        )
        sellers = [
            self.factory.make_seller(seller_id=i + 1)
            for i in range(self.cfg.seed_sellers)
        ]
        users = [
            self.factory.make_user(user_id=i + 1) for i in range(self.cfg.seed_users)
        ]
        for u in users:
            if self.rng.random() < 0.7:
                u.legacy_crm_customer_id = (
                    f"CRM-{self.rng.randint(1_000_000, 9_999_999)}"
                )
            else:
                u.legacy_crm_customer_id = None
        products: List[ProductRef] = []
        for i in range(self.cfg.seed_products):
            seller = self.rng.choice(sellers)
            products.append(self.factory.make_product(product_id=i + 1, seller=seller))

        if self.oltp:
            seller_ids = self.oltp.insert_sellers(sellers)
            for s, sid in zip(sellers, seller_ids):
                s.seller_id = sid
            user_ids = self.oltp.upsert_users(users)
            for u, uid in zip(users, user_ids):
                u.user_id = uid
            for p in products:
                seller_idx = (p.seller_id - 1) % len(sellers)
                p.seller_id = sellers[seller_idx].seller_id
            product_ids = self.oltp.upsert_products(products)
            for p, pid in zip(products, product_ids):
                p.product_id = pid

        self.state.users = users
        self.state.sellers = sellers
        self.state.products = products
        log.info(
            "Reference seed done: users=%s sellers=%s products=%s",
            len(users),
            len(sellers),
            len(products),
        )
        if (
            self.extensions
            and self.cfg.enable_extensions
            and self.oltp
            and self.state.users
        ):
            try:
                self.extensions.seed_oltp(self.oltp, self.state.users)
            except Exception as exc:
                log.exception("Extension OLTP seed failed: %s", exc)

    def _emit_clickstream(self) -> int:
        count = self.rng.randint(self.cfg.clicks_min, self.cfg.clicks_max)
        for _ in range(count):
            event = build_clickstream_event(self.rng, self.state)
            if self.kafka:
                self.kafka.publish(
                    self.cfg.kafka_topic_clickstream,
                    key=event["session_id"],
                    value=event,
                )
            if self.redis:
                self.redis.publish(self.cfg.redis_channel_clickstream, event)
        return count

    def _emit_orders(self) -> int:
        if not self.state.users or not self.state.products:
            return 0
        count = self.rng.randint(self.cfg.orders_min, self.cfg.orders_max)
        produced = 0
        for _ in range(count):
            user = self.rng.choice(self.state.users)
            n_items = max(1, min(5, int(self.rng.gauss(2.5, 1))))
            chosen_products = self.rng.sample(
                self.state.products, k=min(n_items, len(self.state.products))
            )
            items_meta: List[Dict[str, Any]] = []
            db_items: List[tuple] = []
            raw_subtotal = 0.0
            for prod in chosen_products:
                qty = self.rng.choices([1, 2, 3], weights=[80, 15, 5], k=1)[0]
                line_total = round(prod.price * qty, 2)
                raw_subtotal += line_total
                items_meta.append(
                    {
                        "product_id": prod.product_id,
                        "sku": prod.sku,
                        "quantity": qty,
                        "unit_price": prod.price,
                        "subtotal": line_total,
                        "category": prod.category,
                    }
                )
                db_items.append((prod.product_id, qty, prod.price))

            raw_subtotal = round(raw_subtotal, 2)
            legacy_mode = self.rng.random() < 0.3
            disc_amt = 0.0
            coupon: str | None = None
            camp_id: int | None = None
            leg_cc: str | None = None
            leg_ref: str | None = None
            lineage = "canonical"

            if legacy_mode:
                lineage = "legacy_stub"
                disc_amt = round(
                    raw_subtotal * self.rng.uniform(0.0, 0.14), 2
                )
                if self.rng.random() < 0.35:
                    disc_amt = 0.0
                final_total = round(raw_subtotal - disc_amt, 2)
                coupon = self.rng.choice(
                    ["SAVE15", "WELCOME", None, "EXPIRED2020", ""]
                )
                if coupon == "":
                    coupon = None
                leg_cc = (
                    f"LEG-{self.rng.randint(1000, 9999)}"
                    f"-SF-{self.rng.choice(['A', 'B'])}"
                )
                leg_ref = (
                    f"POS-{self.rng.randint(1_000_000, 9_999_999)}"
                    f"-{self.rng.randint(10, 99)}"
                )
            else:
                if self.rng.random() < 0.5:
                    disc_amt = round(
                        raw_subtotal * self.rng.uniform(0.02, 0.16),
                        2,
                    )
                final_total = round(raw_subtotal - disc_amt, 2)
                coupon = self.rng.choice([None, None, "WELCOME10", "BULK5"])
                cands = self._campaign_ids_for_orders()
                if cands and self.rng.random() < 0.55:
                    camp_id = self.rng.choice(cands)

            commercial = {
                "subtotal_before_discount": raw_subtotal,
                "discount_amount": disc_amt,
                "coupon_code": coupon,
                "campaign_id": camp_id,
                "legacy_campaign_code": leg_cc if legacy_mode else None,
                "legacy_order_ref": leg_ref if legacy_mode else None,
                "order_lineage": lineage,
                "crm_customer_key": getattr(user, "legacy_crm_customer_id", None),
            }

            order_id = 0
            if self.oltp:
                order_id = self.oltp.insert_order(
                    user_id=user.user_id,
                    currency_code=user.currency,
                    total_amount=final_total,
                    status="PENDING",
                    items=db_items,
                    coupon_code=coupon,
                    campaign_id=camp_id,
                    legacy_campaign_code=leg_cc,
                    legacy_order_ref=leg_ref,
                    subtotal_before_discount=raw_subtotal,
                    discount_amount=disc_amt,
                    order_lineage=lineage,
                )

            order_payload = build_order_payload(
                self.rng,
                self.state,
                user,
                items_meta,
                order_id,
                final_total,
                commercial=commercial,
            )
            if self.kafka:
                self.kafka.publish(
                    self.cfg.kafka_topic_orders,
                    key=str(order_id or uuid.uuid4()),
                    value=order_payload,
                )
            if self.redis:
                self.redis.publish(self.cfg.redis_channel_orders, order_payload)
                self.redis.xadd(self.cfg.redis_stream_orders, order_payload)
                self.redis.hincr("techmart:counters:orders_by_country", user.country)

            payment = build_payment_event(
                self.rng,
                user,
                order_id,
                self._payment_seq,
                final_total,
            )
            self._payment_seq += 1
            if self.kafka:
                self.kafka.publish(
                    self.cfg.kafka_topic_payments,
                    key=str(payment["payment_id"]),
                    value=payment,
                )
            if self.redis:
                self.redis.publish(self.cfg.redis_channel_payments, payment)

            if self.rng.random() < 0.4:
                shipment = build_shipment_event(
                    self.rng, order_id, self._shipment_seq, user.country
                )
                self._shipment_seq += 1
                if self.kafka:
                    self.kafka.publish(
                        self.cfg.kafka_topic_shipments,
                        key=str(shipment["shipment_id"]),
                        value=shipment,
                    )
            produced += 1
        return produced

    def _emit_minio_batch(self) -> None:
        if not self.minio:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if self.state.products:
            payments_records = [
                build_payment_event(
                    self.rng,
                    self.rng.choice(self.state.users) if self.state.users else None,
                    order_id=self.rng.randint(1, 100000),
                    payment_id=self._payment_seq + i,
                    total_amount=round(
                        self.rng.choice(self.state.products).price
                        * self.rng.randint(1, 3),
                        2,
                    ),
                )
                for i in range(self.rng.randint(40, 80))
            ]
            self._payment_seq += len(payments_records)
            path_payments = self.minio.put_json_lines(
                self.cfg.minio_bucket_raw,
                self.cfg.minio_prefix_payments,
                payments_records,
                f"payments_{ts}.jsonl",
            )
            log.info("MinIO uploaded payments: %s", path_payments)

            returns_records = [
                build_return_record(
                    self.rng,
                    order_id=self.rng.randint(1, 100000),
                    product=self.rng.choice(self.state.products),
                )
                for _ in range(self.rng.randint(5, 20))
            ]
            path_returns = self.minio.put_csv(
                self.cfg.minio_bucket_raw,
                self.cfg.minio_prefix_returns,
                returns_records,
                f"returns_{ts}.csv",
            )
            log.info("MinIO uploaded returns: %s", path_returns)

            catalog_records = [
                build_catalog_update(self.rng, prod)
                for prod in self.rng.sample(
                    self.state.products,
                    k=min(50, len(self.state.products)),
                )
            ]
            path_catalog = self.minio.put_csv(
                self.cfg.minio_bucket_raw,
                self.cfg.minio_prefix_catalog,
                catalog_records,
                f"catalog_update_{ts}.csv",
            )
            log.info("MinIO uploaded catalog: %s", path_catalog)

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        log.info("Generator config: %s", self.cfg)
        self._init_connectors()
        self.seed_reference()
        self._heartbeat()

        while not self._stop:
            self._tick_no += 1
            tick_start = time.time()
            try:
                clicks = self._emit_clickstream()
                orders = self._emit_orders()
                if self.kafka:
                    self.kafka.flush(2.0)
                if (
                    self.extensions
                    and self.cfg.enable_extensions
                ):
                    try:
                        self.extensions.on_tick_extensions(
                            self.cfg,
                            self._tick_no,
                            self.oltp,
                            self.kafka,
                            self.redis,
                            self.minio,
                            self.state.users,
                        )
                    except Exception as exc:
                        log.exception("Extension tick failed: %s", exc)
                    if self.kafka:
                        self.kafka.flush(2.0)
                if (
                    self.cfg.enable_minio
                    and self._tick_no % self.cfg.minio_batch_ticks == 0
                ):
                    self._emit_minio_batch()
                log.info(
                    "tick=%s clicks=%s orders=%s elapsed=%.2fs",
                    self._tick_no,
                    clicks,
                    orders,
                    time.time() - tick_start,
                )
                self._heartbeat()
            except Exception as exc:
                log.exception("Tick %s failed: %s", self._tick_no, exc)

            sleep_for = max(0.1, self.cfg.tick_seconds - (time.time() - tick_start))
            time.sleep(sleep_for)

        if self.kafka:
            self.kafka.flush(5.0)
        if self.oltp:
            self.oltp.close()
        log.info("Generator stopped after %s ticks", self._tick_no)
