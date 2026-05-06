from __future__ import annotations

"""Canonical web pages package surface with explicit owner exports.

The historical ``public_api`` import path is now installed directly by the
package owner instead of a dedicated compat package directory.
"""

from typing import Final

from runtime.public_api_alias import install_public_api_alias

from app.web.pages.admin import AdminPage
from app.web.pages.analytics import AnalyticsPage
from app.web.pages.approvals import ApprovalsPage
from app.web.pages.audit import AuditPage
from app.web.pages.connector_admin import ConnectorAdminPage
from app.web.pages.inference_capacity import InferenceCapacityPage
from app.web.pages.inference_runtime_admin import InferenceRuntimeAdminPage
from app.web.pages.policy_overrides import PolicyOverridesPage
from app.web.pages.platform_control_center import PlatformControlCenterPage
from app.web.pages.client_outcomes import ClientOutcomesPage
from app.web.pages.provider_tokens_admin import ProviderTokensAdminPage
from app.web.pages.queue_history import QueueHistoryPage
from app.web.pages.queue_ops import QueueOpsPage
from app.web.pages.runtime_alerts import RuntimeAlertsPage
from app.web.pages.security import SecurityPage
from app.web.pages.tenants import TenantsPage
from app.web.payload_builder import KindedPayloadBuilder

_PAGE_KINDS: Final[dict[str, str]] = {
    'Autopilot': 'autopilot',
    'Campaigns': 'campaigns',
    'Connectors': 'connectors',
    'Dashboard': 'dashboard',
    'Leads': 'leads',
    'Marketplace': 'marketplace',
    'Notifications': 'notifications',
    'Onboarding': 'onboarding',
    'Platforms': 'platforms',
    'Revenue': 'revenue',
    'Seo': 'seo',
    'Settings': 'settings',
}


def _page_type(name: str, kind: str) -> type[KindedPayloadBuilder]:
    return type(name, (KindedPayloadBuilder,), {'KIND': kind})


PAGE_BUILDERS: Final[dict[str, type[KindedPayloadBuilder]]] = {
    name: _page_type(name, kind) for name, kind in _PAGE_KINDS.items()
}

globals().update(PAGE_BUILDERS)

ADMIN_PAGES = {
    'AdminPage': AdminPage,
    'ApprovalsPage': ApprovalsPage,
    'AuditPage': AuditPage,
    'ConnectorAdminPage': ConnectorAdminPage,
    'ProviderTokensAdminPage': ProviderTokensAdminPage,
    'PlatformControlCenterPage': PlatformControlCenterPage,
    'InferenceCapacityPage': InferenceCapacityPage,
    'InferenceRuntimeAdminPage': InferenceRuntimeAdminPage,
    'PolicyOverridesPage': PolicyOverridesPage,
    'RuntimeAlertsPage': RuntimeAlertsPage,
    'QueueOpsPage': QueueOpsPage,
    'QueueHistoryPage': QueueHistoryPage,
    'SecurityPage': SecurityPage,
    'TenantsPage': TenantsPage,
    'AnalyticsPage': AnalyticsPage,
    'ClientOutcomesPage': ClientOutcomesPage,
}

globals().update(ADMIN_PAGES)
install_public_api_alias(__name__)

__all__ = tuple(PAGE_BUILDERS) + tuple(ADMIN_PAGES) + ('PAGE_BUILDERS', 'ADMIN_PAGES')
