from __future__ import annotations

import time
import uuid


def make_idempotency_key(*, prefix: str) -> str:
    """Generate a stable-enough idempotency key.

    Design goals:
    - No global state
    - Human-readable
    - Low collision probability

    NOTE: Prefix should include domain digest (e.g. plan digest).
    """

    ts_ms = int(time.time() * 1000)
    rnd = uuid.uuid4().hex[:12]
    p = str(prefix).strip() or "key"
    return f"{p}:{ts_ms}:{rnd}"
