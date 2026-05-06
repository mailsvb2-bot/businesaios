from __future__ import annotations

from typing import Any, Mapping

from economics.contracts import BillableFact
from .contracts import ClickBillableFact, ClickCommercialFact


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_click_commercial_fact_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickCommercialFact:
    truth = dict(truth_snapshot)
    lifecycle_payload = _safe_dict(lifecycle)
    lead_payload = _safe_dict(lifecycle_payload.get('lead'))
    stages = _safe_dict(lifecycle_payload.get('stages'))
    captured_payload = _safe_dict(_safe_dict(stages.get('lead_captured')).get('payload'))

    click_id = str(lead_payload.get('click_id') or captured_payload.get('click_id') or truth.get('click_id') or '').strip()
    session_id = str(lead_payload.get('session_id') or captured_payload.get('session_id') or truth.get('session_id') or '').strip()
    source_channel = str(lead_payload.get('source_channel') or captured_payload.get('source_channel') or truth.get('source_channel') or '').strip()
    tracking_token = str(lead_payload.get('tracking_token') or captured_payload.get('tracking_token') or truth.get('tracking_token') or '').strip()

    paid_channel = source_channel.lower() in {'ads', 'paid_search', 'paid_social', 'ppc', 'cpc'}
    linked = bool(click_id or session_id)
    billable_candidate = paid_channel and linked and bool(tracking_token)
    issues: list[str] = []
    if paid_channel and not click_id:
        issues.append('missing_click_id_for_paid_channel')
    if linked and not tracking_token:
        issues.append('click_link_without_tracking_token')
    if paid_channel and not linked:
        issues.append('missing_click_linkage')

    status = 'billable_candidate' if billable_candidate else ('linked' if linked else ('pending' if source_channel else 'unknown'))
    refs = tuple(ref for ref in (click_id, session_id, tracking_token, source_channel) if ref)
    return ClickCommercialFact(
        tenant_id=str(truth.get('tenant_id') or ''),
        business_id=str(truth.get('business_id') or ''),
        entity_id=str(truth.get('order_id') or ''),
        source_channel=source_channel,
        click_id=click_id,
        session_id=session_id,
        tracking_token=tracking_token,
        status=status,
        paid_channel=paid_channel,
        billable_candidate=billable_candidate,
        issues=tuple(issues),
        evidence_refs=refs,
        ready_for_export=bool(truth.get('reconciliation_consistent')),
    )



def _safe_minor_from_payload(value: object) -> int | None:
    if value in (None, ''):
        return None
    try:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None



def _resolve_click_price_minor(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> int | None:
    truth = dict(truth_snapshot)
    metadata = _safe_dict(truth.get('metadata'))
    lifecycle_payload = _safe_dict(lifecycle)
    lead_payload = _safe_dict(lifecycle_payload.get('lead'))
    lead_metadata = _safe_dict(lead_payload.get('metadata'))
    stages = _safe_dict(lifecycle_payload.get('stages'))
    captured_payload = _safe_dict(_safe_dict(stages.get('lead_captured')).get('payload'))
    captured_metadata = _safe_dict(captured_payload.get('metadata'))
    for candidate in (
        truth.get('click_price_minor'),
        metadata.get('click_price_minor'),
        lead_payload.get('click_price_minor'),
        lead_metadata.get('click_price_minor'),
        captured_payload.get('click_price_minor'),
        captured_metadata.get('click_price_minor'),
    ):
        if candidate in (None, ''):
            continue
        try:
            minor = int(str(candidate).strip())
        except (TypeError, ValueError):
            continue
        if minor > 0:
            return minor
    for candidate in (
        truth.get('click_price'),
        metadata.get('click_price'),
        lead_payload.get('click_price'),
        lead_metadata.get('click_price'),
        captured_payload.get('click_price'),
        captured_metadata.get('click_price'),
    ):
        minor = _safe_minor_from_payload(candidate)
        if minor is not None and minor > 0:
            return minor
    return None



def _resolve_currency(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> str:
    truth = dict(truth_snapshot)
    metadata = _safe_dict(truth.get('metadata'))
    lifecycle_payload = _safe_dict(lifecycle)
    lead_payload = _safe_dict(lifecycle_payload.get('lead'))
    lead_metadata = _safe_dict(lead_payload.get('metadata'))
    stages = _safe_dict(lifecycle_payload.get('stages'))
    captured_payload = _safe_dict(_safe_dict(stages.get('lead_captured')).get('payload'))
    captured_metadata = _safe_dict(captured_payload.get('metadata'))
    for candidate in (
        truth.get('currency'), metadata.get('currency'),
        lead_payload.get('currency'), lead_metadata.get('currency'),
        captured_payload.get('currency'), captured_metadata.get('currency'),
    ):
        c = str(candidate or '').strip()
        if c:
            return c
    return 'USD'



def build_click_billable_fact_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> ClickBillableFact | None:
    commercial = build_click_commercial_fact_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    click_price_minor = _resolve_click_price_minor(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    currency = _resolve_currency(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    issues = list(commercial.issues)
    if click_price_minor is None:
        issues.append('missing_click_price')
    ready = commercial.billable_candidate and click_price_minor is not None and click_price_minor > 0
    if not ready and not commercial.billable_candidate:
        return None
    return ClickBillableFact(
        tenant_id=commercial.tenant_id,
        business_id=commercial.business_id,
        entity_id=commercial.entity_id,
        amount_minor=int(click_price_minor or 0),
        currency=currency,
        source_channel=commercial.source_channel,
        click_id=commercial.click_id,
        session_id=commercial.session_id,
        tracking_token=commercial.tracking_token,
        issues=tuple(issues),
        evidence_refs=tuple(ref for ref in (*commercial.evidence_refs, str(click_price_minor or '')) if ref),
        ready_for_billing=ready,
        ready_for_export=ready and commercial.ready_for_export,
    )



def build_click_billable_fact_contract_from_client_outcome(*, truth_snapshot: Mapping[str, Any], lifecycle: object | None) -> BillableFact | None:
    billable = build_click_billable_fact_from_client_outcome(truth_snapshot=truth_snapshot, lifecycle=lifecycle)
    if billable is None or not billable.ready_for_billing:
        return None
    return BillableFact(
        tenant_id=billable.tenant_id,
        business_id=billable.business_id,
        domain='click_economics',
        entity_id=billable.entity_id,
        amount_minor=billable.amount_minor,
        currency=billable.currency,
        reason_code=billable.reason_code,
        evidence_refs=billable.evidence_refs,
        idempotency_key='click:' + ':'.join(part for part in (billable.entity_id, billable.click_id or billable.session_id, str(billable.amount_minor)) if part),
    )
