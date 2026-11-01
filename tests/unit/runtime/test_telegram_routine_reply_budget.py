"""Regression: inbound Telegram replies survive exhausted autonomous budgets."""
from __future__ import annotations

from types import SimpleNamespace

from application.decision_runtime.flow import build_payload
from contracts.action_impact_contract import ActionExecutionContext
from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.policies.telegram.helpers import ProposedAction
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import ActionBudget, is_routine_reply
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.operational_budget_accountant import OperationalBudgetAccountant
from core.safety.operational.action_registry import build_default_operational_action_registry
from runtime import safety_controls

REPLY_PROOF = {"channel": "telegram", "update_id": 462236768}


def _payload(**kw):
    return {"tenant_id": "tenant-live", "user_id": "user-1",
            "meta": {"inbound_user_reply": REPLY_PROOF}, **kw}


def _ctx(action="send_message@v1", **kw):
    return SafetyActionContext(action=action, tenant_id="tenant-live",
                               user_id="user-1", payload=_payload(**kw))


def test_verified_reply_does_not_spend_cumulative_business_budget():
    ledger = InMemoryActionBudgetLedger()
    for _ in range(3):
        ledger.record("tenant-live", estimated_cost=2.0)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5.0, max_actions=2))
    reply = guard.evaluate(_ctx())
    assert reply.status == ControlStatus.ALLOW
    assert reply.reason == "user_reply_budget_not_applicable"
    assert guard.evaluate(_ctx("capture_payment")).reason == "action_budget_exceeded"
    assert guard.evaluate(_ctx(estimated_cost=1)).reason == "action_budget_exceeded"
    assert guard.evaluate(_ctx(meta={})).reason == "action_budget_exceeded"
    assert ledger.snapshot("tenant-live") == (6.0, 3)
    assert not is_routine_reply("send_marketing_offer", _payload())
    assert not is_routine_reply("send_message@v1", _payload(estimated_cost=3))


def test_safety_accounting_excludes_only_verified_user_reply(monkeypatch):
    ledger = InMemoryActionBudgetLedger()
    profile = SimpleNamespace(action_budget_ledger=ledger,
                              action_catalog=SimpleNamespace(resolve=lambda action: None))
    monkeypatch.setattr(safety_controls, "build_safety_control_runtime",
                        lambda: SimpleNamespace(profile=profile))
    monkeypatch.setattr(safety_controls, "_record_safety_event", lambda **kw: True)
    safety_controls.record_allowed_action(action="send_message@v1", payload=_payload())
    assert ledger.snapshot("tenant-live") == (0.0, 0)
    safety_controls.record_allowed_action(action="send_message@v1", payload=_payload(meta={}))
    safety_controls.record_allowed_action(action="send_message@v1", payload=_payload(estimated_cost=1))
    assert ledger.snapshot("tenant-live") == (1.0, 2)


def test_start_proposal_gets_trusted_reply_provenance_and_existing_user_reply_policy():
    state = SimpleNamespace(
        user_id="user-1", meta={"source": "messaging"}, economy={},
        session={"source": "messaging", "channel": "telegram", "command": "/start",
                 "text": "/start", "messaging_update_id": 462236768},
        user={"id": "user-1", "messaging_channel": "telegram"},
        product={"name": "ClientPlatform"},
    )
    proposed = UnifiedTelegramPolicyV3().propose(state)
    assert proposed.action == "send_message@v1"
    tagged, payload = build_payload(
        state=state, out=proposed, pinned_world_model_meta={},
        tenant_id="tenant-live", product_id=None,
        domain=None, product_version=None, actor_id="user-1",
    )
    assert payload["meta"]["inbound_user_reply"] == REPLY_PROOF
    assert is_routine_reply(proposed.action, payload)
    classifier = ActionClassifier(build_default_operational_action_registry())
    execution = ActionExecutionContext(tenant_id="tenant-live", user_id="user-1",
                                       action_name=proposed.action, payload=payload,
                                       metadata={}, execution_id="decision-1")
    assert classifier.classify(execution).spec.dimensions["interaction"] == "user_reply"
    accountant = OperationalBudgetAccountant()
    builder = ActionImpactBuilder(classifier, ActionCostModel())
    reply_envelope = accountant.to_envelope(execution, builder.build(execution))
    assert reply_envelope.actions_count == 0 and reply_envelope.outbound_count == 0

    # A normal autonomous outbound decision cannot spoof inbound provenance.
    untrusted = SimpleNamespace(user_id="user-1", meta={}, product={},
                                session={"source": "headless", "channel": "telegram"})
    _, forged = build_payload(
        state=untrusted, out=ProposedAction("send_message@v1", {
            "user_id": "user-1", "text": "marketing send",
            "meta": {"inbound_user_reply": REPLY_PROOF}}),
        pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert not is_routine_reply("send_message@v1", forged)
    outbound = ActionExecutionContext(tenant_id="tenant-live", user_id="user-1",
                                      action_name="send_message@v1", payload=forged,
                                      metadata={}, execution_id="decision-2")
    assert classifier.classify(outbound).spec.dimensions.get("interaction") != "user_reply"
    normal_envelope = accountant.to_envelope(outbound, builder.build(outbound))
    assert normal_envelope.actions_count == 1 and normal_envelope.outbound_count == 1


def test_registered_channels_respect_user_reply_budget_without_exempting_outbound():
    from contracts.messaging_channels import ALL_CHANNELS
    assert {"telegram", "vk", "max", "whatsapp", "web_chat"}.issubset(set(ALL_CHANNELS))
    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=6.0)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5.0, max_actions=0))
    for channel in ALL_CHANNELS:
        state = SimpleNamespace(
            user_id="user-1", tenant_id="tenant-live", meta={}, product={},
            session={"source": "messaging", "channel": channel,
                     "messaging_update_id": 19 if channel == "telegram" else None,
                     "transport_message_id": "event-19" if channel != "telegram" else ""},
        )
        _, payload = build_payload(
            state=state,
            out=ProposedAction("send_message@v1", {"user_id": "user-1", "text": "reply"}),
            pinned_world_model_meta={}, tenant_id="tenant-live", product_id=None,
            domain=None, product_version=None, actor_id="user-1",
        )
        assert payload["meta"]["inbound_user_reply"]["channel"] == channel
        assert is_routine_reply("send_message@v1", payload)
        assert guard.evaluate(SafetyActionContext(action="send_message@v1",
            tenant_id="tenant-live", user_id="user-1", payload=payload)).status == ControlStatus.ALLOW
        for malicious in (
            {"action": "send_marketing_offer@v1", "payload": payload},
            {"action": "send_message@v1", "payload": {**payload, "estimated_cost": 1.0}},
            {"action": "send_message@v1", "payload": {**payload, "meta": {}}},
        ):
            assert guard.evaluate(SafetyActionContext(
                action=malicious["action"], tenant_id="tenant-live",
                user_id="user-1", payload=malicious["payload"],
            )).status == ControlStatus.BLOCK
    assert ledger.snapshot("tenant-live") == (6.0, 1)


