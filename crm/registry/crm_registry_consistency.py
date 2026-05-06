from __future__ import annotations

from crm.registry.crm_connector_registry import CrmConnectorRegistry
from crm.registry.crm_provider_registry import CrmProviderRegistry


def assert_crm_registry_consistency(
    provider_registry: CrmProviderRegistry,
    connector_registry: CrmConnectorRegistry,
) -> None:
    """Fail closed if provider metadata and concrete connectors drift apart.

    The provider registry is the single source of truth for capability metadata.
    The connector registry owns concrete runtime adapters. They must expose the
    same enabled provider keys; otherwise the runtime can silently plan for a
    provider it cannot execute or execute a provider DecisionCore cannot see.
    """

    provider_keys = set(provider_registry.keys())
    connector_keys = set(connector_registry.keys())

    missing_connectors = provider_keys - connector_keys
    unexpected_connectors = connector_keys - provider_keys
    if missing_connectors or unexpected_connectors:
        problems: list[str] = []
        if missing_connectors:
            problems.append(
                'missing connectors for providers: ' + ', '.join(sorted(missing_connectors))
            )
        if unexpected_connectors:
            problems.append(
                'unexpected connectors without provider metadata: '
                + ', '.join(sorted(unexpected_connectors))
            )
        raise ValueError('CRM registry mismatch: ' + '; '.join(problems))
