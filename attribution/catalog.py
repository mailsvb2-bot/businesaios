from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Sequence

from shared.kinded_payloads import build_kinded_payload


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stable_fingerprint(parts: Sequence[object]) -> str:
    normalized = '|'.join(str(part or '').strip().lower() for part in parts)
    return sha256(normalized.encode('utf-8')).hexdigest()[:16]


@dataclass(frozen=True)
class Touchpoint:
    source: str
    channel: str
    campaign_id: str
    occurred_at_ms: int
    weight_hint: float = 1.0
    contact_fingerprint: str = ''

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> 'Touchpoint':
        return cls(
            source=str(payload.get('source', 'unknown')),
            channel=str(payload.get('channel', payload.get('source', 'unknown'))),
            campaign_id=str(payload.get('campaign_id', 'unknown')),
            occurred_at_ms=int(payload.get('occurred_at_ms', 0) or 0),
            weight_hint=max(0.0, _as_float(payload.get('weight_hint', 1.0), 1.0)),
            contact_fingerprint=str(payload.get('contact_fingerprint', '')),
        )


def _last_channel_for_source(touchpoints: Sequence[Touchpoint], source: str) -> str:
    for tp in reversed(touchpoints):
        if tp.source == source:
            return tp.channel
    return str(source)


class AttributionAudit:
    def record(self, payload: dict) -> dict:
        return build_kinded_payload('attribution_audit', payload)


class AttributionEngine:
    def _normalize_touchpoints(self, payload: Mapping[str, object]) -> list[Touchpoint]:
        raw = payload.get('touchpoints') or []
        touchpoints = [Touchpoint.from_mapping(item) for item in raw if isinstance(item, Mapping)]
        unique: dict[tuple[str, str, str, int], Touchpoint] = {}
        for tp in touchpoints:
            key = (tp.source, tp.channel, tp.campaign_id, tp.occurred_at_ms)
            unique.setdefault(key, tp)
        return sorted(unique.values(), key=lambda item: item.occurred_at_ms)

    def attribute(self, payload: dict) -> dict:
        touchpoints = self._normalize_touchpoints(payload)
        if not touchpoints:
            return build_kinded_payload('attribution_result', payload)
        total_weight = sum(max(tp.weight_hint, 0.0001) for tp in touchpoints)
        shares: dict[str, float] = {}
        for tp in touchpoints:
            shares[tp.source] = shares.get(tp.source, 0.0) + (tp.weight_hint / total_weight)
        shares = {key: round(value, 4) for key, value in shares.items()}
        primary = max(shares.items(), key=lambda item: item[1])[0]
        lead_fingerprint = str(payload.get('lead_fingerprint') or _stable_fingerprint([
            payload.get('email'), payload.get('phone'), payload.get('request_id'), primary,
        ]))
        out = build_kinded_payload('attribution_result', {
            **dict(payload),
            'model': 'weighted_multi_touch_v1',
            'primary_source': primary,
            'primary_channel': _last_channel_for_source(touchpoints, primary),
            'confidence': round(min(1.0, 0.35 + len(touchpoints) * 0.15), 4),
            'attributed_revenue_share': shares,
            'evidence': [f'{tp.source}:{tp.channel}:{tp.campaign_id}' for tp in touchpoints],
            'lead_fingerprint': lead_fingerprint,
            'touch_count': len(touchpoints),
        })
        return out


class CampaignRevenueLinker:
    def link(self, payload: dict) -> dict:
        return build_kinded_payload('campaign_revenue_links', payload)


class FirstTouchModel:
    def attribute(self, payload: dict) -> dict:
        return build_kinded_payload('first_touch_result', payload)


class LastTouchModel:
    def attribute(self, payload: dict) -> dict:
        return build_kinded_payload('last_touch_result', payload)


class LeadToRevenueResolver:
    def resolve(self, payload: dict) -> dict:
        attribution = payload.get('attribution') or {}
        revenue_amount = float(payload.get('revenue_amount', payload.get('revenue', 0.0)) or 0.0)
        lead_fingerprint = str(
            payload.get('lead_fingerprint')
            or attribution.get('lead_fingerprint')
            or _stable_fingerprint([payload.get('email'), payload.get('phone'), payload.get('request_id'), payload.get('lead_id')])
        )
        source_shares = attribution.get('attributed_revenue_share') or {}
        allocated = {
            str(source): round(revenue_amount * float(weight), 2)
            for source, weight in source_shares.items()
        }
        unallocated = round(revenue_amount - sum(allocated.values()), 2)
        if abs(unallocated) >= 0.01 and allocated:
            top_key = max(allocated, key=allocated.get)
            allocated[top_key] = round(allocated[top_key] + unallocated, 2)
            unallocated = 0.0
        return build_kinded_payload('lead_revenue_resolution', {
            **dict(payload),
            'lead_fingerprint': lead_fingerprint,
            'revenue_amount': round(revenue_amount, 2),
            'currency': str(payload.get('currency', 'RUB')),
            'allocated_revenue_by_source': allocated,
            'unallocated_revenue': unallocated,
            'resolution_confidence': float(attribution.get('confidence', 0.0) or 0.0),
        })


class MultiTouchModel:
    def attribute(self, payload: dict) -> dict:
        return build_kinded_payload('multi_touch_result', payload)


class OfflineConversionMapper:
    def map(self, payload: dict) -> dict:
        crm_status = str(payload.get('crm_status', '')).strip().lower()
        normalized_status = {
            'won': 'converted',
            'paid': 'converted',
            'completed': 'completed',
            'booked': 'booked',
            'contacted': 'contacted',
            'lost': 'rejected',
        }.get(crm_status, crm_status or 'unknown')
        return build_kinded_payload('offline_conversion_map', {
            **dict(payload),
            'lead_fingerprint': str(payload.get('lead_fingerprint') or _stable_fingerprint([payload.get('email'), payload.get('phone'), payload.get('crm_lead_id')])),
            'crm_lead_id': str(payload.get('crm_lead_id', '')),
            'external_order_id': str(payload.get('external_order_id', '')),
            'status': normalized_status,
            'revenue_amount': float(payload.get('revenue_amount', 0.0) or 0.0),
            'currency': str(payload.get('currency', 'RUB')),
            'evidence': {
                'source': str(payload.get('source', 'crm')),
                'synced_at_ms': int(payload.get('synced_at_ms', 0) or 0),
            },
        })


class TouchpointRegistry:
    def register(self, payload: dict) -> dict:
        return build_kinded_payload('touchpoint_registry', payload)


ATTRIBUTION_COMPAT_EXPORTS = {
    'AttributionAudit': 'attribution_audit',
    'AttributionEngine': 'attribution_engine',
    'CampaignRevenueLinker': 'campaign_revenue_linker',
    'FirstTouchModel': 'first_touch_model',
    'LastTouchModel': 'last_touch_model',
    'LeadToRevenueResolver': 'lead_to_revenue_resolver',
    'MultiTouchModel': 'multi_touch_model',
    'OfflineConversionMapper': 'offline_conversion_mapper',
    'TouchpointRegistry': 'touchpoint_registry',
}

__all__ = (
    'ATTRIBUTION_COMPAT_EXPORTS',
    'AttributionAudit',
    'AttributionEngine',
    'CampaignRevenueLinker',
    'FirstTouchModel',
    'LastTouchModel',
    'LeadToRevenueResolver',
    'MultiTouchModel',
    'OfflineConversionMapper',
    'TouchpointRegistry',
    'Touchpoint',
)
