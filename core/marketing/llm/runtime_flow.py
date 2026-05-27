from __future__ import annotations

from typing import Any

from core.marketing.llm_telemetry import append_event_sync, emit_trace_async, emit_trace_sync
from core.telemetry.event_types import (
    LLM_BUDGET_BLOCKED,
    LLM_CIRCUIT_OPEN,
    LLM_REQUESTED,
    LLM_SKIPPED,
)
from core.telemetry.event_writer import TelemetryContext, append_event


async def emit_circuit_open_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    await append_event(
        event_store,
        event_type=LLM_CIRCUIT_OPEN,
        ctx=ctx,
        payload={"reason": "circuit_open", "provider": provider, "model": model},
    )


def emit_circuit_open_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    append_event_sync(
        event_store=event_store,
        event_type=LLM_CIRCUIT_OPEN,
        ctx=ctx,
        payload={"reason": "circuit_open", "provider": provider, "model": model},
    )


async def emit_rate_limited_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    await append_event(
        event_store,
        event_type=LLM_SKIPPED,
        ctx=ctx,
        payload={"reason": "rate_limited", "provider": provider, "model": model},
    )


def emit_rate_limited_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str) -> None:
    append_event_sync(
        event_store=event_store,
        event_type=LLM_SKIPPED,
        ctx=ctx,
        payload={"reason": "rate_limited", "provider": provider, "model": model},
    )


async def emit_budget_blocked_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, est: int, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    await append_event(
        event_store,
        event_type=LLM_BUDGET_BLOCKED,
        ctx=ctx,
        payload={
            "provider": provider,
            "model": model,
            "estimated_tokens": est,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "experiment": experiment,
            "variant": variant,
            "offer_id": offer_id,
        },
    )


def emit_budget_blocked_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, est: int, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    append_event_sync(
        event_store=event_store,
        event_type=LLM_BUDGET_BLOCKED,
        ctx=ctx,
        payload={
            "provider": provider,
            "model": model,
            "estimated_tokens": est,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "experiment": experiment,
            "variant": variant,
            "offer_id": offer_id,
        },
    )


async def emit_requested_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    await append_event(
        event_store,
        event_type=LLM_REQUESTED,
        ctx=ctx,
        payload={
            "provider": provider,
            "model": model,
            "request_id": request_id,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "experiment": experiment,
            "variant": variant,
            "offer_id": offer_id,
        },
    )


def emit_requested_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, experiment: str, variant: str, offer_id: str) -> None:
    append_event_sync(
        event_store=event_store,
        event_type=LLM_REQUESTED,
        ctx=ctx,
        payload={
            "provider": provider,
            "model": model,
            "request_id": request_id,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
            "experiment": experiment,
            "variant": variant,
            "offer_id": offer_id,
        },
    )


async def emit_trace_cache_hit_async(*, event_store: Any, debug_sampling: Any, inp: Any, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    await emit_trace_async(
        event_store=event_store,
        debug_sampling=debug_sampling,
        inp=inp,
        model=model,
        provider=provider,
        request_id=request_id,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        ok=True,
        cache_hit=True,
        latency_ms=0,
        finish_reason="cache",
        usage=None,
        error_code="",
    )


def emit_trace_cache_hit_sync(*, event_store: Any, inp: Any, model: str, provider: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    emit_trace_sync(
        event_store=event_store,
        model=model,
        provider=provider,
        inp=inp,
        request_id=request_id,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        ok=True,
        cache_hit=True,
        latency_ms=0,
        finish_reason="cache",
        usage=None,
        error_code="",
    )
