from __future__ import annotations

_TRUE = frozenset({"1", "true", "yes", "on"})


def parse_bool(value) -> bool:
    return str(value or "").strip().lower() in _TRUE


__all__ = ["parse_bool"]
