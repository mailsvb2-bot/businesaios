from __future__ import annotations

import asyncio

from core.llm.contracts import LLMResponse, LLMUsage
from core.marketing.llm_composer import LLMComposerConfig, MarketingLLMComposer
from core.marketing.llm_prompting import MarketingLLMInputs


class _FakeLLM:
    async def generate(self, req):
        return LLMResponse(
            content="Подписка за 990 RUB — доступ",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


def _inp() -> MarketingLLMInputs:
    return MarketingLLMInputs(
        tenant_id="t1",
        user_id="u1",
        locale="ru",
        channel="telegram",
        features={"segment": "warm"},
        offer={"id": "o1", "title": "Подписка", "price": "990", "currency": "RUB", "what_user_gets": "доступ"},
    )


def test_compose_sync_works_inside_running_loop():
    composer = MarketingLLMComposer(_FakeLLM(), LLMComposerConfig(model="test-model"))

    async def _run() -> str | None:
        return composer.compose_sync(_inp())

    result = asyncio.run(_run())
    assert result == "Подписка за 990 RUB — доступ"
