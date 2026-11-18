"""End-to-end admin callbacks: Telegram policy -> canonical owner -> tenant event store."""
from __future__ import annotations

from dataclasses import replace
from time import time_ns
from types import SimpleNamespace

import pytest

from application.decision_runtime.flow import build_payload
from contracts.action_budget import ADMIN_ANALYTICS_ROUTES
from core.actions.catalog import build_schema_registry
from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import ActionBudget
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from runtime.entrypoints.telegram_longpoll import _world_state_from_update
from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def _callback(route):
    return { "update_id": 20, "callback_query": { "id": "callback-20", "from": {"id": 4001},
            "message": {"chat": {"id": 4001}, "message_id": 7, "date": 1700000000},
            "data": route,
        },
    }


@pytest.mark.parametrize("route, event_type, expected", [ ("admin:segments", "payment_captured", "Плательщики 30д: 1"),
    ("admin:ab", "marketing_copy_set", "Сгенерировано вариантов: 1"),
    ("admin:giftshare", "gift_sent", "Отправлено подарков: 1"),
    ("admin:funnel2", "tariffs_viewed", "Просмотр тарифов: 1"),
])
def test_verified_callback_uses_persistent_scoped_canonical_analytics( monkeypatch, tmp_path, route, event_type, expected, ):
    monkeypatch.setattr( "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live", )
    state = _world_state_from_update(_callback(route))
    monkeypatch.setenv("ADMIN_USER_IDS", "4001")
    proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    assert proposal.action == "business_ops_summary@v1"
    assert proposal.payload["op"] == "admin_analytics"
    _, payload = build_payload( state=state, out=proposal, pinned_world_model_meta={}, tenant_id="tenant-live", product_id=None, domain=None,
        product_version=None, actor_id="4001",
    )
    build_schema_registry().validate(proposal.action, payload)

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=1000)
    before = ledger.snapshot("tenant-live")
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0, max_actions=0))
    result = guard.evaluate(SafetyActionContext(proposal.action, "tenant-live", "4001", payload))
    assert result.status == ControlStatus.ALLOW
    assert result.reason == "read_projection_budget_not_applicable"
    assert ledger.snapshot("tenant-live") == before

    class Effects:
        deliveries = []

        def send_message(self, **kwargs):
            self.deliveries.append(kwargs)
            return {"ok": True, "router_evidence": { "source": "telegram", "verified": True, "message_id": "sent-1", }}

    now = time_ns() // 1_000_000
    path = str(tmp_path / "business_events.sqlite3")
    with SqliteEventStore(path) as store:
        for tenant in ("tenant-live", "tenant-foreign"):
            store.append_event({ "event_id": f"ev-{tenant}", "tenant_id": tenant, "user_id": "5002", "source": "test",
                "event_type": event_type, "timestamp_ms": now - 1000,
                "decision_id": "decision-1", "correlation_id": "correlation-1",
                "payload": {},
            })

    with SqliteEventStore(path) as reopened:
        effects = Effects()
        env = SimpleNamespace(decision=SimpleNamespace( decision_id="decision-2", correlation_id="correlation-2", ))
        out = handle_business_ops_summary( dict(payload), effects, env, event_store=reopened, now_ms=now, )
        assert out["ok"] is True
        assert expected in effects.deliveries[-1]["text"]
        assert effects.deliveries[-1]["callback_query_id"] == "callback-20"
        assert effects.deliveries[-1]["tenant_id"] == "tenant-live"
        assert effects.deliveries[-1].get("track_event_type") is None


def test_unknown_analytics_route_never_queries_arbitrary_data(tmp_path):
    from runtime.handler_impl.domains.admin_ops import render_admin_analytics

    with SqliteEventStore(str(tmp_path / "events.sqlite3")) as store:
        with pytest.raises(ValueError, match="unsupported_admin_analytics_route"):
            render_admin_analytics( event_store=store, tenant_id="tenant-live", route="admin:root:export", )


def test_unprivileged_user_cannot_request_any_admin_analytics(monkeypatch):
    monkeypatch.setattr( "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live", )
    for route in ADMIN_ANALYTICS_ROUTES:
        state = _world_state_from_update(_callback(route))
        state = replace(state, user={**state.user, "roles": []})
        proposal = UnifiedTelegramPolicyV3().propose(state)
        assert proposal.action == "send_message@v1"
        assert "Доступ запрещён" in proposal.payload["text"]


@pytest.mark.parametrize("override", [ {"arg": "admin:root:export"}, {"estimated_cost": 1.0}, {"op": "delete"}, {"recipient_count": 200},
    {"meta": {"campaign_id": "untrusted-campaign"}},
])
def test_admin_analytics_exemption_is_read_only_and_fail_closed(override):
    ledger = InMemoryActionBudgetLedger()
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0, max_actions=0))
    payload = { "tenant_id": "tenant-live", "user_id": "4001", "op": "admin_analytics", "arg": "admin:segments", **override, }
    decision = guard.evaluate( SafetyActionContext("business_ops_summary@v1", "tenant-live", "4001", payload) )
    assert decision.status == ControlStatus.BLOCK
    assert decision.reason == "action_budget_exceeded"
