from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict
from typing import Any

from contracts.action_impact_contract import ActionCategory, ActionImpact
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from execution.operator_override_store import build_default_operator_override_store
from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import build_default_approval_store
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.control_plane_audit_log import PersistentGovernanceAuditLog
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
    return bool(
        str(payload.get("external_confirmation_mode") or meta.get("external_confirmation_mode") or "").strip()
        and (payload.get("approval_policy") or meta.get("approval_policy"))
    )


def _build_default_approval_execution_gate() -> ApprovalExecutionGate:
    audit_log = PersistentGovernanceAuditLog()
    tenant_overrides = PersistentTenantPolicyOverrideRegistry(audit_log=audit_log)
    approval_workflow = ApprovalWorkflow(store=build_default_approval_store(), audit_log=audit_log)
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
        executor._approval_execution_gate = gate
    return gate


def _execution_operator_override_store(executor: Any):
    store = getattr(executor, "_operator_override_store", None)
    if store is None:
        store = build_default_operator_override_store()
        executor._operator_override_store = store
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


def _materialize_operator_override_approval(
    *, guard: Any, ctx: Any, impact: ActionImpact, operator_override: Any
) -> str:
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
            action_name=ctx.action_name,
            subject_fingerprint=ctx.subject_fingerprint(),
            requested_by=operator_override.request.requested_by,
            required_roles=operator_override.request.required_roles,
            metadata={"source": "operator_override", "override_id": operator_override.request.override_id},
        )
        workflow.request(request)
        workflow.decide(
            ApprovalDecision(
                approval_id=approval_id,
                tenant_id=ctx.tenant_id,
                actor_id=decision.decided_by,
                role_id=decision.role_id,
                outcome=ApprovalOutcome.APPROVE,
                rationale=decision.rationale,
            )
        )
    return approval_id


def _extract_approval_id(*, payload: dict[str, Any], meta: dict[str, Any]) -> str | None:
    approval_id = str(
        payload.get("approval_id")
        or meta.get("approval_id")
        or _safe_dict(payload.get("approval")).get("approval_id")
        or _safe_dict(meta.get("approval")).get("approval_id")
        or ""
    ).strip()
    return approval_id or None


def _build_actor(*, tenant_id: str, payload: dict[str, Any], meta: dict[str, Any]) -> ActorContext:
    actor_payload = _safe_dict(payload.get("actor")) or _safe_dict(meta.get("actor"))
    role_value = str(actor_payload.get("role_id") or payload.get("role_id") or meta.get("role_id") or RoleId.VIEWER.value)
    try:
        role_id = RoleId(role_value)
    except ValueError:
        role_id = RoleId.VIEWER
    actor_id = str(actor_payload.get("actor_id") or payload.get("actor_id") or meta.get("actor_id") or "runtime").strip()
    return ActorContext(actor_id=actor_id, tenant_id=tenant_id, role_id=role_id)


def _normalize_roles(value: object) -> tuple[RoleId, ...]:
    if value is None:
        return ()
    items: Iterable[object]
    if isinstance(value, str | RoleId):
        items = (value,)
    elif isinstance(value, Iterable):
        items = value
    else:
        return ()
    out: list[RoleId] = []
    for item in items:
        raw = item.value if isinstance(item, RoleId) else str(item or "").strip()
        try:
            role = RoleId(raw)
        except ValueError:
            continue
        if role not in out:
            out.append(role)
    return tuple(out)


def _normalize_non_negative_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _infer_category(*, action_name: str, payload: dict[str, Any], meta: dict[str, Any]) -> ActionCategory:
    raw = str(payload.get("action_category") or meta.get("action_category") or "").strip().lower()
    if raw:
        try:
            return ActionCategory(raw)
        except ValueError:
            pass
    lowered = str(action_name or "").lower()
    if any(token in lowered for token in ("message", "notify", "email", "telegram", "whatsapp", "sms")):
        return ActionCategory.OUTBOUND
    if any(token in lowered for token in ("delete", "remove", "revoke", "cancel")):
        return ActionCategory.DESTRUCTIVE
    if any(token in lowered for token in ("payment", "charge", "refund", "payout", "invoice")):
        return ActionCategory.FINANCIAL
    return ActionCategory.INTERNAL


