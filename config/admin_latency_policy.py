from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class AdminLatencyPolicy:
    default_days: int = 7
    min_days: int = 1
    max_days: int = 90
    default_brief_limit: int = 10
    default_breakdown_limit: int = 10
    default_breaches_limit: int = 5
    min_limit: int = 1
    min_table_limit: int = 3
    max_table_limit: int = 30
    max_breaches_limit: int = 20
    button_key_max_len: int = 80
    p50_quantile: float = 0.50
    p95_quantile: float = 0.95
    p100_quantile: float = 1.00


DEFAULT_ADMIN_LATENCY_POLICY = AdminLatencyPolicy()
