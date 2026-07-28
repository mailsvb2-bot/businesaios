from __future__ import annotations

from entrypoints.api.client_outcome_reconciliation_models import ClientOutcomeReconciliationResponse
from entrypoints.api.client_outcome_routes.module_helpers import _require_order_tenant


def get_reconciliation(
    handlers,
    *,
    order_id: str,
    lead_id: str,
    tenant_id: str | None = None,
) -> ClientOutcomeReconciliationResponse:
    """Read reconciliation with explicit tenant enforcement at HTTP boundaries.

    Public routes always pass ``tenant_id``. Historical trusted in-process callers
    may omit it; reconciliation then derives the tenant from persisted commercial,
    economics, or lifecycle state and never accepts a caller-supplied foreign tenant.
    """

    if tenant_id is not None:
        _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    result = handlers.reconciliation_service.reconcile(order_id=order_id, lead_id=lead_id)
    resolved_tenant_id = handlers._resolve_tenant_id(reconciliation=result)
    if tenant_id is not None and resolved_tenant_id and str(resolved_tenant_id) != str(tenant_id):
        raise PermissionError('client_outcome_reconciliation_tenant_mismatch')
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


__all__ = ['get_reconciliation']
