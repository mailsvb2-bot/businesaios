from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.evidence.base import EvidenceVerifier


CANON_MARKET_INTELLIGENCE_EVIDENCE = True


@dataclass(frozen=True)
class MarketIntelligenceEvidenceVerifier(EvidenceVerifier):
    action_prefixes: tuple[str, ...] = (
        'sync_marketplace_catalog',
        'sync_ads_library',
        'sync_competitor_analytics',
        'sync_search_intelligence',
        'sync_professional_discussions',
        'sync_content_publications',
        'sync_app_store_intelligence',
        'sync_review_intelligence',
        'crawl_competitor_landing',
        'sync_video_platform',
        'sync_ads_spy_intelligence',
        'sync_newsletter_intelligence',
    )

    def verify(self, request: Any, action: Any, action_result: Any, connector_result: Any):
        result_payload = self._connector_payload(connector_result)
        records = result_payload.get('records')
        if not isinstance(records, list):
            return self._verify_from_payload(
                status='unverified',
                request=request,
                action=action,
                action_result=action_result,
                connector_result={'verify': {'ok': False, 'code': 'records_missing', 'message': 'records list missing'}},
            )
        provider = str(result_payload.get('provider') or '').strip()
        source_family = str(result_payload.get('source_family') or '').strip()
        operation = str(result_payload.get('operation') or '').strip()
        if not provider or not source_family or not operation:
            return self._verify_from_payload(
                status='unverified',
                request=request,
                action=action,
                action_result=action_result,
                connector_result={'verify': {'ok': False, 'code': 'identity_missing', 'message': 'provider/source_family/operation missing'}},
            )
        if records and not any(isinstance(item, Mapping) and str(item.get('external_id') or '').strip() for item in records):
            return self._verify_from_payload(
                status='unverified',
                request=request,
                action=action,
                action_result=action_result,
                connector_result={'verify': {'ok': False, 'code': 'record_identity_missing', 'message': 'records missing external_id'}},
            )
        return self._verify_from_payload(
            status='verified',
            request=request,
            action=action,
            action_result=action_result,
            connector_result={'verify': {'ok': True, 'code': 'verified', 'message': 'market intelligence payload verified', 'external_refs': [f'{provider}:{source_family}:{operation}']}, **result_payload},
        )

    def _connector_payload(self, connector_result: Any) -> dict[str, Any]:
        if isinstance(connector_result, Mapping):
            payload = connector_result.get('connector_payload', connector_result)
            return dict(payload) if isinstance(payload, Mapping) else dict(connector_result)
        payload = getattr(connector_result, 'payload', {})
        return dict(payload) if isinstance(payload, Mapping) else {}


__all__ = ['CANON_MARKET_INTELLIGENCE_EVIDENCE', 'MarketIntelligenceEvidenceVerifier']
