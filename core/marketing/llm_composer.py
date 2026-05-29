from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from config.marketing_llm_policy import DEFAULT_MARKETING_LLM_POLICY, MarketingLLMPolicy
from core.llm.budget import BudgetCaps
from core.llm.circuit import CircuitConfig
from core.llm.contracts import LLMClient
from core.llm.sampling import DebugSampling
from core.marketing.async_runner import run_awaitable_sync
from core.marketing.llm.composer_runtime import build_composer_runtime
from core.marketing.llm.service import compose_marketing_text_async, compose_marketing_text_sync
from core.marketing.llm_prompt_builder import MarketingLLMInputs
from core.marketing.llm_telemetry import emit_trace_async, maybe_emit_alert
from core.marketing.llm_text_policy import validate_marketing_text as _validate_marketing_text

validate_marketing_text = _validate_marketing_text


@dataclass(frozen=True)
class LLMComposerConfig:
    model: str
    policy: MarketingLLMPolicy = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY)
    provider: str = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.provider)
    cache_ttl_s: float = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.cache_ttl_s)
    max_chars: int = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.max_chars)
    global_rps: float = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.global_rps)
    global_burst: int = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.global_burst)
    tenant_rps: float = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.tenant_rps)
    tenant_burst: int = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.tenant_burst)
    budget: BudgetCaps = field(default_factory=BudgetCaps)
    budget_source: str = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.budget_source)
    circuit: CircuitConfig = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.circuit)
    debug_sampling: DebugSampling = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.debug_sampling)
    forbid: tuple = field(default_factory=lambda: DEFAULT_MARKETING_LLM_POLICY.forbid)


class MarketingLLMComposer:
    """DecisionCore decides, LLM composes."""

    def __init__(self, llm: LLMClient, cfg: LLMComposerConfig, *, event_store: Any = None) -> None:
        self._llm = llm
        self._cfg = cfg
        self._event_store = event_store
        self._runtime = build_composer_runtime(cfg=cfg, event_store=event_store)

    @property
    def llm_client(self) -> LLMClient:
        """Canonical read-only access to the injected client.

        Exposes the already-wired client without forcing callers to reach into
        a private attribute. This keeps boot wiring on a single path.
        """
        return self._llm

    async def compose(self, inp: MarketingLLMInputs) -> str | None:
        return await self._compose_async(inp)

    def compose_sync(self, inp: MarketingLLMInputs) -> str | None:
        gen_sync = getattr(self._llm, "generate_sync", None)
        if callable(gen_sync):
            return self._compose_sync_via_generate_sync(inp)
        return run_awaitable_sync(self._compose_async(inp))

    async def _compose_async(self, inp: MarketingLLMInputs) -> str | None:
        return await compose_marketing_text_async(self, inp)

    async def _maybe_alert(self, inp: MarketingLLMInputs, *, reason: str) -> None:
        await maybe_emit_alert(
            event_store=self._event_store,
            inp=inp,
            metrics=self._runtime.metrics,
            provider=self._cfg.provider,
            model=self._cfg.model,
            reason=reason,
        )

    async def _emit_guardrail_fail(self, inp: MarketingLLMInputs, request_id: str, prompt_version: str, prompt_hash: str, reason: str) -> None:
        await emit_trace_async(
            event_store=self._event_store,
            debug_sampling=self._cfg.debug_sampling,
            inp=inp,
            model=self._cfg.model,
            provider=self._cfg.provider,
            request_id=request_id,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            ok=False,
            cache_hit=False,
            latency_ms=0,
            finish_reason="guardrail",
            usage=None,
            error_code=f"guardrail:{reason}",
        )

    def _compose_sync_via_generate_sync(self, inp: MarketingLLMInputs) -> str | None:
        return compose_marketing_text_sync(self, inp)
