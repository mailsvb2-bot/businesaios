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



@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_event_store_accounting_failure_never_exposes_generated_content(async_mode):
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.telemetry.event_types import LLM_COMPLETED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class FailingAccountingStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == LLM_COMPLETED:
                raise OSError("simulated durable accounting failure")
            return super().append_event(event)

    class ValidLLM:
        def generate_sync(self, request):
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

        async def generate(self, request):
            return self.generate_sync(request)

    store = FailingAccountingStore()
    composer = MarketingLLMComposer(
        ValidLLM(),
        LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=store,
    )
    inp = MarketingLLMInputs(
        tenant_id="t-fail", user_id="u-fail", locale="ru",
        channel="telegram", features={},
        offer={"id": "charge", "title": "Сеанс", "price": 990, "currency": "₽"},
        last_user_text="",
    )
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert composer._runtime.metrics.snapshot().counters.get("accounting_failed") == 1
    assert store.sum_event_payload_int(
        tenant_id="t-fail", event_type=LLM_COMPLETED, field="total_tokens",
        user_id="u-fail",
    ) == 0



@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_event_store_request_write_failure_prevents_provider_call(async_mode):
    from core.llm.contracts import LLMResponse
    from core.telemetry.event_types import LLM_REQUESTED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class FailingRequestStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == LLM_REQUESTED:
                raise OSError("simulated request journal failure")
            return super().append_event(event)

    class CountingLLM:
        calls = 0

        def generate_sync(self, request):
            self.calls += 1
            return LLMResponse(content="valid output")

        async def generate(self, request):
            return self.generate_sync(request)

    llm = CountingLLM()
    composer = MarketingLLMComposer(
        llm,
        LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=FailingRequestStore(),
    )
    inp = MarketingLLMInputs(
        tenant_id="t-no-request", user_id="u-no-request", locale="ru",
        channel="telegram", features={},
        offer={"id": "offer", "title": "Сеанс"},
        last_user_text="",
    )
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert llm.calls == 0
    assert composer._runtime.metrics.snapshot().counters.get("accounting_unavailable") == 1


