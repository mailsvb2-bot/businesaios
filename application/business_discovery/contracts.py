from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

CANON_BUSINESS_DISCOVERY_CONTRACT = True


@dataclass(frozen=True)
class DiscoveryFieldSpec:
    key: str
    fact_type: str
    field_path: str
    domain: str
    legacy_sources: tuple[str, ...] = ()


_FIELD_SPECS = (
    DiscoveryFieldSpec(
        key="identity.display_name",
        fact_type="business.discovery.identity.display_name",
        field_path="business.profile.display_name",
        domain="identity",
    ),
    DiscoveryFieldSpec(
        key="identity.website",
        fact_type="business.discovery.identity.website",
        field_path="business.profile.website",
        domain="identity",
    ),
    DiscoveryFieldSpec(
        key="identity.industry",
        fact_type="business.discovery.identity.industry",
        field_path="business.profile.industry",
        domain="identity",
    ),
    DiscoveryFieldSpec(
        key="identity.business_model",
        fact_type="business.discovery.identity.business_model",
        field_path="business.profile.business_model",
        domain="identity",
    ),
    DiscoveryFieldSpec(
        key="market.city",
        fact_type="business.discovery.market.city",
        field_path="business.market.city",
        domain="market",
    ),
    DiscoveryFieldSpec(
        key="market.region",
        fact_type="business.discovery.market.region",
        field_path="business.market.region",
        domain="market",
        legacy_sources=("core.autopilot.onboarding.Diagnostics.region",),
    ),
    DiscoveryFieldSpec(
        key="offer.summary",
        fact_type="business.discovery.offer.summary",
        field_path="business.offer.summary",
        domain="offer",
        legacy_sources=("core.autopilot.onboarding.Diagnostics.what",),
    ),
    DiscoveryFieldSpec(
        key="economics.average_check",
        fact_type="business.discovery.economics.average_check",
        field_path="business.economics.average_check",
        domain="economics",
        legacy_sources=(
            "core.autopilot.onboarding.Diagnostics.avg_check_minor",
            "core.autopilot.onboarding.Diagnostics.currency",
        ),
    ),
    DiscoveryFieldSpec(
        key="economics.margin_pct",
        fact_type="business.discovery.economics.margin_pct",
        field_path="business.economics.margin_pct",
        domain="economics",
        legacy_sources=("core.autopilot.onboarding.Diagnostics.margin_pct",),
    ),
    DiscoveryFieldSpec(
        key="sales.has_clients",
        fact_type="business.discovery.sales.has_clients",
        field_path="business.sales.has_clients",
        domain="sales",
        legacy_sources=("core.autopilot.onboarding.Diagnostics.has_clients",),
    ),
    DiscoveryFieldSpec(
        key="acquisition.test_budget_7d",
        fact_type="business.discovery.acquisition.test_budget_7d",
        field_path="business.acquisition.test_budget_7d",
        domain="acquisition",
        legacy_sources=(
            "core.autopilot.onboarding.Diagnostics.budget_minor_7d",
            "core.autopilot.onboarding.Diagnostics.budget_currency",
        ),
    ),
)

DISCOVERY_FIELDS: Final = MappingProxyType({item.key: item for item in _FIELD_SPECS})


def discovery_field_spec(key: str) -> DiscoveryFieldSpec:
    normalized = str(key or "").strip()
    try:
        return DISCOVERY_FIELDS[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported business discovery field: {normalized or '<empty>'}") from exc


__all__ = [
    "CANON_BUSINESS_DISCOVERY_CONTRACT",
    "DISCOVERY_FIELDS",
    "DiscoveryFieldSpec",
    "discovery_field_spec",
]
