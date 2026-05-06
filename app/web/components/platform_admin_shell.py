from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from shared.kinded_payloads import build_kinded_payload

CANON_PLATFORM_ADMIN_SHELL = True


@dataclass(frozen=True, slots=True)
class PlatformAdminShell:
    kind: str = 'platform_admin_shell'

    def build(
        self,
        *,
        tenant_id: str,
        business_id: str,
        title: str,
        subtitle: str,
        summary_cards: Sequence[dict[str, Any]],
        quick_actions: Sequence[dict[str, Any]],
        provider_buttons: Sequence[dict[str, Any]],
        status_badges: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        hero = {
            'title': title,
            'subtitle': subtitle,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'display_density': 'comfortable',
            'accent': 'operator',
        }
        toolbar = {
            'primary_actions': list(provider_buttons),
            'secondary_actions': list(quick_actions),
            'search': {
                'placeholder': 'Поиск по файлам, рискам, блокам и провайдерам',
                'binds_to': ('risk_rows', 'block_rows', 'provider_rows', 'patch_suggestions', 'file_passports'),
            },
            'live_controls': {'refresh': True, 'pause': True, 'polling_seconds': 15},
        }
        tabs = (
            {'key': 'overview', 'label': 'Overview', 'icon': 'layout-dashboard'},
            {'key': 'providers', 'label': 'Providers', 'icon': 'plug'},
            {'key': 'risks', 'label': 'Risks', 'icon': 'triangle-alert'},
            {'key': 'remediation', 'label': 'Remediation', 'icon': 'wrench'},
            {'key': 'ownership', 'label': 'Ownership', 'icon': 'git-branch'},
            {'key': 'history', 'label': 'History', 'icon': 'history'},
        )
        return build_kinded_payload(
            self.kind,
            {
                'hero': hero,
                'toolbar': toolbar,
                'status_badges': list(status_badges),
                'summary_strip': list(summary_cards),
                'tabs': list(tabs),
                'layout': {
                    'sidebar': 'filters_and_drilldowns',
                    'main': 'tabbed_workspace',
                    'right_rail': 'risk_focus_patch_editor_and_actions',
                    'split_view': {'left': 'graph_navigation', 'center': 'workspace', 'right': 'inline_patch_editor'},
                    'drag_drop_enabled': True,
                },
            },
        )


__all__ = ['CANON_PLATFORM_ADMIN_SHELL', 'PlatformAdminShell']
