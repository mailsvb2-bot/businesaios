from __future__ import annotations

from dataclasses import asdict
from typing import Any
from collections.abc import Iterable, Mapping

from contracts.action_impact_contract import ActionCategory, ActionImpact
from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from execution.operator_override_store import build_default_operator_override_store
from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import PersistentApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.control_plane_audit_log import PersistentGovernanceAuditLog
from governance.rbac_contract import ActorContext, RoleId
from governance.tenant_policy_overrides import PersistentTenantPolicyOverrideRegistry
from runtime.execution.governance_runtime_support import _append_governance_audit, _governance_audit_log
from runtime.execution.operational_budget_runtime import build_action_execution_context

CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE = True

def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

def _approval_gate_enabled(*, payload: dict[str, Any], meta: dict[str, Any], impact: ActionImpact) -> bool:
    approval_policy = _safe_dict(payload.get('approval_policy'))
    if approval_policy:
        return True
    if bool(payload.get('approval_gate_enforce') or meta.get('approval_gate_enforce')):
        return True
    if bool(payload.get('requires_human_approval') or meta.get('requires_human_approval')):
        return True
    if str(payload.get('external_confirmation_mode') or meta.get('external_confirmation_mode') or '').strip() and bool(payload.get('approval_policy') or meta.get('approval_policy')):
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
    gate = getattr(executor, '_approval_execution_gate', None)
    if gate is None:
        gate = _build_default_approval_execution_gate()
        setattr(executor, '_approval_execution_gate', gate)
    return gate

def _execution_operator_override_store(executor: Any):
    store = getattr(executor, '_operator_override_store', None)
    if store is None:
        store = build_default_operator_override_store()
        setattr(executor, '_operator_override_store', store)
    return store

def _extract_operator_override_id(*, payload: dict[str, Any], meta: dict[str, Any]) -> str | None:
    override_id = str(
        payload.get('operator_override_id')
        or meta.get('operator_override_id')
        or _safe_dict(payload.get('operator_override')).get('override_id')
        or _safe_dict(meta.get('operator_override')).get('override_id')
        or ''
    ).strip()
    return override_id or None

def _load_operator_override(*, executor: Any, override_id: str):
    return _execution_operator_override_store(executor).get(override_id)

def _consume_operator_override(*, executor: Any, record: Any, execution_id: str) -> Any:
    consumed = record.consume_once(execution_id=execution_id)
    return _execution_operator_override_store(executor).save(consumed)

def _materialize_operator_override_approval(*, guard: Any, ctx: Any, impact: ActionImpact, operator_override: Any) -> str:
    workflow = getattr(guard, '_approval_workflow', None)
    decision = getattr(operator_override, 'decision', None)
    if workflow is None or decision is None:
        raise RuntimeError('operator_override_approval_materialization_unavailable')
    approval_id = f"ap-override-{operator_override.request.override_id}"
    existing = workflow.get(approval_id)
    if existing is None:
        request = ApprovalRequest(
            approval_id=approval_id,
            tenant_id=ctx.tenant_id,
            subject_type='action_execution',
            subject_id=str(ctx.execution_id or ctx.action_name),
            requested_by=operator_override.request.requested_by,
            reason='operator_override_materialized_as_execution_approval',
            required_role_groups=((decision.role_id,),),
            min_distinct_approvers=1,
            prohibit_self_approval=False,
            metadata={
                'decision_id': operator_override.request.decision_id,
                'action_name': operator_override.request.action_name,
                'subject_fingerprint': operator_override.request.subject_fingerprint,
                'approval_source': 'operator_override',
                'operator_override_id': operator_override.request.override_id,
                'impact_category': impact.category.value,
            },
        )
        workflow.submit(request)
    current = workflow.get(approval_id)
    if current is None or getattr(current, 'status', None).value != 'approved':
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
                    'approval_source': 'operator_override',
                    'operator_override_id': operator_override.request.override_id,
                    'resolution': decision.resolution.value,
                },
            ),
        )
    return approval_id

