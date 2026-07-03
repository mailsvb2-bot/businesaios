from __future__ import annotations

from dataclasses import dataclass, field

from core.llm.circuit import CircuitConfig
from core.llm.sampling import DebugSampling

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class MarketingLLMPolicy:
    provider: str = "openai_compat"
    cache_ttl_s: float = 900.0
    max_chars: int = 450
    global_rps: float = 15.0
    global_burst: int = 20
    tenant_rps: float = 4.0
    tenant_burst: int = 6
    budget_source: str = "auto"
    circuit: CircuitConfig = field(default_factory=CircuitConfig)
    debug_sampling: DebugSampling = field(default_factory=DebugSampling)
    forbid: tuple[str, ...] = (
        "DecisionCore",
        "tokens",
        "system prompt",
        "internal",
        "как языковая модель",
    )


DEFAULT_MARKETING_LLM_POLICY = MarketingLLMPolicy()
