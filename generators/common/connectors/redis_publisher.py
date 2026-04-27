import json
import logging
import time
from typing import Any, Dict

import redis


log = logging.getLogger("connectors.redis")


class RedisPublisher:
    def __init__(self, url: str):
        self.url = url
        self.client: redis.Redis | None = None

    def connect(self, retries: int = 20, delay: float = 2.0) -> None:
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.client = redis.from_url(self.url, decode_responses=False)
                self.client.ping()
                log.info("Redis connected (attempt %s)", attempt)
                return
            except Exception as exc:
                last_err = exc
                log.warning("Redis connect attempt %s failed: %s", attempt, exc)
                time.sleep(delay)
        raise RuntimeError(f"Cannot connect to Redis: {last_err}")

    def _client(self) -> redis.Redis:
        if self.client is None:
            raise RuntimeError("Redis client not initialized")
        return self.client

    def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        self._client().publish(
            channel, json.dumps(payload, default=str).encode("utf-8")
        )

    def xadd(self, stream: str, payload: Dict[str, Any], maxlen: int = 10000) -> None:
        flat = {
            k: (v if isinstance(v, (str, int, float)) else json.dumps(v, default=str))
            for k, v in payload.items()
            if v is not None
        }
        self._client().xadd(stream, flat, maxlen=maxlen, approximate=True)

    def set_state(self, key: str, payload: Dict[str, Any], ttl: int = 3600) -> None:
        self._client().setex(
            key, ttl, json.dumps(payload, default=str).encode("utf-8")
        )

    def hincr(self, key: str, field: str, amount: int = 1) -> None:
        self._client().hincrby(key, field, amount)
