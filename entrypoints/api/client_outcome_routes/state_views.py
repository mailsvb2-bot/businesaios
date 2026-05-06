from __future__ import annotations

"""Extracted owner logic for ClientOutcomeRouteHandlers."""

from datetime import datetime, timezone

from admin.client_outcome_control_plane_service import ClientOutcomeControlPlaneService
from application.headless.client_outcome_request_enricher import ClientOutcomeRequestEnricher
from billing.client_outcome_billable_cap_policy import ClientOutcomeBillableCapPolicy
from billing.client_outcome_dispute_service import ClientOutcomeDisputeService
from billing.client_outcome_dispute_store import ClientOutcomeDisputeStore, ClientOutcomeReversalStore
from billing.client_outcome_invoice_aggregator import ClientOutcomeInvoiceAggregator
from billing.client_outcome_negative_usage_builder import ClientOutcomeNegativeUsageBuilder
from billing.client_outcome_package_progress import ClientOutcomePackageProgressCalculator
from billing.client_outcome_refund_projection import ClientOutcomeRefundProjection
from billing.client_outcome_refund_request_bridge import ClientOutcomeRefundRequestBridge
from billing.client_outcome_refund_window_policy import ClientOutcomeRefundWindowPolicy
from billing.client_outcome_revenue_control_service import ClientOutcomeRevenueControlService
from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from billing.client_outcome_reversal_ledger_bridge import ClientOutcomeReversalLedgerBridge
from billing.client_outcome_reversal_posting_service import ClientOutcomeReversalPostingService
from billing.client_outcome_usage_ledger import ClientOutcomeUsageAppender, ClientOutcomeUsageLedger
from billing.ledger_store import InMemoryLedgerStore
from economics.client_outcome_economic_calculator import ClientOutcomeEconomicCalculator
from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest, ClientOutcomeAdminSummaryResponse
from entrypoints.api.client_outcome_admin_view_models import ClientOutcomeAdminViewResponse
from entrypoints.api.client_outcome_commercial_state_models import ClientOutcomeCommercialStateResponse
from entrypoints.api.client_outcome_corrected_economics_models import ClientOutcomeCorrectedEconomicsResponse
from entrypoints.api.client_outcome_reconciliation_models import ClientOutcomeReconciliationResponse
from entrypoints.api.client_outcome_cycle_models import (
    ClientOutcomeRevenueResponse,
    ClientOutcomeVerificationResponse,
    ExecuteClientOutcomeCycleRequest,
    ExecuteClientOutcomeCycleResponse,
)
from entrypoints.api.client_outcome_dispute_models import (
    ClientOutcomeBillableRecordInput,
    ClientOutcomeDisputeResponse,
    ClientOutcomeReversalResponse,
    OpenClientOutcomeDisputeRequest,
    ReverseClientOutcomeDisputeRequest,
)
from entrypoints.api.client_outcome_lifecycle_models import ClientOutcomeLifecycleResponse
from entrypoints.api.client_outcome_models import (
    AmendClientOutcomeOrderRequest,
    ClientOutcomeExecuteResponse,
    ClientOutcomeOrderAmendResponse,
    ClientOutcomeOrderLookupResponse,
    ClientOutcomeOrderResponse,
    ClientOutcomePackageResponse,
    SelectClientOutcomePackageRequest,
)
from lead_outcomes import OutcomeVerifier
from lead_outcomes.client_attribution_policy import ClientAttributionPolicy
from lead_outcomes.client_eligibility_policy import ClientEligibilityPolicy
from lead_outcomes.client_fraud_policy import ClientFraudPolicy
from lead_outcomes.client_outcome_commercial_state_store import (
    ClientOutcomeCommercialStateService,
    ClientOutcomeCommercialStateStore,
)
from lead_outcomes.client_outcome_contract import (
    BillableClientRecord,
    ClientOutcomeOrder,
    ClientOutcomePackage,
    ClientProofEvent,
    OutcomeLead,
)
from lead_outcomes.client_outcome_corrected_economics_store import (
    ClientOutcomeCorrectedEconomicsService,
    ClientOutcomeCorrectedEconomicsStore,
)
from lead_outcomes.client_outcome_reconciliation_service import ClientOutcomeReconciliationService
from lead_outcomes.client_outcome_cycle_idempotency_store import (
    ClientOutcomeCycleIdempotencyService,
    ClientOutcomeCycleIdempotencyStore,
)
from lead_outcomes.client_outcome_lifecycle_store import (
    ClientOutcomeLifecyclePersistenceService,
    ClientOutcomeLifecycleStore,
)
from lead_outcomes.client_outcome_order_factory import ClientOutcomeOrderFactory
from lead_outcomes.client_outcome_order_store import ClientOutcomeOrderPersistenceService, ClientOutcomeOrderStore
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog
from lead_outcomes.client_outcome_registry import ClientOutcomeRegistry
from lead_outcomes.client_outcome_selection_service import ClientOutcomeSelectionInput, ClientOutcomeSelectionService
from lead_outcomes.client_outcome_service import ClientOutcomeService
from lead_outcomes.client_verification_service import ClientVerificationService
from registry.base_registry import BaseRegistry
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry
from runtime.economic_core.client_outcome_bridge import build_client_outcome_truth_snapshot
from runtime.export.client_outcome_export import export_client_outcome_truth_snapshot, verify_client_outcome_truth_export


from entrypoints.api.client_outcome_routes.module_helpers import (
    _billable_record_from_input,
    _billable_record_payload,
    _merge_billable_record_metadata,
    _order_from_input,
    _order_from_response,
    _present_order,
    _revenue_payload,
)

