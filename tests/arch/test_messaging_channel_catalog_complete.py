from __future__ import annotations

from typing import get_args

from contracts.messaging_channels import ALL_CHANNELS as CONTRACT_CHANNELS
from core.growth.strategy.contracts import GROWTH_MESSAGING_CHANNELS, Channel
from interfaces.messaging_runtime.capabilities import DEFAULT_CAPABILITIES
from interfaces.messaging_runtime.channel_loader import BINDING_BUILDERS, load_bindings
from interfaces.messaging_runtime.config import build_default_runtime_config
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_types import ALL_CHANNELS as RUNTIME_CHANNELS
from runtime.messaging_ingress import SUPPORTED_MESSAGING_CHANNELS


def test_runtime_and_growth_consume_one_canonical_channel_catalog() -> None:
    assert RUNTIME_CHANNELS is CONTRACT_CHANNELS
    assert tuple(GROWTH_MESSAGING_CHANNELS[:-1]) == CONTRACT_CHANNELS
    assert GROWTH_MESSAGING_CHANNELS[-1] == "push"
    assert set(CONTRACT_CHANNELS).issubset(set(get_args(Channel)))


def test_every_canonical_channel_has_config_capabilities_binding_and_ingress() -> None:
    expected = set(CONTRACT_CHANNELS)

    assert set(build_default_runtime_config().channels) == expected
    assert set(DEFAULT_CAPABILITIES) == expected
    assert set(BINDING_BUILDERS) == expected
    assert set(SUPPORTED_MESSAGING_CHANNELS) == expected


def test_all_canonical_channel_bindings_can_be_constructed() -> None:
    bindings = load_bindings(enabled_channels=tuple(CONTRACT_CHANNELS))
    assert tuple(binding.channel for binding in bindings) == tuple(CONTRACT_CHANNELS)


def test_vk_and_max_legacy_names_normalize_to_full_channels() -> None:
    assert normalize_channel("vkontakte") == "vk"
    assert normalize_channel("vk_bot") == "vk"
    assert normalize_channel("max_messenger") == "max"
    assert normalize_channel("max_bot") == "max"
