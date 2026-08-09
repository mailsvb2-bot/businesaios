from types import SimpleNamespace

import pytest

from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging.outbound_message import OutboundMessage
from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
from runtime.messaging_policy.policy_plan import PolicyPlan
from runtime.messaging_policy.policy_request import PolicyRequest
from runtime.messaging_policy.resolver import MessagingPolicyResolver
from runtime.messaging_policy.unanswered_snapshot import UnansweredSnapshot


def test_resolver_uses_primary_then_enabled():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(
                primary="whatsapp",
                enabled=("telegram", "whatsapp", "email"),
                verified=("whatsapp", "email"),
            ),
            preferred_channel=None,
            fallback_channels=(),
            verified_only=False,
            critical=False,
        )
    )
    assert plan.ordered_channels == ("whatsapp", "telegram", "email")


def test_resolver_moves_current_channel_back_if_unanswered_threshold_reached():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(
                primary="telegram",
                enabled=("telegram", "whatsapp", "sms"),
                verified=("telegram", "whatsapp", "sms"),
            ),
            preferred_channel="telegram",
            fallback_channels=("whatsapp", "sms"),
            unanswered_threshold_s=3600,
            unanswered_snapshot=UnansweredSnapshot(current_channel="telegram", seconds_since_last_user_reply=7200),
        )
    )
    assert plan.ordered_channels == ("whatsapp", "sms", "telegram")


def test_resolver_drops_failed_and_blocked():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(primary="telegram", enabled=("telegram", "whatsapp", "sms", "email"),
                verified=("telegram", "whatsapp", "sms", "email")),
            preferred_channel="telegram",
            fallback_channels=("whatsapp", "sms", "email"),
            delivery_snapshot=DeliverySnapshot(failed=("telegram", "whatsapp"), blocked=("sms",)),
        )
    )
    assert plan.ordered_channels == ("email",)


def test_resolver_verified_only_filters_non_verified():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(primary="telegram", enabled=("telegram", "whatsapp", "email"), verified=("email",)),
            preferred_channel="telegram", fallback_channels=("whatsapp", "email"), verified_only=True,
        )
    )
    assert plan.ordered_channels == ("email",)


def test_explicit_missing_contact_basis_blocks_outbound_before_channel_selection():
    preference = ChannelPreference(primary="whatsapp", enabled=("whatsapp", "email"))
    plan = MessagingPolicyResolver().resolve(PolicyRequest(preference=preference, contact_basis="none"))
    assert plan.ordered_channels == ()
    assert plan.terminal_reason == "outbound_forbidden"
    assert "outbound_forbidden" in plan.reason_codes


@pytest.mark.parametrize("contact_basis", [False, 0, ""])
def test_malformed_explicit_contact_basis_fails_closed(contact_basis: object) -> None:
    preference = ChannelPreference(primary="whatsapp", enabled=("whatsapp", "email"))
    with pytest.raises(ValueError, match="contact_basis"):
        PolicyRequest(preference=preference, contact_basis=contact_basis)


def test_malformed_contact_basis_returns_deterministic_delivery_block(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    preference = ChannelPreference(primary="whatsapp", enabled=("whatsapp", "email"))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: preference)
    msg = SimpleNamespace(tenant_id="tenant-a", channel="whatsapp", critical=False)
    result = delivery_policy.execute_delivery_path(SimpleNamespace(settings_gateway=None), msg=msg,
        channel_policy={"contact_basis": False}, send_once=lambda _msg: (_ for _ in ()).throw(AssertionError("must not send")))
    assert result[0] is False
    assert result[1]["policy"]["terminal_reason"] == "discipline_violation"


