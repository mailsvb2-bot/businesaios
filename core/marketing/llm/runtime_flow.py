from __future__ import annotations

from typing import Any

from core.marketing.llm_telemetry import append_event_sync, emit_trace_async, emit_trace_sync
from core.telemetry.event_types import LLM_BUDGET_BLOCKED, LLM_CIRCUIT_OPEN, LLM_REQUESTED, LLM_SKIPPED
from core.telemetry.event_writer import TelemetryContext, append_event


def _status_payload(reason: str, provider: str, model: str) -> dict:
    return {"reason": reason, "provider": provider, "model": model}


def _budget_payload(provider: str, model: str, est: int, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> dict:
    return dict(provider=provider, model=model, estimated_tokens=est, prompt_version=prompt_version,
                prompt_hash=prompt_hash, experiment=experiment, variant=variant, offer_id=offer_id)


def _request_payload(provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> dict:
    return dict(provider=provider, model=model, request_id=request_id, prompt_version=prompt_version,
                prompt_hash=prompt_hash, experiment=experiment, variant=variant, offer_id=offer_id)


def _cache_trace(inp: Any, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str) -> dict:
    return dict(inp=inp, model=model, provider=provider, request_id=request_id,
                prompt_version=prompt_version, prompt_hash=prompt_hash, ok=True, cache_hit=True,
                latency_ms=0, finish_reason="cache", usage=None, error_code="")


async def emit_circuit_open_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    await append_event(event_store, event_type=LLM_CIRCUIT_OPEN, ctx=ctx, payload=_status_payload("circuit_open", provider, model))


def emit_circuit_open_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    append_event_sync(event_store=event_store, event_type=LLM_CIRCUIT_OPEN, ctx=ctx, payload=_status_payload("circuit_open", provider, model))


async def emit_rate_limited_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    await append_event(event_store, event_type=LLM_SKIPPED, ctx=ctx, payload=_status_payload("rate_limited", provider, model))


def emit_rate_limited_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    append_event_sync(event_store=event_store, event_type=LLM_SKIPPED, ctx=ctx, payload=_status_payload("rate_limited", provider, model))


async def emit_budget_blocked_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, est: int, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    payload = _budget_payload(provider, model, est, prompt_version, prompt_hash, experiment, variant, offer_id)
    await append_event(event_store, event_type=LLM_BUDGET_BLOCKED, ctx=ctx, payload=payload)


def emit_budget_blocked_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, est: int, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    payload = _budget_payload(provider, model, est, prompt_version, prompt_hash, experiment, variant, offer_id)
    append_event_sync(event_store=event_store, event_type=LLM_BUDGET_BLOCKED, ctx=ctx, payload=payload)


async def emit_requested_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    payload = _request_payload(provider, model, request_id, prompt_version, prompt_hash, experiment, variant, offer_id)
    await append_event(event_store, event_type=LLM_REQUESTED, ctx=ctx, payload=payload)


def emit_requested_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str, required: bool = False) -> None:
    payload = _request_payload(provider, model, request_id, prompt_version, prompt_hash, experiment, variant, offer_id)
    append_event_sync(event_store=event_store, event_type=LLM_REQUESTED, ctx=ctx, payload=payload, required=required)


async def emit_trace_cache_hit_async(*, event_store: Any, debug_sampling: Any, inp: Any, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    kwargs = _cache_trace(inp, model, provider, request_id, prompt_version, prompt_hash)
    await emit_trace_async(event_store=event_store, debug_sampling=debug_sampling, **kwargs)


def emit_trace_cache_hit_sync(*, event_store: Any, inp: Any, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    kwargs = _cache_trace(inp, model, provider, request_id, prompt_version, prompt_hash)
    emit_trace_sync(event_store=event_store, **kwargs)
