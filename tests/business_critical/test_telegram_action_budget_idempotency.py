from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import runtime.safety_controls as safety
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import (
    ActionBudget,
    issue_verified_update_idempotency_key,
    verified_inbound_reply_scope,
)
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger


def _catalog():
    return SimpleNamespace(resolve=lambda _action: SimpleNamespace(default_estimated_cost=1.0))

def _runtime(ledger, catalog):
    return SimpleNamespace(profile=SimpleNamespace( action_budget_ledger=ledger, action_catalog=catalog, ))

def test_verified_telegram_retry_is_charged_once(monkeypatch):
    tenant, user, bot, update_id, chat = "tenant-live", "4001", "primary", 42, "4001"
    ledger, catalog = InMemoryActionBudgetLedger(), _catalog()
    monkeypatch.setattr(safety, "build_safety_control_runtime", lambda: _runtime(ledger, catalog))
    monkeypatch.setattr(safety, "_record_safety_event", lambda **_kwargs: None)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=10.0, max_actions=1), catalog)

    with verified_inbound_reply_scope( tenant_id=tenant, channel="telegram", user_id=user, update_id=update_id, chat_id=chat, bot_id=bot, ):
        payload = {"tenant_id": tenant, "user_id": user, "op": "book", "arg": "1"}
        key = issue_verified_update_idempotency_key( tenant_id=tenant, channel="telegram", user_id=user, update_id=update_id, chat_id=chat, bot_id=bot, )
        assert key
        payload["idempotency_key"] = key
        context = SafetyActionContext("bookings@v1", tenant, user, payload)

        first = guard.evaluate(context)
        assert first.status == ControlStatus.ALLOW
        safety.record_allowed_action(action="bookings@v1", payload=payload)
        assert ledger.snapshot(tenant) == (1.0, 1)

        replay = guard.evaluate(context)
        assert replay.status == ControlStatus.ALLOW
        assert replay.reason == "action_budget_replay_already_accounted"
        safety.record_allowed_action(action="bookings@v1", payload=payload)
        assert ledger.snapshot(tenant) == (1.0, 1)

        mismatch = guard.evaluate(SafetyActionContext( "capture_payment@v1", tenant, user, payload, ))
        assert mismatch.status == ControlStatus.BLOCK
        assert mismatch.reason == "action_budget_idempotency_conflict"

def test_unverified_telegram_key_cannot_bypass_exhausted_budget():
    tenant, user, key = "tenant-live", "4001", "telegram:forged"
    ledger = InMemoryActionBudgetLedger()
    ledger.record_once(tenant, idempotency_key=key, action="bookings@v1", payload_hash="bookings-payload", estimated_cost=1.0)
    guard = ActionBudgetGuard( ledger, ActionBudget(max_cost=10.0, max_actions=1), _catalog(), )
    result = guard.evaluate(SafetyActionContext( "bookings@v1", tenant, user, {"tenant_id": tenant, "user_id": user, "op": "book", "arg": "1",
         "idempotency_key": key},
    ))
    assert result.status == ControlStatus.BLOCK
    assert result.reason == "action_budget_exceeded"

@pytest.mark.parametrize(("action", "op", "arg"), [
    ("sales_pipeline@v1", "list", ""),
    ("partners@v1", "rank", ""),
    ("business_admin@v1", "notifications_show", ""),
])
def test_read_projection_with_full_telegram_metadata_is_not_charged(monkeypatch, action, op, arg):
    tenant, user = "tenant-live", "4001"
    ledger, catalog = InMemoryActionBudgetLedger(), _catalog()
    monkeypatch.setattr(safety, "build_safety_control_runtime", lambda: _runtime(ledger, catalog))
    monkeypatch.setattr(safety, "_record_safety_event", lambda **_kwargs: None)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0.0, max_actions=0), catalog)
    payload = { "tenant_id": tenant, "user_id": user, "actor_id": user, "op": op, "arg": arg, "callback_query_id": "callback-12",
        "product_id": "clientplatform", "domain": "business", "product_version": "v1",
        "idempotency_key": "telegram:0123456789abcdef",
        "world_model_meta": {"source": "canonical"},
        "goal_id": "owner-goal", "autonomy_tier": "supervised",
        "meta": {"world_model_meta": {"source": "canonical"}},
    }
    result = guard.evaluate(SafetyActionContext(action, tenant, user, payload))
    assert result.status == ControlStatus.ALLOW
    assert result.reason == "read_projection_budget_not_applicable"
    safety.record_allowed_action(action=action, payload=payload)
    assert ledger.snapshot(tenant) == (0.0, 0)

