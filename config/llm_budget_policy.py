from __future__ import annotations

import os
from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMBudgetPolicy:
    tenant_tokens_per_day: int = 250_000
    user_tokens_per_day: int = 12_000
    cache_ttl_seconds: float = 30.0
    # Optional rolling-calendar caps (UTC ISO week / calendar month). None = off.
    tenant_tokens_per_week: int | None = None
    user_tokens_per_week: int | None = None
    tenant_tokens_per_month: int | None = None
    user_tokens_per_month: int | None = None

    def __post_init__(self) -> None:
        for name in ("tenant_tokens_per_day", "user_tokens_per_day"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        for name in ("tenant_tokens_per_week", "user_tokens_per_week", "tenant_tokens_per_month", "user_tokens_per_month"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer")


def _optional_period_caps_from_env() -> dict[str, int]:
    """LLM_{TENANT,USER}_TOKENS_PER_{WEEK,MONTH}; unset/empty keeps the cap off. Bad values fail boot."""
    caps = {}
    for name in ("tenant_tokens_per_week", "user_tokens_per_week", "tenant_tokens_per_month", "user_tokens_per_month"):
        if raw := os.environ.get(f"LLM_{name.upper()}", "").strip():
            if not raw.isdecimal():
                raise ValueError(f"LLM_{name.upper()} must be a non-negative integer")
            caps[name] = int(raw)
    return caps


DEFAULT_LLM_BUDGET_POLICY = LLMBudgetPolicy(**_optional_period_caps_from_env())
