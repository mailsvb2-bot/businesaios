from interfaces.messaging_runtime.capabilities import get_capabilities
from interfaces.messaging_runtime.channel_loader import load_bindings


def test_channel_loader_accepts_canonical_aliases_and_telegram():
    bindings = load_bindings(enabled_channels=("telegram", "web_chat", "api"))
    assert tuple(binding.channel for binding in bindings) == ("telegram", "webchat", "api_gateway")


def test_capabilities_resolve_aliases():
    assert get_capabilities("web_chat").channel == "webchat"
    assert get_capabilities("api").channel == "api_gateway"
