from __future__ import annotations

import random

import numpy as np
import pytest

from domain.constants import _sample_initial_rank


def test_sample_initial_rank_empty_rd_uses_np_rng_deterministically() -> None:
    rng = random.Random(1)
    np_r = np.random.default_rng(4242)
    a = _sample_initial_rank(rng, {}, np_rng=np_r)
    np_r2 = np.random.default_rng(4242)
    b = _sample_initial_rank(rng, {}, np_rng=np_r2)
    assert a == b
    assert 1 <= a <= 101


def test_sample_initial_rank_buckets_respect_ranges() -> None:
    rng = random.Random(0)
    rd = {
        "top_3": 1.0,
        "top_10": 0.0,
        "top_20": 0.0,
        "top_50": 0.0,
        "beyond": 0.0,
    }
    r = _sample_initial_rank(rng, rd, np_rng=np.random.default_rng(0))
    assert 1 <= r <= 3
