import pytest

from core.llm import MockLLMClient
from core.marketing.llm_composer import LLMComposerConfig, MarketingLLMComposer
from core.marketing.llm_prompting import MarketingLLMInputs


from core.llm.contracts import LLMResponse, LLMUsage
from core.telemetry.event_types import LLM_COMPLETED
from runtime.platform.event_store.memory_event_store import MemoryEventStore

_VALID = "Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть»."
_REJECTED = "Я DecisionCore и я решил…"


def _input(tenant="tenant", user="user", **changes):
    values = dict(
        tenant_id=tenant, user_id=user, locale="ru", channel="telegram",
        features={}, offer={"id": "offer", "title": "Сеанс", "price": 990, "currency": "₽"},
        last_user_text="",
    )
    values.update(changes)
    return MarketingLLMInputs(**values)


class _UsageLLM:
    def __init__(self, text=_VALID, usage=None):
        self.text = text
        self.usage = usage if usage is not None else LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7)
        self.calls = 0

    def generate_sync(self, request):
        self.calls += 1
        return LLMResponse(content=self.text, usage=self.usage)

    async def generate(self, request):
        return self.generate_sync(request)


def test_composer_returns_text_and_caches():
    composer = MarketingLLMComposer(MockLLMClient(fixed_text=_VALID), LLMComposerConfig(model="mock"))
    inp = _input(tenant="t1", user="u1")
    first = composer.compose_sync(inp)
    assert first
    assert composer.compose_sync(inp) == first


def test_composer_rejects_forbidden_phrase():
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), LLMComposerConfig(model="mock"))
    assert composer.compose_sync(_input()) is None


def test_sync_provider_usage_is_charged_even_when_text_rejected():
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), LLMComposerConfig(model="mock"))
    assert composer.compose_sync(_input()) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=composer._cfg.budget.user_tokens_per_day - 6,
    )


@pytest.mark.asyncio
async def test_async_provider_usage_is_charged_even_when_text_rejected():
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), LLMComposerConfig(model="mock"))
    assert await composer.compose(_input()) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=composer._cfg.budget.user_tokens_per_day - 6,
    )


def test_missing_provider_usage_charges_conservative_estimate():
    llm = _UsageLLM(text=_REJECTED)
    llm.usage = None
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    assert composer.compose_sync(_input()) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=composer._cfg.budget.user_tokens_per_day - 1,
    )


def test_provider_split_usage_is_counted_when_total_is_zero():
    llm = _UsageLLM(text=_REJECTED, usage=LLMUsage(prompt_tokens=17, completion_tokens=9, total_tokens=0))
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    assert composer.compose_sync(_input()) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=composer._cfg.budget.user_tokens_per_day - 25,
    )


def test_event_store_budget_counts_one_provider_completion_after_rejected_text():
    store = MemoryEventStore()
    cfg = LLMComposerConfig(model="mock", budget_source="event_store")
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), cfg, event_store=store)
    assert composer.compose_sync(_input()) is None
    assert store.sum_event_payload_int(
        tenant_id="tenant", event_type=LLM_COMPLETED, field="total_tokens", user_id="user",
    ) == 7
    assert composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=cfg.budget.user_tokens_per_day - 7,
    )
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=cfg.budget.user_tokens_per_day - 6,
    )


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_event_store_accounting_failure_never_exposes_generated_content(async_mode):
    class FailingAccountingStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == LLM_COMPLETED:
                raise OSError("simulated durable accounting failure")
            return super().append_event(event)

    store = FailingAccountingStore()
    composer = MarketingLLMComposer(
        _UsageLLM(), LLMComposerConfig(model="mock", budget_source="event_store"), event_store=store,
    )
    inp = _input(tenant="t-fail", user="u-fail")
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert composer._runtime.metrics.snapshot().counters.get("accounting_failed") == 1
    assert store.sum_event_payload_int(
        tenant_id="t-fail", event_type=LLM_COMPLETED, field="total_tokens", user_id="u-fail",
    ) == 0


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_event_store_request_write_failure_prevents_provider_call(async_mode):
    from core.telemetry.event_types import LLM_REQUESTED

    class FailingRequestStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == LLM_REQUESTED:
                raise OSError("simulated request journal failure")
            return super().append_event(event)

    llm = _UsageLLM()
    composer = MarketingLLMComposer(
        llm, LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=FailingRequestStore(),
    )
    inp = _input(tenant="t-no-request", user="u-no-request")
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert llm.calls == 0
    assert composer._runtime.metrics.snapshot().counters.get("accounting_unavailable") == 1


