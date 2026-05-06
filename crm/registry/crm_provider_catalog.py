from __future__ import annotations

"""Canonical CRM provider catalog.

This file is the single source of provider capability truth for CRM planning.
It deliberately imports provider-specific capability descriptors from the
provider layer instead of duplicating them inline. That avoids catalog drift and
prevents a subtle "second truth" from appearing next to the real adapters.
"""

from crm.crm_capability_contract import CrmCapabilityDescriptor
from crm.crm_provider_contract import CrmProvider
from crm.providers.hubspot.hubspot_capability_descriptor import (
    build_hubspot_capability_descriptor,
)
from crm.providers.pipedrive.pipedrive_capability_descriptor import (
    build_pipedrive_capability_descriptor,
)


def _build_provider(
    *,
    provider_key: str,
    display_name: str,
    default_rank: int,
    capability_descriptor: CrmCapabilityDescriptor,
) -> CrmProvider:
    if capability_descriptor.provider_key != provider_key:
        raise ValueError(
            f"Capability descriptor/provider mismatch: {capability_descriptor.provider_key} != {provider_key}"
        )
    return CrmProvider(
        provider_key=provider_key,
        display_name=display_name,
        default_rank=default_rank,
        capability_descriptor=capability_descriptor,
    )


def build_default_provider_catalog() -> tuple[CrmProvider, ...]:
    """Return enabled CRM providers ordered by default preference.

    The catalog is intentionally small and capability-aware. Selection logic can
    rank providers later, but the catalog itself should remain the canonical
    owner for which providers are available to the runtime.
    """

    return (
        _build_provider(
            provider_key='hubspot',
            display_name='HubSpot',
            default_rank=90,
            capability_descriptor=build_hubspot_capability_descriptor(),
        ),
        _build_provider(
            provider_key='pipedrive',
            display_name='Pipedrive',
            default_rank=80,
            capability_descriptor=build_pipedrive_capability_descriptor(),
        ),
    )
