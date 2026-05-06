from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.market_intelligence_compliance_store import (
    ComplianceProviderPolicy,
    PersistentMarketIntelligenceComplianceStore,
)
from contracts.platforms.market_intelligence_provider_catalog import resolve_provider_catalog_entry


CANON_MARKET_INTELLIGENCE_COMPLIANCE_BOUNDARY = True


@dataclass(frozen=True)
class SourceAccessPolicy:
    provider: str
    allow_access: bool
    robots_aware_mode: bool
    terms_aware_mode: bool
    retention_days: int
    minimize_personal_data: bool
    risk_level: str


@dataclass
class MarketIntelligenceComplianceBoundary:
    store: PersistentMarketIntelligenceComplianceStore = field(default_factory=PersistentMarketIntelligenceComplianceStore)

    def policy_for(self, provider: str) -> SourceAccessPolicy:
        entry = resolve_provider_catalog_entry(provider)
        stored = self.store.get_provider_policy(entry.provider)
        retention_days = stored.retention_days if stored and stored.retention_days is not None else (30 if entry.terms_sensitive else 90)
        robots_aware_mode = bool(stored.robots_aware_override) if stored and stored.robots_aware_override is not None else bool(entry.robots_sensitive)
        terms_aware_mode = bool(stored.terms_aware_override) if stored and stored.terms_aware_override is not None else bool(entry.terms_sensitive)
        allow_access = bool(stored.allow_access) if stored is not None else True
        minimize_personal_data = bool(stored.minimize_personal_data) if stored is not None else True
        risk_level = stored.risk_level if stored is not None else 'standard'
        return SourceAccessPolicy(
            provider=entry.provider,
            allow_access=allow_access,
            robots_aware_mode=robots_aware_mode,
            terms_aware_mode=terms_aware_mode,
            retention_days=int(retention_days),
            minimize_personal_data=minimize_personal_data,
            risk_level=risk_level,
        )

    def upsert_provider_policy(self, *, provider: str, allow_access: bool = True, risk_level: str = 'standard', retention_days: int | None = None, robots_aware_override: bool | None = None, terms_aware_override: bool | None = None, minimize_personal_data: bool = True) -> ComplianceProviderPolicy:
        policy = ComplianceProviderPolicy(
            provider=provider,
            allow_access=allow_access,
            risk_level=risk_level,
            retention_days=retention_days,
            robots_aware_override=robots_aware_override,
            terms_aware_override=terms_aware_override,
            minimize_personal_data=minimize_personal_data,
        )
        return self.store.upsert_provider_policy(policy)

    def enforce_pre_ingestion(self, *, provider: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        policy = self.policy_for(provider)
        if not policy.allow_access:
            raise ValueError(f'provider blocked by compliance policy: {provider}')
        cleaned = dict(payload or {})
        metadata = dict(cleaned.get('metadata') or {})
        for forbidden in ('email', 'phone', 'cookie', 'authorization', 'token'):
            metadata.pop(forbidden, None)
        cleaned['metadata'] = metadata
        cleaned['compliance'] = {
            'robots_aware_mode': policy.robots_aware_mode,
            'terms_aware_mode': policy.terms_aware_mode,
            'retention_days': policy.retention_days,
            'minimize_personal_data': policy.minimize_personal_data,
            'risk_level': policy.risk_level,
        }
        return cleaned