def test_terminal_contact_block_skips_capability_routing(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    preference = ChannelPreference(primary="whatsapp", enabled=("whatsapp", "email"))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: preference)
    monkeypatch.setattr(delivery_policy, "_apply_capability_routing", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("terminal plans must not be rerouted")))
    monkeypatch.setattr(delivery_policy, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(delivery_policy, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    monkeypatch.setattr(delivery_policy, "execute_policy_plan_with_events", lambda **kwargs: kwargs["plan"])
    msg = SimpleNamespace(tenant_id="tenant-a", channel="whatsapp", critical=False)
    plan = delivery_policy.execute_with_policy(SimpleNamespace(settings_gateway=None), msg=msg,
        channel_policy={"contact_basis": "none"}, send_once=lambda _msg: (True, {}))
    assert isinstance(plan, PolicyPlan)
    assert plan.ordered_channels == ()
    assert plan.terminal_reason == "outbound_forbidden"


def test_changed_preference_snapshot_blocks_before_capability_routing_or_send(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    approved = ChannelPreference(primary="telegram", enabled=("telegram",), verified=("telegram",))
    current = ChannelPreference(primary="telegram", enabled=("telegram", "email"), verified=("telegram", "email"))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: current)
    monkeypatch.setattr(delivery_policy, "_apply_capability_routing", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("stale approval must not reach capability routing")))
    monkeypatch.setattr(delivery_policy, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(delivery_policy, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    monkeypatch.setattr(delivery_policy, "execute_policy_plan_with_events", lambda **kwargs: kwargs["plan"])
    msg = SimpleNamespace(tenant_id="tenant-a", channel="telegram", critical=True)
    plan = delivery_policy.execute_with_policy(
        SimpleNamespace(settings_gateway=object()),
        msg=msg,
        channel_policy={"contact_basis": "existing_customer", "preference_snapshot": approved.to_mapping()},
        send_once=lambda _msg: (_ for _ in ()).throw(AssertionError("stale approval must not send")),
    )
    assert isinstance(plan, PolicyPlan)
    assert plan.ordered_channels == ()
    assert plan.reason_codes == ("preference_changed",)
    assert plan.terminal_reason == "preference_changed"


def test_matching_preference_snapshot_is_used_by_the_existing_resolver(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    preference = ChannelPreference(primary="telegram", enabled=("telegram", "email"), verified=("telegram", "email"))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: preference)
    monkeypatch.setattr(delivery_policy, "_apply_capability_routing", lambda _runtime, *, ordered_channels, disciplined_policy: PolicyPlan(ordered_channels=ordered_channels, reason_codes=("capability_route_applied",)))
    monkeypatch.setattr(delivery_policy, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(delivery_policy, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    monkeypatch.setattr(delivery_policy, "execute_policy_plan_with_events", lambda **kwargs: kwargs["plan"])
    msg = SimpleNamespace(tenant_id="tenant-a", channel="telegram", critical=False)
    plan = delivery_policy.execute_with_policy(
        SimpleNamespace(settings_gateway=object()),
        msg=msg,
        channel_policy={"contact_basis": "existing_customer", "preference_snapshot": preference.to_mapping()},
        send_once=lambda _msg: (True, {}),
    )
    assert plan.ordered_channels == ("telegram", "email")
    assert plan.terminal_reason == ""


def test_preference_snapshot_is_rechecked_before_every_transport_attempt(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    approved = ChannelPreference(primary="telegram", enabled=("telegram", "email"), verified=("telegram", "email"))
    changed = ChannelPreference(primary="telegram", enabled=("telegram",), verified=("telegram",))
    reads = iter((approved, approved, changed))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: next(reads))
    monkeypatch.setattr(delivery_policy, "_apply_capability_routing", lambda _runtime, *, ordered_channels, disciplined_policy: PolicyPlan(ordered_channels=ordered_channels, reason_codes=("capability_route_applied",)))
    monkeypatch.setattr(delivery_policy, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(delivery_policy, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    attempted: list[str] = []

    def send_once(selected_msg):
        assert callable(selected_msg.transport_guard)
        attempted.append(selected_msg.channel)
        return False, {}

    msg = OutboundMessage(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="tenant-a",
        user_id="user-1",
        channel="telegram",
        text="approved",
        critical=False,
    )
    ok, meta = delivery_policy.execute_with_policy(
        SimpleNamespace(settings_gateway=object()),
        msg=msg,
        channel_policy={
            "contact_basis": "existing_customer",
            "fallback_channels": ["email"],
            "preference_snapshot": approved.to_mapping(),
        },
        send_once=send_once,
    )
    assert ok is False
    assert attempted == ["telegram"]
    assert meta["policy"]["terminal_reason"] == "preference_changed"
    assert [item["channel"] for item in meta["policy"]["attempts"]] == ["telegram"]


def test_provider_bound_guard_is_terminal_without_health_failure(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy
    from runtime.messaging_policy_events.execute_with_events import execute_policy_plan_with_events

    health_calls: list[dict] = []
    monkeypatch.setattr(delivery_policy, "resolve_capability_telemetry_updater",
        lambda _runtime: SimpleNamespace(record_delivery_outcome=lambda **kwargs: health_calls.append(kwargs)))
    sender = delivery_policy._with_health_feedback(
        SimpleNamespace(),
        send_once=lambda _msg: (False, {"transport_guard_reason": "preference_changed"}),
    )
    plan = PolicyPlan(ordered_channels=("telegram", "email"), reason_codes=("preference_snapshot_bound",))
    msg = OutboundMessage(decision_id="d", correlation_id="c", tenant_id="tenant-a", user_id="u", channel="telegram", text="x")
    ok, meta = execute_policy_plan_with_events(plan=plan, base_message=msg, send_once=sender)
    assert ok is False
    assert meta["policy"]["terminal_reason"] == "preference_changed"
    assert meta["policy"]["attempts"] == []
    assert health_calls == []


def test_guarded_telegram_send_bypasses_async_queue_and_checks_before_http(monkeypatch):
    from runtime._internal.effects_clients.telegram_client import TelegramClient

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    class Queue:
        def __init__(self):
            self.calls: list[dict] = []

        def enqueue(self, **kwargs):
            self.calls.append(dict(kwargs))
            return True

    queue = Queue()
    client = TelegramClient(outbound_queue=queue)
    http_calls: list[dict] = []
    monkeypatch.setattr(client, "_http_post", lambda **kwargs: http_calls.append(dict(kwargs)) or {"ok": True, "result": {"message_id": 1}})

    ok, meta = client.send_message(chat_id="123", text="approved", transport_guard=lambda: "preference_changed")
    assert ok is False and meta["mode"] == "blocked"
    assert meta["transport_guard_reason"] == "preference_changed"
    assert queue.calls == [] and http_calls == []

    ok, meta = client.send_message(chat_id="124", text="approved", transport_guard=lambda: "")
    assert ok is True and meta["mode"] == "direct"
    assert queue.calls == [] and len(http_calls) == 1

    ok, meta = client.send_message(chat_id="125", text="ordinary")
    assert ok is True and meta["mode"] == "queued"
    assert len(queue.calls) == 1 and len(http_calls) == 1


@pytest.mark.parametrize("mode", ["webhook", "smtp"])
def test_multichannel_provider_guard_blocks_before_network(monkeypatch, mode: str):
    from runtime._internal.effects_clients import provider_outbound_sender as sender
    from runtime.messaging.provider_config import ProviderConfig

    cfg = ProviderConfig(
        provider="email" if mode == "smtp" else "whatsapp",
        env_prefix="TEST_PROVIDER",
        mode=mode,
        endpoint="smtp://smtp.example:25" if mode == "smtp" else "https://provider.example/send",
        sender="from@example.com",
        token_present=False,
    )
    msg = OutboundMessage(
        decision_id="decision-1",
        correlation_id="correlation-1",
        tenant_id="tenant-a",
        user_id="to@example.com" if mode == "smtp" else "user-1",
        channel="email" if mode == "smtp" else "whatsapp",
        text="approved",
        transport_guard=lambda _msg: "preference_changed",
    )
    monkeypatch.setattr(sender.urllib_request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("webhook must not run")))
    monkeypatch.setattr(sender.smtplib, "SMTP", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("smtp must not run")))
    monkeypatch.setattr(sender.smtplib, "SMTP_SSL", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("smtp must not run")))

    result = sender.send_outbound(cfg=cfg, msg=msg)
    assert result["ok"] is False
    assert result["mode"] == "blocked"
    assert result["transport_guard_reason"] == "preference_changed"
    assert result["delivery_disposition"] == "suppressed"