def test_untrusted_sources_and_unknown_channels_cannot_bypass_autonomous_budget():
    for source, channel, update_id in (
        ("headless", "vk", 19),
        ("messaging", "unknown-marketplace", 19),
        ("customer_bot", "max", None),
    ):
        state = SimpleNamespace(user_id="user-1", meta={}, product={},
            session={"source": source, "channel": channel, "messaging_update_id": update_id})
        _, payload = build_payload(
            state=state, out=ProposedAction("send_message@v1", {
                "user_id": "user-1", "text": "autonomous",
                "meta": {"inbound_user_reply": {"channel": "telegram", "update_id": 1}},
            }), pinned_world_model_meta={}, tenant_id="tenant-live",
            product_id=None, domain=None, product_version=None, actor_id="user-1",
        )
        assert not is_routine_reply("send_message@v1", payload)

def test_cross_tenant_reply_claim_does_not_exempt_autonomous_budget():
    payload = {"tenant_id": "tenant-live", "user_id": "user-1",
               "meta": {"inbound_user_reply": {
                   "channel": "vk", "update_id": "event-19", "tenant_id": "another"}}}
    assert not is_routine_reply("send_message@v1", payload)
    assert not is_routine_reply("send_message@v1", {**payload, "recipient_count": 2})
    ledger = InMemoryActionBudgetLedger()
    ledger.record("tenant-live", estimated_cost=0)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5, max_actions=0))
    assert guard.evaluate(SafetyActionContext(
        action="send_message@v1", tenant_id="tenant-live",
        user_id="user-1", payload=payload)).status == ControlStatus.BLOCK

def test_provider_inbound_identity_reaches_canonical_decision_budget():
    from runtime.messaging.inbound_message import InboundMessage
    from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state

    for channel in ("vk", "max", "whatsapp"):
        state = map_inbound_to_world_state(InboundMessage(
            tenant_id="tenant-live", user_id="user-1", channel=channel,
            text="hi", transport_message_id="provider-event-42",
        ))
        assert state.session["transport_message_id"] == "provider-event-42"
        _, payload = build_payload(
            state=state,
            out=ProposedAction("send_message@v1", {"user_id": "user-1", "text": "reply"}),
            pinned_world_model_meta={}, tenant_id="tenant-live",
            product_id=None, domain=None, product_version=None, actor_id="user-1",
        )
        assert is_routine_reply("send_message@v1", payload)
        assert payload["meta"]["inbound_user_reply"]["tenant_id"] == "tenant-live"
        assert payload["meta"]["inbound_user_reply"]["update_id"] == "provider-event-42"

    missing_id = map_inbound_to_world_state(InboundMessage(
        tenant_id="tenant-live", user_id="user-1", channel="vk", text="hi",
    ))
    _, unsigned = build_payload(
        state=missing_id,
        out=ProposedAction("send_message@v1", {"user_id": "user-1", "text": "reply"}),
        pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert not is_routine_reply("send_message@v1", unsigned)
