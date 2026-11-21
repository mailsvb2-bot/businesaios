from __future__ import annotations

from datetime import UTC, datetime
from threading import Barrier, Lock, Thread

from config.llm_budget_policy import LLMBudgetPolicy
from core.llm.budget import BudgetCaps, EventStoreDailyTokenBudget
from core.telemetry.event_types import LLM_COMPLETED


class _Store:
    def __init__(self) -> None:
        self.state = {"pending": {"request-1": {"user_id": "user-1", "tokens": 10}}}
        self.windows: list[tuple[int, int]] = []

    def iter_events(self, *, tenant_id, start_ms, end_ms, event_type):
        assert (tenant_id, event_type) == ("tenant-1", LLM_COMPLETED)
        self.windows.append((start_ms, end_ms))
        completed_at = int(datetime(2026, 11, 8, 23, 59, tzinfo=UTC).timestamp() * 1000)
        if start_ms <= completed_at < end_ms:
            yield {"user_id": "user-1", "payload": {"request_id": "request-1", "provider": "openai", "model": "gpt-4.1-mini", "prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}}

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        assert (tenant_id, key) == ("tenant-1", "llm:pending:v1:2026-11-08")
        if self.state != expected:
            return False
        self.state = value
        return True


def test_reconcile_uses_reservation_day_not_current_day():
    store = _Store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert budget._reconcile_completed(tenant_id="tenant-1", day="2026-11-08", current=store.state)
    expected_start = int(datetime(2026, 11, 8, tzinfo=UTC).timestamp() * 1000)
    assert (store.state, store.windows) == ({"pending": {}}, [(expected_start, expected_start + 86_400_000)])


def test_reconcile_rejects_invalid_day_without_releasing_claim():
    store = _Store()
    budget = EventStoreDailyTokenBudget(event_store=store, caps=BudgetCaps())
    assert not budget._reconcile_completed(tenant_id="tenant-1", day="2026-11-08-invalid", current=store.state)
    assert (store.state["pending"]["request-1"]["tokens"], store.windows) == (10, [])


class _PeriodStore:
    def __init__(self, *, events=(), settings=None):
        self.events = list(events)
        self.settings = dict(settings or {})
        self.windows = []

    def iter_events(self, *, tenant_id, start_ms, end_ms, event_type):
        self.windows.append((start_ms, end_ms))
        for event in self.events:
            if event["tenant_id"] != tenant_id or event["event_type"] != event_type:
                continue
            if start_ms <= event["created_at_ms"] < end_ms:
                yield {"user_id": event["user_id"], "payload": event["payload"]}

    def get_setting(self, *, tenant_id, key):
        return self.settings.get((tenant_id, key))

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        current = self.settings.get((tenant_id, key))
        if current != expected:
            return False
        self.settings[(tenant_id, key)] = value
        return True


def _period_event(day, user_id, request_id, tokens):
    created_at_ms = int(datetime.fromisoformat(day).replace(tzinfo=UTC).timestamp() * 1000)
    return {
        "tenant_id": "tenant-1",
        "event_type": LLM_COMPLETED,
        "created_at_ms": created_at_ms,
        "user_id": user_id,
        "payload": {
            "request_id": request_id,
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "prompt_tokens": tokens,
            "completion_tokens": 0,
            "total_tokens": tokens,
        },
    }


def _period_budget(store, *, weekly_tenant=1000, weekly_user=1000, monthly_tenant=1000, monthly_user=1000, day="2026-11-15"):
    caps = BudgetCaps(
        tenant_tokens_per_day=1000,
        user_tokens_per_day=1000,
        tenant_tokens_per_week=weekly_tenant,
        user_tokens_per_week=weekly_user,
        tenant_tokens_per_month=monthly_tenant,
        user_tokens_per_month=monthly_user,
    )
    budget = EventStoreDailyTokenBudget(event_store=store, caps=caps)
    budget._day = lambda: day
    return budget


def test_weekly_budget_counts_completed_usage_from_earlier_days():
    store = _PeriodStore(events=[_period_event("2026-11-10", "user-1", "week-spend", 90)])
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=10)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=11)
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=11, request_id="blocked-week") is None


