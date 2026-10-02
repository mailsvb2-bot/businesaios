from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

CANON_BUSINESS_DISCOVERY_CONTRACT = True


class DiscoveryValueKind(StrEnum):
    TEXT = "text"
    MONEY_MINOR = "money_minor"
    PERCENTAGE = "percentage"
    CLIENT_PRESENCE = "client_presence"


@dataclass(frozen=True)
class DiscoveryFieldSpec:
    key: str
    fact_type: str
    field_path: str
    domain: str
    value_kind: DiscoveryValueKind = DiscoveryValueKind.TEXT
    allowed_values: tuple[str, ...] = ()
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
        value_kind=DiscoveryValueKind.MONEY_MINOR,
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
        value_kind=DiscoveryValueKind.PERCENTAGE,
        legacy_sources=("core.autopilot.onboarding.Diagnostics.margin_pct",),
    ),
    DiscoveryFieldSpec(
        key="sales.has_clients",
        fact_type="business.discovery.sales.has_clients",
        field_path="business.sales.has_clients",
        domain="sales",
        value_kind=DiscoveryValueKind.CLIENT_PRESENCE,
        allowed_values=("yes", "no", "some"),
        legacy_sources=("core.autopilot.onboarding.Diagnostics.has_clients",),
    ),
    DiscoveryFieldSpec(
        key="acquisition.test_budget_7d",
        fact_type="business.discovery.acquisition.test_budget_7d",
        field_path="business.acquisition.test_budget_7d",
        domain="acquisition",
        value_kind=DiscoveryValueKind.MONEY_MINOR,
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


def normalize_discovery_value(spec: DiscoveryFieldSpec, value: Any) -> Any:
    kind = DiscoveryValueKind(spec.value_kind)
    if kind is DiscoveryValueKind.TEXT:
        if not isinstance(value, str):
            raise ValueError(f"{spec.key} must be text")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{spec.key} must not be empty")
        return normalized

    if kind is DiscoveryValueKind.MONEY_MINOR:
        if not isinstance(value, Mapping):
            raise ValueError(f"{spec.key} must be a money object")
        if set(value) != {"amount_minor", "currency"}:
            raise ValueError(
                f"{spec.key} money object must contain only amount_minor and currency"
            )
        amount = value.get("amount_minor")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError(f"{spec.key}.amount_minor must be a non-negative integer")
        currency_raw = value.get("currency")
        if not isinstance(currency_raw, str):
            raise ValueError(f"{spec.key}.currency must be a three-letter currency code")
        currency = currency_raw.strip().upper()
        if len(currency) != 3 or not currency.isalpha() or not currency.isascii():
            raise ValueError(f"{spec.key}.currency must be a three-letter currency code")
        return {"amount_minor": amount, "currency": currency}

    if kind is DiscoveryValueKind.PERCENTAGE:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{spec.key} must be a number from 0 to 100")
        normalized = float(value)
        if not math.isfinite(normalized) or normalized < 0.0 or normalized > 100.0:
            raise ValueError(f"{spec.key} must be a number from 0 to 100")
        return value if isinstance(value, int) else normalized

    if kind is DiscoveryValueKind.CLIENT_PRESENCE:
        if not isinstance(value, str):
            raise ValueError(f"{spec.key} must be one of {', '.join(spec.allowed_values)}")
        normalized = value.strip().lower()
        if normalized not in spec.allowed_values:
            raise ValueError(f"{spec.key} must be one of {', '.join(spec.allowed_values)}")
        return normalized

    raise ValueError(f"unsupported business discovery value kind: {kind}")


__all__ = [
    "CANON_BUSINESS_DISCOVERY_CONTRACT",
    "DISCOVERY_FIELDS",
    "DiscoveryFieldSpec",
    "DiscoveryValueKind",
    "discovery_field_spec",
    "normalize_discovery_value",
]