def _apply_approval_workflow_resolution(*, workflow: Any, approval_decision: ApprovalDecision) -> Any:
    resolver = getattr(workflow, 'decide')
    return resolver(approval_decision)

def _gate_metadata(*, payload: dict[str, Any], meta: dict[str, Any], env: Any, impact: ActionImpact) -> dict[str, object]:
    tags = payload.get('tags', meta.get('tags'))
    if isinstance(tags, (list, tuple, set, frozenset)):
        normalized_tags = [str(item).strip() for item in tags if str(item).strip()]
    elif tags is None:
        normalized_tags = []
    else:
        normalized_tags = [str(tags).strip()] if str(tags).strip() else []
    return {
        'decision_id': str(env.decision.decision_id or '').strip(),
        'actor_id': str(meta.get('actor_id') or payload.get('actor_id') or payload.get('user_id') or meta.get('user_id') or 'system').strip(),
        'requires_manual_review': bool(payload.get('requires_human_approval') or meta.get('requires_human_approval')),
        'tags': normalized_tags,
        'impact_category': impact.category.value,
    }

def _build_approval_output(*, verdict: Any) -> dict[str, object]:
    metadata = _safe_dict(getattr(verdict, 'metadata', {}))
    payload: dict[str, object] = {
        'approval_id': getattr(verdict, 'approval_id', None),
        'subject_fingerprint': getattr(verdict, 'subject_fingerprint', None),
        'status': str(getattr(verdict, 'status', '') or '') or None,
        'reason': str(getattr(verdict, 'reason', '') or '') or None,
        'approval_required': bool(getattr(verdict, 'approval_required', False)),
        'operator_required': bool(getattr(verdict, 'operator_required', False)),
        'manual_override_used': bool(metadata.get('manual_override_used', getattr(verdict, 'used_operator_override', False))),
        'manual_override_allowed': bool(_safe_dict(getattr(verdict, 'policy', {})).get('manual_override_allowed', False)),
        'handoff': _safe_dict(getattr(verdict, 'handoff', {})) or None,
        'expires_at': metadata.get('expires_at'),
        'approval_request_fingerprint': metadata.get('approval_request_fingerprint'),
    }
    return {key: value for key, value in payload.items() if value not in ('', None, False) or key in {'approval_required', 'operator_required', 'manual_override_used', 'manual_override_allowed'}}

def _build_resume_governance_hint(*, ctx: Any, approval_id: str | None, gate_verdict: Any | None, operator_override_id: str | None) -> dict[str, object]:
    hint = {
        'resume_stage': 'governance_approval',
        'execution_id': str(getattr(ctx, 'execution_id', '') or '').strip() or None,
        'approval_id': approval_id or getattr(gate_verdict, 'approval_id', None),
        'operator_override_id': operator_override_id,
        'subject_fingerprint': getattr(gate_verdict, 'subject_fingerprint', None) if gate_verdict is not None else None,
        'reason': getattr(gate_verdict, 'reason', None) if gate_verdict is not None else None,
    }
    return {k: v for k, v in hint.items() if v not in ('', None)}

def _emit_resume_event(*, executor: Any, guard: Any, env: Any, ctx: Any, actor: Any, event_type: str, resume: dict[str, object], extra: dict[str, object] | None = None) -> None:
    payload = {
        'tenant_id': ctx.tenant_id,
        'action_name': getattr(ctx, 'action_name', None),
        'resume': dict(resume),
        **dict(extra or {}),
    }
    if getattr(executor, '_events', None) is not None:
        executor._events.emit(
            event_type=event_type,
            source='runtime.execution.governance_runtime',
            user_id=str(getattr(ctx, 'user_id', None) or getattr(actor, 'actor_id', None) or 'system'),
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
            payload=payload,
        )
    _append_governance_audit(
        executor=executor,
        guard=guard,
        tenant_id=ctx.tenant_id,
        event_type=event_type,
        payload={
            'decision_id': str(env.decision.decision_id),
            'correlation_id': str(env.decision.correlation_id),
            **payload,
        },
    )

