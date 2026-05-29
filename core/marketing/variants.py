from __future__ import annotations

import hashlib
from typing import Dict, Optional

from core.observability.silent import swallow


def choose_variant(
    *,
    user_id: str,
    step_key: str,
    seed: str = "1",
    bandit: dict[str, dict[str, float]] | None = None,
) -> str:
    """Deterministic A/B selection with optional bandit override.

    Returns "a" or "b".
    """
    uid = str(user_id)
    sk = str(step_key)
    sd = str(seed or "1")

    # bandit override
    try:
        if bandit and sk in bandit:
            stats = bandit.get(sk) or {}
            a = float(stats.get("a", 0.0))
            b = float(stats.get("b", 0.0))
            if (a + b) > 0:
                # pick best arm deterministically by user hash
                if a >= b:
                    return "a"
                return "b"
    except Exception:
        swallow(__name__, 'core/marketing/variants.py')


    h = hashlib.sha256(str(f"{uid}|{sk}|{sd}").encode("utf-8")).digest()
    x = int.from_bytes(h[:8], "big") / float(2**64)

    return "a" if x < 0.5 else "b"
