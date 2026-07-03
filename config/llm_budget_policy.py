from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMBudgetPolicy:
    tenant_tokens_per_day: int = 250_000
    user_tokens_per_day: int = 12_000
    cache_ttl_seconds: float = 30.0


DEFAULT_LLM_BUDGET_POLICY = LLMBudgetPolicy()
