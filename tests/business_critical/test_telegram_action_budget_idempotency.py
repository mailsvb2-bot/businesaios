from concurrent.futures import ThreadPoolExecutor
import pytest
from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger

from types import SimpleNamespace

import runtime.safety_controls as safety
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import ( ActionBudget, issue_verified_update_idempotency_key, verified_inbound_reply_scope, )
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus


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


def test_read_projection_with_full_telegram_metadata_is_not_charged(monkeypatch):
    tenant, user = "tenant-live", "4001"
    ledger, catalog = InMemoryActionBudgetLedger(), _catalog()
    monkeypatch.setattr(safety, "build_safety_control_runtime", lambda: _runtime(ledger, catalog))
    monkeypatch.setattr(safety, "_record_safety_event", lambda **_kwargs: None)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0.0, max_actions=0), catalog)
    payload = { "tenant_id": tenant, "user_id": user, "actor_id": user, "op": "list", "arg": "", "callback_query_id": "callback-12",
        "product_id": "clientplatform", "domain": "business", "product_version": "v1",
        "idempotency_key": "telegram:0123456789abcdef",
        "world_model_meta": {"source": "canonical"},
        "goal_id": "owner-goal", "autonomy_tier": "supervised",
        "meta": {"world_model_meta": {"source": "canonical"}},
    }
    result = guard.evaluate(SafetyActionContext("sales_pipeline@v1", tenant, user, payload))
    assert result.status == ControlStatus.ALLOW
    assert result.reason == "read_projection_budget_not_applicable"
    safety.record_allowed_action(action="sales_pipeline@v1", payload=payload)
    assert ledger.snapshot(tenant) == (0.0, 0)


def test_financial_action_remains_blocked_when_budget_is_exhausted():
    tenant, user = "tenant-live", "4001"
    ledger = InMemoryActionBudgetLedger()
    ledger.record(tenant, estimated_cost=10.0)
    guard = ActionBudgetGuard( ledger, ActionBudget(max_cost=10.0, max_actions=1), _catalog(), )
    result = guard.evaluate(SafetyActionContext( "capture_payment@v1", tenant, user, {"tenant_id": tenant, "user_id": user, "amount": 100}, ))
    assert result.status == ControlStatus.BLOCK
    assert result.reason == "action_budget_exceeded"




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
