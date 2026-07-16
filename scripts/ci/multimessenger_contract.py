from __future__ import annotations

from collections.abc import Mapping


# This is a certification baseline, not a runtime registry. Runtime code never
# imports it and no delivery decision is made here. Changing or removing a
# user-facing channel therefore requires an explicit lock update and review.
EXPECTED_CHANNELS = (
    "telegram",
    "whatsapp",
    "sms",
    "email",
    "messenger",
    "instagram",
    "web_chat",
    "api",
    "line",
    "wechat",
    "kakaotalk",
    "viber",
    "slack",
    "discord",
)

EXPECTED_CHANNEL_SPECS: Mapping[str, tuple[str, str, str, str]] = {
    "telegram": ("messaging", "TELEGRAM", "configured_noop", "bot_api"),
    "whatsapp": ("messaging", "WHATSAPP", "webhook", "provider_webhook"),
    "sms": ("messaging", "SMS", "webhook", "provider_webhook"),
    "email": ("messaging", "EMAIL", "smtp", "smtp"),
    "messenger": ("messaging", "MESSENGER", "webhook", "provider_webhook"),
    "instagram": ("messaging", "INSTAGRAM", "webhook", "provider_webhook"),
    "web_chat": ("web", "WEB_CHAT", "configured_noop", "internal_widget"),
    "api": ("web", "API_GATEWAY", "configured_noop", "internal_api"),
    "line": ("regional", "LINE", "webhook", "provider_webhook"),
    "wechat": ("regional", "WECHAT", "webhook", "provider_webhook"),
    "kakaotalk": ("regional", "KAKAOTALK", "webhook", "provider_webhook"),
    "viber": ("regional", "VIBER", "webhook", "provider_webhook"),
    "slack": ("collaboration", "SLACK", "webhook", "provider_webhook"),
    "discord": ("collaboration", "DISCORD", "webhook", "provider_webhook"),
}


def _failure(message: str) -> tuple[bool, str]:
    return False, f"multimessenger runtime lock failed: {message}"


def verify_multimessenger_runtime_contract() -> tuple[bool, str]:
    """Validate one complete transport surface without becoming a decision owner."""

    from interfaces.messaging_runtime.capabilities import (
        DEFAULT_CAPABILITIES,
        get_capabilities,
    )
    from interfaces.messaging_runtime.channel_aliases import canonical_channel_name
    from interfaces.messaging_runtime.channel_loader import BINDING_BUILDERS
    from runtime.messaging import CHANNEL_SPECS
    from runtime.messaging.bootstrap import build_multichannel_dispatcher
    from runtime.messaging.channel_types import ALL_CHANNELS, CHANNELS, CHANNEL_TELEGRAM

    actual_channels = tuple(ALL_CHANNELS)
    if actual_channels != EXPECTED_CHANNELS:
        return _failure(
            f"canonical channels drifted: expected={EXPECTED_CHANNELS!r} actual={actual_channels!r}"
        )
    if tuple(CHANNELS) != EXPECTED_CHANNELS:
        return _failure("legacy CHANNELS compatibility list drifted")
    if len(set(actual_channels)) != len(actual_channels):
        return _failure("canonical channel list contains duplicates")

    expected_set = set(EXPECTED_CHANNELS)
    if set(CHANNEL_SPECS) != expected_set:
        return _failure(
            f"channel spec coverage drifted: missing={sorted(expected_set - set(CHANNEL_SPECS))} "
            f"extra={sorted(set(CHANNEL_SPECS) - expected_set)}"
        )
    for channel, expected in EXPECTED_CHANNEL_SPECS.items():
        spec = CHANNEL_SPECS[channel]
        actual = (
            spec.family,
            spec.provider_env_prefix,
            spec.mode_default,
            spec.transport_kind,
        )
        if spec.key != channel or actual != expected:
            return _failure(
                f"channel spec drifted for {channel}: expected={expected!r} actual={actual!r}"
            )

    dispatcher = build_multichannel_dispatcher()
    expected_dispatch = expected_set - {CHANNEL_TELEGRAM}
    actual_dispatch = set(dispatcher.adapters)
    if actual_dispatch != expected_dispatch:
        return _failure(
            f"dispatcher coverage drifted: missing={sorted(expected_dispatch - actual_dispatch)} "
            f"extra={sorted(actual_dispatch - expected_dispatch)}"
        )
    missing_send = sorted(
        channel
        for channel, adapter in dispatcher.adapters.items()
        if not callable(getattr(adapter, "send", None))
    )
    if missing_send:
        return _failure("adapters without callable send: " + ", ".join(missing_send))

    expected_runtime_names = {
        canonical_channel_name(channel)
        for channel in EXPECTED_CHANNELS
    }
    if set(DEFAULT_CAPABILITIES) != expected_runtime_names:
        return _failure("capability coverage does not match canonical aliases")
    if set(BINDING_BUILDERS) != expected_runtime_names:
        return _failure("binding coverage does not match canonical aliases")
    if len(expected_runtime_names) != len(EXPECTED_CHANNELS):
        return _failure("canonical channel aliases collapse distinct user channels")

    for channel in EXPECTED_CHANNELS:
        runtime_name = canonical_channel_name(channel)
        capabilities = get_capabilities(channel)
        if capabilities.channel != runtime_name:
            return _failure(
                f"capability identity drifted for {channel}: {capabilities.channel!r}"
            )
        if capabilities.plain_text is not True:
            return _failure(f"plain-text user delivery was removed for {channel}")
        if not callable(BINDING_BUILDERS[runtime_name]):
            return _failure(f"binding builder is not callable for {channel}")

    return (
        True,
        "multimessenger runtime lock passed "
        f"({len(EXPECTED_CHANNELS)} channels, {len(expected_dispatch)} non-Telegram adapters)",
    )


__all__ = [
    "EXPECTED_CHANNELS",
    "EXPECTED_CHANNEL_SPECS",
    "verify_multimessenger_runtime_contract",
]
