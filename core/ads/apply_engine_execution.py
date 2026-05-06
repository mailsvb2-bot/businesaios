from __future__ import annotations

from typing import Any, Dict, Optional

from core.ads.apply.audit import build_audit_event
from core.ads.apply.contract import AdsApplyRequest, AdsApplyResult
from core.ads.apply_engine_helpers import AdsApplyPort, best_effort_rollback


def build_dry_run_result(*, req: AdsApplyRequest, idem_norm: str, planned_budget_minor: int, planned_changes: int) -> tuple[dict[str, Any], AdsApplyResult]:
    result = {
        "dry_run": True,
        "planned_budget_minor": int(planned_budget_minor),
        "planned_changes": int(planned_changes),
    }
    ev = build_audit_event(
        tenant_id=str(req.tenant_id),
        user_id=str(req.user_id),
        kind="dry_run",
        plan=req.plan,
        status="dry_run",
        detail=result,
        idempotency_key=idem_norm,
        reason=req.reason,
    )
    return result, AdsApplyResult(status="dry_run", detail=result, audit_event=ev)


def perform_apply_flow(
    *,
    apply_port: AdsApplyPort,
    req: AdsApplyRequest,
    idem_norm: str,
    planned_changes: int,
) -> tuple[str, AdsApplyResult]:
    tenant_id = str(req.tenant_id)
    try:
        out = apply_port.perform_apply(tenant_id, req.plan)
        result: Dict[str, Any] = {"status": "applied", "provider": out}
        ev = build_audit_event(
            tenant_id=tenant_id,
            user_id=str(req.user_id),
            kind="apply",
            plan=req.plan,
            status="applied",
            detail={"planned_changes": int(planned_changes)},
            idempotency_key=idem_norm,
            reason=req.reason,
        )
        return "done", AdsApplyResult(status="applied", detail=result, audit_event=ev)
    except Exception as e:
        rollback_detail: Optional[Dict[str, Any]] = None
        if bool(req.rollback_on_fail):
            rollback_detail = best_effort_rollback(apply_port, tenant_id=tenant_id, plan=req.plan)
        ev = build_audit_event(
            tenant_id=tenant_id,
            user_id=str(req.user_id),
            kind="apply",
            plan=req.plan,
            status="failed",
            detail={"error": str(e), "rollback": rollback_detail},
            idempotency_key=idem_norm,
            reason=req.reason,
            error_code="APPLY_FAILED",
        )
        return "failed", AdsApplyResult(status="failed", detail={"error": str(e), "rollback": rollback_detail}, audit_event=ev)
