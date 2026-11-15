"""Executable Telegram menu contract: callback buttons route; HTTPS links are checked separately."""
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


@pytest.mark.parametrize("item", (x for x in menu_items(role="admin", is_admin=True) if x.key != "connect"), ids=lambda x: x.key)
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
        assert "Этот раздел пока недоступен" not in result.payload["text"], item.key
        assert result.payload.get("callback_query_id") == "callback-12"


@pytest.mark.parametrize("callback", ["ceo:plan", "ceo:run", "admin:evolution:regen_copy:nudge", "demo_kind_work", "weather:city"])
def test_ceo_and_retired_callbacks_have_live_routes(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id", lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(_callback_state(callback))
    assert result.action
    assert "Этот раздел пока недоступен" not in str((result.payload or {}).get("text") or "")


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
        assert "Этот раздел пока недоступен" not in result.payload["text"], callback


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


@pytest.mark.parametrize(("callback", "action", "operation", "argument"), [
    ("cpm:growth", "business_ops_summary@v1", "cockpit", "cpm:growth"),
    ("cpm:growth-an:7", "business_ops_summary@v1", "cockpit", "cpm:growth-an:7"),
    ("cpm:money", "business_ops_summary@v1", "cockpit", "cpm:money"),
    ("cp:section:ad-channels", "bookings@v1", "ad_channels", ""),
])
def test_owner_main_business_sections_use_canonical_executor_contract(
    monkeypatch, callback, action, operation, argument,
):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
                        lambda: "tenant-live")
    result = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(
        _callback_state(callback)
    )
    assert result.action == action
    assert result.payload["op"] == operation
    assert result.payload["arg"] == argument
    assert result.payload["callback_query_id"] == "callback-12"


def test_growth_and_finance_surfaces_expose_real_existing_actions():
    from application.business_flows.cockpit import Parsed, Snapshot, render

    growth, growth_rows = render(Parsed("growth"), Snapshot(), is_owner=True)
    assert "Рост" in growth
    growth_targets = {callback for row in growth_rows for _, callback in row}
    assert {"cp:section:ad-channels", "growth:menu", "cpm:growth-an:7"} <= growth_targets

    finance, finance_rows = render(Parsed("money"), Snapshot(), is_owner=True)
    assert finance
    finance_targets = {callback for row in finance_rows for _, callback in row}
    assert {"cpm:payments:0", "sub:menu"} <= finance_targets


@pytest.mark.parametrize("callback", [
    "cpm:growth", "cpm:growth-an:7", "cpm:money", "cp:section:ad-channels",
])
def test_owner_business_sections_reject_unprivileged_role(monkeypatch, callback):
    monkeypatch.setattr("runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
                        lambda: "tenant-live")
    state = replace(_callback_state(callback), user={"roles": ["operator"]})
    proposal = UnifiedTelegramPolicyV3().propose(state)
    assert proposal.action != "business_ops_summary@v1"
    assert proposal.action != "bookings@v1"


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
    from time import time_ns
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
                        "timestamp_ms": time_ns() // 1_000_000,
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


@pytest.mark.parametrize(("action", "op", "arg"), [
    ("business_ops_summary@v1", "cockpit", "cpm:growth-an:7"),
    ("business_ops_summary@v1", "cockpit", "cpm:money"),
    ("business_ops_summary@v1", "cockpit", "cpm:growth"),
    ("sales_pipeline@v1", "list", ""),
    ("bookings@v1", "ad_channels", ""),
])
def test_readonly_business_buttons_work_after_action_budget_reaches_limit(action, op, arg):
    from core.safety.controls.action_budget.guard import ActionBudgetGuard
    from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
    from core.safety.controls.action_budget.models import ActionBudget
    from core.safety.controls.action_context import SafetyActionContext
    from core.safety.controls.control_result import ControlStatus

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5000)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5000, max_actions=1))
    payload = {"tenant_id": "tenant-live", "user_id": "4001", "op": op, "arg": arg}
    result = guard.evaluate(SafetyActionContext(action, "tenant-live", "4001", payload))
    assert result.status == ControlStatus.ALLOW
    assert result.reason == "read_projection_budget_not_applicable"
    enriched = {**payload, "goal_id": "owner-goal", "autonomy_tier": "supervised",
                "meta": {"world_model_meta": {"source": "canonical"}}}
    assert guard.evaluate(SafetyActionContext(action, "tenant-live", "4001", enriched)).status == ControlStatus.ALLOW


