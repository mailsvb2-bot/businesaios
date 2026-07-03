from __future__ import annotations

from runtime.messaging.channel_preference import ChannelPreference
from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
from runtime.messaging_policy.policy_request import PolicyRequest
from runtime.messaging_policy.resolver import MessagingPolicyResolver
from runtime.messaging_policy.sequence_builder import build_candidate_sequence
from runtime.messaging_policy.unanswered_snapshot import UnansweredSnapshot


def test_candidate_sequence_supports_explicit_multi_channel_fallbacks_without_telegram_bias() -> None:
    preference = ChannelPreference(
        primary="whatsapp",
        enabled=("whatsapp", "sms", "email", "web_chat", "api", "telegram"),
    )
    request = PolicyRequest(
        preference=preference,
        preferred_channel="whatsapp",
        fallback_channels=("web_chat", "api", "sms"),
        critical=True,
    )

    assert build_candidate_sequence(request) == ("whatsapp", "web_chat", "api", "sms", "email")


def test_resolver_filters_failed_and_blocked_channels_across_messengers() -> None:
    preference = ChannelPreference(
        primary="whatsapp",
        enabled=("whatsapp", "sms", "email", "web_chat"),
    )
    request = PolicyRequest(
        preference=preference,
        critical=True,
        delivery_snapshot=DeliverySnapshot(failed=("whatsapp",), blocked=("sms",)),
    )

    plan = MessagingPolicyResolver().resolve(request)

    assert plan.ordered_channels == ("email", "web_chat")
    assert "failed_filtered" in plan.reason_codes
    assert "blocked_filtered" in plan.reason_codes
    assert plan.terminal_reason == ""


def test_resolver_verified_only_does_not_fall_back_to_unverified_telegram() -> None:
    preference = ChannelPreference(
        primary="whatsapp",
        enabled=("whatsapp", "sms", "email", "telegram"),
        verified=("email",),
    )
    request = PolicyRequest(
        preference=preference,
        preferred_channel="whatsapp",
        fallback_channels=("sms", "email", "telegram"),
        verified_only=True,
        critical=True,
    )

    plan = MessagingPolicyResolver().resolve(request)

    assert plan.ordered_channels == ("email",)
    assert "verified_only_filtered" in plan.reason_codes


def test_unanswered_rotation_moves_current_channel_behind_other_messengers() -> None:
    preference = ChannelPreference(
        primary="whatsapp",
        enabled=("whatsapp", "sms", "email"),
    )
    request = PolicyRequest(
        preference=preference,
        critical=True,
        unanswered_threshold_s=300,
        unanswered_snapshot=UnansweredSnapshot(
            current_channel="whatsapp",
            seconds_since_last_user_reply=600,
        ),
    )

    plan = MessagingPolicyResolver().resolve(request)

    assert plan.ordered_channels == ("sms", "email", "whatsapp")
    assert "unanswered_rotation_checked" in plan.reason_codes