def get_lifecycle(handlers, *, order_id: str, lead_id: str) -> ClientOutcomeLifecycleResponse:
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

def get_commercial_state(handlers, *, order_id: str, lead_id: str) -> ClientOutcomeCommercialStateResponse:
    state = handlers.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
    if state is None:
        return ClientOutcomeCommercialStateResponse(found=False)
    return ClientOutcomeCommercialStateResponse(found=True, **state)

def get_corrected_economics(handlers, *, order_id: str, lead_id: str) -> ClientOutcomeCorrectedEconomicsResponse:
    state = handlers.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
    if state is None:
        return ClientOutcomeCorrectedEconomicsResponse(found=False)
    refund_request_payload = state.get('refund_request')
    refund_request = None if refund_request_payload is not None else handlers.refund_request_bridge.to_request(now=datetime.now(timezone.utc), preview=state.get('refund_preview'))
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

def _resolve_tenant_id(handlers, *, order: ClientOutcomeOrder | None = None, lifecycle: dict[str, object] | None = None, commercial_state: dict[str, object] | None = None, corrected_economics: dict[str, object] | None = None, reconciliation: object | None = None) -> str:
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
    handlers.tenant_metrics_registry.set_gauge(tenant_id=normalized_tenant_id, metric_name='client_outcome.reconciliation_consistent', value=1.0 if consistent else 0.0, labels=labels)
    handlers.tenant_metrics_registry.set_gauge(tenant_id=normalized_tenant_id, metric_name='client_outcome.reconciliation_issue_count', value=float(issue_count), labels=labels)
    if issue_count:
        handlers.tenant_metrics_registry.emit(tenant_id=normalized_tenant_id, metric_name='client_outcome.reconciliation_issues_observed', kind=SLIKind.THROUGHPUT, value=float(issue_count), aggregation=MetricAggregation.SUM, labels=labels)

def _build_operational_metrics_widget(handlers, *, tenant_id: str) -> dict[str, object] | None:
    normalized_tenant_id = str(tenant_id or '').strip()
    if not normalized_tenant_id:
        return None
    metric_names = (
        'client_outcome.reconciliation_consistent',
        'client_outcome.reconciliation_issue_count',
        'client_outcome.reconciliation_issues_observed',
    )
    snapshots = {name: snap for name in metric_names if (snap := handlers.tenant_metrics_registry.metric_snapshot(tenant_id=normalized_tenant_id, metric_name=name)) is not None}
    return {
        'widget_id': 'client_outcome_operational_metrics',
        'kind': 'metrics',
        'payload': {
            'tenant_id': normalized_tenant_id,
            'metrics': snapshots,
        },
    } if snapshots else None

def _build_economic_truth_widget(handlers, *, order: object | None, lifecycle: dict[str, object] | None, commercial_state: dict[str, object] | None, corrected_economics: dict[str, object] | None, reconciliation_payload: dict[str, object] | None) -> tuple[dict[str, object], dict[str, object]]:
    truth_snapshot = build_client_outcome_truth_snapshot(
        order=order,
        lifecycle=lifecycle,
        commercial_state=commercial_state,
        corrected_economics=corrected_economics,
        reconciliation=reconciliation_payload,
    )
    exported_truth = export_client_outcome_truth_snapshot(truth_snapshot)
    return ({
        'widget_id': 'client_outcome_economic_truth',
        'kind': 'economic_truth',
        'payload': truth_snapshot,
    }, {
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
    })

def _build_recovery_bridge_widget(handlers, *, reconciliation_payload: dict[str, object] | None, corrected_economics: dict[str, object] | None) -> dict[str, object]:
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

def get_reconciliation(handlers, *, order_id: str, lead_id: str) -> ClientOutcomeReconciliationResponse:
    result = handlers.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    tenant_id = handlers._resolve_tenant_id(reconciliation=result)
    handlers._emit_reconciliation_metrics(tenant_id=tenant_id, result=result)
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

def get_admin_view(handlers, *, order_id: str, lead_id: str) -> ClientOutcomeAdminViewResponse:
    order = handlers.selection_service.get_order(order_id)
    lifecycle = handlers.lifecycle_service.get_state(order_id=order_id, lead_id=lead_id)
    commercial_state = handlers.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
    corrected_economics = handlers.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
    reconciliation = handlers.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    if order is None and lifecycle is None and commercial_state is None and corrected_economics is None and not reconciliation.found:
        return ClientOutcomeAdminViewResponse(found=False)
    tenant_id = handlers._resolve_tenant_id(order=order, lifecycle=lifecycle, commercial_state=commercial_state, corrected_economics=corrected_economics, reconciliation=reconciliation)
    handlers._emit_reconciliation_metrics(tenant_id=tenant_id, result=reconciliation)
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
        widgets.append({
            'widget_id': 'client_outcome_reconciliation',
            'kind': 'status',
            'payload': reconciliation_payload,
        })
    economic_truth_widget, export_widget = handlers._build_economic_truth_widget(order=order, lifecycle=lifecycle, commercial_state=commercial_state, corrected_economics=corrected_economics, reconciliation_payload=reconciliation_payload)
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
    if commercial_state is None or str((commercial_state or {}).get('commercial_status') or '') in {'', 'executed', 'verified', 'verification_rejected'}:
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
    widgets.append(handlers._build_recovery_bridge_widget(reconciliation_payload=reconciliation_payload, corrected_economics=corrected_economics))
    metrics_widget = handlers._build_operational_metrics_widget(tenant_id=tenant_id)
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

def build_admin_summary(handlers, *, request: ClientOutcomeAdminSummaryRequest) -> ClientOutcomeAdminSummaryResponse:
    order = _order_from_input(request.order)
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
