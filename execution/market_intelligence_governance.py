from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.market_intelligence_approval_gate import MarketIntelligenceApprovalGate
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_provider_matrix import MarketIntelligenceProviderMatrix
from execution.market_intelligence_risk_policy import MarketIntelligenceRiskPolicy
from execution.market_intelligence_tenancy_scope import MarketIntelligenceTenancyScope


CANON_MARKET_INTELLIGENCE_GOVERNANCE = True


@dataclass(frozen=True)
class MarketIntelligenceGovernance:
    default_scope_max_limit: int = 100
    max_query_length: int = 512
    max_subject_url_length: int = 2048
    max_metadata_items: int = 32
    max_metadata_value_length: int = 1024
    restricted_providers: tuple[str, ...] = field(default_factory=tuple)
    allowed_metadata_keys: tuple[str, ...] = field(default_factory=lambda: (
        'category', 'country', 'currency', 'domain', 'keyword', 'language', 'page', 'segment', 'sort', 'tag', 'topic'
    ))
    forbidden_metadata_keys: tuple[str, ...] = field(default_factory=lambda: (
        'authorization', 'cookie', 'password', 'secret', 'token', 'x-api-key'
    ))
    risk_policy: MarketIntelligenceRiskPolicy = field(default_factory=MarketIntelligenceRiskPolicy)
    approval_gate: MarketIntelligenceApprovalGate = field(default_factory=MarketIntelligenceApprovalGate)
    provider_matrix: MarketIntelligenceProviderMatrix = field(default_factory=MarketIntelligenceProviderMatrix)

    def enforce(
        self,
        request: MarketIntelligenceIngestionRequest,
        *,
        tenancy_scope: MarketIntelligenceTenancyScope | None = None,
    ) -> tuple[MarketIntelligenceIngestionRequest, dict[str, object]]:
        scoped_request = request
        if tenancy_scope is not None:
            scoped_request = tenancy_scope.apply(request)
        elif int(request.limit) > int(self.default_scope_max_limit):
            scoped_request = MarketIntelligenceIngestionRequest(
                tenant_id=request.tenant_id,
                source_family=request.source_family,
                provider=request.provider,
                action_type=request.action_type,
                query=request.query,
                subject_url=request.subject_url,
                account_ref=request.account_ref,
                region=request.region,
                locale=request.locale,
                limit=self.default_scope_max_limit,
                dry_run=bool(request.dry_run),
                metadata=dict(request.metadata or {}),
            )
        self.provider_matrix.validate(
            source_family=scoped_request.source_family,
            provider=scoped_request.provider,
            action_type=scoped_request.action_type,
        )
        if scoped_request.provider in set(self.restricted_providers):
            raise ValueError(f'provider restricted by governance: {scoped_request.provider}')
        if scoped_request.query and len(scoped_request.query) > int(self.max_query_length):
            raise ValueError('query exceeds governance max length')
        if scoped_request.subject_url and len(scoped_request.subject_url) > int(self.max_subject_url_length):
            raise ValueError('subject_url exceeds governance max length')
        self._validate_metadata(scoped_request.metadata)
        risk = self.risk_policy.assess(scoped_request)
        self.approval_gate.ensure_allowed(tenant_id=scoped_request.tenant_id, risk=risk)
        return scoped_request, risk

    def _validate_metadata(self, metadata: dict[str, Any] | Any) -> None:
        normalized = dict(metadata or {})
        if len(normalized) > int(self.max_metadata_items):
            raise ValueError('metadata exceeds governance max items')
        allowed = set(self.allowed_metadata_keys)
        forbidden = {item.lower() for item in self.forbidden_metadata_keys}
        for key, value in normalized.items():
            key_text = str(key or '').strip()
            if not key_text:
                raise ValueError('metadata contains empty key')
            if key_text.lower() in forbidden:
                raise ValueError(f'metadata key forbidden by governance: {key_text}')
            if allowed and key_text not in allowed:
                raise ValueError(f'metadata key not allowed by governance: {key_text}')
            value_text = str(value or '').strip()
            if len(value_text) > int(self.max_metadata_value_length):
                raise ValueError(f'metadata value too long for key: {key_text}')


__all__ = ['CANON_MARKET_INTELLIGENCE_GOVERNANCE', 'MarketIntelligenceGovernance']
