from __future__ import annotations

from typing import Mapping, Any


CANON_RUNTIME_ECONOMIC_CORE_CROSS_DOMAIN_RECONCILIATION = True


def build_cross_domain_reconciliation_snapshot(*, client_outcome_truth: Mapping[str, Any], billing_truth: Mapping[str, Any], click_truth: Mapping[str, Any], spend_truth: Mapping[str, Any], spend_source: Mapping[str, Any], click_collection: Mapping[str, Any], click_provider_dispatch: Mapping[str, Any] | None = None, spend_runtime_request: Mapping[str, Any] | None = None, click_sealed_execution: Mapping[str, Any] | None = None, spend_sealed_execution: Mapping[str, Any] | None = None) -> dict[str, Any]:
    issues: list[str] = []
    lifecycle_stages: list[str] = []
    revenue_minor_raw = client_outcome_truth.get('revenue_corrected_minor')
    if revenue_minor_raw in (None, '', 0):
        revenue_minor_raw = client_outcome_truth.get('corrected_revenue') or client_outcome_truth.get('revenue_corrected')
    try:
        revenue_minor = int(revenue_minor_raw) if isinstance(revenue_minor_raw, int) else int(round(float(revenue_minor_raw or 0) * 100))
    except (TypeError, ValueError):
        revenue_minor = 0
    if revenue_minor <= 0:
        revenue_minor = int(billing_truth.get('corrected_amount_minor') or billing_truth.get('booked_amount_minor') or 0)
    spend_minor = int(spend_truth.get('spend_total_minor') or 0)
    if bool(click_truth.get('billable_candidate')) and not bool(click_truth.get('click_billable_fact_ready')):
        issues.append('click_candidate_without_billable_fact')
    else:
        lifecycle_stages.append('click_billable_fact_reconciled')
    if bool(click_collection.get('collection_preview')) and not bool(click_truth.get('click_billable_fact_ready')):
        issues.append('collection_preview_without_click_billable_fact')
    if bool(click_collection.get('execution_result')) and not bool(click_collection.get('settlement_result')):
        issues.append('collection_execution_without_settlement')
    if bool((click_provider_dispatch or {}).get('provider_dispatch')) is False and bool(click_collection.get('settlement_result')):
        issues.append('settlement_without_provider_dispatch')
    if str(spend_source.get('status') or '') == 'ready' and spend_minor <= 0:
        issues.append('spend_source_ready_without_spend_fact')
    else:
        lifecycle_stages.append('spend_source_reconciled')
    if str((spend_runtime_request or {}).get('runtime_request') or '') == '' and bool((spend_source.get('status') or '') == 'ready') and spend_minor > 0:
        issues.append('spend_external_batch_without_runtime_request')
    if bool((click_provider_dispatch or {}).get('provider_dispatch')) and str((click_sealed_execution or {}).get('status') or '') != 'ready':
        issues.append('provider_dispatch_without_sealed_execution')
    if str((spend_runtime_request or {}).get('runtime_request') or '') != '' and str((spend_sealed_execution or {}).get('status') or '') != 'ready':
        issues.append('runtime_request_without_sealed_execution')
    if revenue_minor > 0 and str(billing_truth.get('billing_status') or '') in {'missing', 'unknown', ''}:
        issues.append('revenue_without_billing_status')
    else:
        lifecycle_stages.append('billing_status_reconciled')
    if str(client_outcome_truth.get('source_channel') or '').lower() in {'ads','paid_search','paid_social','ppc','cpc'} and not bool(spend_source.get('tracking_token')):
        issues.append('paid_channel_without_tracking_token')
    return {
        'scope_type': 'cross_domain_reconciliation',
        'consistent': len(issues) == 0,
        'issues': tuple(issues),
        'lifecycle_stages': tuple(lifecycle_stages),
        'revenue_minor': revenue_minor,
        'spend_minor': spend_minor,
        'margin_minor': revenue_minor - spend_minor,
    }
