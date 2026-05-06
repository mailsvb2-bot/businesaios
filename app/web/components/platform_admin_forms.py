from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from shared.kinded_payloads import build_kinded_payload

CANON_PLATFORM_ADMIN_FORMS = True


@dataclass(frozen=True, slots=True)
class PlatformAdminForms:
    kind: str = 'platform_admin_forms'

    def build(self, *, provider_rows: Sequence[Mapping[str, Any]], actions: Mapping[str, Any]) -> dict[str, Any]:
        modal_forms = []
        for row in provider_rows:
            provider_key = str(row.get('provider_key') or '').strip()
            title = str(row.get('title') or provider_key)
            if not provider_key:
                continue
            modal_forms.append(
                {
                    'provider_key': provider_key,
                    'title': f'Ввести токен для {title}',
                    'submit_endpoint': actions.get('provider_activate_endpoint'),
                    'fields': [
                        {'name': 'tenant_id', 'type': 'text', 'required': True},
                        {'name': 'business_id', 'type': 'text', 'required': True},
                        {'name': 'secret_payload', 'type': 'secret_bundle', 'required': True, 'provider_key': provider_key},
                        {'name': 'activate_runtime', 'type': 'boolean', 'required': False, 'default': bool(str(row.get('domain') or '') == 'platform_infra')},
                        {'name': 'probe_mode', 'type': 'select', 'required': False, 'default': 'dry_run', 'options': ('dry_run', 'live')},
                    ],
                    'success_toast': 'Данные приняты. Подключение и onboarding запущены.',
                }
            )
        drawers = {
            'file_passport': {'title': 'Архитектурный паспорт файла', 'endpoint': actions.get('file_passport_endpoint'), 'open_mode': 'drawer', 'card_mode': 'rich_passport_cards'},
            'ownership_drilldown': {'title': 'Ownership drill-down', 'endpoint': actions.get('ownership_drilldown_endpoint'), 'open_mode': 'drawer'},
            'patch_preview': {'title': 'Patch preview', 'source': 'patch_suggestions', 'open_mode': 'drawer'},
            'inline_patch_editor': {'title': 'Inline patch editor', 'source': 'patch_suggestions', 'open_mode': 'right_rail', 'editor_mode': 'inline_code_editor'},
            'provider_secret_history': {'title': 'Secret version history', 'endpoint': actions.get('provider_secret_history_endpoint'), 'open_mode': 'drawer'},
            'provider_runtime_routes': {'title': 'Provider runtime routes', 'endpoint': actions.get('provider_runtime_routes_endpoint'), 'open_mode': 'drawer'},
            'provider_response_parser': {'title': 'Provider response parser', 'endpoint': actions.get('provider_response_parser_endpoint'), 'open_mode': 'drawer'},
            'provider_sync_history': {'title': 'Provider sync history', 'endpoint': actions.get('provider_sync_history_endpoint'), 'open_mode': 'drawer'},
        }
        action_forms = {
            'provider_rotate': {
                'endpoint': actions.get('provider_rotate_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                    {'name': 'secrets', 'type': 'secret_bundle', 'required': True},
                ),
                'response_surfaces': ('metadata', 'connected', 'last_updated_utc'),
            },
            'provider_reconnect': {
                'endpoint': actions.get('provider_reconnect_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                    {'name': 'probe_mode', 'type': 'select', 'required': False, 'default': 'dry_run', 'options': ('dry_run', 'live')},
                    {'name': 'activate_runtime', 'type': 'boolean', 'required': False, 'default': False},
                ),
                'response_surfaces': ('metadata', 'connected', 'onboarding_ready'),
            },
            'provider_revoke': {
                'endpoint': actions.get('provider_revoke_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                ),
                'response_surfaces': ('metadata', 'connected'),
            },
            'provider_secret_rollback': {
                'endpoint': actions.get('provider_secret_rollback_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                    {'name': 'secret_name', 'type': 'text', 'required': True},
                    {'name': 'version', 'type': 'text', 'required': True},
                ),
                'response_surfaces': ('rollback', 'status'),
            },
            'provider_sync': {
                'endpoint': actions.get('provider_sync_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                    {'name': 'operation', 'type': 'text', 'required': True},
                    {'name': 'mode', 'type': 'select', 'required': False, 'default': 'dry_run', 'options': ('dry_run', 'live')},
                    {'name': 'payload', 'type': 'json', 'required': False},
                ),
                'response_surfaces': ('status', 'accepted', 'metadata'),
            },
            'provider_webhook_ingest': {
                'endpoint': actions.get('provider_webhook_ingest_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'business_id', 'type': 'text', 'required': True},
                    {'name': 'provider_key', 'type': 'text', 'required': True},
                    {'name': 'event_key', 'type': 'text', 'required': True},
                    {'name': 'topic', 'type': 'text', 'required': False},
                    {'name': 'headers', 'type': 'json', 'required': False},
                    {'name': 'body', 'type': 'textarea', 'required': False},
                ),
                'response_surfaces': ('status', 'accepted', 'metadata'),
            },
            'remediation_run': {
                'endpoint': actions.get('remediation_run_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'file_path', 'type': 'text', 'required': True},
                    {'name': 'risk_type', 'type': 'text', 'required': False},
                ),
                'response_surfaces': ('workflow_steps', 'patch_code', 'code_navigation', 'next_action'),
            },
            'dashboard_layout_save': {
                'endpoint': actions.get('dashboard_layout_endpoint'),
                'method': 'POST',
                'fields': (
                    {'name': 'tenant_id', 'type': 'text', 'required': True},
                    {'name': 'layout', 'type': 'drag_drop_layout', 'required': True},
                ),
                'response_surfaces': ('layout',),
            },
        }
        return build_kinded_payload(self.kind, {'provider_modals': modal_forms, 'drawers': drawers, 'action_forms': action_forms})


__all__ = ['CANON_PLATFORM_ADMIN_FORMS', 'PlatformAdminForms']
