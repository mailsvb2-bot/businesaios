from __future__ import annotations

import pytest

import runtime.messaging.bridge as bridge_module
from runtime.messaging import CHANNEL_SPECS, get_channel_spec
from runtime.messaging.adapter_protocol import MessageAdapter
from runtime.messaging.bridge import MultiChannelEffectsBridge, get_multichannel_effects_bridge
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.delivery_result import DeliveryResult
from runtime.messaging.dispatcher import MultiChannelDispatcher
from runtime.messaging.inbound_decision_gateway import (
    MessagingInboundDecisionGateway,
    process_inbound_gateway_message,
)
from runtime.messaging.inbound_owner_lock import (
    InboundOwnerViolation,
    MessagingInboundOwnerLockError,
    assert_inbound_decision_owner,
    assert_inbound_owner,
)
from runtime.messaging.inbound_strict_owner_guard import (
    InboundOwnerViolation as CompatibilityInboundOwnerViolation,
)
from runtime.messaging.inbound_strict_owner_guard import (
    assert_inbound_owner as assert_compatibility_decision_owner,
)
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging.router import UnifiedConversationRouter
from runtime.messaging.settings import SETTING_KEY, canonical_channel_preference_value


def _message(channel: str = "telegram") -> OutboundMessage:
    return OutboundMessage(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="tenant-1",
        user_id="user-1",
        channel=channel,
        text="hello",
    )


class _Adapter:
    def __init__(self) -> None:
        self.messages: list[OutboundMessage] = []

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        self.messages.append(msg)
        return DeliveryResult(True, msg.channel, "test", "external-1")


def test_channel_catalog_and_normalizer_are_canonical() -> None:
    assert get_channel_spec("tg") is CHANNEL_SPECS["telegram"]
    assert get_channel_spec("webchat").key == "web_chat"
    with pytest.raises(ValueError, match="UNKNOWN_CHANNEL:not_real"):
        normalize_channel("not-real")
    with pytest.raises(KeyError, match="UNKNOWN_CHANNEL"):
        get_channel_spec("not-real")


def test_delivery_result_preserves_success_message_and_error_contracts() -> None:
    success = DeliveryResult(True, "telegram", "bot_api", "42", {"reason": "ignored"})
    assert success.success is True
    assert success.message_id == "42"
    assert success.error is None

    reason = DeliveryResult(False, "sms", "provider", "", {"reason": "rejected"})
    error = DeliveryResult(False, "email", "smtp", None, {"error": "timeout"})
    empty = DeliveryResult(False, "email", "smtp", "", None)
    assert reason.error == "rejected"
    assert error.message_id == ""
    assert error.error == "timeout"
    assert empty.error == ""


def test_dispatcher_and_protocol_preserve_registered_and_missing_adapter_paths() -> None:
    adapter = _Adapter()
    protocol: MessageAdapter = adapter
    dispatcher = MultiChannelDispatcher()
    dispatcher.register_adapter("telegram", protocol)
    result = dispatcher.dispatch(_message())
    assert result.ok is True
    assert adapter.messages == [_message()]

    missing = dispatcher.send(_message("discord"))
    assert missing.ok is False
    assert missing.mode == "missing_adapter"
    assert missing.detail == {"reason": "missing_adapter", "channel": "discord"}