@pytest.mark.parametrize(("action", "op", "arg", "extra"), [
    ("business_ops_summary@v1", "cockpit", "cpm:pay-rf:payment123", {}),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"amount": 1}),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"estimated_cost": 1}),
    ("business_ops_summary@v1", "cockpit", "cpm:money", {"meta": {"requested_budget": 1}}),
    ("sales_pipeline@v1", "add", "", {}),
    ("bookings@v1", "book", "", {}),
    ("bookings@v1", "ad_channels", "", {"campaign_id": "forged"}),
])
def test_readonly_accounting_never_exempts_writes_or_financial_markers(action, op, arg, extra):
    from core.safety.controls.action_budget.guard import ActionBudgetGuard
    from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
    from core.safety.controls.action_budget.models import ActionBudget
    from core.safety.controls.action_context import SafetyActionContext
    from core.safety.controls.control_result import ControlStatus

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5000)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5000, max_actions=1))
    payload = {"tenant_id": "tenant-live", "user_id": "4001", "op": op, "arg": arg, **extra}
    result = guard.evaluate(SafetyActionContext(action, "tenant-live", "4001", payload))
    assert result.status == ControlStatus.BLOCK
    assert result.reason == "action_budget_exceeded"


@pytest.mark.parametrize("callback", [
    "cp:section:customers",
    "cp:section:sales",
    "cpm:growth",
    "cpm:growth-an:7",
    "cpm:money",
    "cp:section:ad-channels",
])
def test_owner_read_callbacks_survive_real_payload_build_and_exhausted_budget(
    monkeypatch, callback,
):
    from application.decision_runtime.flow import build_payload
    from core.actions.catalog import build_schema_registry
    from core.safety.controls.action_budget.guard import ActionBudgetGuard
    from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
    from core.safety.controls.action_budget.models import ActionBudget
    from core.safety.controls.action_context import SafetyActionContext
    from core.safety.controls.control_result import ControlStatus

    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    state = _callback_state(callback)
    state = replace(
        state,
        meta={**state.meta, "goal_id": "owner-goal", "autonomy_tier": "supervised"},
    )
    proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    _, payload = build_payload(
        state=state,
        out=proposal,
        pinned_world_model_meta={"source": "telegram-callback-regression"},
        tenant_id="tenant-live",
        product_id=None,
        domain=None,
        product_version=None,
        actor_id="4001",
    )

    # The same strict registry and budget guard used by DecisionCore must
    # accept the real policy payload without widening any action contract.
    build_schema_registry().validate(proposal.action, payload)
    assert payload["goal_id"] == "owner-goal"
    assert payload["autonomy_tier"] == "supervised"
    assert payload["meta"]["canonical_goal_id"] == "owner-goal"
    assert payload["meta"]["world_model_meta"]["source"] == "telegram-callback-regression"

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5000)
    before = ledger.snapshot("tenant-live")
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5000, max_actions=1))
    decision = guard.evaluate(
        SafetyActionContext(
            proposal.action, "tenant-live", "4001", payload,
        )
    )
    assert decision.status == ControlStatus.ALLOW, (
        f"{callback}: action={proposal.action}, keys={sorted(payload)}, "
        f"reason={decision.reason}"
    )
    assert decision.reason == "read_projection_budget_not_applicable"
    assert ledger.snapshot("tenant-live") == before


def test_telegram_main_menu_reply_keeps_zero_cost_callback_response_budget_exemption(
    monkeypatch,
):
    from application.decision_runtime.flow import build_payload
    from core.safety.controls.action_budget.guard import ActionBudgetGuard
    from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
    from core.safety.controls.action_budget.models import (
        ActionBudget,
        is_routine_reply,
        verified_inbound_reply_scope,
    )
    from core.safety.controls.action_context import SafetyActionContext
    from core.safety.controls.control_result import ControlStatus

    monkeypatch.setenv(
        "BUSINESAIOS_SAFETY_SIGNING_SECRET",
        "test-only-strong-inbound-signing-secret",
    )
    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    state = _callback_state("menu:main")
    state = replace(
        state,
        meta={**state.meta, "goal_id": "owner-goal", "autonomy_tier": "supervised"},
    )
    proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(state)
    assert proposal.action == "send_message@v1"
    with verified_inbound_reply_scope(
        tenant_id="tenant-live",
        channel="telegram",
        user_id=str(state.user_id),
        update_id=state.session["messaging_update_id"],
        chat_id=str(state.session.get("messaging_chat_id") or ""),
    ):
        _, payload = build_payload(
            state=state,
            out=proposal,
            pinned_world_model_meta={},
            tenant_id="tenant-live",
            product_id=None,
            domain=None,
            product_version=None,
            actor_id="4001",
        )

    assert payload["callback_query_id"] == "callback-12"
    assert is_routine_reply("send_message@v1", payload)
    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5000)
    before = ledger.snapshot("tenant-live")
    decision = ActionBudgetGuard(
        ledger, ActionBudget(max_cost=5000, max_actions=1),
    ).evaluate(SafetyActionContext("send_message@v1", "tenant-live", "4001", payload))
    assert decision.status == ControlStatus.ALLOW
    assert decision.reason == "text_delivery_budget_not_applicable"
    assert ledger.snapshot("tenant-live") == before


