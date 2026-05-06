from application.business_autonomy.provider_messaging_binding import ProviderMessagingBinding
from application.business_autonomy.provider_messaging_metadata import messaging_binding_to_metadata


def test_messaging_binding_to_metadata_is_canonical_and_lossless():
    binding = ProviderMessagingBinding(
        provider_key="telegram_bot",
        channel="telegram",
        required_capabilities={"plain_text": True, "buttons": True},
        live_probe_supported=True,
    )
    out = messaging_binding_to_metadata(binding)
    assert out == {
        "channel": "telegram",
        "required_capabilities": {"plain_text": True, "buttons": True},
        "live_probe_supported": True,
    }


def test_messaging_binding_to_metadata_handles_none():
    assert messaging_binding_to_metadata(None) == {}
