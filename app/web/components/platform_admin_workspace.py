from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from shared.kinded_payloads import build_kinded_payload

CANON_PLATFORM_ADMIN_WORKSPACE = True


@dataclass(frozen=True, slots=True)
class PlatformAdminWorkspace:
    kind: str = 'platform_admin_workspace'

    def build(
        self,
        *,
        graphs: Mapping[str, Any],
        block_rows: Sequence[Mapping[str, Any]],
        risk_rows: Sequence[Mapping[str, Any]],
        provider_rows: Sequence[Mapping[str, Any]],
        dependency_rows: Sequence[Mapping[str, Any]],
        ownership_rows: Sequence[Mapping[str, Any]],
        remediation_rows: Sequence[Mapping[str, Any]],
        patch_suggestions: Sequence[Mapping[str, Any]],
        stop_conditions: Sequence[Mapping[str, Any]],
        snapshot_diff_view: Mapping[str, Any],
        block_maturity_trends: Sequence[Mapping[str, Any]],
        live_widget_bundle: Mapping[str, Any],
        visual_conflict_map: Mapping[str, Any],
        dashboard_layout: Mapping[str, Any],
    ) -> dict[str, Any]:
        overview_panels = (
            {'kind': 'live_widgets', 'title': 'Live widgets', 'payload': dict(live_widget_bundle)},
            {'kind': 'widget_runtime_hooks', 'title': 'Widget runtime hooks', 'payload': dict(live_widget_bundle.get('runtime_hooks') or {})},
            {
                'kind': 'card_grid',
                'title': 'Fleet and risk overview',
                'cards': (
                    {'key': 'businesses_by_channel', 'title': 'Businesses by channel', 'chart_type': 'bar', 'rows': list(graphs.get('businesses_by_channel') or []), 'click_action': 'open_provider_panel'},
                    {'key': 'businesses_by_region', 'title': 'Businesses by region', 'chart_type': 'bar', 'rows': list(graphs.get('businesses_by_region') or []), 'click_action': 'open_region_panel'},
                    {'key': 'risk_severity', 'title': 'Risk severity', 'chart_type': 'donut', 'rows': list(graphs.get('risk_severity') or []), 'click_action': 'open_risk_registry'},
                    {'key': 'block_risk_scores', 'title': 'Block risk scores', 'chart_type': 'bar', 'rows': list(graphs.get('block_risk_scores') or []), 'click_action': 'open_ownership_drilldown'},
                ),
            },
            {
                'kind': 'data_table',
                'title': 'Project blocks',
                'rows': list(block_rows),
                'columns': ('block', 'python_files', 'python_lines', 'risk_score', 'maturity'),
                'drilldown_action': {'type': 'ownership_drilldown', 'field': 'block'},
            },
        )
        provider_panels = (
            {'kind': 'provider_cards', 'title': 'Provider intake and activation', 'rows': list(provider_rows), 'status_field': 'connection_status', 'action': 'open_provider_modal'},
        )
        risk_panels = (
            {'kind': 'data_table', 'title': 'Risk registry', 'rows': list(risk_rows), 'columns': ('severity', 'risk_type', 'file_path', 'recommended_change', 'possible_conflict'), 'drilldown_action': {'type': 'file_passport', 'field': 'file_path'}},
            {'kind': 'dependency_heatmap', 'title': 'Dependency heatmap', 'heatmap_ui': dict(graphs.get('dependency_heatmap_ui') or {}), 'rows': list(graphs.get('dependency_heatmap') or [])},
            {'kind': 'visual_conflict_map', 'title': 'Visual conflict map', 'payload': dict(visual_conflict_map)},
            {'kind': 'data_table', 'title': 'Dependency edges', 'rows': list(dependency_rows), 'columns': ('source_block', 'target_block', 'import_count', 'edge_kind')},
        )
        remediation_panels = (
            {'kind': 'data_table', 'title': 'Remediation plan', 'rows': list(remediation_rows), 'columns': ('file_path', 'severity', 'change_summary', 'change_target', 'suggested_patch_shape'), 'action': 'launch_remediation_run'},
            {'kind': 'data_table', 'title': 'Patch suggestions', 'rows': list(patch_suggestions), 'columns': ('file_path', 'risk_type', 'severity', 'patch_summary', 'patch_template'), 'action': 'preview_patch_code'},
            {'kind': 'inline_patch_editor', 'title': 'Inline patch-code preview editor', 'source': 'patch_suggestions', 'editor_mode': 'side_by_side'},
            {'kind': 'data_table', 'title': 'Stop conditions', 'rows': list(stop_conditions), 'columns': ('block', 'current_maturity', 'risk_score', 'critical_count', 'progress_percent', 'stop_condition')},
        )
        ownership_panels = (
            {'kind': 'data_table', 'title': 'Ownership graph', 'rows': list(ownership_rows), 'columns': ('block', 'owner_status', 'owner_strength', 'inbound_edges', 'outbound_edges', 'risk_count'), 'drilldown_action': {'type': 'ownership_drilldown', 'field': 'block'}},
            {'kind': 'clickable_graph_navigation', 'title': 'Clickable graph navigation', 'rows': list(dependency_rows), 'graph_ui': {'kind': 'clickable_graph_navigation', 'drilldown_endpoint': '/control-plane/admin/platform-ownership-drilldown'}},
        )
        history_panels = (
            {'kind': 'snapshot_diff', 'title': 'Snapshot diff', 'payload': dict(snapshot_diff_view)},
            {'kind': 'trend_table', 'title': 'Block maturity trends', 'rows': list(block_maturity_trends), 'columns': ('block', 'latest_maturity', 'latest_risk_score', 'maturity_score')},
        )
        return build_kinded_payload(
            self.kind,
            {
                'tabs': {
                    'overview': list(overview_panels),
                    'providers': list(provider_panels),
                    'risks': list(risk_panels),
                    'remediation': list(remediation_panels),
                    'ownership': list(ownership_panels),
                    'history': list(history_panels),
                },
                'dashboard_layout': dict(dashboard_layout),
                'multi_panel_split_view': {'enabled': True, 'panes': ('left_graphs', 'center_tables', 'right_patch_editor')},
            },
        )


__all__ = ['CANON_PLATFORM_ADMIN_WORKSPACE', 'PlatformAdminWorkspace']
