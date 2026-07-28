from __future__ import annotations

from datetime import datetime, timezone

from entrypoints.api.client_outcome_commercial_state_models import ClientOutcomeCommercialStateResponse
from entrypoints.api.client_outcome_corrected_economics_models import ClientOutcomeCorrectedEconomicsResponse
from entrypoints.api.client_outcome_lifecycle_models import ClientOutcomeLifecycleResponse
from entrypoints.api.client_outcome_reconciliation_models import ClientOutcomeReconciliationResponse
from entrypoints.api.client_outcome_routes.module_helpers import _require_order_tenant
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation
from runtime.economic_core.client_outcome_bridge import build_client_outcome_truth_snapshot
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export


def get_lifecycle(handlers, *, order_id: str, lead_id: str, tenant_id: str) -> ClientOutcomeLifecycleResponse:
    _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    state = handlers.lifecycle_service.get_state(order_id=order_id, lead_id=lead_id)
    if state is None:
        return ClientOutcomeLifecycleResponse(found=False)
    stages = {
        str(name): {'at': str(payload.get('at') or ''), 'payload': dict(payload.get('payload') or {})}
        for name, payload in dict(state.get('stages') or {}).items()
    }
    return ClientOutcomeLifecycleResponse(
        found=True,
        order_id=str(state.get('order_id') or ''),
        lead_id=str(state.get('lead_id') or ''),
        created_at=str(state.get('created_at') or ''),
        updated_at=str(state.get('updated_at') or ''),
        stages=stages,
    )


def get_commercial_state(handlers, *, order_id: str, lead_id: str, tenant_id: str) -> ClientOutcomeCommercialStateResponse:
    _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    state = handlers.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
    if state is None:
        return ClientOutcomeCommercialStateResponse(found=False)
    return ClientOutcomeCommercialStateResponse(found=True, **state)


def get_corrected_economics(handlers, *, order_id: str, lead_id: str, tenant_id: str) -> ClientOutcomeCorrectedEconomicsResponse:
    _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    state = handlers.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
    if state is None:
        return ClientOutcomeCorrectedEconomicsResponse(found=False)
    refund_request_payload = state.get('refund_request')
    refund_request = None if refund_request_payload is not None else handlers.refund_request_bridge.to_request(
        now=datetime.now(timezone.utc),
        preview=state.get('refund_preview'),
    )
    if refund_request_payload is None and refund_request is not None:
        refund_request_payload = {
            'tenant_id': refund_request.tenant_id,
            'invoice_id': refund_request.invoice_id,
            'user_id': refund_request.user_id,
            'amount_minor': refund_request.amount_minor,
            'currency': refund_request.currency,
            'reason': refund_request.reason,
            'provider_name': refund_request.provider_name,
            'requested_at': refund_request.requested_at.isoformat(),
            'idempotency_key': refund_request.idempotency_key,
            'metadata': dict(refund_request.metadata),
        }
    state_payload = dict(state)
    state_payload.pop('refund_request', None)
    return ClientOutcomeCorrectedEconomicsResponse(found=True, refund_request=refund_request_payload, **state_payload)


def _resolve_tenant_id(
    handlers,
    *,
    order: ClientOutcomeOrder | None = None,
    lifecycle: dict[str, object] | None = None,
    commercial_state: dict[str, object] | None = None,
    corrected_economics: dict[str, object] | None = None,
    reconciliation: object | None = None,
) -> str:
    for source in (
        None if order is None else {'tenant_id': order.tenant_id},
        lifecycle,
        commercial_state,
        corrected_economics,
        None if reconciliation is None else getattr(reconciliation, 'commercial_state', None),
        None if reconciliation is None else getattr(reconciliation, 'corrected_economics', None),
        None if reconciliation is None else getattr(reconciliation, 'lifecycle', None),
    ):
        if isinstance(source, dict):
            tenant_id = str(source.get('tenant_id') or '').strip()
            if tenant_id:
                return tenant_id
    return ''


def _emit_reconciliation_metrics(handlers, *, tenant_id: str, result: object) -> None:
    normalized_tenant_id = str(tenant_id or '').strip()
    if not normalized_tenant_id:
        return
    issue_count = len(tuple(getattr(result, 'issues', ()) or ()))
    consistent = bool(getattr(result, 'consistent', False)) and bool(getattr(result, 'found', False))
    labels = {
        'commercial_status': str(getattr(result, 'commercial_status', '') or 'unknown'),
        'economics_status': str(getattr(result, 'economics_status', '') or 'unknown'),
    }
    handlers.tenant_metrics_registry.set_gauge(
        tenant_id=normalized_tenant_id,
        metric_name='client_outcome.reconciliation_consistent',
        value=1.0 if consistent else 0.0,
        labels=labels,
    )
    handlers.tenant_metrics_registry.set_gauge(
        tenant_id=normalized_tenant_id,
        metric_name='client_outcome.reconciliation_issue_count',
        value=float(issue_count),
        labels=labels,
    )
    if issue_count:
        handlers.tenant_metrics_registry.emit(
            tenant_id=normalized_tenant_id,
            metric_name='client_outcome.reconciliation_issues_observed',
            kind=SLIKind.THROUGHPUT,
            value=float(issue_count),
            aggregation=MetricAggregation.SUM,
            labels=labels,
        )