def _build_impact(*, action_name: str, payload: dict[str, Any], meta: dict[str, Any]) -> ActionImpact:
    impact_payload = _safe_dict(payload.get("action_impact")) or _safe_dict(meta.get("action_impact"))
    category = _infer_category(action_name=action_name, payload=impact_payload or payload, meta=meta)
    return ActionImpact(
        action_name=action_name,
        category=category,
        financial_amount_rub=float(impact_payload.get("financial_amount_rub") or payload.get("financial_amount_rub") or 0.0),
        outbound_count=_normalize_non_negative_int(impact_payload.get("outbound_count", payload.get("outbound_count", 0))),
        destructive=bool(impact_payload.get("destructive") or payload.get("destructive")),
        irreversible=bool(impact_payload.get("irreversible") or payload.get("irreversible")),
        requires_human_approval=bool(impact_payload.get("requires_human_approval") or payload.get("requires_human_approval")),
        confidence=float(impact_payload.get("confidence") or payload.get("confidence") or 1.0),
    )


def _gate_metadata(*, payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    metadata = _safe_dict(meta)
    metadata.update(_safe_dict(payload.get("governance_metadata")))
    for key in (
        "decision_id",
        "correlation_id",
        "external_confirmation_mode",
        "requires_human_approval",
        "requires_manual_review",
        "tags",
    ):
        if key in payload and key not in metadata:
            metadata[key] = payload[key]
    return metadata


def _should_enforce(*, payload: dict[str, Any], meta: dict[str, Any], impact: ActionImpact) -> bool:
    return _approval_gate_enabled(payload=payload, meta=meta, impact=impact)


def _apply_approval_workflow_resolution(*, gate: ApprovalExecutionGate, approval_id: str | None, ctx: Any, impact: ActionImpact, payload: dict[str, Any], meta: dict[str, Any]):
    policy = _safe_dict(payload.get("approval_policy")) or _safe_dict(meta.get("approval_policy"))
    return gate.evaluate(
        ctx=ctx,
        impact=impact,
        external_confirmation_mode=str(payload.get("external_confirmation_mode") or meta.get("external_confirmation_mode") or "").strip() or None,
        approval_policy=policy,
        metadata=_gate_metadata(payload=payload, meta=meta),
        approval_id=approval_id,
        requested_by=str(payload.get("requested_by") or meta.get("requested_by") or ctx.user_id or "runtime"),
    )


def _build_approval_output(verdict: Any) -> dict[str, Any]:
    if verdict is None:
        return {}
    if hasattr(verdict, "to_dict"):
        return verdict.to_dict()
    if hasattr(verdict, "__dataclass_fields__"):
        return asdict(verdict)
    return {"allowed": bool(getattr(verdict, "allowed", False)), "reason": str(getattr(verdict, "reason", ""))}


def _build_resume_governance_hint(*, approval_id: str, verdict: Any) -> dict[str, Any]:
    return {
        "approval_id": approval_id,
        "allowed": bool(getattr(verdict, "allowed", False)),
        "reason": str(getattr(verdict, "reason", "")),
    }


def _emit_resume_event(*, event_sink: Any, payload: dict[str, Any]) -> None:
    if event_sink is None:
        return
    emit = getattr(event_sink, "append", None) or getattr(event_sink, "emit", None)
    if callable(emit):
        emit(payload)


class GovernanceExecutionBlocked(RuntimeError):
    def __init__(self, reason: str, *, approval: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.approval = dict(approval or {})


def review_governance_execution(*, executor: Any, action_name: str, payload: dict[str, Any], meta: dict[str, Any]):
    body = dict(payload or {})
    metadata = dict(meta or {})
    ctx = build_action_execution_context(executor=executor, action_name=action_name, payload=body, meta=metadata)
    impact = _build_impact(action_name=action_name, payload=body, meta=metadata)
    if not _should_enforce(payload=body, meta=metadata, impact=impact):
        return None
    gate = _execution_approval_gate(executor)
    override_id = _extract_operator_override_id(payload=body, meta=metadata)
    approval_id = _extract_approval_id(payload=body, meta=metadata)
    if override_id:
        override = _load_operator_override(executor=executor, override_id=override_id)
        if override is not None:
            approval_id = _materialize_operator_override_approval(guard=gate, ctx=ctx, impact=impact, operator_override=override)
    verdict = _apply_approval_workflow_resolution(gate=gate, approval_id=approval_id, ctx=ctx, impact=impact, payload=body, meta=metadata)
    if approval_id and verdict.allowed:
        return _build_resume_governance_hint(approval_id=approval_id, verdict=verdict)
    if verdict.allowed:
        return None
    approval = _build_approval_output(verdict)
    raise GovernanceExecutionBlocked(str(verdict.reason), approval=approval)
