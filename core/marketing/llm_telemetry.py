from __future__ import annotations

from typing import Any

from config.marketing_llm_telemetry_policy import (
    DEFAULT_MARKETING_LLM_TELEMETRY_POLICY,
    MarketingLLMTelemetryPolicy,
)
from core.telemetry.event_types import LLM_ALERT, LLM_CACHE_HIT, LLM_COMPLETED, LLM_FAILED
from core.telemetry.event_writer import TelemetryContext, append_event
from core.telemetry.schemas import LLMTrace


def _trace_payload(*, inp, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str, cache_hit: bool, latency_ms: int, finish_reason: str, usage: Any, ok: bool, error_code: str) -> tuple[TelemetryContext, dict]:
    pt = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
    ct = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
    tt = int(getattr(usage, "total_tokens", 0) or 0) if usage else 0
    trace = LLMTrace(
        tenant_id=str(inp.tenant_id),
        user_id=str(inp.user_id),
        channel=str(inp.channel),
        locale=str(inp.locale),
        kind="marketing_message",
        model=str(model),
        provider=str(provider),
        request_id=str(request_id),
        correlation_id=str(inp.correlation_id or ""),
        message_id=str(inp.message_id or ""),
        offer_id=str((inp.offer or {}).get("id", "")),
        experiment=str(inp.experiment or ""),
        variant=str(inp.variant or ""),
        prompt_version=str(prompt_version),
        prompt_hash=str(prompt_hash),
        cache_hit=bool(cache_hit),
        latency_ms=int(latency_ms),
        finish_reason=str(finish_reason or ""),
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=tt,
        ok=bool(ok),
        error_code=str(error_code or ""),
    )
    ctx = TelemetryContext(
        tenant_id=str(inp.tenant_id),
        user_id=str(inp.user_id),
        message_id=str(inp.message_id or ""),
        correlation_id=str(inp.correlation_id or ""),
    )
    return ctx, trace.to_event_payload()


def append_event_sync(*, event_store, event_type: str, ctx: TelemetryContext, payload: dict, source: str = "telemetry") -> None:
    if event_store is None:
        return
    try:
        from core.events.log import EventLog
        from core.tenancy.scope import TenantScope

        log = EventLog(event_store, tenant=TenantScope(str(ctx.tenant_id)))
        enriched = dict(payload or {})
        if ctx.message_id:
            enriched.setdefault("message_id", ctx.message_id)
        corr = (ctx.correlation_id or ctx.message_id or None)
        log.emit(event_type=str(event_type), source=str(source), user_id=str(ctx.user_id), payload=enriched, correlation_id=corr)
    except Exception:
        return


def emit_trace_sync(*, event_store, inp, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str, ok: bool, cache_hit: bool, latency_ms: int, finish_reason: str, usage: Any, error_code: str, policy: MarketingLLMTelemetryPolicy | None = None) -> None:
    policy = policy or DEFAULT_MARKETING_LLM_TELEMETRY_POLICY
    ctx, payload = _trace_payload(
        inp=inp,
        model=model,
        provider=provider,
        request_id=request_id,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        cache_hit=cache_hit,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        usage=usage,
        ok=ok,
        error_code=error_code,
    )
    append_event_sync(event_store=event_store, event_type=(LLM_CACHE_HIT if cache_hit else (LLM_COMPLETED if ok else LLM_FAILED)), ctx=ctx, payload=payload)


async def emit_trace_async(*, event_store, debug_sampling, inp, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str, ok: bool, cache_hit: bool, latency_ms: int, finish_reason: str, usage: Any, error_code: str, policy: MarketingLLMTelemetryPolicy | None = None) -> None:
    ctx, payload = _trace_payload(
        inp=inp,
        model=model,
        provider=provider,
        request_id=request_id,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        cache_hit=cache_hit,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        usage=usage,
        ok=ok,
        error_code=error_code,
    )
    if cache_hit:
        await append_event(event_store, event_type=LLM_CACHE_HIT, ctx=ctx, payload=payload)
        return
    await append_event(event_store, event_type=(LLM_COMPLETED if ok else LLM_FAILED), ctx=ctx, payload=payload)
    if bool(getattr(debug_sampling, "hit", lambda: False)()):
        await append_event(
            event_store,
            event_type=str(policy.debug_sample_event_type),
            ctx=ctx,
            payload={
                "request_id": request_id,
                "prompt_version": prompt_version,
                "prompt_hash": prompt_hash,
                "provider": provider,
                "model": model,
                "ok": bool(ok),
                "latency_ms": int(latency_ms),
                "user_text_len": len(inp.last_user_text or ""),
                "offer_id": str((inp.offer or {}).get("id", "")),
            },
        )


async def maybe_emit_alert(*, event_store, inp, metrics, provider: str, model: str, reason: str, policy: MarketingLLMTelemetryPolicy | None = None) -> None:
    policy = policy or DEFAULT_MARKETING_LLM_TELEMETRY_POLICY
    p95 = metrics.p95_latency()
    snap = metrics.snapshot()
    failed = int(snap.counters.get("failed", 0))
    ok = int(snap.counters.get("ok", 0))
    total = ok + failed
    err_rate = (failed / total) if total > int(policy.alert_min_total) else float(policy.zero_error_rate)

    if p95 > int(policy.alert_p95_latency_ms) or err_rate > float(policy.alert_error_rate):
        ctx = TelemetryContext(
            tenant_id=str(inp.tenant_id),
            user_id=str(inp.user_id),
            message_id=str(inp.message_id or ""),
            correlation_id=str(inp.correlation_id or ""),
        )
        await append_event(
            event_store,
            event_type=LLM_ALERT,
            ctx=ctx,
            payload={
                "reason": reason,
                "p95_latency_ms": int(p95),
                "err_rate": float(err_rate),
                "provider": provider,
                "model": model,
                "tokens_total": int(snap.tokens_total),
            },
        )
