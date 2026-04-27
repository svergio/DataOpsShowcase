from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from common.factories.events import build_clickstream_event
from common.factories.reference import ReferenceState

_SCHEMES_DIR = Path(__file__).resolve().parent.parent / "common" / "schemas"
SCHEMA_PATH = _SCHEMES_DIR / "clickstream.schema.json"


def sample_clickstream_event(rng: random.Random, state: ReferenceState) -> dict[str, Any]:
    return build_clickstream_event(rng, state)


def deterministic_clickstream_event(seed: int, state: ReferenceState) -> dict[str, Any]:
    rng = random.Random(seed)
    return build_clickstream_event(rng, state)
