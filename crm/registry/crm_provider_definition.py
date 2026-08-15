from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from string import ascii_lowercase, digits

from crm.crm_capability_contract import CrmCapabilityDescriptor
from crm.crm_connector_contract import CrmConnector
from crm.crm_provider_contract import CrmProvider


@dataclass(frozen=True)
class CrmProviderDefinition:
    """Single assembly-time definition for one CRM provider.

    Provider metadata and connector construction intentionally share one
    definition so adding a new adapter cannot silently update the planning
    catalog while forgetting the runtime connector registry, or vice versa.
    """

    provider_key: str
    display_name: str
    default_rank: int
    capability_factory: Callable[[], CrmCapabilityDescriptor]
    connector_factory: Callable[[], CrmConnector]
    enabled: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        key = self.provider_key.strip()
        allowed = set(ascii_lowercase + digits + '_-')
        if (
            not key
            or self.provider_key != key
            or key != key.casefold()
            or any(char not in allowed for char in key)
        ):
            raise ValueError(
                'CRM provider_key must be normalized lowercase ASCII using letters, digits, _ or -'
            )
        if not self.display_name.strip():
            raise ValueError('CRM display_name must not be blank')
        if isinstance(self.default_rank, bool) or not isinstance(self.default_rank, int):
            raise TypeError('CRM default_rank must be an integer')
        if not callable(self.capability_factory) or not callable(self.connector_factory):
            raise TypeError('CRM provider factories must be callable')

    def _build_capability(self) -> CrmCapabilityDescriptor:
        capability = self.capability_factory()
        if not isinstance(capability, CrmCapabilityDescriptor):
            raise TypeError('CRM capability_factory must return CrmCapabilityDescriptor')
        if capability.provider_key != self.provider_key:
            raise ValueError(
                f'Capability descriptor/provider mismatch: {capability.provider_key} != {self.provider_key}'
            )
        return capability

    def build_provider(self) -> CrmProvider:
        capability = self._build_capability()
        return CrmProvider(
            provider_key=self.provider_key,
            display_name=self.display_name,
            default_rank=self.default_rank,
            enabled=self.enabled,
            metadata=dict(self.metadata),
            capability_descriptor=capability,
        )

    def build_connector(self) -> CrmConnector:
        connector = self.connector_factory()
        required_methods = (
            'capabilities',
            'verify_connection',
            'list_pipelines',
            'upsert_pipeline',
            'upsert_contact',
            'upsert_deal',
            'append_note',
            'verify_write',
            'build_snapshot',
        )
        missing = tuple(
            name for name in required_methods
            if not callable(getattr(connector, name, None))
        )
        if missing:
            raise TypeError(
                'CRM connector_factory returned an incomplete connector; missing methods: '
                + ', '.join(missing)
            )
        connector_provider = getattr(connector, 'provider', None)
        if not isinstance(connector_provider, CrmProvider):
            raise TypeError('CRM connector_factory must expose a CrmProvider as provider')
        if connector_provider.provider_key != self.provider_key:
            raise ValueError(
                f'Connector/provider mismatch: {connector_provider.provider_key!r} != {self.provider_key!r}'
            )
        expected_capability = self._build_capability()
        if connector_provider.capability_descriptor != expected_capability:
            raise ValueError(
                f'Connector capability descriptor mismatch for provider {self.provider_key}'
            )
        return connector


def merge_provider_definitions(
    base: tuple[CrmProviderDefinition, ...],
    extra: tuple[CrmProviderDefinition, ...] = (),
) -> tuple[CrmProviderDefinition, ...]:
    """Merge explicit extensions while rejecting duplicate provider keys."""

    merged: list[CrmProviderDefinition] = []
    seen: set[str] = set()
    for definition in (*base, *extra):
        if definition.provider_key in seen:
            raise ValueError(f'Duplicate CRM provider definition: {definition.provider_key}')
        seen.add(definition.provider_key)
        merged.append(definition)
    return tuple(merged)


__all__ = ['CrmProviderDefinition', 'merge_provider_definitions']
