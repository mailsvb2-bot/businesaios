from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers

from application.capability.capability_operator_view import normalize_capability_view
from application.admin.platform_control_center_service import PlatformControlCenterService
from tenancy.tenant_execution_budget_guard import TenantExecutionBudgetGuard, TenantExecutionUsage
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle, build_default_tenant_policy_store
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_registry import InMemoryTenantRegistry, build_default_tenant_registry


CANON_API_ADMIN_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_ADMIN_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class AdminRouteHandlers:
    tenant_registry: InMemoryTenantRegistry = field(default_factory=build_default_tenant_registry)
    tenant_policy_store: InMemoryTenantPolicyStore = field(default_factory=build_default_tenant_policy_store)
    tenant_quota_guard: TenantQuotaGuard = field(init=False)
    tenant_execution_budget_guard: TenantExecutionBudgetGuard = field(init=False)
    business_autonomy_routes: Any = field(default_factory=build_business_autonomy_route_handlers)
    platform_control_center: PlatformControlCenterService = field(default_factory=PlatformControlCenterService.for_repo)

    def __post_init__(self) -> None:
        quota_guard = TenantQuotaGuard(policy_store=self.tenant_policy_store)
        object.__setattr__(self, 'tenant_quota_guard', quota_guard)
        object.__setattr__(self, 'tenant_execution_budget_guard', TenantExecutionBudgetGuard(policy_store=self.tenant_policy_store, quota_guard=quota_guard))

    def list_active_tenants(self) -> dict[str, Any]:
        return {
            'tenants': [
                {
                    'tenant_id': item.tenant_id,
                    'display_name': item.display_name,
                    'status': item.status.value,
                    'plan': item.plan.value,
                    'aliases': list(item.aliases),
                }
                for item in self.tenant_registry.list_active()
            ]
        }

    def get_tenant_policy(self, *, tenant_id: str) -> dict[str, Any]:
        bundle = self.tenant_policy_store.require(tenant_id)
        return _bundle_dict(bundle, quota_snapshot=self.tenant_quota_guard.snapshot(tenant_id=tenant_id))

    def save_tenant_policy(self, bundle: TenantPolicyBundle) -> dict[str, Any]:
        if self.tenant_registry.lookup(bundle.tenant_id) is None:
            raise KeyError(f'unknown tenant: {bundle.tenant_id}')
        saved = self.tenant_policy_store.save(bundle)
        return _bundle_dict(saved, quota_snapshot=self.tenant_quota_guard.snapshot(tenant_id=saved.tenant_id))

    def get_operator_run_view(
        self,
        *,
        tenant_id: str,
        run_snapshot: Any,
        allowed_controls: Iterable[Any] = (),
        recent_events: Iterable[Any] = (),
        recovery_plan: Any | None = None,
        capability_view: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            'tenant_id': str(tenant_id),
            'run': _run_snapshot_dict(run_snapshot),
            'allowed_controls': tuple(_control_row(item) for item in tuple(allowed_controls or ())),
            'recent_events': tuple(_event_row(item) for item in tuple(recent_events or ())),
            'recovery': None if recovery_plan is None else _recovery_plan_dict(recovery_plan),
            'capability_diagnostics': self.get_capability_diagnostics_view(tenant_id=tenant_id, capability_view=capability_view),
            'read_only': True,
        }


    def get_capability_diagnostics_view(self, *, tenant_id: str, capability_view: Mapping[str, Any] | None) -> dict[str, Any] | None:
        normalized_tenant_id = str(tenant_id).strip()
        capability = normalize_capability_view(capability_view)
        diagnostics = dict(capability.get('diagnostics') or {})
        if not normalized_tenant_id or not diagnostics:
            return None
        return {
            'tenant_id': normalized_tenant_id,
            'diagnostics': {
                'status': str(diagnostics.get('status') or '').strip() or 'unknown',
                'headline': str(diagnostics.get('headline') or '').strip() or 'Capability diagnostics unavailable.',
                'operator_action': str(diagnostics.get('operator_action') or '').strip() or 'none',
                'signals': tuple(row for item in tuple(diagnostics.get('signals') or ()) for row in (_diagnostic_signal_row(item),) if row is not None),
            },
            'policy_verdict': dict(capability.get('policy_verdict') or {}),
            'execution_verdict': dict(capability.get('execution_verdict') or {}),
            'read_only': True,
        }

    def get_dead_letter_view(self, *, tenant_id: str, entries: Iterable[Any]) -> dict[str, Any]:
        rows = tuple(_dead_letter_row(item) for item in tuple(entries or ()) if _tenant_matches(item, tenant_id=tenant_id))
        return {'tenant_id': str(tenant_id), 'rows': rows, 'count': len(rows), 'read_only': True}

    def get_recovery_view(self, *, tenant_id: str, plan: Any, transport_results: Iterable[Any] = ()) -> dict[str, Any]:
        return {
            'tenant_id': str(tenant_id),
            'plan': _recovery_plan_dict(plan),
            'reconciliation': _reconciliation_dict(getattr(plan, 'reconciliation', None)),
            'transport_results': tuple(_transport_result_row(item) for item in tuple(transport_results or ())),
            'read_only': True,
        }



    def get_platform_overview(self, *, tenant_id: str = "tenant-demo", business_id: str = "default-business") -> dict[str, Any]:
        return self.platform_control_center.build_overview(tenant_id=tenant_id, business_id=business_id)

    def get_platform_risk_registry(self) -> dict[str, Any]:
        return self.platform_control_center.build_risk_registry()

    def get_platform_dependency_graph(self) -> dict[str, Any]:
        return self.platform_control_center.build_dependency_graph()

    def get_platform_remediation_plan(self) -> dict[str, Any]:
        return self.platform_control_center.build_remediation_plan()

    def get_platform_risk_diff(self, *, tenant_id: str = "tenant-demo") -> dict[str, Any]:
        return self.platform_control_center.build_risk_diff(tenant_id=tenant_id)

    def get_platform_ownership_graph(self) -> dict[str, Any]:
        return self.platform_control_center.build_ownership_graph()

    def get_platform_patch_suggestions(self) -> dict[str, Any]:
        return self.platform_control_center.build_patch_suggestions()

    def get_platform_snapshot_diff_view(self, *, tenant_id: str = "tenant-demo") -> dict[str, Any]:
        return self.platform_control_center.build_snapshot_diff_view(tenant_id=tenant_id)

    def get_platform_file_passport(self, *, file_path: str) -> dict[str, Any]:
        return self.platform_control_center.build_file_passport(file_path=file_path)

    def get_platform_ownership_drilldown(self, *, block: str) -> dict[str, Any]:
        return self.platform_control_center.build_ownership_drilldown(block=block)

    def get_platform_risk_trends(self, *, tenant_id: str = "tenant-demo") -> dict[str, Any]:
        return self.platform_control_center.build_risk_trends(tenant_id=tenant_id)

    def get_platform_maturity_trends(self, *, tenant_id: str = "tenant-demo") -> dict[str, Any]:
        return self.platform_control_center.build_maturity_trends(tenant_id=tenant_id)

    def get_platform_stop_conditions(self) -> dict[str, Any]:
        return self.platform_control_center.build_stop_conditions()

    def get_platform_live_widgets(self, *, tenant_id: str = "tenant-demo", business_id: str = "default-business") -> dict[str, Any]:
        return self.platform_control_center.build_live_widget_bundle(overview_payload=self.platform_control_center.build_overview(tenant_id=tenant_id, business_id=business_id))

    def get_platform_visual_conflicts(self) -> dict[str, Any]:
        return self.platform_control_center.build_visual_conflict_map()

    def get_platform_widget_runtime(self, *, tenant_id: str = 'tenant-demo', business_id: str = 'default-business') -> dict[str, Any]:
        return self.platform_control_center.build_widget_runtime(tenant_id=tenant_id, business_id=business_id)

    def save_platform_dashboard_layout(self, *, tenant_id: str, layout: Mapping[str, Any]) -> dict[str, Any]:
        return self.platform_control_center.save_dashboard_layout(tenant_id=tenant_id, layout=dict(layout or {}))

    def get_platform_remediation_workflow(self, *, file_path: str, risk_type: str = "") -> dict[str, Any]:
        return self.platform_control_center.build_remediation_workflow(file_path=file_path, risk_type=risk_type)

    def run_platform_remediation(self, *, file_path: str, risk_type: str = "") -> dict[str, Any]:
        return self.platform_control_center.build_remediation_run(file_path=file_path, risk_type=risk_type)

    def get_business_autonomy_overview(self, *, business_id: str) -> dict[str, Any]:
        handlers = self.business_autonomy_routes
        return {
            'business_id': business_id,
            'readiness': handlers.get_readiness(),
            'dashboard': handlers.get_dashboard(),
            'observability': handlers.get_observability_report(),
            'capabilities': handlers.get_registered_capabilities(business_id),
            'trust': handlers.get_trust_profile(business_id),
        }

    def export_business_autonomy_bundle(self, *, business_id: str) -> dict[str, Any]:
        handlers = self.business_autonomy_routes
        return {
            'business_id': business_id,
            'observability_bundle': handlers.export_observability_bundle(bundle_name=f'business-autonomy-{business_id}'),
            'audit_bundle': handlers.export_audit_bundle(bundle_name=f'business-autonomy-audit-{business_id}'),
        }

    def get_autonomy_budget_view(self, *, tenant_id: str, usage_payload: Mapping[str, object] | None) -> dict[str, Any]:
        usage = TenantExecutionBudgetGuard.from_execution_payload(tenant_id=tenant_id, payload=usage_payload)
        verdict = self.tenant_execution_budget_guard.evaluate(usage=usage)
        return {
            'tenant_id': verdict.tenant_id,
            'usage': _execution_usage_dict(usage),
            'verdict': _execution_verdict_dict(verdict),
            'read_only': True,
        }