def test_bridge_singleton_and_effect_delegation(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _Adapter()
    monkeypatch.setattr(
        bridge_module,
        "build_multichannel_dispatcher",
        lambda: MultiChannelDispatcher(adapters={"telegram": adapter}),
    )
    monkeypatch.setattr(bridge_module, "_BRIDGE", None)
    first = get_multichannel_effects_bridge()
    second = get_multichannel_effects_bridge()
    assert isinstance(first, MultiChannelEffectsBridge)
    assert first is second
    assert first.send(_message()).external_id == "external-1"


def test_single_inbound_authority_policy_preserves_both_public_surfaces() -> None:
    assert_inbound_owner("interfaces.web.chat_widget.api_handlers")
    assert_inbound_owner(" runtime.messaging.inbound_entrypoint ")
    assert_inbound_decision_owner("runtime.messaging.inbound_entrypoint")
    assert_compatibility_decision_owner(
        "runtime.business_autonomy.provider_webhook_inbound_processor"
    )
    assert CompatibilityInboundOwnerViolation is InboundOwnerViolation

    with pytest.raises(MessagingInboundOwnerLockError, match="messaging_inbound_requires"):
        assert_inbound_owner("interfaces.untrusted")
    with pytest.raises(InboundOwnerViolation, match="canonical_messaging_inbound_requires"):
        assert_inbound_decision_owner("interfaces.web.chat_widget.api_handlers")
    with pytest.raises(InboundOwnerViolation):
        assert_compatibility_decision_owner("")


def test_gateway_uses_only_canonical_owner_and_preserves_legacy_issue_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, object]] = []

    def issue(*, decision_core, message):
        calls.append((decision_core, message))
        return "envelope"

    monkeypatch.setattr(
        "runtime.messaging.inbound_decision_gateway.issue_inbound_message_decision",
        issue,
    )
    message = object()
    gateway = MessagingInboundDecisionGateway(
        decision_core="decision-core",
        caller="runtime.messaging.inbound_entrypoint",
    )
    assert gateway.issue(message=message) == "envelope"
    assert calls == [("decision-core", message)]

    with pytest.raises(InboundOwnerViolation):
        MessagingInboundDecisionGateway(
            decision_core="decision-core",
            caller="interfaces.untrusted",
        ).process(message=message)

    class ProcessGateway:
        def process(self, *, message):
            return ("process", message)

    class IssueGateway:
        def issue(self, *, message):
            return ("issue", message)

    assert process_inbound_gateway_message(gateway=ProcessGateway(), message=message) == (
        "process",
        message,
    )
    assert process_inbound_gateway_message(gateway=IssueGateway(), message=message) == (
        "issue",
        message,
    )
    with pytest.raises(TypeError, match="INBOUND_DECISION_GATEWAY_CONTRACT_VIOLATION"):
        process_inbound_gateway_message(gateway=object(), message=message)


def test_router_preserves_multichannel_user_coordinates_and_describe_contract() -> None:
    router = UnifiedConversationRouter()
    message = router.normalize(
        channel="wa",
        tenant_id="tenant-1",
        payload={
            "sender_id": "user-1",
            "body": "hello",
            "event_id": "event-1",
            "trace_id": "trace-1",
            "phone": "+1000",
            "locale": "nl-NL",
        },
    )
    assert message.channel == "whatsapp"
    assert message.user_id == "user-1"
    assert message.transport_message_id == "event-1"
    assert message.correlation_id == "trace-1"
    assert message.external_user_ref == "+1000"
    assert message.metadata["locale"] == "nl-NL"
    route = router.describe(message)
    assert route.conversation_id == "whatsapp:user-1"
    assert router.route(message) == route.conversation_id


def test_settings_preserve_primary_enabled_verified_and_deduplication() -> None:
    assert SETTING_KEY == "messaging:channel_preference"
    value = canonical_channel_preference_value(
        primary="tg",
        enabled=["telegram", "wa", "telegram"],
        verified=["wa", "discord"],
    )
    assert value == {
        "primary": "telegram",
        "enabled": ["telegram", "whatsapp"],
        "verified": ["whatsapp"],
    }


def test_catalog_missing_spec_branch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(CHANNEL_SPECS, "telegram")
    with pytest.raises(KeyError, match="UNKNOWN_CHANNEL:telegram"):
        get_channel_spec("telegram")


def test_bootstrap_builds_every_non_telegram_effect_adapter() -> None:
    from runtime.messaging.bootstrap import build_multichannel_dispatcher

    dispatcher = build_multichannel_dispatcher()
    assert tuple(sorted(dispatcher.adapters)) == (
        "api",
        "discord",
        "email",
        "instagram",
        "kakaotalk",
        "line",
        "messenger",
        "slack",
        "sms",
        "viber",
        "web_chat",
        "wechat",
        "whatsapp",
    )


