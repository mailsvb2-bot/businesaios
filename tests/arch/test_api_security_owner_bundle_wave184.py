from pathlib import Path


def test_router_adapter_uses_shared_security_owner_bundle() -> None:
    text = Path('adapters/api/fastapi/router_adapter.py').read_text(encoding='utf-8')
    assert 'ApiSecurityOwnerBundle.default()' in text
    assert 'security_bundle.public_surface_guard' in text
    assert 'security_bundle.control_plane_guard' in text
    assert 'security_bundle.webhook_surface_guard' in text
    assert 'security_bundle.api_surface_guard' in text


def test_route_registration_no_longer_builds_parallel_default_guards_in_router_owner() -> None:
    router_text = Path('adapters/api/fastapi/router_adapter.py').read_text(encoding='utf-8')
    assert 'PublicSurfaceSecurityGuard.default()' not in router_text
    assert 'ControlPlaneSecurityGuard()' not in router_text