def _bundle_dict(bundle: TenantPolicyBundle, *, quota_snapshot: dict[str, float]) -> dict[str, Any]:
    return {
        'tenant_id': bundle.tenant_id,
        'feature_flags': dict(bundle.feature_flags.flags),
        'variants': dict(bundle.feature_flags.variants),
        'runtime_limits': bundle.runtime_limits.__dict__,
        'memory_scope': bundle.memory_scope.__dict__,
        'connector_scope': bundle.connector_scope.__dict__,
        'audit_scope': bundle.audit_scope.__dict__,
        'billing_scope': bundle.billing_scope.__dict__,
        'quotas': dict(bundle.quotas),
        'quota_snapshot': dict(quota_snapshot),
        'updated_at': bundle.updated_at.isoformat(),
    }


def _tenant_matches(item: Any, *, tenant_id: str) -> bool:
    candidate = str(item.get('tenant_id') if isinstance(item, Mapping) else getattr(item, 'tenant_id', '') or '').strip()
    return not candidate or candidate == str(tenant_id)


def _run_snapshot_dict(item: Any) -> dict[str, Any]:
    return {
        'run_id': str(getattr(item, 'run_id', '') or '').strip(),
        'trace_id': getattr(item, 'trace_id', None),
        'decision_id': getattr(item, 'decision_id', None),
        'action_id': getattr(item, 'action_id', None),
        'goal': getattr(item, 'goal', None),
        'status': str(getattr(getattr(item, 'status', None), 'value', getattr(item, 'status', None)) or '').strip() or None,
        'stage': str(getattr(getattr(item, 'stage', None), 'value', getattr(item, 'stage', None)) or '').strip() or None,
        'operator_locked': bool(getattr(item, 'operator_locked', False)),
        'human_approval_required': bool(getattr(item, 'human_approval_required', False)),
        'owner_id': getattr(item, 'owner_id', None),
        'isolation_slot_id': getattr(item, 'isolation_slot_id', None),
        'risk_flags': tuple(getattr(item, 'risk_flags', ()) or ()),
    }