def test_monthly_budget_counts_completed_usage_from_earlier_weeks():
    store = _PeriodStore(events=[_period_event("2026-11-02", "user-1", "month-spend", 95)])
    budget = _period_budget(store, weekly_tenant=1000, weekly_user=1000, monthly_tenant=100, monthly_user=100)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=6)
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=6, request_id="blocked-month") is None


def test_weekly_window_starts_on_monday_and_excludes_previous_sunday():
    store = _PeriodStore(events=[_period_event("2026-11-08", "user-1", "previous-week", 90)])
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=20)


def test_monthly_window_excludes_previous_month_completion():
    store = _PeriodStore(events=[_period_event("2026-10-31", "user-1", "previous-month", 90)])
    budget = _period_budget(store, weekly_tenant=1000, weekly_user=1000, monthly_tenant=100, monthly_user=100)
    assert budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=20)


def test_period_budget_counts_pending_reservations_from_prior_days():
    settings = {
        ("tenant-1", "llm:pending:v1:2026-11-10"): {
            "pending": {"old-request": {"user_id": "user-1", "tokens": 80}},
        },
    }
    store = _PeriodStore(settings=settings)
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=21)
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=21, request_id="blocked-pending") is None


def test_period_reconciliation_releases_only_durable_completed_prior_day_claims():
    settings = {
        ("tenant-1", "llm:pending:v1:2026-11-10"): {
            "pending": {"old-request": {"user_id": "user-1", "tokens": 80}},
        },
    }
    store = _PeriodStore(
        events=[_period_event("2026-11-10", "user-1", "old-request", 10)],
        settings=settings,
    )
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=80, request_id="new-request") == "2026-11-15"
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v1:2026-11-10") == {"pending": {}}
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2") == {
        "revision": 1,
        "pending": {"new-request": {"user_id": "user-1", "tokens": 80, "day": "2026-11-15"}},
    }


def test_week_reconciliation_includes_prior_month_days_when_month_starts_on_sunday():
    settings = {
        ("tenant-1", "llm:pending:v1:2026-10-28"): {
            "pending": {"old-request": {"user_id": "user-1", "tokens": 80}},
        },
    }
    store = _PeriodStore(
        events=[_period_event("2026-10-28", "user-1", "old-request", 10)],
        settings=settings,
    )
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100, day="2026-11-01")
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=80, request_id="new-request") == "2026-11-01"
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v1:2026-10-28") == {"pending": {}}
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2") == {
        "revision": 1,
        "pending": {"new-request": {"user_id": "user-1", "tokens": 80, "day": "2026-11-01"}},
    }



def test_reserve_cancels_claim_when_utc_day_changes_after_cas():
    store = _PeriodStore()
    budget = _period_budget(store, day="2026-11-15")
    days = iter(("2026-11-15", "2026-11-15", "2026-11-16"))
    budget._day = lambda: next(days)

    assert budget.reserve(
        tenant_id="tenant-1", user_id="user-1", tokens=10, request_id="midnight-race",
    ) is None
    assert store.get_setting(
        tenant_id="tenant-1", key="llm:pending:v2",
    ) == {"revision": 2, "pending": {}}
    assert store.get_setting(
        tenant_id="tenant-1", key="llm:claim:v2:midnight-race",
    ) is None



def test_budget_caps_keep_optional_period_caps_off_until_configured():
    caps = BudgetCaps(tenant_tokens_per_day=100, user_tokens_per_day=20)
    assert (caps.tenant_tokens_per_week, caps.user_tokens_per_week,
            caps.tenant_tokens_per_month, caps.user_tokens_per_month) == (None, None, None, None)
    policy = LLMBudgetPolicy(tenant_tokens_per_day=50, user_tokens_per_day=10)
    policy_caps = BudgetCaps(policy=policy)
    assert (policy_caps.tenant_tokens_per_week, policy_caps.user_tokens_per_week,
            policy_caps.tenant_tokens_per_month, policy_caps.user_tokens_per_month) == (None, None, None, None)

    explicit = BudgetCaps(
        tenant_tokens_per_day=100,
        user_tokens_per_day=20,
        tenant_tokens_per_week=500,
        user_tokens_per_week=120,
        tenant_tokens_per_month=2000,
        user_tokens_per_month=500,
    )
    assert (explicit.tenant_tokens_per_week, explicit.user_tokens_per_week) == (500, 120)

