from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from shared.kinded_payloads import build_kinded_payload

CANON_PLATFORM_ADMIN_LIVE_RENDERERS = True

@dataclass(frozen=True, slots=True)
class PlatformAdminLiveRenderers:
    kind: str = 'platform_admin_live_renderers'

    def build(self, *, actions: Mapping[str, Any], live_widget_bundle: Mapping[str, Any], provider_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        widget_rows = list(live_widget_bundle.get('widgets') or ())
        return build_kinded_payload(
            self.kind,
            {
                'assets': {'runtime_hook_js': '/web/static/platform_admin_runtime_hooks.js'},
                'widget_renderers': [
                    {
                        'widget_key': str(item.get('widget_key') or ''),
                        'component': str(item.get('renderer') or 'live_widget'),
                        'poll_endpoint': actions.get('live_widgets_endpoint'),
                        'refresh_seconds': int(item.get('refresh_seconds') or 15),
                        'render_target': f"widget:{str(item.get('widget_key') or '')}",
                    }
                    for item in widget_rows
                ],
                'runtime_hooks': {
                    'poll_json': {'kind': 'poll_json', 'endpoint': actions.get('live_widgets_endpoint'), 'refresh_seconds': int((live_widget_bundle.get('polling') or {}).get('refresh_seconds') or 15)},
                    'graph_navigation': {'kind': 'graph_navigation', 'endpoint': actions.get('ownership_drilldown_endpoint')},
                    'patch_preview': {'kind': 'patch_preview', 'endpoint': actions.get('remediation_run_endpoint')},
                    'layout_save': {'kind': 'layout_save', 'endpoint': actions.get('dashboard_layout_endpoint')},
                    'provider_activation': {'kind': 'provider_activation', 'endpoint': actions.get('provider_activate_endpoint')},
                },
                'provider_runtime_cards': [
                    {
                        'provider_key': str(row.get('provider_key') or ''),
                        'title': str(row.get('title') or ''),
                        'connected': bool(row.get('connected')),
                        'runtime_activation': dict(row.get('runtime_activation') or {}),
                        'health_probe': dict(row.get('health_probe') or {}),
                        'live_sync_runner': dict(row.get('live_sync_runner') or {}),
                        'webhook_replay_guard': dict(row.get('webhook_replay_guard') or {}),
                    }
                    for row in provider_rows
                ],
            },
        )

__all__ = ['CANON_PLATFORM_ADMIN_LIVE_RENDERERS', 'PlatformAdminLiveRenderers']
