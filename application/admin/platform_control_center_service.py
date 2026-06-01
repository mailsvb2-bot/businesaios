from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from application.admin.platform_control_center.remediation_workflow_assembler import RemediationWorkflowAssembler

CANON_PLATFORM_CONTROL_CENTER_SERVICE = True
PLATFORM_ADMIN_RUNTIME_MODE = "read_only_advisory"


def _count_python_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding='utf-8').splitlines())
    except OSError:
        return 0


def _file_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


@dataclass(frozen=True)
class PlatformControlCenterService:
    repo_root: Path

    @classmethod
    def for_repo(cls, repo_root: str | Path | None = None) -> PlatformControlCenterService:
        return cls(repo_root=Path(repo_root or '.').resolve())

    def build_overview(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        risk_rows = list(self.build_risk_registry()['risk_rows'])
        stop_conditions = self.build_stop_conditions()
        return {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'runtime_mode': PLATFORM_ADMIN_RUNTIME_MODE,
            'summary_cards': [
                {'title': 'Repo health', 'value': 'alpha/staging', 'status': 'warning'},
                {'title': 'Admin surface', 'value': 'advisory', 'status': 'warning'},
            ],
            'block_rows': [
                {'block': 'admin_surface', 'status': 'present_advisory'},
                {'block': 'provider_runtime', 'status': 'read_only_guarded'},
            ],
            'graphs': {'dependency_nodes': 3, 'ownership_nodes': 2, 'source': 'static_advisory_snapshot'},
            'risk_rows': risk_rows,
            'canon_status': {
                'admin_surface_required_for_new_features': True,
                'production_ready': False,
                'reason': 'control-plane overview is a read-only advisory surface until backed by full repository/runtime scan and green gates',
            },
            'dependency_rows': self.build_dependency_graph()['rows'],
            'remediation_rows': self.build_remediation_plan()['rows'],
            'risk_diff': self.build_risk_diff(tenant_id=tenant_id),
            'ownership_rows': self.build_ownership_graph()['rows'],
            'patch_suggestions': self.build_patch_suggestions()['rows'],
            'stop_conditions': stop_conditions['rows'],
            'admin_contract': {
                'recommended_admin_artifacts': ['dashboard', 'risk_registry', 'remediation_workflow'],
                'status': PLATFORM_ADMIN_RUNTIME_MODE,
            },
            'live_widget_bundle': self.build_live_widget_bundle(overview_payload={}),
            'visual_conflict_map': self.build_visual_conflict_map(),
        }

    def build_risk_registry(self) -> dict[str, Any]:
        risk_rows = [
            self._risk_row('application/admin/platform_control_center_service.py', 'major', 'large_module', 'Keep owner service compact and avoid static optimism.'),
            self._risk_row('application/business_autonomy/provider_admin_service.py', 'major', 'surface_growth', 'Provider lifecycle breadth needs green end-to-end gates before production claims.'),
            self._risk_row('runtime/executor.py', 'major', 'gateway_breadth', 'Runtime executor is the canonical gateway; guard against hidden decision logic and god-module drift.'),
        ]
        return {'count': len(risk_rows), 'severity_counts': {'critical': 0, 'major': 3, 'minor': 0}, 'risk_rows': risk_rows}

    def build_dependency_graph(self) -> dict[str, Any]:
        rows = [
            {'from': 'control_plane_routes', 'to': 'admin_route_handlers'},
            {'from': 'admin_route_handlers', 'to': 'platform_control_center_service'},
            {'from': 'platform_control_center_service', 'to': 'repo_files_read_only'},
        ]
        return {'rows': rows, 'dependency_rows': rows, 'graph_source': 'read_only_advisory'}

    def build_remediation_plan(self) -> dict[str, Any]:
        rows = [
            {'file_path': 'application/admin/platform_control_center_service.py', 'risk_type': 'static_optimism', 'next_step': 'report advisory status and missing proof explicitly'},
            {'file_path': 'runtime/executor.py', 'risk_type': 'gateway_breadth', 'next_step': 'keep execution logic delegated and locked by tests'},
            {'file_path': 'application/business_autonomy/provider_admin_service.py', 'risk_type': 'provider_lifecycle_breadth', 'next_step': 'prove selected→credentials→health→read sync→advisory→approval-gated write→evidence with tests'},
        ]
        return {'rows': rows, 'remediation_rows': rows, 'mode': PLATFORM_ADMIN_RUNTIME_MODE}

    def build_risk_diff(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'risk_type': 'snapshot_diff_unavailable', 'change': 'unknown', 'reason': 'no persisted baseline snapshot wired into this service'}]
        return {'tenant_id': tenant_id, 'added': 0, 'removed': 0, 'changed': 0, 'snapshot_available': False, 'risk_diff_rows': rows, 'summary': 'snapshot diff is unavailable, not clean'}

    def build_ownership_graph(self) -> dict[str, Any]:
        rows = [{'owner': 'application.admin.platform_control_center_service', 'surface': 'platform_control_center', 'mode': PLATFORM_ADMIN_RUNTIME_MODE}]
        return {'rows': rows, 'ownership_rows': rows}

    def build_patch_suggestions(self) -> dict[str, Any]:
        rows = [
            {'file_path': 'application/admin/platform_control_center_service.py', 'patch_hint': 'keep service read-only and honest; do not emit fake patch_code'},
            {'file_path': 'tests/', 'patch_hint': 'add/keep locks for admin honesty, provider write guard, and execution contract'},
        ]
        return {'rows': rows, 'patch_suggestion_rows': rows, 'patch_suggestions': rows}

    def build_snapshot_diff_view(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'file_path': 'repository', 'status': 'unknown', 'reason': 'baseline snapshot store is not wired'}]
        return {'tenant_id': tenant_id, 'changed_files': None, 'summary': 'snapshot drift cannot be determined from this advisory service', 'snapshot_available': False, 'code_diff_rows': rows}

    def build_file_passport(self, *, file_path: str) -> dict[str, Any]:
        path = self.repo_root / file_path
        exists = _file_exists(path)
        return {
            'file_path': file_path,
            'exists': exists,
            'code_navigation': {'editor_hint': f'open:{file_path}:1'},
            'dependency_context': {'imports': ['pathlib', 'dataclasses'], 'import_count': 2, 'status': 'static_advisory'},
            'passport_cards': {'structure': {'python_lines': _count_python_lines(path) if exists else 0}},
        }

    def build_ownership_drilldown(self, *, block: str) -> dict[str, Any]:
        rows = [{'owner': 'application.admin.platform_control_center_service', 'reason': 'final admin owner', 'mode': PLATFORM_ADMIN_RUNTIME_MODE}]
        return {'block': block, 'owners': rows, 'owner_rows': rows}

    def build_risk_trends(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'period': 'current', 'major': 3, 'minor': 0, 'source': 'advisory_snapshot'}]
        return {'tenant_id': tenant_id, 'trend_rows': rows, 'trend_available': False, 'reason': 'historical risk snapshots are not wired'}

    def build_maturity_trends(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'period': 'current', 'maturity': None, 'source': 'not_computed'}]
        return {'tenant_id': tenant_id, 'trend_rows': rows, 'maturity_trend_rows': rows, 'trend_available': False, 'reason': 'maturity is not computed without repository gates and runtime evidence'}

    def build_stop_conditions(self) -> dict[str, Any]:
        rows = [
            {'name': 'full_pytest_green', 'state': 'open', 'required_for': 'production_ready'},
            {'name': 'canonical_decision_execution_verification_evidence_e2e', 'state': 'open', 'required_for': 'production_ready'},
            {'name': 'provider_lifecycle_e2e_with_approval_gated_write', 'state': 'open', 'required_for': 'live_write'},
            {'name': 'sealed_effects_scan_green', 'state': 'open', 'required_for': 'production_ready'},
            {'name': 'server_health_green', 'state': 'open', 'required_for': 'staging_operational'},
        ]
        return {'rows': rows, 'stop_condition_rows': rows, 'stop_conditions': rows, 'status': 'not_closed'}

    def build_live_widget_bundle(self, *, overview_payload: Mapping[str, Any]) -> dict[str, Any]:
        del overview_payload
        widgets = [{'id': 'risk-summary', 'status': 'advisory'}, {'id': 'stop-conditions', 'status': 'open'}]
        return {'polling': {'enabled': True, 'interval_seconds': 30}, 'widgets': widgets, 'widget_rows': widgets, 'mode': PLATFORM_ADMIN_RUNTIME_MODE}

    def build_visual_conflict_map(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        return {'conflicts': rows, 'conflict_rows': rows, 'visual_conflict_map': rows, 'status': 'no_conflicts_reported_by_static_advisory_surface'}

    def build_widget_runtime(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        return {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'runtime': PLATFORM_ADMIN_RUNTIME_MODE,
            'live_ready': False,
            'reason': 'widget runtime is advisory until backed by live runtime evidence and green gates',
        }

    def save_dashboard_layout(self, *, tenant_id: str, layout: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(layout or {})
        normalized.setdefault('mode', 'drag_drop_dashboard')
        return {'tenant_id': tenant_id, 'saved': True, 'layout': normalized, 'layout_rows': tuple(normalized.get('widgets') or ()), 'runtime_mode': PLATFORM_ADMIN_RUNTIME_MODE}

    def build_remediation_workflow(self, *, file_path: str, risk_type: str = '') -> dict[str, Any]:
        return RemediationWorkflowAssembler(self.repo_root).build_remediation_workflow(
            file_path=file_path,
            risk_rows=self.build_risk_registry()['risk_rows'],
            risk_type=risk_type,
        )

    def build_remediation_run(self, *, file_path: str, risk_type: str = '') -> dict[str, Any]:
        if risk_type != 'large_module':
            return {
                'status': 'manual_review_required',
                'file_path': file_path,
                'risk_type': risk_type or 'unspecified',
                'patch_code': None,
                'reason': 'admin surface must not generate pretend remediation patches without repository diff, tests, and owner context',
                'next_step': 'inspect file, prepare real diff, run targeted tests, then full gate',
            }
        return RemediationWorkflowAssembler(self.repo_root).build_remediation_run(
            file_path=file_path,
            risk_rows=self.build_risk_registry()['risk_rows'],
            risk_type=risk_type,
        )

    def _risk_row(self, file_path: str, severity: str, risk_type: str, detail: str) -> dict[str, Any]:
        return {
            'file_path': file_path,
            'severity': severity,
            'risk_type': risk_type,
            'detail': detail,
            'stop_condition': f'close:{risk_type}',
            'code_navigation': {'editor_hint': f'open:{file_path}:1'},
        }


__all__ = ['CANON_PLATFORM_CONTROL_CENTER_SERVICE', 'PLATFORM_ADMIN_RUNTIME_MODE', 'PlatformControlCenterService']
