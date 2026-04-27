from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Any

from common.factories.events import build_order_payload
from common.factories.reference import ReferenceState

_SCHEMES_DIR = Path(__file__).resolve().parent.parent / "common" / "schemas"
SCHEMA_PATH = _SCHEMES_DIR / "order_event.schema.json"


def sample_order_event(
    rng: random.Random,
    state: ReferenceState,
    *,
    order_id: int,
) -> dict[str, Any] | None:
    if not state.users or not state.products:
        return None
    user = rng.choice(state.users)
    n_items = max(1, min(5, int(rng.gauss(2.5, 1))))
    chosen = rng.sample(state.products, k=min(n_items, len(state.products)))
    items_meta: list[dict[str, Any]] = []
    total = 0.0
    for prod in chosen:
        qty = rng.choices([1, 2, 3], weights=[80, 15, 5], k=1)[0]
        line_total = round(prod.price * qty, 2)
        total += line_total
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
    return build_order_payload(rng, state, user, items_meta, order_id, total)


def deterministic_order_event(seed: int, state: ReferenceState) -> dict[str, Any] | None:
    rng = random.Random(seed)
    return sample_order_event(rng, state, order_id=1 + (seed % 1_000_000))


def message_key_for_order(value: dict[str, Any]) -> str:
    return str(value.get("order_id") or uuid.uuid4())
