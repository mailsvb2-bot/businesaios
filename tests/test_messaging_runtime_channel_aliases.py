from interfaces.messaging_runtime.capabilities import get_capabilities
from interfaces.messaging_runtime.channel_loader import load_bindings


def test_channel_loader_accepts_legacy_aliases_and_returns_canonical_channels():
    bindings = load_bindings(
        enabled_channels=("telegram", "webchat", "api_gateway")
    )
    assert tuple(binding.channel for binding in bindings) == (
        "telegram",
        "web_chat",
        "api",
    )


def test_capabilities_resolve_to_runtime_canonical_names():
    assert get_capabilities("webchat").channel == "web_chat"
    assert get_capabilities("api_gateway").channel == "api"
