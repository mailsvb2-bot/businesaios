from __future__ import annotations

import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import ApprovalStoreContract, build_default_approval_store
from governance.approval_workflow import ApprovalWorkflow
from governance.rbac_contract import RoleId
from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
    is_operator_override_role_allowed,
)
from execution.operator_override_store import (
    InMemoryOperatorOverrideStore,
    build_default_operator_override_store,
)
from governance.control_plane_audit_log import GovernanceAuditLogContract, PersistentGovernanceAuditLog
from entrypoints.api.approval_route_support import (
    append_control_plane_audit,
    audit_payload_summary,
    build_control_plane_timeline,
    latest_records,
    lifecycle_counts,
    list_tenant_records,
    override_action_summary,
    override_record_dict,
    record_dict,
    resume_candidates,
    route_action_summary,
    safe_dict,
    safe_int,
    safe_iso,
    text,
)


CANON_API_APPROVAL_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_APPROVAL_ROUTE_HANDLERS = True

@dataclass(frozen=True)
class ApprovalRouteHandlers:
    approval_store: ApprovalStoreContract = field(default_factory=build_default_approval_store)
    operator_override_store: object = field(default_factory=build_default_operator_override_store)
    audit_log: GovernanceAuditLogContract = field(default_factory=PersistentGovernanceAuditLog)
    approval_workflow: ApprovalWorkflow = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'approval_workflow', ApprovalWorkflow(store=self.approval_store, audit_log=self.audit_log))

    def submit(
        self,
        *,
        tenant_id: str,
        subject_type: str,
        subject_id: str,
        requested_by: str,
        reason: str,
        required_role_groups: tuple[tuple[RoleId, ...], ...] = (),
        min_distinct_approvers: int = 1,
        prohibit_self_approval: bool = True,
        expires_at: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        normalized_subject_type = text(subject_type)
        normalized_subject_id = text(subject_id)
        normalized_requested_by = text(requested_by)
        normalized_reason = text(reason)
        if not normalized_subject_type:
            raise ValueError('subject_type is required')
        if not normalized_subject_id:
            raise ValueError('subject_id is required')
        if not normalized_requested_by:
            raise ValueError('requested_by is required')
        if not normalized_reason:
            raise ValueError('reason is required')
        normalized_metadata = dict(metadata or {})
        request = ApprovalRequest(
            approval_id=f'appr_{secrets.token_hex(8)}',
            tenant_id=tenant_id,
            subject_type=normalized_subject_type,
            subject_id=normalized_subject_id,
            requested_by=normalized_requested_by,
            reason=normalized_reason,
            required_role_groups=required_role_groups,
            min_distinct_approvers=min_distinct_approvers,
            prohibit_self_approval=prohibit_self_approval,
            expires_at=expires_at,
            metadata=normalized_metadata,
        )
        record = self.approval_workflow.submit(request)
        return record_dict(record)

    def submit_execution_approval(
        self,
        *,
        tenant_id: str,
        execution_id: str,
        decision_id: str,
        action_name: str,
        requested_by: str,
        reason: str,
        required_role_groups: tuple[tuple[RoleId, ...], ...],
        min_distinct_approvers: int,
        subject_fingerprint: str,
        autonomy_tier: str = 'supervised',
        external_confirmation_mode: str = 'required',
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        normalized_execution_id = text(execution_id)
        normalized_metadata = {
            **dict(metadata or {}),
            'decision_id': text(decision_id),
            'action_name': text(action_name),
            'subject_fingerprint': text(subject_fingerprint),
            'autonomy_tier': text(autonomy_tier, default='supervised'),
            'external_confirmation_mode': text(external_confirmation_mode, default='required'),
            'approval_kind': 'execution_gate',
            'route_action': 'operator_review',
            'route_subject_label': f"{text(action_name)}:{normalized_execution_id}",
        }
        if not normalized_execution_id:
            raise ValueError('execution_id is required for execution approval')
        if not normalized_metadata['decision_id']:
            raise ValueError('decision_id is required for execution approval')
        if not normalized_metadata['action_name']:
            raise ValueError('action_name is required for execution approval')
        if not normalized_metadata['subject_fingerprint']:
            raise ValueError('subject_fingerprint is required for execution approval')
        return self.submit(
            tenant_id=tenant_id,
            subject_type='action_execution',
            subject_id=normalized_execution_id,
            requested_by=requested_by,
            reason=reason,
            required_role_groups=required_role_groups,
            min_distinct_approvers=min_distinct_approvers,
            prohibit_self_approval=True,
            metadata=normalized_metadata,
        )

    def evaluate(
        self,
        *,
        approval_id: str,
        tenant_id: str,
        actor_id: str,
        role_id: RoleId,
        outcome: ApprovalOutcome,
        rationale: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        decision = ApprovalDecision(
            approval_id=approval_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            role_id=role_id,
            outcome=outcome,
            rationale=rationale,
            metadata=dict(metadata or {}),
        )
        record = self.approval_workflow.evaluate(decision)
        return record_dict(record)
    decide = evaluate

    def get(self, *, approval_id: str) -> dict[str, Any] | None:
        record = self.approval_workflow.get(approval_id)
        if record is None:
            return None
        return record_dict(record)


    def submit_operator_override(
        self,
        *,
        tenant_id: str,
        execution_id: str,
        decision_id: str,
        action_name: str,
        requested_by: str,
        reason: str,
        subject_fingerprint: str,
        expires_at: object | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        request = OperatorOverrideRequest(
            override_id=f'ovr_{secrets.token_hex(8)}',
            tenant_id=tenant_id,
            execution_id=text(execution_id),
            decision_id=text(decision_id),
            action_name=text(action_name),
            requested_by=text(requested_by),
            reason=text(reason),
            subject_fingerprint=text(subject_fingerprint),
            expires_at=expires_at,
            metadata=dict(metadata or {}),
        )
        record = self.operator_override_store.create(request)
        append_control_plane_audit(
            self.audit_log,
            tenant_id=tenant_id,
            event_type='operator_override_submitted',
            payload={
                'override_id': record.request.override_id,
                'execution_id': record.request.execution_id,
                'decision_id': record.request.decision_id,
                'action_name': record.request.action_name,
                'subject_fingerprint': record.request.subject_fingerprint,
            },
        )
        return override_record_dict(record)

    def decide_operator_override(
        self,
        *,
        override_id: str,
        tenant_id: str,
        actor_id: str,
        role_id: RoleId,
        resolution: OperatorOverrideResolution,
        note: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        record = self.operator_override_store.get(override_id)
        if record is None:
            raise ValueError(f'operator override not found: {override_id}')
        if record.is_terminal:
            raise RuntimeError(f'operator override already terminal: {override_id}')
        if record.request.tenant_id != text(tenant_id):
            raise RuntimeError('cross_tenant_operator_override_decision_forbidden')
        if not is_operator_override_role_allowed(role_id):
            raise RuntimeError('operator_override_role_not_authorized')
        decision = OperatorOverrideDecision(
            override_id=record.request.override_id,
            tenant_id=record.request.tenant_id,
            actor_id=text(actor_id),
            role_id=role_id,
            resolution=resolution,
            note=text(note),
            metadata=dict(metadata or {}),
        )
        decision.validate()
        if resolution is OperatorOverrideResolution.APPROVE_ONCE:
            updated = replace(record, status=OperatorOverrideStatus.APPROVED, decision=decision, final_reason='override_approved_once')
        elif resolution is OperatorOverrideResolution.REJECT:
            updated = replace(record, status=OperatorOverrideStatus.REJECTED, decision=decision, final_reason='override_rejected')
        elif resolution is OperatorOverrideResolution.CANCEL:
            updated = replace(record, status=OperatorOverrideStatus.CANCELLED, decision=decision, final_reason='override_cancelled')
        else:
            updated = replace(record, status=OperatorOverrideStatus.REQUESTED, decision=decision, final_reason=None)
        saved = self.operator_override_store.save(updated)
        append_control_plane_audit(
            self.audit_log,
            tenant_id=tenant_id,
            event_type='operator_override_decided',
            payload={
                'override_id': saved.request.override_id,
                'execution_id': saved.request.execution_id,
                'decision_id': saved.request.decision_id,
                'action_name': saved.request.action_name,
                'subject_fingerprint': saved.request.subject_fingerprint,
                'status': saved.status.value,
                'resolution': resolution.value,
            },
        )
        return override_record_dict(saved)


    def get_operator_override(self, *, override_id: str) -> dict[str, Any] | None:
        record = self.operator_override_store.get(override_id)
        if record is None:
            return None
        return override_record_dict(record)

    def list_open_operator_overrides(self, *, tenant_id: str) -> dict[str, Any]:
        all_records = tuple(override_record_dict(item) for item in list_tenant_records(self.operator_override_store, tenant_id=tenant_id, include_terminal=True))
        records = tuple(item for item in all_records if text(item.get('status')) == 'requested')
        records = tuple(sorted(records, key=lambda item: (str(item.get('status') or ''), str(item.get('requested_at') or ''), str(item.get('override_id') or ''))))
        actionable = tuple(override_action_summary(item) for item in records[:25])
        lifecycle = lifecycle_counts(all_records)
        resume_ready = resume_candidates(latest_records(all_records, limit=50, timestamp_keys=('consumed_at', 'requested_at', 'expires_at')))
        audit_summary = audit_payload_summary(self.audit_log, tenant_id=tenant_id)
        timeline = build_control_plane_timeline(approvals=(), overrides=all_records, audit_summary=audit_summary)
        return {
            'tenant_id': tenant_id,
            'count': len(records),
            'history_count': len(all_records),
            'records': records,
            'summary': {
                'open_override_count': len(records),
                'history_count': len(all_records),
                'fingerprint_bound_count': sum(1 for item in records if text(item.get('subject_fingerprint'))),
                'expiring_count': sum(1 for item in records if bool(item.get('expires_at'))),
                'action_bound_count': sum(1 for item in records if text(item.get('action_name'))),
                'decision_bound_count': sum(1 for item in records if text(item.get('decision_id'))),
                'operator_actionable_count': len(actionable),
                'lifecycle_counts': lifecycle,
                'resume_candidate_count': len(resume_ready),
                'consumed_count': lifecycle.get('consumed', 0),
            },
            'operator_actions': actionable,
            'resume_candidates': resume_ready,
            'audit': audit_summary,
            'timeline': timeline,
            'operator_console': {
                'action_required': len(actionable) > 0,
                'pending_operator_overrides': len(records),
                'expiring_operator_overrides': sum(1 for item in records if bool(item.get('expires_at'))),
                'resume_candidate_count': len(resume_ready),
                'resume_ready_overrides': len(resume_ready),
            },
        }

    def list_open(self, *, tenant_id: str, subject_type: str | None = None) -> dict[str, Any]:
        all_records = list_tenant_records(self.approval_store, tenant_id=tenant_id, include_terminal=True)
        normalized_subject_type = text(subject_type) or None
        normalized_records = []
        historical_records = []
        for item in all_records:
            row = record_dict(item)
            if normalized_subject_type and row['subject_type'] != normalized_subject_type:
                continue
            historical_records.append(row)
            if row['status'] == 'requested':
                normalized_records.append(row)
        normalized_records.sort(key=lambda item: (str(item.get('status') or ''), str(item.get('created_at') or ''), str(item.get('approval_id') or '')))
        historical_records.sort(key=lambda item: (str(item.get('created_at') or ''), str(item.get('approval_id') or '')))
        execution_pending = [item for item in normalized_records if item['subject_type'] == 'action_execution' and item.get('status') == 'requested']
        expiring = [item for item in execution_pending if bool(item.get('expires_at'))]
        operator_actions = tuple(route_action_summary(item) for item in execution_pending[:25])
        lifecycle = lifecycle_counts(tuple(historical_records))
        resume_ready = resume_candidates(latest_records(tuple(historical_records), limit=50, timestamp_keys=('created_at', 'expires_at')))
        audit_summary = audit_payload_summary(self.audit_log, tenant_id=tenant_id)
        timeline = build_control_plane_timeline(approvals=tuple(historical_records), overrides=(), audit_summary=audit_summary)
        return {
            'tenant_id': tenant_id,
            'count': len(normalized_records),
            'history_count': len(historical_records),
            'subject_type': normalized_subject_type,
            'records': normalized_records,
            'summary': {
                'execution_pending_count': len(execution_pending),
                'history_count': len(historical_records),
                'fingerprint_bound_count': sum(1 for item in execution_pending if text(safe_dict(item.get('metadata')).get('subject_fingerprint'))),
                'action_bound_count': sum(1 for item in execution_pending if text(safe_dict(item.get('metadata')).get('action_name'))),
                'decision_bound_count': sum(1 for item in execution_pending if text(safe_dict(item.get('metadata')).get('decision_id'))),
                'dual_control_count': sum(1 for item in historical_records if safe_int(item.get('min_distinct_approvers', 1), default=1) > 1),
                'expiring_count': sum(1 for item in normalized_records if bool(item.get('expires_at'))),
                'operator_actionable_count': len(operator_actions),
                'lifecycle_counts': lifecycle,
                'resume_candidate_count': len(resume_ready),
                'consumed_count': lifecycle.get('consumed', 0),
            },
            'operator_actions': operator_actions,
            'resume_candidates': resume_ready,
            'audit': audit_summary,
            'timeline': timeline,
            'operator_console': {
                'action_required': len(operator_actions) > 0,
                'pending_execution_approvals': len(execution_pending),
                'expiring_execution_approvals': len(expiring),
                'resume_candidate_count': len(resume_ready),
                'resume_ready_approvals': len(resume_ready),
            },
        }



__all__ = [
    'ApprovalRouteHandlers',
    'CANON_API_APPROVAL_ROUTE_HANDLERS',
]
