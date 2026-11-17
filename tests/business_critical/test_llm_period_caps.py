"""Weekly/monthly LLM token caps on the single canonical budget owner (#569 scope)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

import core.llm.budget as budget_mod
from config.llm_budget_policy import LLMBudgetPolicy, _optional_period_caps_from_env
from core.llm.budget import BudgetCaps, DailyTokenBudget, EventStoreDailyTokenBudget
from core.telemetry.event_types import LLM_COMPLETED

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)  # Wednesday; week starts Mon 16th, month 1st.


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class _Store:
    supports_durable_llm_budget = True

    def __init__(self, completed: list[tuple[datetime, str, int]]) -> None:
        self.events = [
            (_ms(ts), {"user_id": user, "payload": {"request_id": f"r{i}", "provider": "yandexgpt", "model": "yandexgpt-lite",
                                                     "prompt_tokens": 0, "completion_tokens": tokens, "total_tokens": tokens}})
            for i, (ts, user, tokens) in enumerate(completed)
        ]
        self.settings: dict[str, object] = {}

    def iter_events(self, *, tenant_id, start_ms, end_ms, event_type):
        assert event_type == LLM_COMPLETED
        return [ev for ts, ev in self.events if start_ms <= ts < end_ms]

    def get_setting(self, *, tenant_id, key):
        return self.settings.get(key)

    def compare_and_set_setting(self, *, tenant_id, key, expected, value):
        if self.settings.get(key) != expected:
            return False
        self.settings[key] = value
        return True

    def append_event(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError


@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch):
    monkeypatch.setattr(budget_mod.time, "time", lambda: NOW.timestamp())
    monkeypatch.setattr(budget_mod, "day_key_utc", lambda *a, **k: NOW.date().isoformat())


def _caps(**kw) -> BudgetCaps:
    return BudgetCaps(tenant_tokens_per_day=1_000, user_tokens_per_day=1_000, **kw)


def test_period_caps_are_off_by_default_and_day_behaviour_is_unchanged():
    assert BudgetCaps().periods()[0][0] == "day" and len(BudgetCaps().periods()) == 1
    store = _Store([(datetime(2026, 11, 16, 9, tzinfo=UTC), "u1", 900)])
    assert EventStoreDailyTokenBudget(event_store=store, caps=_caps()).reserve(
        tenant_id="t1", user_id="u1", tokens=900, request_id="new") == "2026-11-18"


def test_weekly_tenant_cap_counts_earlier_days_of_the_iso_week_only():
    store = _Store([
        (datetime(2026, 11, 15, 23, 59, tzinfo=UTC), "u1", 5_000),  # Sunday: previous week
        (datetime(2026, 11, 16, 9, tzinfo=UTC), "u1", 600),
        (datetime(2026, 11, 17, 9, tzinfo=UTC), "u2", 300),
    ])
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(tenant_tokens_per_week=1_000))
    assert budget.reserve(tenant_id="t1", user_id="u1", tokens=101, request_id="over") is None
    assert budget.reserve(tenant_id="t1", user_id="u1", tokens=100, request_id="fits") == "2026-11-18"
    # The pending claim of today now also counts against the week.
    assert budget.reserve(tenant_id="t1", user_id="u3", tokens=1, request_id="after") is None


def test_monthly_user_cap_is_per_user_and_ignores_previous_month():
    store = _Store([
        (datetime(2026, 10, 31, 23, 0, tzinfo=UTC), "u1", 9_000),
        (datetime(2026, 11, 2, 9, tzinfo=UTC), "u1", 700),
        (datetime(2026, 11, 3, 9, tzinfo=UTC), "u2", 700),
    ])
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(user_tokens_per_month=800))
    assert not budget.can_spend(tenant_id="t1", user_id="u1", tokens=101)
    assert budget.can_spend(tenant_id="t1", user_id="u1", tokens=100)
    assert budget.reserve(tenant_id="t1", user_id="u2", tokens=100, request_id="u2-ok") == "2026-11-18"
    assert budget.reserve(tenant_id="t1", user_id="u1", tokens=101, request_id="u1-over") is None


def test_corrupt_completion_inside_the_month_window_fails_closed():
    store = _Store([(datetime(2026, 11, 2, 9, tzinfo=UTC), "u1", 10)])
    store.events[0][1]["payload"]["total_tokens"] = "10"
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(tenant_tokens_per_month=10_000))
    with pytest.raises(RuntimeError, match="LLM_BUDGET_CORRUPT_COMPLETION"):
        budget.reserve(tenant_id="t1", user_id="u1", tokens=1, request_id="x")


@pytest.mark.parametrize("bad", [-1, True, 1.5, "100"])
def test_invalid_caps_are_rejected(bad):
    with pytest.raises(ValueError):
        BudgetCaps(tenant_tokens_per_week=bad)
    with pytest.raises(ValueError):
        BudgetCaps(user_tokens_per_day=bad)


def test_in_memory_fallback_refuses_rather_than_ignoring_period_caps():
    assert DailyTokenBudget(_caps()).can_spend(tenant_id="t1", user_id="u1", tokens=1)
    assert not DailyTokenBudget(_caps(tenant_tokens_per_month=10)).can_spend(tenant_id="t1", user_id="u1", tokens=1)


def test_env_binding_is_off_when_unset_and_rejects_garbage(monkeypatch):
    for name in ("TENANT_TOKENS_PER_WEEK", "USER_TOKENS_PER_WEEK", "TENANT_TOKENS_PER_MONTH", "USER_TOKENS_PER_MONTH"):
        monkeypatch.delenv(f"LLM_{name}", raising=False)
    assert _optional_period_caps_from_env() == {}
    monkeypatch.setenv("LLM_TENANT_TOKENS_PER_MONTH", "5000000")
    assert LLMBudgetPolicy(**_optional_period_caps_from_env()).tenant_tokens_per_month == 5_000_000
    monkeypatch.setenv("LLM_USER_TOKENS_PER_WEEK", "-5")
    with pytest.raises(ValueError):
        _optional_period_caps_from_env()

def test_cross_midnight_unfinished_reservation_counts_against_week_and_month(monkeypatch):
    from datetime import timedelta
    clock = [datetime(2026, 11, 17, 23, 59, tzinfo=UTC)]
    monkeypatch.setattr(budget_mod.time, "time", lambda: clock[0].timestamp())
    monkeypatch.setattr(budget_mod, "day_key_utc", lambda: clock[0].date().isoformat())
    store = _Store([])
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(
        tenant_tokens_per_week=100, tenant_tokens_per_month=100))
    assert budget.reserve(tenant_id="t", user_id="u", tokens=80, request_id="old") == "2026-11-17"
    clock[0] += timedelta(minutes=2)
    assert budget.reserve(tenant_id="t", user_id="u", tokens=21, request_id="overflow") is None
    assert budget.reserve(tenant_id="t", user_id="u", tokens=20, request_id="fits") == "2026-11-18"
    assert budget.release(tenant_id="t", request_id="old", day="2026-11-17")
    assert budget.reserve(tenant_id="t", user_id="u", tokens=80, request_id="after-release") == "2026-11-18"


def test_legacy_pending_from_previous_day_is_counted(monkeypatch):
    from datetime import timedelta
    clock = [datetime(2026, 11, 17, 23, 59, tzinfo=UTC)]
    monkeypatch.setattr(budget_mod.time, "time", lambda: clock[0].timestamp())
    monkeypatch.setattr(budget_mod, "day_key_utc", lambda: clock[0].date().isoformat())
    store = _Store([])
    store.settings["llm:pending:v1:2026-11-17"] = {"pending": {"old": {"user_id": "u", "tokens": 95}}}
    clock[0] += timedelta(minutes=2)
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(tenant_tokens_per_week=100))
    assert budget.reserve(tenant_id="t", user_id="u", tokens=6, request_id="blocked") is None
    assert budget.reserve(tenant_id="t", user_id="u", tokens=5, request_id="fits") == "2026-11-18"


def test_single_cas_key_coordinates_new_reservations_across_days(monkeypatch):
    from datetime import timedelta
    clock = [datetime(2026, 11, 17, 23, 59, tzinfo=UTC)]
    monkeypatch.setattr(budget_mod.time, "time", lambda: clock[0].timestamp())
    monkeypatch.setattr(budget_mod, "day_key_utc", lambda: clock[0].date().isoformat())
    store = _Store([])
    budget = EventStoreDailyTokenBudget(event_store=store, caps=_caps(tenant_tokens_per_week=100))
    assert budget.reserve(tenant_id="t", user_id="u", tokens=75, request_id="tuesday")
    clock[0] += timedelta(minutes=2)
    assert budget.reserve(tenant_id="t", user_id="u", tokens=26, request_id="wednesday") is None
    assert set(store.settings["llm:pending:v2"]["pending"]) == {"tuesday"}
