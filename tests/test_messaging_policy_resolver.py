from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
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
