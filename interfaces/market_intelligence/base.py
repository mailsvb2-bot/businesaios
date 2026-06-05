from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from collections.abc import Mapping

from contracts.platforms.market_intelligence_contract import (
    MarketIntelligenceEnvelope,
    MarketIntelligenceRecord,
    MarketIntelligenceTarget,
)
from interfaces.common.auth_session import AuthSession
from interfaces.common.base_connector import BaseConnector
from interfaces.common.connector_capabilities import ConnectorCapabilities
from interfaces.common.connector_health import ConnectorHealth
from interfaces.common.connector_maturity import ConnectorMaturity
from interfaces.common.connector_result import ConnectorResult

CANON_MARKET_INTELLIGENCE_BASE = True

_OPERATION_MAP = {
    "marketplace": ["sync_catalog", "fetch_listing", "fetch_reviews", "fetch_pricing", "fetch_images"],
    "ads_library": ["sync_ads", "fetch_creative", "fetch_landing_url", "fetch_engagement"],
    "competitor_analytics": ["sync_analytics", "fetch_keywords", "fetch_top_pages", "fetch_backlinks", "fetch_ads"],
    "search_intelligence": ["sync_search_results", "fetch_keywords", "fetch_trends", "fetch_related_queries"],
    "professional_network": ["sync_discussions", "fetch_posts", "fetch_questions", "fetch_objections"],
    "content_platform": ["sync_publications", "fetch_articles", "fetch_docs", "fetch_repos"],
    "app_store": ["sync_apps", "fetch_reviews", "fetch_features", "fetch_pricing"],
    "review_platform": ["sync_reviews", "fetch_ratings", "fetch_objections", "fetch_use_cases"],
    "landing_intelligence": ["crawl_landing_pages", "fetch_pricing", "fetch_offers", "fetch_cta_structure"],
    "video_platform": ["sync_videos", "fetch_transcript", "fetch_metadata", "fetch_comments"],
    "ads_spy": ["sync_ads_spy", "fetch_creatives", "fetch_cta", "fetch_landing_url"],
    "newsletter_intelligence": ["sync_newsletters", "fetch_editions", "fetch_offers", "fetch_cta"],
}

_EVIDENCE_FIELDS = (
    'source_family',
    'provider',
    'operation',
    'query',
    'subject_url',
    'records',
    'summary',
)


@runtime_checkable
class ProviderClientProtocol(Protocol):
    def execute_market_intelligence(
        self,
        *,
        provider: str,
        source_family: str,
        operation: str,
        payload: Mapping[str, Any],
        dry_run: bool,
    ) -> Mapping[str, Any]:
        ...


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _safe_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _safe_text(value: object | None) -> str | None:
    text = str(value or '').strip()
    return text or None