class GovernanceExecutionBlocked(RuntimeError):
    def __init__(self, *, error: str, output: dict[str, object]) -> None:
        super().__init__(str(error))
        self.error = str(error)
        self.output = dict(output)

def review_governance_execution(*, executor: Any, env: Any) -> None:
    guard = getattr(executor, '_governance_execution_guard', None)
    if guard is None:
        return
    payload = env.decision.payload if isinstance(env.decision.payload, dict) else {}
    meta = payload.get('meta') if isinstance(payload.get('meta'), dict) else {}
    if not _should_enforce(payload=payload, meta=meta):
        return

    ctx = build_action_execution_context(env=env)
    actor = _build_actor(payload=payload, meta=meta, tenant_id=ctx.tenant_id)
    impact = _build_impact(ctx=ctx, payload=payload, meta=meta)
    approval_id = _extract_approval_id(payload=payload, meta=meta)
    operator_override_id = _extract_operator_override_id(payload=payload, meta=meta)
    operator_override = None
    if operator_override_id:
        operator_override = _load_operator_override(executor=executor, override_id=operator_override_id)
        if operator_override is None:
            resume = _build_resume_governance_hint(ctx=ctx, approval_id=approval_id, gate_verdict=None, operator_override_id=operator_override_id)
            _emit_resume_event(
                executor=executor,
                guard=guard,
                env=env,
                ctx=ctx,
                actor=actor,
                event_type='governance_execution_resume_hint_emitted',
                resume=resume,
                extra={'reason': 'operator_override_not_found'},
            )
            raise GovernanceExecutionBlocked(
                error='operator_override_not_found',
                output={
                    'blocked_by_governance': True,
                    'operator_required': True,
                    'governance': {
                        'reason': 'operator_override_not_found',
                        'operator_override_id': operator_override_id,
                        'resume': resume,
                    },
                },
            )
    gate_verdict = None
    if _approval_gate_enabled(payload=payload, meta=meta, impact=impact):
        gate = _execution_approval_gate(executor)
        gate_verdict = gate.evaluate(
            ctx=ctx,
            impact=impact,
            autonomy_tier=str(payload.get('autonomy_tier') or meta.get('autonomy_tier') or 'supervised'),
            external_confirmation_mode=str(payload.get('external_confirmation_mode') or meta.get('external_confirmation_mode') or 'required'),
            approval_policy=_safe_dict(payload.get('approval_policy')) or _safe_dict(meta.get('approval_policy')),
            metadata=_gate_metadata(payload=payload, meta=meta, env=env, impact=impact),
            approval_id=approval_id,
            operator_override=operator_override,
            requested_by=str(actor.actor_id or 'system'),
        )
        if not gate_verdict.allowed:
            approval_output = {
                **_build_approval_output(verdict=gate_verdict),
                'tenant_id': ctx.tenant_id,
                'decision_id': str(env.decision.decision_id or '').strip(),
                'execution_id': str(ctx.execution_id or '').strip() or str(env.decision.decision_id or '').strip(),
                'action_name': ctx.action_name,
                'operator_override_id': operator_override_id,
            }
            approval_required_payload = {
                'tenant_id': ctx.tenant_id,
                'action_name': ctx.action_name,
                'approval': approval_output,
                'impact': asdict(impact),
            }
            if getattr(executor, '_events', None) is not None:
                executor._events.emit(
                    event_type='governance_execution_approval_required',
                    source='execution.approval_execution_gate',
                    user_id=str(ctx.user_id or actor.actor_id or 'system'),
                    decision_id=str(env.decision.decision_id),
                    correlation_id=str(env.decision.correlation_id),
                    payload=approval_required_payload,
                )
            _append_governance_audit(
                executor=executor,
                guard=guard,
                tenant_id=ctx.tenant_id,
                event_type='governance_execution_approval_required',
                payload={
                    'decision_id': str(env.decision.decision_id),
                    'correlation_id': str(env.decision.correlation_id),
                    **approval_required_payload,
                },
            )
            resume = _build_resume_governance_hint(ctx=ctx, approval_id=approval_output.get('approval_id'), gate_verdict=gate_verdict, operator_override_id=operator_override_id)
            _emit_resume_event(
                executor=executor,
                guard=guard,
                env=env,
                ctx=ctx,
                actor=actor,
                event_type='governance_execution_resume_hint_emitted',
                resume=resume,
                extra={'reason': gate_verdict.reason, 'approval_id': approval_output.get('approval_id')},
            )
            raise GovernanceExecutionBlocked(
                error=str(gate_verdict.reason),
                output={
                    'blocked_by_governance': True,
                    'approval_required': bool(gate_verdict.approval_required),
                    'operator_required': bool(gate_verdict.operator_required),
                    'approval': approval_output,
                    'governance': {
                        'approval_id': approval_output.get('approval_id'),
                        'reason': gate_verdict.reason,
                        'approval_required': bool(gate_verdict.approval_required),
                        'metadata': {'source': 'execution.approval_execution_gate'},
                        'resume': resume,
                    },
                },
            )
        if bool(getattr(gate_verdict, 'used_operator_override', False)):
            if operator_override is None:
                raise GovernanceExecutionBlocked(
                    error='operator_override_consumption_requires_record',
                    output={
                        'blocked_by_governance': True,
                        'operator_required': True,
                        'governance': {'reason': 'operator_override_consumption_requires_record', 'resume': _build_resume_governance_hint(ctx=ctx, approval_id=approval_id, gate_verdict=gate_verdict, operator_override_id=operator_override_id)},
                    },
                )
            consumed_override = _consume_operator_override(
                executor=executor,
                record=operator_override,
                execution_id=str(ctx.execution_id or ''),
            )
            operator_override = consumed_override
            approval_id = _materialize_operator_override_approval(
                guard=guard,
                ctx=ctx,
                impact=impact,
                operator_override=consumed_override,
            )
            consumed_payload = {
                'tenant_id': ctx.tenant_id,
                'action_name': ctx.action_name,
                'override_id': consumed_override.request.override_id,
                'subject_fingerprint': consumed_override.request.subject_fingerprint,
                'consumed_by_execution_id': consumed_override.consumed_by_execution_id,
                'materialized_approval_id': approval_id,
            }
            if getattr(executor, '_events', None) is not None:
                executor._events.emit(
                    event_type='governance_execution_operator_override_consumed',
                    source='execution.approval_execution_gate',
                    user_id=str(ctx.user_id or actor.actor_id or 'system'),
                    decision_id=str(env.decision.decision_id),
                    correlation_id=str(env.decision.correlation_id),
                    payload=consumed_payload,
                )
            _append_governance_audit(
                executor=executor,
                guard=guard,
                tenant_id=ctx.tenant_id,
                event_type='governance_execution_operator_override_consumed',
                payload={
                    'decision_id': str(env.decision.decision_id),
                    'correlation_id': str(env.decision.correlation_id),
                    **consumed_payload,
                },
            )
            _emit_resume_event(
                executor=executor,
                guard=guard,
                env=env,
                ctx=ctx,
                actor=actor,
                event_type='governance_execution_resume_ready',
                resume=_build_resume_governance_hint(ctx=ctx, approval_id=approval_id, gate_verdict=gate_verdict, operator_override_id=consumed_override.request.override_id),
                extra={'resume_source': 'operator_override_consumed'},
            )
        approval_satisfied_payload = {
            'tenant_id': ctx.tenant_id,
            'action_name': ctx.action_name,
            'approval': _build_approval_output(verdict=gate_verdict),
            'operator_override_id': None if operator_override is None else operator_override.request.override_id,
        }
        if getattr(executor, '_events', None) is not None:
            executor._events.emit(
                event_type='governance_execution_approval_satisfied',
                source='execution.approval_execution_gate',
                user_id=str(ctx.user_id or actor.actor_id or 'system'),
                decision_id=str(env.decision.decision_id),
                correlation_id=str(env.decision.correlation_id),
                payload=approval_satisfied_payload,
            )
        _append_governance_audit(
            executor=executor,
            guard=guard,
            tenant_id=ctx.tenant_id,
            event_type='governance_execution_approval_satisfied',
            payload={
                'decision_id': str(env.decision.decision_id),
                'correlation_id': str(env.decision.correlation_id),
                **approval_satisfied_payload,
            },
        )
        approval_id = approval_id or str(getattr(gate_verdict, 'approval_id', '') or '').strip() or None
        _emit_resume_event(
            executor=executor,
            guard=guard,
            env=env,
            ctx=ctx,
            actor=actor,
            event_type='governance_execution_resume_ready',
            resume=_build_resume_governance_hint(ctx=ctx, approval_id=approval_id, gate_verdict=gate_verdict, operator_override_id=None if operator_override is None else operator_override.request.override_id),
            extra={'resume_source': 'approval_satisfied'},
        )

    verdict = guard.evaluate(actor=actor, ctx=ctx, impact=impact, approval_id=approval_id)
    if not verdict.allowed:
        resume = _build_resume_governance_hint(ctx=ctx, approval_id=approval_id, gate_verdict=gate_verdict, operator_override_id=operator_override_id)
        _emit_resume_event(
            executor=executor,
            guard=guard,
            env=env,
            ctx=ctx,
            actor=actor,
            event_type='governance_execution_resume_hint_emitted',
            resume=resume,
            extra={'reason': verdict.reason, 'required_permission': verdict.required_permission.value if verdict.required_permission else None},
        )
        if getattr(executor, '_events', None) is not None:
            executor._events.emit(
                event_type='governance_execution_veto',
                source='governance.sox_like_action_guard',
                user_id=str(ctx.user_id or actor.actor_id or 'system'),
                decision_id=str(env.decision.decision_id),
                correlation_id=str(env.decision.correlation_id),
                payload={
                    'tenant_id': ctx.tenant_id,
                    'action_name': ctx.action_name,
                    'approval_id': approval_id,
                    'impact': asdict(impact),
                    'verdict': {
                        'reason': verdict.reason,
                        'required_permission': verdict.required_permission.value if verdict.required_permission else None,
                        'approval_required': verdict.approval_required,
                        'operator_required': verdict.operator_required,
                        'tags': list(verdict.tags),
                        'metadata': dict(verdict.metadata),
                    },
                },
            )
        raise GovernanceExecutionBlocked(
            error=str(verdict.reason),
            output={
                'blocked_by_governance': True,
                'operator_required': bool(verdict.operator_required),
                'governance': {
                    'approval_id': approval_id,
                    'reason': verdict.reason,
                    'required_permission': verdict.required_permission.value if verdict.required_permission else None,
                    'approval_required': bool(verdict.approval_required),
                    'tags': list(verdict.tags),
                    'metadata': dict(verdict.metadata),
                    'resume': resume,
                },
            },
        )

    return

