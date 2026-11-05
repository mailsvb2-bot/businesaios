"""Regression: inbound Telegram replies survive exhausted autonomous budgets."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from application.decision_runtime.flow import build_payload
from contracts.action_impact_contract import ActionExecutionContext
from core.policies.telegram.helpers import ProposedAction
from core.policies.telegram.unified_policy import UnifiedTelegramPolicyV3
from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import (
    ActionBudget,
    is_routine_reply,
    issue_verified_reply,
    verified_inbound_reply_scope,
)
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from core.safety.operational.action_classifier import ActionClassifier
from core.safety.operational.action_cost_model import ActionCostModel
from core.safety.operational.action_impact_builder import ActionImpactBuilder
from core.safety.operational.action_registry import build_default_operational_action_registry
from core.safety.operational.operational_budget_accountant import OperationalBudgetAccountant
from runtime import safety_controls

REPLY_PROOF = {"channel": "telegram", "update_id": 462236768, "tenant_id": "tenant-live", "user_id": "user-1"}


@pytest.fixture(autouse=True)
def _verified_test_key(monkeypatch):
    monkeypatch.setenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", "test-only-strong-inbound-signing-secret")
    with verified_inbound_reply_scope(
        tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
    ):
        REPLY_PROOF.clear()
        REPLY_PROOF.update(issue_verified_reply(
            tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
        ))


def _trusted_build_payload(*, state, out, **kw):
    session = state.get("session", {}) if isinstance(state, dict) else state.session
    channel = str(session.get("channel") or "")
    event_id = session.get("messaging_update_id") if channel == "telegram" else session.get("transport_message_id")
    tenant_id = state.get("tenant_id") if isinstance(state, dict) else state.tenant_id
    user_id = state.get("user_id") if isinstance(state, dict) else state.user_id
    with verified_inbound_reply_scope(
        tenant_id=str(tenant_id), channel=channel, user_id=str(user_id),
        update_id=event_id, chat_id=str(session.get("chat_id") or session.get("messaging_chat_id") or ""),
    ):
        return build_payload(state=state, out=out, **kw)


def _payload(**kw):
    return {"tenant_id": "tenant-live", "user_id": "user-1", "channel": "telegram",
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
        tenant_id="tenant-live", user_id="user-1", meta={"source": "messaging"}, economy={},
        session={"source": "messaging", "channel": "telegram", "command": "/start",
                 "text": "/start", "messaging_update_id": 462236768},
        user={"id": "user-1", "messaging_channel": "telegram"},
        product={"name": "ClientPlatform"},
    )
    proposed = UnifiedTelegramPolicyV3().propose(state)
    assert proposed.action == "send_message@v1"
    tagged, payload = _trusted_build_payload(
        state=state, out=proposed, pinned_world_model_meta={},
        tenant_id="tenant-live", product_id=None,
        domain=None, product_version=None, actor_id="user-1",
    )
    assert all(payload["meta"]["inbound_user_reply"][key] == value
               for key, value in REPLY_PROOF.items() if key not in {"issued_at", "signature", "content_sha256"})
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
        _, payload = _trusted_build_payload(
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
        _, payload = _trusted_build_payload(
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


def test_inbound_reply_must_match_outbound_channel_and_chat():
    state = SimpleNamespace(
        tenant_id="tenant-live", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "vk",
                 "transport_message_id": "verified-event-9", "chat_id": "chat-1"},
    )
    for override in ({"channel": "max"}, {"chat_id": "chat-2"},
                     {"channel": "vk", "chat_id": "chat-2"}):
        with pytest.raises(RuntimeError, match="DECISION_(CHANNEL|CHAT_ID)_MISMATCH"):
            _trusted_build_payload(
                state=state,
                out=ProposedAction("send_message@v1", {
                    "user_id": "user-1", "text": "not a reply", **override,
                }),
                pinned_world_model_meta={}, tenant_id="tenant-live",
                product_id=None, domain=None, product_version=None, actor_id="user-1",
            )

    _, reply = _trusted_build_payload(
        state=state, out=ProposedAction("send_message@v1", {
            "user_id": "user-1", "text": "reply", "channel": "vk", "chat_id": "chat-1",
        }), pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert is_routine_reply("send_message@v1", reply)
    _, bound = _trusted_build_payload(
        state=state, out=ProposedAction("send_message@v1", {
            "user_id": "user-1", "text": "reply",
        }), pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert bound["channel"] == "vk" and bound["chat_id"] == "chat-1"
    assert is_routine_reply("send_message@v1", bound)


def test_inbound_mapping_preserves_chat_coordinate():
    from runtime.messaging.inbound_message import InboundMessage
    from runtime.messaging.inbound_to_world_state import map_inbound_to_world_state

    state = map_inbound_to_world_state(InboundMessage(
        tenant_id="tenant-live", user_id="user-1", channel="max",
        transport_message_id="event-1", metadata={"chat_id": "room-42"},
    ))
    assert state.session["chat_id"] == "room-42"


def test_long_raw_event_id_cannot_spoof_a_bounded_reply():
    event_id = " " * 256 + "x"
    payload = {"tenant_id": "tenant-live", "user_id": "user-1",
               "meta": {"inbound_user_reply": {
                   "channel": "vk", "update_id": event_id, "tenant_id": "tenant-live"}}}
    assert not is_routine_reply("send_message@v1", payload)
    state = SimpleNamespace(
        tenant_id="tenant-live", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "vk",
                 "transport_message_id": event_id},
    )
    _, outbound = build_payload(
        state=state, out=ProposedAction("send_message@v1", {
            "user_id": "user-1", "text": "not a verified reply",
        }), pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert not is_routine_reply("send_message@v1", outbound)


def test_telegram_inbound_tenant_mismatch_cannot_bypass_budget():
    state = SimpleNamespace(
        tenant_id="tenant-other", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "telegram", "messaging_update_id": 123},
    )
    _, payload = build_payload(
        state=state, out=ProposedAction("send_message@v1", {
            "user_id": "user-1", "text": "cross-tenant reply",
        }), pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert not is_routine_reply("send_message@v1", payload)
    # A matching channel/update ID is insufficient without tenant binding.
    forged = {"tenant_id": "tenant-live", "user_id": "user-1",
              "meta": {"inbound_user_reply": {
                  "channel": "telegram", "update_id": 123, "tenant_id": "tenant-other",
              }}}
    assert not is_routine_reply("send_message@v1", forged)


def test_null_mapping_identity_cannot_be_signed_as_literal_none():
    for missing in ("tenant_id", "user_id"):
        state = {
            "tenant_id": "tenant-live", "user_id": "user-1",
            "session": {"source": "messaging", "channel": "vk",
                        "transport_message_id": "event-42"},
        }
        state[missing] = None
        _, payload = build_payload(
            state=state,
            out=ProposedAction("send_message@v1", {
                "user_id": "None" if missing == "user_id" else "user-1",
                "text": "not a verified reply",
            }),
            pinned_world_model_meta={}, tenant_id="None" if missing == "tenant_id" else "tenant-live",
            product_id=None, domain=None, product_version=None, actor_id="user-1",
        )
        assert not is_routine_reply("send_message@v1", payload)


def test_signed_reply_proof_binds_exact_recipient_channel_and_chat():
    state = SimpleNamespace(tenant_id="tenant-live", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "vk", "transport_message_id": "provider-event-42", "chat_id": "room-42"})
    _, payload = _trusted_build_payload(
        state=state, out=ProposedAction("send_message@v1",
            {"user_id": "user-1", "text": "reply", "channel": "vk", "chat_id": "room-42"}),
        pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1")
    proof = payload["meta"]["inbound_user_reply"]
    assert is_routine_reply("send_message@v1", payload)
    for key, bad in (("user_id", "another-recipient"), ("channel", "max"),
                     ("chat_id", "another-room"), ("recipient_count", True), ("recipient_count", "1")):
        assert not is_routine_reply("send_message@v1", {**payload, key: bad})
    for key, bad in (("user_id", "another-recipient"), ("chat_id", "another-room")):
        assert not is_routine_reply("send_message@v1", {**payload, "meta": {"inbound_user_reply": {**proof, key: bad}}})
    assert not is_routine_reply("send_message@v1", {**payload, "meta": {"inbound_user_reply": {k: v for k, v in proof.items() if k != "user_id"}}})



@pytest.mark.parametrize("channel,event_id", [
    ("telegram", 101), ("vk", "vk-event-101"), ("max", "max-event-101"),
])
def test_signed_reply_without_inbound_chat_cannot_target_unrelated_chat(channel, event_id):
    """An absent inbound chat coordinate is not permission to select a new destination."""
    with verified_inbound_reply_scope(
        tenant_id="tenant-live", channel=channel, user_id="user-1", update_id=event_id,
    ):
        proof = issue_verified_reply(
            tenant_id="tenant-live", channel=channel, user_id="user-1",
            update_id=event_id, text="reply",
        )
    assert proof is not None and proof["chat_id"] == ""
    payload = {
        "tenant_id": "tenant-live", "user_id": "user-1", "channel": channel,
        "text": "reply", "meta": {"inbound_user_reply": proof},
    }
    assert is_routine_reply("send_message@v1", payload)
    assert is_routine_reply("send_message@v1", {**payload, "chat_id": "user-1"})
    ledger = InMemoryActionBudgetLedger()
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0, max_actions=0))
    for other_chat in ("unrelated-room", "  ", "0"):
        outbound = {**payload, "chat_id": other_chat}
        assert not is_routine_reply("send_message@v1", outbound)
        assert guard.evaluate(SafetyActionContext(
            action="send_message@v1", tenant_id="tenant-live",
            user_id="user-1", payload=outbound,
        )).status == ControlStatus.BLOCK


def test_unsigned_claim_and_untrusted_state_cannot_mint_budget_exemption():
    forged = _payload(meta={"inbound_user_reply": {
        "tenant_id": "tenant-live", "channel": "telegram", "user_id": "user-1",
        "update_id": 462236768, "chat_id": "",
    }})
    assert not is_routine_reply("send_message@v1", forged)
    state = SimpleNamespace(tenant_id="tenant-live", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "telegram", "messaging_update_id": 462236768})
    _, payload = build_payload(state=state, out=ProposedAction("send_message@v1", {
        "user_id": "user-1", "text": "forged",
    }), pinned_world_model_meta={}, tenant_id="tenant-live", product_id=None,
        domain=None, product_version=None, actor_id="user-1")
    assert "inbound_user_reply" not in payload.get("meta", {})
    assert not is_routine_reply("send_message@v1", payload)


def test_proof_is_bound_to_content_and_cryptographic_identity():
    state = SimpleNamespace(tenant_id="tenant-live", user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "vk", "transport_message_id": "vk-event-77",
                 "chat_id": "vk-room-1"})
    _, payload = _trusted_build_payload(state=state, out=ProposedAction("send_message@v1", {
        "user_id": "user-1", "channel": "vk", "chat_id": "vk-room-1", "text": "hello",
    }), pinned_world_model_meta={}, tenant_id="tenant-live", product_id=None,
        domain=None, product_version=None, actor_id="user-1")
    assert is_routine_reply("send_message@v1", payload)
    proof = payload["meta"]["inbound_user_reply"]
    assert not is_routine_reply("send_message@v1", {**payload, "text": "marketing"})
    assert not is_routine_reply("send_message@v1", {**payload, "meta": {
        "inbound_user_reply": {**proof, "update_id": "another-event"}}})
    assert not is_routine_reply("send_message@v1", {**payload, "meta": {
        "inbound_user_reply": {**proof, "signature": "0" * 64}}})
    assert not is_routine_reply("send_message@v1", {**payload, "recipient_count": True})


def test_verified_ingress_scope_is_request_local_and_fails_closed_without_key(monkeypatch):
    assert issue_verified_reply(
        tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
    ) is None
    with verified_inbound_reply_scope(
        tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
    ):
        assert issue_verified_reply(
            tenant_id="another", channel="telegram", user_id="user-1", update_id=462236768,
        ) is None
        assert issue_verified_reply(
            tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
        ) is not None
        monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_SECRET", raising=False)
        monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS", raising=False)
        monkeypatch.delenv("BUSINESAIOS_SAFETY_SIGNING_KEYS_JSON", raising=False)
        assert issue_verified_reply(
            tenant_id="tenant-live", channel="telegram", user_id="user-1", update_id=462236768,
        ) is None
    assert not is_routine_reply("send_message@v1", _payload())


def test_verified_reply_proof_expires_fail_closed(monkeypatch):
    from core.safety.controls.action_budget import models

    assert is_routine_reply("send_message@v1", _payload())
    now = models.time.time()
    monkeypatch.setattr(models.time, "time", lambda: now + 601)
    assert not is_routine_reply("send_message@v1", _payload())



def test_authenticated_telegram_processor_binds_real_update_and_scopes_reply(monkeypatch):
    from contextlib import nullcontext

    from interfaces.telegram.pipeline import update_processor as processor_module
    from kernel.world_state import WorldStateV1

    seen = []
    monkeypatch.setattr(processor_module, "Span", lambda **kw: nullcontext())
    monkeypatch.setattr(processor_module, "resolve_product_context", lambda **kw: {})
    monkeypatch.setattr(processor_module, "emit_behavior_telemetry", lambda **kw: None)
    monkeypatch.setattr(processor_module, "build_worldstate_with_overlays", lambda **kw:
        WorldStateV1(schema_version=1, tenant_id="tenant-live", user_id="777",
                     user={}, session={"channel": "telegram"}, product={}, economy={},
                     meta={}, timestamp_ms=1))
    def run(**kw):
        ws, ctx = kw["ws"], kw["ctx"]
        assert ws.session["source"] == "messaging"
        assert ws.session["messaging_update_id"] == ctx.update_id == 101
        assert ws.session["messaging_chat_id"] == ctx.chat_id == "777"
        seen.append(issue_verified_reply(
            tenant_id=ws.tenant_id, channel="telegram", user_id=ws.user_id,
            update_id=ctx.update_id, chat_id=ctx.chat_id, text="reply",
        ))
    monkeypatch.setattr(processor_module, "run_decision_and_execution", run)
    processor = processor_module.TelegramUpdateProcessor(
        decide_fn=lambda ws: None, execute_fn=lambda env: None,
        enricher=SimpleNamespace(enrich_user=lambda **kw: {}),
        event_log=SimpleNamespace(),
    )
    processor.handle_update({"update_id": 101, "message": {
        "chat": {"id": 777}, "from": {"id": 777}, "text": "/start",
    }})
    assert len(seen) == 1 and seen[0] is not None
    payload = {"tenant_id": "tenant-live", "user_id": "777", "channel": "telegram",
               "text": "reply", "meta": {"inbound_user_reply": seen[0]}}
    assert is_routine_reply("send_message@v1", payload)
    assert issue_verified_reply(
        tenant_id="tenant-live", channel="telegram", user_id="777",
        update_id=101, chat_id="777",
    ) is None



def test_verified_ingress_context_cannot_escape_into_child_async_task():
    import asyncio

    async def child():
        return issue_verified_reply(
            tenant_id="tenant-live", channel="vk", user_id="user-1", update_id="event-9",
        )

    async def parent():
        with verified_inbound_reply_scope(
            tenant_id="tenant-live", channel="vk", user_id="user-1", update_id="event-9",
        ):
            assert issue_verified_reply(
                tenant_id="tenant-live", channel="vk", user_id="user-1", update_id="event-9",
            ) is not None
            return await asyncio.create_task(child())

    assert asyncio.run(parent()) is None



def test_only_authenticated_ingress_owners_can_open_signed_reply_scope():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    allowed = {
        "core/safety/controls/action_budget/models.py",
        "interfaces/telegram/pipeline/update_processor.py",
        "runtime/entrypoints/telegram_longpoll.py",
        "runtime/business_autonomy/provider_inbound_webhook_service.py",
    }
    # A public facade may re-export the signer, but must not open a scope.
    import ast

    facade = root / "runtime/safety/_surface.py"
    tree = ast.parse(facade.read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "core.safety.controls.action_budget.models"
        and any(alias.name == "verified_inbound_reply_scope" for alias in node.names)
        for node in tree.body
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "verified_inbound_reply_scope"
        for node in ast.walk(tree)
    )
    for path in (root / "runtime", root / "interfaces", root / "application", root / "core"):
        for file in path.rglob("*.py"):
            rel = file.relative_to(root).as_posix()
            if "verified_inbound_reply_scope" in file.read_text(errors="replace"):
                assert rel in allowed or rel == "runtime/safety/_surface.py", f"unverified ingress signer: {rel}"



@pytest.mark.parametrize("key,value", [
    ("recipients", ["user-1", "user-2"]), ("recipient_ids", ["user-2"]),
    ("target_users", ["user-2"]), ("audience", "all"),
    ("segment_id", "all"), ("broadcast", True), ("bulk", True),
    ("batch_id", "batch-1"), ("campaign_id", "campaign-1"),
    ("scheduled_at", "tomorrow"), ("marketing", True),
    ("autonomous", True), ("proactive", True), ("charge_amount", 5),
])
def test_authenticated_reply_cannot_exempt_bulk_marketing_or_paid_effects(key, value):
    assert is_routine_reply("send_message@v1", _payload())
    assert not is_routine_reply("send_message@v1", _payload(**{key: value}))


@pytest.mark.parametrize("extra", [
    {"kind": "marketing"}, {"kind": "broadcast"},
    {"track_payload": {"campaign_id": "campaign-1"}},
    {"track_payload": {"marketing_variant": "variant-b"}},
    {"track_payload": {"recipients": ["user-1", "user-2"]}},
    {"channel_policy": {"fallback_channels": ["telegram", "max"]}},
])
def test_signed_reply_does_not_exempt_marketing_routing_metadata(extra):
    assert not is_routine_reply("send_message@v1", _payload(**extra))



def test_signed_reply_cannot_bypass_budget_of_another_safety_context_tenant():
    ledger = InMemoryActionBudgetLedger()
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=0, max_actions=0))
    assert is_routine_reply("send_message@v1", _payload())
    ctx = SafetyActionContext(
        action="send_message@v1", tenant_id="tenant-other", user_id="user-1",
        payload=_payload(),
    )
    assert guard.evaluate(ctx).status == ControlStatus.BLOCK



def test_operational_user_reply_classification_requires_same_tenant():
    from contracts.action_impact_contract import ActionExecutionContext
    from core.safety.operational.action_classifier import ActionClassifier
    from core.safety.operational.action_registry import (
        USER_REPLY_INTERACTION,
        build_default_operational_action_registry,
    )

    classifier = ActionClassifier(build_default_operational_action_registry())
    def classify(tenant):
        return classifier.classify(ActionExecutionContext(
            tenant_id=tenant, user_id="user-1", action_name="send_message@v1",
            payload=_payload(),
        )).spec.dimensions.get("interaction")
    assert classify("tenant-live") == USER_REPLY_INTERACTION
    assert classify("tenant-other") != USER_REPLY_INTERACTION


@pytest.mark.parametrize("channel", ["vk", "max", "whatsapp"])
def test_unverified_messaging_reply_is_sealed_to_session_channel(channel):
    state = SimpleNamespace(user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": channel, "chat_id": "-9"})
    _, payload = build_payload(
        state=state, out=ProposedAction("send_message@v1", {"user_id": "user-1", "text": "menu"}),
        pinned_world_model_meta={}, tenant_id="tenant-live",
        product_id=None, domain=None, product_version=None, actor_id="user-1",
    )
    assert payload["channel"] == channel
    assert payload["chat_id"] == -9

@pytest.mark.parametrize("field,bad", [("channel", "telegram"), ("chat_id", "-10")])
def test_unverified_reply_rejects_cross_transport_target(field, bad):
    state = SimpleNamespace(user_id="user-1", meta={}, product={},
        session={"source": "messaging", "channel": "vk", "chat_id": "-9"})
    with pytest.raises(RuntimeError, match="DECISION_(CHANNEL|CHAT_ID)_MISMATCH"):
        build_payload(
            state=state, out=ProposedAction("send_message@v1",
                {"user_id": "user-1", "text": "menu", field: bad}),
            pinned_world_model_meta={}, tenant_id="tenant-live",
            product_id=None, domain=None, product_version=None, actor_id="user-1",
        )
