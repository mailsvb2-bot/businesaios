from __future__ import annotations

"""Canonical shared security owner bundle for API surfaces.

This module keeps the API security contour on one shared adapter/audit path so
route registration does not silently create parallel security subsystems.
"""

from dataclasses import dataclass
from pathlib import Path

from entrypoints.api.control_plane_security_guard import ControlPlaneSecurityGuard
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.security_surface_guard import ApiSecuritySurfaceGuard
from entrypoints.api.webhook_security_surface_guard import WebhookSecuritySurfaceGuard
from security.owner_factory import build_security_infrastructure
from security.security_integration_adapter import SecurityIntegrationAdapter


CANON_API_SECURITY_OWNER_BUNDLE = True
CANON_API_FINAL_OWNER = True


@dataclass(frozen=True)
class ApiSecurityOwnerBundle:
    adapter: SecurityIntegrationAdapter
    api_surface_guard: ApiSecuritySurfaceGuard
    control_plane_guard: ControlPlaneSecurityGuard
    public_surface_guard: PublicSurfaceSecurityGuard
    webhook_surface_guard: WebhookSecuritySurfaceGuard

    @classmethod
    def default(cls, *, audit_path: str | Path | None = None) -> 'ApiSecurityOwnerBundle':
        path = Path(audit_path or 'runtime/data/security/api_owner_security_audit.jsonl')
        adapter = build_security_infrastructure(audit_path=path).adapter
        api_guard = ApiSecuritySurfaceGuard(adapter=adapter)
        return cls(
            adapter=adapter,
            api_surface_guard=api_guard,
            control_plane_guard=ControlPlaneSecurityGuard(security_guard=api_guard),
            public_surface_guard=PublicSurfaceSecurityGuard(adapter=adapter),
            webhook_surface_guard=WebhookSecuritySurfaceGuard(adapter=adapter),
        )


__all__ = [
    'ApiSecurityOwnerBundle',
    'CANON_API_FINAL_OWNER',
    'CANON_API_SECURITY_OWNER_BUNDLE',
]