def _control_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return {
            'code': str(item.get('code') or '').strip(),
            'enabled': bool(item.get('enabled', True)),
            'operator_required': bool(item.get('operator_required', True)),
            'confirmation_required': bool(item.get('confirmation_required', True)),
            'reason': str(item.get('reason') or '').strip() or None,
        }
    code = str(item or '').strip()
    return {'code': code, 'enabled': True, 'operator_required': True, 'confirmation_required': True, 'reason': None}


def _event_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    return {
        'tenant_id': getattr(item, 'tenant_id', None),
        'trace_id': getattr(item, 'trace_id', None),
        'run_id': getattr(item, 'run_id', None),
        'sequence_no': int(getattr(item, 'sequence_no', 0) or 0),
        'stage': str(getattr(getattr(item, 'stage', None), 'value', getattr(item, 'stage', None)) or '').strip() or None,
        'event_type': str(getattr(item, 'event_type', '') or '').strip() or None,
        'summary': str(getattr(item, 'summary', '') or '').strip() or None,
    }


def _reconciliation_dict(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    if isinstance(item, Mapping):
        return dict(item)
    return {
        'run_id': str(getattr(item, 'run_id', '') or '').strip() or None,
        'latest_stage': getattr(item, 'latest_stage', None),
        'idempotency_state': getattr(item, 'idempotency_state', None),
        'outbox_state': getattr(item, 'outbox_state', None),
        'checkpoint_count': int(getattr(item, 'checkpoint_count', 0) or 0),
        'anomalies': tuple(getattr(item, 'anomalies', ()) or ()),
        'ok': bool(getattr(item, 'is_clean', False)),
    }


def _recovery_plan_dict(item: Any) -> dict[str, Any]:
    return {
        'run_id': str(getattr(item, 'run_id', '') or '').strip() or None,
        'recovery_action': str(getattr(item, 'recovery_action', '') or '').strip() or None,
        'reason': str(getattr(item, 'reason', '') or '').strip() or None,
        'delivery_hint': getattr(item, 'delivery_hint', None),
        'dead_letter_hint': getattr(item, 'dead_letter_hint', None),
        'operator_required': bool(getattr(item, 'operator_required', False)),
        'operator_hint': getattr(item, 'operator_hint', None),
        'resume_action': getattr(item, 'resume_action', None),
        'resume_stage': getattr(item, 'resume_stage', None),
        'risk_flags': tuple(getattr(item, 'risk_flags', ()) or ()),
        'anomalies': tuple(getattr(item, 'anomalies', ()) or ()),
        'policy_snapshot': dict(getattr(item, 'policy_snapshot', {}) or {}),
    }


def _transport_result_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    return {
        'transport_name': getattr(item, 'transport_name', None),
        'worker_id': getattr(item, 'worker_id', None),
        'backend_name': getattr(item, 'backend_name', None),
        'processed': int(getattr(item, 'processed', 0) or 0),
        'delivered': int(getattr(item, 'delivered', 0) or 0),
        'retried': int(getattr(item, 'retried', 0) or 0),
        'dead_lettered': int(getattr(item, 'dead_lettered', 0) or 0),
        'skipped': int(getattr(item, 'skipped', 0) or 0),
    }


def _dead_letter_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    return {
        'tenant_id': getattr(item, 'tenant_id', None),
        'message_id': getattr(item, 'message_id', None),
        'run_id': getattr(item, 'run_id', None),
        'trace_id': getattr(item, 'trace_id', None),
        'decision_id': getattr(item, 'decision_id', None),
        'topic': getattr(item, 'topic', None),
        'state': str(getattr(getattr(item, 'state', None), 'value', getattr(item, 'state', None)) or '').strip() or None,
        'delivery_attempts': int(getattr(item, 'delivery_attempts', 0) or 0),
        'last_error': getattr(item, 'last_error', None),
        'backend_name': getattr(item, 'backend_name', None),
    }


def _execution_usage_dict(item: Any) -> dict[str, Any]:
    return {
        'tenant_id': getattr(item, 'tenant_id', None),
        'action_count': int(getattr(item, 'action_count', 0) or 0),
        'effect_count': int(getattr(item, 'effect_count', 0) or 0),
        'outbound_message_count': int(getattr(item, 'outbound_message_count', 0) or 0),
        'publication_count': int(getattr(item, 'publication_count', 0) or 0),
        'memory_write_count': int(getattr(item, 'memory_write_count', 0) or 0),
        'connector_call_count': int(getattr(item, 'connector_call_count', 0) or 0),
        'budget_delta': float(getattr(item, 'budget_delta', 0.0) or 0.0),
        'labels': dict(getattr(item, 'labels', {}) or {}),
    }


def _execution_verdict_dict(item: Any) -> dict[str, Any]:
    return {
        'allowed': bool(getattr(item, 'allowed', False)),
        'reason': str(getattr(item, 'reason', '') or '').strip(),
        'tenant_id': getattr(item, 'tenant_id', None),
        'violations': tuple(getattr(item, 'violations', ()) or ()),
        'runtime_limit_checks': dict(getattr(item, 'runtime_limit_checks', {}) or {}),
        'quota_checks': dict(getattr(item, 'quota_checks', {}) or {}),
        'consumed': bool(getattr(item, 'consumed', False)),
    }


def _diagnostic_signal_row(item: Any) -> dict[str, Any] | None:
    row = dict(item or {}) if isinstance(item, Mapping) else {}
    code = str(row.get('code') or '').strip()
    if not code:
        return None
    return {
        'code': code,
        'severity': str(row.get('severity') or 'info').strip() or 'info',
        'summary': str(row.get('summary') or '').strip() or None,
        'operator_actionable': bool(row.get('operator_actionable', False)),
        'metadata': dict(row.get('metadata') or {}),
    }


__all__ = [
    'AdminRouteHandlers',
    'CANON_API_ADMIN_ROUTE_HANDLERS',
]