@pytest.mark.parametrize("different_scope", ["tenant", "user", "channel"])
def test_marketing_cache_is_isolated_by_tenant_user_and_channel(different_scope):
    from core.llm.contracts import LLMResponse, LLMUsage

    class CountingLLM:
        def __init__(self):
            self.calls = 0

        def generate_sync(self, request):
            self.calls += 1
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    llm = CountingLLM()
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    common = {
        "tenant_id": "t-cache", "user_id": "u-cache",
        "locale": "ru", "channel": "telegram", "features": {},
        "offer": {"id": "cache", "title": "Сеанс", "price": 990, "currency": "₽"},
        "last_user_text": "",
    }
    first = MarketingLLMInputs(**common)
    assert composer.compose_sync(first)
    assert composer.compose_sync(first)
    assert llm.calls == 1
    changed = dict(common)
    changed[{"tenant": "tenant_id", "user": "user_id", "channel": "channel"}[different_scope]] += "-other"
    composer.compose_sync(MarketingLLMInputs(**changed))
    # Dedupe may reject identical text on the same tenant/user, but the
    # provider must not be bypassed by a cache hit across scopes.
    assert llm.calls == 2


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_deduped_marketing_response_records_one_completion_per_provider_call(async_mode):
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.telemetry.event_types import LLM_COMPLETED, LLM_SKIPPED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class CountingLLM:
        def generate_sync(self, request):
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

        async def generate(self, request):
            return self.generate_sync(request)

    store = MemoryEventStore()
    composer = MarketingLLMComposer(
        CountingLLM(), LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=store,
    )
    common = {
        "tenant_id": "t-dedupe", "user_id": "u-dedupe", "locale": "ru",
        "channel": "telegram", "features": {},
        "offer": {"id": "dedupe", "title": "Сеанс", "price": 990, "currency": "₽"},
    }
    first = MarketingLLMInputs(**common, last_user_text="первый запрос")
    second = MarketingLLMInputs(**common, last_user_text="другой запрос")
    compose = composer.compose if async_mode else composer.compose_sync
    if async_mode:
        assert await compose(first)
        assert await compose(second) is None
    else:
        assert compose(first)
        assert compose(second) is None
    assert store.count_events(tenant_id="t-dedupe", event_type=LLM_COMPLETED) == 2
    assert store.count_events(tenant_id="t-dedupe", event_type=LLM_SKIPPED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-dedupe", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 14


def test_event_store_budget_reservation_blocks_concurrent_overspend():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock

    from core.llm.budget import BudgetCaps
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.telemetry.event_types import LLM_COMPLETED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class BlockingLLM:
        def __init__(self):
            self.entered = Event()
            self.resume = Event()
            self.lock = Lock()
            self.calls = 0

        def generate_sync(self, request):
            with self.lock:
                self.calls += 1
            self.entered.set()
            assert self.resume.wait(timeout=5)
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    store = MemoryEventStore()
    llm = BlockingLLM()
    cfg = LLMComposerConfig(
        model="mock", budget_source="event_store",
        budget=BudgetCaps(tenant_tokens_per_day=1027, user_tokens_per_day=1027),
    )
    first = MarketingLLMComposer(llm, cfg, event_store=store)
    second = MarketingLLMComposer(llm, cfg, event_store=store)
    inp = MarketingLLMInputs(
        tenant_id="t-concurrent", user_id="u-concurrent", locale="ru",
        channel="telegram", features={},
        offer={"id": "concurrent", "title": "Сеанс", "price": 990, "currency": "₽"},
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(first.compose_sync, inp)
        assert llm.entered.wait(timeout=5)
        try:
            assert pool.submit(second.compose_sync, inp).result(timeout=5) is None
            assert llm.calls == 1
        finally:
            llm.resume.set()
        assert running.result(timeout=5)
    assert store.sum_event_payload_int(
        tenant_id="t-concurrent", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 7
    # Once the durable completion is visible, headroom is available again.
    assert second._runtime.budget.can_spend(
        tenant_id="t-concurrent", user_id="u-concurrent", tokens=1020,
    )


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_missing_atomic_reservation_fails_closed_before_provider(async_mode):
    from core.llm.contracts import LLMResponse
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class NoCASStore(MemoryEventStore):
        compare_and_set_setting = None

    class CountingLLM:
        def __init__(self):
            self.calls = 0

        def generate_sync(self, request):
            self.calls += 1
            return LLMResponse(content="some text")

        async def generate(self, request):
            return self.generate_sync(request)

    llm = CountingLLM()
    composer = MarketingLLMComposer(
        llm, LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=NoCASStore(),
    )
    inp = MarketingLLMInputs(
        tenant_id="t-cas", user_id="u-cas", locale="ru",
        channel="telegram", features={}, offer={"id": "cas", "title": "Сеанс"},
    )
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert llm.calls == 0


def test_sqlite_budget_reservations_are_shared_between_store_connections(tmp_path):
    from core.events.log import EventLog
    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
    from core.telemetry.event_types import LLM_COMPLETED
    from core.tenancy.scope import TenantScope
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    caps = BudgetCaps(tenant_tokens_per_day=1027, user_tokens_per_day=1027)
    path = str(tmp_path / "llm-reservations.sqlite3")
    with SqliteEventStore(path) as first_store, SqliteEventStore(path) as second_store:
        first = EventStoreDailyTokenBudget(event_store=first_store, caps=caps)
        second = EventStoreDailyTokenBudget(event_store=second_store, caps=caps)
        day = first.reserve(
            tenant_id="tenant", user_id="user", tokens=1020, request_id="first",
        )
        assert day
        assert second.reserve(
            tenant_id="tenant", user_id="user", tokens=1020, request_id="second",
        ) is None
        EventLog(first_store, tenant=TenantScope("tenant")).emit(
            event_type=LLM_COMPLETED, source="telemetry", user_id="user",
            payload={"total_tokens": 7, "request_id": "first"},
        )
        assert first.release(tenant_id="tenant", request_id="first", day=day)
        assert second.reserve(
            tenant_id="tenant", user_id="user", tokens=1020, request_id="second",
        ) == day


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_replayed_message_id_does_not_recharge_or_reinvoke_provider(async_mode):
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.telemetry.event_types import LLM_COMPLETED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class CountingLLM:
        def __init__(self):
            self.calls = 0

        def generate_sync(self, request):
            self.calls += 1
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

        async def generate(self, request):
            return self.generate_sync(request)

    llm = CountingLLM()
    store = MemoryEventStore()
    cfg = LLMComposerConfig(model="mock", budget_source="event_store")
    inp = MarketingLLMInputs(
        tenant_id="t-replay", user_id="u-replay", locale="ru",
        channel="telegram", features={},
        offer={"id": "replay", "title": "Сеанс", "price": 990, "currency": "₽"},
        message_id="incoming-123",
    )
    # Different composer instances have different caches and rate limiters.
    first = MarketingLLMComposer(llm, cfg, event_store=store)
    second = MarketingLLMComposer(llm, cfg, event_store=store)
    if async_mode:
        assert await first.compose(inp)
        assert await second.compose(inp) is None
    else:
        assert first.compose_sync(inp)
        assert second.compose_sync(inp) is None
    assert llm.calls == 1
    assert store.count_events(tenant_id="t-replay", event_type=LLM_COMPLETED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-replay", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 7
