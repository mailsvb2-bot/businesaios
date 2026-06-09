from __future__ import annotations

from dataclasses import asdict
from typing import Any
from collections.abc import Mapping

from contracts.action_impact_contract import ActionCategory, ActionImpact
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from execution.operator_override_store import build_default_operator_override_store
from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import PersistentApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog
from governance.rbac_contract import ActorContext, RoleId
from governance.tenant_policy_overrides import PersistentTenantPolicyOverrideRegistry
from runtime.execution.operational_budget_runtime import build_action_execution_context

CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _approval_gate_enabled(*, payload: dict[str, Any], meta: dict[str, Any], impact: ActionImpact) -> bool:
    approval_policy = _safe_dict(payload.get("approval_policy"))
    if approval_policy:
        return True
    if bool(payload.get("approval_gate_enforce") or meta.get("approval_gate_enforce")):
        return True
    if bool(payload.get("requires_human_approval") or meta.get("requires_human_approval")):
        return True
    if str(payload.get("external_confirmation_mode") or meta.get("external_confirmation_mode") or "").strip() and bool(payload.get("approval_policy") or meta.get("approval_policy")):
        return True
    return False


def _build_default_approval_execution_gate() -> ApprovalExecutionGate:
    audit_log = PersistentGovernanceAuditLog()
    tenant_overrides = PersistentTenantPolicyOverrideRegistry(audit_log=audit_log)
    approval_workflow = ApprovalWorkflow(store=PersistentApprovalStore(), audit_log=audit_log)
    return ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(tenant_overrides=tenant_overrides),
        ),
        approval_workflow=approval_workflow,
        audit_log=audit_log,
    )


def _execution_approval_gate(executor: Any) -> ApprovalExecutionGate:
    gate = getattr(executor, "_approval_execution_gate", None)
    if gate is None:
        gate = _build_default_approval_execution_gate()
        setattr(executor, "_approval_execution_gate", gate)
    return gate


def _execution_operator_override_store(executor: Any):
    store = getattr(executor, "_operator_override_store", None)
    if store is None:
        store = build_default_operator_override_store()
        setattr(executor, "_operator_override_store", store)
    return store


def _extract_operator_override_id(*, payload: dict[str, Any], meta: dict[str, Any]) -> str | None:
    override_id = str(
        payload.get("operator_override_id")
        or meta.get("operator_override_id")
        or _safe_dict(payload.get("operator_override")).get("override_id")
        or _safe_dict(meta.get("operator_override")).get("override_id")
        or ""
    ).strip()
    return override_id or None


def _load_operator_override(*, executor: Any, override_id: str):
    return _execution_operator_override_store(executor).get(override_id)


def _consume_operator_override(*, executor: Any, record: Any, execution_id: str) -> Any:
    consumed = record.consume_once(execution_id=execution_id)
    return _execution_operator_override_store(executor).save(consumed)


def _materialize_operator_override_approval(*, guard: Any, ctx: Any, impact: ActionImpact, operator_override: Any) -> str:
    workflow = getattr(guard, "_approval_workflow", None)
    decision = getattr(operator_override, "decision", None)
    if workflow is None or decision is None:
        raise RuntimeError("operator_override_approval_materialization_unavailable")
    approval_id = f"ap-override-{operator_override.request.override_id}"
    existing = workflow.get(approval_id)
    if existing is None:
        request = ApprovalRequest(
            approval_id=approval_id,
            tenant_id=ctx.tenant_id,
            subject_type="action_execution",
            subject_id=str(ctx.execution_id or ctx.action_name),
            requested_by=operator_override.request.requested_by,
            reason="operator_override_materialized_as_execution_approval",
            required_role_groups=((decision.role_id,),),
            min_distinct_approvers=1,
            prohibit_self_approval=False,
            metadata={
                "decision_id": operator_override.request.decision_id,
                "action_name": operator_override.request.action_name,
                "subject_fingerprint": operator_override.request.subject_fingerprint,
                "approval_source": "operator_override",
                "operator_override_id": operator_override.request.override_id,
                "impact_category": impact.category.value,
            },
        )
        workflow.submit(request)
    current = workflow.get(approval_id)
    if current is None or getattr(current, "status", None).value != "approved":
        _apply_approval_workflow_resolution(
            workflow=workflow,
            approval_decision=ApprovalDecision(
                approval_id=approval_id,
                tenant_id=ctx.tenant_id,
                actor_id=decision.actor_id,
                role_id=decision.role_id,
                outcome=ApprovalOutcome.APPROVE,
                rationale=decision.note,
                metadata={
                    "approval_source": "operator_override",
                    "operator_override_id": operator_override.request.override_id,
                },
            ),
        )
    return approval_id


