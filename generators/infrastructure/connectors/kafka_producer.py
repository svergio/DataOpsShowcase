import json
import logging
import time
from typing import Any, Dict

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic


log = logging.getLogger("connectors.kafka")


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "linger.ms": 50,
                "compression.type": "lz4",
                "enable.idempotence": True,
            }
        )

    def ensure_topics(
        self, topics: Dict[str, int], retries: int = 20, delay: float = 3.0
    ) -> None:
        admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        for attempt in range(1, retries + 1):
            try:
                meta = admin.list_topics(timeout=5)
                existing = set(meta.topics.keys())
                missing = [
                    NewTopic(name, num_partitions=parts, replication_factor=1)
                    for name, parts in topics.items()
                    if name not in existing
                ]
                if missing:
                    futures = admin.create_topics(missing)
                    for name, fut in futures.items():
                        try:
                            fut.result()
                            log.info("Created kafka topic %s", name)
                        except Exception as exc:
                            log.warning("Topic %s create error: %s", name, exc)
                return
            except Exception as exc:
                log.warning(
                    "Kafka admin attempt %s failed: %s", attempt, exc
                )
                time.sleep(delay)
        raise RuntimeError("Kafka admin unreachable")

    @staticmethod
    def _delivery(err, msg) -> None:
        if err is not None:
            log.warning("Kafka delivery failed: %s", err)

    def publish(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        self.producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(value, default=str).encode("utf-8"),
            callback=self._delivery,
        )
        self.producer.poll(0)

    def flush(self, timeout: float = 5.0) -> None:
        self.producer.flush(timeout)
