from __future__ import annotations

from typing import Any

from core.marketing.llm_telemetry import append_event_sync
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
