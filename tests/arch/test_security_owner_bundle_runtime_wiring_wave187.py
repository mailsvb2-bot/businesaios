from pathlib import Path


def test_fastapi_dependency_container_owns_shared_security_bundle_before_router_fallback() -> None:
    dependency_text = Path('adapters/api/fastapi/dependencies.py').read_text(encoding='utf-8')
    router_text = Path('adapters/api/fastapi/router_adapter.py').read_text(encoding='utf-8')

    assert 'def security_owner_bundle(self)' in dependency_text
    assert 'dependency_container.security_owner_bundle() if dependency_container is not None else ApiSecurityOwnerBundle.default()' in router_text


def test_only_guard_modules_call_security_adapter_evaluate_surface() -> None:
    allowed = {
        Path('app/web/app.py'),
        Path('entrypoints/api/security_surface_guard.py'),
        Path('entrypoints/api/public_surface_security_guard.py'),
        Path('entrypoints/api/webhook_security_surface_guard.py'),
        Path('security/security_integration_adapter.py'),
    }
    for path in Path('.').rglob('*.py'):
        if path.parts and path.parts[0] == 'tests':
            continue
        text = path.read_text(encoding='utf-8')
        if 'evaluate_surface(' not in text:
            continue
        assert path in allowed, f'{path} must not call evaluate_surface() outside canonical guard/adapter owners'
