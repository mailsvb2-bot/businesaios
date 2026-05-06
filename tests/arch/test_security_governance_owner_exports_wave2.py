from __future__ import annotations

from pathlib import Path


def test_security_governance_owner_exports_present() -> None:
    root = Path(__file__).resolve().parents[2]
    init_text = (root / 'security' / '__init__.py').read_text(encoding='utf-8')
    assert 'SecurityGovernanceOrchestrator' in init_text
    assert 'SQLiteSecurityQuarantineRegistry' in init_text
    assert 'InMemoryKMSProvider' in init_text
