from __future__ import annotations

from dataclasses import dataclass

CANON_ADMIN_LATENCY_READ_MODEL_POLICY = True


@dataclass(frozen=True)
class AdminLatencyReadModelPolicy:
    """Data-only bounds for admin latency dashboard read models."""

    default_brief_limit: int = 20
    min_table_limit: int = 1
    max_table_limit: int = 100


DEFAULT_ADMIN_LATENCY_READ_MODEL_POLICY = AdminLatencyReadModelPolicy()

__all__ = [
    "AdminLatencyReadModelPolicy",
    "CANON_ADMIN_LATENCY_READ_MODEL_POLICY",
    "DEFAULT_ADMIN_LATENCY_READ_MODEL_POLICY",
]