def _should_enforce(*, payload: dict[str, Any], meta: dict[str, Any]) -> bool:
    if bool(meta.get('governance_enforce')) or bool(payload.get('governance_enforce')):
        return True
    role_values = payload.get('role_ids', meta.get('role_ids'))
    return bool(_normalize_roles(role_values))

def _build_actor(*, payload: dict[str, Any], meta: dict[str, Any], tenant_id: str) -> ActorContext:
    actor_id = str(
        meta.get('actor_id')
        or payload.get('actor_id')
        or payload.get('user_id')
        or meta.get('user_id')
        or 'system'
    ).strip()
    role_ids = _normalize_roles(payload.get('role_ids', meta.get('role_ids')))
    return ActorContext(
        actor_id=actor_id,
        tenant_id=tenant_id,
        role_ids=role_ids,
        is_service=actor_id == 'system',
        attributes={'source': 'runtime.execution.governance_runtime'},
    )

def _normalize_roles(value: Any) -> frozenset[RoleId]:
    values: Iterable[Any]
    if isinstance(value, (list, tuple, set, frozenset)):
        values = value
    elif value is None:
        values = ()
    else:
        values = (value,)
    normalized: set[RoleId] = set()
    for item in values:
        raw = str(getattr(item, 'value', item) or '').strip()
        if not raw:
            continue
        try:
            normalized.add(RoleId(raw))
        except ValueError:
            continue
    return frozenset(normalized)

