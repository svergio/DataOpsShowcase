import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from .reference import ProductRef, ReferenceState, UserRef


CLICK_TYPES = [
    "PAGE_VIEW",
    "PRODUCT_VIEW",
    "ADD_TO_CART",
    "REMOVE_FROM_CART",
    "CHECKOUT_START",
    "SEARCH",
    "FILTER_APPLIED",
]

ORDER_STATUSES = [
    "PENDING",
    "CONFIRMED",
    "PROCESSING",
    "SHIPPED",
    "DELIVERED",
    "CANCELLED",
]

PAYMENT_METHODS = ["CREDIT_CARD", "DEBIT_CARD", "PAYPAL", "STRIPE", "BANK_TRANSFER"]
PAYMENT_STATUSES = ["INITIATED", "AUTHORIZED", "CAPTURED", "DECLINED"]
DECLINE_REASONS = [
    "INSUFFICIENT_FUNDS",
    "CARD_EXPIRED",
    "FRAUD_SUSPECTED",
    "INVALID_CVV",
    "CARD_BLOCKED",
]
DEVICE_TYPES = ["MOBILE", "DESKTOP", "TABLET"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def build_clickstream_event(
    rng: random.Random, state: ReferenceState
) -> Dict[str, Any]:
    user = rng.choice(state.users) if state.users and rng.random() < 0.85 else None
    product = rng.choice(state.products) if state.products else None
    event_type = rng.choice(CLICK_TYPES)
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:16]}",
        "event_type": event_type,
        "timestamp": _now_ms(),
        "session_id": f"sess_{uuid.uuid4().hex[:12]}",
        "customer_id": user.user_id if user else None,
        "product_id": product.product_id if product else None,
        "category": product.category if product else None,
        "page_url": f"/products/{product.product_id}" if product else "/",
        "device_type": rng.choice(DEVICE_TYPES),
        "country_code": user.country if user else "US",
        "metadata": {
            "viewport": rng.choice(["1920x1080", "375x812", "1440x900"]),
            "referrer": rng.choice(["google", "direct", "facebook", "newsletter"]),
        },
    }


def build_order_payload(
    rng: random.Random,
    state: ReferenceState,
    user: UserRef,
    items: List[Dict[str, Any]],
    order_id: int,
    total_amount: float,
    commercial: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "event_id": f"ord_evt_{uuid.uuid4().hex[:16]}",
        "event_type": "ORDER_CREATED",
        "order_id": order_id,
        "order_number": f"ORD-{datetime.now(timezone.utc).year}-{order_id:06d}",
        "customer_id": user.user_id,
        "country_code": user.country,
        "timestamp": _now_iso(),
        "previous_status": None,
        "new_status": "PENDING",
        "total_amount": round(total_amount, 2),
        "currency": user.currency,
        "items_count": len(items),
        "items": items,
        "metadata": {"source": "data_generator", "triggered_by": "tick"},
    }
    if commercial:
        out["commercial"] = commercial
    return out


def build_payment_event(
    rng: random.Random,
    user: UserRef,
    order_id: int,
    payment_id: int,
    total_amount: float,
) -> Dict[str, Any]:
    method = rng.choices(
        PAYMENT_METHODS, weights=[45, 25, 20, 8, 2], k=1
    )[0]
    status = rng.choices(
        ["CAPTURED", "AUTHORIZED", "DECLINED", "FAILED"],
        weights=[88, 6, 4, 2],
        k=1,
    )[0]
    decline_reason = rng.choice(DECLINE_REASONS) if status == "DECLINED" else None
    return {
        "event_id": f"pay_evt_{uuid.uuid4().hex[:16]}",
        "event_type": f"PAYMENT_{status}",
        "payment_id": payment_id,
        "order_id": order_id,
        "transaction_id": f"TXN-{method}-{uuid.uuid4().hex[:10].upper()}",
        "amount": round(total_amount, 2),
        "currency": user.currency,
        "payment_method": method,
        "gateway": rng.choice(["stripe", "paypal", "adyen", "internal"]),
        "status": status,
        "decline_reason": decline_reason,
        "risk_score": rng.randint(0, 100),
        "timestamp": _now_ms(),
    }


def build_shipment_event(
    rng: random.Random, order_id: int, shipment_id: int, country: str
) -> Dict[str, Any]:
    status = rng.choice(
        ["LABEL_CREATED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]
    )
    carrier_pool = {
        "US": ["FedEx", "UPS", "USPS"],
        "GB": ["Royal Mail", "DHL"],
        "DE": ["Deutsche Post", "DHL"],
        "JP": ["Japan Post", "DHL"],
        "CN": ["SF Express", "DHL"],
    }.get(country, ["DHL"])
    carrier = rng.choice(carrier_pool)
    return {
        "event_id": f"ship_evt_{uuid.uuid4().hex[:16]}",
        "event_type": status,
        "shipment_id": shipment_id,
        "order_id": order_id,
        "tracking_number": f"{carrier[:3].upper()}{rng.randint(10**11, 10**12 - 1)}",
        "carrier": carrier,
        "status": status,
        "country": country,
        "timestamp": _now_iso(),
    }


def build_return_record(
    rng: random.Random, order_id: int, product: ProductRef
) -> Dict[str, Any]:
    return {
        "return_id": uuid.uuid4().hex[:10],
        "order_id": order_id,
        "product_id": product.product_id,
        "return_reason": rng.choice(
            ["DEFECTIVE_PRODUCT", "WRONG_ITEM", "NOT_AS_DESCRIBED", "CHANGED_MIND"]
        ),
        "quantity": rng.randint(1, 2),
        "refund_amount": round(product.price * rng.uniform(0.5, 1.0), 2),
        "currency": "USD",
        "status": rng.choice(["PENDING", "APPROVED", "COMPLETED"]),
        "requested_at": _now_iso(),
        "notes": "auto-generated return record",
    }


def build_catalog_update(
    rng: random.Random, product: ProductRef
) -> Dict[str, Any]:
    return {
        "product_id": product.product_id,
        "seller_id": product.seller_id,
        "product_name": product.product_name,
        "brand": product.brand,
        "category": product.category,
        "price": round(product.price * rng.uniform(0.9, 1.1), 2),
        "currency": "USD",
        "stock": rng.randint(0, 500),
        "is_active": product.is_active,
        "updated_at": _now_iso(),
    }
