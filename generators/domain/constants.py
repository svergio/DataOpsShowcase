from __future__ import annotations

import random
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np


CHANNELS_BY_TYPE: Dict[str, List[str]] = {
    "EMAIL": ["EMAIL", "FACEBOOK"],
    "GOOGLE_ADS": ["GOOGLE"],
    "SOCIAL_ADS": ["FACEBOOK", "INSTAGRAM", "TIKTOK"],
    "DISPLAY": ["GOOGLE"],
    "PUSH": ["GOOGLE"],
    "SMS": ["SMS"],
    "AFFILIATE": ["GOOGLE", "FACEBOOK"],
}

SEO_CATEGORIES = {
    "PRODUCT": 0.40,
    "BRAND": 0.20,
    "CATEGORY": 0.25,
    "INFORMATIONAL": 0.10,
    "TRANSACTIONAL": 0.05,
}

DEPTS = {
    "ENGINEERING": 0.35,
    "PRODUCT": 0.08,
    "MARKETING": 0.12,
    "SALES": 0.15,
    "OPERATIONS": 0.10,
    "CUSTOMER_SUPPORT": 0.12,
    "DATA": 0.05,
    "FINANCE": 0.02,
    "HR": 0.01,
}

ENG_LEVELS = {
    "JUNIOR": 0.25,
    "MID": 0.40,
    "SENIOR": 0.25,
    "LEAD": 0.08,
    "PRINCIPAL": 0.02,
}

CHART_ACCOUNTS = {
    "1010": ("Cash - Operating Account", "ASSET"),
    "1020": ("Cash - Payment Gateway", "ASSET"),
    "1200": ("Accounts Receivable", "ASSET"),
    "4000": ("Product Sales", "REVENUE"),
    "5000": ("Cost of Goods Sold", "EXPENSE"),
    "5100": ("Marketing Expenses", "EXPENSE"),
    "5200": ("Payroll Expenses", "EXPENSE"),
    "5400": ("Payment Processing Fees", "EXPENSE"),
    "5500": ("Refunds", "EXPENSE"),
}


def _weights_from_xm(xm: Dict[str, Any], key: str, default: Dict[str, float]) -> Dict[str, float]:
    w = xm.get(key)
    if isinstance(w, dict) and len(w) > 0:
        out = {str(k): float(v) for k, v in w.items()}
        s = sum(out.values())
        if s > 0:
            return out
    return dict(default)


def _season_mult_for_date(d: date, xm: Dict[str, Any]) -> float:
    s = xm.get("seasonality")
    if isinstance(s, dict) and d.month in s:
        return float(s[d.month])
    return _season_mult(d)


def _sample_initial_rank(
    rng: random.Random,
    rd: Dict[str, float],
    *,
    np_rng: Optional[np.random.Generator] = None,
) -> int:
    if not rd:
        npr = np_rng if np_rng is not None else np.random.default_rng(0)
        return max(1, min(101, round(float(npr.lognormal(3.0, 0.9)))))
    b = _weighted_choice(rng, rd)
    if b == "top_3":
        return rng.randint(1, 3)
    if b == "top_10":
        return rng.randint(4, 10)
    if b == "top_20":
        return rng.randint(11, 20)
    if b == "top_50":
        return rng.randint(21, 50)
    return rng.randint(51, 120)


def _weighted_choice(rng: random.Random, weights: Dict[str, float]) -> str:
    items = list(weights.keys())
    probs = np.array([weights[k] for k in items], dtype=float)
    probs /= probs.sum()
    return str(rng.choices(items, weights=probs, k=1)[0])


def _season_mult(d: date) -> float:
    m = d.month
    if m == 11:
        return 10.0
    if m == 12:
        return 5.0
    if m in (8, 9):
        return 3.0
    if m in (6, 7):
        return 2.0
    return 1.0
