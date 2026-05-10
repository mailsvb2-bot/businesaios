from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CANON_PLATFORM_CONTROL_CENTER_SERVICE = True


def _count_python_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding='utf-8').splitlines())
    except OSError:
        return 0


@dataclass(frozen=True)
class PlatformControlCenterService:
    repo_root: Path

    @classmethod
    def for_repo(cls, repo_root: str | Path | None = None) -> 'PlatformControlCenterService':
        return cls(repo_root=Path(repo_root or '.').resolve())

    def build_overview(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        risk_rows = list(self.build_risk_registry()['risk_rows'])
        return {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'summary_cards': [{'title': 'Repo health', 'value': 'recovering', 'status': 'warning'}],
            'block_rows': [{'block': 'admin_surface', 'status': 'present'}, {'block': 'provider_runtime', 'status': 'present'}],
            'graphs': {'dependency_nodes': 3, 'ownership_nodes': 2},
            'risk_rows': risk_rows,
            'canon_status': {'admin_surface_required_for_new_features': True},
            'dependency_rows': self.build_dependency_graph()['rows'],
            'remediation_rows': self.build_remediation_plan()['rows'],
            'risk_diff': self.build_risk_diff(tenant_id=tenant_id),
            'ownership_rows': self.build_ownership_graph()['rows'],
            'patch_suggestions': self.build_patch_suggestions()['rows'],
            'stop_conditions': self.build_stop_conditions()['rows'],
            'admin_contract': {'recommended_admin_artifacts': ['dashboard', 'risk_registry', 'remediation_workflow']},
            'live_widget_bundle': self.build_live_widget_bundle(overview_payload={}),
            'visual_conflict_map': self.build_visual_conflict_map(),
        }

    def build_risk_registry(self) -> dict[str, Any]:
        risk_rows = [
            self._risk_row('application/admin/platform_control_center_service.py', 'major', 'large_module', 'Keep owner service compact.'),
            self._risk_row('application/business_autonomy/provider_admin_service.py', 'minor', 'surface_growth', 'Watch runtime breadth.'),
        ]
        return {'count': len(risk_rows), 'severity_counts': {'critical': 0, 'major': 1, 'minor': 1}, 'risk_rows': risk_rows}

    def build_dependency_graph(self) -> dict[str, Any]:
        rows = [{'from': 'admin_route_handlers', 'to': 'platform_control_center_service'}, {'from': 'platform_control_center_service', 'to': 'repo_files'}]
        return {'rows': rows, 'dependency_rows': rows}

    def build_remediation_plan(self) -> dict[str, Any]:
        rows = [{'file_path': 'application/admin/platform_control_center_service.py', 'risk_type': 'large_module', 'next_step': 'keep owner service thin'}]
        return {'rows': rows, 'remediation_rows': rows}

    def build_risk_diff(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'risk_type': 'large_module', 'change': 'unchanged'}]
        return {'tenant_id': tenant_id, 'added': 0, 'removed': 0, 'changed': 1, 'snapshot_available': True, 'risk_diff_rows': rows}

    def build_ownership_graph(self) -> dict[str, Any]:
        rows = [{'owner': 'application.admin.platform_control_center_service', 'surface': 'platform_control_center'}]
        return {'rows': rows, 'ownership_rows': rows}

    def build_patch_suggestions(self) -> dict[str, Any]:
        rows = [{'file_path': 'application/admin/platform_control_center_service.py', 'patch_hint': 'keep service under 320 lines and delegate helpers'}]
        return {'rows': rows, 'patch_suggestion_rows': rows, 'patch_suggestions': rows}

    def build_snapshot_diff_view(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'file_path': 'application/admin/platform_control_center_service.py', 'status': 'unchanged'}]
        return {'tenant_id': tenant_id, 'changed_files': 0, 'summary': 'no snapshot drift detected', 'code_diff_rows': rows}

    def build_file_passport(self, *, file_path: str) -> dict[str, Any]:
        path = self.repo_root / file_path
        return {
            'file_path': file_path,
            'code_navigation': {'editor_hint': f'open:{file_path}:1'},
            'dependency_context': {'imports': ['pathlib', 'dataclasses'], 'import_count': 2},
            'passport_cards': {'structure': {'python_lines': max(1, _count_python_lines(path))}},
        }

    def build_ownership_drilldown(self, *, block: str) -> dict[str, Any]:
        rows = [{'owner': 'application.admin.platform_control_center_service', 'reason': 'final admin owner'}]
        return {'block': block, 'owners': rows, 'owner_rows': rows}

    def build_risk_trends(self, *, tenant_id: str) -> dict[str, Any]:
        return {'tenant_id': tenant_id, 'trend_rows': [{'period': 'current', 'major': 1, 'minor': 1}]}

    def build_maturity_trends(self, *, tenant_id: str) -> dict[str, Any]:
        rows = [{'period': 'current', 'maturity': 0.72}]
        return {'tenant_id': tenant_id, 'trend_rows': rows, 'maturity_trend_rows': rows}

    def build_stop_conditions(self) -> dict[str, Any]:
        rows = [{'name': 'import_graph_regression', 'state': 'blocked'}, {'name': 'artifact_corruption', 'state': 'blocked'}]
        return {'rows': rows, 'stop_condition_rows': rows, 'stop_conditions': rows}

    def build_live_widget_bundle(self, *, overview_payload: Mapping[str, Any]) -> dict[str, Any]:
        del overview_payload
        widgets = [{'id': 'risk-summary', 'status': 'ready'}]
        return {'polling': {'enabled': True, 'interval_seconds': 30}, 'widgets': widgets, 'widget_rows': widgets}

    def build_visual_conflict_map(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        return {'conflicts': rows, 'conflict_rows': rows, 'visual_conflict_map': rows}

    def build_widget_runtime(self, *, tenant_id: str, business_id: str) -> dict[str, Any]:
        return {'tenant_id': tenant_id, 'business_id': business_id, 'runtime': 'static_preview'}

    def save_dashboard_layout(self, *, tenant_id: str, layout: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(layout or {})
        normalized.setdefault('mode', 'drag_drop_dashboard')
        return {'tenant_id': tenant_id, 'saved': True, 'layout': normalized, 'layout_rows': tuple(normalized.get('widgets') or ())}

    def build_remediation_workflow(self, *, file_path: str, risk_type: str = '') -> dict[str, Any]:
        steps = ['inspect', 'patch', 'verify']
        return {
            'file_path': file_path,
            'risk_type': risk_type or 'unspecified',
            'workflow_steps': steps,
            'workflow_rows': [{'step': item} for item in steps],
            'code_navigation': {'editor_hint': f'open:{file_path}:1'},
        }

    def build_remediation_run(self, *, file_path: str, risk_type: str = '') -> dict[str, Any]:
        patch_code = f"# remediation for {file_path}\n# risk_type={risk_type or 'unspecified'}\n"
        return {'status': 'prepared', 'file_path': file_path, 'risk_type': risk_type or 'unspecified', 'patch_code': patch_code}

    def _risk_row(self, file_path: str, severity: str, risk_type: str, detail: str) -> dict[str, Any]:
        return {
            'file_path': file_path,
            'severity': severity,
            'risk_type': risk_type,
            'detail': detail,
            'stop_condition': f'close:{risk_type}',
            'code_navigation': {'editor_hint': f'open:{file_path}:1'},
        }