def _build_impact(*, ctx: Any, payload: dict[str, Any], meta: dict[str, Any]) -> ActionImpact:
    raw_category = str(payload.get('action_category') or meta.get('action_category') or '').strip()
    try:
        category = ActionCategory(raw_category) if raw_category else _infer_category(ctx.action_name)
    except ValueError:
        category = ActionCategory.UNKNOWN
    impact = ActionImpact(
        action_name=ctx.action_name,
        category=category,
        cost_minor=_normalize_non_negative_int(payload.get('cost_minor'), meta.get('cost_minor')),
        publication_count=_normalize_non_negative_int(payload.get('publication_count'), meta.get('publication_count')),
        outbound_count=_normalize_non_negative_int(payload.get('outbound_count'), meta.get('outbound_count')),
        strategic_change_count=_normalize_non_negative_int(payload.get('strategic_change_count'), meta.get('strategic_change_count')),
        rollback_event_count=_normalize_non_negative_int(payload.get('rollback_event_count'), meta.get('rollback_event_count')),
        requires_human_approval=bool(payload.get('requires_human_approval') or meta.get('requires_human_approval')),
    )
    impact.validate()
    return impact

def _normalize_non_negative_int(primary: Any, fallback: Any) -> int:
    value = primary if primary not in (None, "") else fallback
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0

