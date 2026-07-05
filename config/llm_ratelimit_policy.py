from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class LLMRateLimitPolicy:
    tenant_rps: float = 0.0
    tenant_burst: int = 0
    min_rps: float = 0.0
    min_burst: int = 1
    check_cost: int = 1
    global_tenant_id: str = "__global__"
    global_subject: str = "__provider__"
    global_bucket: str = "llm:global"
    tenant_subject: str = "__tenant__"
    tenant_bucket: str = "llm:tenant"


DEFAULT_LLM_RATELIMIT_POLICY = LLMRateLimitPolicy()
