from __future__ import annotations

from typing import Any

from application.public_site.service import PublicSiteService

CANON_PUBLIC_SITE_ROUTE_HANDLERS = True


class PublicSiteRouteHandlers:
    def __init__(self, service: PublicSiteService | None = None) -> None:
        self._service = service or PublicSiteService()

    def get_landing(self, *, include_roadmap: bool = True) -> dict[str, Any]:
        return self._service.landing(include_roadmap=include_roadmap)

    def get_capabilities(self, *, include_roadmap: bool = True) -> dict[str, Any]:
        return self._service.capabilities(include_roadmap=include_roadmap)

    def get_admin_status(self) -> dict[str, Any]:
        return self._service.admin_status()


def public_site_route_handlers() -> PublicSiteRouteHandlers:
    return PublicSiteRouteHandlers()


__all__ = ['CANON_PUBLIC_SITE_ROUTE_HANDLERS', 'PublicSiteRouteHandlers', 'public_site_route_handlers']
