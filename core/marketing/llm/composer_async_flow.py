from __future__ import annotations

from core.marketing.llm.compose_context import build_compose_context
from core.marketing.llm.flow import (
    build_cache_key,
    build_request,
    finalize_text,
    idempotent_request_id,
    start_request,
    with_accounting_metadata,
)
from core.marketing.llm.runtime_flow import (
    emit_circuit_open_async,
    emit_rate_limited_async,
    emit_trace_cache_hit_async,
)
from core.marketing.llm.skip_flow import emit_dedupe_skip_async
from core.marketing.llm_guardrails import err_code
from core.marketing.llm_telemetry import emit_trace_async
from core.telemetry.trace_utils import now_ms


async def compose_async_flow(composer, inp):
    request_id, t0 = start_request()
    compose_ctx = build_compose_context(inp)
    tenant_id, user_id = compose_ctx.tenant_id, compose_ctx.user_id
    offer_id, ctx = compose_ctx.offer_id, compose_ctx.telemetry
    runtime = composer._runtime
    if runtime.circuit.is_open():
        runtime.metrics.inc("circuit_open")
        await emit_circuit_open_async(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model)
        return None
    if not runtime.limiter.allow(tenant_id):
        runtime.metrics.inc("limited")
        await emit_rate_limited_async(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model)
        return None

    req, prompt_version, prompt_hash = build_request(model=composer._cfg.model, inp=inp)
    request_id = idempotent_request_id(inp=inp, provider=composer._cfg.provider, model=composer._cfg.model, generated=request_id)
    cache_key = build_cache_key(cache=runtime.cache, provider=composer._cfg.provider, model=composer._cfg.model, inp=inp, prompt_version=prompt_version, prompt_hash=prompt_hash, offer_id=offer_id, req=req)
    if cached := runtime.cache.get(cache_key):
        runtime.metrics.inc("cache_hit")
        await emit_trace_cache_hit_async(event_store=composer._event_store, debug_sampling=composer._cfg.debug_sampling, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        return cached

    req = with_accounting_metadata(request=req, inp=inp, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
    try:
        resp = await composer.accounted_gateway.generate(req)
        runtime.circuit.on_success()
    except Exception as exc:  # noqa: BLE001 - provider boundary fails closed
        code = str(exc) if isinstance(exc, RuntimeError) else ""
        if code == "LLM_BUDGET_BLOCKED":
            runtime.metrics.inc("budget_blocked")
        elif code.startswith("LLM_ACCOUNTING_"):
            runtime.metrics.inc("accounting_failed" if code.endswith(
                ("_WRITE_FAILED", "_RELEASE_FAILED", "_CANCEL_FAILED")) else "accounting_unavailable")
        else:
            runtime.circuit.on_failure()
            runtime.metrics.inc("failed")
            latency = max(0, now_ms() - t0)
            runtime.metrics.observe_latency(latency)
            await emit_trace_async(event_store=composer._event_store, debug_sampling=composer._cfg.debug_sampling, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="error", usage=None, error_code=err_code(exc))
            await composer._maybe_alert(inp, reason="error_spike")
        return None

    usage = resp.usage
    if usage is None:
        runtime.metrics.inc("accounting_unavailable")
        return None
    runtime.metrics.add_tokens(usage.total_tokens)
    latency = max(0, now_ms() - t0)
    runtime.metrics.observe_latency(latency)
    await emit_trace_async(event_store=composer._event_store, debug_sampling=composer._cfg.debug_sampling, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=True, cache_hit=False, latency_ms=latency, finish_reason=resp.finish_reason or "stop", usage=usage, error_code="", completion_recorded=True)
    ok_text, text, guard_reason = finalize_text(text=resp.content or "", max_chars=int(composer._cfg.max_chars), forbid=composer._cfg.forbid, offer=(inp.offer or {}))
    if not ok_text:
        await emit_trace_async(event_store=composer._event_store, debug_sampling=composer._cfg.debug_sampling, inp=inp, model=composer._cfg.model, provider=composer._cfg.provider, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash, ok=False, cache_hit=False, latency_ms=latency, finish_reason="guardrail", usage=usage, error_code=f"guardrail:{guard_reason}")
        return None
    if not text:
        await composer._emit_guardrail_fail(inp, request_id, prompt_version, prompt_hash, "empty")
        return None
    if not runtime.dedupe.allow(tenant_id=tenant_id, user_id=user_id, text=text):
        runtime.metrics.inc("deduped")
        await emit_dedupe_skip_async(event_store=composer._event_store, ctx=ctx, provider=composer._cfg.provider, model=composer._cfg.model, request_id=request_id, prompt_version=prompt_version, prompt_hash=prompt_hash)
        return None
    runtime.metrics.inc("ok")
    runtime.cache.set(cache_key, text)
    await composer._maybe_alert(inp, reason="latency_or_cost")
    return text
