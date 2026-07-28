from __future__ import annotations

from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest, ClientOutcomeAdminSummaryResponse
from entrypoints.api.client_outcome_admin_view_models import ClientOutcomeAdminViewResponse
from entrypoints.api.client_outcome_routes.module_helpers import _order_from_input, _present_order, _require_order_tenant


def get_admin_view(handlers, *, order_id: str, lead_id: str, tenant_id: str) -> ClientOutcomeAdminViewResponse:
    order = _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    lifecycle = handlers.lifecycle_service.get_state(order_id=order_id, lead_id=lead_id)
    commercial_state = handlers.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
    corrected_economics = handlers.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
    reconciliation = handlers.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    if order is None and lifecycle is None and commercial_state is None and corrected_economics is None and not reconciliation.found:
        return ClientOutcomeAdminViewResponse(found=False)
    resolved_tenant_id = handlers._resolve_tenant_id(
        order=order,
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation=reconciliation,
    )
    if resolved_tenant_id and str(resolved_tenant_id).strip() != str(tenant_id).strip():
        raise PermissionError('client_outcome_admin_tenant_mismatch')
    handlers._emit_reconciliation_metrics(tenant_id=resolved_tenant_id, result=reconciliation)
    reconciliation_payload = None if not reconciliation.found else {
        'found': reconciliation.found,
        'order_id': reconciliation.order_id,
        'lead_id': reconciliation.lead_id,
        'consistent': reconciliation.consistent,
        'issues': tuple(reconciliation.issues),
        'commercial_status': reconciliation.commercial_status,
        'economics_status': reconciliation.economics_status,
        'reversal_amount': reconciliation.reversal_amount,
        'corrected_revenue': reconciliation.corrected_revenue,
    }
    widgets: list[dict[str, object]] = []
    metadata = {} if order is None else dict(order.metadata)
    amendment_count = int(metadata.get('amendment_count') or 0)
    amendments = tuple(dict(item) for item in (metadata.get('amendments') or ()))
    if order is not None:
        widgets.append({
            'widget_id': 'client_outcome_amendments',
            'kind': 'audit_list',
            'payload': {
                'amendment_count': amendment_count,
                'amendments': amendments,
                'current_package_id': order.package.package_id,
            },
        })
    stages = {} if lifecycle is None else dict(lifecycle.get('stages') or {})
    if lifecycle is not None:
        widgets.append({
            'widget_id': 'client_outcome_timeline',
            'kind': 'timeline',
            'payload': {
                'stage_names': tuple(stages.keys()),
                'stage_count': len(stages),
                'latest_stage': next(reversed(stages.keys()), '') if stages else '',
            },
        })
    if reconciliation_payload is not None:
        widgets.append({'widget_id': 'client_outcome_reconciliation', 'kind': 'status', 'payload': reconciliation_payload})
    economic_truth_widget, export_widget = handlers._build_economic_truth_widget(
        order=order,
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation_payload=reconciliation_payload,
    )
    widgets.append(economic_truth_widget)
    widgets.append(export_widget)
    anomaly_issues = tuple(reconciliation.issues) if reconciliation.found else ('missing_reconciliation_truth',)
    widgets.append({
        'widget_id': 'client_outcome_anomalies',
        'kind': 'flags',
        'payload': {
            'issue_count': len(anomaly_issues),
            'issues': anomaly_issues,
            'severity': 'ok' if reconciliation.found and reconciliation.consistent else 'attention_required',
        },
    })
    allowed_actions: list[str] = []
    if reconciliation.found and reconciliation.consistent:
        allowed_actions.append('view_reconciliation')
    else:
        allowed_actions.extend(['inspect_reconciliation', 'repair_commercial_truth'])
    if commercial_state is None or str((commercial_state or {}).get('commercial_status') or '') in {
        '', 'executed', 'verified', 'verification_rejected'
    }:
        allowed_actions.append('amend_package')
    refund_request = {} if corrected_economics is None else dict((corrected_economics or {}).get('refund_request') or {})
    refund_preview = {} if corrected_economics is None else dict((corrected_economics or {}).get('refund_preview') or {})
    if refund_preview and not refund_request:
        allowed_actions.append('create_refund_request')
    if refund_request:
        allowed_actions.append('inspect_refund_request')
        widgets.append({
            'widget_id': 'client_outcome_refund_bridge',
            'kind': 'bridge_status',
            'payload': {
                'has_refund_preview': bool(refund_preview),
                'has_refund_request': True,
                'invoice_id': refund_request.get('invoice_id'),
                'provider_name': refund_request.get('provider_name'),
                'amount_minor': refund_request.get('amount_minor'),
                'currency': refund_request.get('currency'),
            },
        })
    widgets.append({
        'widget_id': 'client_outcome_operator_actions',
        'kind': 'actions',
        'payload': {
            'allowed_actions': tuple(dict.fromkeys(allowed_actions)),
            'amendment_count': amendment_count,
            'has_reversal': bool((corrected_economics or {}).get('reversal') or (commercial_state or {}).get('reversal')),
            'has_refund_request': bool(refund_request),
        },
    })
    widgets.append(
        handlers._build_recovery_bridge_widget(
            reconciliation_payload=reconciliation_payload,
            corrected_economics=corrected_economics,
        )
    )
    metrics_widget = handlers._build_operational_metrics_widget(tenant_id=resolved_tenant_id)
    if metrics_widget is not None:
        widgets.append(metrics_widget)
    return ClientOutcomeAdminViewResponse(
        found=True,
        order=None if order is None else _present_order(order).model_dump(),
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation=reconciliation_payload,
        widgets=tuple(widgets),
    )


def build_admin_summary(handlers, *, request: ClientOutcomeAdminSummaryRequest, tenant_id: str) -> ClientOutcomeAdminSummaryResponse:
    order = _order_from_input(request.order)
    if str(order.tenant_id).strip() != str(tenant_id).strip():
        raise PermissionError('client_outcome_order_tenant_mismatch')
    snapshot = ClientOutcomeEconomicSnapshot(
        tenant_id=order.tenant_id,
        business_id=order.business_id,
        order_id=order.order_id,
        package_id=order.package.package_id,
        verified_clients=request.economic_snapshot.verified_clients,
        billable_clients=request.economic_snapshot.billable_clients,
        billed_revenue=request.economic_snapshot.billed_revenue,
        acquisition_cost=request.economic_snapshot.acquisition_cost,
        gross_margin=request.economic_snapshot.gross_margin,
        cac=request.economic_snapshot.cac,
        revenue_per_client=request.economic_snapshot.revenue_per_client,
        margin_per_client=request.economic_snapshot.margin_per_client,
        currency=request.economic_snapshot.currency,
    )
    summary = handlers.control_plane_service.build_summary(order=order, economic_snapshot=snapshot)
    widgets = handlers.control_plane_service.build_widgets(summary=summary)
    return ClientOutcomeAdminSummaryResponse(
        tenant_id=summary.tenant_id,
        business_id=summary.business_id,
        order_id=summary.order_id,
        package_id=summary.package_id,
        requested_clients=summary.requested_clients,
        verified_clients=summary.verified_clients,
        billable_clients=summary.billable_clients,
        reversed_clients=summary.reversed_clients,
        open_disputes=summary.open_disputes,
        reversed_disputes=summary.reversed_disputes,
        gross_revenue=summary.gross_revenue,
        net_revenue=summary.net_revenue,
        currency=summary.currency,
        widgets=tuple({'widget_id': item.widget_id, 'kind': item.kind, 'payload': item.payload} for item in widgets),
    )


__all__ = ['get_admin_view', 'build_admin_summary']
