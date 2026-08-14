from __future__ import annotations

"""Canonical CRM provider catalog assembled from provider definitions."""

from crm.crm_provider_contract import CrmProvider
from crm.registry.crm_provider_definition import (
    CrmProviderDefinition,
    merge_provider_definitions,
)
from crm.registry.crm_provider_definitions import build_default_crm_provider_definitions


def build_default_provider_catalog(
    *,
    extra_definitions: tuple[CrmProviderDefinition, ...] = (),
) -> tuple[CrmProvider, ...]:
    """Return built-in providers plus explicitly supplied extensions.

    The definition manifest is the single source for both planning metadata and
    runtime connector construction. External composition roots can add a CRM by
    supplying one definition; no core decision/runtime module needs modification.
    """

    definitions = merge_provider_definitions(
        build_default_crm_provider_definitions(),
        extra_definitions,
    )
    return tuple(definition.build_provider() for definition in definitions)


__all__ = ['build_default_provider_catalog']
