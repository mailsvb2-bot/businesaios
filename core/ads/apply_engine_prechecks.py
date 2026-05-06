from __future__ import annotations

from typing import Any

from core.ads.apply.audit import build_audit_event
from core.ads.apply.contract import AdsApplyRequest, AdsApplyResult
from core.ads.apply.limits import planned_stats
from core.ads.apply_gate import AdsApplyState, assert_ads_apply_allowed
from core.ads.apply_engine_results import blocked_result
from core.governance.guards.feedback_loop_guard import FeedbackLoopGuard


def check_kill_switch(*, enabled: bool, reason: str | None, req: AdsApplyRequest, idem_norm: str) -> AdsApplyResult | None:
    if enabled:
        return None
    return blocked_result(
        tenant_id=str(req.tenant_id),
        user_id=str(req.user_id),
        kind="kill" "_switch",
        plan=req.plan,
        idem_norm=idem_norm,
        reason=req.reason,
        code="ADS_KILL_SWITCH",
        detail={"message": "kill" "_switch", "reason": str(reason or "")},
    )


def check_rate_limit(*, allowed: bool, req: AdsApplyRequest, idem_norm: str) -> AdsApplyResult | None:
    if allowed:
        return None
    return blocked_result(
        tenant_id=str(req.tenant_id),
        user_id=str(req.user_id),
        kind="rate_limit",
        plan=req.plan,
        idem_norm=idem_norm,
        reason=req.reason,
        code="ADS_RATE_LIMITED",
        detail={"message": "rate_limited"},
    )


def build_duplicate_result(*, previous: Any, req: AdsApplyRequest, idem_norm: str) -> AdsApplyResult:
    ev = build_audit_event(
        tenant_id=str(req.tenant_id),
        user_id=str(req.user_id),
        kind="idempotency",
        plan=req.plan,
        status="duplicate",
        detail={"previous": previous},
        idempotency_key=idem_norm,
        reason=req.reason,
        error_code="DUPLICATE",
    )
    return AdsApplyResult(status="duplicate", detail={"previous": previous}, audit_event=ev)


def evaluate_gate_and_feedback(
    *,
    req: AdsApplyRequest,
    idem_norm: str,
    gate_state: AdsApplyState,
    hard_env_enabled: bool,
    max_daily_budget_minor: int,
    max_changes_per_day: int,
    feedback_guard: FeedbackLoopGuard | None,
) -> tuple[AdsApplyResult | None, int, int, str | None]:
    planned_budget_minor, planned_changes = planned_stats(req.plan)
    err = assert_ads_apply_allowed(
        state=gate_state,
        hard_env_enabled=bool(hard_env_enabled),
        max_daily_budget_minor=int(max_daily_budget_minor),
        planned_daily_budget_minor=int(planned_budget_minor),
        max_changes_per_day=int(max_changes_per_day),
        planned_changes=int(planned_changes),
    )
    if err:
        ev = build_audit_event(
            tenant_id=str(req.tenant_id),
            user_id=str(req.user_id),
            kind="gate",
            plan=req.plan,
            status="blocked",
            detail={
                "error": str(err),
                "planned_budget_minor": int(planned_budget_minor),
                "planned_changes": int(planned_changes),
            },
            idempotency_key=idem_norm,
            reason=req.reason,
            error_code=str(err),
        )
        return AdsApplyResult(status="blocked", detail={"error": str(err)}, audit_event=ev), int(planned_budget_minor), int(planned_changes), str(err)

    if feedback_guard is not None:
        guard = feedback_guard.check_planned_budget(
            tenant_id=str(req.tenant_id),
            planned_daily_budget_minor=int(planned_budget_minor),
        )
        if not guard.allowed:
            code = str(guard.code or "ADS_RUNAWAY_FEEDBACK_LOOP")
            ev = build_audit_event(
                tenant_id=str(req.tenant_id),
                user_id=str(req.user_id),
                kind="feedback_loop_guard",
                plan=req.plan,
                status="blocked",
                detail={
                    "message": str(guard.message or ""),
                    "planned_budget_minor": int(planned_budget_minor),
                    "planned_changes": int(planned_changes),
                },
                idempotency_key=idem_norm,
                reason=req.reason,
                error_code=code,
            )
            return AdsApplyResult(
                status="blocked",
                detail={"error": code, "message": str(guard.message or "")},
                audit_event=ev,
            ), int(planned_budget_minor), int(planned_changes), code

    return None, int(planned_budget_minor), int(planned_changes), None
