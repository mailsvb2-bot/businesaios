from __future__ import annotations

import sys

import interfaces.messaging._shared.outbound_sender as compat_sender
import interfaces.messaging._shared.provider_config as compat_config
import runtime._internal.effects_clients.provider_outbound_sender as sender
import runtime.execution.provider_outbound_sender as public_sender
from runtime.messaging.provider_config import ProviderConfig


def test_contract_and_compatibility_facades_preserve_identity() -> None:
    assert compat_config.ProviderConfig is ProviderConfig
    assert compat_config.CANON_PROVIDER_TRANSPORT_CONFIG is True
    assert compat_config.CANON_PROVIDER_CONFIG_COMPAT_FACADE is True
    assert public_sender is sender
    assert compat_sender is sender
    assert sys.modules["runtime.execution.provider_outbound_sender"] is sender
    assert sys.modules["interfaces.messaging._shared.outbound_sender"] is sender
    assert sender.CANON_SEALED_PROVIDER_OUTBOUND_TRANSPORT is True
    assert sender.CANON_PROVIDER_OUTBOUND_TRANSPORT_FACADE is True


