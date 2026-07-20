from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

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
from interfaces.common.connector_support import (
    build_invalid_payload_result,
    normalize_operation,
    normalize_payload,
)

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


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _safe_text(value: object | None) -> str | None:
    text = str(value or '').strip()
    return text or None


def _bounded_limit(value: object, *, default: int = 25) -> int:
    if value is None or str(value).strip() == '':
        return int(default)
    if isinstance(value, bool):
        raise ValueError('limit must be an integer')
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('limit must be an integer') from exc
    if not parsed.is_integer():
        raise ValueError('limit must be an integer')
    return max(1, min(int(parsed), 250))


def _normalize_tags(value: object, *, defaults: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return defaults
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else defaults
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError('record tags must be a string or sequence')
    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    return normalized or defaults


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
        self.connector_name = str(self.connector_name or '').strip() or 'market_intelligence'
        self.connector_id = str(self.connector_id or '').strip()
        self.provider_key = str(self.provider_key or '').strip()
        self.source_family = str(self.source_family or '').strip()
        self.version = str(self.version or '').strip() or 'v1'
        if not self.connector_id:
            raise ValueError('connector_id is required')
        if not self.provider_key:
            raise ValueError('provider_key is required')
        if self.source_family not in _OPERATION_MAP:
            raise ValueError(f'unsupported source_family: {self.source_family}')
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
        if not dry_run:
            return super().execute(operation, payload, idempotency_key=idempotency_key, dry_run=False)
        if hasattr(self, 'decide'):
            raise RuntimeError('connectors must never expose decide()')
        op = normalize_operation(operation)
        if not op:
            return ConnectorResult(ok=False, code='invalid_operation', message='operation is required')
        normalized_payload = normalize_payload(payload)
        if normalized_payload is None:
            return build_invalid_payload_result(connector_name=self.connector_name, operation=op)
        if not self.rate_limit_guard.allow(f'{self.connector_name}:{op}'):
            return ConnectorResult(ok=False, code='rate_limited', message='connector rate limit reached')
        if not self.supports_dry_run():
            return self._enrich_result(
                ConnectorResult(ok=False, code='dry_run_not_supported', message=f'{self.connector_name}.{op} does not support dry_run'),
                operation=op,
                dry_run=True,
                idempotency_key=idempotency_key,
            )
        if idempotency_key and not self.supports_idempotency():
            return self._enrich_result(
                ConnectorResult(ok=False, code='idempotency_not_supported', message=f'{self.connector_name}.{op} does not support idempotency'),
                operation=op,
                dry_run=True,
                idempotency_key=idempotency_key,
            )
        if op not in set(self._operation_names()):
            return self._enrich_result(
                ConnectorResult(ok=False, code='unsupported_operation', message=f'unsupported operation: {op}'),
                operation=op,
                dry_run=True,
                idempotency_key=idempotency_key,
            )
        try:
            target = self._build_target(normalized_payload)
        except ValueError as exc:
            return self._enrich_result(
                ConnectorResult(ok=False, code='invalid_payload', message=str(exc)),
                operation=op,
                dry_run=True,
                idempotency_key=idempotency_key,
            )
        envelope = self._build_dry_run_envelope(operation=op, target=target, payload=normalized_payload)
        result = self._to_result(ok=True, code='dry_run', message='dry-run preview generated', envelope=envelope, dry_run=True)
        return self._enrich_result(result, operation=op, dry_run=True, idempotency_key=idempotency_key)

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
                'operation_names': list(self._operation_names()),
            },
        )

    def health(self) -> ConnectorHealth:
        if self.provider_client is not None:
            healthy = True
            reason = 'provider_configured'
        elif self.support_dry_run:
            healthy = True
            reason = 'dry_run_only'
        else:
            healthy = False
            reason = 'not_configured'
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
                'operations': list(self._operation_names()),
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
        if operation not in set(self._operation_names()):
            return ConnectorResult(ok=False, code='unsupported_operation', message=f'unsupported operation: {operation}')
        normalized_payload = _safe_dict(payload)
        try:
            target = self._build_target(normalized_payload)
        except ValueError as exc:
            return ConnectorResult(ok=False, code='invalid_payload', message=str(exc))
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
        except Exception as exc:
            return ConnectorResult(ok=False, code='provider_error', message=str(exc) or exc.__class__.__name__)
        if not isinstance(raw, Mapping):
            return ConnectorResult(ok=False, code='provider_contract_error', message='provider result must be a mapping')
        normalized_raw = dict(raw)
        provider_status = str(normalized_raw.get('status') or '').strip().lower()
        if normalized_raw.get('ok') is False or normalized_raw.get('executed') is False or provider_status in {'error', 'failed', 'rejected'}:
            return ConnectorResult(
                ok=False,
                code=str(normalized_raw.get('code') or 'provider_error').strip() or 'provider_error',
                message=str(normalized_raw.get('message') or 'provider returned a failed result').strip(),
                payload={'provider_status': provider_status},
            )
        raw_records = normalized_raw.get('records')
        if raw_records is not None and not isinstance(raw_records, (list, tuple)):
            return ConnectorResult(ok=False, code='provider_contract_error', message='provider records must be a list or tuple')
        if isinstance(raw_records, (list, tuple)) and any(not isinstance(item, Mapping) for item in raw_records):
            return ConnectorResult(ok=False, code='provider_contract_error', message='provider records must contain mappings')
        try:
            envelope = self._build_envelope_from_provider(operation=operation, target=target, payload=normalized_payload, raw=normalized_raw)
        except (TypeError, ValueError) as exc:
            return ConnectorResult(ok=False, code='provider_contract_error', message=str(exc))
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
        raw_records = normalized_result.get('records')
        if not isinstance(raw_records, (list, tuple)):
            return ConnectorResult(ok=False, code='verification_records_invalid', message='records must be a list or tuple')
        if any(not isinstance(item, Mapping) for item in raw_records):
            return ConnectorResult(ok=False, code='verification_records_invalid', message='records must contain mappings')
        records = _safe_list(raw_records)
        if records and any(not str(item.get('external_id') or '').strip() for item in records):
            return ConnectorResult(ok=False, code='verification_record_identity_missing', message='records missing external_id')
        requested_query = _safe_text(normalized_payload.get('query'))
        requested_subject = _safe_text(normalized_payload.get('subject_url') or normalized_payload.get('url'))
        requested_tenant = _safe_text(normalized_payload.get('tenant_id') or normalized_payload.get('tenant'))
        envelope_target_raw = normalized_result.get('target')
        if (requested_query or requested_subject or requested_tenant) and not isinstance(envelope_target_raw, Mapping):
            return ConnectorResult(ok=False, code='verification_target_missing', message='target evidence is required')
        envelope_target = envelope_target_raw if isinstance(envelope_target_raw, Mapping) else {}
        target_query = _safe_text(envelope_target.get('query'))
        target_subject = _safe_text(envelope_target.get('subject_url'))
        target_tenant = _safe_text(envelope_target.get('tenant_id'))
        if requested_query and requested_query != target_query:
            return ConnectorResult(ok=False, code='verification_query_mismatch', message='query mismatch')
        if requested_subject and requested_subject != target_subject:
            return ConnectorResult(ok=False, code='verification_subject_mismatch', message='subject_url mismatch')
        if requested_tenant and requested_tenant != target_tenant:
            return ConnectorResult(ok=False, code='verification_tenant_mismatch', message='tenant_id mismatch')
        return ConnectorResult(
            ok=True,
            code='verified',
            message='market intelligence payload verified',
            payload={'records_count': len(records)},
        )

    def _build_target(self, payload: Mapping[str, Any]) -> MarketIntelligenceTarget:
        metadata = payload.get('metadata')
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError('metadata must be a mapping')
        return MarketIntelligenceTarget(
            source_family=self.source_family,
            provider=self.provider_key,
            tenant_id=str(payload.get('tenant_id') or payload.get('tenant') or 'default').strip() or 'default',
            query=_safe_text(payload.get('query')),
            subject_url=_safe_text(payload.get('subject_url') or payload.get('url')),
            account_ref=_safe_text(payload.get('account_ref') or payload.get('handle')),
            region=_safe_text(payload.get('region')),
            locale=_safe_text(payload.get('locale')),
            limit=_bounded_limit(payload.get('limit')),
            metadata=_safe_dict(metadata),
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
                    tags=_normalize_tags(item.get('tags'), defaults=(self.source_family, self.provider_key)),
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

    def _operation_names(self) -> tuple[str, ...]:
        return tuple(_OPERATION_MAP[self.source_family])


__all__ = ['CANON_MARKET_INTELLIGENCE_BASE', 'MarketIntelConnectorBase', 'ProviderClientProtocol']
