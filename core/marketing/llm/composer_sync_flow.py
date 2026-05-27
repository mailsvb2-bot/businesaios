from __future__ import annotations

from core.marketing.async_runner import run_awaitable_sync
from core.marketing.llm.cache_keys import build_cache_key
from core.marketing.llm.compose_context import build_compose_context
from core.marketing.llm.flow import build_request, finalize_text, start_request
from core.marketing.llm.runtime_flow import (
    emit_budget_blocked_sync,
    emit_circuit_open_sync,
    emit_rate_limited_sync,
    emit_requested_sync,
    emit_trace_cache_hit_sync,
)
from core.marketing.llm.skip_flow import append_dedupe_skip_sync, emit_dedupe_skip_sync
from core.marketing.llm_guardrails import err_code
from core.marketing.llm_telemetry import emit_trace_sync
from core.telemetry.trace_utils import now_ms


def compose_sync_flow(composer, inp):
    request_id, t0 = start_request()
    compose_ctx = build_compose_context(inp)
    tenant_id = compose_ctx.tenant_id
    user_id = compose_ctx.user_id
    offer_id = compose_ctx.offer_id
    ctx = compose_ctx.telemetry
    runtime = composer._runtime

    if runtime.circuit.is_open():
        runtime.metrics.inc("circuit_open")
        emit_circuit_open_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model)
        return None
    if not runtime.limiter.allow(tenant_id):
        runtime.metrics.inc("limited")
        emit_rate_limited_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model)
        return None

    req, prompt_version, prompt_hash = build_request(model=composer._cfg.model, inp=inp)
    cache_key = build_cache_key(cache=runtime.cache, provider=composer._cfg.provider, model=composer._cfg.model, inp=inp, prompt_version=prompt_version, prompt_hash=prompt_hash, offer_id=offer_id, req=req)
    cached = runtime.cache.get(cache_key)
    if cached:
        runtime.metrics.inc("cache_hit")
        emit_trace_cache_hit_sync(event_store=composer._event_store, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        return cached

    est = int(req.max_tokens) + 800
    if not runtime.budget.can_spend(tenant_id=tenant_id, user_id=user_id, tokens=est):
        runtime.metrics.inc("budget_blocked")
        emit_budget_blocked_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, est=est, prompt_version=prompt_version, prompt_hash=prompt_hash, experiment=inp.experiment, variant=inp.variant, offer_id=offer_id)
        return None

    emit_requested_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, experiment=inp.experiment, variant=inp.variant, offer_id=offer_id)
    gen_sync = getattr(composer._llm, "generate_sync", None)
    if not callable(gen_sync):
        return run_awaitable_sync(composer._compose_async(inp))
    try:
        resp = gen_sync(req)
        runtime.circuit.on_success()
    except Exception as e:  # noqa: BLE001
        runtime.circuit.on_failure()
        runtime.metrics.inc("failed")
        latency = max(0, now_ms() - t0)
        runtime.metrics.observe_latency(latency)
        emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="error", usage=None, error_code=err_code(e))
        return None

    latency = max(0, now_ms() - t0)
    runtime.metrics.observe_latency(latency)
    ok_text, text, guard_reason = finalize_text(text=resp.content or "", max_chars=int(composer._cfg.max_chars), forbid=composer._cfg.forbid, offer=(inp.offer or {}))
    if not ok_text:
        emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="guardrail", usage=resp.usage, error_code=f"guardrail:{guard_reason}")
        return None
    if not text:
        return None
    if not runtime.dedupe.allow(tenant_id=tenant_id, user_id=user_id, text=text):
        runtime.metrics.inc("deduped")
        append_dedupe_skip_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        emit_dedupe_skip_sync(event_store=composer._event_store, inp=inp, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, latency_ms=latency, usage=resp.usage)
        return None

    emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=True, cache_hit=False, latency_ms=latency, finish_reason=resp.finish_reason or "stop", usage=resp.usage, error_code="")
    runtime.cache.set(cache_key, text)
    return text
