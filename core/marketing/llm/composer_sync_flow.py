from __future__ import annotations

from core.llm.budget import EventStoreDailyTokenBudget, estimate_request_tokens, validated_llm_usage
from core.llm.contracts import LLMUsage
from core.marketing.llm.compose_context import build_compose_context
from core.marketing.llm.flow import build_cache_key, build_request, finalize_text, idempotent_request_id, start_request
from core.marketing.llm.runtime_flow import (
    emit_budget_blocked_sync,
    emit_circuit_open_sync,
    emit_rate_limited_sync,
    emit_requested_sync,
    emit_trace_cache_hit_sync,
)
from core.marketing.llm.skip_flow import append_dedupe_skip_sync
from core.marketing.llm_guardrails import err_code
from core.marketing.llm_telemetry import emit_trace_sync
from core.telemetry.trace_utils import now_ms


def compose_sync_flow(composer, inp):
    request_id, t0 = start_request()
    compose_ctx = build_compose_context(inp)
    tenant_id, user_id = compose_ctx.tenant_id, compose_ctx.user_id
    offer_id, ctx = compose_ctx.offer_id, compose_ctx.telemetry
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
    request_id = idempotent_request_id(
        inp=inp, provider=composer._cfg.provider, model=composer._cfg.model, generated=request_id)
    cache_key = build_cache_key(cache=runtime.cache, provider=composer._cfg.provider, model=composer._cfg.model, inp=inp, prompt_version=prompt_version, prompt_hash=prompt_hash, offer_id=offer_id, req=req)
    cached = runtime.cache.get(cache_key)
    if cached:
        runtime.metrics.inc("cache_hit")
        emit_trace_cache_hit_sync(event_store=composer._event_store, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        return cached

    est = estimate_request_tokens(req)
    if not runtime.budget.can_spend(tenant_id=tenant_id, user_id=user_id, tokens=est):
        runtime.metrics.inc("budget_blocked")
        emit_budget_blocked_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, est=est, prompt_version=prompt_version, prompt_hash=prompt_hash, experiment=inp.experiment, variant=inp.variant, offer_id=offer_id)
        return None

    reservation_day = None
    if isinstance(runtime.budget, EventStoreDailyTokenBudget):
        reservation_day = runtime.budget.reserve(
            tenant_id=tenant_id, user_id=user_id, tokens=est, request_id=request_id,
        )
        if reservation_day is None:
            runtime.metrics.inc("budget_blocked")
            return None

    try:
        emit_requested_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, experiment=inp.experiment, variant=inp.variant, offer_id=offer_id, required=isinstance(runtime.budget, EventStoreDailyTokenBudget))
    except Exception:  # noqa: BLE001
        if reservation_day is not None and not runtime.budget.cancel_unstarted_reservation(
            tenant_id=tenant_id, request_id=request_id, day=reservation_day,
        ):
            runtime.metrics.inc("reservation_release_failed")
        runtime.metrics.inc("accounting_unavailable")
        return None
    try:
        resp = composer._llm.generate_sync(req)
        runtime.circuit.on_success()
    except Exception as e:  # noqa: BLE001
        runtime.circuit.on_failure()
        runtime.metrics.inc("failed")
        latency = max(0, now_ms() - t0)
        runtime.metrics.observe_latency(latency)
        emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="error", usage=None, error_code=err_code(e))
        return None

    # Record actual provider usage even for content rejected by guardrails.
    reported = validated_llm_usage(resp.usage)
    if reported is None:
        runtime.metrics.inc("accounting_unavailable")
        return None  # Keep the reservation/claim: the provider may have charged us.
    prompt, completion, used = reported
    usage_for_accounting = LLMUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=used)
    runtime.budget.spend(tenant_id=tenant_id, user_id=user_id, tokens=used)
    runtime.metrics.add_tokens(used)
    latency = max(0, now_ms() - t0)
    runtime.metrics.observe_latency(latency)
    try:
        emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=True, cache_hit=False, latency_ms=latency, finish_reason=resp.finish_reason or "stop", usage=usage_for_accounting, error_code="", required=isinstance(runtime.budget, EventStoreDailyTokenBudget))
    except Exception:  # noqa: BLE001
        # Never expose generated content when the authoritative spend write fails.
        runtime.metrics.inc("accounting_failed")
        return None
    if reservation_day is not None and not runtime.budget.release(
        tenant_id=tenant_id, request_id=request_id, day=reservation_day,
    ):
        runtime.metrics.inc("accounting_failed")
        return None
    ok_text, text, guard_reason = finalize_text(text=resp.content or "", max_chars=int(composer._cfg.max_chars), forbid=composer._cfg.forbid, offer=(inp.offer or {}))
    if not ok_text:
        emit_trace_sync(event_store=composer._event_store, model=composer._cfg.model, provider=composer._cfg.provider, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="guardrail", usage=usage_for_accounting, error_code=f"guardrail:{guard_reason}")
        return None
    if not text:
        return None
    if not runtime.dedupe.allow(tenant_id=tenant_id, user_id=user_id, text=text):
        runtime.metrics.inc("deduped")
        append_dedupe_skip_sync(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        return None

    runtime.cache.set(cache_key, text)
    return text
