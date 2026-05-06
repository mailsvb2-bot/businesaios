from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.llm.budget import DailyTokenBudget, EventStoreDailyTokenBudget, TokenBudget
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
    limiter = TokenBucketLimiter(
        global_rps=cfg.global_rps,
        global_burst=cfg.global_burst,
        tenant_rps=cfg.tenant_rps,
        tenant_burst=cfg.tenant_burst,
    )
    src = str(cfg.budget_source or "auto").lower()
    if src in {"event_store", "auto"} and event_store is not None and callable(getattr(event_store, "sum_event_payload_int", None)):
        budget = EventStoreDailyTokenBudget(event_store=event_store, caps=cfg.budget)
    else:
        budget = DailyTokenBudget(cfg.budget)
    return ComposerRuntime(
        cache=cache,
        limiter=limiter,
        budget=budget,
        circuit=CircuitBreaker(cfg.circuit),
        metrics=LLMMetrics(),
        dedupe=MessageDedupe(DedupeConfig()),
    )
