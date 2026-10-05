from __future__ import annotations

import re

_DECIMAL = re.compile(r"^[0-9]+$")


def compare_source_order(left: object, right: object) -> int:
    """Compare provider-native order keys without lexicographic numeric bugs.

    Decimal provider ids are compared numerically (10 > 9 and 010 == 10).
    Non-decimal keys retain deterministic lexical ordering. Missing keys fail
    closed because freshness cannot be established.
    """

    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        raise ValueError("source order keys must be non-empty")
    if _DECIMAL.fullmatch(a) and _DECIMAL.fullmatch(b):
        ai, bi = int(a), int(b)
        return (ai > bi) - (ai < bi)
    return (a > b) - (a < b)


def source_order_is_newer(incoming: object, current: object) -> bool:
    return compare_source_order(incoming, current) > 0
