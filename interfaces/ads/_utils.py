from __future__ import annotations

from typing import Optional


def maybe_float(x) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None
