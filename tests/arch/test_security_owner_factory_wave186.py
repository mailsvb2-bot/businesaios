from pathlib import Path


def test_security_owner_construction_is_centralized() -> None:
    allowed = {
        Path('security/owner_factory.py'),
        Path('observability/immutable_event_store.py'),
    }
    roots = [Path('app/web'), Path('entrypoints/api')]
    forbidden = (
        'SecurityIntegrationAdapter(',
        'SecurityPolicyEngine(',
        'SecurityAuditLog(',
        'ImmutableEventStore(',
    )
    for root in roots:
        for path in root.glob('*.py'):
            if path in allowed:
                continue
            text = path.read_text(encoding='utf-8')
            for pattern in forbidden:
                assert pattern not in text, f"{path} must build security infrastructure only via security.owner_factory, not {pattern}"


def test_web_and_api_use_owner_factory_for_default_security_adapter() -> None:
    web_text = Path('app/web/app.py').read_text(encoding='utf-8')
    api_text = Path('entrypoints/api/security_owner_bundle.py').read_text(encoding='utf-8')
    assert 'build_default_security_adapter(' in web_text
    assert 'build_security_infrastructure(' in api_text