@pytest.mark.parametrize(("callback", "action", "operation", "argument"), [
    ("cp:section:sales", "sales_pipeline@v1", "list", ""),
    ("cp:section:ad-channels", "bookings@v1", "ad_channels", ""),
])
def test_owner_read_projection_callback_payload_matches_closed_decision_schema(
    monkeypatch, callback, action, operation, argument,
):
    from core.actions.catalog import build_schema_registry

    monkeypatch.setattr(
        "runtime.entrypoints.telegram_longpoll._configured_telegram_tenant_id",
        lambda: "tenant-live",
    )
    proposal = UnifiedTelegramPolicyV3(admin_user_ids=("4001",)).propose(
        _callback_state(callback)
    )
    assert proposal.action == action
    assert proposal.payload["op"] == operation
    assert proposal.payload["arg"] == argument
    assert proposal.payload["callback_query_id"] == "callback-12"

    # These are transport/DecisionCore metadata, not permission to widen the
    # action contract. The exact action remains closed to arbitrary extra keys.
    payload = {
        "tenant_id": "tenant-live",
        **proposal.payload,
        "goal_id": "owner-goal",
        "autonomy_tier": "supervised",
        "meta": {"world_model_meta": {"source": "canonical"}},
    }
    schemas = build_schema_registry()
    schemas.validate(action, payload)
    with pytest.raises(ValueError, match="UNKNOWN_PAYLOAD_KEYS"):
        schemas.validate(action, {**payload, "untrusted_extra": "reject"})


@pytest.mark.parametrize(("action", "operation", "argument"), [
    ("business_ops_summary@v1", "cockpit", "cpm:menu"),
    ("sales_pipeline@v1", "list", ""),
    ("bookings@v1", "ad_channels", ""),
])
def test_read_projection_accounting_does_not_double_charge_with_telegram_metadata(
    monkeypatch, action, operation, argument,
):
    from types import SimpleNamespace

    from core.safety.controls.action_budget.guard import ActionBudgetGuard
    from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
    from core.safety.controls.action_budget.models import ActionBudget
    from core.safety.controls.action_context import SafetyActionContext
    from core.safety.controls.control_result import ControlStatus
    import runtime.safety_controls as safety

    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=5000)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5000, max_actions=1))
    payload = {
        "tenant_id": "tenant-live",
        "user_id": "4001",
        "op": operation,
        "arg": argument,
        "callback_query_id": "callback-12",
        "goal_id": "owner-goal",
        "autonomy_tier": "supervised",
        "meta": {"world_model_meta": {"source": "canonical"}},
    }
    before = ledger.snapshot("tenant-live")
    decision = guard.evaluate(
        SafetyActionContext(action, "tenant-live", "4001", payload)
    )
    assert decision.status == ControlStatus.ALLOW
    assert decision.reason == "read_projection_budget_not_applicable"
    assert ledger.snapshot("tenant-live") == before

    events = []
    profile = SimpleNamespace(
        action_catalog=SimpleNamespace(
            resolve=lambda name: SimpleNamespace(default_estimated_cost=0)
        ),
        action_budget_ledger=ledger,
    )
    monkeypatch.setattr(
        safety, "build_safety_control_runtime",
        lambda: SimpleNamespace(profile=profile),
    )
    monkeypatch.setattr(
        safety, "_record_safety_event",
        lambda **kwargs: events.append(kwargs),
    )
    safety.record_allowed_action(action=action, payload=payload)

    assert ledger.snapshot("tenant-live") == before
    assert events[-1]["reason"] == "read_projection_not_charged"
