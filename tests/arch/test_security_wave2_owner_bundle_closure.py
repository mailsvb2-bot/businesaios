from __future__ import annotations

from pathlib import Path


def test_security_owner_bundle_exposes_closure_surfaces() -> None:
    text = Path('security/__init__.py').read_text(encoding='utf-8')
    assert 'SQLiteKMSProvider' in text
    assert 'SecurityDrillExecutor' in text
    assert 'build_security_governance_infrastructure' in text


def test_governance_factory_registers_canonical_kms_providers() -> None:
    text = Path('security/governance_owner_factory.py').read_text(encoding='utf-8')
    assert 'KMSProviderRegistry' in text
    assert 'InMemoryKMSProvider' in text
    assert 'SQLiteKMSProvider' in text
