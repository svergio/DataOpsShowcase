from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterator

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition

from services.common.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class KafkaMessage:
    topic: str
    partition: int
    offset: int
    key: str | None
    value: dict
    timestamp_ms: int | None
    raw: bytes


@dataclass
class MicroBatchResult:
    messages: list[KafkaMessage] = field(default_factory=list)
    last_offsets: dict[int, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.messages)


class MicroBatchKafkaConsumer:
    def __init__(
        self,
        *,
        topic: str,
        group_id: str,
        bootstrap_servers: str | None = None,
        max_messages: int = 5000,
        poll_timeout: float = 5.0,
        max_empty_polls: int = 3,
        auto_offset_reset: str = "earliest",
    ) -> None:
        self.topic = topic
        self.group_id = group_id
        self.bootstrap = bootstrap_servers or os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.max_messages = max_messages
        self.poll_timeout = poll_timeout
        self.max_empty_polls = max_empty_polls
        self.auto_offset_reset = auto_offset_reset
        self._consumer: Consumer | None = None

    def __enter__(self) -> "MicroBatchKafkaConsumer":
        self._consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap,
                "group.id": self.group_id,
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": False,
                "session.timeout.ms": 30000,
                "max.poll.interval.ms": 600000,
            }
        )
        self._consumer.subscribe([self.topic])
        logger.info(
            "kafka consumer initialised",
            extra={
                "extra_payload": {
                    "topic": self.topic,
                    "group_id": self.group_id,
                    "bootstrap": self.bootstrap,
                }
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._consumer:
            try:
                self._consumer.close()
            except Exception as exc:
                logger.warning(
                    "kafka consumer close failure",
                    extra={"extra_payload": {"error": str(exc)}},
                )
            self._consumer = None

    def seek_to_offsets(self, offsets: dict[int, int]) -> None:
        if not offsets or not self._consumer:
            return
        partitions = [TopicPartition(self.topic, int(p), int(o) + 1) for p, o in offsets.items()]
        self._consumer.assign(partitions)
        for tp in partitions:
            self._consumer.seek(tp)
        logger.info(
            "kafka consumer seek",
            extra={"extra_payload": {"topic": self.topic, "offsets": offsets}},
        )

    def fetch(self) -> MicroBatchResult:
        if not self._consumer:
            raise RuntimeError("consumer is not started")
        result = MicroBatchResult()
        empty_polls = 0
        while len(result) < self.max_messages and empty_polls < self.max_empty_polls:
            msg = self._consumer.poll(self.poll_timeout)
            if msg is None:
                empty_polls += 1
                continue
            if msg.error():
                err = msg.error()
                if err.code() == KafkaError._PARTITION_EOF:
                    empty_polls += 1
                    continue
                raise KafkaException(err)
            empty_polls = 0
            try:
                value = json.loads(msg.value().decode("utf-8")) if msg.value() else {}
            except json.JSONDecodeError as exc:
                logger.warning(
                    "kafka payload not json",
                    extra={
                        "extra_payload": {
                            "topic": msg.topic(),
                            "partition": msg.partition(),
                            "offset": msg.offset(),
                            "error": str(exc),
                        }
                    },
                )
                value = {"_raw": msg.value().decode("utf-8", errors="replace") if msg.value() else None}
            key = msg.key().decode("utf-8") if msg.key() else None
            timestamp_ms = msg.timestamp()[1] if msg.timestamp() else None
            kafka_message = KafkaMessage(
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                key=key,
                value=value,
                timestamp_ms=timestamp_ms,
                raw=msg.value() or b"",
            )
            result.messages.append(kafka_message)
            result.last_offsets[kafka_message.partition] = max(
                result.last_offsets.get(kafka_message.partition, -1), kafka_message.offset
            )
        logger.info(
            "kafka micro-batch fetched",
            extra={
                "extra_payload": {
                    "topic": self.topic,
                    "count": len(result),
                    "offsets": result.last_offsets,
                }
            },
        )
        return result

    def get_high_watermarks(self) -> dict[int, int]:
        """Return latest offsets per partition for the subscribed topic."""
        if not self._consumer:
            return {}
        try:
            metadata = self._consumer.list_topics(topic=self.topic, timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "kafka high watermark fetch failed",
                extra={"extra_payload": {"topic": self.topic, "error": str(exc)}},
            )
            return {}
        topic_meta = metadata.topics.get(self.topic)
        if topic_meta is None or topic_meta.error is not None:
            return {}
        result: dict[int, int] = {}
        for partition_id in topic_meta.partitions.keys():
            try:
                _, high = self._consumer.get_watermark_offsets(
                    TopicPartition(self.topic, int(partition_id)),
                    timeout=2.0,
                    cached=False,
                )
                result[int(partition_id)] = int(high)
            except Exception:  # noqa: BLE001
                continue
        return result

    def commit_offsets(self, offsets: dict[int, int]) -> None:
        if not offsets or not self._consumer:
            return
        partitions = [TopicPartition(self.topic, int(p), int(o) + 1) for p, o in offsets.items()]
        self._consumer.poll(0.0)
        try:
            self._consumer.commit(offsets=partitions, asynchronous=False)
        except KafkaException as exc:
            err = exc.args[0] if exc.args else None
            if err is not None and err.code() == KafkaError.ILLEGAL_GENERATION:
                logger.warning(
                    "kafka commit skipped after illegal generation",
                    extra={
                        "extra_payload": {
                            "topic": self.topic,
                            "group_id": self.group_id,
                            "offsets": offsets,
                        }
                    },
                )
                return
            raise
        logger.info(
            "kafka offsets committed",
            extra={"extra_payload": {"topic": self.topic, "offsets": offsets}},
        )


def iter_messages(result: MicroBatchResult) -> Iterator[KafkaMessage]:
    yield from result.messages
