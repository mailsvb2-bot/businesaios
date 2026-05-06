from __future__ import annotations

from typing import Any

from core.marketing.llm_telemetry import append_event_sync, emit_trace_sync
from core.telemetry.event_types import LLM_SKIPPED
from core.telemetry.event_writer import TelemetryContext, append_event


async def emit_dedupe_skip_async(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    await append_event(
        event_store,
        event_type=LLM_SKIPPED,
        ctx=ctx,
        payload={
            "reason": "dedupe_cooldown",
            "provider": provider,
            "model": model,
            "request_id": request_id,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
        },
    )


def emit_dedupe_skip_sync(*, event_store: Any, inp: Any, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str, latency_ms: int, usage: Any) -> None:
    emit_trace_sync(
        event_store=event_store,
        model=model,
        provider=provider,
        inp=inp,
        request_id=request_id,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        ok=True,
        cache_hit=False,
        latency_ms=latency_ms,
        finish_reason="dedupe",
        usage=usage,
        error_code="",
    )


def append_dedupe_skip_sync(*, event_store: Any, ctx: TelemetryContext, provider: str, model: str, request_id: str, prompt_version: str, prompt_hash: str) -> None:
    append_event_sync(
        event_store=event_store,
        event_type=LLM_SKIPPED,
        ctx=ctx,
        payload={
            "reason": "dedupe_cooldown",
            "provider": provider,
            "model": model,
            "request_id": request_id,
            "prompt_version": prompt_version,
            "prompt_hash": prompt_hash,
        },
    )
