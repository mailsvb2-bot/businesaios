from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.llm.budget import DailyTokenBudget, EventStoreDailyTokenBudget, TokenBudget, has_durable_budget_store
from core.llm.cache import TTLTextCache
from core.llm.circuit import CircuitBreaker
from core.llm.metrics import LLMMetrics
from core.llm.ratelimit import TokenBucketLimiter
from core.marketing.dedupe import DedupeConfig, MessageDedupe


@dataclass(frozen=True)
class ComposerRuntime:
    cache: TTLTextCache
    limiter: TokenBucketLimiter
    budget: TokenBudget
    circuit: CircuitBreaker
    metrics: LLMMetrics
    dedupe: MessageDedupe


def build_composer_runtime(*, cfg, event_store: Any = None) -> ComposerRuntime:
    cache = TTLTextCache(ttl_s=cfg.cache_ttl_s)
    limiter = TokenBucketLimiter(global_rps=cfg.global_rps, global_burst=cfg.global_burst,
                                 tenant_rps=cfg.tenant_rps, tenant_burst=cfg.tenant_burst)
    src = str(cfg.budget_source or "auto").lower()
    if src not in {"event_store", "auto", "memory"}:
        raise RuntimeError("LLM_BUDGET_SOURCE_INVALID")
    if src != "memory" and not has_durable_budget_store(event_store):
        raise RuntimeError("LLM_BUDGET_EVENT_STORE_UNAVAILABLE")
    budget = (DailyTokenBudget(cfg.budget) if src == "memory" else
              EventStoreDailyTokenBudget(event_store=event_store, caps=cfg.budget))
    return ComposerRuntime(cache=cache, limiter=limiter, budget=budget,
                           circuit=CircuitBreaker(cfg.circuit), metrics=LLMMetrics(),
                           dedupe=MessageDedupe(DedupeConfig()))