def test_policy_period_caps_remain_authoritative_when_daily_caps_are_overridden():
    policy = LLMBudgetPolicy(
        tenant_tokens_per_day=100, user_tokens_per_day=20,
        tenant_tokens_per_week=500, user_tokens_per_week=120,
        tenant_tokens_per_month=2000, user_tokens_per_month=500,
    )
    caps = BudgetCaps(policy=policy, tenant_tokens_per_day=50, user_tokens_per_day=10)
    assert (caps.tenant_tokens_per_week, caps.user_tokens_per_week) == (500, 120)
    assert (caps.tenant_tokens_per_month, caps.user_tokens_per_month) == (2000, 500)



class _ConcurrentPeriodStore(_PeriodStore):
    def __init__(self, barrier):
        super().__init__()
        self._lock = Lock()
        self._barrier = barrier
        self._initial_reads = 0

    def get_setting(self, *, tenant_id, key):
        with self._lock:
            value = self.settings.get((tenant_id, key))
            wait = key == "llm:pending:v2" and value is None and self._initial_reads < 2
            if wait:
                self._initial_reads += 1
        if wait:
            self._barrier.wait(timeout=3)
        return value

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        with self._lock:
            current = self.settings.get((tenant_id, key))
            if current != expected:
                return False
            self.settings[(tenant_id, key)] = value
            return True


def test_weekly_reservations_are_atomic_across_distinct_utc_days():
    store = _ConcurrentPeriodStore(Barrier(2))
    caps = dict(
        weekly_tenant=100, weekly_user=100,
        monthly_tenant=1000, monthly_user=1000,
    )
    first = _period_budget(store, **caps, day="2026-11-09")
    second = _period_budget(store, **caps, day="2026-11-10")
    results = {}

    def reserve(name, budget):
        results[name] = budget.reserve(
            tenant_id="tenant-1", user_id="user-1", tokens=60, request_id=name,
        )

    threads = [Thread(target=reserve, args=("worker-a", first)), Thread(target=reserve, args=("worker-b", second))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert sum(value is not None for value in results.values()) == 1
    state = store.get_setting(tenant_id="tenant-1", key="llm:pending:v2")
    assert sum(row["tokens"] for row in state["pending"].values()) == 60


def test_completion_after_utc_midnight_reconciles_prior_day_reservation():
    reservation_day = "2026-11-15"
    current_day = "2026-11-16"
    state = {"revision": 1, "pending": {
        "cross-midnight": {"user_id": "user-1", "tokens": 10, "day": reservation_day},
    }}
    store = _PeriodStore(
        events=[_period_event(current_day, "user-1", "cross-midnight", 10)],
        settings={("tenant-1", "llm:pending:v2"): state},
    )
    budget = _period_budget(store, day=current_day)
    assert budget._reconcile_v2(
        tenant_id="tenant-1", current=state,
    )
    expected_start = int(datetime.fromisoformat(reservation_day).replace(tzinfo=UTC).timestamp() * 1000)
    expected_end = int(datetime.fromisoformat("2026-11-17").replace(tzinfo=UTC).timestamp() * 1000)
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2") == {"revision": 2, "pending": {}}
    assert store.windows == [(expected_start, expected_end)]


def test_unreconciled_legacy_writer_after_v2_cutover_fails_closed():
    store = _PeriodStore(settings={
        ("tenant-1", "llm:pending:v2"): {
            "revision": 0,
            "pending": {"known": {"user_id": "user-1", "tokens": 10, "day": "2026-11-15"}},
        },
        ("tenant-1", "llm:pending:v1:2026-11-15"): {
            "pending": {"late-legacy": {"user_id": "user-1", "tokens": 10}},
        },
    })
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=1)
    assert budget.reserve(
        tenant_id="tenant-1", user_id="user-1", tokens=1, request_id="must-not-start",
    ) is None
    assert store.get_setting(
        tenant_id="tenant-1", key="llm:pending:v2",
    )["pending"] == {"known": {"user_id": "user-1", "tokens": 10, "day": "2026-11-15"}}


