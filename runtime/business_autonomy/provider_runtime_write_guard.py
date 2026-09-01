from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_truth_matrix import ProviderTruthRow, provider_truth_map
from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from governance.approval_store import build_default_approval_store
from runtime.business_autonomy.provider_sync_runtime import ProviderSyncRuntimePlanner
from runtime.execution.governance_runtime_support import build_default_approval_execution_gate

CANON_PROVIDER_RUNTIME_WRITE_GUARD = True
PROVIDER_WRITE_BLOCK_STATUS = "rejected_provider_write_guard"


@dataclass(frozen=True)
class ProviderRuntimeWriteGuardDecision:
    provider_key: str
    operation: str
    mode: str
    is_write_operation: bool
    allowed: bool
    status: str
    reason: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        return {"provider_key": self.provider_key, "operation": self.operation, "mode": self.mode, "is_write_operation": self.is_write_operation, "allowed": self.allowed, "status": self.status, "reason": self.reason, "metadata": dict(self.metadata or {})}


@dataclass(frozen=True)
class ProviderRuntimeWriteGuard:
    planner: ProviderSyncRuntimePlanner = field(default_factory=ProviderSyncRuntimePlanner)
    approval_gate: Any | None = None
    approval_store: Any | None = None

    def evaluate(self, *, provider: ProviderDefinition, operation: str, mode: str, tenant_id: str = "", business_id: str = "", payload: Mapping[str, Any] | None = None) -> ProviderRuntimeWriteGuardDecision:
        normalized_mode, normalized_operation = str(mode or "dry_run").strip().lower() or "dry_run", str(operation or "").strip()
        plan, truth = self.planner.describe(provider), provider_truth_map().get(provider.provider_key)
        is_write = normalized_operation in set(plan.write_operations)
        base_metadata = {"truth_source": "application.business_autonomy.provider_truth_matrix", "planner_source": "runtime.business_autonomy.provider_sync_runtime.ProviderSyncRuntimePlanner", "read_operations": list(plan.read_operations), "write_operations": list(plan.write_operations), "truth": {} if truth is None else self._truth_metadata(truth)}
        decision_args = {"provider_key": provider.provider_key, "operation": normalized_operation, "mode": normalized_mode}
        if normalized_mode != "live":
            return ProviderRuntimeWriteGuardDecision(**decision_args, is_write_operation=is_write, allowed=True, status="allowed_non_live_mode", reason="non_live_mode_is_read_only_or_prepared", metadata=base_metadata)
        if not is_write:
            return ProviderRuntimeWriteGuardDecision(**decision_args, is_write_operation=False, allowed=True, status="allowed_live_read_operation", reason="operation_not_in_provider_write_operations", metadata=base_metadata)
        if truth is None or not truth.write_supported:
            reason = "provider_truth_row_missing" if truth is None else "write_supported_false_in_provider_truth_matrix"
            return ProviderRuntimeWriteGuardDecision(**decision_args, is_write_operation=True, allowed=False, status=PROVIDER_WRITE_BLOCK_STATUS, reason=reason, metadata=base_metadata)
        if not truth.approval_required:
            return ProviderRuntimeWriteGuardDecision(**decision_args, is_write_operation=True, allowed=True, status="allowed_live_write_operation", reason="provider_truth_matrix_allows_guarded_write", metadata=base_metadata)
        approval = self._approval_evidence(provider=provider, operation=normalized_operation, tenant_id=tenant_id, business_id=business_id, payload=payload)
        return ProviderRuntimeWriteGuardDecision(**decision_args, is_write_operation=True, allowed=bool(approval.get("allowed")), status="allowed_live_write_operation" if approval.get("allowed") else PROVIDER_WRITE_BLOCK_STATUS, reason=str(approval.get("reason") or "approval_required"), metadata={**base_metadata, "approval": approval})

    def _approval_evidence(self, *, provider: ProviderDefinition, operation: str, tenant_id: str, business_id: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        raw, visible = dict(payload or {}), {str(k): v for k, v in dict(payload or {}).items() if not str(k).startswith("_")}
        approval = raw.get("_approval") if isinstance(raw.get("_approval"), Mapping) else {}
        decision_id, execution_id = str(approval.get("decision_id") or "").strip(), str(approval.get("execution_id") or "").strip()
        if not str(tenant_id or "").strip() or not str(business_id or "").strip() or not decision_id or not execution_id:
            return {"allowed": False, "reason": "approval_context_missing", "required_fields": ["tenant_id", "business_id", "_approval.decision_id", "_approval.execution_id", "_approval.approval_id"]}
        action_name, gate = f"provider.{provider.provider_key}.{operation}", self.approval_gate or build_default_approval_execution_gate()
        business_scope = str(business_id).strip()
        resume_context = {"provider_key": provider.provider_key, "business_id": business_scope, "operation": operation, "payload": visible}
        ctx = ActionExecutionContext(tenant_id=str(tenant_id).strip(), user_id=None, action_name=action_name, payload={"provider_key": provider.provider_key, "business_id": business_scope, "operation": operation, "payload": visible}, metadata={"decision_id": decision_id, "approval_resume_context": resume_context}, execution_id=execution_id)
        impact = ActionImpact(action_name=action_name, category=ActionCategory.OUTBOUND, outbound_count=1, requires_human_approval=True, dimensions={"provider_key": provider.provider_key, "business_id": business_scope})
        verdict = gate.evaluate(ctx=ctx, impact=impact, autonomy_tier="supervised", external_confirmation_mode="required", approval_policy={"force_human_approval": True, "allow_operator_override": False, "auto_submit_approval": True}, metadata={"decision_id": decision_id, "requires_manual_review": True, "tags": ["provider_outbound", provider.provider_key]}, approval_id=str(approval.get("approval_id") or "").strip() or None, requested_by="provider_runtime")
        evidence = verdict.to_dict()
        if verdict.allowed:
            stored_fingerprint = '' if (record := (self.approval_store or build_default_approval_store()).get(str(verdict.approval_id or ''))) is None else str(dict(record.request.metadata).get('approval_request_fingerprint') or '').strip()
            if not stored_fingerprint:
                return {**evidence, "allowed": False, "status": PROVIDER_WRITE_BLOCK_STATUS, "reason": "approval_request_fingerprint_missing"}
            evidence['metadata'] = {**dict(evidence.get('metadata') or {}), 'approval_request_fingerprint': stored_fingerprint}
        return evidence

    def _truth_metadata(self, truth: ProviderTruthRow) -> dict[str, Any]:
        return {name: getattr(truth, name) for name in ("status", "live_ready", "read_only_supported", "write_supported", "approval_required", "risk_level", "admin_visible")}


__all__ = ["CANON_PROVIDER_RUNTIME_WRITE_GUARD", "PROVIDER_WRITE_BLOCK_STATUS", "ProviderRuntimeWriteGuard", "ProviderRuntimeWriteGuardDecision"]
