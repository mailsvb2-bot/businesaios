from __future__ import annotations

from interfaces.messaging_runtime.capabilities import DEFAULT_CAPABILITIES
from interfaces.messaging_runtime.channel_loader import BINDING_BUILDERS, load_bindings
from interfaces.messaging_runtime.config import build_default_runtime_config
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_types import ALL_CHANNELS
from runtime.messaging_ingress import SUPPORTED_MESSAGING_CHANNELS


def test_every_canonical_channel_has_config_capabilities_binding_and_ingress() -> None:
    expected = set(ALL_CHANNELS)

    assert set(build_default_runtime_config().channels) == expected
    assert set(DEFAULT_CAPABILITIES) == expected
    assert set(BINDING_BUILDERS) == expected
    assert set(SUPPORTED_MESSAGING_CHANNELS) == expected


def test_all_canonical_channel_bindings_can_be_constructed() -> None:
    bindings = load_bindings(enabled_channels=tuple(ALL_CHANNELS))
    assert tuple(binding.channel for binding in bindings) == tuple(ALL_CHANNELS)


def test_vk_and_max_legacy_names_normalize_to_full_channels() -> None:
    assert normalize_channel("vkontakte") == "vk"
    assert normalize_channel("vk_bot") == "vk"
    assert normalize_channel("max_messenger") == "max"
    assert normalize_channel("max_bot") == "max"