def test_financial_action_remains_blocked_when_budget_is_exhausted():
    tenant, user = "tenant-live", "4001"
    ledger = InMemoryActionBudgetLedger()
    ledger.record(tenant, estimated_cost=10.0)
    guard = ActionBudgetGuard( ledger, ActionBudget(max_cost=10.0, max_actions=1), _catalog(), )
    result = guard.evaluate(SafetyActionContext( "capture_payment@v1", tenant, user, {"tenant_id": tenant, "user_id": user, "amount": 100}, ))
    assert result.status == ControlStatus.BLOCK
    assert result.reason == "action_budget_exceeded"
    for op in ("add", "invite", "send", "approve_quote", "ai_draft"):
        attempt = guard.evaluate(SafetyActionContext(
            "partners@v1", tenant, user, {"tenant_id": tenant, "user_id": user, "op": op, "arg": ""}))
        assert attempt.status == ControlStatus.BLOCK
    for extra in ({"amount": 100}, {"campaign_id": "campaign"}, {"meta": {"autonomous": True}}):
        attempt = guard.evaluate(SafetyActionContext(
            "partners@v1", tenant, user, {"tenant_id": tenant, "user_id": user, "op": "rank", "arg": "", **extra}))
        assert attempt.status == ControlStatus.BLOCK

def test_sqlite_action_budget_retry_is_atomic_and_preserves_existing_totals(tmp_path):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / "safety.sqlite3"))
    ledger.record("tenant-live", estimated_cost=2.5)
    key = "telegram:0123456789abcdef"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map( lambda _index: ledger.record_once( "tenant-live", idempotency_key=key,
                action="bookings@v1", payload_hash="payload-v1", estimated_cost=3.5,
            ),
            range(4),
        ))

    assert sum(results) == 1
    assert ledger.recorded_action("tenant-live", key) == ("bookings@v1", "payload-v1")
    with pytest.raises(RuntimeError, match="action_budget_idempotency_conflict"):
        ledger.record_once( "tenant-live", idempotency_key=key, action="bookings@v1", payload_hash="modified-payload", estimated_cost=3.5, )
    assert ledger.snapshot("tenant-live") == (6.0, 2)
    with pytest.raises(RuntimeError, match="action_budget_idempotency_conflict"):
        ledger.record_once( "tenant-live", idempotency_key=key, action="capture_payment@v1", payload_hash="payload-v2", estimated_cost=99.0, )
    assert ledger.snapshot("tenant-live") == (6.0, 2)

@pytest.mark.parametrize("bad", [float('nan'), float('inf'), -1.0, float('-inf')])
def test_invalid_action_cost_fails_closed_without_ledger_write(tmp_path, bad):
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(tmp_path / 'budget.sqlite'))
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=100, max_actions=10), _catalog())
    result = guard.evaluate(SafetyActionContext('capture_payment@v1', 'tenant', 'user', {'tenant_id': 'tenant', 'estimated_cost': bad}))
    assert result.status == ControlStatus.BLOCK and result.reason == 'action_budget_invalid_cost'
    with pytest.raises(ValueError, match='action_budget_invalid_cost'):
        ledger.record_once('tenant', idempotency_key='key', action='capture_payment@v1', payload_hash='hash', estimated_cost=bad)
    assert ledger.recorded_action('tenant', 'key') is None
    assert ledger.snapshot('tenant') == (0.0, 0)

@pytest.mark.parametrize("event_type,variant,extra", [
    ("campaign_send", "a", {}),
    ("tariffs_viewed", "a", {"campaign_id": "campaign-1"}),
    ("tariffs_viewed", "a", {"track_payload": {"marketing_variant": "a", "broadcast": True}}),
    ("tariffs_viewed", "x" * 65, {}),
    ("tariffs_viewed", 1, {}),
])
def test_tariff_view_exemption_never_becomes_campaign_budget_bypass(event_type, variant, extra):
    from core.safety.controls.action_budget.models import is_budget_free_text_message
    payload = {"tenant_id": "tenant", "user_id": "owner", "text": "Тарифы",
               "track_event_type": event_type, "track_payload": {"marketing_variant": variant}, **extra}
    assert not is_budget_free_text_message("send_message@v1", payload)


@pytest.mark.parametrize("op", ["notifications_toggle", "notifications_level", "other"])
def test_notification_write_operations_still_consume_action_budget(op):
    from core.safety.controls.action_budget.models import is_budget_free_read_projection
    assert not is_budget_free_read_projection(
        "business_admin@v1", {"tenant_id": "tenant", "user_id": "owner", "op": op, "arg": ""})

def test_tariff_menu_analytics_is_preserved_without_consuming_autonomy_budget(monkeypatch):
    tenant, user = "tenant-live", "4001"
    ledger, catalog = InMemoryActionBudgetLedger(), _catalog()
    monkeypatch.setattr(safety, "build_safety_control_runtime", lambda: _runtime(ledger, catalog))
    monkeypatch.setattr(safety, "_record_safety_event", lambda **_kwargs: None)
    ledger.record(tenant, estimated_cost=1.0)
    payload = {"tenant_id": tenant, "user_id": user, "text": "Тарифы", "channel": "telegram",
               "track_event_type": "tariffs_viewed", "track_payload": {"marketing_variant": "a"}}
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=1.0, max_actions=1), catalog)
    verdict = guard.evaluate(SafetyActionContext("send_message@v1", tenant, user, payload))
    assert verdict.status == ControlStatus.ALLOW
    safety.record_allowed_action(action="send_message@v1", payload=payload)
    assert ledger.snapshot(tenant) == (1.0, 1)
    assert payload["track_event_type"] == "tariffs_viewed"
