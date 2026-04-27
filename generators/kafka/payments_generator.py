from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Any

from common.factories.events import build_payment_event
from common.factories.reference import UserRef

_SCHEMES_DIR = Path(__file__).resolve().parent.parent / "common" / "schemas"
SCHEMA_PATH = _SCHEMES_DIR / "payment_event.schema.json"


def sample_payment_event(
    rng: random.Random,
    user: UserRef,
    *,
    order_id: int,
    payment_id: int,
    total_amount: float,
) -> dict[str, Any]:
    return build_payment_event(rng, user, order_id, payment_id, total_amount)


def deterministic_payment_event(seed: int, user: UserRef) -> dict[str, Any]:
    rng = random.Random(seed)
    oid = 1000 + (seed % 10_000)
    pid = 1 + (seed % 1_000_000)
    amt = round(10.0 + (seed % 1000) / 10, 2)
    return build_payment_event(rng, user, oid, pid, amt)


def message_key_for_payment(value: dict[str, Any]) -> str:
    return str(value.get("payment_id") or uuid.uuid4())