def test_pending_period_reservation_is_isolated_by_tenant_and_user():
    store = _PeriodStore(settings={
        ("tenant-1", "llm:pending:v2"): {
            "revision": 1,
            "pending": {"other-user-request": {"user_id": "user-1", "tokens": 80, "day": "2026-11-15"}},
        },
    })
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert budget.can_spend(tenant_id="tenant-1", user_id="user-2", tokens=20)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-2", tokens=21)
    assert budget.can_spend(tenant_id="tenant-2", user_id="user-2", tokens=21)
    assert not budget.can_spend(tenant_id="tenant-1", user_id="user-1", tokens=21)


def test_completed_legacy_claim_after_v2_cutover_reconciles_before_new_admission():
    state = {"revision": 0, "pending": {}}
    store = _PeriodStore(
        events=[_period_event("2026-11-10", "user-1", "old-request", 10)],
        settings={
            ("tenant-1", "llm:pending:v2"): state,
            ("tenant-1", "llm:pending:v1:2026-11-10"): {
                "pending": {"old-request": {"user_id": "user-1", "tokens": 80}},
            },
        },
    )
    budget = _period_budget(store, weekly_tenant=100, weekly_user=100)
    assert budget.reserve(tenant_id="tenant-1", user_id="user-1", tokens=80, request_id="new-request") == "2026-11-15"
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v1:2026-11-10") == {"pending": {}}
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2")["revision"] == 1


class _AbaInterleavingStore(_PeriodStore):
    def __init__(self):
        super().__init__(settings={
            ("tenant-1", "llm:pending:v2"): {"revision": 0, "pending": {}},
        })
        self.interleave = True
        self.second_budget = None
        self.second_result = None

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        if key == "llm:pending:v2" and self.interleave:
            self.interleave = False
            self.second_result = self.second_budget.reserve(
                tenant_id="tenant-1", user_id="user-1", tokens=80, request_id="worker-b",
            )
            assert self.second_result == "2026-11-09"
            self.events.append(_period_event("2026-11-09", "user-1", "worker-b", 80))
            assert self.second_budget.release(
                tenant_id="tenant-1", request_id="worker-b", day="2026-11-09",
            )
        return super().compare_and_set_setting(tenant_id=tenant_id, key=key, expected=expected, value=value)


def test_reservation_revision_prevents_aba_overspend_after_completed_release():
    store = _AbaInterleavingStore()
    first = _period_budget(store, weekly_tenant=100, weekly_user=100, day="2026-11-09")
    store.second_budget = _period_budget(store, weekly_tenant=100, weekly_user=100, day="2026-11-09")

    assert first.reserve(
        tenant_id="tenant-1", user_id="user-1", tokens=80, request_id="worker-a",
    ) is None
    state = store.get_setting(tenant_id="tenant-1", key="llm:pending:v2")
    assert state == {"revision": 2, "pending": {}}
    assert len(store.events) == 1

def test_cancel_unstarted_reservation_releases_its_pending_claim():
    store = _PeriodStore()
    budget = _period_budget(store)
    day = budget.reserve(
        tenant_id="tenant-1", user_id="user-1", tokens=10, request_id="pre-provider-abort",
    )
    assert day == "2026-11-15"
    claim_key = "llm:claim:v2:pre-provider-abort"
    assert store.get_setting(tenant_id="tenant-1", key=claim_key) == {"user_id": "user-1"}

    assert budget.cancel_unstarted_reservation(
        tenant_id="tenant-1", request_id="pre-provider-abort", day=day,
    )
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2") == {
        "revision": 2, "pending": {},
    }
    assert store.get_setting(tenant_id="tenant-1", key=claim_key) is None


def test_failed_duplicate_reservation_does_not_delete_existing_claim():
    claim_key = "llm:claim:v2:already-claimed"
    store = _PeriodStore(settings={
        ("tenant-1", claim_key): {"user_id": "user-1"},
    })
    budget = _period_budget(store)

    assert budget.reserve(
        tenant_id="tenant-1", user_id="user-1", tokens=10, request_id="already-claimed",
    ) is None
    assert store.get_setting(tenant_id="tenant-1", key=claim_key) == {"user_id": "user-1"}
    assert store.get_setting(tenant_id="tenant-1", key="llm:pending:v2") == {
        "revision": 2, "pending": {},
    }