def test_channel_preference_mapping_compatibility_paths() -> None:
    from runtime.messaging.channel_preference import ChannelPreference

    defaulted = ChannelPreference.from_mapping(None)
    assert defaulted.primary == "telegram"
    assert defaulted.enabled == ("telegram",)
    assert defaulted.verified == ()

    explicit = ChannelPreference.from_mapping(
        {
            "primary": "wa",
            "enabled": ("sms", "wa"),
            "verified": ["sms", "email"],
        }
    )
    assert explicit.primary == "whatsapp"
    assert explicit.enabled == ("whatsapp", "sms")
    assert explicit.verified == ("sms",)

    malformed = ChannelPreference.from_mapping(
        {"primary": "email", "enabled": "sms", "verified": {"email"}}
    )
    assert malformed.enabled == ("email",)
    assert malformed.verified == ()


def test_inbound_entrypoint_preserves_single_locked_decision_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import runtime.messaging.inbound_entrypoint as entrypoint
    from runtime.messaging.inbound_message import InboundMessage

    message = InboundMessage(
        tenant_id="tenant-1",
        channel="slack",
        user_id="user-1",
        text="hello",
        correlation_id="corr-1",
        transport_message_id="msg-1",
    )
    observed: dict[str, object] = {}

    class Result:
        def __init__(self, envelope):
            self.envelope = envelope

    def issue_locked_decision(*, decision_core, state):
        observed["decision_core"] = decision_core
        observed["state"] = state
        return Result("issued-envelope")

    def lock_decision_for_executor(*, envelope):
        observed["locked"] = envelope
        return Result("executor-envelope")

    monkeypatch.setattr(entrypoint, "issue_locked_decision", issue_locked_decision)
    monkeypatch.setattr(entrypoint, "lock_decision_for_executor", lock_decision_for_executor)

    assert entrypoint.handle_inbound_message(decision_core="core", message=message) == "executor-envelope"
    assert observed["decision_core"] == "core"
    assert observed["locked"] == "issued-envelope"
    state = observed["state"]
    assert state.channel == "slack"
    assert state.message_text == "hello"


def test_outbound_message_preserves_default_and_explicit_payload_identity() -> None:
    defaulted = OutboundMessage(
        decision_id="d",
        correlation_id="c",
        tenant_id="t",
        user_id="u",
        channel="",
        text=None,
        reply_markup={"inline": True},
        callback_query_id="cb",
        track_event_type="sent",
        track_payload={"x": 1},
        priority="",
    )
    assert defaulted.channel == "telegram"
    assert defaulted.priority == "normal"
    assert defaulted.text == ""
    assert defaulted.payload == {
        "text": "",
        "reply_markup": {"inline": True},
        "track_event_type": "sent",
        "track_payload": {"x": 1},
        "callback_query_id": "cb",
    }
    assert len(defaulted.payload_digest) == 64
    assert len(defaulted.delivery_key) == 64

    explicit = OutboundMessage(
        decision_id="d",
        correlation_id="c",
        tenant_id="t",
        user_id="u",
        channel="email",
        text="body",
        payload={"subject": "hello", "body": "body"},
    )
    reordered = OutboundMessage(
        decision_id="d",
        correlation_id="c",
        tenant_id="t",
        user_id="u",
        channel="email",
        text="body",
        payload={"body": "body", "subject": "hello"},
    )
    assert explicit.payload == {"subject": "hello", "body": "body"}
    assert explicit.payload_digest == reordered.payload_digest
    assert explicit.delivery_key == reordered.delivery_key


def test_router_extractors_return_empty_coordinates_for_empty_payload() -> None:
    from runtime.messaging.router_extractors import (
        correlation_id_from_payload,
        external_user_ref_from_payload,
        message_id_from_payload,
        metadata_from_payload,
        pick,
        text_from_payload,
        user_id_from_payload,
    )

    assert pick({}, "missing") is None
    assert text_from_payload({}) == ""
    assert user_id_from_payload({}) == ""
    assert message_id_from_payload({}) == ""
    assert correlation_id_from_payload({}, fallback_message_id="fallback") == "fallback"
    assert external_user_ref_from_payload({}, fallback_user_id="user") == "user"
    assert metadata_from_payload({}, channel="discord") == {
        "channel": "discord",
        "payload_keys": (),
    }