def _infer_category(action_name: str) -> ActionCategory:
    action = str(action_name or '').strip().lower()
    hints = {
        'read': ActionCategory.SAFE_READ,
        'get': ActionCategory.SAFE_READ,
        'list': ActionCategory.SAFE_READ,
        'fetch': ActionCategory.SAFE_READ,
        'publish': ActionCategory.PUBLICATION,
        'post': ActionCategory.PUBLICATION,
        'send': ActionCategory.OUTBOUND,
        'message': ActionCategory.OUTBOUND,
        'email': ActionCategory.OUTBOUND,
        'budget': ActionCategory.BUDGET_CHANGE,
        'price': ActionCategory.STRATEGIC_CHANGE,
        'strategy': ActionCategory.STRATEGIC_CHANGE,
        'rollback': ActionCategory.ROLLBACK,
        'revert': ActionCategory.ROLLBACK,
        'execute': ActionCategory.EXECUTION,
        'run': ActionCategory.EXECUTION,
        'update': ActionCategory.INTERNAL_WRITE,
        'write': ActionCategory.INTERNAL_WRITE,
        'save': ActionCategory.INTERNAL_WRITE,
    }
    for fragment, category in hints.items():
        if fragment in action:
            return category
    return ActionCategory.UNKNOWN

def _extract_approval_id(*, payload: dict[str, Any], meta: dict[str, Any]) -> str | None:
    value = payload.get('approval_id') or meta.get('approval_id')
    normalized = str(value or '').strip()
    return normalized or None

__all__ = [
    'CANON_RUNTIME_GOVERNANCE_EXECUTION_GATE',
    'GovernanceExecutionBlocked',
    'review_governance_execution',
]
