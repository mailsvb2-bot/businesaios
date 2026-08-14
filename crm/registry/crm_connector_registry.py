from __future__ import annotations

from dataclasses import dataclass

from crm.crm_connector_contract import CrmConnector
from crm.registry.crm_provider_definition import (
    CrmProviderDefinition,
    merge_provider_definitions,
)
from crm.registry.crm_provider_definitions import build_default_crm_provider_definitions


@dataclass
class CrmConnectorRegistry:
    """Canonical runtime registry for concrete CRM connector instances."""

    connectors: dict[str, CrmConnector]

    @classmethod
    def build_default(
        cls,
        *,
        extra_definitions: tuple[CrmProviderDefinition, ...] = (),
    ) -> 'CrmConnectorRegistry':
        definitions = merge_provider_definitions(
            build_default_crm_provider_definitions(),
            extra_definitions,
        )
        return cls.from_definitions(definitions)

    @classmethod
    def from_definitions(
        cls,
        definitions: tuple[CrmProviderDefinition, ...],
    ) -> 'CrmConnectorRegistry':
        connectors: dict[str, CrmConnector] = {}
        seen: set[str] = set()
        for definition in definitions:
            if definition.provider_key in seen:
                raise ValueError(
                    f'Duplicate CRM connector definition: {definition.provider_key}'
                )
            seen.add(definition.provider_key)
            if not definition.enabled:
                continue
            connectors[definition.provider_key] = definition.build_connector()
        return cls(connectors=connectors)

    def get(self, provider_key: str) -> CrmConnector:
        try:
            return self.connectors[provider_key]
        except KeyError as exc:
            raise LookupError(f'Unknown CRM connector: {provider_key}') from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.connectors))


__all__ = ['CrmConnectorRegistry']
