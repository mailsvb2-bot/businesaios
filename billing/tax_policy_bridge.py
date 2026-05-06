from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from runtime.monetization import MonetizationService, TaxBreakdown, TaxContext


CANON_BILLING_TAX_POLICY_BRIDGE = True


@dataclass(frozen=True)
class BillingTaxCountryPolicy:
    country_code: str
    require_tax_id_for_business: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        normalized_country = str(self.country_code or '').strip().upper()
        if not normalized_country:
            raise ValueError('country_code is required')

    def normalized_copy(self) -> 'BillingTaxCountryPolicy':
        self.validate()
        return BillingTaxCountryPolicy(
            country_code=str(self.country_code).strip().upper(),
            require_tax_id_for_business=bool(self.require_tax_id_for_business),
            metadata=dict(self.metadata),
        )


class BillingTaxPolicyRegistry:
    def __init__(self, policies: tuple[BillingTaxCountryPolicy, ...] | None = None) -> None:
        self._policies: dict[str, BillingTaxCountryPolicy] = {}
        for policy in policies or ():
            self.register(policy)

    def register(self, policy: BillingTaxCountryPolicy) -> BillingTaxCountryPolicy:
        normalized = policy.normalized_copy()
        key = normalized.country_code
        existing = self._policies.get(key)
        if existing is not None and existing != normalized:
            raise ValueError(f'tax policy for country {key} already registered with different configuration')
        self._policies[key] = normalized
        return normalized

    def get(self, country_code: str) -> BillingTaxCountryPolicy:
        key = str(country_code or '').strip().upper()
        if not key:
            raise ValueError('country_code is required')
        try:
            return self._policies[key]
        except KeyError as exc:
            raise LookupError(f'unsupported tax country: {country_code}') from exc


@dataclass(frozen=True)
class BillingTaxPolicyBridge:
    """Thin bridge to the canonical runtime monetization tax resolver.

    The bridge stays intentionally thin, but it may fail-closed against a
    registry of allowed tax regimes so billing cannot silently invent country
    handling outside the canonical monetization surface.
    """

    registry: BillingTaxPolicyRegistry | None = None

    def resolve(self, *, service: MonetizationService, subtotal_minor: int, context: TaxContext) -> TaxBreakdown:
        normalized_subtotal = int(subtotal_minor)
        if normalized_subtotal < 0:
            raise ValueError('subtotal_minor must be >= 0')
        normalized_country = str(context.country_code or '').strip().upper()
        if not normalized_country:
            raise ValueError('context.country_code is required')
        normalized_tax_id = None if context.tax_id is None else str(context.tax_id).strip()
        if normalized_tax_id == '':
            normalized_tax_id = None
        normalized_context = TaxContext(
            country_code=normalized_country,
            is_business_customer=bool(context.is_business_customer),
            tax_id=normalized_tax_id,
        )
        if self.registry is not None:
            policy = self.registry.get(normalized_country)
            if policy.require_tax_id_for_business and normalized_context.is_business_customer and not normalized_context.tax_id:
                raise ValueError(f'business customer tax_id is required for country {normalized_country}')
        return service.resolve_tax(subtotal_minor=normalized_subtotal, context=normalized_context)


__all__ = [
    'BillingTaxCountryPolicy',
    'BillingTaxPolicyBridge',
    'BillingTaxPolicyRegistry',
    'CANON_BILLING_TAX_POLICY_BRIDGE',
]
