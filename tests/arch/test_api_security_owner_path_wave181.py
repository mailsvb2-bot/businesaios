from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_auth_dependencies_use_api_security_surface_guard() -> None:
    content = _read('adapters/api/fastapi/auth_dependencies.py')
    assert 'ApiSecuritySurfaceGuard' in content
    assert 'self.security_guard.enforce(' in content


def test_tenant_route_guard_uses_api_security_surface_guard() -> None:
    content = _read('entrypoints/api/tenant_route_guards.py')
    assert 'ApiSecuritySurfaceGuard' in content
    assert 'self.security_guard.enforce(' in content


def test_interfaces_api_exports_security_surface_guard_alias() -> None:
    content = _read('interfaces/api/__init__.py')
    assert 'security_surface_guard' in content
