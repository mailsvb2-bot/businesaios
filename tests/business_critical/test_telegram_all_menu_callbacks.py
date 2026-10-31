"""Executable Telegram menu contract: each visible button is a routed callback."""
from dataclasses import replace

import pytest

from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.ux.unified_messenger_menu import menu_items
from runtime.entrypoints.telegram_longpoll import _world_state_from_update


def _callback_state(callback):
    update = {
        "update_id": 12,
        "callback_query": {
            "id": "callback-12",
            "from": {"id": 4001},
            "message": {"message_id": 10, "date": 1700000000, "chat": {"id": 4001}},
            "data": callback,
        },
    }
    state = _world_state_from_update(update)
    return replace(state, user={**state.user, "roles": ["admin"]})


@pytest.mark.parametrize("item", menu_items(role="admin", is_admin=True), ids=lambda x: x.key)
def test_every_visible_main_menu_button_enters_its_own_route(monkeypatch, item):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = _callback_state(item.callback)
    policy = UnifiedTelegramPolicyV3()
    ctx, _ = policy._context(state)
    assert ctx.callback_data == item.callback
    assert ctx.callback_query_id == "callback-12"
    assert ctx.cmd is None or ctx.cmd == ""
    result = policy.propose(state)
    assert result.action, item.key
    if result.action == "send_message@v1":
        assert result.payload.get("text")
        assert "Я здесь. Напиши" not in result.payload["text"], item.key
        assert result.payload.get("callback_query_id") == "callback-12"