@pytest.mark.parametrize("different_scope", ["tenant", "user", "channel"])
def test_marketing_cache_is_isolated_by_tenant_user_and_channel(different_scope):
    llm = _UsageLLM()
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock"))
    inp = _input(tenant="t-cache", user="u-cache")
    assert composer.compose_sync(inp)
    assert composer.compose_sync(inp)
    assert llm.calls == 1
    changed = dict(inp.__dict__)
    changed[{"tenant": "tenant_id", "user": "user_id", "channel": "channel"}[different_scope]] += "-other"
    composer.compose_sync(MarketingLLMInputs(**changed))
    assert llm.calls == 2


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_deduped_marketing_response_records_one_completion_per_provider_call(async_mode):
    from core.telemetry.event_types import LLM_SKIPPED

    store = MemoryEventStore()
    composer = MarketingLLMComposer(
        _UsageLLM(), LLMComposerConfig(model="mock", budget_source="event_store"),
        event_store=store,
    )
    first = _input(tenant="t-dedupe", user="u-dedupe", last_user_text="первый запрос")
    second = _input(tenant="t-dedupe", user="u-dedupe", last_user_text="другой запрос")
    if async_mode:
        assert await composer.compose(first)
        assert await composer.compose(second) is None
    else:
        assert composer.compose_sync(first)
        assert composer.compose_sync(second) is None
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
    changed_features = MarketingLLMInputs(
        **{**inp.__dict__, "features": {"segment": "changed-after-retry"}},
    )
    if async_mode:
        assert await first.compose(inp)
        assert await second.compose(changed_features) is None
    else:
        assert first.compose_sync(inp)
        assert second.compose_sync(changed_features) is None
    assert llm.calls == 1
    assert store.count_events(tenant_id="t-replay", event_type=LLM_COMPLETED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-replay", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 7


@pytest.mark.asyncio
async def test_optional_debug_event_failure_does_not_strand_durable_spend():
    from core.llm.contracts import LLMResponse, LLMUsage
    from core.llm.sampling import DebugSampling
    from core.telemetry.event_types import LLM_COMPLETED
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    class FailingDebugStore(MemoryEventStore):
        def append_event(self, event):
            if event.get("event_type") == "llm_debug_sample":
                raise OSError("debug telemetry unavailable")
            return super().append_event(event)

    class ValidLLM:
        async def generate(self, request):
            return LLMResponse(
                content="Хочешь продолжить? Есть «Сеанс» за 990₽. Нажми «Открыть».",
                usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            )

    store = FailingDebugStore()
    composer = MarketingLLMComposer(
        ValidLLM(),
        LLMComposerConfig(
            model="mock", budget_source="event_store",
            debug_sampling=DebugSampling(rate=1.0),
        ),
        event_store=store,
    )
    inp = MarketingLLMInputs(
        tenant_id="t-debug", user_id="u-debug", locale="ru",
        channel="telegram", features={},
        offer={"id": "debug", "title": "Сеанс", "price": 990, "currency": "₽"},
        last_user_text="",
        message_id="debug-event-1",
    )
    assert await composer.compose(inp)
    assert store.count_events(tenant_id="t-debug", event_type=LLM_COMPLETED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-debug", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 7
    day = composer._runtime.budget._day()
    pending = store.get_setting(tenant_id="t-debug", key=f"llm:pending:v1:{day}")
    assert pending == {"pending": {}}
    assert composer._runtime.metrics.snapshot().counters.get("accounting_failed", 0) == 0


def test_event_store_idempotency_claim_survives_budget_day_rollover(monkeypatch):
    from core.events.log import EventLog
    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
    from core.telemetry.event_types import LLM_COMPLETED
    from core.tenancy.scope import TenantScope
    from runtime.platform.event_store.memory_event_store import MemoryEventStore

    store = MemoryEventStore()
    budget = EventStoreDailyTokenBudget(
        event_store=store,
        caps=BudgetCaps(tenant_tokens_per_day=10000, user_tokens_per_day=10000),
    )
    monkeypatch.setattr(budget, "_day", lambda: "2026-11-01")
    assert budget.reserve(
        tenant_id="tenant", user_id="user", tokens=100,
        request_id="same-inbound-event",
    ) == "2026-11-01"
    EventLog(store, tenant=TenantScope("tenant")).emit(
        event_type=LLM_COMPLETED, source="telemetry", user_id="user",
        payload={"total_tokens": 7, "request_id": "same-inbound-event"},
    )
    assert budget.release(
        tenant_id="tenant", request_id="same-inbound-event", day="2026-11-01",
    )
    monkeypatch.setattr(budget, "_day", lambda: "2026-11-02")
    assert budget.reserve(
        tenant_id="tenant", user_id="user", tokens=100,
        request_id="same-inbound-event",
    ) is None
    assert store.get_setting(
        tenant_id="tenant", key="llm:pending:v1:2026-11-02",
    ) == {"pending": {}}


def test_inbound_idempotency_does_not_depend_on_mutable_offer_or_model():
    from core.marketing.llm.flow import idempotent_request_id

    common = {
        "tenant_id": "tenant", "user_id": "user", "locale": "ru",
        "channel": "telegram", "features": {},
        "message_id": "event-123", "last_user_text": "",
    }
    first = MarketingLLMInputs(
        **common, offer={"id": "offer-one", "title": "Первый"},
    )
    changed = MarketingLLMInputs(
        **common, offer={"id": "offer-two", "title": "Второй"},
    )
    assert idempotent_request_id(
        inp=first, provider="yandex", model="model-a", generated="one",
    ) == idempotent_request_id(
        inp=changed, provider="openai_compat", model="model-b", generated="two",
    )