def _build_operational_metrics_widget(handlers, *, tenant_id: str) -> dict[str, object] | None:
    normalized_tenant_id = str(tenant_id or '').strip()
    if not normalized_tenant_id:
        return None
    metric_names = (
        'client_outcome.reconciliation_consistent',
        'client_outcome.reconciliation_issue_count',
        'client_outcome.reconciliation_issues_observed',
    )
    snapshots = {
        name: snap
        for name in metric_names
        if (snap := handlers.tenant_metrics_registry.metric_snapshot(tenant_id=normalized_tenant_id, metric_name=name)) is not None
    }
    if not snapshots:
        return None
    return {
        'widget_id': 'client_outcome_operational_metrics',
        'kind': 'metrics',
        'payload': {'tenant_id': normalized_tenant_id, 'metrics': snapshots},
    }


def _build_economic_truth_widget(
    handlers,
    *,
    order: object | None,
    lifecycle: dict[str, object] | None,
    commercial_state: dict[str, object] | None,
    corrected_economics: dict[str, object] | None,
    reconciliation_payload: dict[str, object] | None,
) -> tuple[dict[str, object], dict[str, object]]:
    truth_snapshot = build_client_outcome_truth_snapshot(
        order=order,
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation=reconciliation_payload,
    )
    exported_truth = export_client_outcome_truth_snapshot(truth_snapshot)
    return (
        {'widget_id': 'client_outcome_economic_truth', 'kind': 'economic_truth', 'payload': truth_snapshot},
        {
            'widget_id': 'client_outcome_export_bundle',
            'kind': 'export_bundle',
            'payload': {
                'algorithm': exported_truth['algorithm'],
                'hash': exported_truth['hash'],
                'verified': verify_client_outcome_truth_export(exported_truth),
                'export_ready': bool(truth_snapshot.get('reconciliation_consistent')),
                'final_truth_revenue': truth_snapshot.get('final_truth_revenue'),
                'issue_count': len(tuple(truth_snapshot.get('issues') or ())),
            },
        },
    )


def _build_recovery_bridge_widget(
    handlers,
    *,
    reconciliation_payload: dict[str, object] | None,
    corrected_economics: dict[str, object] | None,
) -> dict[str, object]:
    corrected_payload = dict(corrected_economics or {})
    refund_request = dict(corrected_payload.get('refund_request') or {})
    refund_preview = dict(corrected_payload.get('refund_preview') or {})
    issues = tuple(reconciliation_payload.get('issues') or ()) if isinstance(reconciliation_payload, dict) else ()
    recovery_actions: list[str] = []
    if refund_preview and not refund_request:
        recovery_actions.append('materialize_refund_request')
    if issues:
        recovery_actions.append('repair_reconciliation_truth')
    if refund_request:
        recovery_actions.append('export_refund_bundle')
    return {
        'widget_id': 'client_outcome_recovery_bridge',
        'kind': 'recovery_bridge',
        'payload': {
            'has_refund_preview': bool(refund_preview),
            'has_refund_request': bool(refund_request),
            'recovery_actions': tuple(dict.fromkeys(recovery_actions)),
            'issue_count': len(issues),
            'export_ready': bool(refund_request),
        },
    }


def get_reconciliation(handlers, *, order_id: str, lead_id: str, tenant_id: str) -> ClientOutcomeReconciliationResponse:
    _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    result = handlers.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    resolved_tenant_id = handlers._resolve_tenant_id(reconciliation=result)
    handlers._emit_reconciliation_metrics(tenant_id=resolved_tenant_id, result=result)
    if not result.found:
        return ClientOutcomeReconciliationResponse(found=False)
    return ClientOutcomeReconciliationResponse(
        found=True,
        order_id=result.order_id,
        lead_id=result.lead_id,
        consistent=result.consistent,
        issues=result.issues,
        commercial_status=result.commercial_status,
        economics_status=result.economics_status,
        reversal_amount=result.reversal_amount,
        corrected_revenue=result.corrected_revenue,
        commercial_state=result.commercial_state,
        corrected_economics=result.corrected_economics,
        lifecycle=result.lifecycle,
    )


__all__ = [
    'get_lifecycle',
    'get_commercial_state',
    'get_corrected_economics',
    '_resolve_tenant_id',
    '_emit_reconciliation_metrics',
    '_build_operational_metrics_widget',
    '_build_economic_truth_widget',
    '_build_recovery_bridge_widget',
    'get_reconciliation',
]
