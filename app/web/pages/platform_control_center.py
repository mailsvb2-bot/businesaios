from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components import PlatformAdminForms, PlatformAdminLiveRenderers, PlatformAdminShell, PlatformAdminWorkspace
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_PLATFORM_CONTROL_CENTER_PAGE = True


@dataclass(frozen=True, slots=True)
class PlatformControlCenterPage:
    shell: PlatformAdminShell = field(default_factory=PlatformAdminShell)
    workspace: PlatformAdminWorkspace = field(default_factory=PlatformAdminWorkspace)
    forms: PlatformAdminForms = field(default_factory=PlatformAdminForms)
    live_renderers: PlatformAdminLiveRenderers = field(default_factory=PlatformAdminLiveRenderers)
    kind: str = 'platform_control_center_page'

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        business_id = str(normalized.get('business_id') or '').strip() or 'default-business'
        actions = {
            'overview_endpoint': '/control-plane/admin/platform-overview',
            'risk_registry_endpoint': '/control-plane/admin/platform-risks',
            'provider_catalog_endpoint': '/control-plane/provider-admin/catalog',
            'provider_capabilities_endpoint': '/control-plane/provider-admin/capabilities',
            'provider_activate_endpoint': '/control-plane/provider-admin/activate',
            'provider_secret_history_endpoint': '/control-plane/provider-admin/secret-history',
            'provider_secret_rollback_endpoint': '/control-plane/provider-admin/secret-rollback',
            'provider_runtime_routes_endpoint': '/control-plane/provider-runtime/routes',
            'provider_response_parser_endpoint': '/control-plane/provider-runtime/response-parser',
            'provider_sync_history_endpoint': '/control-plane/provider-runtime/sync-history',
            'provider_rotate_endpoint': '/control-plane/provider-admin/rotate',
            'provider_reconnect_endpoint': '/control-plane/provider-admin/reconnect',
            'provider_revoke_endpoint': '/control-plane/provider-admin/revoke',
            'provider_sync_endpoint': '/control-plane/provider-runtime/sync',
            'provider_webhook_ingest_endpoint': '/control-plane/provider-runtime/webhook-ingest',
            'dependency_graph_endpoint': '/control-plane/admin/platform-dependencies',
            'remediation_endpoint': '/control-plane/admin/platform-remediation',
            'risk_diff_endpoint': '/control-plane/admin/platform-risk-diff',
            'ownership_endpoint': '/control-plane/admin/platform-ownership',
            'patch_suggestions_endpoint': '/control-plane/admin/platform-patch-suggestions',
            'risk_trends_endpoint': '/control-plane/admin/platform-risk-trends',
            'stop_conditions_endpoint': '/control-plane/admin/platform-stop-conditions',
            'remediation_workflow_endpoint': '/control-plane/admin/platform-remediation-workflow',
            'remediation_run_endpoint': '/control-plane/admin/platform-remediation-run',
            'snapshot_diff_view_endpoint': '/control-plane/admin/platform-snapshot-diff-view',
            'file_passport_endpoint': '/control-plane/admin/platform-file-passport',
            'ownership_drilldown_endpoint': '/control-plane/admin/platform-ownership-drilldown',
            'maturity_trends_endpoint': '/control-plane/admin/platform-maturity-trends',
            'live_widgets_endpoint': '/control-plane/admin/platform-live-widgets',
            'visual_conflict_map_endpoint': '/control-plane/admin/platform-visual-conflicts',
            'dashboard_layout_endpoint': '/control-plane/admin/platform-dashboard-layout',
            'widget_runtime_endpoint': '/control-plane/admin/platform-widget-runtime',
        }
        summary_cards = tuple(normalized.get('summary_cards') or ())
        provider_rows = tuple(normalized.get('provider_rows') or ())
        primary_buttons = tuple({'label': f"Ввести токен для {row.get('title')}", 'provider_key': row.get('provider_key'), 'action': 'open_modal'} for row in provider_rows[:10]) or (
            {'label': 'Ввести токен для Telegram Bot', 'provider_key': 'telegram_bot', 'action': 'open_modal'},
            {'label': 'Ввести токен для Shopify', 'provider_key': 'shopify', 'action': 'open_modal'},
        )
        secondary_buttons = (
            {'label': 'Обновить overview', 'action': 'refresh_overview'},
            {'label': 'Live refresh', 'action': 'start_polling'},
            {'label': 'Открыть risk registry', 'action': 'open_risks'},
            {'label': 'Открыть dependency graph', 'action': 'open_dependencies'},
            {'label': 'Открыть ownership graph', 'action': 'open_ownership'},
            {'label': 'Открыть remediation plan', 'action': 'open_remediation'},
            {'label': 'Открыть patch suggestions', 'action': 'open_patch_suggestions'},
            {'label': 'Открыть risk diff', 'action': 'open_risk_diff'},
            {'label': 'Открыть historical trends', 'action': 'open_trends'},
            {'label': 'Открыть stop conditions', 'action': 'open_stop_conditions'},
            {'label': 'Открыть snapshot diff', 'action': 'open_snapshot_diff'},
            {'label': 'Открыть maturity trends', 'action': 'open_maturity_trends'},
            {'label': 'Открыть visual conflict map', 'action': 'open_visual_conflicts'},
        )
        status_badges = (
            {'label': 'Tenant bound', 'tone': 'success'},
            {'label': 'Control plane connected', 'tone': 'info'},
            {'label': 'Canon admin policy enforced', 'tone': 'warning' if not normalized.get('canon_status') else 'success'},
            {'label': 'Live widgets enabled', 'tone': 'success'},
        )
        shell = self.shell.build(
            tenant_id=tenant_id,
            business_id=business_id,
            title='Индивидуальная админка / Platform Control Center',
            subtitle='Единая админка со статистикой, токенами, live widgets, drag/drop dashboard, графами, remediation workflow, patch editor и code-aware рекомендациями по всем блокам проекта.',
            summary_cards=summary_cards,
            quick_actions=secondary_buttons,
            provider_buttons=primary_buttons,
            status_badges=status_badges,
        )['payload']
        workspace = self.workspace.build(
            graphs=dict(normalized.get('graphs') or {}),
            block_rows=tuple(normalized.get('block_rows') or ()),
            risk_rows=tuple(normalized.get('risk_rows') or ()),
            provider_rows=provider_rows,
            dependency_rows=tuple(normalized.get('dependency_rows') or ()),
            ownership_rows=tuple(normalized.get('ownership_rows') or ()),
            remediation_rows=tuple(normalized.get('remediation_rows') or ()),
            patch_suggestions=tuple(normalized.get('patch_suggestions') or ()),
            stop_conditions=tuple(normalized.get('stop_conditions') or ()),
            snapshot_diff_view=dict(normalized.get('snapshot_diff_view') or {}),
            block_maturity_trends=tuple(normalized.get('block_maturity_trends') or ()),
            live_widget_bundle=dict(normalized.get('live_widget_bundle') or {}),
            visual_conflict_map=dict(normalized.get('visual_conflict_map') or {}),
            dashboard_layout=dict(normalized.get('dashboard_layout') or {}),
        )['payload']
        forms = self.forms.build(provider_rows=provider_rows, actions=actions)['payload']
        live_renderers = self.live_renderers.build(actions=actions, live_widget_bundle=dict(normalized.get('live_widget_bundle') or {}), provider_rows=provider_rows)['payload']
        return build_kinded_payload(
            self.kind,
            {
                'tenant_id': tenant_id,
                'business_id': business_id,
                'title': shell['hero']['title'],
                'subtitle': shell['hero']['subtitle'],
                'summary_cards': summary_cards,
                'graphs': dict(normalized.get('graphs') or {}),
                'block_rows': tuple(normalized.get('block_rows') or ()),
                'risk_rows': tuple(normalized.get('risk_rows') or ()),
                'provider_rows': provider_rows,
                'snapshot_diff_view': dict(normalized.get('snapshot_diff_view') or {}),
                'block_maturity_trends': tuple(normalized.get('block_maturity_trends') or ()),
                'dependency_rows': tuple(normalized.get('dependency_rows') or ()),
                'conflict_rows': tuple(normalized.get('conflict_rows') or ()),
                'ownership_rows': tuple(normalized.get('ownership_rows') or ()),
                'remediation_rows': tuple(normalized.get('remediation_rows') or ()),
                'patch_suggestions': tuple(normalized.get('patch_suggestions') or ()),
                'stop_conditions': tuple(normalized.get('stop_conditions') or ()),
                'risk_diff': dict(normalized.get('risk_diff') or {}),
                'canon_status': dict(normalized.get('canon_status') or {}),
                'admin_contract': dict(normalized.get('admin_contract') or {}),
                'live_widget_bundle': dict(normalized.get('live_widget_bundle') or {}),
                'dashboard_layout': dict(normalized.get('dashboard_layout') or {}),
                'visual_conflict_map': dict(normalized.get('visual_conflict_map') or {}),
                'actions': actions,
                'shell': shell,
                'workspace': workspace,
                'forms': forms,
                'live_renderers': live_renderers,
                'ui_schema': {
                    'sections': (
                        'summary_cards', 'graphs', 'block_rows', 'risk_rows', 'provider_rows', 'dependency_rows', 'conflict_rows', 'ownership_rows', 'remediation_rows', 'patch_suggestions', 'stop_conditions', 'risk_diff', 'snapshot_diff_view', 'block_maturity_trends', 'canon_status', 'shell', 'workspace', 'forms', 'live_renderers', 'live_widget_bundle', 'dashboard_layout', 'visual_conflict_map',
                    ),
                    'primary_buttons': primary_buttons,
                    'secondary_buttons': secondary_buttons,
                    'risk_registry_columns': ('severity', 'risk_type', 'file_path', 'recommended_change', 'possible_conflict', 'code_navigation', 'architectural_score', 'stop_condition'),
                    'dependency_graph_columns': ('source_block', 'target_block', 'import_count', 'edge_kind'),
                    'ownership_columns': ('block', 'owner_status', 'owner_strength', 'inbound_edges', 'outbound_edges', 'risk_count', 'recommended_change'),
                    'conflict_columns': ('conflict_kind', 'source_block', 'target_block', 'summary', 'recommended_change', 'possible_conflict'),
                    'remediation_columns': ('file_path', 'severity', 'change_summary', 'change_target', 'suggested_patch_shape', 'code_navigation', 'architectural_score', 'stop_condition'),
                    'patch_suggestion_columns': ('file_path', 'risk_type', 'severity', 'patch_summary', 'patch_template', 'patch_code', 'code_navigation', 'apply_endpoint'),
                    'stop_condition_columns': ('block', 'current_maturity', 'risk_score', 'risk_count', 'critical_count', 'progress_percent', 'stop_condition'),
                    'snapshot_diff_columns': ('file_path', 'risk_type', 'previous_severity', 'current_severity', 'diff_summary', 'code_navigation'),
                    'maturity_trend_columns': ('block', 'latest_maturity', 'latest_risk_score', 'maturity_score', 'history'),
                    'file_passport_columns': ('file_path', 'block', 'python_lines', 'imports', 'owner_guess', 'architectural_score', 'recommended_change', 'code_navigation'),
                    'layout_mode': 'luxury_operator_console_live',
                    'supports_drawers': True,
                    'supports_modal_forms': True,
                    'supports_patch_preview': True,
                    'supports_inline_patch_editor': True,
                    'supports_drag_drop_layout': True,
                    'supports_live_polling': True,
                    'supports_clickable_graph_navigation': True,
                    'supports_multi_panel_split_view': True,
                    'supports_visual_conflict_map': True,
                    'supports_file_passport_cards': True,
                    'modal_behavior': 'provider_secrets_and_admin_actions',
                    'polling': {'enabled': True, 'default_refresh_seconds': 15, 'endpoint': actions['live_widgets_endpoint']},
                    'widget_runtime_hooks_endpoint': actions['widget_runtime_endpoint'],
                    'asset_bundle': {'runtime_hook_js': '/web/static/platform_admin_runtime_hooks.js'},
                },
            },
        )


__all__ = ['CANON_WEB_PLATFORM_CONTROL_CENTER_PAGE', 'PlatformControlCenterPage']
