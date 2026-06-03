from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_ANOMALY_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_anomaly_truth_snapshot(
    *,
    reconciliation: Mapping[str, Any] | None,
    billing_snapshot: Mapping[str, Any] | None,
    attribution_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    recon = _safe_dict(reconciliation)
    billing = _safe_dict(billing_snapshot)
    attribution = _safe_dict(attribution_snapshot)
    issues: list[str] = []
    issues.extend(str(item) for item in tuple(recon.get('issues') or ()))
    if not bool(recon.get('consistent', True)):
        issues.append('reconciliation_mismatch')
    if int(billing.get('refund_total_minor') or 0) > 0 and recon.get('reversal_amount') in (None, '', 0, 0.0):
        issues.append('refund_without_reversal')
    if bool(attribution.get('attributed')) and not str(attribution.get('source_channel') or '').strip():
        issues.append('missing_attribution_source')
    if attribution.get('tracking_token_present') is False:
        issues.append('missing_tracking_token')
    deduped = tuple(dict.fromkeys(issue for issue in issues if issue))
    return {
        'tenant_id': str(recon.get('tenant_id') or billing.get('tenant_id') or attribution.get('tenant_id') or ''),
        'business_id': str(recon.get('business_id') or billing.get('business_id') or attribution.get('business_id') or ''),
        'entity_id': str(recon.get('order_id') or billing.get('entity_id') or attribution.get('entity_id') or ''),
        'anomaly_status': 'issues_present' if deduped else 'clear',
        'issue_count': len(deduped),
        'issues': deduped,
        'has_issues': bool(deduped),
        'ready_for_export': not bool(deduped),
    }


def build_anomaly_truth_fragment(*, anomaly_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(anomaly_snapshot)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='anomaly',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('anomaly_status') or 'clear'),
        lifecycle_stages=('issues_present',) if bool(snapshot.get('has_issues')) else ('clear',),
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        aggregation_mode='consistency_only',
        issues=tuple(str(item) for item in tuple(snapshot.get('issues') or ())),
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
