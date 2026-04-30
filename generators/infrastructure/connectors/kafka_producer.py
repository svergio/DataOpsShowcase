import json
import logging
import time
from typing import Any, Dict

from confluent_kafka import KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic


log = logging.getLogger("connectors.kafka")

# EOS idempotent producer often ends in unrecoverable FATAL after broker quirks; synthetic load does not need it.
DEFAULT_PRODUCER_CONF = {
    "linger.ms": 50,
    "compression.type": "lz4",
    "enable.idempotence": False,
    "acks": "all",
    "retries": 10,
    "socket.keepalive.enable": True,
}


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer_conf = {
            **DEFAULT_PRODUCER_CONF,
            "bootstrap.servers": bootstrap_servers,
        }
        self.producer = Producer(self._producer_conf)

    def _recreate_producer(self) -> None:
        self.producer = Producer(self._producer_conf)
        log.warning("Kafka producer recreated after fatal error")

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
        payload = json.dumps(value, default=str).encode("utf-8")
        key_b = key.encode("utf-8")
        attempts = 0
        while attempts < 16:
            attempts += 1
            try:
                self.producer.produce(
                    topic,
                    key=key_b,
                    value=payload,
                    callback=self._delivery,
                )
                self.producer.poll(0)
                return
            except BufferError:
                self.producer.poll(1.0)
            except KafkaException as exc:
                err = exc.args[0] if exc.args else None
                if err is not None and err.fatal():
                    self._recreate_producer()
                    continue
                raise
        raise RuntimeError("Kafka produce exceeded retry budget")

    def flush(self, timeout: float = 5.0) -> None:
        try:
            self.producer.flush(timeout)
        except KafkaException as exc:
            err = exc.args[0] if exc.args else None
            if err is not None and err.fatal():
                self._recreate_producer()
                return
            raise
