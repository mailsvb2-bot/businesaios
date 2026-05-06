from __future__ import annotations


def resolve_now_ms(*, explicit_now_ms: int | None, fallback_now_ms) -> int:
    """Resolve analysis time from the single explicit source when available."""
    if explicit_now_ms is not None:
        return int(explicit_now_ms)
    return int(fallback_now_ms())


__all__ = ["resolve_now_ms"]
