from __future__ import annotations

from dataclasses import dataclass

from redis import Redis


@dataclass(frozen=True)
class RedisConfig:
    url: str


def build_client(cfg: RedisConfig) -> Redis:
    return Redis.from_url(cfg.url, decode_responses=True)
