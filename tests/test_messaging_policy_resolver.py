from types import SimpleNamespace

import pytest

from runtime.messaging.channel_preference import ChannelPreference
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
            unanswered_snapshot=UnansweredSnapshot(
                current_channel="telegram",
                seconds_since_last_user_reply=7200,
            ),
        )
    )
    assert plan.ordered_channels == ("whatsapp", "sms", "telegram")


def test_resolver_drops_failed_and_blocked():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(
                primary="telegram",
                enabled=("telegram", "whatsapp", "sms", "email"),
                verified=("telegram", "whatsapp", "sms", "email"),
            ),
            preferred_channel="telegram",
            fallback_channels=("whatsapp", "sms", "email"),
            delivery_snapshot=DeliverySnapshot(
                failed=("telegram", "whatsapp"),
                blocked=("sms",),
            ),
        )
    )
    assert plan.ordered_channels == ("email",)


def test_resolver_verified_only_filters_non_verified():
    resolver = MessagingPolicyResolver()
    plan = resolver.resolve(
        PolicyRequest(
            preference=ChannelPreference(
                primary="telegram",
                enabled=("telegram", "whatsapp", "email"),
                verified=("email",),
            ),
            preferred_channel="telegram",
            fallback_channels=("whatsapp", "email"),
            verified_only=True,
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
        PolicyRequest(preference=preference, contact_basis=contact_basis)  # type: ignore[arg-type]


def test_terminal_contact_block_skips_capability_routing(monkeypatch):
    from runtime._internal.effects_actions.telegram.messaging_parts import policy as delivery_policy

    preference = ChannelPreference(primary="whatsapp", enabled=("whatsapp", "email"))
    monkeypatch.setattr(delivery_policy, "load_channel_preference", lambda **_kwargs: preference)
    monkeypatch.setattr(delivery_policy, "_apply_capability_routing", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("terminal plans must not be rerouted")))
    monkeypatch.setattr(delivery_policy, "build_policy_event_recorder_from_runtime", lambda _runtime: None)
    monkeypatch.setattr(delivery_policy, "_with_health_feedback", lambda _runtime, *, send_once: send_once)
    monkeypatch.setattr(delivery_policy, "execute_policy_plan_with_events", lambda **kwargs: kwargs["plan"])
    msg = SimpleNamespace(tenant_id="tenant-a", channel="whatsapp", critical=False)
    plan = delivery_policy.execute_with_policy(SimpleNamespace(settings_gateway=None), msg=msg, channel_policy={"contact_basis": "none"}, send_once=lambda _msg: (True, {}))
    assert isinstance(plan, PolicyPlan)
    assert plan.ordered_channels == ()
    assert plan.terminal_reason == "outbound_forbidden"