def _apply_approval_workflow_resolution(*, workflow: ApprovalWorkflow, approval_decision: ApprovalDecision) -> None:
    workflow.resolve(approval_decision)


def _gate_metadata(*, payload: dict[str, Any], meta: dict[str, Any], impact: ActionImpact) -> dict[str, Any]:
    approval_policy = _safe_dict(payload.get("approval_policy")) or _safe_dict(meta.get("approval_policy"))
    return {
        "approval_policy": approval_policy,
        "approval_required": bool(payload.get("requires_human_approval") or meta.get("requires_human_approval")),
        "external_confirmation_mode": str(payload.get("external_confirmation_mode") or meta.get("external_confirmation_mode") or "").strip(),
        "impact_category": impact.category.value,
        "impact_risk_score": int(impact.risk_score),
    }


def _build_approval_output(*, approval_id: str, reason: str, impact: ActionImpact, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "approval_required",
        "approval_id": approval_id,
        "reason": reason,
        "impact": asdict(impact),
        "metadata": dict(metadata),
    }


def _build_resume_governance_hint(*, approval_id: str, override_id: str | None = None) -> dict[str, Any]:
    hint = {"approval_id": approval_id, "resume_required": True}
    if override_id:
        hint["operator_override_id"] = override_id
    return hint


def _emit_resume_event(*, executor: Any, env: Any, approval_id: str, override_id: str | None = None) -> None:
    events = getattr(executor, "_events", None)
    if events is None or not hasattr(events, "emit"):
        return
    try:
        events.emit(
            event_type="governance_execution_paused",
            source="governance",
            user_id=str(getattr(getattr(env, "decision", None), "user_id", "system") or "system"),
            decision_id=str(getattr(getattr(env, "decision", None), "decision_id", "") or ""),
            correlation_id=str(getattr(getattr(env, "decision", None), "correlation_id", "") or ""),
            payload={"approval_id": approval_id, "operator_override_id": override_id},
        )
    except Exception:
        return


def _governance_audit_log(executor: Any, guard: Any | None = None):
    approval_gate = getattr(executor, "_approval_execution_gate", None)
    guard_workflow = getattr(guard, "_approval_workflow", None) if guard is not None else None
    gate_workflow = getattr(approval_gate, "_approval_workflow", None) if approval_gate is not None else None

    candidates = (
        getattr(guard, "_audit_log", None) if guard is not None else None,
        getattr(approval_gate, "_audit_log", None) if approval_gate is not None else None,
        getattr(guard_workflow, "_audit_log", None) if guard_workflow is not None else None,
        getattr(gate_workflow, "_audit_log", None) if gate_workflow is not None else None,
        getattr(executor, "_governance_audit_log", None),
    )
    for audit_log in candidates:
        if audit_log is not None and hasattr(audit_log, "append"):
            return audit_log

    audit_log = PersistentGovernanceAuditLog()
    setattr(executor, "_governance_audit_log", audit_log)
    return audit_log


def _append_governance_audit(
    *,
    executor: Any,
    event: GovernanceAuditEvent | None = None,
    guard: Any | None = None,
    tenant_id: str | None = None,
    event_type: str | None = None,
    payload: Mapping[str, object] | None = None,
) -> None:
    try:
        audit_event = event
        if audit_event is None:
            audit_event = GovernanceAuditEvent(
                event_type=str(event_type or "").strip(),
                tenant_id=str(tenant_id or "").strip() or "unknown",
                payload=dict(payload or {}),
            )
        _governance_audit_log(executor, guard=guard).append(audit_event)
    except Exception:
        return


