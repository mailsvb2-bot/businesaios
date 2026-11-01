import pytest

from core.llm import MockLLMClient
from core.marketing.llm_composer import LLMComposerConfig, MarketingLLMComposer
from core.marketing.llm_prompting import MarketingLLMInputs


def test_composer_returns_text_and_caches():
    llm = MockLLMClient(fixed_text="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть». ")
    c = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t1",
        user_id="u1",
        locale="ru",
        channel="telegram",
        features={"segment": "warm"},
        offer={"id": "o1", "title": "Сеанс", "price": 990, "currency": "₽", "what_user_gets": "12 минут"},
        last_user_text="мой телефон +31 6 1234 5678",
    )
    t1 = c.compose_sync(inp)
    t2 = c.compose_sync(inp)
    assert t1
    assert t2 == t1


def test_composer_rejects_forbidden_phrase():
    llm = MockLLMClient(fixed_text="Я DecisionCore и я решил…")
    c = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t1",
        user_id="u1",
        locale="ru",
        channel="telegram",
        features={},
        offer={"id": "o1", "title": "Сеанс"},
        last_user_text="",
    )
    t = c.compose_sync(inp)
    assert t is None


def test_sync_provider_usage_is_charged_even_when_text_rejected():
    from core.llm.contracts import LLMResponse, LLMUsage

    class CountingLLM:
        def generate_sync(self, request):
            return LLMResponse(
                content="Я DecisionCore и я решил…",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    composer = MarketingLLMComposer(CountingLLM(), LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t-charge", user_id="u-charge", locale="ru",
        channel="telegram", features={}, offer={"id": "charge", "title": "Сеанс"},
        last_user_text="",
    )
    assert composer.compose_sync(inp) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="t-charge", user_id="u-charge",
        tokens=composer._cfg.budget.user_tokens_per_day - 6,
    )


@pytest.mark.asyncio
async def test_async_provider_usage_is_charged_even_when_text_rejected():
    from core.llm.contracts import LLMResponse, LLMUsage

    class AsyncCountingLLM:
        async def generate(self, request):
            return LLMResponse(
                content="Я DecisionCore и я решил…",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    composer = MarketingLLMComposer(AsyncCountingLLM(), LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t-async-charge", user_id="u-async-charge", locale="ru",
        channel="telegram", features={}, offer={"id": "charge", "title": "Сеанс"},
        last_user_text="",
    )
    assert await composer.compose(inp) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="t-async-charge", user_id="u-async-charge",
        tokens=composer._cfg.budget.user_tokens_per_day - 6,
    )


def test_missing_provider_usage_charges_conservative_estimate():
    from core.llm.contracts import LLMResponse

    class NoUsageLLM:
        def generate_sync(self, request):
            return LLMResponse(content="Я DecisionCore и я решил…", usage=None)

    composer = MarketingLLMComposer(NoUsageLLM(), LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t-missing-usage", user_id="u-missing-usage",
        locale="ru", channel="telegram", features={},
        offer={"id": "missing", "title": "Сеанс"}, last_user_text="",
    )
    assert composer.compose_sync(inp) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="t-missing-usage", user_id="u-missing-usage",
        tokens=composer._cfg.budget.user_tokens_per_day - 1,
    )


def test_provider_split_usage_is_counted_when_total_is_zero():
    from core.llm.contracts import LLMResponse, LLMUsage

    class SplitUsageLLM:
        def generate_sync(self, request):
            return LLMResponse(
                content="Я DecisionCore и я решил…",
                usage=LLMUsage(prompt_tokens=17, completion_tokens=9, total_tokens=0),
            )

    composer = MarketingLLMComposer(SplitUsageLLM(), LLMComposerConfig(model="mock"))
    inp = MarketingLLMInputs(
        tenant_id="t-split", user_id="u-split", locale="ru",
        channel="telegram", features={}, offer={"id": "split", "title": "Сеанс"},
        last_user_text="",
    )
    assert composer.compose_sync(inp) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="t-split", user_id="u-split",
        tokens=composer._cfg.budget.user_tokens_per_day - 25,
    )


def test_event_store_budget_counts_one_provider_completion_after_rejected_text():
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.telemetry.event_types import LLM_COMPLETED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class CountingLLM:
        def generate_sync(self, request):
            return LLMResponse(
                content="Я DecisionCore и я решил…",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    store = MemoryEventStore()
    cfg = LLMComposerConfig(model="mock", budget_source="event_store")
    composer = MarketingLLMComposer(CountingLLM(), cfg, event_store=store)
    inp = MarketingLLMInputs(
        tenant_id="t-store", user_id="u-store", locale="ru",
        channel="telegram", features={}, offer={"id": "charge", "title": "Сеанс"},
        last_user_text="",
    )
    assert composer.compose_sync(inp) is None
    assert store.sum_event_payload_int(
        tenant_id="t-store", event_type=LLM_COMPLETED, field="total_tokens",
        user_id="u-store",
    ) == 7
    assert composer._runtime.budget.can_spend(
        tenant_id="t-store", user_id="u-store",
        tokens=cfg.budget.user_tokens_per_day - 7,
    )
    assert not composer._runtime.budget.can_spend(
        tenant_id="t-store", user_id="u-store",
        tokens=cfg.budget.user_tokens_per_day - 6,
    )
