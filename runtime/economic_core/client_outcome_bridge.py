from __future__ import annotations

from typing import Any, Mapping

CANON_CLIENT_OUTCOME_ECONOMIC_CORE_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_client_outcome_truth_snapshot(
    *,
    order: object | None,
    lifecycle: object | None,
    commercial_state: object | None,
    corrected_economics: object | None,
    reconciliation: object | None,
) -> dict[str, Any]:
    """Compose a single read-only commercial truth snapshot.

    This bridge is translation-only. It must not create alternative economics,
    mutate stores, or bypass canonical client outcome owner surfaces.
    """
    lifecycle_payload = _safe_dict(lifecycle)
    commercial_payload = _safe_dict(commercial_state)
    corrected_payload = _safe_dict(corrected_economics)
    reconciliation_payload = _safe_dict(reconciliation)

    order_payload: dict[str, Any] = {}
    if order is not None:
        order_payload = {
            'order_id': getattr(order, 'order_id', ''),
            'tenant_id': getattr(order, 'tenant_id', ''),
            'business_id': getattr(order, 'business_id', ''),
            'package_id': getattr(getattr(order, 'package', None), 'package_id', ''),
            'requested_clients': getattr(getattr(order, 'package', None), 'requested_clients', 0),
            'currency': getattr(getattr(order, 'package', None), 'currency', ''),
            'metadata': dict(getattr(order, 'metadata', {}) or {}),
        }

    revenue_before = _safe_dict(commercial_payload.get('revenue_before_reversal'))
    revenue_after = _safe_dict(commercial_payload.get('revenue_after_reversal'))
    corrected_revenue = _safe_dict(corrected_payload.get('corrected_revenue'))
    effective_revenue = corrected_revenue or revenue_after or revenue_before

    reversal = _safe_dict(corrected_payload.get('reversal')) or _safe_dict(commercial_payload.get('reversal'))
    final_truth_revenue = _safe_float(effective_revenue.get('billed_revenue'))
    acquisition_cost = _safe_float(effective_revenue.get('acquisition_cost'))
    cac = _safe_float(effective_revenue.get('cac'))
    consistent = bool(reconciliation_payload.get('consistent', False)) and bool(reconciliation_payload.get('found', False))

    return {
        'order_id': str(order_payload.get('order_id') or reconciliation_payload.get('order_id') or ''),
        'tenant_id': str(order_payload.get('tenant_id') or commercial_payload.get('tenant_id') or corrected_payload.get('tenant_id') or lifecycle_payload.get('tenant_id') or ''),
        'business_id': str(order_payload.get('business_id') or ''),
        'package_id': str(order_payload.get('package_id') or ''),
        'requested_clients': int(order_payload.get('requested_clients') or 0),
        'currency': str(order_payload.get('currency') or effective_revenue.get('currency') or ''),
        'metadata': dict(order_payload.get('metadata') or {}),
        'commercial_status': str(commercial_payload.get('commercial_status') or reconciliation_payload.get('commercial_status') or ''),
        'economics_status': str(corrected_payload.get('economics_status') or reconciliation_payload.get('economics_status') or ''),
        'lifecycle_stage_names': tuple(_safe_dict(lifecycle_payload.get('stages')).keys()),
        'revenue_before_reversal': revenue_before,
        'revenue_after_reversal': revenue_after,
        'corrected_revenue': corrected_revenue,
        'reversal': reversal,
        'reversal_amount': _safe_float(reversal.get('amount')),
        'refund_preview': _safe_dict(corrected_payload.get('refund_preview')),
        'refund_request': _safe_dict(corrected_payload.get('refund_request')),
        'reconciliation_found': bool(reconciliation_payload.get('found', False)),
        'reconciliation_consistent': consistent,
        'issues': tuple(str(item) for item in tuple(reconciliation_payload.get('issues') or ())),
        'acquisition_cost': acquisition_cost,
        'cac': cac,
        'final_truth_revenue': final_truth_revenue if consistent else None,
    }


from economics.contracts import TruthFragment


def build_client_outcome_truth_fragment(*, truth_snapshot: Mapping[str, Any]) -> TruthFragment:
    booked_amount_minor = 0
    corrected_amount_minor = 0
    before = _safe_dict(truth_snapshot.get('revenue_before_reversal'))
    corrected = _safe_dict(truth_snapshot.get('corrected_revenue'))
    after = _safe_dict(truth_snapshot.get('revenue_after_reversal'))
    try:
        booked_amount_minor = int(round(float(before.get('billed_revenue', 0.0)) * 100))
    except (TypeError, ValueError):
        booked_amount_minor = 0
    source = corrected or after
    try:
        corrected_amount_minor = int(round(float(source.get('billed_revenue', 0.0)) * 100))
    except (TypeError, ValueError):
        corrected_amount_minor = 0
    currency = before.get('currency') or source.get('currency') or None
    return TruthFragment(
        tenant_id=str(truth_snapshot.get('tenant_id') or ''),
        business_id=str(truth_snapshot.get('business_id') or ''),
        domain='client_outcome',
        entity_id=str(truth_snapshot.get('order_id') or ''),
        commercial_status=str(truth_snapshot.get('commercial_status') or ''),
        lifecycle_stages=tuple(str(item) for item in tuple(truth_snapshot.get('lifecycle_stage_names') or ())),
        booked_amount_minor=booked_amount_minor,
        corrected_amount_minor=corrected_amount_minor,
        currency=None if currency is None else str(currency),
        aggregation_mode='financial_primary',
        issues=tuple(str(item) for item in tuple(truth_snapshot.get('issues') or ())),
        ready_for_export=bool(truth_snapshot.get('reconciliation_consistent')),
    )