def _should_enforce(*, executor: Any, payload: dict[str, Any], meta: dict[str, Any], impact: ActionImpact) -> bool:
    if getattr(executor, "_governance_execution_guard", None) is not None:
        return True
    return _approval_gate_enabled(payload=payload, meta=meta, impact=impact)


def _build_actor(*, payload: dict[str, Any], meta: dict[str, Any]) -> ActorContext:
    actor_id = str(payload.get("actor_id") or meta.get("actor_id") or payload.get("user_id") or meta.get("user_id") or "system")
    roles = _normalize_roles(payload.get("roles") or meta.get("roles") or ("owner",))
    return ActorContext(actor_id=actor_id, roles=roles)


def _normalize_roles(value: object) -> tuple[RoleId, ...]:
    if isinstance(value, (list, tuple, set)):
        raw = tuple(str(item) for item in value)
    else:
        raw = (str(value or "owner"),)
    result: list[RoleId] = []
    for item in raw:
        token = str(item or "").strip()
        if not token:
            continue
        try:
            result.append(RoleId(token))
        except ValueError:
            continue
    return tuple(result or (RoleId.OWNER,))


def _build_impact(*, action_name: str, payload: dict[str, Any], meta: dict[str, Any]) -> ActionImpact:
    budget_delta = _normalize_non_negative_int(payload.get("budget_delta_cents") or meta.get("budget_delta_cents"))
    external_write = bool(payload.get("external_write") or meta.get("external_write") or payload.get("provider") or meta.get("provider"))
    requires_human = bool(payload.get("requires_human_approval") or meta.get("requires_human_approval"))
    category = _infer_category(action_name)
    return build_action_execution_context(
        action_name=action_name,
        category=category,
        budget_delta_cents=budget_delta,
        external_write=external_write,
        requires_human=requires_human,
    )


def _normalize_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _infer_category(action_name: str) -> ActionCategory:
    action = str(action_name or "").lower()
    hints = {
        "refund": ActionCategory.FINANCIAL_REVERSAL,
        "reverse": ActionCategory.FINANCIAL_REVERSAL,
        "payment": ActionCategory.FINANCIAL_WRITE,
        "charge": ActionCategory.FINANCIAL_WRITE,
        "transfer": ActionCategory.FINANCIAL_WRITE,
        "ad": ActionCategory.AD_SPEND,
        "campaign": ActionCategory.AD_SPEND,
        "publish": ActionCategory.PUBLICATION,
        "post": ActionCategory.PUBLICATION,
        "send": ActionCategory.OUTBOUND,
        "message": ActionCategory.OUTBOUND,
        "email": ActionCategory.OUTBOUND,
        "budget": ActionCategory.BUDGET_CHANGE,
        "price": ActionCategory.STRATEGIC_CHANGE,
        "strategy": ActionCategory.STRATEGIC_CHANGE,
        "rollback": ActionCategory.ROLLBACK,
        "revert": ActionCategory.ROLLBACK,
        "execute": ActionCategory.EXECUTION,
        "run": ActionCategory.EXECUTION,
        "update": ActionCategory.INTERNAL_WRITE,
        "write": ActionCategory.INTERNAL_WRITE,
        "save": ActionCategory.INTERNAL_WRITE,
    }
    for fragment, category in hints.items():
        if fragment in action:
            return category
    return ActionCategory.UNKNOWN


def _extract_approval_id(*, payload: dict[str, Any], meta: dict[str, Any]) -> str | None:
    value = payload.get("approval_id") or meta.get("approval_id")
    normalized = str(value or "").strip()
    return normalized or None


__all__ = [
    "_safe_dict",
    "_approval_gate_enabled",
    "_build_default_approval_execution_gate",
    "_execution_approval_gate",
    "_execution_operator_override_store",
    "_extract_operator_override_id",
    "_load_operator_override",
    "_consume_operator_override",
    "_materialize_operator_override_approval",
    "_apply_approval_workflow_resolution",
    "_gate_metadata",
    "_build_approval_output",
    "_build_resume_governance_hint",
    "_emit_resume_event",
    "_governance_audit_log",
    "_append_governance_audit",
    "_should_enforce",
    "_build_actor",
    "_normalize_roles",
    "_build_impact",
    "_normalize_non_negative_int",
    "_infer_category",
    "_extract_approval_id",
    "CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE",
]
