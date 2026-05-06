from __future__ import annotations

from typing import Any

from application.public_site.service import PublicSiteService

CANON_PUBLIC_SITE_ADMIN_PAGE = True


def build_public_site_admin_page(*, tenant_id: str | None = None) -> dict[str, Any]:
    service = PublicSiteService()
    status = service.admin_status()
    return {
        'page': 'public_site_admin',
        'tenant_id': tenant_id,
        'title': 'Public Site Control Plane',
        'status': status,
        'safe_to_publish': status['safe_to_publish'],
        'violations': status['violations'],
        'capabilities_summary': status['capabilities_summary'],
        'guards': status['guards'],
        'endpoints': status['endpoints'],
    }


__all__ = ['CANON_PUBLIC_SITE_ADMIN_PAGE', 'build_public_site_admin_page']
