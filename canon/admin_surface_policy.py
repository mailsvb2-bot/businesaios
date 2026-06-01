from __future__ import annotations

from dataclasses import dataclass

CANON_ADMIN_SURFACE_POLICY = True
ADMIN_SURFACE_POLICY = {
    'new_feature_must_be_visible_in_admin': True,
    'required_admin_artifacts': (
        'page_or_panel',
        'control_plane_endpoint',
        'risk_or_status_visibility',
    ),
    'recommended_admin_artifacts': (
        'code_navigation',
        'remediation_action',
        'graph_or_metric',
        'patch_suggestion',
        'stop_condition',
        'file_passport',
        'snapshot_diff',
        'live_widget',
        'visual_conflict_map',
        'dashboard_layout',
    ),
}


@dataclass(frozen=True)
class AdminSurfaceDeclaration:
    feature_name: str
    page_or_panel: str
    control_plane_endpoint: str
    risk_or_status_visibility: str

    def validate(self) -> None:
        if not str(self.feature_name).strip():
            raise ValueError('feature_name is required')
        if not str(self.page_or_panel).strip():
            raise ValueError('page_or_panel is required')
        if not str(self.control_plane_endpoint).strip():
            raise ValueError('control_plane_endpoint is required')
        if not str(self.risk_or_status_visibility).strip():
            raise ValueError('risk_or_status_visibility is required')


def assert_admin_surface_declared(declaration: AdminSurfaceDeclaration) -> None:
    declaration.validate()


__all__ = [
    'CANON_ADMIN_SURFACE_POLICY',
    'ADMIN_SURFACE_POLICY',
    'AdminSurfaceDeclaration',
    'assert_admin_surface_declared',
]
