import pytest

from core.llm import MockLLMClient
from core.llm.contracts import LLMResponse, LLMUsage
from core.marketing.llm_composer import LLMComposerConfig, MarketingLLMComposer
from core.marketing.llm_prompting import MarketingLLMInputs
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
    composer = MarketingLLMComposer(MockLLMClient(fixed_text=_VALID), LLMComposerConfig(model="mock", budget_source="memory"))
    inp = _input(tenant="t1", user="u1")
    first = composer.compose_sync(inp)
    assert first
    assert composer.compose_sync(inp) == first


def test_composer_rejects_forbidden_phrase():
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), LLMComposerConfig(model="mock", budget_source="memory"))
    assert composer.compose_sync(_input()) is None


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_provider_usage_is_charged_even_when_text_rejected(async_mode):
    composer = MarketingLLMComposer(_UsageLLM(text=_REJECTED), LLMComposerConfig(model="mock", budget_source="memory"))
    assert (await composer.compose(_input()) if async_mode else composer.compose_sync(_input())) is None
    assert not composer._runtime.budget.can_spend(
        tenant_id="tenant", user_id="user", tokens=composer._cfg.budget.user_tokens_per_day - 6,
    )


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("usage", [
    None,
    LLMUsage(),
    LLMUsage(prompt_tokens=-1, completion_tokens=1, total_tokens=1),
    LLMUsage(prompt_tokens=1, completion_tokens=0, total_tokens=-1),
    LLMUsage(prompt_tokens=1.5, completion_tokens=2, total_tokens=3),
    LLMUsage(prompt_tokens="1", completion_tokens=2, total_tokens=3),
    LLMUsage(prompt_tokens=True, completion_tokens=0, total_tokens=1),
])
@pytest.mark.asyncio
async def test_unverified_provider_usage_never_fabricates_durable_spend_or_replays(async_mode, usage):
    llm, store = _UsageLLM(), MemoryEventStore()
    llm.usage = usage
    composer = MarketingLLMComposer(
        llm, LLMComposerConfig(model="mock", budget_source="event_store"), event_store=store,
    )
    inp = _input(tenant="t-invalid-usage", user="u-invalid-usage", message_id="event-1")
    assert (await composer.compose(inp) if async_mode else composer.compose_sync(inp)) is None
    assert store.count_events(tenant_id="t-invalid-usage", event_type=LLM_COMPLETED) == 0
    assert composer._runtime.metrics.snapshot().counters.get("accounting_unavailable") == 1
    assert (await composer.compose(inp) if async_mode else composer.compose_sync(inp)) is None
    assert llm.calls == 1


def test_sync_entrypoint_with_async_only_provider_claims_once():
    class AsyncOnly:
        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            return LLMResponse(content=_VALID, usage=LLMUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7))

    llm, store = AsyncOnly(), MemoryEventStore()
    composer = MarketingLLMComposer(
        llm, LLMComposerConfig(model="mock", budget_source="event_store"), event_store=store,
    )
    assert composer.compose_sync(_input(tenant="t-async-only", user="u-async-only", message_id="event-2"))
    assert llm.calls == 1
    assert store.count_events(tenant_id="t-async-only", event_type=LLM_COMPLETED) == 1


def test_provider_split_usage_is_rejected_when_total_is_zero():
    store, llm = MemoryEventStore(), _UsageLLM(text=_REJECTED, usage=LLMUsage(prompt_tokens=17, completion_tokens=9, total_tokens=0))
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock", budget_source="event_store"), event_store=store)
    inp = _input(message_id="zero-total")
    assert composer.compose_sync(inp) is None
    assert store.count_events(tenant_id="tenant", event_type=LLM_COMPLETED) == 0
    assert composer.compose_sync(inp) is None and llm.calls == 1


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
    inp = _input(tenant="t-no-request", user="u-no-request", message_id="preflight-1")
    result = await composer.compose(inp) if async_mode else composer.compose_sync(inp)
    assert result is None
    assert llm.calls == 0
    assert composer._runtime.metrics.snapshot().counters.get("accounting_unavailable") == 1
    assert composer._event_store.get_setting(
        tenant_id="t-no-request", key=f"llm:pending:v1:{composer._runtime.budget._day()}",
    ) == {"pending": {}}
    # Retained claim prevents retrying a failed preflight under the same inbound id.
    assert (await composer.compose(inp) if async_mode else composer.compose_sync(inp)) is None
    assert llm.calls == 0


