from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from application.business_autonomy.provider_messaging_binding import (
    describe_provider_messaging_binding,
)


EXPECTED_MESSAGING_CHANNELS = {
    'email',
    'sms',
    'telegram',
    'web_chat',
    'whatsapp',
}


def test_provider_catalog_is_multichannel_not_telegram_only() -> None:
    bindings = tuple(
        binding
        for provider in provider_map().values()
        if (binding := describe_provider_messaging_binding(provider)) is not None
    )
    channels = {binding.channel for binding in bindings}

    assert EXPECTED_MESSAGING_CHANNELS <= channels
    assert len(channels) > 1


def test_each_catalogued_messaging_provider_has_explicit_capabilities() -> None:
    bindings = tuple(
        binding
        for provider in provider_map().values()
        if (binding := describe_provider_messaging_binding(provider)) is not None
    )

    assert bindings
    for binding in bindings:
        assert binding.provider_key
        assert binding.channel
        assert 'plain_text' in binding.required_capabilities
        assert isinstance(binding.live_probe_supported, bool)
