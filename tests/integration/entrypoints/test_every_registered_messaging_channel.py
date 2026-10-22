"""Provider-derived mandatory coverage: never silently omit a messaging ingress.

These checks establish catalog-to-canonical-contract coverage, not live delivery.
"""
from __future__ import annotations

import pytest

from application.business_autonomy.provider_catalog import (
    MESSAGING_CHANNEL_PROVIDER_KEYS,
    provider_map,
)
from application.business_autonomy.provider_messaging_binding import describe_provider_messaging_binding


@pytest.mark.parametrize(
    ("channel", "provider_key"),
    sorted(MESSAGING_CHANNEL_PROVIDER_KEYS.items()),
    ids=lambda value: str(value),
)
def test_every_registered_messaging_channel_has_canonical_provider_binding(channel, provider_key):
    assert channel
    assert provider_key
    providers = provider_map()
    assert provider_key in providers, f"{channel}: missing canonical provider {provider_key}"
    definition = providers[provider_key]
    assert definition.provider_key == provider_key
    assert definition.connector_id
    assert definition.adapter_key
    binding = describe_provider_messaging_binding(definition)
    assert binding is not None, f"{channel}: missing messaging capability binding"


def test_messaging_channel_registry_has_no_duplicate_provider_owners():
    mapping = MESSAGING_CHANNEL_PROVIDER_KEYS
    assert mapping
    assert len(mapping) == len(set(mapping))
    assert len(mapping.values()) == len(set(mapping.values())), "two channels share one provider identity"
