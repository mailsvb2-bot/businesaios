from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMBudgetPolicy:
    tenant_tokens_per_day: int = 250_000
    user_tokens_per_day: int = 12_000
    cache_ttl_seconds: float = 30.0
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


DEFAULT_LLM_BUDGET_POLICY = LLMBudgetPolicy()
