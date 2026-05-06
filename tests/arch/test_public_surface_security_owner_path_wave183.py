from __future__ import annotations

from pathlib import Path


def test_public_routes_use_canonical_public_surface_security_guard() -> None:
    source = Path('adapters/api/fastapi/public_routes.py').read_text(encoding='utf-8')
    assert 'PublicSurfaceSecurityGuard' in source
    assert "enforce_public_security(route_path='/actions/execute'" in source
    assert "RequestContext.from_http_request" in source


def test_public_surface_security_guard_remains_single_owner() -> None:
    source = Path('entrypoints/api/public_surface_security_guard.py').read_text(encoding='utf-8')
    assert 'CANON_API_PUBLIC_SURFACE_SECURITY_GUARD = True' in source
    assert '_ROUTE_SPECS' in source
    assert 'SecurityIntegrationAdapter' in source