@pytest.mark.parametrize("different_scope", ["tenant", "user", "channel"])
def test_marketing_cache_is_isolated_by_tenant_user_and_channel(different_scope):
    llm = _UsageLLM()
    composer = MarketingLLMComposer(llm, LLMComposerConfig(model="mock", budget_source="memory"))
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
    assert await composer.compose(first) if async_mode else composer.compose_sync(first)
    assert (await composer.compose(second) if async_mode else composer.compose_sync(second)) is None
    assert store.count_events(tenant_id="t-dedupe", event_type=LLM_COMPLETED) == 2
    assert store.count_events(tenant_id="t-dedupe", event_type=LLM_SKIPPED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-dedupe", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 14


def test_event_store_budget_reservation_blocks_concurrent_overspend():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock

    from core.llm.budget import BudgetCaps

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
    cfg = LLMComposerConfig(model="mock", budget_source="event_store",
        budget=BudgetCaps(tenant_tokens_per_day=3000, user_tokens_per_day=3000))
    first = MarketingLLMComposer(llm, cfg, event_store=store)
    second = MarketingLLMComposer(llm, cfg, event_store=store)
    inp = MarketingLLMInputs(tenant_id="t-concurrent", user_id="u-concurrent", locale="ru",
        channel="telegram", features={}, offer={"id": "concurrent", "title": "Сеанс", "price": 990, "currency": "₽"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(first.compose_sync, inp)
        assert llm.entered.wait(timeout=5)
        try:
            assert pool.submit(second.compose_sync, inp).result(timeout=5) is None
            assert llm.calls == 1
        finally:
            llm.resume.set()
        assert running.result(timeout=5)
    # Long prompts must not bypass the reservation cap before provider execution.
    huge = MarketingLLMInputs(**{**inp.__dict__, "last_user_text": "long " * 3000})
    assert first.compose_sync(huge) is None
    assert llm.calls == 1
    assert store.sum_event_payload_int(tenant_id="t-concurrent",
        event_type=LLM_COMPLETED, field="total_tokens") == 7
    # Once the durable completion is visible, headroom is available again.
    assert second._runtime.budget.can_spend(tenant_id="t-concurrent", user_id="u-concurrent", tokens=2993)


def test_missing_atomic_reservation_fails_closed_before_provider():
    class NoCASStore(MemoryEventStore):
        compare_and_set_setting = None

    llm = _UsageLLM()
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(
            llm, LLMComposerConfig(model="mock", budget_source="event_store"),
            event_store=NoCASStore(),
        )
    assert llm.calls == 0


def test_sqlite_budget_reservations_are_shared_between_store_connections(tmp_path):
    from core.events.log import EventLog
    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
    from core.tenancy.scope import TenantScope
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    caps = BudgetCaps(tenant_tokens_per_day=1027, user_tokens_per_day=1027)
    path = str(tmp_path / "llm-reservations.sqlite3")
    with SqliteEventStore(path) as first_store, SqliteEventStore(path) as second_store:
        first = EventStoreDailyTokenBudget(event_store=first_store, caps=caps)
        second = EventStoreDailyTokenBudget(event_store=second_store, caps=caps)
        assert second.can_spend(tenant_id="tenant", user_id="user", tokens=1027)
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
        assert not second.can_spend(tenant_id="tenant", user_id="user", tokens=1027)
        assert second.reserve(
            tenant_id="tenant", user_id="user", tokens=1020, request_id="second",
        ) == day


def test_postgres_budget_claim_is_atomic_across_independent_connections():
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from urllib.parse import urlsplit
    from uuid import uuid4

    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
    from runtime.platform.event_store.postgres_event_store import PostgresEventStore

    dsn = os.environ.get("BUSINESAIOS_TEST_POSTGRES_DSN", "")
    if not dsn:
        pytest.skip("isolated PostgreSQL test DSN not configured")
    if not urlsplit(dsn).path.lstrip("/").startswith("businesaios_test_"):
        pytest.fail("PostgreSQL budget test requires an isolated businesaios_test_* database")

    tenant = f"budget-concurrency-{uuid4().hex}"
    barrier = Barrier(8)
    caps = BudgetCaps(tenant_tokens_per_day=1027, user_tokens_per_day=1027)

    def reserve_once(index):
        with PostgresEventStore(dsn, enabled=True) as store:
            budget = EventStoreDailyTokenBudget(event_store=store, caps=caps)
            barrier.wait(timeout=15)
            return budget.reserve(
                tenant_id=tenant, user_id="user", tokens=1020, request_id=f"request-{index}",
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reserve_once, range(8)))
    assert sum(day is not None for day in outcomes) == 1

    winner = outcomes.index(next(day for day in outcomes if day))
    with PostgresEventStore(dsn, enabled=True) as store:
        from core.events.log import EventLog
        from core.tenancy.scope import TenantScope

        budget = EventStoreDailyTokenBudget(event_store=store, caps=caps)
        assert budget.reserve(
            tenant_id=tenant, user_id="user", tokens=1020, request_id=f"request-{winner}",
        ) is None
        EventLog(store, tenant=TenantScope(tenant)).emit(
            event_type=LLM_COMPLETED, source="telemetry", user_id="user",
            payload={"request_id": f"request-{winner}", "total_tokens": 7},
        )
    with PostgresEventStore(dsn, enabled=True) as store:
        budget = EventStoreDailyTokenBudget(event_store=store, caps=caps)
        assert budget.reserve(tenant_id=tenant, user_id="user", tokens=1020, request_id="recovered") is not None


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.asyncio
async def test_replayed_message_id_does_not_recharge_or_reinvoke_provider(async_mode):
    llm, store = _UsageLLM(), MemoryEventStore()
    cfg = LLMComposerConfig(model="mock", budget_source="event_store")
    inp = _input(tenant="t-replay", user="u-replay", message_id="incoming-123")
    first = MarketingLLMComposer(llm, cfg, event_store=store)
    second = MarketingLLMComposer(llm, cfg, event_store=store)
    changed = _input(
        tenant="t-replay", user="u-replay", message_id="incoming-123",
        features={"segment": "changed-after-retry"},
    )
    assert await first.compose(inp) if async_mode else first.compose_sync(inp)
    assert (await second.compose(changed) if async_mode else second.compose_sync(changed)) is None
    assert llm.calls == 1
    assert store.count_events(tenant_id="t-replay", event_type=LLM_COMPLETED) == 1
    assert store.sum_event_payload_int(
        tenant_id="t-replay", event_type=LLM_COMPLETED, field="total_tokens",
    ) == 7


@pytest.mark.asyncio
async def test_optional_debug_event_failure_does_not_strand_durable_spend():
    from core.llm.sampling import DebugSampling

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
    inp = _input(tenant="t-debug", user="u-debug", message_id="debug-event-1",
                 offer={"id": "debug", "title": "Сеанс", "price": 990, "currency": "₽"})
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
    from core.tenancy.scope import TenantScope

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


@pytest.mark.parametrize("claim_was_committed", [False, True])
def test_claim_write_error_releases_pending_headroom_without_replaying(claim_was_committed):
    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget

    class BrokenClaimStore(MemoryEventStore):
        def compare_and_set_setting(self, *, tenant_id, key, expected, value):
            if key.startswith("llm:claim:v2:") and not getattr(self, "_failed_once", False):
                self._failed_once = True
                if claim_was_committed:
                    super().compare_and_set_setting(
                        tenant_id=tenant_id, key=key, expected=expected, value=value,
                    )
                raise OSError("claim storage interrupted")
            return super().compare_and_set_setting(
                tenant_id=tenant_id, key=key, expected=expected, value=value,
            )

    store = BrokenClaimStore()
    budget = EventStoreDailyTokenBudget(
        event_store=store, caps=BudgetCaps(tenant_tokens_per_day=100, user_tokens_per_day=100),
    )
    with pytest.raises(OSError, match="claim storage interrupted"):
        budget.reserve(tenant_id="t", user_id="u", tokens=50, request_id="event-1")
    assert store.get_setting(tenant_id="t", key=f"llm:pending:v1:{budget._day()}") == {"pending": {}}
    assert bool(store.get_setting(tenant_id="t", key="llm:claim:v2:event-1")) is claim_was_committed
    if claim_was_committed:
        assert budget.reserve(tenant_id="t", user_id="u", tokens=50, request_id="event-1") is None


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

@pytest.mark.parametrize("completion_user, expected_recovery", [("u", True), ("other", False)])
def test_completed_claim_reconciles_after_crash_but_uncompleted_claim_stays(completion_user, expected_recovery):
    from core.events.log import EventLog
    from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
    from core.tenancy.scope import TenantScope

    store = MemoryEventStore()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps(tenant_tokens_per_day=100, user_tokens_per_day=100))
    day = budget.reserve(tenant_id="t", user_id="u", tokens=80, request_id="completed")
    assert day
    EventLog(store, tenant=TenantScope("t")).emit(
        event_type=LLM_COMPLETED, source="telemetry", user_id=completion_user,
        payload={"request_id": "completed", "total_tokens": 20},
    )
    recovered = budget.reserve(tenant_id="t", user_id="u", tokens=70, request_id="new")
    assert (recovered == day) is expected_recovery
    assert budget.reserve(tenant_id="t", user_id="u", tokens=20, request_id="blocked") is None
    assert set(store.get_setting(tenant_id="t", key=f"llm:pending:v1:{day}")["pending"]) == (
        {"new"} if expected_recovery else {"completed"}
    )

@pytest.mark.parametrize("source", ["auto", "event_store", ""])
def test_default_and_auto_budget_never_call_provider_without_durable_store(source):
    llm = _UsageLLM()
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(llm, LLMComposerConfig(model="mock", budget_source=source))
    assert llm.calls == 0


def test_real_provider_transport_never_runs_without_durable_budget():
    from core.llm import build_openai_compat

    calls = []
    provider = build_openai_compat(base_url="https://example.invalid/v1", api_key="fake",
                                  transport=lambda *args: calls.append(args) or {})
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(provider, LLMComposerConfig(model="real-provider"))
    assert calls == []


def test_unknown_budget_source_cannot_fall_back_to_memory():
    with pytest.raises(RuntimeError, match="LLM_BUDGET_SOURCE_INVALID"):
        MarketingLLMComposer(_UsageLLM(), LLMComposerConfig(model="mock", budget_source="typo"),
                             event_store=MemoryEventStore())


def test_explicit_durable_budget_rejects_missing_store():
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(_UsageLLM(), LLMComposerConfig(model="mock", budget_source="event_store"))
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(_UsageLLM(), LLMComposerConfig(model="mock", budget_source="event_store"),
                             event_store=object())


def test_boot_llm_cannot_fall_back_to_process_local_budget(monkeypatch):
    from types import SimpleNamespace

    from core.llm.budget import EventStoreDailyTokenBudget
    from runtime.boot.builders import marketing_llm as boot

    class Logger:
        def warning(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

    llm = _UsageLLM()
    monkeypatch.setattr(boot, "_build_llm_client", lambda **kwargs: ("mock", "mock", llm))
    settings = SimpleNamespace(LLM_ENABLED=True, LLM_BUDGET_SOURCE="memory")
    assert boot.build_marketing_llm_composer(settings=settings, event_store=None, logger=Logger()) is None
    assert boot.build_marketing_llm_composer(settings=settings, event_store=object(), logger=Logger()) is None
    composer = boot.build_marketing_llm_composer(settings=settings, event_store=MemoryEventStore(), logger=Logger())
    assert isinstance(composer._runtime.budget, EventStoreDailyTokenBudget)
    assert composer.compose_sync(_input(tenant="t-boot", user="u-boot", message_id="boot-1"))

@pytest.mark.parametrize("provider", ["openai_compat", "anthropic", "gigachat", "yandexgpt"])
def test_explicit_memory_budget_never_allows_live_provider_transport(provider):
    """Explicit memory mode must not be an escape hatch for paid provider clients."""
    from core.llm import AnthropicClient, GigaChatClient, OpenAICompatClient, OpenAICompatConfig, YandexGPTClient

    called = []
    def transport(*args):
        called.append(args)
        return {}
    clients = {
        "openai_compat": OpenAICompatClient(OpenAICompatConfig(
            base_url="https://example.invalid", api_key="unused", transport=transport,
        )),
        "anthropic": AnthropicClient(
            transport=transport, base_url="https://example.invalid", api_key="unused", model="mock",
        ),
        "gigachat": GigaChatClient(
            transport=transport, base_url="https://example.invalid", api_key="unused", model="mock",
        ),
        "yandexgpt": YandexGPTClient(
            transport=transport, base_url="https://example.invalid", api_key="unused", model="mock",
        ),
    }
    with pytest.raises(RuntimeError, match="LLM_BUDGET_EVENT_STORE_UNAVAILABLE"):
        MarketingLLMComposer(clients[provider], LLMComposerConfig(model="mock", budget_source="memory"))
    assert called == []
