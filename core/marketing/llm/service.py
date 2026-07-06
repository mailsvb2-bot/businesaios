"""Canonical orchestration surface for marketing LLM composition."""

from __future__ import annotations

from core.marketing.llm.composer_async_flow import compose_async_flow
from core.marketing.llm.composer_sync_flow import compose_sync_flow
from core.marketing.llm_prompt_builder import MarketingLLMInputs


async def compose_marketing_text_async(composer, inp: MarketingLLMInputs) -> str | None:
    return await compose_async_flow(composer, inp)


def compose_marketing_text_sync(composer, inp: MarketingLLMInputs) -> str | None:
    return compose_sync_flow(composer, inp)


__all__ = ["compose_marketing_text_async", "compose_marketing_text_sync"]
