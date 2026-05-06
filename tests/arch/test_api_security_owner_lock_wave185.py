from pathlib import Path


FORBIDDEN_PATTERNS = {
    "PublicSurfaceSecurityGuard.default()",
    "ControlPlaneSecurityGuard()",
    "WebhookSecuritySurfaceGuard.default()",
    "ApiSecuritySurfaceGuard.default()",
}


def test_fastapi_owner_wiring_does_not_build_local_security_defaults() -> None:
    root = Path('adapters/api/fastapi')
    for path in root.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        if path.name == 'router_adapter.py':
            continue
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in text, f"{path} must not build local security owner via {pattern}"


def test_api_entrypoints_do_not_hide_parallel_security_owner_bundle() -> None:
    allowed = {
        Path('entrypoints/api/security_owner_bundle.py'),
        Path('entrypoints/api/security_surface_guard.py'),
        Path('entrypoints/api/public_surface_security_guard.py'),
        Path('entrypoints/api/webhook_security_surface_guard.py'),
    }
    root = Path('entrypoints/api')
    for path in root.glob('*.py'):
        if path in allowed:
            continue
        text = path.read_text(encoding='utf-8')
        assert 'SecurityIntegrationAdapter(' not in text, f"{path} must not instantiate SecurityIntegrationAdapter directly"
        assert 'SecurityPolicyEngine(' not in text, f"{path} must not instantiate SecurityPolicyEngine directly"
        assert 'ImmutableEventStore(' not in text, f"{path} must not instantiate ImmutableEventStore directly"
        assert 'SecurityAuditLog(' not in text, f"{path} must not instantiate SecurityAuditLog directly"