@dataclass
class MarketIntelConnectorBase(BaseConnector):
    connector_name: str = 'market_intelligence'
    connector_id: str = 'market_intelligence'
    provider_key: str = 'generic'
    source_family: str = 'marketplace'
    version: str = 'v1'
    provider_client: ProviderClientProtocol | None = None
    support_verify: bool = True
    support_dry_run: bool = True
    support_idempotency: bool = True
    session: AuthSession = field(default_factory=AuthSession)

    def __post_init__(self) -> None:
        if self.provider_client is None:
            from interfaces.market_intelligence.provider_factory import build_default_provider_client

            self.provider_client = build_default_provider_client(self.provider_key)
        if self.provider_client is not None and not bool(self.session.configured):
            self.session = AuthSession(
                account_id=self.provider_key,
                configured=True,
                scopes=(f'market_intelligence:{self.source_family}', f'provider:{self.provider_key}'),
                metadata={'provider': self.provider_key, 'source_family': self.source_family, 'version': self.version},
            )

    def execute(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        if dry_run:
            normalized_payload = _safe_dict(payload)
            target = self._build_target(normalized_payload)
            envelope = self._build_dry_run_envelope(operation=str(operation).strip(), target=target, payload=normalized_payload)
            return self._to_result(ok=True, code='dry_run', message='dry-run preview generated', envelope=envelope, dry_run=True)
        return super().execute(operation, payload, idempotency_key=idempotency_key, dry_run=dry_run)

    def connector_maturity(self) -> ConnectorMaturity:
        return ConnectorMaturity.CAPABILITY_SHELL if self.provider_client is None else ConnectorMaturity.REAL

    def connector_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            read=True,
            write=False,
            verify=bool(self.support_verify),
            dry_run=bool(self.support_dry_run),
            idempotent=bool(self.support_idempotency),
            reversible=False,
            requires_human_approval=False,
            evidence_fields=_EVIDENCE_FIELDS,
            metadata={
                'provider': self.provider_key,
                'source_family': self.source_family,
                'version': self.version,
                'maturity': self.connector_maturity().value,
                'operation_names': list(_OPERATION_MAP[self.source_family]),
            },
        )

    def health(self) -> ConnectorHealth:
        healthy = bool(self.provider_client is not None) or bool(self.support_dry_run)
        reason = 'provider_configured' if self.provider_client is not None else 'dry_run_only'
        return ConnectorHealth(
            connector_name=self.connector_name,
            healthy=healthy,
            reason=reason,
            metadata={
                'connector_id': self.connector_id,
                'provider': self.provider_key,
                'source_family': self.source_family,
                'version': self.version,
                'mode': self.mode,
                'operations': list(_OPERATION_MAP[self.source_family]),
            },
        )

    def _execute_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> ConnectorResult:
        del idempotency_key, dry_run
        if operation not in set(_OPERATION_MAP[self.source_family]):
            return ConnectorResult(ok=False, code='unsupported_operation', message=f'unsupported operation: {operation}')
        normalized_payload = _safe_dict(payload)
        target = self._build_target(normalized_payload)
        if self.provider_client is None:
            return ConnectorResult(
                ok=False,
                code='not_configured',
                message='provider_client is not configured',
                payload={
                    'connector_id': self.connector_id,
                    'provider': self.provider_key,
                    'source_family': self.source_family,
                    'operation': operation,
                },
            )
        try:
            raw = self.provider_client.execute_market_intelligence(
                provider=self.provider_key,
                source_family=self.source_family,
                operation=operation,
                payload=normalized_payload,
                dry_run=False,
            )
        except TimeoutError as exc:
            return ConnectorResult(ok=False, code='temporary_unavailable', message=str(exc) or 'provider timeout')
        except Exception as exc:  # fail-closed by default
            return ConnectorResult(ok=False, code='provider_error', message=str(exc) or exc.__class__.__name__)
        envelope = self._build_envelope_from_provider(operation=operation, target=target, payload=normalized_payload, raw=raw)
        return self._to_result(ok=True, code='synced', message='market intelligence synchronized', envelope=envelope, dry_run=False)

    def _verify_configured(
        self,
        operation: str,
        payload: dict[str, Any],
        result_payload: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        normalized_payload = _safe_dict(payload)
        normalized_result = _safe_dict(result_payload)
        required = ('connector_id', 'provider', 'source_family', 'operation', 'records')
        missing = [item for item in required if item not in normalized_result]
        if missing:
            return ConnectorResult(
                ok=False,
                code='verification_missing_fields',
                message='missing verification fields',
                payload={'missing_fields': missing, 'operation': operation},
            )
        if str(normalized_result.get('connector_id') or '').strip() != self.connector_id:
            return ConnectorResult(ok=False, code='verification_connector_mismatch', message='connector_id mismatch')
        if str(normalized_result.get('provider') or '').strip() != self.provider_key:
            return ConnectorResult(ok=False, code='verification_provider_mismatch', message='provider mismatch')
        if str(normalized_result.get('source_family') or '').strip() != self.source_family:
            return ConnectorResult(ok=False, code='verification_family_mismatch', message='source family mismatch')
        if str(normalized_result.get('operation') or '').strip() != str(operation).strip():
            return ConnectorResult(ok=False, code='verification_operation_mismatch', message='operation mismatch')
        records = _safe_list(normalized_result.get('records'))
        if records and not any(str(item.get('external_id') or '').strip() for item in records):
            return ConnectorResult(ok=False, code='verification_record_identity_missing', message='records missing external_id')
        requested_query = _safe_text(normalized_payload.get('query'))
        requested_subject = _safe_text(normalized_payload.get('subject_url') or normalized_payload.get('url'))
        envelope_target = normalized_result.get('target') if isinstance(normalized_result.get('target'), Mapping) else {}
        target_query = _safe_text(envelope_target.get('query'))
        target_subject = _safe_text(envelope_target.get('subject_url'))
        if requested_query and target_query and requested_query != target_query:
            return ConnectorResult(ok=False, code='verification_query_mismatch', message='query mismatch')
        if requested_subject and target_subject and requested_subject != target_subject:
            return ConnectorResult(ok=False, code='verification_subject_mismatch', message='subject_url mismatch')
        return ConnectorResult(
            ok=True,
            code='verified',
            message='market intelligence payload verified',
            payload={'records_count': len(records)},
        )

    def _build_target(self, payload: Mapping[str, Any]) -> MarketIntelligenceTarget:
        return MarketIntelligenceTarget(
            source_family=self.source_family,
            provider=self.provider_key,
            tenant_id=str(payload.get('tenant_id') or payload.get('tenant') or 'default').strip() or 'default',
            query=_safe_text(payload.get('query')),
            subject_url=_safe_text(payload.get('subject_url') or payload.get('url')),
            account_ref=_safe_text(payload.get('account_ref') or payload.get('handle')),
            region=_safe_text(payload.get('region')),
            locale=_safe_text(payload.get('locale')),
            limit=int(payload.get('limit') or 25),
            metadata=_safe_dict(payload.get('metadata')),
        )

    def _build_dry_run_envelope(
        self,
        *,
        operation: str,
        target: MarketIntelligenceTarget,
        payload: Mapping[str, Any],
    ) -> MarketIntelligenceEnvelope:
        record = MarketIntelligenceRecord(
            source_family=self.source_family,
            provider=self.provider_key,
            external_id=f'preview:{self.provider_key}:{operation}',
            title=f'Preview for {self.connector_id}',
            body='Dry-run preview only. No external request executed.',
            url=target.subject_url,
            evidence={'query': target.query, 'account_ref': target.account_ref, 'limit': target.limit},
            metadata={'preview': True, 'requested_payload_keys': sorted(str(key) for key in payload)},
            tags=(self.source_family, self.provider_key, 'preview'),
        )
        return MarketIntelligenceEnvelope(
            connector_id=self.connector_id,
            provider=self.provider_key,
            source_family=self.source_family,
            operation=operation,
            target=target,
            records=(record,),
            summary={'preview': True, 'records_count': 1},
            metadata={'mode': 'dry_run'},
        )

    def _build_envelope_from_provider(
        self,
        *,
        operation: str,
        target: MarketIntelligenceTarget,
        payload: Mapping[str, Any],
        raw: Mapping[str, Any] | None,
    ) -> MarketIntelligenceEnvelope:
        normalized_raw = _safe_dict(raw)
        records: list[MarketIntelligenceRecord] = []
        for index, item in enumerate(_safe_list(normalized_raw.get('records'))):
            records.append(
                MarketIntelligenceRecord(
                    source_family=self.source_family,
                    provider=self.provider_key,
                    external_id=str(item.get('external_id') or item.get('id') or f'{self.provider_key}:{index}'),
                    title=str(item.get('title') or item.get('headline') or item.get('name') or '').strip(),
                    body=str(item.get('body') or item.get('description') or item.get('copy') or '').strip(),
                    url=_safe_text(item.get('url') or item.get('landing_url')),
                    price=item.get('price'),
                    rating=item.get('rating'),
                    currency=_safe_text(item.get('currency')),
                    evidence=_safe_dict(item.get('evidence')),
                    metadata={**_safe_dict(item.get('metadata')), 'source_payload': dict(item)},
                    tags=tuple(item.get('tags') or (self.source_family, self.provider_key)),
                )
            )
        if not records:
            records.append(
                MarketIntelligenceRecord(
                    source_family=self.source_family,
                    provider=self.provider_key,
                    external_id=f'empty:{self.provider_key}:{operation}',
                    title='No records returned',
                    body='Provider returned an empty record list.',
                    evidence={'query': target.query, 'subject_url': target.subject_url},
                    tags=(self.source_family, self.provider_key, 'empty'),
                )
            )
        return MarketIntelligenceEnvelope(
            connector_id=self.connector_id,
            provider=self.provider_key,
            source_family=self.source_family,
            operation=operation,
            target=target,
            records=tuple(records),
            cursor=_safe_text(normalized_raw.get('cursor')),
            summary={'records_count': len(records), 'provider_status': str(normalized_raw.get('status') or 'ok'), 'requested_limit': target.limit},
            metadata={'source_payload_keys': sorted(str(key) for key in payload), 'provider_metadata': _safe_dict(normalized_raw.get('metadata'))},
        )

    def _to_result(
        self,
        *,
        ok: bool,
        code: str,
        message: str,
        envelope: MarketIntelligenceEnvelope,
        dry_run: bool,
    ) -> ConnectorResult:
        payload = envelope.as_dict()
        payload['dry_run'] = bool(dry_run)
        payload['connector_id'] = self.connector_id
        payload['capability_family'] = 'market_intelligence'
        return ConnectorResult(ok=bool(ok), code=str(code), message=str(message), payload=payload)


__all__ = ['CANON_MARKET_INTELLIGENCE_BASE', 'MarketIntelConnectorBase', 'ProviderClientProtocol']
