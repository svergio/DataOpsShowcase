from __future__ import annotations

import random

import pytest

pytest.importorskip("faker")

from common.factories.events import build_clickstream_event, build_order_payload, build_payment_event
from common.factories.reference import ProductRef, ReferenceState, UserRef
from common.factories import reference as ref_mod


def _user(uid: int = 1) -> UserRef:
    return ref_mod.UserRef(
        user_id=uid,
        email="a@b.c",
        full_name="Test",
        country="US",
        currency="USD",
    )


def test_build_payment_event_shape() -> None:
    rng = random.Random(42)
    p = build_payment_event(rng, _user(), 100, 1, 25.0)
    assert p["order_id"] == 100
    assert "payment_id" in p
    assert p["amount"] == 25.0


def test_build_order_payload() -> None:
    rng = random.Random(0)
    state = ReferenceState()
    u = _user(1)
    p = _product()
    state.users = [u]
    state.products = [p]
    line = {
        "product_id": p.product_id,
        "sku": p.sku,
        "quantity": 1,
        "unit_price": p.price,
        "subtotal": p.price,
        "category": p.category,
    }
    o = build_order_payload(rng, state, u, [line], 42, 99.0)
    assert o["order_id"] == 42
    assert o["event_type"] == "ORDER_CREATED"


def _product() -> ProductRef:
    return ref_mod.ProductRef(
        product_id=1,
        seller_id=1,
        sku="SKU-1",
        product_name="P",
        category="C",
        brand="B",
        price=10.0,
        is_active=True,
    )


def test_build_clickstream_event() -> None:
    rng = random.Random(1)
    state = ReferenceState()
    state.users = [_user(1)]
    state.products = [_product()]
    e = build_clickstream_event(rng, state)
    assert "event_id" in e
    assert "timestamp" in e
