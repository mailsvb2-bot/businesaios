import pytest

from interfaces.messaging_runtime.registry import ChannelRegistry


def test_registry_rejects_duplicate_channel_registration():
    registry = ChannelRegistry()
    registry.register("sms", object())
    with pytest.raises(RuntimeError):
        registry.register("sms", object())
