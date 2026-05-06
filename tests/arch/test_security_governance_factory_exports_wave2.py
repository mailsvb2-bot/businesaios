from __future__ import annotations

from pathlib import Path


def test_security_governance_factory_exports_present() -> None:
    init_text = Path('security/__init__.py').read_text(encoding='utf-8')
    factory_text = Path('security/governance_owner_factory.py').read_text(encoding='utf-8')

    assert 'build_security_governance_infrastructure' in init_text
    assert 'SecurityGovernanceInfrastructureOwner' in init_text
    assert 'CANON_SECURITY_GOVERNANCE_OWNER_FACTORY' in init_text
    assert 'SecurityGovernanceOrchestrator(' in factory_text
    assert 'SecurityAuditExportService(' in factory_text