@pytest.mark.parametrize("callback", ["menu:main", "settings:state", "state:rate", "state:today", "settings:time:work", "settings:time:home"])
def test_nested_and_back_callbacks_never_fall_through(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3().propose(_callback_state(callback))
    assert result.action == "send_message@v1"
    assert "Я здесь. Напиши" not in result.payload["text"]


def _nested_buttons():
    from core.ux.keyboards.admin import kb_staff_menu
    from core.ux.keyboards.autopilot import kb_autopilot_menu, kb_growth_menu, kb_profit_sprint_lead_sources
    from core.ux.keyboards.settings import kb_settings_menu, kb_state_menu, kb_mood_rate
    keyboards = (kb_staff_menu(), kb_autopilot_menu(), kb_growth_menu(),
                 kb_profit_sprint_lead_sources(), kb_settings_menu(), kb_state_menu(), kb_mood_rate())
    return tuple(sorted({button["callback_data"] for keyboard in keyboards
                         for row in keyboard["inline_keyboard"] for button in row}))


@pytest.mark.parametrize("callback", _nested_buttons())
def test_all_nested_visible_buttons_have_concrete_route(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = _callback_state(callback)
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    assert result.action, callback
    if result.action == "send_message@v1":
        assert result.payload.get("text"), callback
        assert not result.payload["text"].startswith("Я здесь. Напиши"), callback


@pytest.mark.parametrize(("callback", "action", "operation"), [
    ("cp:section:customers", "business_ops_summary@v1", "cockpit"),
    ("cp:section:sales", "sales_pipeline@v1", "list"),
])
def test_owner_section_calls_existing_canonical_operation(monkeypatch, callback, action, operation):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(_callback_state(callback))
    assert result.action == action
    assert result.payload["op"] == operation
    assert result.payload["callback_query_id"] == "callback-12"


@pytest.mark.parametrize("callback", ["cp:section:customers", "cp:section:sales"])
def test_owner_section_rejects_unprivileged_telegram_user(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    state = replace(_callback_state(callback), user={"roles": ["operator"]})
    result = UnifiedTelegramPolicyV3().propose(state)
    assert result.action == "send_message@v1"
    assert "запрещён" in result.payload["text"]


@pytest.mark.parametrize(("callback", "action", "operation"), [
    ("cp:section:customers", "business_ops_summary@v1", "cockpit"),
    ("cp:section:sales", "sales_pipeline@v1", "list"),
])
def test_clientplatform_owner_button_reads_durable_business_state(
    monkeypatch, tmp_path, callback, action, operation,
):
    """Real Telegram update -> policy -> canonical owner -> reopened event store."""
    from types import SimpleNamespace
    from uuid import uuid4

    from runtime.handler_impl.domains.business_flow_ops import (
        handle_business_ops_summary, handle_sales_pipeline, handle_bookings,
    )
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    event_path = str(tmp_path / "clientplatform.sqlite3")
    with SqliteEventStore(event_path) as store:
        class DeliveredEffects:
            def __init__(self):
                self.deliveries = []

            def send_message(self, **kwargs):
                self.deliveries.append(kwargs)
                if kwargs.get("track_event_type"):
                    store.append_event({
                        "event_id": str(uuid4()), "tenant_id": kwargs["tenant_id"],
                        "user_id": kwargs["user_id"], "source": "telegram",
                        "event_type": kwargs["track_event_type"],
                        "timestamp_ms": 1800000000000,
                        "decision_id": kwargs["decision_id"],
                        "correlation_id": kwargs["correlation_id"],
                        "payload": kwargs["track_payload"],
                    })
                return {"ok": True, "router_evidence": {
                    "source": "telegram", "verified": True, "message_id": "sent-1",
                }}

        effects = DeliveredEffects()
        env = SimpleNamespace(decision=SimpleNamespace(
            decision_id="decision-owner", correlation_id="correlation-owner",
        ))
        created = handle_sales_pipeline({
            "tenant_id": "tenant-live", "user_id": "4001",
            "op": "add", "arg": "Test customer | Telegram",
        }, effects, env, event_store=store)
        assert created["ok"] is True
        assert store.count_events(tenant_id="tenant-live", event_type="sales_pipeline@v1") == 1
        handle_bookings({
            "tenant_id": "tenant-live", "user_id": "4001",
            "op": "add_slot", "arg": "2027-01-20 15:00 90 Business review",
        }, effects, env, event_store=store, now_ms=1800000000000)
        handle_bookings({
            "tenant_id": "tenant-live", "user_id": "6002",
            "op": "book", "arg": "1",
        }, effects, env, event_store=store, now_ms=1800000000000)
        assert store.count_events(tenant_id="tenant-live", event_type="bookings@v1") == 2

    with SqliteEventStore(event_path) as reopened:
        proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(
            _callback_state(callback)
        )
        assert (proposal.action, proposal.payload["op"]) == (action, operation)
        assert proposal.payload["callback_query_id"] == "callback-12"
        body = {"tenant_id": "tenant-live", **proposal.payload}
        handler = (handle_sales_pipeline if action == "sales_pipeline@v1"
                   else handle_business_ops_summary)
        delivered = handler(body, effects, env, event_store=reopened)
        assert delivered["ok"] is True
        assert effects.deliveries[-1]["callback_query_id"] == "callback-12"
        assert effects.deliveries[-1]["text"]
        if action == "sales_pipeline@v1":
            assert "Test customer" in effects.deliveries[-1]["text"]
        else:
            assert "6002" in effects.deliveries[-1]["text"]
        assert list(reopened.iter_events(
            tenant_id="tenant-live", event_type="sales_pipeline@v1",
        ))[0]["payload"]["name"] == "Test customer"


@pytest.mark.parametrize("callback", ["cp:section:customers", "cp:section:sales"])
def test_clientplatform_telegram_entrypoint_gateway_persists_outcome(
    monkeypatch, tmp_path, callback,
):
    """Exercise the canonical ingress/gateway/execute sequence with test adapters."""
    from types import SimpleNamespace
    from uuid import uuid4

    from core.ai import set_decision_core_singleton
    from runtime.decision_gateway import execute_runtime_decision
    from runtime.entrypoints.telegram_longpoll import _execute_update
    from runtime.execution.executor_result import ExecutionResult
    from runtime.handler_impl.domains.business_flow_ops import handle_business_ops_summary, handle_sales_pipeline
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    monkeypatch.setenv("TENANT_ID", "tenant-live")
    db = str(tmp_path / "button-outcome.sqlite3")
    with SqliteEventStore(db) as store:
        class Effects:
            def send_message(self, **kwargs):
                return {"ok": True, "router_evidence": {"source": "telegram", "verified": True, "external_refs": ["test-message-1"]}}

        class Issuer:
            def issue(self, state):
                proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
                return SimpleNamespace(decision=SimpleNamespace(
                    decision_id="decision-button", correlation_id="correlation-button",
                    action=proposal.action, payload=proposal.payload,
                ))

        class Executor:
            def execute(self, envelope):
                action = envelope.decision.action
                handler = (handle_sales_pipeline if action == "sales_pipeline@v1"
                           else handle_business_ops_summary)
                assert action in {"business_ops_summary@v1", "sales_pipeline@v1"}
                body = {"tenant_id": "tenant-live", **envelope.decision.payload}
                out = handler(body, Effects(), envelope, event_store=store)
                return ExecutionResult(
                    ok=out["ok"], output=out,
                    decision_id=envelope.decision.decision_id,
                    correlation_id=envelope.decision.correlation_id,
                )

        class Audit:
            def append(self, event):
                store.append_event({
                    "event_id": str(uuid4()), "tenant_id": "tenant-live",
                    "user_id": "4001", "source": "telegram_ingress",
                    "event_type": event["event_type"], "timestamp_ms": event["timestamp_ms"],
                    "decision_id": "decision-button", "correlation_id": "correlation-button",
                    "payload": event["payload"],
                })

        issuer = Issuer()
        set_decision_core_singleton(issuer)
        update = {
            "update_id": 12,
            "callback_query": {
                "id": "callback-12", "from": {"id": 4001},
                "message": {"message_id": 10, "date": 1700000000, "chat": {"id": 4001}},
                "data": callback,
            },
        }
        result = _execute_update(core=issuer, executor=Executor(), event_log=Audit(),
                                 update=update, transport="longpoll")
        assert result.ok is True
    with SqliteEventStore(db) as reopened:
        outcomes = list(reopened.iter_events(
            tenant_id="tenant-live", event_type="telegram_update_executed",
        ))
        assert len(outcomes) == 1
        assert outcomes[0]["payload"]["ok"] is True
        assert outcomes[0]["payload"]["update_id"] == 12
