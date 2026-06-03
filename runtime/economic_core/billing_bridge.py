from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_BILLING_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_billing_truth_snapshot_from_client_outcome(*, truth_snapshot: Mapping[str, Any], corrected_economics: object | None) -> dict[str, Any]:
    """Read-only billing projection for the current client-outcome billing path.

    This bridge must stay translation-only until the billing owner publishes a
    first-class truth fragment for this contour.
    """
    truth = dict(truth_snapshot)
    corrected = _safe_dict(corrected_economics)
    refund_request = _safe_dict(corrected.get('refund_request')) or _safe_dict(truth.get('refund_request'))
    reversal = _safe_dict(corrected.get('reversal')) or _safe_dict(truth.get('reversal'))
    corrected_revenue = _safe_dict(corrected.get('corrected_revenue')) or _safe_dict(truth.get('corrected_revenue')) or _safe_dict(truth.get('revenue_after_reversal'))
    currency = str(corrected_revenue.get('currency') or truth.get('currency') or refund_request.get('currency') or 'USD').upper()
    metadata = _safe_dict(truth.get('metadata'))
    invoice_id = str(refund_request.get('invoice_id') or truth.get('invoice_id') or metadata.get('invoice_id') or '')
    provider_name = str(refund_request.get('provider_name') or truth.get('provider_name') or metadata.get('provider_name') or '')
    billed_revenue = corrected_revenue.get('billed_revenue')
    try:
        billed_revenue_float = float(billed_revenue)
    except (TypeError, ValueError):
        billed_revenue_float = 0.0
    try:
        refund_minor = int(refund_request.get('amount_minor') or 0)
    except (TypeError, ValueError):
        refund_minor = 0
    return {
        'tenant_id': str(truth.get('tenant_id') or corrected.get('tenant_id') or ''),
        'business_id': str(truth.get('business_id') or ''),
        'entity_id': str(truth.get('order_id') or ''),
        'invoice_id': invoice_id,
        'provider_name': provider_name,
        'billing_status': 'refunded' if refund_request else ('reversed' if reversal else str(truth.get('commercial_status') or 'pending')),
        'booked_amount_minor': int(round(float(truth.get('final_truth_revenue') or billed_revenue_float or 0.0) * 100)),
        'corrected_amount_minor': max(0, int(round(billed_revenue_float * 100)) - refund_minor),
        'refund_total_minor': refund_minor,
        'chargeback_total_minor': 0,
        'currency': currency,
        'issues': tuple(str(item) for item in tuple(truth.get('issues') or ())),
        'ready_for_export': bool(truth.get('reconciliation_consistent')),
    }


def build_billing_truth_fragment(*, billing_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(billing_snapshot)
    evidence_refs = tuple(ref for ref in (str(snapshot.get('invoice_id') or '').strip(), str(snapshot.get('provider_name') or '').strip()) if ref)
    stages = ('invoice_linked',)
    if int(snapshot.get('refund_total_minor') or 0) > 0:
        stages = stages + ('refund_requested',)
    if str(snapshot.get('billing_status') or '') == 'refunded':
        stages = stages + ('refund_materialized',)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='billing',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('billing_status') or ''),
        lifecycle_stages=stages,
        booked_amount_minor=int(snapshot.get('booked_amount_minor') or 0),
        corrected_amount_minor=int(snapshot.get('corrected_amount_minor') or 0),
        currency=str(snapshot.get('currency') or 'USD'),
        aggregation_mode='consistency_only',
        issues=tuple(str(item) for item in tuple(snapshot.get('issues') or ())),
        evidence_refs=evidence_refs,
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
