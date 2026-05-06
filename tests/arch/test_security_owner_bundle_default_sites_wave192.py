from pathlib import Path


def test_api_security_owner_bundle_default_is_confined_to_canonical_sites() -> None:
    root = Path(__file__).resolve().parents[2]
    allowed = {
        'bootstrap/security_boot_surface.py',
        'adapters/api/fastapi/dependencies.py',
        'adapters/api/fastapi/router_adapter.py',
    }
    hits: list[str] = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root).as_posix()
        if rel.startswith('tests/'):
            continue
        text = path.read_text(encoding='utf-8')
        if 'ApiSecurityOwnerBundle.default(' in text:
            hits.append(rel)
    assert set(hits) == allowed, f'Unexpected ApiSecurityOwnerBundle.default construction sites: {sorted(set(hits) - allowed)}'
