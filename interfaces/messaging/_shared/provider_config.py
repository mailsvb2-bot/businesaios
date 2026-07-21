"""Compatibility export for the canonical runtime provider configuration."""

from runtime.messaging.provider_config import (
    CANON_PROVIDER_TRANSPORT_CONFIG,
    ProviderConfig,
)

CANON_PROVIDER_CONFIG_COMPAT_FACADE = True

__all__ = [
    "CANON_PROVIDER_CONFIG_COMPAT_FACADE",
    "CANON_PROVIDER_TRANSPORT_CONFIG",
    "ProviderConfig",
]
