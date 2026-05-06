from __future__ import annotations

CANONICAL_TRACE_STAGES: tuple[str, ...] = (
    "request",
    "world_state",
    "decision",
    "executor",
    "verification",
    "memory",
)

__all__ = ["CANONICAL_TRACE_STAGES"]
